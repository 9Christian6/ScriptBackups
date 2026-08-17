#!/usr/bin/env bash
# ~/.config/polybar/tageslisten.sh
#
# Polybar helper:
# - show first line of newest file in ~/Documents/Tageslisten/
# - scroll through lines
# - click to remove currently displayed line
# - add new day goal via rofi
#
# Subcommands:
#   show    Show current line
#   prev    Previous line
#   next    Next line
#   remove  Remove current line
#   add     Prompt with rofi and append a new line

set -euo pipefail

DIR="${HOME}/Documents/Tageslisten"

# State is kept here between scroll/click events.
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/polybar/tageslisten"
STATE_FILE="${STATE_DIR}/state"
LOCK_FILE="${STATE_DIR}/lock"

# Rofi theme.
# You gave a relative path; absolute is safer when launched from Polybar.
ROFI_THEME="${XDG_CONFIG_HOME:-${HOME}/.config}/rofi/themes/command-palette.rasi"

# Messages / placeholders. Change if desired.
MSG_NO_FILES="no file"
MSG_NO_LINES="no lines"
MSG_EMPTY_LINE="␣"

# Display mode:
# 1 = show "current/total line_text"
# 0 = show only "current/total"
SHOW_LINE_TEXT=1

mkdir -p "$STATE_DIR"

acquire_lock() {
  exec 9>"$LOCK_FILE"
  if command -v flock >/dev/null 2>&1; then
    flock -x 9
  fi
}

esc() {
  # Escape % for Polybar output.
  printf '%s' "${1//%/%%}"
}

emit() {
  printf '%s\n' "$(esc "$1")"
}

emit_zero() {
  # Used for 0/0 states.
  local msg="${1:-}"

  if (( SHOW_LINE_TEXT )) && [[ -n "$msg" ]]; then
    emit "0/0 ${msg}"
  else
    emit "0/0"
  fi
}

trim() {
  local s="$1"

  # Remove leading whitespace.
  s="${s#"${s%%[![:space:]]*}"}"

  # Remove trailing whitespace.
  s="${s%"${s##*[![:space:]]}"}"

  printf '%s' "$s"
}

newest_file() {
  # Newest regular file by modification time.
  # Requires GNU find/sort; normal on Linux.
  [[ -d "$DIR" ]] || return 0

  local entry
  while IFS= read -r -d '' entry; do
    # entry format: mtime<TAB>filepath
    printf '%s' "${entry#*$'\t'}"
    return 0
  done < <(find "$DIR" -maxdepth 1 -type f -printf '%T@\t%p\0' 2>/dev/null | sort -z -nr)

  return 0
}

count_lines() {
  local f="$1" n

  if [[ ! -f "$f" || ! -r "$f" ]]; then
    printf '0'
    return 0
  fi

  # awk counts the last line even if it has no trailing newline.
  n="$(awk 'END { print NR }' "$f" 2>/dev/null || printf '0')"

  if [[ ! "$n" =~ ^[0-9]+$ ]]; then
    n=0
  fi

  printf '%s' "$n"
}

line_at() {
  local f="$1" n="$2"

  [[ -f "$f" && -r "$f" ]] || return 0

  sed -n "${n}p" "$f" 2>/dev/null || true
}

ensure_trailing_newline() {
  local f="$1"

  # If file is empty, nothing to do.
  [[ -f "$f" && -r "$f" && -s "$f" ]] || return 0

  # If last character is not a newline, add one before appending.
  if [[ -n "$(tail -c 1 "$f" 2>/dev/null || true)" ]]; then
    printf '\n' >> "$f"
  fi
}

read_state() {
  STATE_PATH=""
  STATE_IDX=1

  if [[ -f "$STATE_FILE" ]]; then
    local idx="" path=""

    {
      IFS= read -r idx || true
      IFS= read -r path || true
    } < "$STATE_FILE"

    STATE_PATH="${path:-}"
    STATE_IDX="${idx:-1}"
  fi

  if [[ ! "$STATE_IDX" =~ ^[0-9]+$ ]]; then
    STATE_IDX=1
  fi
}

write_state() {
  # $1 = file path
  # $2 = line index
  printf '%s\n%s\n' "$2" "$1" > "$STATE_FILE"
}

prepare() {
  local mode="$1"

  FILE="$(newest_file)"

  if [[ -z "$FILE" ]]; then
    write_state "" 1
    emit_zero "$MSG_NO_FILES"
    exit 0
  fi

  read_state

  # "show" is used on Polybar startup and always resets to line 1.
  # If the newest file changed, also reset to line 1.
  if [[ "$mode" == "show" || "$STATE_PATH" != "$FILE" ]]; then
    IDX=1
  else
    IDX="$STATE_IDX"
  fi

  COUNT="$(count_lines "$FILE")"

  if (( COUNT == 0 )); then
    write_state "$FILE" 1
    emit_zero "$MSG_NO_LINES"
    exit 0
  fi

  (( IDX >= 1 )) || IDX=1
  (( IDX <= COUNT )) || IDX="$COUNT"

  write_state "$FILE" "$IDX"
}

output_current() {
  if (( SHOW_LINE_TEXT )); then
    local line
    line="$(line_at "$FILE" "$IDX")"

    # Remove Windows carriage return, if present.
    line="${line%$'\r'}"

    # Show placeholder for empty / whitespace-only lines.
    if [[ -z "${line//[[:space:]]/}" ]]; then
      line="$MSG_EMPTY_LINE"
    fi

    emit "${IDX}/${COUNT} ${line}"
  else
    emit "${IDX}/${COUNT}"
  fi
}

CMD="${1:-show}"

# ------------------------------------------------------------
# add command
# ------------------------------------------------------------
if [[ "$CMD" == "add" ]]; then
  if ! command -v rofi >/dev/null 2>&1; then
    emit "rofi not found"
    exit 0
  fi

  # Prompt without holding the file lock while Rofi is open.
  if [[ -f "$ROFI_THEME" ]]; then
    task="$(rofi -dmenu -p "Day goal:" -theme "$ROFI_THEME" < /dev/null 2>/dev/null || true)"
  else
    # Fallback if theme file is missing.
    task="$(rofi -dmenu -p "Day goal:" < /dev/null 2>/dev/null || true)"
  fi

  task="$(trim "$task")"

  acquire_lock

  # If cancelled or empty, do not add anything.
  if [[ -z "$task" ]]; then
    prepare add
    output_current
    exit 0
  fi

  if ! mkdir -p "$DIR" 2>/dev/null; then
    emit "cannot create directory"
    exit 0
  fi

  FILE="$(newest_file)"

  # If no day goal list exists yet, create one.
  if [[ -z "$FILE" ]]; then
    FILE="$DIR/$(date +%Y-%m-%d).txt"

    # If a non-file entry with that name exists, use a timestamped fallback.
    if [[ -e "$FILE" && ! -f "$FILE" ]]; then
      FILE="$DIR/$(date +%Y-%m-%d_%H%M%S).txt"
    fi

    if [[ ! -f "$FILE" ]]; then
      if ! : > "$FILE" 2>/dev/null; then
        emit "cannot create file"
        exit 0
      fi
    fi
  fi

  if [[ ! -w "$FILE" ]]; then
    emit "not writable"
    exit 0
  fi

  ensure_trailing_newline "$FILE"

  if ! printf '%s\n' "$task" >> "$FILE" 2>/dev/null; then
    emit "add failed"
    exit 0
  fi

  COUNT="$(count_lines "$FILE")"

  # Jump to the newly added line.
  IDX="$COUNT"

  write_state "$FILE" "$IDX"
  output_current
  exit 0
fi

# ------------------------------------------------------------
# Normal commands
# ------------------------------------------------------------

acquire_lock

case "$CMD" in
  show)
    prepare show
    output_current
    ;;

  prev)
    prepare prev

    if (( IDX > 1 )); then
      IDX=$((IDX - 1))
      write_state "$FILE" "$IDX"
    fi

    output_current
    ;;

  next)
    prepare next

    if (( IDX < COUNT )); then
      IDX=$((IDX + 1))
      write_state "$FILE" "$IDX"
    fi

    output_current
    ;;

  remove)
    prepare remove

    if (( COUNT > 0 )); then
      if sed -i "${IDX}d" "$FILE" 2>/dev/null; then
        COUNT="$(count_lines "$FILE")"

        if (( COUNT == 0 )); then
          IDX=1
          write_state "$FILE" "$IDX"
          emit_zero "$MSG_NO_LINES"
        else
          (( IDX <= COUNT )) || IDX="$COUNT"
          write_state "$FILE" "$IDX"
          output_current
        fi
      else
        emit "remove failed"
      fi
    else
      emit_zero "$MSG_NO_LINES"
    fi
    ;;

  *)
    echo "Usage: ${0##*/} {show|prev|next|remove|add}" >&2
    exit 1
    ;;
esac