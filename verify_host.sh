#!/bin/bash

myPath=$(dirname $0)
myAbsPath=$(readlink -fn "$myPath")


find $myAbsPath/IPTVPlayer/hosts -maxdepth 1 -iname "*.py" | 
  while read F 
  do
    #echo "$F"
    MAIN_URL=`egrep 'self.MAIN_URL[ ]*=[ ]*.http' < "$F"|egrep -o "http[^']*"`
    if [ "$MAIN_URL" != '' ];then
      #echo "$MAIN_URL"
      curl -s -m 5 "$MAIN_URL" -o /dev/null
      if [ $? -eq 0 ];then
        echo "Page $MAIN_URL exists :)"
      else
        echo "Page $MAIN_URL DOES NOT exist, "$F" broken, renamed to OFF !!!"
        mv "$F" "$F.OFF"
      fi
    fi
  done
  
  