#!/bin/bash
# firefox --kiosk --no-remote --class WebApp --profile /home/christian/snap/firefox/common/.mozilla/firefox/1kj8jpiu.Calendar https://mail.tutanota.com/calendar/week&
firefox --kiosk --no-remote --class WebApp --profile /home/christian/snap/firefox/common/.mozilla/firefox/1kj8jpiu.Calendar https://calendar.google.com/calendar/u/0/r/week&
sleep 3 && swaymsg workspace next && swaymsg workspace prev
# echo 'moving window'
# swaymsg "[title=\"Google Calendar\"] move workspace 13" 
# echo 'disabling fullscreen'
# swaymsg "[title=\"Google Calendar\"] fullscreen disable"
