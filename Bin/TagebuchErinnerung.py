#!/bin/python3
import datetime


def get_last_date():
    with open('/home/christian/Documents/TagebuchErinnerung.txt') as f:
        for line in f:
            pass
        last_line = line
    return datetime.datetime.strptime(last_line.rstrip(), '%d.%m.%Y')


def main():
    last_line = get_last_date()
    dateDiff = datetime.datetime.today() - last_line
    if dateDiff.days > 1:
        print("Tagebuch")
        exit()
    if dateDiff.days == 1:
        if datetime.datetime.now().hour >= 20:
            print("Tagebuch")
            exit()
    print("")
    exit()


if __name__ == "__main__":
    main()
