#!/home/christian/Opt/PythonEnvs/myVirtualEnv/bin/python3
import os
import subprocess
import sys
from datetime import datetime, timedelta

journal_path = os.path.expanduser("~/Documents/Tagebuch.txt")
separator = "--------------------------------------------------------------------\n"


def format_date(date):
    return date.strftime("%d.%m.%y")


def find_date(offset_days):
    with open(journal_path, "r") as journal:
        journal.readline()
        date_line = journal.readline().strip()
        date = datetime.strptime(date_line, "%d.%m.%Y")
        new_date = date + timedelta(days=offset_days)
        return datetime.strftime(new_date, "%d.%m.%Y")


def prepend_to_journal(text):
    if os.path.exists(journal_path) and os.path.getsize(journal_path) > 0:
        with open(journal_path, "r") as original:
            journal_content = original.read()
        with open(journal_path, "w") as prepended:
            prepended.write(text + "\n" + journal_content)


def main():
    offset_days = 1
    if (len(sys.argv) > 1):
        offset_days = int(sys.argv[1])
    date_separator = f"{separator}{find_date(offset_days)}\n{separator}"
    prepend_to_journal(date_separator)
    subprocess.run(
        [
            "/home/christian/Bin/kitty",
            "--detach",
            "nvim",
            "+normal }O",
            "+startinsert",
            journal_path,
        ]
    )


if __name__ == "__main__":
    main()
