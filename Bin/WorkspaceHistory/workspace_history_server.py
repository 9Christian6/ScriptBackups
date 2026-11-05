#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
from __future__ import annotations

import argparse
import atexit
import json
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import i3ipc


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOCKET_PATH = SCRIPT_DIR / "workspace_history.sock"
DEFAULT_HISTORY_LOG_PATH = SCRIPT_DIR / "workspaceHistory"
DEFAULT_STATE_PATH = SCRIPT_DIR / "workspace_history_state.json"
MAX_HISTORY_LOG_BYTES = 1 * 1024 * 1024


def _canonical_outputs(outputs: dict[str, int]) -> dict[str, int]:
    return {name: outputs[name] for name in sorted(outputs)}


class WorkspaceHistoryServer:
    def __init__(
            self,
            socket_path: Path,
            history_log_path: Path,
            state_path: Path,
            ) -> None:
        self.socket_path = socket_path
        self.history_log_path = history_log_path
        self.state_path = state_path

        self.history: list[dict[str, Any]] = []
        self.index: int = -1
        self.suppress_target_snapshot: dict[str, Any] | None = None

        self.i3 = i3ipc.Connection()
        self.server_socket: socket.socket | None = None
        self.lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()

    def run(self) -> None:
        self._prepare_files()
        self._load_persisted_state()
        self._sync_with_current_workspace()
        self._write_state()

        socket_thread = threading.Thread(
                target=self._socket_loop,
                name="workspace-history-socket",
                daemon=True,
                )
        socket_thread.start()

        self.i3.on("workspace::focus", self._on_workspace_focus)
        self.i3.on("shutdown", self._on_i3_shutdown)

        try:
            self.i3.main()
        finally:
            self.running.clear()
            socket_thread.join(timeout=1.0)
            self._cleanup_socket()

    def _prepare_files(self) -> None:
        self.history_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        self.history_log_path.touch(exist_ok=True)

        if self.socket_path.exists():
            self.socket_path.unlink()

        atexit.register(self._cleanup_socket)

    def _cleanup_socket(self) -> None:
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass

    def _load_persisted_state(self) -> None:
        loaded = self._load_from_state_file()
        if not loaded:
            self._load_from_history_file()

        self._enforce_history_log_size()

    def _load_from_state_file(self) -> bool:
        if not self.state_path.exists():
            return False

        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False

        history_raw = raw.get("history")
        index_raw = raw.get("index")

        if not isinstance(history_raw, list):
            return False

        loaded_history: list[dict[str, Any]] = []
        for item in history_raw:
            parsed = self._parse_snapshot(item)
            if parsed is None:
                return False
            loaded_history.append(parsed)

        if not loaded_history:
            self.history = []
            self.index = -1
            return True

        if not isinstance(index_raw, int):
            return False

        if index_raw < 0:
            self.history = []
            self.index = -1
            return True

        if index_raw >= len(loaded_history):
            return False

        self.history = loaded_history
        self.index = index_raw
        return True

    def _load_from_history_file(self) -> None:
        self.history = []
        self.index = -1

        try:
            lines = self.history_log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return

        for line in lines:
            if "\t" not in line:
                continue
            fields = line.split("\t")
            if len(fields) < 2:
                continue
            workspace_num = self._parse_workspace_number(fields[1].strip())
            if workspace_num is None:
                continue

            outputs: dict[str, int] = {}
            if len(fields) >= 3:
                try:
                    raw_outputs = json.loads(fields[2])
                    parsed_outputs = self._parse_outputs_map(raw_outputs)
                    if parsed_outputs is not None:
                        outputs = parsed_outputs
                except json.JSONDecodeError:
                    pass

            # Legacy fallback: focused-only snapshots if no output map is available.
            snapshot = {"focused_workspace": workspace_num, "outputs": _canonical_outputs(outputs)}
            if self.history and self.history[-1] == snapshot:
                continue
            self.history.append(snapshot)

        if self.history:
            self.index = len(self.history) - 1

    def _sync_with_current_workspace(self) -> None:
        current = self._get_current_snapshot()
        if current is None:
            return

        if self.index >= 0 and self.index < len(self.history) and self.history[self.index] == current:
            return

        self._record_snapshot(current)

    def _get_current_snapshot(self) -> dict[str, Any] | None:
        workspaces = self.i3.get_workspaces()
        focused_workspace = None
        outputs: dict[str, int] = {}

        for workspace in workspaces:
            workspace_num = self._workspace_num_from_event(workspace)
            if workspace_num is None:
                continue

            output_name = getattr(workspace, "output", None)
            if isinstance(output_name, str) and output_name and getattr(workspace, "visible", False):
                outputs[output_name] = workspace_num

            if getattr(workspace, "focused", False):
                focused_workspace = workspace_num

        if focused_workspace is None:
            return None

        return {
                "focused_workspace": focused_workspace,
                "outputs": _canonical_outputs(outputs),
                }

    def _record_snapshot(self, snapshot: dict[str, Any]) -> None:
        # Ignore duplicate focus events for the current history position.
        # This must run before branch truncation so replayed events after a
        # back/forward navigation do not accidentally erase forward history.
        if 0 <= self.index < len(self.history) and self.history[self.index] == snapshot:
            self._write_state()
            return

        if self.index < len(self.history) - 1:
            self.history = self.history[: self.index + 1]

        if self.history and self.history[-1] == snapshot:
            self.index = len(self.history) - 1
            self._write_state()
            return

        self.history.append(snapshot)
        self.index = len(self.history) - 1

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.history_log_path.open("a", encoding="utf-8") as file_handle:
            outputs_json = json.dumps(snapshot["outputs"], ensure_ascii=True, sort_keys=True)
            file_handle.write(f"{timestamp}\t{snapshot['focused_workspace']}\t{outputs_json}\n")

        self._enforce_history_log_size()
        self._write_state()

    def _enforce_history_log_size(self) -> None:
        try:
            if self.history_log_path.stat().st_size <= MAX_HISTORY_LOG_BYTES:
                return
        except OSError:
            return

        try:
            raw = self.history_log_path.read_bytes()
        except OSError:
            return

        lines = raw.splitlines(keepends=True)

        kept_lines: list[bytes] = []
        total_size = 0
        for line in reversed(lines):
            line_size = len(line)
            if total_size + line_size > MAX_HISTORY_LOG_BYTES:
                break
            kept_lines.append(line)
            total_size += line_size

        kept_lines.reverse()

        try:
            self.history_log_path.write_bytes(b"".join(kept_lines))
        except OSError:
            return

    def _write_state(self) -> None:
        state = {
                "history": self.history,
                "index": self.index,
                "current": self.history[self.index]["focused_workspace"] if 0 <= self.index < len(self.history) else None,
                "can_go_back": self.index > 0,
                "can_go_forward": self.index < len(self.history) - 1,
                }
        with self.state_path.open("w", encoding="utf-8") as file_handle:
            json.dump(state, file_handle, ensure_ascii=True, indent=2)
            file_handle.write("\n")

    def _socket_loop(self) -> None:
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(8)
        self.server_socket.settimeout(0.5)

        while self.running.is_set():
            try:
                conn, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            with conn:
                try:
                    raw = conn.recv(1024)
                except OSError:
                    continue

                command = raw.decode("utf-8", errors="ignore").strip().lower()
                response = self._handle_client_command(command)
                try:
                    conn.sendall((response + "\n").encode("utf-8"))
                except OSError:
                    pass

    def _handle_client_command(self, command: str) -> str:
        with self.lock:
            if command == "back":
                return self._navigate(-1)
            if command == "forward":
                return self._navigate(+1)
            if command == "status":
                return self._status_string()
            return "error: unsupported command"

    def _navigate(self, delta: int) -> str:
        target_index = self.index + delta
        if target_index < 0 :
            subprocess.run(["notify-send", "Lower boundary reached"])
            return "error: lower boundary reached"
        if target_index >= len(self.history):
            subprocess.run(["notify-send", "Upper boundary reached"])
            return "error: upper boundary reached"

        target_snapshot = self.history[target_index]
        self.index = target_index
        self.suppress_target_snapshot = target_snapshot
        self._write_state()

        # Restore visible workspaces on outputs first, then focused workspace last.
        for output_name, workspace_num in target_snapshot["outputs"].items():
            escaped_output_name = output_name.replace('"', '\\"')
            self.i3.command(f'focus output "{escaped_output_name}"; workspace number {workspace_num}')
        self.i3.command(f"workspace number {target_snapshot['focused_workspace']}")
        return f"ok: {target_snapshot['focused_workspace']}"

    def _status_string(self) -> str:
        if self.index < 0 or self.index >= len(self.history):
            return "status: empty"
        current = self.history[self.index]
        return (
                f"status: current={current['focused_workspace']} "
                f"index={self.index} size={len(self.history)}"
                )

    def _on_workspace_focus(self, _i3: i3ipc.Connection, _event: Any) -> None:
        current_snapshot = self._get_current_snapshot()
        if current_snapshot is None:
            return

        with self.lock:
            if self.suppress_target_snapshot is not None:
                if current_snapshot == self.suppress_target_snapshot:
                    self.suppress_target_snapshot = None
                return

            self._record_snapshot(current_snapshot)

    def _workspace_num_from_event(self, workspace_obj: Any) -> int | None:
        if workspace_obj is None:
            return None

        number = getattr(workspace_obj, "num", None)
        if isinstance(number, int) and number >= 0:
            return number

        name = getattr(workspace_obj, "name", None)
        if isinstance(name, str):
            return self._parse_workspace_number(name)

        return None

    def _parse_workspace_number(self, raw_value: str) -> int | None:
        if not raw_value:
            return None

        if raw_value.isdigit():
            return int(raw_value)

        match = re.match(r"^\s*(\d+)", raw_value)
        if match is None:
            return None
        return int(match.group(1))

    def _on_i3_shutdown(self, _i3: i3ipc.Connection, _event: Any) -> None:
        self.running.clear()

    def _parse_snapshot(self, raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None

        focused_raw = raw.get("focused_workspace")
        if not isinstance(focused_raw, int) or focused_raw < 0:
            return None

        outputs = self._parse_outputs_map(raw.get("outputs"))
        if outputs is None:
            return None

        return {
                "focused_workspace": focused_raw,
                "outputs": _canonical_outputs(outputs),
                }

    def _parse_outputs_map(self, raw: Any) -> dict[str, int] | None:
        if not isinstance(raw, dict):
            return None

        outputs: dict[str, int] = {}
        for output_name, workspace_num in raw.items():
            if not isinstance(output_name, str) or not output_name:
                return None
            if not isinstance(workspace_num, int) or workspace_num < 0:
                return None
            outputs[output_name] = workspace_num
        return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="i3 workspace history server")
    parser.add_argument(
            "--socket-path",
            type=Path,
            default=DEFAULT_SOCKET_PATH,
            help=f"UNIX socket path (default: {DEFAULT_SOCKET_PATH})",
            )
    parser.add_argument(
            "--history-file",
            type=Path,
            default=DEFAULT_HISTORY_LOG_PATH,
            help=f"History log file path (default: {DEFAULT_HISTORY_LOG_PATH})",
            )
    parser.add_argument(
            "--state-file",
            type=Path,
            default=DEFAULT_STATE_PATH,
            help=f"State file path (default: {DEFAULT_STATE_PATH})",
            )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = WorkspaceHistoryServer(
            socket_path=args.socket_path,
            history_log_path=args.history_file,
            state_path=args.state_file,
            )

    try:
        server.run()
    except KeyboardInterrupt:
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"workspace history server failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
