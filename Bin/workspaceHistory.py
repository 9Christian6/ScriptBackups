#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import sys
import i3ipc
from pynput import keyboard

class WorkspaceHistory:
    def __init__(self):
        self.i3 = i3ipc.Connection()
        self.history = []
        self.current_index = -1
        self.ignore_next_event = False

        # Initialize history with the currently focused workspace
        focused = self.i3.get_tree().find_focused()
        if focused and focused.workspace():
            self.history.append(focused.workspace().name)
            self.current_index = 0
            print(f"Initialized history: {self.history}")

    def on_workspace_focus(self, i3, e):
        if not e.current:
            return

        new_name = e.current.num

        # Ignore events triggered by our own history navigation
        if self.ignore_next_event:
            self.ignore_next_event = False
            return

        # Ignore if effectively on the same workspace
        if self.history and self.history[self.current_index] == new_name:
            return

        # -- LOGIC FOR MANUAL SWITCH --
        # If we went back in history and then manually switched, truncate future
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]

        self.history.append(new_name)
        self.current_index = len(self.history) - 1

        # Limit history size to 100
        if len(self.history) > 100:
            self.history.pop(0)
            self.current_index -= 1

        print(f"Manual Switch. Stack: {self.history} | Index: {self.current_index}")

    def go_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            target_ws = self.history[self.current_index]
            print(f"<-- GO BACK to: {target_ws}")
            self.switch_to(target_ws)

    def go_forward(self):
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            target_ws = self.history[self.current_index]
            print(f"--> GO FORWARD to: {target_ws}")
            self.switch_to(target_ws)

    def switch_to(self, ws_number):
        self.ignore_next_event = True
        self.i3.command(f'workspace number "{ws_number}"')

def main():
    history_manager = WorkspaceHistory()

    # --- SETUP HOTKEYS (pynput) ---
    # <cmd> maps to the Super/Windows key
    hotkeys = keyboard.GlobalHotKeys({
        '<cmd>+o': history_manager.go_back,
        '<cmd>+i': history_manager.go_forward
    })

    # Start the hotkey listener in a non-blocking way
    hotkeys.start()
    print("Listening for Super+o / Super+i...")

    # --- SETUP I3 LISTENER ---
    history_manager.i3.on(i3ipc.Event.WORKSPACE_FOCUS, history_manager.on_workspace_focus)

    # Start the blocking i3 loop
    try:
        history_manager.i3.main()
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
