#!/bin/bash
MESSAGE=$1
exec /home/christian/Bin/tts.sh --in-place "$MESSAGE"&
exec /usr/bin/notify-send "$MESSAGE"
