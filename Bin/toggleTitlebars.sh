#!/bin/bash
FONTSIZE=$(cat /home/christian/.config/i3/config|grep "font pango:monospace"|awk '{print $3}')
if [ "$FONTSIZE" -eq 0 ]; then
  sed --in-place 's/font pango:monospace 0/font pango:monospace 10/' /home/christian/.config/i3/config
else
  sed --in-place 's/font pango:monospace 10/font pango:monospace 0/' /home/christian/.config/i3/config
fi
exec i3-msg "reload" >> /dev/null
