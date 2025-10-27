#!/bin/bash

# --- Configuration ---
GREEN_LIMIT=50   # harmless
YELLOW_LIMIT=70  # under load
# Above 70°C is dangerous (red)

# --- Get temperature from sensors ---
TEMP_RAW=$(/usr/bin/sensors | awk '{print $2}' | sed -n '3p')

# --- Clean up the raw value ---
TEMP_CLEAN=$(echo "$TEMP_RAW" | tr -d '+°C' | sed 's/,/./g' | sed 's/[^0-9.]//g')

# --- Handle empty or invalid output ---
if [[ -z "$TEMP_CLEAN" ]]; then
  TEMP_CLEAN=0
fi

# --- Convert to integer safely ---
# (awk ensures numeric output; if invalid, defaults to 0)
TEMP_INT=$(awk -v t="$TEMP_CLEAN" 'BEGIN {
  if (t ~ /^[0-9]+(\.[0-9]+)?$/) printf "%d", t;
  else print 0;
}')

# --- Choose color & icon based on temperature ---
if [ "$TEMP_INT" -lt "$GREEN_LIMIT" ]; then
  COLOR="#00FF00"   # Green
  ICON=""
elif [ "$TEMP_INT" -lt "$YELLOW_LIMIT" ]; then
  COLOR="#FFFF00"   # Yellow
  ICON=""
else
  COLOR="#FF0000"   # Red
  ICON=""
fi

# --- Output for Polybar ---
echo "%{F$COLOR}${ICON} ${TEMP_INT}°C%{F-}"

