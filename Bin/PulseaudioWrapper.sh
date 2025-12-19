#!/usr/bin/env bash
#
# polybar-pulseaudio-wrapper.sh
# Prepends the output of $BIN/soundSinkIcon.sh to a volume+bar line for polybar.
#

# -------- config / env overrides --------
BIN="${BIN:-$HOME/Bin}"                   # fallback if $BIN not exported
ICON_SCRIPT="${BIN}/soundSinkIcon.sh"
BAR_WIDTH=15
SUFFIX=" |"
ROOT_FOREGROUND="${ROOT_FOREGROUND:-#ffffff}"   # override by exporting ROOT_FOREGROUND
LEVEL1_COLOR="#00FF00"
LEVEL2_COLOR="#FFFF00"
LEVEL3_COLOR="#FF0000"
LEVEL1_THRESHHOLD=50
LEVEL2_THRESHHOLD=80
MUTED_COLOR="#666666"
FILL_CHAR="─"
INDICATOR="|"

# -------- get prefix (icon) --------
prefix=""
if [ -x "$ICON_SCRIPT" ]; then
  prefix="$("$ICON_SCRIPT" 2>/dev/null)"
fi
prefix="$(printf '%s' "$prefix" | tr -d '\n')"
if [ -n "$prefix" ]; then
  prefix="${prefix} "
fi

# -------- get volume & mute --------
volume=""
mute="false"

if command -v pamixer >/dev/null 2>&1; then
  volume="$(pamixer --get-volume 2>/dev/null || echo 0)"
  mute="$(pamixer --get-mute 2>/dev/null || echo false)"
else
  vol_token="$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | awk '{ for(i=1;i<=NF;i++) if($i ~ /%/){ print $i; exit } }')"
  volume="${vol_token%\%}"
  mute_token="$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | awk '{print $2; exit}')"
  case "$mute_token" in
    yes) mute="true" ;;
    no)  mute="false" ;;
    *)   mute="false" ;;
  esac
fi

# normalize numeric volume and clamp
if ! [[ "$volume" =~ ^[0-9]+$ ]]; then
  volume="$(printf '%s' "$volume" | tr -cd '0-9')"
fi
volume=${volume:-0}
if [ "$volume" -lt 0 ]; then volume=0; fi
if [ "$volume" -gt 100 ]; then volume=100; fi

# -------- build bar with indicator --------
filled=$(( (volume * BAR_WIDTH) / 100 ))
if [ "$filled" -lt 0 ]; then filled=0; fi
if [ "$filled" -gt "$BAR_WIDTH" ]; then filled=$BAR_WIDTH; fi

_repeat_char() {
  local c="$1"; local n="$2"
  local s=""
  for i in $(seq 1 "$n"); do s="${s}${c}"; done
  printf '%s' "$s"
}

# --- Define thresholds ---
half_point=$(( BAR_WIDTH * 50 / 100 ))   # up to 50%
mid_point=$(( BAR_WIDTH * 80 / 100 ))    # up to 80%

# --- Determine filled segments in each color zone ---
filled_lvl1=$(( filled > half_point ? half_point : filled ))
filled_lvl2=0
filled_lvl3=0

if [ "$filled" -gt "$half_point" ]; then
  filled_lvl2=$(( filled > mid_point ? mid_point - half_point : filled - half_point ))
fi
if [ "$filled" -gt "$mid_point" ]; then
  filled_lvl3=$(( filled - mid_point ))
fi

# --- Build the colored filled portion of the bar ---
filled_part=""
if [ "$filled_lvl1" -gt 0 ]; then
  filled_part="${filled_part}%{F${LEVEL1_COLOR}}$(_repeat_char "$FILL_CHAR" "$filled_lvl1")"
fi
if [ "$filled_lvl2" -gt 0 ]; then
  filled_part="${filled_part}%{F${LEVEL2_COLOR}}$(_repeat_char "$FILL_CHAR" "$filled_lvl2")"
fi
if [ "$filled_lvl3" -gt 0 ]; then
  filled_part="${filled_part}%{F${LEVEL3_COLOR}}$(_repeat_char "$FILL_CHAR" "$filled_lvl3")"
fi

# --- Empty part ---
empty_count=$(( BAR_WIDTH - filled ))
if [ "$empty_count" -gt 0 ]; then
  empty_part="$(_repeat_char "$FILL_CHAR" "$empty_count")"
else
  empty_part=""
fi

# --- Combine everything ---
bar="${filled_part}%{F-}${INDICATOR}${empty_part}"

# --- Final output ---
if [ "$mute" = "true" ] || [ "$mute" = "yes" ]; then
  # Muted style
  printf '%%{F%s}%s %s%% %%{F%s}%s%%{F-}%s\n' \
    "$MUTED_COLOR" "$prefix" "$volume" "$MUTED_COLOR" "$bar" "$SUFFIX"
else
  # Active style: white percentage, colorized bar
  printf '%s %%{F#FFFFFF}%s%% %%{F-}%s%s%%{F-}\n' \
    "$prefix" "$volume" "$bar" "$SUFFIX"
fi
