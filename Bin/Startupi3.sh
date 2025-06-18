#!/bin/bash	
exec $HOME/Bin/connectionTest.sh&
wait
exec $HOME/Opt/picom-animations/build/src/picom --config /home/christian/.config/picom/picom.conf --experimental-backends --animations --glx-no-stencil --glx-no-rebind-pixmap -b&
exec $HOME/Bin/startWorkstyle.sh&
exec $HOME/Bin/StartAnimation.sh&
exec $HOME/Bin/FloatingTab.sh&
python3 $HOME/Bin/inactiveOpacityException.py&
exec /usr/bin/gnome-calendar&
exec spotify&
exec $HOME/Bin/TerminalStartupi3.sh&
exec $HOME/Bin/Mails&
exec $HOME/Bin/StartSocials.sh&
exec /snap/bin/teams-for-linux&
exec /snap/bin/todoist&
