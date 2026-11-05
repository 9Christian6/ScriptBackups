#!/bin/sh
BLANK='#00000000'
CLEAR='#ffffffff'
DEFAULT='#ff00ffff'
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
  --color $BLANK					\
  --clock                      			\
  --blur 2                     			\
  --indicator                  			\
  --time-str="%S:%M:%H"        			\
  --date-str="%A, %d.%m.%Y"       		\
  --keylayout 1                			\
