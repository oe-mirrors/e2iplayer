# -*- coding: utf-8 -*-

import urllib2
import urllib
import sys


def ReportCrash(url, except_msg):
    request = urllib2.Request(url, data=urllib.urlencode({'except': except_msg}))
    data = urllib2.urlopen(request).read()
    print(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    ReportCrash(sys.argv[1], sys.argv[2])
    sys.exit(0)
