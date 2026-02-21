#!/bin/bash

# Define colors
GREEN='\033[0;32m'
MAGENTA='\033[38;2;255;0;255m'
NC='\033[0m'
# Update packages

box() {
  local msg="$1"
  local cols inner
  cols=$(tput cols 2>/dev/null)
  [[ -z "$cols" || "$cols" -lt 20 ]] && cols=80
  inner=$((cols - 2))

  local hr
  printf -v hr '%*s' "$inner" ''
  hr=${hr// /─}

  printf "%b╭%s╮%b\n" "${MAGENTA}" "$hr" "${NC}"
  printf "%b│%b%-*s%b│%b\n" "${MAGENTA}" "${NC}" "$inner" "$msg" "${MAGENTA}" "${NC}"
  printf "%b╰%s╯%b\n" "${MAGENTA}" "$hr" "${NC}"
}

print_box_top() {
  local inner="$1"
  local hr
  printf -v hr '%*s' "$inner" ''
  hr=${hr// /─}
  printf "%b╭%s╮%b\n" "${MAGENTA}" "$hr" "${NC}"
}

print_box_bottom() {
  local inner="$1"
  local hr
  printf -v hr '%*s' "$inner" ''
  hr=${hr// /─}
  printf "%b╰%s╯%b\n" "${MAGENTA}" "$hr" "${NC}"
}

print_box_line() {
  local content_width="$1"
  local line="$2"
  local chunk

  line=$(sanitize_line "$line")

  # Split long lines so borders stay aligned
  while [[ ${#line} -gt content_width ]]; do
    chunk=${line:0:content_width}
    printf "%b│%b%-*s%b│%b\n" "${MAGENTA}" "${NC}" "$content_width" "$chunk" "${MAGENTA}" "${NC}"
    line=${line:content_width}
  done
  printf "%b│%b%-*s%b│%b\n" "${MAGENTA}" "${NC}" "$content_width" "$line" "${MAGENTA}" "${NC}"
}

sanitize_line() {
  local line="$1"

  # Remove carriage-return progress updates and ANSI control sequences.
  line=${line//$'\r'/}
  line=$(printf '%s' "$line" | sed -E $'s/\x1B\\[[0-9;?]*[ -/]*[@-~]//g')
  printf '%s' "$line"
}

run_in_box() {
  local cols inner content_width
  cols=$(tput cols 2>/dev/null)
  [[ -z "$cols" || "$cols" -lt 20 ]] && cols=80
  inner=$((cols - 2))
  content_width=$inner

  print_box_top "$inner"
  "$@" 2>&1 | while IFS= read -r line || [[ -n "$line" ]]; do
    print_box_line "$content_width" "$line"
  done
  local cmd_status=${PIPESTATUS[0]}
  print_box_bottom "$inner"
  return "$cmd_status"
}


box "Starting apt update"
run_in_box sudo nala update && run_in_box sudo nala upgrade
box "apt update done"

echo

box "Starting snap update"
run_in_box sudo snap refresh
box "snap update done"

echo

box "Starting flatpak update"
run_in_box sudo flatpak update
box "flatpak update done"
#promt the user if update should be executed again
read -p "Update again? (Y/n): " yn
if [[ "$yn" == "n" ]]; then
    :
else
    clear
    exec $HOME/Bin/Update.sh
fi

# Prompt user to clear screen
echo " "
read -p "Clear screen? (Y/n): " yn
# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
else
  #su -c '/home/christian/Bin/Clear.sh' christian
  $HOME/Bin/Clear.sh
fi
