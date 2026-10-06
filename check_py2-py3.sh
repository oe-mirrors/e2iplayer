#!/bin/bash

myPath=$(dirname "$0")
myAbsPath=$(readlink -fn "$myPath")

#the best to verify python script is to try to compile it. ;)
#read as bytes, so compile() uses the file's coding (utf-8 by default) and not the locale
checker=$(mktemp /tmp/checker.XXXXXX.py)
trap 'rm -f "$checker"' EXIT
echo "import sys
filename = sys.argv[1]
#print(filename)
source = open(filename, 'rb').read() + b'\n'
compile(source, filename, 'exec')
" > "$checker"


declare -a StringArray=('.iteritems()' '^import urllib' '^import urlparse' 'print[ ]*["]' )
#find $myAbsPath/IPTVPlayer/hosts -iname "*.py" |
#  while read F
#  do
#    sed -i 's/^import urllib/from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import */' "$F"
#    sed -i 's/urllib\./urllib_/g' "$F"
#  done

#no pipe into the loop, else exit 1 only leaves the subshell and the script goes on
while read -r F
  do
    #removing BOM, is a garbage from windows
    sed -i '1s/^\xEF\xBB\xBF//' "$F"
    if [ `echo "$F"|grep -E -c '/p2p3/|/scripts/'` -eq 0 ];then
      for aVal in "${StringArray[@]}"; do
        [ `grep -c "$aVal" < "$F"` -gt 0 ] && echo "WARNING: $F uses '$aVal' which is NOT compatible with python3"
      done
      [ `grep -c "StringIO" < "$F"` -gt 0 ] && [ `grep -c "from io import StringIO" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'StringIO' which is NOT compatible with python3"
      [ `grep -c "BytesIO" < "$F"` -gt 0 ] && [ `grep -c "from io import BytesIO" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'BytesIO' which is NOT compatible with python3"
      #[ `grep -c "unicode" < "$F"` -gt 0 ] && [ `grep -c "unicode = str" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'unicode' which is NOT compatible with python3"
    fi
    if [ -e /usr/bin/python2 ];then
      python2 "$checker" "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY2 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
      fi
    fi
    if [ -e /usr/bin/python3 ];then
      python3 "$checker" "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY3 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
      fi
    fi
    if [ -e /usr/bin/python3.10 ];then
      python3.10 "$checker" "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY3.10 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
      fi
    fi
  done < <(find "$myAbsPath/IPTVPlayer" -iname "*.py")

echo "refreshing mo files..."
find "$myAbsPath/IPTVPlayer/locale" -type f -name "*.po" -exec bash -c 'msgfmt "$1" -o "${1%.po}".mo' - '{}' \;
