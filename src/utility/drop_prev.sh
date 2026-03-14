#!/usr/bin/env bash
# drop_prev.sh — remove exactly the line immediately before any line containing "only_enforce_if",
#                preserve everything else (including blanks), and never duplicate.
#
# Usage: ./drop_prev.sh input.txt > output.txt

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <input-file>" >&2
  exit 1
fi

input="$1"
exec 3< "$input"

# Read the first line into prev_line (exit if empty file)
if ! read -r prev_line <&3; then
  exit 0
fi

# This flag tells us, on the *next* non-matching line, whether we already dropped prev_line
drop_prev=false

while read -r curr_line <&3; do
  if [[ "$curr_line" == *only_enforce_if* ]]; then
    # Drop prev_line (do not print it) and emit curr_line
    drop_prev=true
    echo "$curr_line"
  else
    # curr_line not matching: if prev_line wasn't dropped for an only_enforce_if, print it
    if ! $drop_prev; then
      echo "$prev_line"
    fi
    # Reset the flag so we only skip *one* print after a drop
    drop_prev=false
  fi

  # Slide the window
  prev_line="$curr_line"
done

# At EOF, if the last prev_line wasn't marked dropped, print it
if ! $drop_prev; then
  echo "$prev_line"
fi
