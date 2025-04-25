#!/bin/bash	
#i3-sensible-terminal & sleep 5 && i3-msg '[instance=x-terminal-emulator] move to workspace 4'
alacritty&
sleep 4 
exec i3-msg '[title="christian@christiansDesktop:~"] move to workspace 4'
