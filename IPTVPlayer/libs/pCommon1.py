# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
# FOREIGN import
###################################################
import urllib.request, urllib.parse, urllib.error
import base64
try:
    import ssl
except Exception:
    pass
import re
import time
import http.cookiejar
import unicodedata
try:
    import pycurl
except Exception:
    pass

from io import BytesIO, StringIO

import gzip
from urllib.parse import urljoin, urlparse, urlunparse
from binascii import hexlify
import six
###################################################


buffer = BytesIO()
maxDataSize = -1
responseHeaders = {}

def _headerFunction(headerLine):
    headerLine = six.ensure_str(headerLine)
    if ':' not in headerLine:
        if 0 == maxDataSize:
            if headerLine in ['\r\n', '\n']:
                if 'n' not in responseHeaders:
                    return 0
                responseHeaders.pop('n', None)
            elif headerLine.startswith('HTTP/') and headerLine.split(' 30', 1)[-1][0:1] in ['1', '2', '3', '7']: # new location with 301, 302, 303, 307
                responseHeaders['n'] = True
        return

    name, value = headerLine.split(':', 1)

    name = name.strip()
    value = value.strip()

    name = name.lower()
    responseHeaders[name] = value

def _breakConnection(toWriteData):
    buffer.write(toWriteData)
    if maxDataSize <= buffer.tell():
        return 0

def _bodyFunction(toWriteData):
    # we started receiving body data so all headers are available
    # so we can check them if needed
    buffer.write(toWriteData)
    return 0


def _terminateFunction(download_t, download_d, upload_t, upload_d):
    return False # anything else then None will cause pycurl perform cancel

try:

    curlSession = pycurl.Curl()

    customHeaders = []

    #curlSession.setopt(pycurl.ACCEPT_ENCODING, "") # enable all supported built-in compressions
#    if None != params.get('ssl_protocol', None):
#        sslProtoVer = self.getPyCurlSSLProtocolVersion(params['ssl_protocol'])
#        if None != sslProtoVer:
    #curlSession.setopt(pycurl.SSLVERSION, pycurl.SSLVERSION_TLSv1_2)


    #curlSession.setopt(pycurl.FOLLOWLOCATION, 1)
    #curlSession.setopt(pycurl.UNRESTRICTED_AUTH, 1)
    #curlSession.setopt(pycurl.MAXREDIRS, 5)

    # debug
    #curlSession.setopt(pycurl.VERBOSE, 1)
    #curlSession.setopt(pycurl.DEBUGFUNCTION, print)

    curlSession.setopt(pycurl.CAINFO, "/etc/ssl/certs/ca-certificates.crt")
    curlSession.setopt(pycurl.PROXY_CAINFO, "/etc/ssl/certs/ca-certificates.crt")

    pageUrl = "https://zdf-cdn.live.cellular.de/mediathekV2/broadcast-missed/2021-05-17"

    curlSession.setopt(pycurl.URL, pageUrl)

    #curlSession.setopt(pycurl.HEADERFUNCTION, _headerFunction)

    curlSession.setopt(pycurl.WRITEDATA, buffer)

    #curlSession.setopt(pycurl.NOPROGRESS, False)
    #curlSession.setopt(pycurl.PROGRESSFUNCTION, _terminateFunction)
    #curlSession.setopt(pycurl.NOSIGNAL, 1)

    curlSession.perform()

    curlSession.close()

    print(buffer.getvalue())

except pycurl.error as e:
    print('pycurl.error 903')
    print(e)
#            metadata['pycurl_error'] (e[0], str(e[1]))
except Exception:
    pass



