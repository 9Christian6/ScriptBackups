#!/bin/bash
# Always control the default sink shown by the volume module.
export LC_ALL=C
case "${1:-}" in
  mute) exec pactl set-sink-mute @DEFAULT_SINK@ toggle ;;
  up|down) ;;
  *) echo "Usage: $0 {up|down|mute}" >&2; exit 1 ;;
esac

# Serialize read/modify/write so rapid scrolling does not lose volume steps.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/sound-volume-${UID}.lock"
flock -x 9
volume_output=$(pactl get-sink-volume @DEFAULT_SINK@) || exit 1
if [[ "$volume_output" =~ ([0-9]+)% ]]; then
  current_volume=${BASH_REMATCH[1]}
else
  exit 1
fi
if [[ "$1" == up ]]; then
  new_volume=$((current_volume + 5))
else
  new_volume=$((current_volume - 5))
fi
((new_volume > 100)) && new_volume=100
((new_volume < 0)) && new_volume=0
exec pactl set-sink-volume @DEFAULT_SINK@ "${new_volume}%"
