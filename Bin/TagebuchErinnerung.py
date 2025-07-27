#!/bin/python3
import os
import datetime
import calendar

with open('/home/christian/Opt/TagebuchErinnerung.txt') as f:
    for line in f:
        pass
    last_line = line
last_line = last_line.rstrip()
lastLineDate = datetime.datetime.strptime(last_line, '%d.%m.%Y')
today = datetime.datetime.today().strftime('%d.%m.%Y')
todayDate = datetime.datetime.strptime(today, '%d.%m.%Y')
dateDiff = todayDate - lastLineDate
if dateDiff.days == 0:
    exit()
if dateDiff.days > 1:
    print("Tagebuch")
    exit()
if datetime.datetime.now().hour >= 17:
    print("Tagebuch")
    exit()
exit()
