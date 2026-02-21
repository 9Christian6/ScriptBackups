#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
from __future__ import annotations

import argparse
import atexit
import json
import socket
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

        self.history: list[str] = []
        self.index: int = -1
        self.suppress_expected_workspace: str | None = None

        self.i3 = i3ipc.Connection()
        self.server_socket: socket.socket | None = None
        self.lock = threading.Lock()
        self.running = threading.Event()
        self.running.set()

    def run(self) -> None:
        self._prepare_files()
        self._capture_initial_workspace()
        self._write_state()

        socket_thread = threading.Thread(target=self._socket_loop, name="workspace-history-socket", daemon=True)
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

    def _capture_initial_workspace(self) -> None:
        current = self._get_current_workspace_name()
        if current is None:
            return
        self._record_workspace_switch(current)

    def _get_current_workspace_name(self) -> str | None:
        tree = self.i3.get_tree()
        focused = tree.find_focused()
        if focused is None:
            return None
        workspace = focused.workspace()
        if workspace is None:
            return None
        return workspace.name

    def _record_workspace_switch(self, workspace_name: str) -> None:
        if self.index < len(self.history) - 1:
            self.history = self.history[: self.index + 1]

        self.history.append(workspace_name)
        self.index = len(self.history) - 1

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with self.history_log_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(f"{timestamp}\t{workspace_name}\n")

        self._write_state()

    def _write_state(self) -> None:
        state = {
                "history": self.history,
                "index": self.index,
                "current": self.history[self.index] if 0 <= self.index < len(self.history) else None,
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
        if target_index < 0 or target_index >= len(self.history):
            return "error: boundary reached"

        target_workspace = self.history[target_index]
        self.index = target_index
        self.suppress_expected_workspace = target_workspace
        self._write_state()

        self.i3.command(f'workspace "{target_workspace}"')
        return f"ok: {target_workspace}"

    def _status_string(self) -> str:
        if self.index < 0 or self.index >= len(self.history):
            return "status: empty"
        return (
                f"status: current={self.history[self.index]!r} "
                f"index={self.index} size={len(self.history)}"
                )

    def _on_workspace_focus(self, _i3: i3ipc.Connection, event: Any) -> None:
        current_workspace = event.current.name if event.current is not None else None
        if current_workspace is None:
            return

        with self.lock:
            if self.suppress_expected_workspace is not None:
                if current_workspace == self.suppress_expected_workspace:
                    self.suppress_expected_workspace = None
                    return
                self.suppress_expected_workspace = None

            self._record_workspace_switch(current_workspace)

    def _on_i3_shutdown(self, _i3: i3ipc.Connection, _event: Any) -> None:
        self.running.clear()


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
