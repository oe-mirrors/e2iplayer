# -*- coding: utf-8 -*-

from __future__ import print_function
import urllib
import urllib2
import sys
import traceback
import base64
import SocketServer
import SimpleHTTPServer
import re
import ssl
from urlparse import urlparse, urljoin
try:
    import json
except Exception:
    import simplejson as json
import cookielib
import time

import signal
import os


def signal_handler(sig, frame):
    os.kill(os.getpid(), signal.SIGTERM)


signal.signal(signal.SIGINT, signal_handler)


def rm(file):
    try:
        os.remove(file)
    except Exception:
        pass


def printDBG(strDat):
    return
    strDat = str(strDat)
    f = open('/tmp/iptv.dbg', 'a')
    f.write(strDat + '\n')
    f.close
    print("%s" % strDat)


def printExc(msg=''):
    printDBG("===============================================")
    printDBG("                   EXCEPTION                   ")
    printDBG("===============================================")
    msg = msg + ': \n%s' % traceback.format_exc()
    printDBG(msg)
    printDBG("===============================================")


cj = None


def getPage(url, params={}):
    printDBG('url [%s]' % url)
    global cj
    customOpeners = []

    try:
        ctx = ssl._create_unverified_context(params['ssl_protocol']) if params.get('ssl_protocol', None) != None else ssl._create_unverified_context()
        customOpeners.append(urllib2.HTTPSHandler(context=ctx))
    except Exception:
        pass

    if params.get('cookiefile'):
        if cj == None:
            cj = cookielib.MozillaCookieJar()
            try:
                cj.load(params['cookiefile'], ignore_discard=True)
            except IOError:
                pass
        customOpeners.append(urllib2.HTTPCookieProcessor(cj))

    sts = False
    data = None
    try:
        req = urllib2.Request(url)
        for key in ('Referer', 'User-Agent', 'Origin', 'Accept-Encoding', 'Accept'):
            if key in params:
                req.add_header(key, params[key])
        printDBG("++++HEADERS START++++")
        printDBG(req.headers)
        printDBG("++++HEADERS END++++")
        opener = urllib2.build_opener(*customOpeners)
        resp = opener.open(req)
        data = resp.read()
        sts = True
    except urllib2.HTTPError, e:
        data = e
    except Exception:
        printExc()
    return sts, data


jsscriptPath = '/'.join(os.path.dirname(os.path.abspath(__file__)).split('/')[:-1]) + '/jsscripts/'
reCFScript = re.compile('<script[^>]*?>(.*?)</script>', re.DOTALL)
reCFForm = re.compile('<form[^>]*?id="challenge-form"[^>]*?>(.*?)</form>', re.DOTALL)
reCFAction = re.compile('action="([^"]+?)"')
reCFInput = re.compile(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>')


def getPageCF(url, params={}):
    global duktape
    global reCFScript
    global reCFForm
    global reCFAction
    global reCFInput
    global jsscriptPath
    sts, data = getPage(url, params)
    if not sts and data and data.code == 503:
        current = 0
        try:
            while current < 5 and not sts and None != data:
                start_time = time.time()
                current += 1
                e = data
                cUrl = data.fp.geturl()
                verData = e.fp.read(1 * 1024 * 1024)
                e.fp.close()

                dat = reCFScript.findall(verData)
                for item in dat:
                    if 'setTimeout' in item and 'submit()' in item:
                        dat = item
                        break

                jsdata = "var location = {hash:''}; var iptv_domain='%s';\n%s\niptv_fun();" % ('{uri.scheme}://{uri.netloc}/'.format(uri=urlparse(cUrl)), dat)
                jstmp = '/tmp/cf_%s' % os.getpid()
                with open(jstmp + '.js', 'w') as f:
                    f.write(jsdata)
                cmd = '%s "%s" "%s.js" > %s 2> /dev/null' % (duktape, jsscriptPath + 'cf.byte', jstmp, jstmp)
                os.system(cmd)
                with open(jstmp, 'r') as f:
                    decoded = f.read()
                rm(jstmp + '.js')
                rm(jstmp)
                printDBG(">>" + cmd)
                decoded = json.loads(decoded.strip())
                verData = reCFForm.search(verData).group(0)
                verUrl = reCFAction.search(verData).group(1)
                get_data = dict(reCFInput.findall(verData))
                get_data['jschl_answer'] = decoded['answer']
                verUrl += '?jschl_vc=%s&pass=%s&jschl_answer=%s' % (get_data['jschl_vc'], get_data['pass'], get_data['jschl_answer'])
                verUrl = urljoin(cUrl, verUrl)
                params2 = dict(params)
                params2.update({'Referer': cUrl, 'Accept-Encoding': 'text', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
                printDBG("Time spent: [%s]" % (time.time() - start_time))
                if current == 1:
                    time.sleep(1 + (decoded['timeout'] / 1000.0) - (time.time() - start_time))
                else:
                    time.sleep((decoded['timeout'] / 1000.0))
                printDBG("Time spent: [%s]" % (time.time() - start_time))
                printDBG("Timeout: [%s]" % decoded['timeout'])
                sts, data = getPage(verUrl, params2)
        except Exception:
            printExc()

    return sts, data


class Proxy(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        global mainUrl
        global userAgent
        global urlPath
        global scriptUrl
        global cookiefile
        global duktape
        keyUrl = self.path

        if keyUrl.startswith('/https/'):
            keyUrl = 'https://' + keyUrl[7:]
        elif keyUrl.startswith('/http/'):
            keyUrl = 'http://' + keyUrl[6:]

        printDBG("do_GET: " + keyUrl)

        if isinstance(scriptUrl, list):
            for item in scriptUrl:
                keyUrl = keyUrl.replace(item[0], item[1])
        elif scriptUrl.startswith('/tmp'):
            hash = scriptUrl[1:]
            with open(scriptUrl + '.js', 'w') as f:
                f.write("tmp.open('', '%s')" % keyUrl)
            cmd = '%s "%s.byte" "%s.js" > %s 2> /dev/null' % (duktape, scriptUrl, scriptUrl, scriptUrl)
            os.system(cmd)
            with open(scriptUrl, 'r') as f:
                keyUrl = f.read().strip()
        else:
            #keyUrl = urlPath + base64.b64encode('l=' + 'nhl' + '&g=' + 'OTT-COL-20171110' + '&f=' + 'home' + '&u=' + base64.b64encode(keyUrl))
            keyUrl = urlPath + base64.b64encode(keyUrl)
        if not keyUrl.startswith('https://') and not keyUrl.startswith('http://'):
            if keyUrl[0] == '/':
                keyUrl = keyUrl[1:]
            keyUrl = mainUrl + keyUrl
        parsedUri = urlparse(mainUrl)
        sts, data = getPageCF(keyUrl, {'User-Agent': userAgent, 'Referer': mainUrl, 'Origin': '{uri.scheme}://{uri.netloc}'.format(uri=parsedUri), 'cookiefile': cookiefile})
        #printDBG("sts [%s] data[%s]" % (sts, data))
        if sts:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print('Wrong parameters', file=sys.stderr)
        sys.exit(1)
    try:
        port = int(sys.argv[1])
        hlsUrl = sys.argv[2]
        mainUrl = sys.argv[3]
        scriptUrl = sys.argv[4]
        userAgent = sys.argv[5]
        cookiefile = sys.argv[6] if len(sys.argv) > 6 else None
        duktape = sys.argv[7] if len(sys.argv) > 7 else ''

        if scriptUrl.startswith('<proxy>'):
            urlPath = scriptUrl[7:]
            if urlPath.startswith('/'):
                urlPath = urlPath[1:]
        elif scriptUrl.startswith('|'):
            scriptUrl = json.loads(base64.b64decode(scriptUrl))

        SocketServer.TCPServer.allow_reuse_address = True
        #httpd = SocketServer.ForkingTCPServer(('127.0.0.1', port), Proxy)
        httpd = SocketServer.TCPServer(('127.0.0.1', port), Proxy)
        print('\n%s\n' % hlsUrl, file=sys.stderr)
        httpd.serve_forever()
    except KeyboardInterrupt:
        printExc()
        printDBG("Closing Server")
        httpd.shutdown()
        httpd.socket.close()
        httpd.server_close()
    sys.exit(0)
