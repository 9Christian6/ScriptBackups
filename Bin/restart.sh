#!/bin/bash

LOG_DIR="$HOME/ScriptOutputs"
BIN_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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
echo "Starting target: $@"
"$BIN_DIR/startSilent.sh" -r "$@" &
