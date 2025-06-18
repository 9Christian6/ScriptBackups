#!/bin/bash
spinner=('\' '|' '/' '-')
spinnerIndex=0
display=""
increment=0.1

if [[ $# -ne 2 ]]
then
    echo "Not the correct options, use -s, -m or -h"
    exit
fi

mode=$1
time=$2
if [[ $1 != "-m" ]] && [[ $1 != "-s" ]] && [[ $1 != "-h" ]]
then
    echo "Not the correct options, use -s, -m or -h"
    exit
fi

if [[ $1 == "-m" ]]
then
    time=$(echo "scale=1; $time * 60" | bc)
fi

if [[ $1 == "-h" ]]
then
    time=$(echo "scale=1; $time * 3600" | bc)
fi
while [ "$(bc <<< "$time > 0")"  == "1" ]
do
    time=$(echo "scale=1; $time-$increment" | bc)
    minutes=$(bc <<< "$time/60")
    seconds=$(bc <<< "$time%60")
    if [ "$(bc <<< "$seconds < 10")" == "1" ]
    then
        seconds=${seconds%.*}
        seconds="0${seconds}"
        if [ "$(bc <<< "$seconds == 0")" == "1" ]
        then
            seconds="00"
        fi
    fi
    seconds=${seconds%.*}
    if [ "$(bc <<< "$minutes > 0")"  == "1" ]
    then
        timeDisplay=$minutes
        timeDisplay+=":"
    fi
    timeDisplay+=$seconds
    spinnerDisplay="${spinner[spinnerIndex]}"
    spinnerIndex=$(echo "($spinnerIndex+1)%4" | bc)
    cols=$(tput cols)
    cols=$(echo "$cols - 9" | bc)
    printf "%s%${cols}s%s\r" "$timeDisplay" " " "$spinnerDisplay"
    timeDisplay=""
    sleep $increment
done
notify-send "Done"
# #!/bin/bash
# 
# SPINS=("←↖↑↗→↘↓↙" "▁▃▄▅▆▇█▇▆▅▄▃▁" "▉▊▋▌▍▎▏▎▍▌▋▊▉" "▖▘▝▗" "┤┘┴└├┌┬┐" "◢◣◤◥" "◰ ◳ ◲ ◱" "◴◷◶◵" "◐◓◑◒" "|/-\\")
# SPINNERINDEX=8
# DISPLAY=""
# INCREMENT=0.1
# MODE=$1
# TIME=0
# 
# function checkInput(){
#   if [ $# -lt 1 ]
#   then
#     displayHelp
#     exit
#   fi
#   for i in "$@"
#   do
#     if [[ $i == "-m" ]] || [[ $i == "-s" ]] || [[ $i == "-h" ]]
#     then
#       shift
#       next_arg=$1
#       if [[ $next_arg =~ ^[0-9]+$ ]]
#       then
# 	continue
#       else
# 	displayHelp
# 	exit
#       fi
#     fi
#   done
# }
# 
# function split() {
#   local string=$1
#   local array=()
#   for (( i=0; i<${#string}; i++ )); do
#     array+=("${string:$i:1}")
#   done
#   echo ${array[@]}
# }
# 
# function setTime() {
#   for i in "$@"
#   do
#     if [ $i == "-s" ]
#     then
#       shift
#       TIME=$(bc <<< "$TIME+$1")
#     fi
#     if [ $i == "-m" ]
#     then
#       shift
#       TIME=$(bc <<<"$TIME+$1*60")
#     fi
#     if [ $i == "-h" ]
#     then
#       shift
#       TIME=$(bc <<< "$TIME+$1*3600")
#     fi
#   done
# }
# 
# function displayTime() {
#   hours=$(bc <<< "$TIME/3600")
#   if [[ $(bc <<< "$hours < 10") == "1" ]]
#   then
#     hours="0$hours"
#   fi
#   if [[ $(bc <<< "$hours > 0") == "1" ]]
#   then
#     TIME=$(bc <<< "$TIME%3600")
#   fi
# 
#   minutes=$(bc <<< "$TIME/60")
#   if [[ $(bc <<< "$minutes < 10") == "1" ]]
#   then 
#     minutes="0$minutes"
#   fi
#   if [[ $(bc <<< "$minutes > 0") == "1" ]]
#   then 
#     TIME=$(bc <<< "$TIME%60")
#   fi
# 
#   seconds=$(bc <<< "$TIME")
#   if [[ $(bc <<< "$seconds < 10") == "1" ]]
#   then
#     seconds="0$seconds"
#   fi
# 
#   timeDisplay="$hours:$minutes:$seconds"
#   cols=$(tput cols)
#   cols=$(echo "$cols - 9" | bc)
#   printf "%s%${cols}s%s\r" "$timeDisplay" " " "$spinnerDisplay"
# }
# 
# function countDown() {
#   while [[ "$(bc <<< "$TIME > 0")" == "1" ]]
#   do
#     TIME=$(bc <<< "$TIME-$INCREMENT")
#     displayTime $@
#     sleep $INCREMENT
#   done
# }
# 
# function displayHelp(){
#   echo "Not the correct options, use -s, -m or -h"
#   exit
# }
# 
# function main(){
#   checkInput $@
#   setTime $@
# 
#   spinner=($(split "${SPINS[SPINNERINDEX]}"))
# 
#   countDown $@
# #
# #  while [ "$(bc <<< "$TIME > 0")"  == "1" ]
# #  do
# #    TIME=$(echo "scale=1; $TIME-$INCREMENT" | bc)
# #    minutes=$(bc <<< "$TIME/60")
# #    seconds=$(bc <<< "$TIME%60")
# #    if [ "$(bc <<< "$seconds < 10")" == "1" ]
# #    then
# #      seconds=${seconds%.*}
# #      seconds="0${seconds}"
# #      if [ "$(bc <<< "$seconds == 0")" == "1" ]
# #      then
# #	seconds="00"
# #      fi
# #    fi
# #    seconds=${seconds%.*}
# #    if [ "$(bc <<< "$minutes > 0")"  == "1" ]
# #    then
# #      timeDisplay=$minutes
# #      timeDisplay+=":"
# #    fi
# #    timeDisplay+=$seconds
# #    spinnerDisplay="${spinner[SPINNERINDEX]}"
# #    SPINNERINDEX=$(echo "($SPINNERINDEX+1)%4" | bc)
# #    cols=$(tput cols)
# #    cols=$(echo "$cols - 9" | bc)
# #    printf "%s%${cols}s%s\r" "$timeDisplay" " " "$spinnerDisplay"
# #    timeleftWithSpinner="$timeDisplay $spinnerDisplay"
# #    echo "$timeleftWithSpinner" > "$HOME/Bin/timeLeft"
# #    timeDisplay=""
# #    sleep $INCREMENT
# #  done
#   notify-send "Done"
# }
# 
# main $@
