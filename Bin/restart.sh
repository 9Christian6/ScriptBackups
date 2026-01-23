#!/bin/bash

LOG_DIR="$HOME/ScriptOutputs"

if [ -z "$1" ]; then
  echo "Usage: ./restart.sh <script_name> [args...]"
  exit 1
fi

if [ "$1" == "-h" ]; then
  echo "Usage: ./restart.sh <script_name> [args...]"
  exit 1
fi

TARGET=$1
PIDS=$(pgrep -fA "$TARGET" | grep -v ^$$\$)
echo "$PIDS"
if [ -n "$PIDS" ]; then
  /usr/bin/kill $PIDS
  echo "killed target"
  sleep 1
fi

exec "$BIN/startSilent.sh" -r "$@" &
