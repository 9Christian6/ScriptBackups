#!/bin/bash
sinkNumber=$(pactl list sinks short | grep RUNNING | awk '{print $1}')
if [ "$1" == "up" ]; then
		pactl set-sink-volume $sinkNumber +5%
elif [ "$1" == "down" ]; then
		pactl set-sink-volume $sinkNumber -5%
elif [ "$1" == "mute" ]; then
		pactl set-sink-mute $sinkNumber toggle
fi
