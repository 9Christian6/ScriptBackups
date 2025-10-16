#!/usr/bin/env bash

# Array of clock emojis for each hour with half-hour variation
clocks=(🕛 🕧 🕐 🕜 🕑 🕝 🕒 🕞 🕓 🕟 🕔 🕠 🕕 🕡 🕖 🕢 🕗 🕣 🕘 🕤 🕙 🕥 🕚 🕦)

# Get current hour and minute
hour=$(date +%I)   # 01–12
minute=$(date +%M) # 00–59

# Convert hour/minute into index in clocks array
index=$(( (10#$hour % 12) * 2 ))
if [ "$minute" -ge 30 ]; then
  index=$((index + 1))
fi

# Print clock emoji + time
echo "${clocks[$index]} $(date +'%H:%M:%S')"
