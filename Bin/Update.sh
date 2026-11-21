#!/bin/bash

# # Define colors
# GREEN='\033[0;32m'
# NC='\033[0m'
# # Update packages
# echo -e "---------------------------------------------------------------------"
# printf "${GREEN}"
# echo -e "Starting apt update"
# printf "${NC}"
# echo -e "---------------------------------------------------------------------"
# sudo nala update && sudo nala upgrade 
# printf "${GREEN}"
# echo -e "apt update done"
# printf "${NC}"
# echo -e "\n---------------------------------------------------------------------"
# printf "${GREEN}"
# echo -e "Starting snap update"
# printf "${NC}"
# echo -e "---------------------------------------------------------------------"
# sudo snap refresh 
# printf "${GREEN}"
# echo -e "snap update done"
# printf "${NC}"
# echo -e "\n---------------------------------------------------------------------"
# printf "${GREEN}"
# echo -e "Starting flatpak update"
# printf "${NC}"
# echo -e "---------------------------------------------------------------------"
# sudo flatpak update
# printf "${GREEN}"
# echo -e "flatpak update done\n"
# printf "${NC}"
# 
# #promt the user if update should be executed again
# read -p "Update again? (Y/n): " yn
# if [[ "$yn" == "n" ]]; then
#     :
# else
#     clear
#     exec $HOME/Bin/Update.sh
# fi
# 
# # Prompt user to clear screen
# echo " "
# read -p "Clear screen? (Y/n): " yn
# # If user entered "n", exit the script without clearing the screen
# if [[ "$yn" == "n" ]]; then
#     exit 0
# else
#   #su -c '/home/christian/Bin/Clear.sh' christian
#   $HOME/Bin/Clear.sh
# fi
# Define colors
GREEN='\033[0;32m'
MAGENTA='\033[38;2;255;0;255m'
NC='\033[0m'
# Update packages

box() {
  local msg="$1"
  local cols
  cols=$(tput cols)

  # Leave 8 columns of margin to prevent wrapping
  local inner=$((cols - 8))

  printf "${MAGENTA}"

  # Top
  printf "╭"
  printf '─%.0s' $(seq 1 "$inner")
  printf "╮\n"

  # Middle
  printf "│ %-*s│\n" "$((inner-1))" "$msg"
  
  # Bottom
  printf "╰"
  printf '─%.0s' $(seq 1 "$inner")
  printf "╯\n"

  printf "${NC}"
}


box "Starting apt update"
sudo nala update && sudo nala upgrade
box "apt update done"

echo

box "Starting snap update"
sudo snap refresh
box "snap update done"

echo

box "Starting flatpak update"
sudo flatpak update
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
