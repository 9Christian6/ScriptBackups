#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
import subprocess
import sys

REMINDER_SCRIPT = "/home/christian/Bin/reminderScript.py"
TAGESLISTEN_DIRECTORY = Path("/home/christian/Documents/Tageslisten")
ROFI_INPUT_THEME = "/home/christian/.config/rofi/themes/command-palette.rasi"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

QUERY_COMMAND = [REMINDER_SCRIPT, "query"]
LIST_COMMAND = [REMINDER_SCRIPT, "list"]

ROFI_THEME = """configuration { show-icons: false; border-radius: 6px; }
inputbar { enabled: false; }
listview { fixed-height: false; }
"""


def run_command(cmd: Sequence[str], input_text: str | None = None) -> str:
    result = subprocess.run(
        cmd, input=input_text, text=True, capture_output=True, check=False
    )
    return result.stdout.strip()


def notify(message: str) -> None:
    subprocess.run(["notify-send", message], check=False)


def select_option(options: Sequence[str]) -> str | None:
    if not options:
        return None

    selection = run_command(
        ["rofi", "-i", "-dmenu", "-theme-str", ROFI_THEME], "\n".join(options)
    )

    return selection or None


def get_input(prompt: str) -> str:
    return run_command(
        [
            "rofi",
            "-dmenu",
            "-p",
            prompt,
            "-theme",
            ROFI_INPUT_THEME,
        ]
    )


def normalize_weekdays(value: str) -> str:
    if not value.strip():
        raise ValueError("Empty weekday list")

    days = [day.strip().lower() for day in value.split(",")]

    for day in days:
        if day not in WEEKDAYS:
            raise ValueError(f"Invalid weekday: {day}")

    return " ".join(sorted(days, key=WEEKDAYS.index))


def select_pending_event() -> tuple[str, str] | None:
    """Return the selected pending reminder's ID and message, if any."""
    pending = run_command(QUERY_COMMAND)

    if not pending:
        notify("No pending reminders")
        return

    events = [entry.strip().split(maxsplit=1) for entry in pending.split(",")]
    names = [message for _, message in events]
    name_to_id = {message: event_id for event_id, message in events}
    if len(names) == 1:
        selected = names[0]
    else:
        selected = select_option(names)

    if not selected:
        return

    return name_to_id[selected], selected


def handle_tagesliste() -> None:
    """Date the daily list, open it for editing, and show its Polybar module."""
    file_path = TAGESLISTEN_DIRECTORY / f"Tagesliste_{datetime.today():%d.%m.%Y}.txt"
    for entry in TAGESLISTEN_DIRECTORY.iterdir():
        if entry.name.startswith("Tagesliste"):
            entry.rename(file_path)

    subprocess.run(["kitty", "-e", "nvim", str(file_path)], check=False)
    subprocess.run(["polybar-msg", "action", "#tageslisten.show"], check=False)


def acknowledge_event() -> None:
    event = select_pending_event()
    if event is None:
        return

    event_id, selected = event

    if event_id == "1":
        # The journal records the date selected in its own rofi menu.
        result = subprocess.run(["/home/christian/Bin/Tagebuch.py"], check=False)
        if result.returncode == 0:
            notify(f"Acknowledged: {selected}")
        elif result.returncode != 2:
            notify("Could not open journal; reminder was not acknowledged")
        return
    elif event_id == "3":
        subprocess.run(["/home/christian/Bin/Dankbarkeit.py"], check=False)
    elif event_id == "5":
        handle_tagesliste()
        selected = "Tagesliste"
    subprocess.run([REMINDER_SCRIPT, "ack", event_id], check=False)
    notify(f"Acknowledged: {selected}")


def add_event() -> None:
    try:
        name = get_input("Event Name")
        message = get_input("Message")

        weekdays = normalize_weekdays(get_input("Weekdays (mon, tue, ...)"))

        time_str = get_input("Time (HH:MM)")

        datetime.strptime(time_str, "%H:%M")

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

    except ValueError as error:
        notify(str(error))


def delete_event() -> None:
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


def dismiss_event() -> None:
    event = select_pending_event()
    if event is None:
        return

    event_id, selected = event

    subprocess.run([REMINDER_SCRIPT, "ack", event_id], check=False)
    notify(f"Dismissed: {selected}")


def reset_event() -> None:
    """Select an event and undo its last acknowledgement or dismissal."""
    event_list = run_command(LIST_COMMAND)
    if not event_list:
        notify("No events found")
        return

    # Each schedule has its own row, so present each event only once.
    events = {}
    for line in event_list.splitlines():
        event_id, details = line.split(maxsplit=1)
        name, _, _ = details.rsplit(maxsplit=2)
        events[event_id] = name

    selected = select_option(
        [f"{event_id} {name}" for event_id, name in events.items()]
    )
    if not selected:
        return

    event_id = selected.split(maxsplit=1)[0]
    notify(run_command([REMINDER_SCRIPT, "reset", event_id]))


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "ack":
        action = "Acknowledge"
    else:
        action = select_option(["Acknowledge", "Add", "Delete", "Dismiss", "Reset"])

    if action == "Acknowledge":
        acknowledge_event()

    elif action == "Add":
        add_event()

    elif action == "Delete":
        delete_event()

    elif action == "Dismiss":
        dismiss_event()

    elif action == "Reset":
        reset_event()


if __name__ == "__main__":
    main()
