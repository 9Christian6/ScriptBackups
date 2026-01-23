#!/bin/bash

LOG_DIR="$HOME/ScriptOutputs"
TIME="$(date '+%H:%M:%S')"
DATE="$(date '+%d.%m.%Y')"
TIMESTAMP="📅: $DATE, 🕒: $TIME"
#TIMESTAMP="$(date '+%H:%M:%S %d.%m.%Y')"

LASTCHAR=$(tail -c 1 "$LOG_DIR/stdout.log")

if [ -n "$LASTCHAR" ]; then
  echo >> "$LOG_DIR/stdout.log"
fi

if [ "$1" == "-r" ]; then
  RESTARTSTRING=$'Restart\n'
  TIMESTAMP="${RESTARTSTRING}${TIMESTAMP}"
  shift
fi

# 1. Log the execution start to stdout file
echo "" >> "$LOG_DIR/stdout.log"
echo "$TIMESTAMP" >> "$LOG_DIR/stdout.log"
echo ": \"$@\"" >> "$LOG_DIR/stdout.log"

function runInBackground(){
  echo -n "$: " >> "$LOG_DIR/stdout.log"
  # 2. Run the command
  # - Stdin is redirected from /dev/null to prevent nohup warnings.
  # - Stdout appends to your stdout log.
  # - Stderr is redirected to a process substitution >(...)
  nohup "$@" < /dev/null >> "$LOG_DIR/stdout.log" 2> >(
    # This block runs only for the error stream
    if read -r line; then
      # If we successfully read a line, it means there IS an error.
      # Print the timestamp header to stderr log
      echo "$TIMESTAMP \"$1\":" >> "$LOG_DIR/stderr.log"

      # Print the line we just captured
      echo "$line" >> "$LOG_DIR/stderr.log"

      # Use 'cat' to print the rest of the error stream (if any)
      cat >> "$LOG_DIR/stderr.log"
    fi
  )&
}

runInBackground "$@" &
