#!/bin/bash	
/home/christian/Bin/power-dim.sh &
/home/christian/Bin/StartSocials.sh &
/home/christian/Bin/StartupTerminali3.sh &
spotify &
/home/christian/Bin/Mails &
mails_pid=$!
#exec /home/christian/Bin/Calendar.sh&

wait "$mails_pid"

for window_id in $(wmctrl -l | awk '{print $1}'); do
  wmctrl -i -r "$window_id" -b remove,demands_attention >/dev/null 2>&1
done

i3-msg 'workspace number 1' >/dev/null 2>&1

