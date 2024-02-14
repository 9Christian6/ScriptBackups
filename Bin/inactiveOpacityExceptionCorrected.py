import argparse
import i3ipc
import signal
import sys
import psutil
import fcntl
import os
from functools import partial

alwaysOpaque = ["YouTube", "Twitch", "nvim"]

def isExcluded(name):
    for excludedName in alwaysOpaque:
        if excludedName in name:
            return True
    return False

def on_window_focus(inactive_opacity, ipc, event):
    global prev_focused
    global prev_workspace

    focused_workspace = ipc.get_tree().find_focused()

    if focused_workspace is None:
        return

    focused = event.container
    workspace = focused_workspace.workspace()

    if focused.id != prev_focused.id:
        focused.command("opacity 1")

        if workspace.num == prev_workspace and focused_workspace.name != prev_focused_workspace:
            prev_focused.command("opacity " + inactive_opacity)
            if isExcluded(prev_focused.name):
                prev_focused.command("opacity 0.90")

        prev_focused = focused
        prev_workspace = workspace.num
        prev_focused_workspace = focused_workspace.name

def remove_opacity(ipc):
    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            w.command("opacity 1")
    ipc.main_quit()
    sys.exit(0)

def instance_already_running(label="default"):
    # The implementation of this function seems to be missing in the provided script.
    # Make sure you implement this function to detect if another instance is already running.
    pass

if __name__ == "__main__":
    transparency_val = "0.80"

    # Uncomment the lines below to check if another instance is already running.
    # if instance_already_running():
    #     sys.exit('Instance already running')

    for process in psutil.process_iter():
        if process.cmdline() == ['python', 'inactiveOpacityException.py']:
            sys.exit('Process found: exiting.')

    parser = argparse.ArgumentParser(
        description="This script allows you to set the transparency of unfocused windows in sway."
    )
    parser.add_argument(
        "--opacity",
        "-o",
        type=str,
        default=transparency_val,
        help="set opacity value in range 0...1",
    )
    args = parser.parse_args()

    ipc = i3ipc.Connection()
    prev_focused = ipc.get_tree().find_focused()
    prev_workspace = prev_focused.workspace().num
    prev_focused_workspace = prev_focused.workspace().name

    for window in ipc.get_tree():
        if not window.focused:
            window.command("opacity " + args.opacity)

    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: remove_opacity(ipc))

    ipc.on("window::focus", partial(on_window_focus, args.opacity))
    ipc.main()
