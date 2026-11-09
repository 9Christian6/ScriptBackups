#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
"""Merge Brave windows or split the focused tab into a new window under i3.

Usage: brotabControle.py left|right|up|down|split [--dry-run]
The short directions l/r/u/d also work. Requires i3ipc, brotab (with the
browser extension connected), and xdotool. Moving the last tab closes the
source window. A directional dry run briefly focuses both windows to identify them,
then restores the original focus without moving any tabs.
After merging, the previously selected source tab is selected in the destination.
Inactive tabs are moved first so they are not selected in the source window.
The split command moves only the selected tab, preserving its page state
and history, and focuses the new window.
"""

import argparse
import shutil
import subprocess
import sys
import time
from uuid import uuid4
from urllib.parse import quote_plus
from urllib.request import urlopen

import i3ipc


BRAVE_CLASS = "brave-browser"
TIMEOUT = 2.0
COMMAND_TIMEOUT = 5.0
POLL_INTERVAL = 0.05
SIDE_ALIASES = {"l": "left", "r": "right", "u": "up", "d": "down"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "side", choices=("left", "right", "up", "down", *SIDE_ALIASES, "split"),
        help="Destination direction, or 'split' to detach the focused tab.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report the action without creating windows or moving tabs.",
    )
    return parser.parse_args(argv)


def ensure_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} is not available in PATH.")
    return path


def run_command(*args: str, input_text: str | None = None) -> str:
    """Keep a stalled desktop command from leaving the shortcut hanging."""
    result = subprocess.run(
        args, input=input_text, capture_output=True, text=True, check=True,
        timeout=COMMAND_TIMEOUT,
    )
    return result.stdout


def get_tab_ids(output: str) -> list[str]:
    """Read IDs from Brotab's tab-separated rows, keeping browser tab order."""
    tabs = []
    for line in output.splitlines():
        if not line.strip():
            continue
        tab_id = line.split("\t", 1)[0].strip()
        parts = tab_id.split(".")
        if len(parts) != 3 or not parts[0] or not all(p.isdecimal() for p in parts[1:]):
            raise RuntimeError(f"Invalid Brotab tab ID: {tab_id!r}.")
        tabs.append(tab_id)
    return tabs


def tab_to_window_id(tab_id: str) -> str:
    # Brotab IDs contain a client prefix, browser window ID, and tab ID.
    # The browser window ID alone is not unique across different clients.
    return tab_id.rsplit(".", 1)[0]


def get_brotab_clients(brotab_path: str) -> dict[str, str]:
    clients = {}
    for line in run_command(brotab_path, "clients").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            raise RuntimeError(f"Invalid Brotab client row: {line!r}.")
        clients[parts[0].strip().rstrip(".")] = parts[1].strip()
    return clients


def is_brave_window(node: i3ipc.Con) -> bool:
    return bool(node.window) and BRAVE_CLASS in {
        (node.window_class or "").lower(), (node.window_instance or "").lower(),
    }


def center(node: i3ipc.Con) -> tuple[float, float]:
    rect = node.rect
    return rect.x + rect.width / 2, rect.y + rect.height / 2


def choose_target_window(source, candidates, side):
    """Prefer an aligned neighbor, then distance in the requested direction."""
    sx, sy = center(source)
    horizontal = side in {"left", "right"}
    direction = -1 if side in {"left", "up"} else 1

    def rank(node):
        tx, ty = center(node)
        along = (tx - sx) if horizontal else (ty - sy)
        across = (ty - sy) if horizontal else (tx - sx)
        a, b = source.rect, node.rect
        # Overlapping vertical spans make a better left/right neighbor;
        # overlapping horizontal spans make a better up/down neighbor.
        if horizontal:
            overlap = max(a.y, b.y) < min(a.y + a.height, b.y + b.height)
        else:
            overlap = max(a.x, b.x) < min(a.x + a.width, b.x + b.width)
        return not overlap, direction * along, abs(across), node.id

    directional = []
    for node in candidates:
        tx, ty = center(node)
        along = (tx - sx) if horizontal else (ty - sy)
        if node.id != source.id and direction * along > 0:
            directional.append(node)
    return min(directional, key=rank, default=None)


def focus_window(i3, xdotool_path, node):
    replies = i3.command(f"[con_id={node.id}] focus")
    if not replies or not all(reply.success for reply in replies):
        raise RuntimeError(f"Could not focus Brave window {node.name!r}.")
    # Synchronize X11's active window with i3 before querying the extension.
    run_command(xdotool_path, "windowactivate", "--sync", str(node.window))


def focus_and_get_tab(i3, brotab_path, xdotool_path, node, exclude=None):
    """Identify the selected tab of a specific i3/X11 window."""
    focus_window(i3, xdotool_path, node)
    deadline = time.monotonic() + TIMEOUT
    previous = None
    while time.monotonic() < deadline:
        active = int(run_command(xdotool_path, "getactivewindow").strip())
        if active != node.window:
            raise RuntimeError("Window focus changed while identifying Brave windows; try again.")
        tabs = get_tab_ids(run_command(brotab_path, "query", "+active", "+windowFocused"))
        # `active` alone means the selected tab in EVERY browser window.
        # Taking its first row can silently merge the wrong windows. Require
        # one focused result, stable across two polls, instead of guessing.
        window_id = tab_to_window_id(tabs[0]) if len(tabs) == 1 else None
        if window_id and window_id != exclude:
            if tabs[0] == previous:
                return tabs[0]
            previous = tabs[0]
        else:
            previous = None
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(
        f"Timed out identifying Brave window {node.name!r}. "
        "Check that its Brotab extension is connected."
    )


def focus_and_map_window(i3, brotab_path, xdotool_path, node, exclude=None):
    """Map an i3/X11 window to a Brotab window by focusing it first."""
    return tab_to_window_id(
        focus_and_get_tab(i3, brotab_path, xdotool_path, node, exclude=exclude)
    )


def move_tabs_via_brotab_api(
    clients, tab_ids, target_window_id, target_index_start, *, selected_tab=None,
):
    """Append tabs in their existing order, moving the selected tab last."""
    if not tab_ids:
        return
    prefix, window_id = target_window_id.split(".")
    if any(tab_id.split(".")[0] != prefix for tab_id in tab_ids):
        raise RuntimeError("Source and target windows belong to different Brotab clients.")
    if any(tab_to_window_id(tab_id) == target_window_id for tab_id in tab_ids):
        raise RuntimeError("Source and target resolve to the same Brotab window.")
    if prefix not in clients:
        raise RuntimeError(f"No Brotab client found for prefix {prefix!r}.")
    if selected_tab is not None and selected_tab not in tab_ids:
        raise RuntimeError("The selected tab is not among the tabs to move.")
    # `brotab move` launches an editor; positional arguments do not move tabs.
    # Its underlying API takes comma-separated `tabID windowID index` triplets.
    # Leave the selected tab in the source until all its neighbors are gone.
    # Otherwise Brave selects a neighbor on detach, loading unopened videos.
    # Append the inactive tabs, then insert the selected tab at its original
    # relative position to preserve the final order in the destination.
    inactive_tabs = [tab_id for tab_id in tab_ids if tab_id != selected_tab]
    moves = [(tab_id, target_index_start + offset)
             for offset, tab_id in enumerate(inactive_tabs)]
    if selected_tab is not None:
        moves.append((selected_tab, target_index_start + tab_ids.index(selected_tab)))
    commands = ",".join(
        f"{int(tab_id.rsplit('.', 1)[1])} {int(window_id)} {index}"
        for tab_id, index in moves
    )
    url = f"http://{clients[prefix]}/move_tabs/{quote_plus(commands)}"
    with urlopen(url, timeout=COMMAND_TIMEOUT) as response:
        response.read()


def split_focused_tab(i3, brotab_path, xdotool_path, focused, dry_run=False):
    """Move the actual selected tab into a new window of the same client."""
    clients = get_brotab_clients(brotab_path)
    if not clients:
        raise RuntimeError("No Brotab clients found. Check the Brave Brotab extension.")
    tab_id = focus_and_get_tab(i3, brotab_path, xdotool_path, focused)
    prefix, source_window, tab_number = tab_id.split(".")
    if get_brotab_clients(brotab_path) != clients or prefix not in clients:
        raise RuntimeError("Brotab clients changed during discovery; try again.")
    print(f"Splitting tab {tab_id} from {focused.name!r} into a new Brave window.")
    if dry_run:
        print("Dry run: no window was created and no tabs were moved.")
        return 0

    # Pin all subsequent calls to this mediator's address. With --target and
    # just one client, Brotab always assigns prefix 'a', regardless of the
    # prefix returned by the earlier discovery of all browser clients.
    address = clients[prefix]
    command = (brotab_path, "--target", address)
    source_tab = f"a.{source_window}.{tab_number}"
    marker = f"about:blank#brotab-split-{uuid4().hex}"
    # Window ID 0 asks the extension to create a new window. This installed
    # extension returns no ID when opening a single URL in a new window, so
    # find our unique blank page in the tab list instead of guessing by focus.
    run_command(*command, "open", "a.0", input_text=marker + "\n")
    deadline = time.monotonic() + TIMEOUT
    blank_tab = None
    while time.monotonic() < deadline:
        rows = run_command(*command, "list")
        matches = [line for line in rows.splitlines() if line.split("\t", 2)[-1] == marker]
        if len(matches) == 1:
            blank_tab = get_tab_ids(matches[0])[0]
            break
        time.sleep(POLL_INTERVAL)
    if blank_tab is None:
        raise RuntimeError("Could not identify the new Brave window; no tabs were moved.")
    target_id = tab_to_window_id(blank_tab)
    if target_id == tab_to_window_id(source_tab):
        raise RuntimeError("Brotab did not create a separate window; no tabs were moved.")
    move_tabs_via_brotab_api({"a": address}, [source_tab], target_id, 1)

    # A tab keeps its numeric ID when moved, but its window component changes.
    # Confirm it arrived before removing the placeholder: an HTTP success
    # alone does not prove that the browser accepted the tab move.
    moved_tab = f"{target_id}.{tab_number}"
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if moved_tab in get_tab_ids(run_command(*command, "list")):
            run_command(*command, "close", blank_tab)
            run_command(*command, "activate", "--focused", moved_tab)
            return 0
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(
        "Could not confirm the tab move. The temporary blank tab was left open."
    )


def main(argv=None) -> int:
    args = parse_args(argv)
    side = SIDE_ALIASES.get(args.side, args.side)
    brotab_path = ensure_command("brotab")
    xdotool_path = ensure_command("xdotool")
    try:
        i3 = i3ipc.Connection()
    except Exception as exc:
        # i3ipc uses a plain Exception when it cannot discover an IPC socket.
        raise RuntimeError(f"Could not connect to i3: {exc}") from exc
    focused = i3.get_tree().find_focused()
    if focused is None or not is_brave_window(focused):
        raise RuntimeError("The focused window is not a Brave window.")
    # Splitting also works when this is the only Brave window on the workspace.
    if args.side == "split":
        return split_focused_tab(i3, brotab_path, xdotool_path, focused, args.dry_run)
    workspace = focused.workspace()
    if workspace is None:
        raise RuntimeError("Could not determine the focused workspace.")
    candidates = [node for node in workspace.leaves() if is_brave_window(node)]
    target = choose_target_window(focused, candidates, side)
    if target is None:
        raise RuntimeError(f"No Brave window found on the {side} side on this workspace.")

    clients = get_brotab_clients(brotab_path)
    if not clients:
        raise RuntimeError("No Brotab clients found. Check the Brave Brotab extension.")
    moved = False
    try:
        selected_tab = focus_and_get_tab(i3, brotab_path, xdotool_path, focused)
        source_id = tab_to_window_id(selected_tab)
        target_id = focus_and_map_window(i3, brotab_path, xdotool_path, target, exclude=source_id)
        if source_id.split(".")[0] != target_id.split(".")[0]:
            raise RuntimeError("Source and target windows belong to different Brotab clients.")
        # Prefixes are assigned during discovery. Abort if clients changed
        # while mapping, rather than sending IDs to a different browser.
        if get_brotab_clients(brotab_path) != clients:
            raise RuntimeError("Brotab clients changed during discovery; try again.")
        tabs = get_tab_ids(run_command(brotab_path, "list"))
        source_tabs = [tab for tab in tabs if tab_to_window_id(tab) == source_id]
        target_tabs = [tab for tab in tabs if tab_to_window_id(tab) == target_id]
        if not source_tabs or not target_tabs:
            raise RuntimeError("Source or target tabs disappeared during discovery; try again.")
        if selected_tab not in source_tabs:
            raise RuntimeError("The selected source tab disappeared during discovery; try again.")
        print(f"Moving {len(source_tabs)} tab(s) from {focused.name!r} to {target.name!r} ({side}).")
        if args.dry_run:
            print("Dry run: no tabs were moved.")
            return 0
        move_tabs_via_brotab_api(
            clients, source_tabs, target_id, len(target_tabs), selected_tab=selected_tab,
        )
        moved = True
        focus_window(i3, xdotool_path, target)
        # Moving tabs does not select them. Keep the source's selected tab
        # active, using its new window ID and pinning the original client.
        prefix, target_window = target_id.split(".")
        tab_number = selected_tab.rsplit(".", 1)[1]
        run_command(
            brotab_path, "--target", clients[prefix], "activate", "--focused",
            f"a.{target_window}.{tab_number}",
        )
        return 0
    finally:
        # Mapping temporarily focuses the target. Restore focus after a dry
        # run or failure; after a move the source window may no longer exist.
        if not moved:
            try:
                focus_window(i3, xdotool_path, focused)
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                print(f"Could not restore the original focus: {exc}", file=sys.stderr)


def cli() -> int:
    try:
        return main()
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, "stderr", None)
        message = detail.strip() if detail and detail.strip() else str(exc)
        print(f"brotabControle: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(cli())

