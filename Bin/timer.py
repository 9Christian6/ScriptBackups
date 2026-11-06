#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import argparse
import atexit
import os
import re
import select
import signal
import subprocess
import sys
import tempfile
import termios
import threading
import time
import tty
import wave
from datetime import datetime, timedelta, tzinfo

import i3ipc
from pynput import keyboard
from tzlocal import get_localzone


class Mytz(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=2)


# --- Globals ---
SPINNERBAR = ["\\", "-", "/", "|", "\\", "-", "/", "|"]
SPINNERCLOCK = ["🕛", "🕚", "🕘", "🕖", "🕔", "🕓", "🕒", "🕑", "🕐"]
SPINNERFRAME = ["⠏", "⠇", "⠧", "⠦", "⠴", "⠼", "⠸", "⠹", "⠙", "⠋"]
SPINNERCIRCLE = [
    "( ●    )",
    "(  ●   )",
    "(   ●  )",
    "(    ● )",
    "(     ●)",
    "(    ● )",
    "(   ●  )",
    "(  ●   )",
    "( ●    )",
    "(●     )",
]
SPINNERFILLINGBAR = [
    "▰▰▰▰▰▰▰",
    "▰▰▰▰▰▰▱",
    "▰▰▰▰▰▱▱",
    "▰▰▰▰▱▱▱",
    "▰▰▰▱▱▱▱",
    "▰▰▱▱▱▱▱",
    "▰▱▱▱▱▱▱",
]
SPINNERS = [SPINNERCLOCK, SPINNERBAR, SPINNERFRAME, SPINNERCIRCLE, SPINNERFILLINGBAR]
BARSYMBOLSFULL = ["■", "▓"]
BARSYMBOLSEMPTY = ["▢", "▒"]
seconds = 0
paused = False
ack_waiting = False
ack_enabled = True
ack_interval = 1.0
ack_event = threading.Event()
skip_current = False
stdin_fd = None
stdin_settings = None
terminal_input_enabled = False
terminal_input_thread = None
terminal_input_stop = threading.Event()
keyboard_controller = keyboard.Controller()


def handle_args(args):
    global seconds_total, seconds, SPINNER
    if args.silent:
        subprocess.Popen(
            [sys.executable] + sys.argv[:-1],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        sys.exit()
    else:
        hide_cursor()

    if args.spinner is not None:
        try:
            SPINNER = SPINNERS[args.spinner]
        except IndexError:
            SPINNER = SPINNERS[0]

    if args.pomodoro:
        run_pomodoro(
            args.pomodoro_length, args.short_break, args.long_break, args.cycles + 1
        )
        return

    if args.time:
        try:
            now = datetime.now(get_localzone())
            fmt = "%H:%M:%S" if len(args.time) >= 8 else "%H:%M"
            parsed_time = datetime.strptime(args.time, fmt).time()
            target = datetime.combine(now.date(), parsed_time, tzinfo=get_localzone())
            if target <= now:
                target += timedelta(days=1)
            seconds = (target - now).total_seconds()
        except ValueError:
            sys.stderr.write("Invalid time format. Use HH:MM[:SS].\n")
            sys.exit(1)

    if args.message:
        write_message_to_file(args.message)

    if args.seconds:
        seconds += args.seconds

    if args.minutes:
        seconds += args.minutes * 60

    seconds_total = seconds

    if args.run:
        countup_seconds()
    elif seconds > 0:
        countdown_seconds(args.message or "")


def calc_finish_time(secs):
    finish_time = datetime.now(tz=Mytz()) + timedelta(seconds=secs)
    print(finish_time)


def hide_cursor():
    sys.stdout.write("\033[?25l")


def show_cursor():
    sys.stdout.write("\033[?25h")


def setup_terminal_input():
    global stdin_fd, stdin_settings, terminal_input_enabled, terminal_input_thread
    if terminal_input_enabled:
        return True
    if not sys.stdin.isatty():
        return False
    stdin_fd = sys.stdin.fileno()
    if os.tcgetpgrp(stdin_fd) != os.getpgrp():
        return False
    stdin_settings = termios.tcgetattr(stdin_fd)
    # Cbreak disables echo without disabling terminal signals such as Ctrl-C.
    # This only changes the terminal; desktop shortcuts remain available.
    tty.setcbreak(stdin_fd)
    terminal_input_enabled = True
    terminal_input_stop.clear()
    terminal_input_thread = threading.Thread(target=discard_terminal_input, daemon=True)
    terminal_input_thread.start()
    return True


def discard_terminal_input():
    # pynput handles timer shortcuts. Drain their terminal copies (and all other
    # input) so they cannot build up or reach the shell when the timer exits.
    while not terminal_input_stop.is_set():
        try:
            readable, _, _ = select.select([stdin_fd], [], [], 0.1)
            if readable and not os.read(stdin_fd, 4096):
                return
        except (OSError, ValueError):
            return


def restore_terminal_input():
    global stdin_fd, stdin_settings, terminal_input_enabled, terminal_input_thread
    if stdin_fd is None or stdin_settings is None:
        return
    terminal_input_stop.set()
    if terminal_input_thread is not None:
        terminal_input_thread.join()
        terminal_input_thread = None
    termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, stdin_settings)
    stdin_settings = None
    terminal_input_enabled = False


# --- Cleanup handler ---
def exit_handler():
    restore_terminal_input()
    write_time_to_file("")
    subprocess.call(
        ["polybar-msg", "action", f"#timerIPC.send."], stdout=subprocess.DEVNULL
    )
    show_cursor()
    clear_current_line()


# --- Helpers ---
def daemonize():
    """Run process in the background (double fork)."""
    pid = os.fork()
    if pid > 0:
        sys.exit(0)
    os.setsid()
    os.umask(0)
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    with open("/dev/null", "r") as dev_null_r, open("/dev/null", "a+") as dev_null_w:
        os.dup2(dev_null_r.fileno(), sys.stdin.fileno())
        os.dup2(dev_null_w.fileno(), sys.stdout.fileno())
        os.dup2(dev_null_w.fileno(), sys.stderr.fileno())


def signal_handler(sig, frame):
    global seconds
    time_display = str(timedelta(seconds=int(seconds)))
    msg = f"\rCounting interrupted at {time_display}!\n"
    sys.stdout.write(msg)
    show_cursor()
    sys.exit(0)


def write_time_to_file(time_str):
    with open("/home/christian/Bin/timeLeft", "w") as f:
        f.write(time_str + "\n")


def write_message_to_file(message):
    with open("/home/christian/Bin/timerMessage", "w") as f:
        f.write(message + "\n")


def notify(message, reading="", sound=True):
    if reading == "":
        reading = message
    subprocess.Popen(["notify-send", message])
    if message:
        subprocess.Popen(
            ["/home/christian/Bin/tts.sh", "--in-place", reading],
            stdin=subprocess.DEVNULL,
        )
    elif sound:
        subprocess.Popen(
            "play /home/christian/Music/Bellsound.aiff -q",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def create_tts_file(message, directory):
    """Generate speech in directory and return its path and duration in seconds."""
    path = os.path.join(directory, "speech.wav")
    text = message.strip() or "Countdown finished"
    subprocess.run(
        ["pico2wave", f"--wave={path}", "--lang=de-DE", "--", text],
        stdin=subprocess.DEVNULL,
        check=True,
    )
    with wave.open(path, "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    return path, duration


def repeat_alert_until_ack(message, reading="", interval=1.0):
    global ack_waiting, skip_current
    ack_event.clear()
    ack_waiting = True
    try:
        with tempfile.TemporaryDirectory(prefix="timer-tts-") as directory:
            speech = None
            while not ack_event.is_set() and not skip_current:
                duration = 0.0
                deadline = None
                try:
                    if speech is None:
                        speech = create_tts_file(reading or message, directory)
                    path, duration = speech
                    # Count playback time once: the total period is the WAV
                    # duration plus the pause, rather than adding both twice.
                    deadline = time.monotonic() + duration + max(0.1, interval)
                    subprocess.call(
                        ["/home/christian/Bin/timerMessage.sh", message,
                         "--wave", path],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                    )
                except (OSError, subprocess.CalledProcessError, wave.Error) as exc:
                    print(f"Unable to produce timer alert: {exc}", file=sys.stderr)
                if deadline is None:
                    deadline = time.monotonic() + max(0.1, interval)
                while not ack_event.is_set() and not skip_current:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    ack_event.wait(min(0.1, remaining))
    finally:
        ack_waiting = False
        skip_current = False


# --- Timer functions ---
def countup_seconds():
    global seconds, TICKTIME
    while True:
        if not paused:
            time_display = str(timedelta(seconds=int(seconds)))
            spinner_char = SPINNER[calculate_spinner_char_index(seconds)]
            width = os.get_terminal_size().columns - 15
            sys.stdout.write(f"\r{time_display.ljust(width)}{spinner_char}")
            sys.stdout.flush()
            seconds = round(seconds + TICKTIME, 1)
            time.sleep(TICKTIME)


def calculate_spinner_char_index(seconds):
    decimals = str(seconds).split(".")
    if len(decimals) == 1:
        return 0
    index = int((seconds * len(SPINNER)) % len(SPINNER))
    return index


def calculate_bar(seconds_passed, bar_length):
    global seconds_total
    bar_full = BARSYMBOLSFULL[1]
    bar_empty = BARSYMBOLSEMPTY[1]
    bar = ""
    seconds_passed = seconds_total - seconds_passed
    passed_time_percent = seconds_passed / seconds_total
    passed_bar = (int)(passed_time_percent * bar_length + 1)
    bar += bar_full * passed_bar
    missing_bar = bar_length - passed_bar
    bar += bar_empty * missing_bar
    return bar


def countdown_seconds(message):
    global seconds, TICKTIME, ack_enabled, ack_interval
    write_message_to_file(message)
    while seconds > 0:
        if not paused:
            display_time(seconds)
            seconds = round(seconds - TICKTIME, 1)
        time.sleep(TICKTIME)
    final_message = message or "Countdown finished"
    final_reading = message or "Countdown finished"
    if ack_enabled:
        sys.stdout.write("\nPress Esc to acknowledge the alert.\n")
        sys.stdout.flush()
        repeat_alert_until_ack(final_message, final_reading, ack_interval)
    else:
        notify(final_message, final_reading)


def visible_length(text):
    # ANSI escape code pattern
    ansi_escape = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

    # Remove ANSI codes and return the length of the visible text
    clean_text = ansi_escape.sub("", text)
    return len(clean_text)


def display_content(content):
    try:
        width = os.get_terminal_size().columns - 2
    except OSError:
        width = 80
    terminal_prompt_left = os.environ["LEFT_PROMPT_LINE"].replace('"', "")
    terminal_prompt_right = os.environ["RIGHT_PROMPT_LINE"].replace('"', "")
    width_terminal_prompt_r = visible_length(terminal_prompt_right)
    width_terminal_prompt_l = visible_length(terminal_prompt_left)
    width_content_display = len(content)
    width_padding = (
        width
        - width_content_display
        - width_terminal_prompt_l
        - width_terminal_prompt_r
        + 16
    )
    content_prompt = (
        terminal_prompt_left + content + " " * width_padding + terminal_prompt_right
    )
    sys.stdout.write(f"\r{content_prompt}")
    sys.stdout.flush()


def display_time(seconds):
    terminal_prompt_left = ""
    terminal_prompt_right = ""
    width_terminal_prompt_r = 0
    width_terminal_prompt_l = 0
    try:
        terminal_prompt_left = os.environ["LEFT_PROMPT_LINE"].replace('"', "")
        terminal_prompt_right = os.environ["RIGHT_PROMPT_LINE"].replace('"', "")
        width_terminal_prompt_r = visible_length(terminal_prompt_right)
        width_terminal_prompt_l = visible_length(terminal_prompt_left)
        width = os.get_terminal_size().columns - 2
    except:
        width = 80
    spinner_char = SPINNER[calculate_spinner_char_index(seconds)]
    time_bar = calculate_bar(seconds, 10)
    time_display = str(timedelta(seconds=int(seconds))).strip()
    width_time_display = len(time_display)
    width_spinner = len(spinner_char)
    width_padding = (
        width
        - width_time_display
        - width_spinner
        - width_terminal_prompt_l
        - width_terminal_prompt_r
        + 16
    )
    cli_time_display = (
        terminal_prompt_left
        + time_display
        + " " * width_padding
        + spinner_char
        + terminal_prompt_right
    )
    polybar_time_display = spinner_char + " " + time_display
    width -= len(spinner_char)

    subprocess.call(
        ["polybar-msg", "action", f"#timerIPC.send.{polybar_time_display}"],
        stdout=subprocess.DEVNULL,
    )
    sys.stdout.write(f"\r{cli_time_display}")
    sys.stdout.flush()


def clear_current_line():
    try:
        cols, rows = os.get_terminal_size()
        terminal_prompt = os.environ["LEFT_PROMPT_LINE"]
        sys.stdout.write(
            "\r" + terminal_prompt + " " * (cols - len(terminal_prompt)) + "\r"
        )
        sys.stdout.flush()
    except KeyError:
        return


def on_press(key):
    global seconds_total, seconds, paused, skip_current

    if key == keyboard.Key.esc:
        if ack_waiting:
            ack_event.set()
        return

    if not is_terminal_focused():
        return True
    try:
        pressed_char = key.char
    except AttributeError:
        return True

    if pressed_char == "q":
        exit_handler()
        os.kill(os.getpid(), signal.SIGINT)
        return

    if pressed_char == "s":
        skip_current = True
        seconds = 0

    if pressed_char == "+":
        seconds += 10
        seconds_total += 10
        return

    if pressed_char == "-":
        seconds = max(0, seconds - 10)
        seconds_total = max(0, seconds_total - 10)
        return

    if pressed_char == "l":
        clear_current_line()
        return

    if pressed_char == "p":
        # Add your code for the 'p' key here
        paused = not paused
        time_display = str(timedelta(seconds=int(seconds)))
        display_content(f"rTimer paused at {time_display}")
        return

    return True


# --- Pomodoro ---
def run_pomodoro(pomodoro_len, short_break, long_break, cycles):
    global seconds, seconds_total
    round_count = 0
    try:
        while True:
            round_count += 1
            print(f"Starting Pomodoro #{round_count}")
            seconds = pomodoro_len * 60
            seconds_total = seconds
            print(f"Pomodoro #{round_count}")
            countdown_seconds(f"Pomodoro #{round_count}")
            if round_count % cycles == 0:
                print("Taking a long break.")
                seconds = long_break * 60
                seconds_total = seconds
                countdown_seconds("Long break")
            else:
                print("Taking a short break.")
                seconds = short_break * 60
                seconds_total = seconds
                countdown_seconds("Short break.")
    except KeyboardInterrupt:
        print("\nPomodoro session ended.")


def is_terminal_focused():
    """
    Returns True if the terminal running this script is focused in i3,
    otherwise False.
    """
    i3 = i3ipc.Connection()
    focused = i3.get_tree().find_focused()
    this_window_id = int(os.environ.get("WINDOWID", "0"))
    return bool(focused and focused.window == this_window_id)


# --- Main ---
def main():
    global seconds, silent, TICKTIME, SPINNER, SPINNERS, ack_enabled, ack_interval

    atexit.register(exit_handler)
    parser = argparse.ArgumentParser(description="A simple timer")
    parser.add_argument("-s", "--seconds", type=int, help="Number of seconds")
    parser.add_argument("-m", "--minutes", type=int, help="Number of minutes")
    parser.add_argument(
        "-r", "--run", action="store_true", help="Count up indefinitely"
    )
    parser.add_argument("-t", "--time", type=str, help="Counts until HH:MM[:SS]")
    parser.add_argument(
        "--message", type=str, help="Message displayed when timer finishes"
    )
    parser.add_argument("--silent", action="store_true", help="Run timer in background")
    parser.add_argument(
        "--polybar", action="store_true", help="Run timer in polybar output mode"
    )
    parser.add_argument("--pomodoro", action="store_true", help="Enable Pomodoro mode")
    parser.add_argument(
        "--pomodoro-length", type=int, default=20, help="Pomodoro length (min)"
    )
    parser.add_argument(
        "--short-break", type=int, default=5, help="Short break length (min)"
    )
    parser.add_argument(
        "--long-break", type=int, default=15, help="Long break length (min)"
    )
    parser.add_argument(
        "--cycles", type=int, default=4, help="Pomodoros before long break"
    )
    parser.add_argument(
        "--spinner",
        type=int,
        default=0,
        help="Index of the spinner used in animation, defaults to bar spinner",
    )
    parser.add_argument(
        "--no-ack", action="store_true", help="Do not repeat alert until acknowledged"
    )
    parser.add_argument(
        "--ack-interval",
        type=float,
        default=1.0,
        help="Extra pause after the measured speech duration (default: 1 second)",
    )

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    TICKTIME = 0.1
    ack_enabled = not args.no_ack
    ack_interval = max(0.5, args.ack_interval)

    listener = keyboard.Listener(on_press=on_press, suppress=False)
    listener.start()

    try:
        if not args.silent:
            setup_terminal_input()
        handle_args(args)
    finally:
        listener.stop()
        restore_terminal_input()
    exit_handler()
    show_cursor()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    main()
