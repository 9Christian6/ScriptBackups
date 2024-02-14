#!/usr/bin/python

# This script requires i3ipc-python package (install it from a system package manager
# or pip).
# It makes inactive windows transparent. Use `transparency_val` variable to control
# transparency strength in range of 0…1 or use the command line argument -o.

import argparse
import i3ipc
import signal
import sys
import psutil
import fcntl
import os
from functools import partial

alwaysOpaque = ["feh", "Okular", "YouTube", "Twitch", "nvim", "Discord"]

def isExcluded(name):
    for excludedName in alwaysOpaque:
        if excludedName in name:
            return True

def on_window_focus(inactive_opacity, ipc, event):
    global prev_focused
    global prev_workspace

    focused_workspace = ipc.get_tree().find_focused()

    if focused_workspace == None:
        return

    focused = event.container
    workspace = focused_workspace.workspace().num

    if focused.id != prev_focused.id:  # https://github.com/swaywm/sway/issues/2859
        focused.command("opacity 1")
        if workspace == prev_workspace:
            prev_focused.command("opacity " + inactive_opacity)
            if isExcluded(prev_focused.name):
                prev_focused.command("opacity 1.0")
                #prev_focused.command("opacity 0.90")
        prev_focused = focused
        prev_workspace = workspace


def remove_opacity(ipc):
    for workspace in ipc.get_tree().workspaces():
        for w in workspace:
            w.command("opacity 1")
    ipc.main_quit()
    sys.exit(0)

def instance_already_running(label="default"):
    """
    Detect if an an instance with the label is already running, globally
    at the operating system level.

    Using `os.open` ensures that the file pointer won't be closed
    by Python's garbage collector after the function's scope is exited.

    The lock will be released when the program exits, or could be
    released if the file pointer were closed.
    """

    lock_file_pointer = os.open(f"/tmp/instance_{label}.lock", os.O_WRONLY)

    try:
        fcntl.lockf(lock_file_pointer, fcntl.LOCK_EX | fcntl.LOCK_NB)
        already_running = False
    except IOError:
        already_running = True

    return already_running

if __name__ == "__main__":
    transparency_val = "0.80"

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
    prev_focused = None
    prev_workspace = ipc.get_tree().find_focused().workspace().num

    for window in ipc.get_tree():
        if window.focused:
            prev_focused = window
        else:
            window.command("opacity " + args.opacity)
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, lambda signal, frame: remove_opacity(ipc))
    ipc.on("window::focus", partial(on_window_focus, args.opacity))
    ipc.main()
