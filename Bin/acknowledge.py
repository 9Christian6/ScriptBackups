#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3

import datetime
import shlex
import subprocess

QUERY_COMMAND = [
    "/home/christian/Bin/reminderScript.py",
    "query",
    "--format",
    "acknowledge",
]

LIST_COMMAND = [
    "/home/christian/Bin/reminderScript.py",
    "list",
]

ROFI_THEME = """configuration { show-icons: false; border-radius: 6px; }
inputbar { enabled: false; }
listview { dynamic: true; fixed-height: false; }
element-icon { size: 1.3em; padding: 0 8px 0 0; color: #ffffff; }"""


ROFI_THEME_SLIM = (
    ROFI_THEME
    + """
window { width: 7%; border-radius: 6px; }
"""
)


def handle_dankbarkeit():
    subprocess.run("/home/christian/Bin/Dankbarkeit.py")


def handle_tagebuch():
    subprocess.run("/home/christian/Bin/Tagebuch.py")


def run_command(cmd, input_text=None):
    result = subprocess.run(cmd, input=input_text, text=True, capture_output=True)
    return result.stdout.strip()


def notify(message):
    subprocess.run(["notify-send", message])


def select_option(options):
    selected_option = run_command(
        ["rofi", "-i", "-dmenu", "-theme-str", ROFI_THEME],
        input_text="\n".join(options),
    ).strip()
    if select_option == "":
        quit()
    return selected_option


def get_action():
    # Send only names to rofi
    actions = ["Acknowledge", "Reset", "Add", "Edit", "Delete"]
    if actions == "":
        quit()
    return select_option(actions)


def get_input(prompt):
    rofi_args = [
        "rofi",
        "-dmenu",
        "-p",
        prompt,
        "-theme",
        "/home/christian/.config/rofi/themes/command-palette.rasi",
    ]
    # user_input = subprocess.run( rofi_args, input="", text=True, capture_output=True)
    user_input = run_command(rofi_args)
    return user_input


def reset_event():
    return


def acknowledge_event():
    pending = run_command(QUERY_COMMAND)
    if pending == "":
        quit()
    events = []
    names = []
    for line in pending.splitlines():
        event_id, name = line.split(maxsplit=1)
        events.append((event_id, name))
        names.append(name)

    # Build mapping name -> id
    name_to_id = {name: event_id for event_id, name in events}

    # Select Event by name
    selected_event = select_option(names)

    # Get the id
    selected_event_id = name_to_id.get(selected_event)

    print(selected_event_id)
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
        "--id",
        selected_event_id,
    ]

    print(" ".join(shlex.quote(x) for x in ack_command))
    notify(" ".join(shlex.quote(x) for x in ack_command))
    response = run_command(ack_command)


def normalize_weekdays(s: str) -> str:
    valid_days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    order = {day: i for i, day in enumerate(valid_days)}

    if not s.strip():
        raise ValueError("Empty weekday list")

    days = [d.strip() for d in s.split(",")]

    # Reject empty elements like ",mon"
    if any(not d for d in days):
        raise ValueError("Invalid weekday list")

    # Validate weekday names
    for d in days:
        if d not in valid_days:
            raise ValueError(f"Invalid weekday: {d}")

    # Sort in weekday order
    days_sorted = sorted(days, key=lambda d: order[d])

    return ", ".join(days_sorted)


def add_event():
    inteval = 0
    weekdays = ""
    command = ["/home/christian/Bin/reminderScript.py", "add"]
    try:
        command.append("--name")
        command.append(get_input("Event Name: "))
        command.append("--message")
        command.append(get_input("Event Message: "))
        mode = select_option(["Interval", "Weekdays"])
        match mode:
            case "Interval":
                command.append("--interval")
                command.append(str(int(get_input("Interval:"))))
            case "Weekdays":
                command.append("--weekdays")
                command.append(
                    normalize_weekdays(get_input("Weekdays (mon, tue, ..., sun): "))
                )
        command.append("--time")
        time_str = get_input("Time (%H:%M): ")
        datetime.datetime.strptime(time_str, "%H:%M")
        command.append(time_str)
    except ValueError as e:
        notify("Value error " + e.args[0])
        quit()
    print(command)
    notify(run_command(command))
    return


def edit_event():
    notify("Edit event")
    return


def delete_event():
    delete_command = ["/home/christian/Bin/reminderScript.py", "delete", "--id"]
    event_list = run_command(LIST_COMMAND)
    events = []
    for line in event_list.splitlines():
        lineArgs = line.split()
        events.append((lineArgs[0], lineArgs[1]))
    # Build mapping name -> id
    name_to_id = {name: event_id for event_id, name in events}

    # Send only names to rofi
    selected_event = run_command(
        ["rofi", "-dmenu", "-theme-str", ROFI_THEME],
        input_text="\n".join(name_to_id.keys()),
    ).strip()

    # Get the id
    selected_event_id = name_to_id.get(selected_event)
    delete_command.append(str(selected_event_id))
    print(delete_command)
    response = run_command(delete_command)
    notify(response)
    return


def main():
    selected_action = get_action()
    match selected_action:
        case "Acknowledge":
            acknowledge_event()
            pass
        case "Reset":
            reset_event()
            pass
        case "Add":
            add_event()
            pass
        case "Edit":
            edit_event()
            pass
        case "Delete":
            delete_event()
            pass
        case "":
            quit()
    return
    # if not pending:
    #     print("nothing pending")
    #     return


if __name__ == "__main__":
    main()
