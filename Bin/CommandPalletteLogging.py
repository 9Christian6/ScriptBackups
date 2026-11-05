#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import datetime
import os
import shlex
import subprocess
import time

# Log file location
LOG_FILE = os.path.expanduser("~/.rofi_zsh.log")
ZSH_HISTORY_FILE = os.path.expanduser("~/.zsh_history")
SHELL_SOURCE_FILES = [
    "~/.aliases",
    "~/.functions",
]
INTERACTIVE_COMMANDS = {
    "btop",
    "htop",
    "top",
    "btm",
    "vim",
    "nvim",
    "less",
    "more",
    "man",
    "ssh",
    "tmux",
    "ranger",
    "nnn",
    "lazygit",
    "tig",
    "watch",
    "alsamixer",
}


def write_log(msg):
    with open(LOG_FILE, "a") as f:
        timestamp = datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=2))
        ).strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{timestamp} {msg}\n")


def get_interactive_zsh_env():
    # Capture environment exactly as interactive zsh exports it.
    proc = subprocess.run(
        ["zsh", "-i", "-c", "env -0"],
        capture_output=True,
        check=True,
    )
    env = {}
    for item in proc.stdout.split(b"\x00"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        env[key.decode("utf-8", "surrogateescape")] = value.decode(
            "utf-8", "surrogateescape"
        )
    return env


def load_zsh_history_commands():
    try:
        with open(ZSH_HISTORY_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []

    commands = []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        if not line:
            continue

        # Extended history format: ": <epoch>:<duration>;<command>"
        if line.startswith(": ") and ";" in line:
            _, command = line.split(";", 1)
        else:
            command = line

        if command:
            commands.append(command)

    # Newest command first for backward navigation.
    commands.reverse()
    return commands


def run_rofi_prompt(prefill):
    rofi_args = [
        "rofi",
        "-dmenu",
        "-p",
        "Run in ZSH:",
        "-theme",
        ".config/rofi/themes/command-palette.rasi",
        "-kb-row-up",
        "",
        "-kb-row-down",
        "",
        "-kb-custom-1",
        "Control+k,Up",
        "-kb-custom-2",
        "Control+j,Down",
    ]
    if prefill:
        rofi_args.extend(["-filter", prefill])

    return subprocess.run(
        rofi_args,
        input="",
        text=True,
        capture_output=True,
        check=False,
    )


def get_user_command_from_rofi():
    history_commands = load_zsh_history_commands()
    history_index = -1
    prefill = ""
    draft_before_history = ""

    while True:
        proc = run_rofi_prompt(prefill)
        entered_text = proc.stdout.rstrip("\n")

        # Enter pressed.
        if proc.returncode == 0:
            return entered_text

        # Escape/close pressed.
        if proc.returncode == 1:
            return None

        # Ctrl+K / Up: older command (backward in history).
        if proc.returncode == 10:
            if not history_commands:
                prefill = entered_text
                continue
            if history_index == -1:
                draft_before_history = entered_text
            if history_index < len(history_commands) - 1:
                history_index += 1
            prefill = history_commands[history_index]
            continue

        # Ctrl+J / Down: newer command (forward in history).
        if proc.returncode == 11:
            if history_index == -1:
                prefill = entered_text
                continue
            history_index -= 1
            if history_index >= 0:
                prefill = history_commands[history_index]
            else:
                prefill = draft_before_history
            continue

        # Report actual Rofi failures, while allowing custom navigation codes.
        proc.check_returncode()
        return None


def extract_command_name(command):
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts:
        return None
    if parts[0] in {"sudo", "doas"} and len(parts) > 1:
        return parts[1]
    return parts[0]


def should_launch_in_kitty(command):
    cmd_name = extract_command_name(command)
    if not cmd_name:
        return False
    return cmd_name in INTERACTIVE_COMMANDS


def build_source_clause():
    parts = ["setopt aliases;"]
    for path in SHELL_SOURCE_FILES:
        expanded = os.path.expanduser(path)
        quoted = shlex.quote(expanded)
        parts.append(f"[[ -f {quoted} ]] && source {quoted};")
    return " ".join(parts)


def append_to_zsh_history(command):
    # Write in zsh extended-history format: ": <epoch>:<duration>;<command>"
    clean_command = command.replace("\n", " ").strip()
    if not clean_command:
        return
    line = f": {int(time.time())}:0;{clean_command}\n"
    with open(ZSH_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(line)


def main():
    try:
        user_command = get_user_command_from_rofi()
    except subprocess.CalledProcessError as e:
        err_msg = f"SCRIPT CRASH: {e!s}"
        write_log(err_msg)
        subprocess.run(["notify-send", "Rofi Script Error", str(e)], check=True)
        return

    if user_command is None:
        write_log("Rofi menu closed (Escape pressed).")
        subprocess.run(
            ["notify-send", "Rofi menu closed (Escape pressed)."], check=True
        )
        return
    if not user_command.strip():
        write_log("Cancelled or empty input.")
        return

    try:
        append_to_zsh_history(user_command)
    except OSError as e:
        write_log(f"Failed to append to zsh history: {e}")

    write_log(f"COMMAND RECEIVED: {user_command}")

    # 2. Execute command in NON-INTERACTIVE zsh, with env captured from
    # interactive zsh so exports match normal interactive startup.
    try:
        interactive_env = get_interactive_zsh_env()
    except subprocess.CalledProcessError as e:
        write_log(f"Interactive env capture failed, using current env: {e}")
        interactive_env = os.environ.copy()
    else:
        # Preserve desktop/session vars required by notify-send in GUI sessions.
        for key in (
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_RUNTIME_DIR",
            "XAUTHORITY",
        ):
            if key in os.environ:
                interactive_env[key] = os.environ[key]

    quoted_user_command = shlex.quote(user_command)
    source_clause = build_source_clause()
    base_command = f"{source_clause} eval {quoted_user_command}"

    if should_launch_in_kitty(user_command):
        write_log(f"Launching interactive command in kitty: {user_command}")
        try:
            subprocess.Popen(
                ["kitty", "zsh", "-ic", base_command],
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=interactive_env,
            )
            return
        except FileNotFoundError:
            write_log("kitty not found; falling back to non-interactive execution.")

    with open(LOG_FILE, "a") as log_out:
        log_out.write(f"--- Start Output of '{user_command}' ---\n")
        quoted_log_file = shlex.quote(LOG_FILE)
        shell_command = (
            f'output="$({base_command} 2>&1)"; '
            f"cmd_status=$?; "
            f"printf '%s\\n' \"$output\" >> {quoted_log_file}; "
            f'if [[ -n "$output" ]]; then '
            f"notify-send 'Command Output' \"$output\"; "
            f"fi; "
            f"exit $cmd_status"
        )
        subprocess.Popen(
            ["zsh", "-c", shell_command],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=interactive_env,
        )


if __name__ == "__main__":
    main()
