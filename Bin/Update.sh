#!/bin/bash

# Update packages
echo -e "---------------------------------------------------------------------"
echo -e "Starting apt-get update"
echo -e "---------------------------------------------------------------------"
nala update && nala upgrade 
echo -e "apt-get update done"
echo -e "\n---------------------------------------------------------------------"
echo -e "Starting snap update"
echo -e "---------------------------------------------------------------------"
snap refresh 
echo -e "snap update done"
echo -e "\n---------------------------------------------------------------------"
echo -e "Starting flatpak update"
echo -e "---------------------------------------------------------------------"
flatpak update
echo -e "flatpak update done\n"

#promt the user if update should be executed again
read -p "Update again? (Y/n): " yn
if [[ "$yn" == "n" ]]; then
    :
else
    exec /home/christian/Bin/Update.sh
fi

# Prompt user to clear screen
echo " "
read -p "Clear screen? (Y/n): " yn
# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
else
    clear
fi
