#!/bin/bash	
# Clear urgency while autostart applications load; normal urgency resumes after 90s.
/usr/bin/python3 /home/christian/Bin/clearStartupUrgency.py &
exec /home/christian/Bin/StartWorkspaceHistory.sh&
exec /home/christian/Bin/StartSocials.sh&
exec /home/christian/Bin/StartupTerminali3.sh&
exec spotify&
# exec /home/christian/Bin/Soundcloud.sh&
exec /home/christian/Bin/NextcloudBraveLogin.py --hizmail &
exec /home/christian/Bin/NextcloudBraveLogin.py --protonmail &
exec thunderbird&

exec /snap/bin/discord&
# exec /usr/bin/nextcloud --background&
# exec /home/christian/Bin/Mails.sh&
# exec /home/christian/Bin/NextcloudBraveLogin.py --calendar &
# exec /home/christian/Bin/NextcloudBraveLogin.py --photos &
# exec /home/christian/Bin/NextcloudBraveLogin.py --tasks &
