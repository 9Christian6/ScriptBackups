#!/usr/bin/python3
"""Clear i3 urgency during login without changing focus or workspaces."""

import argparse
import subprocess
import time

import i3ipc


def clear_urgent_windows(connection):
    for window in connection.get_tree().leaves():
        if not window.urgent or not window.window:
            continue
        window_id = str(window.window)
        # Clear both ICCCM urgency and EWMH attention requests. Updating
        # WM_HINTS also clears urgency that i3 set for an activation request.
        # A window may close between reading the tree and running these commands.
        subprocess.run(
            ["xdotool", "set_window", "--urgency", "0", window_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        subprocess.run(
            ["wmctrl", "-i", "-r", window_id, "-b", "remove,demands_attention"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seconds", type=float, default=90,
        help="startup cleanup duration (default: 90 seconds; 0 clears once)",
    )
    args = parser.parse_args()
    if args.seconds < 0:
        parser.error("--seconds must be nonnegative")

    connection = i3ipc.Connection()
    deadline = time.monotonic() + args.seconds
    while True:
        clear_urgent_windows(connection)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(1, remaining))


if __name__ == "__main__":
    main()
