#!/bin/bash
FONTSIZE=$(cat $CONFIG/i3/config|grep "font pango:monospace"|awk '{print $3}')
if [ "$FONTSIZE" -eq 0 ]; then
  sed --in-place 's/font pango:monospace 0/font pango:monospace 10/' /home/christian/.config/i3/config
else
  sed --in-place 's/font pango:monospace 10/font pango:monospace 0/' /home/christian/.config/i3/config
fi
echo $FONTSIZE
exec i3-msg "reload"
