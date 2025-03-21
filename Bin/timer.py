#!/usr/bin/env python3
import time
import sys
import os
import subprocess
import argparse
import signal
from datetime import datetime, timedelta
from pynput import keyboard
from pynput.keyboard import Key, Listener

spinner = ['|', '/', '-', '\\']
seconds = 0
crtlPressed = False

def signal_handler(sig, frame):
    global seconds
    seconds = int(seconds)
    if seconds == 1:
        sys.stdout.write(f"\rCounting interrupted at {seconds} second!\n")
    else:
        sys.stdout.write(f"\rCounting interrupted at {seconds} seconds!\n")
    sys.exit(0)

def countup_seconds():
    global spinner
    global seconds
    while True:
        columns = os.get_terminal_size().columns - 15
        time_display = str(timedelta(seconds=int(seconds)))
        spinner_char = spinner[int(seconds * 10 % 4)]
        sys.stdout.write(f"\r{time_display.ljust(columns)}{spinner_char}")
        sys.stdout.flush()
        time.sleep(0.1)
        seconds = round(seconds + 0.1, 1)

def countdown_seconds(message):
    global spinner
    global seconds
    while seconds > 0:
        columns = os.get_terminal_size().columns - 2
        time_display = str(timedelta(seconds=int(seconds)))
        with open('/home/christian/Bin/timeLeft', 'w') as f:
            f.write(time_display)
        spinner_char = spinner[int(seconds * 10 % 4)]
        sys.stdout.write(f"\r{time_display.ljust(columns)}{spinner_char}")
        sys.stdout.flush()
        time.sleep(0.1)
        seconds = round(seconds - 0.1, 1)
        with open('/home/christian/Bin/timeLeft', 'w') as f:
            f.write('')
    if message != "":
        print("\033[A                             \033[A")
        #sys.stdout.write(f"\r{message}")
        print(message, flush=True)
        subprocess.Popen(['notify-send', message])
    else:
        sys.stdout.write("\rCountdown finished\n")
        subprocess.Popen(['notify-send', 'Countdown finished'])
    #subprocess.Popen(['play', '/home/christian/Music/Bellsound.aiff', '-q', stdout=None])
    #subprocess.run("nohup play /home/christian/Music/Bellsound.aiff -q", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    subprocess.Popen("play /home/christian/Music/Bellsound.aiff -q", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def on_press(key):
    global seconds
    try:
        if key.char == ('+'):
            seconds+= 10
        if key.char == ('-'):
            seconds-= 10
        if key.char == ('l'):
            os.system('clear')
        if key == keyboard.Key.crtl:
            os.system('cls')
    except:
        return

def on_release(key):
    global crtlPressed
    if key == Keyboard.Key.crtl:
        crtlPressed = False

def main():
    global seconds

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    parser = argparse.ArgumentParser(
        prog='Timer',
        description='A simple timer',
        epilog='Enjoy the program!',
    )
    parser.add_argument('-s', '--seconds', type=int, help='Number of seconds')
    parser.add_argument('-m', '--minutes', type=int, help='Number of minutes')
    parser.add_argument('-r', '--run', action='store_true', help='Runs a timer that counts up in seconds indefinitely')
    parser.add_argument('-t', '--time', type=str, help='Counts until the given time in the format HH:MM:SS')
    parser.add_argument('--message', type=str, help='Message that is displayed when timer runs up')

    if (sys.argv.__len__() <= 1):
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()

    if args.time:
        try:
            time_str = args.time
            now = datetime.now()
            if len(time_str) < 8:
                time_obj = datetime.strptime(time_str, '%H:%M').time()
            else:
                time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
            next_occurance = datetime.combine(now, time_obj)
            if next_occurance <= now:
                next_occurance += timedelta(days=1)
            seconds = (next_occurance - now).total_seconds()
        except ValueError:
            sys.stderr.write("Invalid time format. Use HH:MM:SS.\n")
            sys.exit(1)

    if args.run:
        countup_seconds()

    if args.seconds:
        seconds += args.seconds

    if args.minutes:
        seconds += args.minutes * 60

    if args.message:
        message = args.message
    else:
        message = ""

    if seconds > 0:
        countdown_seconds(message)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    main()
