#!/bin/bash
set -euo pipefail

if (( $# )); then
    message=$1
else
    message=$(cat /home/christian/Bin/timerMessage)
fi
[[ $message =~ [^[:space:]] ]] || message="Countdown finished"

/usr/bin/notify-send -- "$message" >/dev/null 2>&1 &
# Stay in the foreground so repeated alerts wait for speech to finish.
if [[ ${2-} == --wave ]]; then
    aplay -q "$3" </dev/null
else
    /home/christian/Bin/tts.sh --in-place "$message"
fi
