#!/usr/bin/env /home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import datetime
import os
import shlex
import subprocess

# Log file location
LOG_FILE = os.path.expanduser("~/.rofi_zsh.log")
HISTORY_LIMIT = 1000


def write_log(msg):
    with open(LOG_FILE, "a") as f:
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{timestamp} {msg}\n")
    truncate_log_file()


def truncate_log_file():
    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    if len(lines) > HISTORY_LIMIT:
        lines = lines[-HISTORY_LIMIT:]
    with open(LOG_FILE, "w") as f:
        f.writelines(lines)


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


def main():
    try:
        # 1. Launch Rofi
        proc = subprocess.run(
            [
                "rofi",
                "-dmenu",
                "-theme",
                "pallette.rasi",
                "-p",
                "Run in ZSH:",
                "-lines",
                "0",
            ],
            input="",
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        write_log("Rofi menu closed (Escape pressed).")
        return
    except Exception as e:
        err_msg = f"SCRIPT CRASH: {str(e)}"
        write_log(err_msg)
        subprocess.run(["notify-send", "Rofi Script Error", str(e)])
        return

    user_command = proc.stdout.strip()

    if not user_command:
        write_log("Cancelled or empty input.")
        return

    write_log(f"COMMAND RECEIVED: {user_command}")

    # 2. Execute command in NON-INTERACTIVE zsh, with env captured from
    # interactive zsh so exports match normal interactive startup.
    try:
        interactive_env = get_interactive_zsh_env()
    except Exception as e:
        write_log(f"Interactive env capture failed, using current env: {e}")
        interactive_env = os.environ.copy()

    with open(LOG_FILE, "a") as log_out:
        log_out.write(f"--- Start Output of '{user_command}' ---\n")
        aliases_file = os.path.expanduser("~/.aliases")
        quoted_aliases_file = shlex.quote(aliases_file)
        quoted_user_command = shlex.quote(user_command)
        shell_command = (
            f"setopt aliases; "
            f"[[ -f {quoted_aliases_file} ]] && source {quoted_aliases_file}; "
            f"eval {quoted_user_command}"
        )
        subprocess.Popen(
            ["zsh", "-c", shell_command],
            start_new_session=True,
            stdout=log_out,
            stderr=log_out,
            env=interactive_env,
        )


if __name__ == "__main__":
    main()
