#!/bin/bash

# 1. Check if an argument was provided
if [ -z "$1" ]; then
    echo "Usage: ./restart.sh <script_name> [args...]"
    exit 1
fi

# 2. Check if an argument was provided
if [ "$1" == "-h" ]; then
    echo "Usage: ./restart.sh <script_name> [args...]"
    exit 1
fi

TARGET=$1

# 2. Find PIDs matching the target name
# -f: matches the full command line (useful if run as "python foo.py" or "./foo.sh")
# grep -v $$: excludes the PID of *this* restart script so it doesn't kill itself
PIDS=$(pgrep -f "$TARGET" | grep -v $$)

# 3. Logic: Kill if found, then start
if [ -n "$PIDS" ]; then
    echo "⚠️  Found running process(es) for '$TARGET' (PID: $PIDS)."
    echo "   Killing process..."
    kill $PIDS
    
    # Optional: Wait a moment to ensure it closes before restarting
    sleep 1
else
    echo "ℹ️  No running process found for '$TARGET'."
fi

echo "🚀 Starting '$TARGET'..."

# 4. Execute the command
# "$@" executes the command exactly as typed, passing all arguments along.
# The '&' runs it in the background so your terminal doesn't hang.
exec $BIN/startSilent.sh $@ &

echo "✅ Done. New PID: $!"
