#!/bin/bash
list="$(/home/christian/Opt/PythonEnvs/TwitchFollowedStreamers/bin/python3.12 /home/christian/Bin/TwitchFollowedStreamersList.py --no-pretty-prints --time 10)"
count=$(printf "%s\n" "$list" | wc -l)
longest=$(printf "%s\n" "$list" | awk '{ print length }' | sort -nr | head -1)
width=$(( longest * 6 ))
[ "$width" -gt 80 ] && width=80 
echo $width
streamerName=$(printf "%s\n" "$list" | rofi -i -theme-str 'entry { placeholder: "Type to search for streamer..."; } prompt { enabled: false; } window { width: 80%; } listview { lines: '$count'; }' -dmenu -fixed-num-lines "$count" | awk '{print $3}')
if [ -n "$streamerName" ]; then
  streamerURL='https://twitch.tv/'$streamerName
  brave-browser -new-window $streamerURL
fi
