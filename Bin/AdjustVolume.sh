#!/bin/bash
# Get the currently active sink
sinkNumber=$(pactl list sinks short | grep RUNNING | awk '{print $1}')

# Fallback: if no sink is running, pick the first available one
if [ -z "$sinkNumber" ]; then
  sinkNumber=$(pactl list sinks short | head -n 1 | awk '{print $1}')
fi

# Get current volume (average of left/right channels)
current_volume=$(pactl get-sink-volume "$sinkNumber" | awk '{print $5}' | head -n 1 | tr -d '%')

# Mute/unmute
if [ "$1" == "mute" ]; then
  pactl set-sink-mute "$sinkNumber" toggle
  exit 0
fi

# Change volume
if [ "$1" == "up" ]; then
  new_volume=$(( current_volume + 5 ))
elif [ "$1" == "down" ]; then
  new_volume=$(( current_volume - 5 ))
else
  echo "Usage: $0 {up|down|mute}"
  exit 1
fi

# Clamp the volume between 0 and 100
if [ "$new_volume" -gt 100 ]; then new_volume=100; fi
if [ "$new_volume" -lt 0 ]; then new_volume=0; fi

# Apply the new volume
pactl set-sink-volume "$sinkNumber" "${new_volume}%"
