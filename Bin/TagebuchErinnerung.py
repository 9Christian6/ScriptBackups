#!/bin/python3
import datetime

reminder_log_path = '/home/christian/Documents/TagebuchErinnerung.txt'

def get_first_line():
    with open(reminder_log_path) as reminder_file:
        return datetime.datetime.strptime(reminder_file.readline().rstrip(), '%d.%m.%Y') 


def main():
    first_line = get_first_line()
    dateDiff = datetime.datetime.today() - first_line
    if dateDiff.days > 1:
        print("Tagebuch")
        exit()
    if dateDiff.days == 1:
        if datetime.datetime.now().hour >= 18:
            print("Tagebuch")
            exit()
    print("")
    exit()


if __name__ == "__main__":
    main()
