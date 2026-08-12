#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import shutil
import subprocess
import datetime
import sys
import shlex
import os
import glob
from pathlib import Path

REMINDER_SCRIPT = "/home/christian/Bin/reminderScript.py"

QUERY_COMMAND = [REMINDER_SCRIPT, "query"]
LIST_COMMAND = [REMINDER_SCRIPT, "list"]

ROFI_THEME = """configuration { show-icons: false; border-radius: 6px; }
inputbar { enabled: false; }
listview { fixed-height: false; }
"""


def run_command(cmd, input_text=None):
    result = subprocess.run(cmd, input=input_text, text=True, capture_output=True)
    return result.stdout.strip()


def notify(msg):
    subprocess.run(["notify-send", msg])


def select_option(options):

    if not options:
        return None

    selection = run_command(
            ["rofi", "-i", "-dmenu", "-theme-str", ROFI_THEME], "\n".join(options)
            )

    return selection.strip() if selection else None


def get_input(prompt):

    return run_command(
            [
                "rofi",
                "-dmenu",
                "-p",
                prompt,
                "-theme",
                "/home/christian/.config/rofi/themes/command-palette.rasi",
                ]
            )


def normalize_weekdays(s):

    valid = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    if not s.strip():
        raise ValueError("Empty weekday list")

    days = [d.strip().lower() for d in s.split(",")]

    for d in days:
        if d not in valid:
            raise ValueError(f"Invalid weekday: {d}")

    order = {d: i for i, d in enumerate(valid)}

    return " ".join(sorted(days, key=lambda d: order[d]))


def acknowledge_event():
    pending = run_command(QUERY_COMMAND)

    if not pending:
        notify("No pending reminders")
        return

    events = []
    names = []

    for line in pending.split(","):
        line = line.strip()
        event_id, message = line.split(maxsplit=1)
        events.append((event_id, message))
        names.append(message)

    name_to_id = {name: eid for eid, name in events}
    if len(names) == 1:
        selected = names[0].strip()
    else:
        selected = select_option(names)

    if not selected:
        return

    event_id = name_to_id[selected]

    if event_id == "1":
        subprocess.run("/home/christian/Bin/Tagebuch.py", check=False)
    if event_id == "3":
        subprocess.run("/home/christian/Bin/Dankbarkeit.py", check=False)
    if event_id == "5":
        list_path = "/home/christian/Documents/Tageslisten/"
        file_name = (
                list_path
                + "Tagesliste_"
                + datetime.datetime.today().strftime("%d.%m.%Y")
                + ".txt"
                )
        for filename in os.listdir(list_path):
            if filename.startswith("Tagesliste"):
                os.rename(os.path.join(list_path, filename), file_name)
                # os.remove(os.path.join(list_path, filename))
        subprocess.call(shlex.split("kitty -e nvim " + file_name))

    subprocess.run([REMINDER_SCRIPT, "ack", event_id], check=False)
    notify(f"Acknowledged: {selected}")


def add_event():

    try:
        name = get_input("Event Name")
        message = get_input("Message")

        weekdays = normalize_weekdays(get_input("Weekdays (mon, tue, ...)"))

        time_str = get_input("Time (HH:MM)")

        datetime.datetime.strptime(time_str, "%H:%M")

        cmd = [
                REMINDER_SCRIPT,
                "add",
                "--name",
                name,
                "--message",
                message,
                "--weekdays",
                *weekdays.split(),
                "--time",
                time_str,
                ]

        notify(run_command(cmd))

    except ValueError as e:
        notify(str(e))


def delete_event():

    event_list = run_command(LIST_COMMAND)

    if not event_list:
        notify("No events found")
        return

    events = []

    for line in event_list.splitlines():
        parts = line.split()
        events.append((parts[0], parts[1]))

    names = [name for _, name in events]

    selected = select_option(names)

    if not selected:
        return

    event_id = next(eid for eid, name in events if name == selected)

    run_command([REMINDER_SCRIPT, "delete", event_id])

    notify(f"Deleted: {selected}")


def main():

    if len(sys.argv) > 1 and sys.argv[1] == "ack":
        action = "Acknowledge"
    else:
        action = select_option(["Acknowledge", "Add", "Delete"])

    if action == "Acknowledge":
        acknowledge_event()

    elif action == "Add":
        add_event()

    elif action == "Delete":
        delete_event()


if __name__ == "__main__":
    main()
