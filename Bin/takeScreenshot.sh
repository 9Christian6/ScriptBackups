#!/bin/bash
fileName=$((echo "/home/christian/Pictures/Screenshots/Screenshot"; ls /home/christian/Pictures/Screenshots | wc -l ; echo ".png") | paste -d" " -s | sed s/' '//g)
scrot -s -F $fileName
