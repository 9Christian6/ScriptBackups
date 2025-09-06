#!/bin/bash
bar_height="$(xwininfo -name "polybar-right_DVI-D-0" | grep Height | awk '{print $2}')"
declare -A rename_map
rename_map["alsa_output.usb-ASUS_Xonar_U7-00.analog-stereo"]="Kopfhörer"
rename_map["alsa_output.pci-0000_04_00.1.hdmi-stereo-extra1"]="Monitor"

move_sink_inputs() {
  sink="$1"
  [ -n "$sink" ] || return 1

  sink_inputs=$(pactl list sink-inputs) || return 1

  while read -r sink_input; do
    index=$(echo "$sink_input" | grep -oP "\d+$")
    pactl move-sink-input "$index" "$sink" || return 1
  done < <(echo "$sink_inputs" | grep "Sink Input")
}

list_sinks() {
  # Get sinks as an array
  mapfile -t sinks < <(pactl list sinks short | awk '{print $2}') || return 1
  for sink in "${sinks[@]}"; do
    case "$sink" in
      alsa_output.usb-ASUS_Xonar_U7-00.analog-stereo)
        echo "🎧 Kopfhörer $sink"
        ;;
      alsa_output.pci-0000_04_00.1.hdmi-stereo-extra1)
        echo "🖥️ Monitor $sink"
        ;;
      *)
        # Default: show the original sink name
        #echo "$sink"
        ;;
    esac
  done
}

select_sink() {
  sink="$(list_sinks | rofi -dmenu -no-custom -theme-str 'inputbar { enabled: false; } listview { lines: 2; }' -l 2 -location 5 -anchor west -yoffset -27 -xoffset -400 -p "Pick a sound sink")" || return 1
  sink="$(echo "$sink" | cut -f 3 -d " ")"
  echo "$sink"
  [ -n "$sink" ] || return 1

  pactl set-default-sink $sink || return 1
  move_sink_inputs $sink || return 1
}

case "$1" in
  list) list_sinks || exit 1;;
  current);;
  *) select_sink || exit 1;;
esac

exit 0
