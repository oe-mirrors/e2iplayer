# -*- coding: utf-8 -*-

from __future__ import print_function
import urllib
import urllib2
import sys
import traceback
import time

import signal
import os


def signal_handler(sig, frame):
    os.kill(os.getpid(), signal.SIGTERM)


signal.signal(signal.SIGINT, signal_handler)


def printDBG(strDat):
    if 0:
        print("%s" % strDat)


def printExc(msg=''):
    printDBG("===============================================")
    printDBG("                   EXCEPTION                   ")
    printDBG("===============================================")
    msg = msg + ': \n%s' % traceback.format_exc()
    printDBG(msg)
    printDBG("===============================================")


def getPage(url, params={}):
    printDBG('url [%s]' % url)
    sts = False
    try:
        req = urllib2.Request(url)
        if 'Referer' in params:
            req.add_header('Referer', params['Referer'])
        if 'User-Agent' in params:
            req.add_header('User-Agent', params['User-Agent'])
        resp = urllib2.urlopen(req)
        data = resp.read()
        sts = True
    except Exception:
        printExc()
    return sts, data


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print('Refresh and referer urls are needed', file=sys.stderr)
        sys.exit(1)
    try:
        timeout = 20 # 20s
        hlsUrl = sys.argv[1]
        refreshUrl = sys.argv[2]
        referer = sys.argv[3]
        userAgent = sys.argv[4]
        print(hlsUrl, file=sys.stderr)
        while True:
            printDBG("Refreshing....")
            start_time = time.time()
            tm = str(int(start_time * 1000))
            url = refreshUrl + "&_=" + tm + "&callback=?"
            getPage(url, {'Referer': referer, 'User-Agent': userAgent})
            dt = time.time() - start_time
            if dt > 0 and dt < 20:
                time.sleep(20 - dt)
    except Exception:
        printExc()
    sys.exit(0)
