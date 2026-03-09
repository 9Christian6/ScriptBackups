#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3

import subprocess
import shlex

QUERY_COMMAND = ["/home/christian/Bin/reminderScript.py", "query", "--format", "text"]

ROFI_THEME = """
window {width: 30%;}
mainbox {children: [listview];}
listview {dynamic: true; fixed-height: false;}
"""

ROFI_THEME_SHUTDOWN = """
    inputbar { enabled: false; }
    listview {dynamic: true; fixed-height: false;}
    element-icon { size: 1.3em; padding: 0 8px 0 0; color: #ffffff; }
"""

def handle_dankbarkeit():
    subprocess.run('/home/christian/Bin/Dankbarkeitv2.py')

def handle_tagebuch():
    subprocess.run('/home/christian/Bin/Tagebuch.py')

def run_command(cmd, input_text=None):
    result = subprocess.run(
            cmd,
            input=input_text,
            text=True,
            capture_output=True
            )
    return result.stdout.strip()


def notify(message):
    subprocess.run(["notify-send", message])

def main():
    pending = run_command(QUERY_COMMAND)

    if not pending:
        print("nothing pending")
        return

    # Extract first column (like awk '{print $1}')
    event_names = "\n".join(line.split()[0] for line in pending.splitlines())

    selected_event = run_command(
            ["rofi", "-dmenu", "-theme-str", ROFI_THEME_SHUTDOWN],
            input_text=event_names
            )

    if not selected_event:
        notify("No Event Acknowledged")
        return

    if selected_event == "Tagebuch":
        handle_tagebuch()

    if selected_event == "DankbarkeitsTagebuch":
        handle_dankbarkeit()

    ack_command = [
            "/home/christian/Bin/reminderScript.py",
            "acknowledge",
            "--name",
            selected_event
            ]

    print(" ".join(shlex.quote(x) for x in ack_command))
    notify(" ".join(shlex.quote(x) for x in ack_command))
    response = run_command(ack_command)
    notify(response)


if __name__ == "__main__":
    main()
