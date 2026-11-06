#!/bin/bash
set -euo pipefail

usage() {
    echo 'Usage: tts.sh PATH | tts.sh --in-place TEXT' >&2
    exit 2
}

if [[ ${1-} == --in-place ]]; then
    [[ $# == 2 ]] || usage
    message=$2
else
    [[ $# == 1 ]] || usage
    message=$(cat -- "$1")
fi

# With no text pico2wave reads stdin, which may be a nonblocking terminal.
[[ $message =~ [^[:space:]] ]] || exit 0

wave_dir=$(mktemp -d "${TMPDIR:-/tmp}/timer-tts.XXXXXXXX")
trap 'rm -rf -- "$wave_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Never read timer keystrokes, and never play a failed or stale synthesis.
pico2wave --wave="$wave_dir/speech.wav" --lang=de-DE -- "$message" </dev/null
aplay -q "$wave_dir/speech.wav" </dev/null
