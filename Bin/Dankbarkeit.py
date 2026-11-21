#!/bin/python3
import os
import sys
import subprocess
import time
import datetime

def get_next_weekday(target_weekday):
    today = datetime.today()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # Ensure it picks the next occurrence, not today
    return today + timedelta(days=days_ahead)

def format_date(date):
    return date.strftime('%d.%m.%y')

def get_formatted_string():
    next_wednesday = get_next_weekday(2)  # 2 = Wednesday
    next_sunday = get_next_weekday(6)  # 6 = Sunday

    if (next_wednesday - datetime.today()).days < (next_sunday - datetime.today()).days:
        closer_day = "Wednesday"
        closer_date = next_wednesday
    else:
        closer_day = "Sunday"
        closer_date = next_sunday
    return closer_date

def main():
    string="--------------------------------------------------------------------\n"
    today = datetime.today()
    sundayDelta = timedelta()
    sunday = today - timedelta(days=today.weekday() - 6)
    formatted_sunday = sunday.strftime("%d.%m.%Y")
    string+="Woche vom " + get_formatted_string() +"\n"
    string+="--------------------------------------------------------------------\n"
    with open("/home/christian/Desktop/Dankbarkeitstagebuch", "a") as f:
        f.write(string)
    subprocess.run(["alacritty", "-e", "nvim", "/home/christian/Desktop/Dankbarkeitstagebuch"])
    #subprocess.run(["alacritty", "-e nvim + /home/christian/Desktop/Dankbarkeitstagebuch"])
    #tagebuchPath = os.path.expanduser("~/Desktop/Dankbarkeitstagebuch")
    #subprocess.run(["nvim", tagebuchPath])

    file_path = os.path.expanduser("~/Opt/DankbarkeitstagebuchErinnerung.txt")
    current_date = datetime.datetime.today().strftime('%d.%m.%Y')
    with open(file_path, "a") as f:
        f.write(f"{current_date}\n")

if __name__ == "__main__":
    main()
