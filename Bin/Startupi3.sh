#!/bin/bash	
#exec feh --bg-fill $HOME/Opt/Wallpapers/RoomAtNightCroppedWithBackground.png&
while ! ping -c 1 www.google.de &> /dev/null
do
		sleep 1
done
exec $HOME/Bin/StartAnimation.sh&
#exec $HOME/Bin/FloatingTab.sh&
exec picom&
sleep 1 
python3 $HOME/Bin/inactiveOpacityException.py&
exec $HOME/.cargo/bin/workstyle&
exec spotify&
exec $HOME/Bin/TerminalStartupi3.sh&
exec $HOME/Bin/Mails&
exec $HOME/Bin/Calendar.sh&
exec $HOME/Bin/StartSocials.sh&
exec i3-msg "workspace 1"
exec $HOME/Bin/removeUrgency
exec swaymsg 'workspace 1'
