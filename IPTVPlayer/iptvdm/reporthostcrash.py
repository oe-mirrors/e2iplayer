# -*- coding: utf-8 -*-


import urllib.request
import urllib.error
import urllib.parse
import urllib.request
import urllib.parse
import urllib.error
import sys

def ReportCrash(url, except_msg):
    request = urllib.request.Request(url, data=urllib.parse.urlencode({'except':except_msg}))
    data = urllib.request.urlopen(request).read()
    print(data)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    ReportCrash(sys.argv[1], sys.argv[2])
    sys.exit(0)
