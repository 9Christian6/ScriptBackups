#!/bin/bash

# Update packages
sudo apt-get update && sudo apt-get upgrade && sudo snap refresh && flatpak update

# Prompt user to clear screen
read -p "Clear screen? (Y/n): " yn

# If user entered "n", exit the script without clearing the screen
if [[ "$yn" == "n" ]]; then
    exit 0
fi

# Otherwise, clear the screen
clear
