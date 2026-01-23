#!/bin/bash

LOG_DIR="$HOME/ScriptOutputs"
TIME="$(date '+%H:%M:%S')"
DATE="$(date '+%d.%m.%Y')"
TIMESTAMP="📅: $DATE, 🕒: $TIME"
#TIMESTAMP="$(date '+%H:%M:%S %d.%m.%Y')"

# 1. Log the execution start to stdout file
echo "$TIMESTAMP" >> "$LOG_DIR/stdout"
echo ": \"$@\"" >> "$LOG_DIR/stdout"

function runInBackground(){
  echo -n "$: " >> "$LOG_DIR/stdout"
  # 2. Run the command
  # - Stdin is redirected from /dev/null to prevent nohup warnings.
  # - Stdout appends to your stdout log.
  # - Stderr is redirected to a process substitution >(...)
  nohup "$@" < /dev/null >> "$LOG_DIR/stdout" 2> >(
    # This block runs only for the error stream
    if read -r line; then
      # If we successfully read a line, it means there IS an error.
      # Print the timestamp header to stderr log
      echo "$TIMESTAMP \"$1\":" >> "$LOG_DIR/stderr"

      # Print the line we just captured
      echo "$line" >> "$LOG_DIR/stderr"

      # Use 'cat' to print the rest of the error stream (if any)
      cat >> "$LOG_DIR/stderr"
    fi
  )
  echo "" >> "$LOG_DIR/stdout"
}

runInBackground "$@" &
# 3. Append a spacer line to stdout
