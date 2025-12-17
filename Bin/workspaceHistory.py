#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
"""
Scaffold for an i3 workspace history helper.

Goals:
- Track recently focused workspaces.
- Persist history to disk between sessions.
- Provide simple CLI for navigating backwards/forwards.

Implementation notes:
- Uses only stdlib; calls `i3-msg` via subprocess. Swap with `i3ipc` if preferred.
- All TODOs are intentional placeholders for your project-specific behavior.
"""

from __future__ import annotations
import subprocess
import sys
from collections import deque
from typing import Deque, Optional, Sequence
from i3ipc import Connection, Event


class i3Event:

    def __init__(self):
        self.listeners = []

    def subscribe(self, listener):
        self.listeners.append(listener)

    def unsubscribe(self, listener):
        self.listeners.remove(listener)

    def trigger(self, *args, **kwargs):
        for listener in self.listeners:
            listener(*args, **kwargs)


stack = deque()  # type: Deque[str]
commandWasFromHistory = False


def print_stack():
    print('The current stack is:')
    print(stack)
    print('')


def on_event_fired(message):
    print(f"Event triggered with message: {message}")


# Detect the Windows (Mod4) + o key combo via i3 binding events.
def on_binding_event(i3_conn: Connection, event: Event) -> None:
    """
    i3 must have a binding for $mod+o (e.g., `bindsym $mod+o nop`) so the
    binding event is emitted. This handler only logs detection for now.
    """
    binding = getattr(event, "binding", None)
    if not binding:
        return
    # Some setups populate `binding.symbols`; others only set `binding.symbol`.
    symbols = list(getattr(binding, "symbols", []) or [])
    symbol = getattr(binding, "symbol", None)
    mods = getattr(binding, "mods", []) or []

    # Debug print to see what the binding looks like when symbols are empty.
    if not symbols and symbol:
        symbols.append(symbol)
    if not symbols:
        print(f"Binding had no symbols; raw binding: {binding}")
        return

    if "o" in symbols and ("Mod4" in mods or "Mod4Mask" in mods):
        print('o was pressed')
        print_stack()
        if len(stack) > 0:
            focus_workspace(stack.pop())
        print('workspace was focused')
        print_stack()


# ---------- Helpers for talking to i3 ----------


def run_i3_msg(command: Sequence[str]) -> str:
    """Run `i3-msg` and return stdout as text."""
    completed = subprocess.run(
        ["i3-msg", *command],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def focus_workspace(name: str) -> None:
    """Focus a workspace by name."""
    global commandWasFromHistory
    commandWasFromHistory = True
    run_i3_msg([f'workspace number "{name}"'])


# Define a callback to be called when you switch workspaces.
def on_workspace_focus(self, e):
    global commandWasFromHistory
    # The first parameter is the connection to the ipc and the second is an object
    # with the data of the event sent from i3.
    if not commandWasFromHistory:
        stack.append(e.old.num)
        print('appended ' + str(e.old.num))
        if stack.__len__() > 500:
            stack.popleft()
    commandWasFromHistory = False
    print_stack()


def main(argv: Optional[Sequence[str]] = None) -> int:
    return 0


if __name__ == "__main__":
    # Example usages:
    #   python workspaceHistory.py add-current
    #   python workspaceHistory.py back
    # Hook these up to i3 bindings as desired.
    i3 = Connection()
# Print the name of the focused window
focused = i3.get_tree().find_focused()
print('Focused window %s is on workspace %s' %
      (focused.name, focused.workspace().name))
# Query the ipc for outputs. The result is a list that represents the parsed
# reply of a command like `i3-msg -t get_outputs`.
outputs = i3.get_outputs()
print('Active outputs:')
for output in filter(lambda o: o.active, outputs):
    print(output.name)
# Subscribe to events
i3.on(Event.WORKSPACE_FOCUS, on_workspace_focus)
i3.on(Event.BINDING, on_binding_event)

# Start the main loop and wait for events to come in.
i3.main()
sys.exit(main())
