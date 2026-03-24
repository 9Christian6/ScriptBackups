#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3.12
import os
import sys
import time
import signal
import argparse
import subprocess
import atexit
import threading
import select
import termios
import tty
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
BARSYMBOLSFULL = ['■', '▓']
BARSYMBOLSEMPTY = ['▢', '▒']
seconds = 0
paused = False
ack_waiting = False
ack_enabled = True
ack_interval = 8.0
ack_event = threading.Event()
stdin_fd = None
stdin_settings = None
terminal_input_enabled = False

def handle_args(args):
    global seconds_total, seconds, TICKTIME, ack_enabled, ack_interval, SPINNER, SPINNERS
    if args.silent:
        subprocess.Popen([sys.executable] + sys.argv[:-1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        exit()
    else:
        hide_cursor()

    if args.spinner is not None:
        try:
            SPINNER = SPINNERS[args.spinner]
        except Exception:
            SPINNER = SPINNERS[0]

    if args.pomodoro:
        run_pomodoro(args.pomodoro_length, args.short_break, args.long_break, args.cycles + 1)
        return

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


def hide_cursor():
    sys.stdout.write("\033[?25l")

def show_cursor():
    sys.stdout.write("\033[?25h")

def setup_terminal_input():
    global stdin_fd, stdin_settings, terminal_input_enabled
    if not sys.stdin.isatty():
        return False
    stdin_fd = sys.stdin.fileno()
    stdin_settings = termios.tcgetattr(stdin_fd)
    tty.setcbreak(stdin_fd)
    terminal_input_enabled = True
    return True

def restore_terminal_input():
    global stdin_fd, stdin_settings, terminal_input_enabled
    if stdin_fd is None or stdin_settings is None:
        return
    termios.tcsetattr(stdin_fd, termios.TCSADRAIN, stdin_settings)
    stdin_settings = None
    terminal_input_enabled = False

# --- Cleanup handler ---
def exit_handler():
    write_time_to_file('')
    restore_terminal_input()
    show_cursor()
    #clear_current_line()

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
    subprocess.Popen("pico2wave -w=/tmp/timerMessage.wav --lang=de-DE {0}".format(message), shell=True)

def notify(message, reading='', sound=True):
    if reading == '':
        reading = message
    subprocess.Popen(['notify-send', message])
    if message:
        subprocess.Popen(['/home/christian/Bin/startSilent.sh', 'tts.sh', reading])
    elif sound:
        subprocess.Popen("play /home/christian/Music/Bellsound.aiff -q", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def repeat_alert_until_ack(message, reading='', interval=2.0):
    global ack_waiting
    ack_waiting = True
    ack_event.clear()
    while not ack_event.is_set():
        notify(message, reading)
        ack_event.wait(interval)
    ack_waiting = False

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
    while seconds > 0:
        if not paused:
            display_time(seconds)
            seconds = round(seconds - TICKTIME, 1)
        time.sleep(TICKTIME)
    sys.stdout.write("\rCountdown finished\n" if not message else "")
    final_message = message or "Countdown finished"
    final_reading = message or "Countdown finished"
    if ack_enabled:
        sys.stdout.write("\nPress Esc to acknowledge the alert.\n")
        sys.stdout.flush()
        repeat_alert_until_ack(final_message, final_reading, ack_interval)
    else:
        notify(final_message, final_reading)

def display_time(seconds):
    try:
        width = os.get_terminal_size().columns - 2
    except OSError:
        width = 80
    time_bar = calculate_bar(seconds, 10)
    time_display = str(timedelta(seconds=int(seconds)))
    spinner_char = SPINNER[calculate_spinner_char_index(seconds)]
    width -= len(spinner_char)
    write_time_to_file(spinner_char + ' ' + time_display + ' ' + time_bar)
    sys.stdout.write(f"\r{time_display.ljust(width)}{spinner_char}")
    #sys.stdout.write(f"\r{time_bar}")
    sys.stdout.flush()

# --- Keyboard handlers ---

# def on_key_event(event):
#     if event.name == 'z':
#         return
#     # for the keys we don't want to suppress, we just send the events back out
#     if event.event_type == 'down':
#         keyboard.Controller.press(event.name)
#     else:
#         keyboard.Controller.release(event.name)

def clear_current_line():
    subprocess.Popen(['/usr/bin/clear'])
    cols, rows = os.get_terminal_size()
    sys.stdout.write('\r' + ' ' * cols + '\r')
    sys.stdout.flush()

def handle_keypress(key):
    global seconds, paused, ack_waiting
    if ack_waiting and key == 'esc':
        ack_event.set()
        return

    if key not in ('+', '-', 'l', 'p'):
        return

    clear_current_line()
    if key == '+':
        seconds += 10
    if key == '-':
        seconds = max(0, seconds - 10)
    if key == 'l':
        clear_current_line()
    if key == 'p':
        paused = not paused
        time_display = str(timedelta(seconds=int(seconds)))
        sys.stdout.write(f"\rTimer paused at {time_display}")
        sys.stdout.flush()

def read_terminal_key():
    if stdin_fd is None:
        return None

    try:
        raw = os.read(stdin_fd, 1)
    except OSError:
        return None

    if not raw:
        return None
    if raw == b'\x1b':
        # Drain terminal escape sequences like arrow keys without treating them as Esc.
        while select.select([stdin_fd], [], [], 0.01)[0]:
            os.read(stdin_fd, 1)
        return 'esc'
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None

def read_terminal_keys():
    while True:
        key = read_terminal_key()
        if key is None:
            continue
        handle_keypress(key)

def on_press(key):
    if key == keyboard.Key.esc:
        handle_keypress('esc')
        return

    if terminal_input_enabled:
        return

    if not is_terminal_focused():
        return
    try:
        handle_keypress(key.char)
    except AttributeError:
        return

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
    parser.add_argument('--no-ack', action='store_true', help='Do not repeat alert until acknowledged')
    parser.add_argument('--ack-interval', type=float, default=8.0, help='Seconds between repeated alerts while waiting for acknowledgment')

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    TICKTIME = 0.1
    ack_enabled = not args.no_ack
    ack_interval = max(0.5, args.ack_interval)

    if not args.silent:
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        if setup_terminal_input():
            input_thread = threading.Thread(target=read_terminal_keys, daemon=True)
            input_thread.start()

    handle_args(args)
    exit_handler()
    show_cursor()

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
