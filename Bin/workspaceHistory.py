#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3

import sys
import json
import os
import tempfile
import i3ipc

STATE_FILE = "/tmp/i3_workspace_history.json"
MAX_HISTORY = 100


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"history": [], "index": -1}

    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"history": [], "index": -1}


def save_state(state):
    # atomic write
    fd, tmp = tempfile.mkstemp(dir="/tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)

    os.replace(tmp, STATE_FILE)


def current_workspace(i3):
    focused = i3.get_tree().find_focused()
    if focused and focused.workspace():
        return focused.workspace().num
    return None


# -----------------------------------------------------------

def record():
    i3 = i3ipc.Connection()
    state = load_state()

    ws = current_workspace(i3)
    if ws is None:
        return

    history = state["history"]
    idx = state["index"]

    # ignore duplicate
    if history and idx >= 0 and history[idx] == ws:
        return

    # truncate future
    if idx < len(history) - 1:
        history = history[: idx + 1]

    history.append(ws)
    idx = len(history) - 1

    if len(history) > MAX_HISTORY:
        history.pop(0)
        idx -= 1

    save_state({"history": history, "index": idx})


def go(delta):
    i3 = i3ipc.Connection()
    state = load_state()

    history = state["history"]
    idx = state["index"]

    if not history:
        return

    new_idx = idx + delta

    if new_idx < 0 or new_idx >= len(history):
        return

    target = history[new_idx]

    i3.command(f'workspace number "{target}"')

    save_state({"history": history, "index": new_idx})


# -----------------------------------------------------------

def usage():
    print("usage: workspace_history.py record|back|forward")
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        usage()

    cmd = sys.argv[1]

    if cmd == "record":
        record()
    elif cmd == "back":
        go(-1)
    elif cmd == "forward":
        go(1)
    else:
        usage()


if __name__ == "__main__":
    main()
