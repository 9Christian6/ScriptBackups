#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import os
import subprocess
from datetime import datetime, timedelta

separator = "--------------------------------------------------------------------\n"
journal_path = os.path.expanduser("~/Documents/Dankbarkeitstagebuch.txt")
reminder_path = os.path.expanduser("~/Documents/DankbarkeitstagebuchErinnerung.txt")


def prepend_to_journal(text):
    if os.path.exists(journal_path) and os.path.getsize(journal_path) > 0:
        with open(journal_path, "r") as original:
            journal_content = original.read()
        with open(journal_path, "w") as prepended:
            prepended.write(text + "\n" + journal_content)
            

def format_date(date):
    return date.strftime('%d.%m.%y')


def main():
    closer_date = datetime.today()
    while closer_date.weekday() not in [2, 6]:
        closer_date = closer_date - timedelta(days=1)

    date_separator = f"{separator}Woche vom {format_date(closer_date)}\n{separator}"
    prepend_to_journal(date_separator)
    subprocess.run([ "kitty", "--detach", "nvim", "+normal }O", "+startinsert", journal_path ])

if __name__ == "__main__":
    main()
