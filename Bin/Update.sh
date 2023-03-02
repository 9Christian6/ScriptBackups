#!/bin/bash

# Update packages
echo -e "Starting apt-get update\n"
sudo apt-get update && sudo apt-get upgrade 
# Prompt user to call autoremove
read -p "call apt autoremove? (Y/n): " yn
# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
fi
sudo apt autoremove
echo -e "apt-get update done"
echo -e "---------------------------------------------------------------------"
echo -e "\nStarting snap update\n"
sudo snap refresh 
echo -e "snap update done"
echo -e "---------------------------------------------------------------------"
echo -e "\nStarting flatpak update\n"
flatpak update
echo -e "flatpak update done"
echo -e "---------------------------------------------------------------------"


# Prompt user to clear screen
read -p "Clear screen? (Y/n): " yn

# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
fi

# Otherwise, clear the screen
clear
