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
