#!/bin/bash
picomPID=$(exec pidof picom)
echo $picomPID
if [ -n "$picomPID" ]; then
  killall picom
else
  exec $BIN/StartPicom.sh
fi
