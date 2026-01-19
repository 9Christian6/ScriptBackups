#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import os
import sys
import time
import signal
import argparse
import subprocess
import atexit
# import termios
# import tty
import i3ipc
# import curses
from datetime import datetime, timedelta
from pynput import keyboard

# --- Globals ---
SPINNERBAR = ['\\', '-', '/', '|', '\\', '-', '/', '|']
SPINNERCLOCK = ['🕛', '🕚', '🕘', '🕖', '🕔', '🕓', '🕒', '🕑', '🕐']
SPINNERFRAME = ['⠏', '⠇', '⠧', '⠦', '⠴', '⠼', '⠸', '⠹', '⠙', '⠋']
SPINNERCIRCLE = ["( ●    )", "(  ●   )", "(   ●  )", "(    ● )", "(     ●)", "(    ● )", "(   ●  )", "(  ●   )", "( ●    )", "(●     )"]
SPINNERFILLINGBAR = ["▰▰▰▰▰▰▰", "▰▰▰▰▰▰▱", "▰▰▰▰▰▱▱", "▰▰▰▰▱▱▱", "▰▰▰▱▱▱▱", "▰▰▱▱▱▱▱", "▰▱▱▱▱▱▱"]
SPINNERS = [SPINNERCLOCK, SPINNERBAR, SPINNERFRAME, SPINNERCIRCLE, SPINNERFILLINGBAR]
seconds = 0
paused = False
ctrl_pressed = False
silent = False

def hide_cursor():
    sys.stdout.write("\033[?25l")

def show_cursor():
    sys.stdout.write("\033[?25h")

# --- Cleanup handler ---
def exit_handler():
    write_time_to_file('')
    write_message_to_file('')
    # with open('/home/christian/Bin/timeLeft', 'w') as f:
    #    f.write('')
    show_cursor()

atexit.register(exit_handler)

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

    with open('/dev/null', 'r') as dev_null_r, \
         open('/dev/null', 'a+') as dev_null_w:
        os.dup2(dev_null_r.fileno(), sys.stdin.fileno())
        os.dup2(dev_null_w.fileno(), sys.stdout.fileno())
        os.dup2(dev_null_w.fileno(), sys.stderr.fileno())

def signal_handler(sig, frame):
    global seconds
    time_display = str(timedelta(seconds=int(seconds)))
    # msg = f"\rCounting interrupted at {int(seconds)} second(s)!\n"
    msg = f"\rCounting interrupted at {time_display}!\n"
    sys.stdout.write(msg)
    show_cursor()
    sys.exit(0)

def write_time_to_file(time_str):
    with open('/home/christian/Bin/timeLeft', 'w') as f:
        f.write(time_str + '\n')

def write_message_to_file(message):
    with open('/home/christian/Bin/timerMessage', 'w') as f:
        f.write(message + '\n')

def notify(message, reading='', sound=True):
    if reading == '':
        reading = message
    subprocess.Popen(['notify-send', message])
    if message:
        subprocess.Popen(['espeak-ng', '-v', 'German', reading])
    elif sound:
        subprocess.Popen("play /home/christian/Music/Bellsound.aiff -q", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
    decimals = str(seconds).split('.')
    if len(decimals) == 1:
        return 0
    index = int((seconds * len(SPINNER)) % len(SPINNER))
    return index


def countdown_seconds(message):
    global seconds, TICKTIME
    while seconds > 0:
        if not paused:
            display_time(seconds)
            seconds = round(seconds - TICKTIME, 1)
        time.sleep(TICKTIME)
    sys.stdout.write("\rCountdown finished\n" if not message else "")
    notify(message or "Countdown finished", message or "Countdown finishd")

def display_time(seconds):
    try:
        width = os.get_terminal_size().columns - 2
    except OSError:
        width = 80
    time_display = str(timedelta(seconds=int(seconds)))
    spinner_char = SPINNER[calculate_spinner_char_index(seconds)]
    width -= len(spinner_char)
    write_time_to_file(spinner_char + ' ' + time_display)
    sys.stdout.write(f"\r{time_display.ljust(width)}{spinner_char}")
    sys.stdout.flush()

# --- Keyboard handlers ---
def on_press(key):
    global seconds, fd, paused
    if not is_terminal_focused():
        return
    try:
        if key.char == '+':
            seconds += 10
        if key.char == '-':
            seconds = max(0, seconds - 10)
        if key.char == 'l':
            os.system('clear')
        if key.char == 'p':
            paused = not paused
            time_display = str(timedelta(seconds=int(seconds)))
            sys.stdout.write(f"\rTimer paused at {time_display}")
            sys.stdout.flush()
    except AttributeError:
        return

def on_release(key):
    global ctrl_pressed
    if key == keyboard.Key.ctrl:
        ctrl_pressed = False

# --- Pomodoro ---
def run_pomodoro(pomodoro_len, short_break, long_break, cycles):
    global seconds
    round_count = 0
    try:
        while True:
            round_count += 1
            print(f"\nStarting Pomodoro #{round_count}")
            seconds = pomodoro_len * 60
            countdown_seconds("Pomodoro finished! Take a break!")
            if round_count % cycles == 0:
                print("Taking a long break.")
                seconds = long_break * 60
                countdown_seconds("Long break over. Back to work!")
            else:
                print("Taking a short break.")
                seconds = short_break * 60
                countdown_seconds("Short break over. Ready for next Pomodoro?")
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
    global seconds, silent, fd, TICKTIME, SPINNER, SPINNERS

    # i3 connection stuff
    i3 = i3ipc.Connection()
    fd = sys.stdin.fileno()
    # old_settings = termios.tcgetattr(fd)

    # Start keyboard listener
    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    parser = argparse.ArgumentParser(description='A simple timer')
    parser.add_argument('-s', '--seconds', type=int, help='Number of seconds')
    parser.add_argument('-m', '--minutes', type=int, help='Number of minutes')
    parser.add_argument('-r', '--run', action='store_true', help='Count up indefinitely')
    parser.add_argument('-t', '--time', type=str, help='Counts until HH:MM[:SS]')
    parser.add_argument('--message', type=str, help='Message displayed when timer finishes')
    parser.add_argument('--silent', action='store_true', help='Run timer in background')
    parser.add_argument('--pomodoro', action='store_true', help='Enable Pomodoro mode')
    parser.add_argument('--pomodoro-length', type=int, default=20, help='Pomodoro length (min)')
    parser.add_argument('--short-break', type=int, default=5, help='Short break length (min)')
    parser.add_argument('--long-break', type=int, default=15, help='Long break length (min)')
    parser.add_argument('--cycles', type=int, default=4, help='Pomodoros before long break')
    parser.add_argument('--spinner', type=int, default=0, help='Index of the spinner used in animation, defaults to bar spinner')

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    silent = args.silent
    TICKTIME = 0.1

    if args.silent:
        subprocess.Popen([sys.executable] + sys.argv[:-1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        exit()
    else:
        hide_cursor()

    if args.pomodoro:
        run_pomodoro(args.pomodoro_length, args.short_break, args.long_break, args.cycles + 1)
        return

    if args.spinner is not None:
        try:
            SPINNER = SPINNERS[args.spinner]
        except Exception:
            SPINNER = SPINNERS[0]

    if args.time:
        try:
            now = datetime.now()
            fmt = '%H:%M:%S' if len(args.time) >= 8 else '%H:%M'
            target = datetime.combine(now, datetime.strptime(args.time, fmt).time())
            if target <= now:
                target += timedelta(days=1)
            seconds = (target - now).total_seconds()
        except ValueError:
            sys.stderr.write("Invalid time format. Use HH:MM[:SS].\n")
            sys.exit(1)

    if args.seconds:
        seconds += args.seconds

    if args.minutes:
        seconds += args.minutes * 60

    if args.message:
        write_message_to_file(args.message)
    else:
        write_message_to_file("No message available")

    if args.run:
        countup_seconds()
    elif seconds > 0:
        countdown_seconds(args.message or "")

    show_cursor()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
