#!/bin/bash	
#exec feh --bg-fill $HOME/Opt/Wallpapers/RoomAtNightCroppedWithBackground.png&
# while ! ping -c 1 www.google.de &> /dev/null
# do
# 		sleep 10
# done
exec $HOME/Bin/connectionTest.sh&
wait
exec picom&
#exec $HOME/.cargo/bin/workstyle&
exec $HOME/Bin/startWorkstyle.sh&
exec $HOME/Bin/StartAnimation.sh&
python3 $HOME/Bin/inactiveOpacityException.py&
exec /usr/bin/gnome-calendar&
exec spotify&
exec $HOME/Bin/TerminalStartupi3.sh&
exec $HOME/Bin/Mails&
exec $HOME/Bin/StartSocials.sh&
exec i3-msg "workspace 1"
sleep 60 && exec $HOME/Bin/removeUrgency
#exec swaymsg 'workspace 1'
#exec $HOME/Bin/FloatingTab.sh&
#exec $HOME/Bin/Calendar.sh&
#exec flatpak run io.github.remindersdevs.Reminders.Devel --restart-service&
#exec flatpak run io.github.dgsasha.Remembrance&
