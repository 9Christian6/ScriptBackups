#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import json
import subprocess
import toml
from pathlib import Path
import re

CONFIG_PATH = Path("/home/christian/.config/workstyle/config.toml")


def find_terminal_key_from_title(title):
    """
    Finds the FIRST config key that appears inside the terminal window title.
    Case-insensitive.
    Example:
        title = "~/Bin - VIFM"
        config key "VIFM" → match
    """
    config_keys = load_config_keys_and_values()
    # Find all keys that appear in the title
    matches = []
    for key in config_keys:
        if (key in title):
            matches.append((key, config_keys[key]))
            break
    # Return the key with the earliest appearance
    if matches:
        matches.sort(key=lambda x: x[0])  # sort by index in title
        return matches[0][1]
    return config_keys["kitty"]


def find_browser_key_from_title(title):
    """
    Finds the FIRST config key that appears inside the browser window title.
    Case-insensitive.
    Example:
        title = "Following - Twitch - Brave"
        config key "twitch" → match
    """
    config_keys = load_config_keys_and_values()

    # Find all keys that appear in the title
    matches = []
    for key in config_keys:
        if (key in title):
            matches.append((key, config_keys[key]))
            break
    # Return the key with the earliest appearance
    if matches:
        matches.sort(key=lambda x: x[0])  # sort by index in title
        return matches[0][1]
    return None


# Add any browser classes here
SPECIAL_CLASSES = {
    "firefox": find_browser_key_from_title,
    "chromium": find_browser_key_from_title,
    "google-chrome": find_browser_key_from_title,
    "Google-chrome": find_browser_key_from_title,
    "brave-browser": find_browser_key_from_title,
    "Brave-browser": find_browser_key_from_title,
    "vivaldi-stable": find_browser_key_from_title,
    "alacritty": find_terminal_key_from_title,
    "kitty": find_terminal_key_from_title
}


def get_scratch_windows():
    """
    Returns a list:
    { "class": <class>, "title": <title> }
    for all windows in the scratchpad.
    """
    tree_json = subprocess.check_output(["i3-msg", "-t", "get_tree"])
    tree = json.loads(tree_json)

    found = []

    def walk(node):
        if node.get("name") == "__i3_scratch":
            for f in node.get("floating_nodes", []):
                for inner in f.get("nodes", []):
                    wp = inner.get("window_properties", {})
                    if "class" in wp:
                        found.append({
                            "class": wp.get("class"),
                            "title": wp.get("title", "")
                        })
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key, []):
                walk(child)

    walk(tree)
    return found


def load_config_keys_and_values():
    """
    Loads key/value pairs from TOML lines like:
    "twitch" = "T"

    Returns:
        { key: value }
    """
    mapping = {}
    with CONFIG_PATH.open() as f:
        mapping = toml.loads(f.read())
    mappingLower = {}
    for key, val in mapping.items():
        mappingLower[key.lower()] = val
    return mapping

def icon_for_class(config, app_class, title):
    appIcon = ''
    if app_class in SPECIAL_CLASSES:
        appIcon = SPECIAL_CLASSES[app_class](title)
    elif app_class in config:
        appIcon = config[app_class]
    return appIcon

def main():
    windows = get_scratch_windows()
    config = load_config_keys_and_values()
    results = []

    for win in windows:
        app_class = win["class"].lower()
        title = win["title"].lower()
        results.append(icon_for_class(config, app_class, title))
    results = list(dict.fromkeys(results))
    print(" , ".join(results))


if __name__ == "__main__":
    main()
