#!/bin/sh
pkill -SIGUSR1 dunst
#/home/christian/Bin/i3lock-color --color 000000FF --clock --indicator --time-str="%H:%M:%S"\
#/home/christian/Opt/i3lock-color/build/i3lock --color 000000FF --clock --indicator --time-str="%H:%M:%S" --screen 1 --time-color='#ee00eeee' --date-color='#ee00eeee' --verif-color='#ee00eeee' --wrong-color='#ee00eeee' --layout-color='#ee00eeee' --ring-color='#ee00eeee' --line-color='#ee00eeee' --insidever-color='#00ee00' --ringver-color='#00ee00' --nofork
BLANK='#00000000'
CLEAR='#ffffff22'
DEFAULT='#ff00ffcc'
TEXT='#ee00eeee'
WRONG='#00ee00ee'
VERIFYING='#bb00bbbb'

/home/christian/Opt/i3lock-color/build/i3lock 	\
--insidever-color=$CLEAR     			\
--ringver-color=$VERIFYING   			\
\
--insidewrong-color=$CLEAR   			\
--ringwrong-color=$WRONG     			\
\
--inside-color=$BLANK        			\
--ring-color=$DEFAULT        			\
--line-color=$BLANK          			\
--separator-color=$DEFAULT   			\
\
--verif-color=$TEXT          			\
--wrong-color=$TEXT          			\
--time-color=$TEXT           			\
--date-color=$TEXT           			\
--layout-color=$TEXT         			\
--keyhl-color=$WRONG         			\
--bshl-color=$WRONG          			\
  \
--screen 2                   			\
--blur 2                     			\
--clock                      			\
--indicator                  			\
--time-str="%H:%M:%S"        			\
--date-str="%A, %Y-%m-%d"       		\
--keylayout 1                			\
--color $BLANK					\
pkill -SIGUSR2 dunst
