#!/bin/bash

# Update packages
echo -e "---------------------------------------------------------------------"
echo -e "Starting apt-get update"
echo -e "---------------------------------------------------------------------"
sudo nala update && sudo nala upgrade 
# Prompt user to call autoremove
echo -e "\n---------------------------------------------------------------------"
echo -e "apt autoremove"
echo -e "---------------------------------------------------------------------"
read -p "call apt autoremove? (Y/n): " yn
# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]];
then
    :
else
    sudo nala autoremove
fi
echo -e "apt-get update done"
echo -e "\n---------------------------------------------------------------------"
echo -e "Starting snap update"
echo -e "---------------------------------------------------------------------"
sudo snap refresh 
echo -e "snap update done"
echo -e "\n---------------------------------------------------------------------"
echo -e "Starting flatpak update"
echo -e "---------------------------------------------------------------------"
flatpak update
echo -e "flatpak update done\n"


# Prompt user to clear screen
read -p "Clear screen? (Y/n): " yn

# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
fi

# Otherwise, clear the screen
clear
