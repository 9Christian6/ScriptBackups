#!/bin/bash
brave --new-window --app="https://web.whatsapp.com" &
# firefox --kiosk --no-remote --name Whatsapp --profile /home/christian/snap/firefox/common/.mozilla/firefox/dz8sxtjs.Whatsapp https://web.whatsapp.com &
sleep 2
swaymsg '[app_id="Whatsapp"] fullscreen'
