#!/bin/python3
import os
import subprocess
from datetime import datetime, timedelta


def get_next_weekday(target_weekday):
    today = datetime.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # Ensure it picks the next occurrence, not today
    return today + timedelta(days=days_ahead)


def format_date(date):
    return date.strftime('%d.%m.%y')


def main():
    # Define file paths
    journal_path = os.path.expanduser("~/Desktop/Tagebuch")
    reminder_path = os.path.expanduser("~/Opt/TagebuchErinnerung.txt")

    # Create a separator line
    separator = "--------------------------------------------------------------------\n"

    # Get today's date and compute the Sunday of the current week
    today = datetime.today()
    formatted_today = today.strftime("%d.%m.%Y")

    # Read the last line of the file if it exists
    last_line = ""
    if os.path.exists(journal_path) and os.path.getsize(journal_path) > 0:
        with open(journal_path, "r") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()  # Read the last line and remove trailing newlines

    # Only write the new entry if the last line isn't already a separator
    if last_line != separator.strip():
        entry = f"\n{separator}{formatted_today}\n{separator}"
        with open(journal_path, "a") as f:
            f.write(entry)

    # Open the journal in Alacritty with Neovim
    subprocess.run(["alacritty", "-e", "nvim", "+normal Go", "+startinsert", journal_path])

    # Log the current date in the reminder file
    current_date = today.strftime('%d.%m.%Y')
    with open(reminder_path, "a") as f:
        f.write(f"{current_date}\n")


if __name__ == "__main__":
    main()
