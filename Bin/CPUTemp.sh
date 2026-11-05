#!/bin/bash

BARE_FLAG=$1
# --- Configuration ---
GREEN_LIMIT=30   # harmless
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

USAGE_INT=$(vmstat 1 3 | awk 'NR>3 {idle+=$15; count++} END {if(count>0) printf "%d", 100 - (idle/count); else print "No data"}')

if [ "$USAGE_INT" -lt "$GREEN_LIMIT" ]; then
  COLOR="#6000FF"   # Green
  ICON=""
elif [ "$USAGE_INT" -lt "$YELLOW_LIMIT" ]; then
  COLOR="#8000FF"   # Yellow
  ICON=""
else
  COLOR="#FF00FF"   # Red
  ICON=""
fi
# --- Choose color & icon based on temperature ---
# if [ "$TEMP_INT" -lt "$GREEN_LIMIT" ]; then
#   COLOR="#00FF00"   # Green
#   ICON=""
# elif [ "$TEMP_INT" -lt "$YELLOW_LIMIT" ]; then
#   COLOR="#FFFF00"   # Yellow
#   ICON=""
# else
#   COLOR="#FF0000"   # Red
#   ICON=""
# fi

if [ -n "$BARE_FLAG" ]; then
  echo "%{F$COLOR}%{F-}"
  exit
fi

# --- Output for Polybar ---
echo "${TEMP_INT}°C %{F$COLOR}%{F-}"
