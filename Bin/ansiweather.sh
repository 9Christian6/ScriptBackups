#!/bin/zsh
WEATHER=$(ansiweather | awk '{print $6" "$4$5}')
echo $WEATHER 
echo $WEATHER > /home/christian/Opt/ansiweatherDisplayPolybar/weather
