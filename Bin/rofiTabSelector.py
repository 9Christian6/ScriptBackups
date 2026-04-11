#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import json
from pathlib import Path
import subprocess
import sys
import i3ipc

BRAVE_CLASS = "brave-browser"
CACHE_PATH = Path(__file__).with_name(".rofiTabSelector.cache.json")


def get_tabs():
    result = subprocess.run(['brotab', 'list'], capture_output=True, text=True, check=True)
    tabs = []
    for line in result.stdout.splitlines():
        parts = line.split('\t', 2)
        if len(parts) >= 2:
            tabs.append((parts[0].strip(), parts[1].strip()))
    return tabs

def select_tab(tabs):
    titles = [title for _, title in tabs]
    numTabs = len(tabs)
    numTabs = min(16, numTabs)
    proc = subprocess.run(['rofi', '-dmenu', '-p', 'Browser Tabs', '-i', '-theme-str', 'listview { lines: ' + f'{numTabs}'+ '; }'],
                          input='\n'.join(titles), capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        sys.exit(0)
    selected_title = proc.stdout.strip()
    for tid, title in tabs:
        if title == selected_title:
            return tid, title
    return None, None


def get_active_tab_ids():
    proc = subprocess.run(
        ['brotab', 'active'],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.split()[0] for line in proc.stdout.splitlines() if line.strip()]


def tab_to_window_id(tab_id):
    return '.'.join(tab_id.split('.')[:-1])


def is_brave_window(node):
    window_class = (node.window_class or '').lower()
    window_instance = (node.window_instance or '').lower()
    return BRAVE_CLASS in {window_class, window_instance}


def normalize_title(title):
    if not title:
        return ''
    return title.replace(' - Brave', '').strip().lower()


def get_brave_windows(i3):
    tree = i3.get_tree()
    windows = []
    seen = set()

    for node in tree.leaves():
        if node.id not in seen and is_brave_window(node):
            windows.append(node)
            seen.add(node.id)

    return windows


def load_cache():
    try:
        data = json.loads(CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(cache):
    CACHE_PATH.write_text(json.dumps(cache))


def filter_cache(cache, brave_windows):
    valid = {str(win.window): win.id for win in brave_windows if win.window}
    filtered = {}
    for brotab_window_id, x_window_id in cache.items():
        if x_window_id in valid:
            filtered[brotab_window_id] = x_window_id
    return filtered


def get_direct_window_map(tabs):
    title_by_tab_id = {tab_id: title for tab_id, title in tabs}
    brotab_windows = {}
    for active_tab_id in get_active_tab_ids():
        brotab_windows[tab_to_window_id(active_tab_id)] = normalize_title(
            title_by_tab_id.get(active_tab_id, '')
        )
    return brotab_windows


def update_cache_from_titles(cache, brave_windows, tabs):
    brotab_titles = get_direct_window_map(tabs)
    title_to_window_ids = {}
    for brotab_window_id, title in brotab_titles.items():
        if title:
            title_to_window_ids.setdefault(title, []).append(brotab_window_id)

    for win in brave_windows:
        title = normalize_title(win.name)
        matches = title_to_window_ids.get(title, [])
        if len(matches) == 1 and win.window:
            cache[matches[0]] = str(win.window)

    return cache


def focus_window(i3, brave_windows, x_window_id):
    for win in brave_windows:
        if win.window and str(win.window) == x_window_id:
            ws = win.workspace()
            if ws:
                i3.command(f'workspace "{ws.name}"')
            i3.command(f'[con_id={win.id}] focus')
            return True
    return False


def focus_in_i3(tab_id, _title, tabs):
    i3 = i3ipc.Connection()
    brave_windows = get_brave_windows(i3)
    if not brave_windows:
        print("No Brave window found.", file=sys.stderr)
        return

    target_window_id = tab_to_window_id(tab_id)
    cache = filter_cache(load_cache(), brave_windows)
    cache = update_cache_from_titles(cache, brave_windows, tabs)
    save_cache(cache)

    x_window_id = cache.get(target_window_id)
    if x_window_id and focus_window(i3, brave_windows, x_window_id):
        subprocess.run(['brotab', 'activate', tab_id], check=True)
        return

    print(f"Could not map {tab_id} to a Brave i3 container instantly.", file=sys.stderr)

def main():
    tabs = get_tabs()
    if not tabs:
        sys.exit(0)
    tab_id, title = select_tab(tabs)
    if tab_id:
        focus_in_i3(tab_id, title, tabs)

if __name__ == '__main__':
    main()
