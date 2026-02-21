#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOCKET_PATH = SCRIPT_DIR / "workspace_history.sock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Client for i3 workspace history server")
    parser.add_argument(
        "command",
        choices=["back", "forward", "status"],
        help="Navigation command",
    )
    parser.add_argument(
        "--socket-path",
        type=Path,
        default=DEFAULT_SOCKET_PATH,
        help=f"UNIX socket path (default: {DEFAULT_SOCKET_PATH})",
    )
    return parser.parse_args()


def send_command(socket_path: Path, command: str) -> str:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(socket_path))
        client.sendall((command + "\n").encode("utf-8"))
        return client.recv(4096).decode("utf-8", errors="ignore").strip()


def main() -> int:
    args = parse_args()

    if not args.socket_path.exists():
        print(f"error: socket not found at {args.socket_path}", file=sys.stderr)
        return 1

    try:
        response = send_command(args.socket_path, args.command)
    except FileNotFoundError:
        print(f"error: socket not found at {args.socket_path}", file=sys.stderr)
        return 1
    except ConnectionRefusedError:
        print("error: server is not accepting connections", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: failed to talk to server: {exc}", file=sys.stderr)
        return 1

    if response.startswith("error:"):
        print(response, file=sys.stderr)
        return 1

    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
