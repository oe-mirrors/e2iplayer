# -*- coding: utf-8 -*-

from urllib.request import urlopen, Request
from urllib.parse import urlencode
import sys


def ReportCrash(url, except_msg):
    request = Request(url, data=urlencode({'except': except_msg}))
    data = urlopen(request).read()
    print(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    ReportCrash(sys.argv[1], sys.argv[2])
    sys.exit(0)
