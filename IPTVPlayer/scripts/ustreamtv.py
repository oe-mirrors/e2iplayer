# -*- coding: utf-8 -*-

from __future__ import print_function
import urllib
import urllib2
import sys
import traceback
import time
try:
    import json
except Exception:
    import simplejson as json
from random import randint

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


def getLink(width, mediaId, referer, userAgent):
    WS_URL = "http://r{0}-1-{1}-{2}-{3}.ums.ustream.tv"

    rsid = "{0:x}:{1:x}".format(randint(0, 1e10), randint(0, 1e10))
    rpin = "_rpin.{0:x}".format(randint(0, 1e15))

    apiUrl = WS_URL.format(randint(0, 0xffffff), mediaId, 'channel', 'lp-live') + '/1/ustream'
    url = apiUrl + '?' + urllib.urlencode([('media', mediaId), ('referrer', referer), ('appVersion', 2), ('application', 'channel'), ('rsid', rsid), ('appId', 11), ('rpin', rpin), ('type', 'viewer')])

    params = {'Referer': referer, 'User-Agent': userAgent}
    sts, data = getPage(url, params)
    if not sts:
        return ''

    data = json.loads(data)
    host = data[0]['args'][0]['host'].encode('utf-8')
    connectionId = data[0]['args'][0]['connectionId']
    if len(host):
        apiUrl = "http://" + host + '/1/ustream'
    url = apiUrl + '?connectionId=' + str(connectionId)

    for i in range(5):
        sts, data = getPage(url, params)
        if not sts:
            continue
        if 'm3u8' in data:
            break
        time.sleep(1)
    data = json.loads(data)
    playlistUrl = data[0]['args'][0]['stream'][0]['url'].encode('utf-8')

    sts, data = getPage(playlistUrl, params)
    if not sts:
        return ''

    data = data.split('\n')
    marker = 'RESOLUTION=%sx' % width
    for idx in range(len(data)):
        if marker in data[idx]:
            m3u8Url = data[idx + 1].strip()
            print('\n%s\n' % m3u8Url, file=sys.stderr)
            return url
    return ''


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print('Refresh and referer urls are needed', file=sys.stderr)
        sys.exit(1)
    try:
        width = sys.argv[1]
        mediaId = sys.argv[2]
        referer = sys.argv[3]
        userAgent = sys.argv[4]

        refreshUrl = getLink(width, mediaId, referer, userAgent)
        if refreshUrl != '':
            while True:
                printDBG("Refreshing....")
                tm = str(time.time())
                url = refreshUrl + "&_=" + tm + "&callback=?"
                getPage(url, {'Referer': referer, 'User-Agent': userAgent})
                time.sleep(1)
    except Exception:
        printExc()
    sys.exit(0)
