#!/bin/bash
counter=0
while true; do
  result=$("$HOME/Bin/checkInternetConnection.sh")
  echo "$result"
  
  if [[ "$result" == "0" ]]; then
    exit 0
  fi

  ((counter++))  # Increment before checking the limit

  if (( counter > 100 )); then
    exit 1
  fi

  sleep 1
  echo "$counter"
done
