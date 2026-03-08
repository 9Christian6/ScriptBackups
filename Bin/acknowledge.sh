#!/bin/bash
QUERYCOMMAND="/home/christian/Bin/reminderScript.py query --format text"
PENDING=$($QUERYCOMMAND)
if [[ -z "$PENDING" ]]; then
  exit 0
else
  SELECTEDEVENT=$($QUERYCOMMAND |  awk '{print $1}' | rofi -dmenu -theme-str '
  window {width: 30%;}
  mainbox {children: [listview];}
  listview {dynamic: true; fixed-height: false;}
  ')
  if [[ -z "$SELECTEDEVENT" ]]; then
    notify-send "No Event Acknowledged"
    exit 0
  else
    ACKCOMMAND="/home/christian/Bin/reminderScript.py acknowledge --name $SELECTEDEVENT"
    echo $ACKCOMMAND
    RESPONSE=$($ACKCOMMAND)
    notify-send "$RESPONSE"
  fi
fi
