#!/bin/sh
pkill -SIGUSR1 dunst
/home/christian/Bin/i3lock-color --color 00000000 --clock --indicator --time-str="%H:%M:%S" --screen 1 --time-color='#ee00eeee' --date-color='#ee00eeee' --verif-color='#ee00eeee' --wrong-color='#ee00eeee' --layout-color='#ee00eeee' --ring-color='#ee00eeee' --line-color='#ee00eeee' --insidever-color='#00ee00' --ringver-color='#00ee00' --nofork
pkill -SIGUSR2 dunst
