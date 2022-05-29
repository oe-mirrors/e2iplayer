#!/bin/bash

myPath=$(dirname $0)
myAbsPath=$(readlink -fn "$myPath")

#the best to verify python script is to try to compile it. ;)
echo "import sys
filename = sys.argv[1]
print(filename)
source = open(filename, 'r').read() + '\n'
compile(source, filename, 'exec')
" > /tmp/checker.py

find $myAbsPath/IPTVPlayer -iname "*.py" | 
  while read F 
  do
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
