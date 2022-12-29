#!/bin/bash

myPath=$(dirname $0)
myAbsPath=$(readlink -fn "$myPath")

#the best to verify python script is to try to compile it. ;)
echo "import sys
filename = sys.argv[1]
#print(filename)
source = open(filename, 'r').read() + '\n'
compile(source, filename, 'exec')
" > /tmp/checker.py


declare -a StringArray=('.iteritems()' '^import urllib' '^import urlparse' 'print[ ]*["]' )
#find $myAbsPath/IPTVPlayer/hosts -iname "*.py" | 
#  while read F 
#  do
#    sed -i 's/^import urllib/from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import */' "$F"
#    sed -i 's/urllib\./urllib_/g' "$F"
#  done

find $myAbsPath/IPTVPlayer -iname "*.py" | 
  while read F 
  do
    #removing BOM, is a garbage from windows
    sed -i '1s/^\xEF\xBB\xBF//' "$F"
    if [ `echo "$F"|egrep -c '/p2p3/|/scripts/'` -eq 0 ];then
      for aVal in "${StringArray[@]}"; do
        [ `grep -c "$aVal" < "$F"` -gt 0 ] && echo "WARNING: $F uses '$aVal' which if NOT compatible with python3" 
      done
      [ `grep -c "basetring" < "$F"` -gt 0 ] && [ `grep -c "basetring = str" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'basetring' which if NOT compatible with python3" 
      [ `grep -c "StringIO" < "$F"` -gt 0 ] && [ `grep -c "from io import StringIO" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'StringIO' which if NOT compatible with python3" 
      [ `grep -c "BytesIO" < "$F"` -gt 0 ] && [ `grep -c "from io import BytesIO" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'BytesIO' which if NOT compatible with python3" 
      #[ `grep -c "unicode" < "$F"` -gt 0 ] && [ `grep -c "unicode = str" < "$F"` -eq 0 ] && echo "WARNING: $F uses 'unicode' which if NOT compatible with python3" 
    fi
    if [ -e /usr/bin/python2 ];then
      python2 /tmp/checker.py "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY2 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
        break
      fi
    fi
    if [ -e /usr/bin/python3 ];then
      python3 /tmp/checker.py "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY3 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
        break
      fi
    fi
    if [ -e /usr/bin/python3.10 ];then
      python3.10 /tmp/checker.py "$F"
      if [[ $? -gt 0 ]];then
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! ERROR in PY3.10 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!!!!!!!! $F !!!!!!!!!!"
        exit 1
        break
      fi
    fi
  done

echo "refreshing mo files..."
find $myAbsPath/IPTVPlayer/locale -type f -name *.po  -exec bash -c 'msgfmt "$1" -o "${1%.po}".mo' - '{}' \;
