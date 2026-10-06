#!/bin/bash
# Checks the MAIN_URL of every host in IPTVPlayer/hosts and disables hosts whose page is gone
# by renaming them to host*_blocked_.py (names with _blocked_ are skipped by GetHostsFromList).

myPath=$(dirname "$0")
myAbsPath=$(readlink -fn "$myPath")

find "${myAbsPath}/IPTVPlayer/hosts" -maxdepth 1 -iname "*.py" ! -name "*_blocked_*" |
  while read -r F; do
    # echo "$F"
    MAIN_URL=$(grep -E 'self.MAIN_URL[ ]*=[ ]*.http' <"$F" | grep -E -o "http[^'\"]*" | head -n 1)
    if [ "$MAIN_URL" != '' ]; then
      # echo "$MAIN_URL"
      CODE=$(curl -s -L -m 5 -o /dev/null -w '%{http_code}' "$MAIN_URL")
      case "$CODE" in
        2?? | 3??)
          echo "Page $MAIN_URL exists :)"
          ;;
        000 | 404 | 410)
          echo "Page $MAIN_URL DOES NOT exist (HTTP $CODE), '${F}' broken, renamed to '${F%.py}_blocked_.py' !!!"
          mv "$F" "${F%.py}_blocked_.py"
          ;;
        *)
          echo "Page $MAIN_URL answers HTTP $CODE (Cloudflare / geo block?), '${F}' kept, check it manually"
          ;;
      esac
    fi
  done
