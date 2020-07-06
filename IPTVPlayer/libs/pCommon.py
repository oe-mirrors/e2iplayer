# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsHttpsCertValidationEnabled, byteify, GetDefaultLang, rm, UsePyCurl, GetJSScriptFile, IsExecutable, iptv_system
from Plugins.Extensions.IPTVPlayer.components.asynccall import IsMainThread, IsThreadTerminated, SetThreadKillable
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
###################################################
# FOREIGN import
###################################################
import urllib
import urllib2
import base64
try: import ssl
except Exception: pass
import re
import time
import cookielib
import unicodedata
try: import pycurl
except Exception: pass
try:
    try: from cStringIO import StringIO
    except Exception: from StringIO import StringIO 
    import gzip
except Exception: pass
from urlparse import urljoin, urlparse, urlunparse
from binascii import hexlify
import os
###################################################

def DecodeGzipped(data):
    buf = StringIO(data)
    f = gzip.GzipFile(fileobj=buf)
    return f.read()

def EncodeGzipped(data):
    f = StringIO()
    gzf = gzip.GzipFile(mode="wb", fileobj=f, compresslevel=1)
    gzf.write(data)
    gzf.close()
    encoded = f.getvalue()
    f.close()
    return encoded

class NoRedirection(urllib2.HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return infourl
    http_error_300 = http_error_302
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302

class MultipartPostHandler(urllib2.BaseHandler):
    handler_order = urllib2.HTTPHandler.handler_order - 10

    def http_request(self, request):
        data = request.get_data()
        if data is not None and type(data) != str:
            content_type, data = self.encode_multipart_formdata( data )
            request.add_unredirected_header('Content-Type', content_type)
            request.add_data(data)
        return request
        
    def encode_multipart_formdata(self, fields):
        LIMIT = '-----------------------------14312495924498'
        CRLF = '\r\n'
        L = []
        for (key, value) in fields:
            L.append('--' + LIMIT)
            L.append('Content-Disposition: form-data; name="%s"' % key)
            L.append('')
            L.append(value)
        L.append('--' + LIMIT + '--')
        L.append('')
        body = CRLF.join(L)
        content_type = 'multipart/form-data; boundary=%s' % LIMIT
        return content_type, body
    
    https_request = http_request

class CParsingHelper:
    @staticmethod
    def listToDir(cList, idx):
        cTree = {'dat':''}
        deep = 0 
        while (idx+1) < len(cList):
            if cList[idx].startswith('<ul') or cList[idx].startswith('<li'):
                deep += 1
                nTree, idx, nDeep = CParsingHelper.listToDir(cList, idx+1)
                if 'list' not in cTree: cTree['list'] = []
                cTree['list'].append(nTree)
                deep += nDeep
            elif cList[idx].startswith('</ul>') or cList[idx].startswith('</li>'):
                deep -= 1
                idx += 1
            else:
                cTree['dat'] += cList[idx]
                idx += 1
            if deep < 0:
                break
        return cTree, idx, deep

    @staticmethod
    def getSearchGroups(data, pattern, grupsNum=1, ignoreCase=False):
        return ph.search(data, pattern, ph.IGNORECASE if ignoreCase else 0, grupsNum)

    @staticmethod
    def getDataBeetwenReMarkers(data, pattern1, pattern2, withMarkers=True):
        match1 = pattern1.search(data)
        if None == match1 or -1 == match1.start(0): return False, ''
        match2 = pattern2.search(data[match1.end(0):])
        if None == match2 or -1 == match2.start(0): return False, ''
        
        if withMarkers:
            return True, data[match1.start(0): (match1.end(0) + match2.end(0)) ]
        else:
            return True, data[match1.end(0): (match1.end(0) + match2.start(0)) ]

    @staticmethod
    def getDataBeetwenMarkers(data, marker1, marker2, withMarkers=True, caseSensitive=True):
        flags = 0
        if withMarkers: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.find(data, marker1, marker2, flags)

    @staticmethod
    def getAllItemsBeetwenMarkers(data, marker1, marker2, withMarkers=True, caseSensitive=True):
        flags = 0
        if withMarkers: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.findall(data, marker1, marker2, flags)

    @staticmethod
    def rgetAllItemsBeetwenMarkers(data, marker1, marker2, withMarkers=True, caseSensitive=True):
        flags = 0
        if withMarkers: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.rfindall(data, marker1, marker2, flags)

    @staticmethod
    def rgetDataBeetwenMarkers2(data, marker1, marker2, withMarkers=True, caseSensitive=True):
        flags = 0
        if withMarkers: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.rfind(data, marker1, marker2, flags)

    @staticmethod
    def rgetDataBeetwenMarkers(data, marker1, marker2, withMarkers = True):
        # this methods is not working as expected, but is is used in many places
        # so I will leave at it is, please use rgetDataBeetwenMarkers2
        idx1 = data.rfind(marker1)
        if -1 == idx1: return False, ''
        idx2 = data.rfind(marker2, idx1 + len(marker1))
        if -1 == idx2: return False, ''
        if withMarkers:
            idx2 = idx2 + len(marker2)
        else:
            idx1 = idx1 + len(marker1)
        return True, data[idx1:idx2]

    @staticmethod
    def getDataBeetwenNodes(data, node1, node2, withNodes=True, caseSensitive=True):
        flags = 0
        if withNodes: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.find(data, node1, node2, flags)

    @staticmethod
    def getAllItemsBeetwenNodes(data, node1, node2, withNodes=True, numNodes=-1, caseSensitive=True):
        flags = 0
        if withNodes: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.findall(data, node1, node2, flags, limits=numNodes)

    @staticmethod
    def rgetDataBeetwenNodes(data, node1, node2, withNodes=True, caseSensitive=True):
        flags = 0
        if withNodes: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.rfind(data, node1, node2, flags)
        
    @staticmethod
    def rgetAllItemsBeetwenNodes(data, node1, node2, withNodes=True, numNodes=-1, caseSensitive=True):
        flags = 0
        if withNodes: flags |= ph.START_E|ph.END_E
        if not caseSensitive: flags |= ph.IGNORECASE
        return ph.rfindall(data, node1, node2, flags, limits=numNodes)

    # this method is useful only for developers 
    # to dump page code to the file
    @staticmethod
    def writeToFile(file, data, mode = "w"):
        #helper to see html returned by ajax
        file_path = file
        text_file = open(file_path, mode)
        text_file.write(data)
        text_file.close()
    
    @staticmethod
    def getNormalizeStr(txt, idx=None):
        POLISH_CHARACTERS = {u'ą':u'a', u'ć':u'c', u'ę':u'ę', u'ł':u'l', u'ń':u'n', u'ó':u'o', u'ś':u's', u'ż':u'z', u'ź':u'z',
                             u'Ą':u'A', u'Ć':u'C', u'Ę':u'E', u'Ł':u'L', u'Ń':u'N', u'Ó':u'O', u'Ś':u'S', u'Ż':u'Z', u'Ź':u'Z',
                             u'á':u'a', u'é':u'e', u'í':u'i', u'ñ':u'n', u'ó':u'o', u'ú':u'u', u'ü':u'u',
                             u'Á':u'A', u'É':u'E', u'Í':u'I', u'Ñ':u'N', u'Ó':u'O', u'Ú':u'U', u'Ü':u'U',
                            }
        txt = txt.decode('utf-8')
        if None != idx: txt = txt[idx]
        nrmtxt = unicodedata.normalize('NFC', txt)
        ret_str = []
        for item in nrmtxt:
            if ord(item) > 128:
                item = POLISH_CHARACTERS.get(item)
                if item: ret_str.append(item)
            else: # pure ASCII character
                ret_str.append(item)
        return ''.join(ret_str).encode('utf-8')

    @staticmethod
    def isalpha(txt, idx=None):
        return CParsingHelper.getNormalizeStr(txt, idx).isalpha()

    @staticmethod 
    def cleanHtmlStr(str):
        return ph.clean_html(str)

class common:
    HOST   = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
    HEADER = None
    ph = CParsingHelper
    
    @staticmethod
    def getDefaultHeader(browser='firefox'):
        if browser == 'firefox': ua = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:46.0) Gecko/20100101 Firefox/46.0'
        elif browser == 'iphone_3_0': ua = 'Mozilla/5.0 (iPhone; U; CPU iPhone OS 3_0 like Mac OS X; en-us) AppleWebKit/528.18 (KHTML, like Gecko) Version/4.0 Mobile/7A341 Safari/528.16'
        else: ua = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'
        
        HTTP_HEADER = { 'User-Agent':ua,
                        'Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Encoding':'gzip, deflate',
                        'DNT':1 
                      }
        return dict(HTTP_HEADER)
    
    @staticmethod
    def getParamsFromUrlWithMeta(url, baseHeaderOutParams=None):
        from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
        HANDLED_HTTP_HEADER_PARAMS = DMHelper.HANDLED_HTTP_HEADER_PARAMS #['Host', 'User-Agent', 'Referer', 'Cookie', 'Accept',  'Range']
        outParams = {}
        tmpParams = {}
        postData = None
        if isinstance(url, strwithmeta):
            if None != baseHeaderOutParams: tmpParams['header'] = baseHeaderOutParams
            else: tmpParams['header'] = {}
            for key in url.meta:
                if key in HANDLED_HTTP_HEADER_PARAMS:
                    tmpParams['header'][key] = url.meta[key]
            if 0 < len(tmpParams['header']):
                outParams = tmpParams
            if 'iptv_proxy_gateway' in url.meta:
                outParams['proxy_gateway'] = url.meta['iptv_proxy_gateway']
            if 'iptv_http_proxy' in url.meta:
                outParams['http_proxy'] = url.meta['iptv_http_proxy']
        return outParams, postData
        
    @staticmethod
    def getBaseUrl(url, domainOnly=False):
        parsed_uri = urlparse( url )
        if domainOnly:
            domain = '{uri.netloc}'.format(uri=parsed_uri)
        else:
            domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
        return domain
        
    @staticmethod
    def getFullUrl(url, mainUrl='http://fake/'):
        if not url: return ''
        if url.startswith('./'):
            url = url[1:]

        currUrl = mainUrl
        mainUrl = common.getBaseUrl(currUrl)

        if url.startswith('//'):
            proto = mainUrl.split('://', 1)[0]
            url = proto + ':' + url
        elif url.startswith('://'):
            proto = mainUrl.split('://', 1)[0]
            url = proto + url
        elif url.startswith('/'):
            url = mainUrl + url[1:]
        elif 0 < len(url) and '://' not in url:
            if currUrl == mainUrl:
                url =  mainUrl + url
            else:
                url = urljoin(currUrl, url)
        return url

    @staticmethod
    def isValidUrl(url):
        return url.startswith('http://') or url.startswith('https://')

    @staticmethod
    def buildHTTPQuery(query):
        def _process(query, data, key_prefix):
            if isinstance(data, dict):
                for key, value in data.iteritems():
                    key = '%s[%s]' % (key_prefix, key) if key_prefix else key
                    _process(query, value, key)
            elif isinstance(data, list):
                for idx in range(len(data)):
                    _process(query, data[idx], '%s[%s]' % (key_prefix, idx))
            else:
                query.append((key_prefix, data))
        _query = []
        _process(_query, query, '')
        return _query

    def __init__(self, proxyURL= '', useProxy = False, useMozillaCookieJar=True):
        self.proxyURL = proxyURL
        self.useProxy = useProxy
        self.geolocation = {}
        self.meta = {} # metadata from previus request
        
        self.curlSession = None
        self.pyCurlAvailable = None
        if not useMozillaCookieJar:
            raise Exception("You should stop use parameter useMozillaCookieJar it change nothing, because from only MozillaCookieJar can be used")
    
    def reportHttpsError(self, type, url, msg):
        domain = self.getBaseUrl(url, True)
        messages = []
        messages.append(_('HTTPS connection error "%s"\n') % msg)
        messages.append(_('It looks like your current configuration do not allow to connect to the https://%s/.\n') % domain)
        
        if type == 'verify' and IsHttpsCertValidationEnabled():
            messages.append(_('You can disable HTTPS certificates validation in the E2iPlayer configuration to suppress this problem.'))
        else:
            pyCurlInstalled = False
            try:
                verInfo = pycurl.version_info()
                printDBG("usePyCurl VERSION: %s" % [verInfo])
                if verInfo[4] & (1<<7) and verInfo[1].startswith('7.6') and verInfo[5] == 'wolfSSL/3.15.3':
                    pyCurlInstalled = True
            except Exception:
                printExc()
            if pyCurlInstalled:
                if not UsePyCurl():
                    messages.append(_('You can enable PyCurl in the E2iPlayer configuration to fix this problem.'))
                else:
                    messages.append(_('Please report this problem to the developer %s.') % 'iptvplayere2@gmail.com')
            else:
                messages.append(_('You can install PyCurl package from %s to fix this problem.') % 'http://www.iptvplayer.gitlab.io/')
        GetIPTVNotify().push('\n'.join(messages), 'error', 40, type + domain, 40)
    
    def usePyCurl(self):
        bRet = False
        if UsePyCurl():
            if self.pyCurlAvailable == None:
                try:
                    #import pycurl as pycurl
                    #test = pycurl.SSLVERSION_TLSv1_3
                    verInfo = pycurl.version_info()
                    printDBG("usePyCurl VERSION: %s" % [verInfo])
                    # #define CURL_VERSION_ASYNCHDNS    (1<<7)
                    # we need to have ASYNC DNS to be able "cancel"
                    # request
                    if verInfo[4] & (1<<7):
                        self.pyCurlAvailable = True
                    else:
                        self.pyCurlAvailable = False
                except Exception:
                    self.pyCurlAvailable = False
                    printExc()
            bRet = self.pyCurlAvailable
        return bRet
        
    def getCountryCode(self, lower=True):
        if 'countryCode' not in self.geolocation:
            sts, data = self.getPage('http://ip-api.com/json')
            if sts:
                try:
                    self.geolocation['countryCode'] = json_loads(data)['countryCode']
                except Exception:
                    printExc()
        return self.geolocation.get('countryCode', '').lower()
        
    def _pyCurlLoadCookie(self, cookiefile, ignoreDiscard=True, ignoreExpires=False):
        cj = cookielib.MozillaCookieJar()
        f = open(cookiefile)
        lines = f.readlines()
        f.close()
        for idx in range(len(lines)):
            lineNeedFix = False
            fields = lines[idx].split('\t')
            if len(fields) < 5: continue
            if fields[0].startswith('#HttpOnly_'):
                fields[0] = fields[0][10:]
                lineNeedFix = True
            if fields[4] == '0':
                fields[4] = ''
                lineNeedFix = True
            if lineNeedFix: 
                lines[idx] = '\t'.join(fields)
        cj._really_load(StringIO(''.join(lines)), cookiefile, ignore_discard=ignoreDiscard, ignore_expires=ignoreExpires)
        return cj
        
    def clearCookie(self, cookiefile, leaveNames=[], removeNames=None, ignoreDiscard=True, ignoreExpires=False):
        try:
            toRemove = []
            if self.usePyCurl():
                cj = self._pyCurlLoadCookie(cookiefile, ignoreDiscard, ignoreExpires)
            else:
                cj = cookielib.MozillaCookieJar()
            cj.load(cookiefile, ignore_discard = ignoreDiscard)
            for cookie in cj:
                if cookie.name not in leaveNames and (None == removeNames or cookie.name in removeNames):
                    toRemove.append(cookie)
            for cookie in toRemove:
                cj.clear(cookie.domain, cookie.path, cookie.name)
            cj.save(cookiefile, ignore_discard = ignoreDiscard)
        except Exception:
            printExc()
            return False
        return True
        
    def getCookieItem(self, cookiefile, item):
        cookiesDict = self.getCookieItems(cookiefile)
        return cookiesDict.get(item, '')
        
    def getCookie(self, cookiefile, ignoreDiscard=True, ignoreExpires=False):
        cj = None
        try:
            if self.usePyCurl():
                cj = self._pyCurlLoadCookie(cookiefile, ignoreDiscard, ignoreExpires)
            else:
                cj = cookielib.MozillaCookieJar()
                cj.load(cookiefile, ignore_discard = ignoreDiscard)
        except Exception:
            printExc()
        return cj

    def getCookieItems(self, cookiefile, ignoreDiscard=True, ignoreExpires=False):
        cookiesDict = {}
        try:
            cj = self.getCookie(cookiefile, ignoreDiscard, ignoreExpires)
            for cookie in cj:
                cookiesDict[cookie.name] = cookie.value
        except Exception:
            printExc()
        return cookiesDict
        
    def getCookieHeader(self, cookiefile, allowedNames=[], unquote=True, ignoreDiscard=True, ignoreExpires=False):
        ret = ''
        try:
            cookiesDict = self.getCookieItems(cookiefile, ignoreDiscard, ignoreExpires)
            for name in cookiesDict:
                if 0 < len(allowedNames) and name not in allowedNames: continue
                value = cookiesDict[name]
                if unquote: value = urllib.unquote(value)
                ret += '%s=%s; ' % (name, value)
        except Exception:
            printExc()
        return ret

    def _getPageWithPyCurl(self, url, params = {}, post_data = None):
        if IsMainThread():
            msg1 = _('It is not allowed to call getURLRequestData from main thread.')
            msg2 = _('You should never perform block I/O operations in the __init__.')
            GetIPTVNotify().push('\s'.join([msg1, msg2]), 'error', 40)
            raise Exception("Wrong usage!")
        
        # by default we will work in return_data mode
        if 'return_data' not in params:
            params['return_data'] = True
        
        self.meta = {}
        metadata = self.meta
        out_data = None
        sts = False
        
        buffer = StringIO()
        checkFromFirstBytes = params.get('check_first_bytes', [])
        fileHandler = None
        firstAttempt = [True]
        maxDataSize = params.get('max_data_size', -1)
        
        responseHeaders = {}
        def _headerFunction(headerLine):
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
            if firstAttempt[0]:
                firstAttempt[0] = False
                if 'check_maintype' in params and \
                    params['check_maintype'] != responseHeaders.get('content-type', '').split('/', 1)[0]:
                    printDBG('wrong maintype: %s' % responseHeaders.get('content-type', ''))
                    return 0
                
                if 'check_subtypes' in params:
                    contentSubType = responseHeaders.get('content-type', '').split('/', 1)[-1]
                    try:
                        valid = False
                        for subType in params['check_subtypes']:
                            if subType == contentSubType:
                                valid = True
                                break
                        if not valid:
                            printDBG('wrong type: %s' % responseHeaders.get('content-type', ''))
                            return 0
                    except Exception:
                        printExc()
                        return 0 # wrong params?
 
            # if we should check start body data 
            if len(checkFromFirstBytes):
                buffer.write(toWriteData)
                toWriteData = None
                valid = False
                value = buffer.getvalue()
                for toCheck in checkFromFirstBytes:
                    if len(toCheck) <= len(value):
                        if value.startswith(toCheck):
                            valid = True
                            # valid no need to check anymore
                            del checkFromFirstBytes[:]
                            break
                    elif toCheck.startswith(value):
                        # it could be valid - we need to wait for more data
                        valid = True
                if not valid:
                    printDBG('wrong body: %s' % hexlify(value))
                    return 0
            
            if fileHandler != None and 0 == len(checkFromFirstBytes):
                # all check were done so, we can start write data to file
                try:
                    if fileHandler.tell() == 0 and buffer.tell() > 0:
                        fileHandler.write(buffer.getvalue())
                    
                    if toWriteData != None:
                        fileHandler.write(toWriteData)
                except Exception:
                    printExc()
                    return 0 # wrong file handle
                
            if  toWriteData != None and params['return_data']:
                buffer.write(toWriteData)
            
        def _terminateFunction(download_t, download_d, upload_t, upload_d):
            if IsThreadTerminated():
                printDBG(">> _terminateFunction")
                return True # anything else then None will cause pycurl perform cancel
        
        try:
            timeout = params.get('timeout', None)
            
            if 'host' in params:
                host = params['host']
            else:
                host = self.HOST

            if 'header' in params:
                headers = params['header']
            elif None != self.HEADER:
                headers = self.HEADER
            else:
                headers = { 'User-Agent' : host }
                
            if 'User-Agent' not in headers:
                headers['User-Agent'] = host
            
            printDBG('pCommon - getPageWithPyCurl() -> params: ' + str(params))
            printDBG('pCommon - getPageWithPyCurl() -> headers: ' + str(headers)) 
            
            if 'save_to_file' in params:
                fileHandler = file(params['save_to_file'], "wb")
            
            # we can not kill thread when we are in any function of pycurl
            SetThreadKillable(False)
            
            if None == self.curlSession:
                curlSession = pycurl.Curl()
            elif params.get('use_new_session', False):
                curlSession = self.curlSession
                self.curlSession = None
                curlSession.close()
                curlSession = pycurl.Curl()
            else:
                # use previous session to be able to reuse connection
                curlSession = self.curlSession
                self.curlSession = None
                curlSession.reset()
            
            if params.get('use_fresh_connect', False):
                curlSession.setopt(pycurl.FRESH_CONNECT, 1);
            
            customHeaders = []
            for key in headers:
                lKey = key.lower()
                if lKey == 'user-agent': curlSession.setopt(pycurl.USERAGENT, headers[key])
                elif lKey == 'cookie': curlSession.setopt(pycurl.COOKIE, headers[key])
                elif lKey == 'referer': curlSession.setopt(pycurl.REFERER, headers[key])
                else: customHeaders.append('%s: %s' % (key, headers[key]))
            if len(customHeaders):
                curlSession.setopt(pycurl.HTTPHEADER, customHeaders)
            
            curlSession.setopt(pycurl.ACCEPT_ENCODING, "") # enable all supported built-in compressions
            if None != params.get('ssl_protocol', None):
                sslProtoVer = self.getPyCurlSSLProtocolVersion(params['ssl_protocol'])
                if None != sslProtoVer:
                    curlSession.setopt(pycurl.SSLVERSION, sslProtoVer)
            
            if 'use_cookie' not in params and 'cookiefile' in params and ('load_cookie' in params or 'save_cookie' in params):
                params['use_cookie'] = True
                
            if params.get('use_cookie', False):
                cookiesStr = ''
                for cookieKey in params.get('cookie_items', {}).keys():
                    printDBG("cookie_item[%s=%s]" % (cookieKey, params['cookie_items'][cookieKey]))
                    cookiesStr += '%s=%s; ' % (cookieKey, params['cookie_items'][cookieKey])
                
                if cookiesStr != '':
                    curlSession.setopt(pycurl.COOKIE, cookiesStr) #'Set-Cookie: foo=baar') #
            
                if params.get('load_cookie', False):
                    curlSession.setopt(pycurl.COOKIEFILE, params.get('cookiefile', ''))
                
                if params.get('save_cookie', False):
                    curlSession.setopt(pycurl.COOKIEJAR, params.get('cookiefile', ''))
                    
            if timeout != None:
                curlSession.setopt(pycurl.CONNECTTIMEOUT, timeout) # in seconds - connection timeout
                curlSession.setopt(pycurl.LOW_SPEED_TIME, timeout) # in seconds
                curlSession.setopt(pycurl.LOW_SPEED_LIMIT, 10) # in bytes
                # set maximum time the request is allowed to take
                #curlSession.setopt(pycurl.TIMEOUT, 300) # in seconds
            
            if not params.get('no_redirection', False):
                curlSession.setopt(pycurl.FOLLOWLOCATION, 1)
                curlSession.setopt(pycurl.UNRESTRICTED_AUTH, 1)
                curlSession.setopt(pycurl.MAXREDIRS, 5)
            
            # debug 
            #curlSession.setopt(pycurl.VERBOSE, 1)
            #curlSession.setopt(pycurl.DEBUGFUNCTION, debug_fun)
            
            if not IsHttpsCertValidationEnabled():
                curlSession.setopt(pycurl.SSL_VERIFYHOST, 0)
                curlSession.setopt(pycurl.SSL_VERIFYPEER, 0)
                #curlSession.setopt(pycurl.PROXY_SSL_VERIFYHOST, 0)
                curlSession.setopt(pycurl.PROXY_SSL_VERIFYPEER, 0)
            else:
                curlSession.setopt(pycurl.CAINFO, "/etc/ssl/certs/ca-certificates.crt")
                curlSession.setopt(pycurl.PROXY_CAINFO, "/etc/ssl/certs/ca-certificates.crt")
            
            #proxy support
            if self.useProxy:
                http_proxy = self.proxyURL
            else:
                http_proxy = ''
            #proxy from parameters (if available) overwrite default one
            if 'http_proxy' in params:
                http_proxy = params['http_proxy']
            if '' != http_proxy:
                printDBG('getPageWithPyCurl USE PROXY')
                curlSession.setopt(pycurl.PROXY, http_proxy)
            
            pageUrl = url
            proxy_gateway = params.get('proxy_gateway', '')
            if proxy_gateway != '':
                pageUrl = proxy_gateway.format(urllib.quote_plus(pageUrl, ''))
            printDBG("pageUrl: [%s]" % pageUrl)
            
            curlSession.setopt(pycurl.URL, pageUrl)
            
            if None != post_data:
                printDBG('pCommon - getPageWithPyCurl() -> post data: ' + str(post_data))
                if params.get('raw_post_data', False):
                    curlSession.setopt(pycurl.POSTFIELDS, post_data)
                elif params.get('multipart_post_data', False):
                    printDBG("multipart_post_data NOT SUPPORTED")
                    dataPost = post_data
                    curlSession.setopt(pycurl.HTTPPOST, post_data)
                    #curlSession.setopt(pycurl.CUSTOMREQUEST, "PUT")
                else:
                    curlSession.setopt(pycurl.POSTFIELDS, urllib.urlencode(post_data))

            curlSession.setopt(pycurl.HEADERFUNCTION, _headerFunction)

            if fileHandler: curlSession.setopt(pycurl.WRITEFUNCTION, _bodyFunction)
            elif maxDataSize >= 0: curlSession.setopt(pycurl.WRITEFUNCTION, _breakConnection)
            else: curlSession.setopt(pycurl.WRITEDATA, buffer)

            curlSession.setopt(pycurl.NOPROGRESS, False)
            curlSession.setopt(pycurl.PROGRESSFUNCTION, _terminateFunction)
            curlSession.setopt(pycurl.NOSIGNAL, 1)
            #if 0 == maxDataSize:
            #    curlSession.setopt(pycurl.NOBODY, True);

            if not IsThreadTerminated():
                if maxDataSize >= 0:
                    try:
                        curlSession.perform()
                    except pycurl.error as e:
                        if e[0] != pycurl.E_WRITE_ERROR:
                            raise e
                        else: printExc()
                else:
                    curlSession.perform()
                
                metadata['url'] = curlSession.getinfo(pycurl.EFFECTIVE_URL)
                metadata['status_code'] = curlSession.getinfo(pycurl.HTTP_CODE)
                metadata['size_download'] = curlSession.getinfo(pycurl.SIZE_DOWNLOAD)
                
                # reset will cause lost all cookies, so we force to saved them in the file
                if params.get('use_cookie', False) and params.get('save_cookie', False):
                    curlSession.setopt(pycurl.COOKIELIST , 'FLUSH')
                    curlSession.setopt(pycurl.COOKIELIST , 'ALL')
                
                curlSession.reset()
                # to be re-used in next request
                self.curlSession = curlSession 
                
                # we should not use pycurl anymore
                SetThreadKillable(True)
                
                self.fillHeaderItems(metadata, responseHeaders, collectAllHeaders=params.get('collect_all_headers'))
                
                if params['return_data']:
                    out_data = buffer.getvalue()
                else:
                    out_data = ""
                
                out_data, metadata = self.handleCharset(params, out_data, metadata)
                if metadata['status_code'] != 200:
                    ignoreCodeRanges = params.get('ignore_http_code_ranges', [(404, 404), (500, 500)])
                    for ignoreCodeRange in ignoreCodeRanges:
                        if metadata['status_code'] >= ignoreCodeRange[0] and metadata['status_code'] <= ignoreCodeRange[1]:
                            sts = True
                            break
                else:
                    sts = True
                    if metadata['content-type'] == 'image/webp':
                        new_name = params['save_to_file'].replace(".jpg",".webp")
                        printDBG("Change extension of webp image: %s" % new_name)
                        try:
                            os.rename(params['save_to_file'], new_name)
                            self.convertWebp(new_name)
                        except:
                            pass
                            
            if fileHandler:
                fileHandler.close()
        except pycurl.error as e:
            metadata['pycurl_error'] = (e[0], str(e[1]))
            printExc()
        except Exception:
            printExc()
        
        SetThreadKillable(True)
        
        printDBG('pCommon - getPageWithPyCurl() return -> \nsts: %s\nmetadata: %s\n' % (sts, metadata))
        if params.get('with_metadata', False):
            out_data = strwithmeta(out_data, metadata)
        
        return sts, out_data
    
    def getPageWithPyCurl(self, url, params = {}, post_data = None):
        # some error can be caused because of session reuse 
        # if we use old curlSession and fail we should
        # re-try with fresh curlSession
        if self.curlSession != None:
            sessionReused = True
        else:
            sessionReused = False
        
        sts, data = False, None
        try:
            maxTries = 3
            tries = 0
            while tries < maxTries:
                tries += 1
                sts, data = self._getPageWithPyCurl(url, params, post_data)
                if not sts and 'pycurl_error' in self.meta and \
                   pycurl.E_SSL_CONNECT_ERROR == self.meta['pycurl_error'][0]:
                    if 'SSL_set_session failed' in self.meta['pycurl_error'][1] or '-308' in self.meta['pycurl_error'][1]:
                        printDBG("pCommon - getPageWithPyCurl() - retry with fresh session")
                        if sessionReused:
                            sessionReused = False
                            continue
                    elif '-313' in self.meta['pycurl_error'][1] and 'ssl_protocol' not in params:
                        params = dict(params)
                        params['ssl_protocol'] = 'TLSv1_2'
                        continue
                break
            
            if not sts and 'pycurl_error' in self.meta:
                if self.meta['pycurl_error'][0] == pycurl.E_SSL_CONNECT_ERROR:
                    self.reportHttpsError('other', url, self.meta['pycurl_error'][1])
                elif self.meta['pycurl_error'][0] in [pycurl.E_SSL_CACERT, pycurl.E_SSL_ISSUER_ERROR, \
                                                      pycurl.E_SSL_PEER_CERTIFICATE, pycurl.E_SSL_CACERT_BADFILE]:
                    self.reportHttpsError('verify', url, self.meta['pycurl_error'][1])
                elif self.meta['pycurl_error'][0] == pycurl.E_SSL_INVALIDCERTSTATUS:
                    self.reportHttpsError('verify', url, self.meta['pycurl_error'][1])
        except Exception:
            printExc()
        return sts, data

    def fillHeaderItems(self, metadata, responseHeaders, camelCase=False, collectAllHeaders=False):

        returnKeys = ['content-type', 'content-disposition', 'content-length', 'location']
        
        if camelCase: 
            sourceKeys = ['Content-Type', 'Content-Disposition', 'Content-Length', 'Location']
        else: 
            sourceKeys = returnKeys
        
        for idx in range(len(returnKeys)):
            if sourceKeys[idx] in responseHeaders:
                metadata[returnKeys[idx]] = responseHeaders[sourceKeys[idx]]
                #printDBG(sourceKeys[idx] + " ---->  " + responseHeaders[sourceKeys[idx]])
                
        #printDBG(str(responseHeaders))
        
        if collectAllHeaders:
            if "Access-Control-Allow-Headers" in responseHeaders:
                acah = responseHeaders["Access-Control-Allow-Headers"]
                acah_keys= acah.split(',')
                
                for key in acah_keys:
                    key = key.strip()
                    if key in responseHeaders:
                        metadata[key.lower()]=responseHeaders[key]
                        #printDBG(key + " ---->  " + responseHeaders[key])

            for header, value in responseHeaders.iteritems():
                metadata[header.lower()] = responseHeaders[header]
                #printDBG(header + " ---->  " + value)

    def getPage(self, url, addParams = {}, post_data = None):
        ''' wraps getURLRequestData '''
        
        # if curl should be used and can be used
        if addParams.get('return_data', True) and self.usePyCurl():
            return self.getPageWithPyCurl(url, addParams, post_data)
        
        try:
            addParams['url'] = url
            if 'return_data' not in addParams:
                addParams['return_data'] = True
            response = self.getURLRequestData(addParams, post_data)
            status = True
        except urllib2.HTTPError, e:
            try:
                printExc()
                status = False
                response = e
                if addParams.get('return_data', False):
                    self.meta = {}
                    metadata = self.meta
                    metadata['url'] = e.fp.geturl()
                    metadata['status_code'] = e.code
                    self.fillHeaderItems(metadata, e.fp.info(), True, collectAllHeaders=addParams.get('collect_all_headers'))
                    
                    data = e.fp.read(addParams.get('max_data_size', -1))
                    if e.fp.info().get('Content-Encoding', '') == 'gzip':
                        data = DecodeGzipped(data)
                    
                    data, metadata = self.handleCharset(addParams, data, metadata)
                    response = strwithmeta(data, metadata)
                    e.fp.close()
            except Exception:
                printExc()
        except urllib2.URLError, e:
            printExc()
            errorMsg = str(e) 
            if 'ssl_protocol' not in addParams and 'TLSV1_ALERT_PROTOCOL_VERSION' in errorMsg:
                    try:
                        newParams = dict(addParams)
                        newParams['ssl_protocol'] = 'TLSv1_2'
                        return self.getPage(url, newParams, post_data)
                    except Exception: 
                        pass
            if 'VERSION' in errorMsg:
                self.reportHttpsError('version', url, errorMsg)
            elif 'VERIFY_FAILED' in errorMsg:
                self.reportHttpsError('verify', url, errorMsg)
            elif 'SSL' in errorMsg or 'unknown url type: https' in errorMsg: #GET_SERVER_HELLO
                self.reportHttpsError('other', url, errorMsg)
            
            response = None
            status = False
                
        except Exception:
            printExc()
            response = None
            status = False
        
        if addParams['return_data'] and status and not isinstance(response, basestring):
            status = False
            
        return (status, response)
    
    def getPageCFProtection(self, baseUrl, params={}, post_data=None):
        cfParams = params.get('cloudflare_params', {})
        
        def _getFullUrl(url, baseUrl):
            if 'full_url_handle' in cfParams:
                return cfParams['full_url_handle'](url)
            return self.getFullUrl(url, baseUrl)
        
        def _getFullUrl2(url, baseUrl):
            if 'full_url_handle2' in cfParams:
                return cfParams['full_url_handle2'](url)
            return url
        
        r = ""
        url = baseUrl
        header = {'Referer':url, 'User-Agent':cfParams.get('User-Agent', ''), 'Accept-Encoding':'text'}
        header.update(params.get('header', {}))
        params.update({'with_metadata':True, 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': cfParams.get('cookie_file', ''), 'header':header})
        sts, data = self.getPage(url, params, post_data)
        
        #printDBG("Cloudflare Url: %s" % data.meta["url"])
        
        current = 0
        while current < 5:
            #if True:
            if not sts and None != data:
                start_time = time.time()
                current += 1
                doRefresh = False
                try:
                    domain = self.getBaseUrl(data.meta['url'])
                    verData = data
                    #printDBG("------------------")
                    #printDBG(verData)
                    #printDBG("------------------")
                    if 'sitekey' not in verData and 'challenge' not in verData: break
                    
                    printDBG(">>")
                    printDBG(verData)
                    printDBG("<<")
                    
                    sitekey = self.ph.getSearchGroups(verData, 'data-sitekey="([^"]+?)"')[0]
                    id = self.ph.getSearchGroups(verData, 'data-ray="([^"]+?)"')[0]
                    
                    if sitekey != '':
                        if self.ph.getSearchGroups(verData, 'data-sitekey="([^"]+?)"')[0]:
                            printDBG("*************** CloudFlare prompts hCaptcha *************")
                            
                            challenge_form = re.findall("(<form class=\"challenge-form\".*?</form>)",verData, re.S)
                            if not challenge_form:
                                continue
                            
                            challenge_form = challenge_form[0]
                            
                            from Plugins.Extensions.IPTVPlayer.libs.hcaptcha import UnCaptchahCaptcha
                            hcaptcha = UnCaptchahCaptcha(lang=GetDefaultLang(), params = params)
                            
                            token = hcaptcha.processCaptcha(challenge_form, domain , GetDefaultLang(), params)
                            
                            if token == '': 
                                return False, None
                            
                            action = re.findall('action="([^"]+?)"', challenge_form)[0]
                            key = re.findall('data-sitekey="([^"]+?)"', challenge_form)[0]
                            dataray = re.findall('data-ray="([^"]+?)"', challenge_form)[0]
                            scriptUrl = re.findall('<script.*src="([^"]+?)"', challenge_form)[0]
                            
                            post_data2 = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', challenge_form))
                            post_data2['id'] = dataray
                            post_data2['h-captcha-response'] = token
                            post_data2['g-recaptcha-response'] = token
                            #if post_data2.get("r","") == "":
                            #    post_data2["r"] = r
                                
                            printDBG("--------------- post data after captcha ------------")
                            printDBG(json_dumps(post_data2))
                            
                            url = _getFullUrl(action, domain)
                        
                            params2 = { 
                                'use_cookie': True, 
                                'load_cookie': True,
                                'save_cookie': True,
                                'raw_post_data': True, 
                                'return_data': True, 
                                'cookiefile': params['cloudflare_params']['cookie_file']
                            }
                            
                            params2['header'] = {
                                'Referer': baseUrl,
                                'Accept': 'text/html',
                                'Accept-Encoding': 'gzip',
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.106 Safari/537.36'
                            }
                            
                            post_data2= json_dumps(post_data2)
                            
                        else:
                            printDBG("*************** CloudFlare prompts reCaptcha *************")
                                
                            from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
                        
                            recaptcha = UnCaptchaReCaptcha(lang=GetDefaultLang())
                            recaptcha.HTTP_HEADER['Referer'] = baseUrl
                            if '' != cfParams.get('User-Agent', ''): recaptcha.HTTP_HEADER['User-Agent'] = cfParams['User-Agent']
                        
                            token = recaptcha.processCaptcha(sitekey)
                        
                            if token == '': 
                                return False, None
                        
                            sts, tmp = self.ph.getDataBeetwenMarkers(verData, '<form', '</form>', caseSensitive=False)
                            if not sts: return False, None

                            url = self.ph.getSearchGroups(tmp, 'action="([^"]+?)"')[0]
                            if url != '': url = _getFullUrl( url, domain )
                            else: url = data.meta['url']
                            actionType = self.ph.getSearchGroups(tmp, 'method="([^"]+?)"', 1, True)[0].lower()
                            post_data2 = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', tmp))
                            #post_data2['id'] = id
                        
                            if '' != token:
                                post_data2['g-recaptcha-response'] = token
                            else:
                                continue
                            params2 = dict(params)
                            params2['header']= dict(params['header'])
                            params2['header']['Referer'] = baseUrl
                            
                            if actionType == 'get':
                                if '?' in url:
                                    url += '&'
                                else:
                                    url += '?'
                                url += urllib.urlencode(post_data2)
                                post_data2 = None
                            
                        sts, data = self.getPage(url, params2, post_data2)
                        printDBG("+++++++++++++")
                        printDBG(sts)
                        printDBG("-------------")
                        printDBG(data)
                        printDBG("++++++++++++++")
                    
                    else:
                        printDBG("*************** CloudFlare: Searching javascript code *************")

                        dat = ""
                        challengeType = 0
                        
                        datas = ph.findall(verData, ('<script', '>'), '</script>', flags=0)
                        for item in datas:
                            if 'setTimeout' in item and 'submit()' in item:
                                dat = item
                                challengeType = 1
                                break
                            elif 'window._cf_chl_opt' in item:
                                dat = item 
                                challengeType = 2

                        if challengeType == 0:
                            GetIPTVNotify().push(_("New javascript not yet supported!"), 'info', 5)
                             
                            sts, data = self.getPage(url, params, post_data)
                            
                        elif challengeType == 2:
                            #new javascript challenge
                            GetIPTVNotify().push(_("New javascript not yet supported!"), 'info', 5)
                            
                            # read data in input
                            '''
                                window._cf_chl_opt={
                                  cvId: "1",
                                  cType: "non-interactive",
                                  cNounce: "26660",
                                  cRay: "5ac74ed95fb0f933",
                                  cHash: "eb58dc0fc80046a",
                                  cRq: {
                                    d: "2wOPpt6Rz0hp98w7LWqi2DCq40ly1Caj7tlM3OzjWh+x3STQIs92O5s1emIiqTUBgRI9LGqSs3KEjhhHtABOz48TWHrhvrSRErjPosaSt1fp4a3hVF06KFnNNyGYX00wdybYjMm7GTis3AlAT6kEWXKZ3m22o0IEPgbsDjV5HSlnjiV28fhf3OSadQlKe69HC5ntRLiXHDMwhMayLLbYqQIc/kbWej6PPjuDWCZqTNYGHNkBnQnRVVPN+JT5iMMvDCKxod5+6XzN2OBgwLES7++REiANKzjPcbNV0NviqU+rSVzoKwTIWL3iRWYTX+xrxXxPWEgrzyaj+GvHTUmvpfS865ulGhqMHOJYojIlIl7UFAXeXgUs4BqvHcCjLu+o",
                                    t: "MTU5MzY4MTgwNi4zMDYwMDA=",
                                    m: "YsUG/qEAi/HzONdr+WCreA0qbRGWCidXJeJdAfTrYQo=",
                                    i1: "dXmQj8RI29F/GXqoNbw7Dg==",
                                    i2: "FqoqVwUBuH8bcn9eSrnu3w==",
                                  }
                                }
                                window._cf_chl_enter = function(){window._cf_chl_opt.p=1};
                            '''
                            
                            data_input = re.findall("(window._cf_chl_opt=\{.*?\};)", data, re.S)
                            if data_input:
                                data_input = data_input[0]
                                printDBG("-------------- data_input---------------")
                                printDBG(data_input)
                                
                                jsch_url = re.findall("cpo.src\s?=\s?\"([^\"]+?)\"", data, re.S)
                                if jsch_url:
                                    jsch_url = urljoin(domain, jsch_url[0])
                                    printDBG(jsch_url)
                                    
                                    sts, jschCode = self.getPage(jsch_url, params)

                                    
                                    printDBG("-----------  jschCode  -----------")
                                    printDBG("----------------------------------")
                                    printDBG(jschCode)
                                    printDBG("----------------------------------")

                                    js_params = [{'path' : GetJSScriptFile('cf_max.byte')}]
                                    code = "var window = {}; \n\n" + data_input + "\n\n" + jschCode
                                    js_params.append({'code': code})
                                    ret = js_execute_ext( js_params )
                                    printDBG(ret)

                                    
                        else:
                            
                            # old javascript challenge
                            
                            # uncomment to solve 
                            #break
                            
                            decoded = ''
                            
                            #first part of code
                            js_params = [{'path' : GetJSScriptFile('cf_max.byte')}]
                            #particular div element
                            #tmp = ph.findall(verData, ('<div', '>', 'id'), '</div>', flags=ph.START_S)
                            
                            
                            code2=''
                            numChildren = 5
                            #<div style="display:none;visibility:hidden;">
                            
                            divs = re.findall("<div.*?id=\"([^\"]+)\">(.*?)</div>", data)
                            for t in divs:
                                name_id = t[0]
                                if len(name_id)>=8 and len(name_id)<=12:
                                    numChildren = numChildren + 1
                                    value_id = t[1]
                                    code2 = code2 + "\ndocument.children.push ( new element('', '%s', 'div')); document.children[%d].innerHTML ='%s';" % (name_id, numChildren,value_id)
                                                                    
                            printDBG("--------------- code 2 ------------------")
                            printDBG(code2)
                            printDBG("-----------------------------------------")
                            #script part in variable called 'dat'
                            printDBG("-------------- dat prima delle sostituzioni----------------------")
                            printDBG(dat)
                            printDBG("-----------------------------------------")
                            #dat = dat.replace('(function(){\n\n    var a = function() {try{return !!window.addEventListener} catch(e) {return !1} },\n    b = function(b, c) {a() ? document.addEventListener("DOMContentLoaded", b, c) : document.attachEvent("onreadystatechange", b)};\n    b(function()','function pippo()')
                            pattern = re.compile("\(function\(\)\{.*?b\(function\(\)", re.S)
                            dat = re.sub(pattern, "function pippo()", dat)
                            
                            if 'return  f.submit();' in dat:
                                dat = dat.replace('return  f.submit();','print(a.value); return (a.value);')
                            else:
                                dat = dat.replace('f.submit()','print(a.value);')
                            dat = dat.replace('setTimeout(function(){','')
                            
                            #var cookiesEnabled=(navigator.cookieEnabled)? true : false;
                            #var cookieSupportInfix=cookiesEnabled?'/nocookie':'/cookie';
                            dat = dat.replace("var cookiesEnabled=(navigator.cookieEnabled)? true : false;","")
                            dat = dat.replace("var cookieSupportInfix=cookiesEnabled?'/nocookie':'/cookie';","")
                            
                            pattern2= re.compile("\},4000\);.*?\)\(\)",re .S)
                            dat = re.sub(pattern2,'}', dat)
                            
                            
                            #new version
                            #t = document.createElement('div');
                            #t.innerHTML="<a href='/'>x</a>";
                            #t = t.firstChild.href;r = (setInterval(function(){}, 100),t.match(/https?:\/\//)[0]);
                            dat = dat.replace("r = (setInterval(function(){}, 100),t.match(/https?:\/\//)[0]);","r = t.match(/https?:\/\//)[0];")
                            #old version
                            if 'cpo' in dat:
                                dat = dat.replace("t = document.createElement('div');\n        cpo = {};\n        t.innerHTML=\"<a href='/'>x</a>\";\n        cpo.src = \"/cdn-cgi/challenge-platform/orchestrate/jsch/v1\";\n        t = t.firstChild.href;",'t="%domain%";').replace('%domain%',domain)
                            else:
                                dat = dat.replace("t = document.createElement('div');\n        t.innerHTML=\"<a href='/'>x</a>\";\n        t = t.firstChild.href;",'t="%domain%";').replace('%domain%',domain)
                            
                            
                            
                            pattern3 = re.compile("var a = document.*?appendChild\(.*?\);",re.S)
                            dat = re.sub(pattern3, "", dat)
                            
                            printDBG("-------------- dat dopo le sostituzioni----------------------")
                            printDBG(dat)
                            printDBG("-----------------------------------------")
                            
                            js_params.append({'code': "%s\n%s\n\npippo(); " % (code2, dat)})
                            ret = js_execute_ext( js_params )
                            printDBG(ret)
                            
                            formTag = self.ph.getDataBeetwenNodes(verData, ('<form','>', 'challenge'), ('</form','>'))[1]
                            formTag = re.sub("<!--.*?-->", "<!-- -->", formTag)

                            printDBG("--------challenge form-----------")
                            printDBG(formTag)
                            printDBG("--------challenge form-----------")
                            
                            get_data_1 = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', formTag))
                            
                            get_data_2 = dict(re.findall(r'<input[^>]*value="([^"]*)"[^>]*name="([^"]*)"[^>]*>', formTag))

                            printDBG("get_data_1: %s" % str(get_data_1))
                            printDBG("get_data_2: %s" % str(get_data_2))

                            get_data={}
                            
                            for xx in get_data_1:
                                if not get_data.get(xx,''):
                                    get_data[xx] = get_data_1[xx]
                                        
                            #get_data.update(get_data_1)
                            
                            for xx in get_data_2:
                                if not get_data.get(get_data_2[xx],''):
                                    get_data[get_data_2[xx]] = xx
                                    
                            #get_data.update(get_data_2_swap)
                            #get_data['cf_ch_verify']='plat'
                            
                            get_data['jschl_answer'] = ret['data'].replace('\n','')
                            
                            verUrl =  _getFullUrl( ph.getattr(verData, 'action'), domain)
                            
                            #unescape html code of & 
                            verUrl = verUrl.replace("&amp;",'&')
                            
                            postDataCF = {}
                            for key in get_data:
                                #postDataCF[key] = urllib.quote(get_data[key])
                                postDataCF[key] = get_data[key]
                                if key == "r":
                                    r = get_data[key]
                                    
                            printDBG("CF verification url: %s" % verUrl)
                            printDBG("CF post data: %s" % str(postDataCF))
                            
                            params2 = dict(params)
                            params2['load_cookie'] = True
                            params2['save_cookie'] = True
                            params2['header'] = dict(params.get('header', {}))
                            params2['header'].update({'Referer':url, 'User-Agent':cfParams.get('User-Agent', ''), 'Accept': 'text/html,application/xhtml+xml,application/xml','Accept-Encoding':'gzip', 'Content-Type':'application/x-www-form-urlencoded'})
                            if params2.get('raw_post_data',False):
                                params2.pop('raw_post_data')
                            
                            printDBG("Time spent: [%s]" % (time.time() - start_time))
                            if current == 1:
                                GetIPTVSleep().Sleep(4 -(time.time() - start_time))
                            else:
                                GetIPTVSleep().Sleep(4)
                            printDBG("Time spent: [%s]" % (time.time() - start_time))
                            printDBG("Timeout: [%s]" % 4000)
                        
                            sts, data = self.getPage(verUrl, params2, postDataCF)
  
                    #printDBG("Cloudflare Url: %s" % data.meta["url"])

                    #printDBG("--------- cf verification server answer -------")
                    #printDBG(data)
                    #printDBG(" ----------------------------------------------")
                        
                except Exception:
                    printExc()
                    break
            else:
                break
        return sts, data

    def convertWebp(self,file_path):
        printDBG("PCommon.convertWebp %s" % file_path)
        
        output_path = file_path.replace('.webp','.jpg')
        if IsExecutable('ffmpeg'):
            command = "ffmpeg -i %s %s && test -e %s && rm %s " % (file_path, output_path, output_path, file_path) 
            printDBG("Send command %s" % command)
            self.cmd = iptv_system(command)
            
    def removeWebp(self, file_path):
        printDBG("PCommon.removeWebp %s" % file_path)

            
    def saveWebFileWithPyCurl(self, file_path, url, add_params = {}, post_data = None):
        bRet = False
        downDataSize = 0
        
        add_params['with_metadata'] = True
        add_params['save_to_file'] = file_path
        if 'maintype' in add_params:
            add_params['check_maintype'] = add_params.pop('maintype')
        if 'subtypes' in add_params:
            add_params['check_subtypes'] = add_params.pop('subtypes')
        
        sts, data = self.getPageWithPyCurl(url, add_params, post_data)
        if sts:
            downDataSize = data.meta['size_download']
        else:
            rm(file_path)
        return {'sts': sts, 'fsize': downDataSize}
            
    def saveWebFile(self, file_path, url, addParams = {}, post_data = None):
        addParams = dict(addParams)
        
        outParams, postData = self.getParamsFromUrlWithMeta(url)
        addParams.update(outParams)
        if 'header' not in addParams and 'host' not in addParams:
            host = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'
            header = {'User-Agent': host, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
            addParams['header'] = header
        addParams['return_data'] = False
        
        # if curl should and can be used
        if self.usePyCurl():
            return self.saveWebFileWithPyCurl(file_path, url, addParams, post_data)
    
        bRet = False
        downDataSize = 0
        dictRet = {}
        try:
            sts, downHandler = self.getPage(url, addParams, post_data)

            if addParams.get('ignore_content_length', False):
                meta = downHandler.info()
                contentLength = int(meta.getheaders("Content-Length")[0])
            else:
                contentLength = None
            
            checkFromFirstBytes = addParams.get('check_first_bytes', [])
            
            OK = True
            if 'maintype' in addParams and addParams['maintype'] != downHandler.headers.maintype:
                printDBG("common.getFile wrong maintype! requested[%r], retrieved[%r]" % (addParams['maintype'], downHandler.headers.maintype))
                if 0 == len(checkFromFirstBytes):
                    downHandler.close()
                OK = False
            
            if OK and 'subtypes' in addParams:
                OK = False
                for item in addParams['subtypes']:
                    if item == downHandler.headers.subtype:
                        OK = True
                        break
            
            if OK or len(checkFromFirstBytes):
                blockSize = addParams.get('block_size', 8192)
                fileHandler = None
                while True:
                    buffer = downHandler.read(blockSize)
                    
                    if len(checkFromFirstBytes):
                        OK = False
                        for item in checkFromFirstBytes:
                            if buffer.startswith(item):

                                # change extension of file
                                if item in ['\xFF\xD8','\xFF\xD9']: 
                                    printDBG("SaveWebFile. It's a jpeg")
                                elif item == '\x89\x50\x4E\x47': 
                                    printDBG("SaveWebFile. It's a png")
                                    #file_path = file_path.replace('.jpg','.png')
                                elif item in ['GIF87a','GIF89a']: 
                                    printDBG("SaveWebFile. It's a gif")
                                    #file_path = file_path.replace('.jpg','.gif')
                                elif item == 'RI':
                                    printDBG("SaveWebFile. It's a webp")
                                    file_path = file_path.replace('.jpg','.webp')
                                OK = True
                                break
                        if not OK:
                            break
                        else:
                            checkFromFirstBytes = []
                    
                    if not buffer:
                        break
                    downDataSize += len(buffer)
                    if len(buffer):
                        if fileHandler == None:
                            fileHandler = file(file_path, "wb")
                        fileHandler.write(buffer)
                if fileHandler != None:
                    fileHandler.close()
                downHandler.close()
                if None != contentLength:
                    if contentLength == downDataSize:
                        bRet = True
                elif downDataSize > 0:
                    bRet = True
                
                # decode webp to jpeg
                if file_path.endswith(".webp"):
                    self.convertWebp(file_path)
                         
        except Exception:
            printExc("common.getFile download file exception")
        dictRet.update( {'sts': bRet, 'fsize': downDataSize} )
        return dictRet
        
    def getUrllibSSLProtocolVersion(self, protocolName):
        if not isinstance(protocolName, basestring):
            GetIPTVNotify().push('getUrllibSSLProtocolVersion error. Please report this problem to iptvplayere2@gmail.com', 'error', 40)
            return protocolName
        if protocolName == 'TLSv1_2':
            return ssl.PROTOCOL_TLSv1_2
        elif protocolName == 'TLSv1_1':
            return ssl.PROTOCOL_TLSv1_1
        return None
        
    def getPyCurlSSLProtocolVersion(self, protocolName):
        if not isinstance(protocolName, basestring):
            GetIPTVNotify().push('getPyCurlSSLProtocolVersion error. Please report this problem to iptvplayere2@gmail.com', 'error', 40)
            return protocolName
        if protocolName == 'TLSv1_2':
            return pycurl.SSLVERSION_TLSv1_2
        elif protocolName == 'TLSv1_1':
            return pycurl.SSLVERSION_TLSv1_1
        return None
    
    def getURLRequestData(self, params = {}, post_data = None):
        
        def urlOpen(req, customOpeners, timeout):
            if len(customOpeners) > 0:
                opener = urllib2.build_opener( *customOpeners )
                if timeout != None:
                    response = opener.open(req, timeout=timeout)
                else:
                    response = opener.open(req)
            else:
                if timeout != None:
                    response = urllib2.urlopen(req, timeout=timeout)
                else:
                    response = urllib2.urlopen(req)
            return response
        
        if IsMainThread():
            msg1 = _('It is not allowed to call getURLRequestData from main thread.')
            msg2 = _('You should never perform block I/O operations in the __init__.')
            GetIPTVNotify().push('\s'.join([msg1, msg2]), 'error', 40)
            raise Exception("Wrong usage!")
            
        if 'max_data_size' in params and not params.get('return_data', False):
            raise Exception("return_data == False is not accepted with max_data_size.\nPlease also note that return_data == False is deprecated and not supported with PyCurl HTTP backend!")
        
        cj = cookielib.MozillaCookieJar()
        response = None
        req      = None
        out_data = None
        opener   = None
        self.meta = {}
        metadata = self.meta
        
        timeout = params.get('timeout', None)
        
        if 'host' in params:
            host = params['host']
        else:
            host = self.HOST

        if 'header' in params:
            headers = params['header']
        elif None != self.HEADER:
            headers = self.HEADER
        else:
            headers = { 'User-Agent' : host }
            
        if 'User-Agent' not in headers:
            headers['User-Agent'] = host
        
        printDBG('pCommon - getURLRequestData() -> params: ' + str(params))
        printDBG('pCommon - getURLRequestData() -> headers: ' + str(headers)) 

        customOpeners = []
        #cookie support
        if 'use_cookie' not in params and 'cookiefile' in params and ('load_cookie' in params or 'save_cookie' in params):
            params['use_cookie'] = True 
        
        if params.get('use_cookie', False):
            if params.get('load_cookie', False):
                try:
                    cj.load(params['cookiefile'], ignore_discard = True)
                except IOError:
                    printDBG('Cookie file [%s] not exists' % params['cookiefile'])
                except Exception:
                    printExc()
            try:
                for cookieKey in params.get('cookie_items', {}).keys():
                    printDBG("cookie_item[%s=%s]" % (cookieKey, params['cookie_items'][cookieKey]))
                    cookieItem = cookielib.Cookie(version=0, name=cookieKey, value=params['cookie_items'][cookieKey], port=None, port_specified=False, domain='', domain_specified=False, domain_initial_dot=False, path='/', path_specified=True, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={'HttpOnly': None}, rfc2109=False)
                    cj.set_cookie(cookieItem)
            except Exception:
                printExc()
            customOpeners.append( urllib2.HTTPCookieProcessor(cj) )
            
        if params.get('no_redirection', False):
            customOpeners.append( NoRedirection() )
        
        if None != params.get('ssl_protocol', None):
            sslProtoVer = self.getUrllibSSLProtocolVersion(params['ssl_protocol'])
        else:
            sslProtoVer = None
        # debug 
        #customOpeners.append(urllib2.HTTPSHandler(debuglevel=1))
        #customOpeners.append(urllib2.HTTPHandler(debuglevel=1))
        if not IsHttpsCertValidationEnabled():
            try:
                if sslProtoVer != None:
                    ctx = ssl._create_unverified_context( sslProtoVer )
                else:
                    ctx = ssl._create_unverified_context()
                customOpeners.append(urllib2.HTTPSHandler(context=ctx))
            except Exception: pass
        elif sslProtoVer != None:
            ctx = ssl.SSLContext( sslProtoVer )
            customOpeners.append(urllib2.HTTPSHandler(context=ctx))
        
        #proxy support
        if self.useProxy:
            http_proxy = self.proxyURL
        else:
            http_proxy = ''
        #proxy from parameters (if available) overwrite default one
        if 'http_proxy' in params:
            http_proxy = params['http_proxy']
        if '' != http_proxy:
            printDBG('getURLRequestData USE PROXY')
            customOpeners.append( urllib2.ProxyHandler({"http":http_proxy}) )
            customOpeners.append( urllib2.ProxyHandler({"https":http_proxy}) )
        
        pageUrl = params['url']
        proxy_gateway = params.get('proxy_gateway', '')
        if proxy_gateway != '':
            pageUrl = proxy_gateway.format(urllib.quote_plus(pageUrl, ''))
        printDBG("pageUrl: [%s]" % pageUrl)

        if None != post_data:
            printDBG('pCommon - getURLRequestData() -> post data: ' + str(post_data))
            if params.get('raw_post_data', False):
                dataPost = post_data
            elif params.get('multipart_post_data', False):
                customOpeners.append( MultipartPostHandler() )
                dataPost = post_data
            else:
                dataPost = urllib.urlencode(post_data)
            req = urllib2.Request(pageUrl, dataPost, headers)
        else:
            req = urllib2.Request(pageUrl, None, headers)

        if not params.get('return_data', False):
            out_data = urlOpen(req, customOpeners, timeout)
        else:
            gzip_encoding = False
            try:
                response = urlOpen(req, customOpeners, timeout)
                if response.info().get('Content-Encoding') == 'gzip':
                    gzip_encoding = True
                try: 
                    metadata['url'] = response.geturl()
                    metadata['status_code'] = response.getcode()
                    self.fillHeaderItems(metadata, response.info(), True, collectAllHeaders=params.get('collect_all_headers'))
                except Exception: pass
                
                data = response.read(params.get('max_data_size', -1))
                response.close()
            except urllib2.HTTPError, e:
                ignoreCodeRanges = params.get('ignore_http_code_ranges', [(404, 404), (500, 500)])
                ignoreCode = False
                metadata['status_code'] = e.code
                for ignoreCodeRange in ignoreCodeRanges:
                    if e.code >= ignoreCodeRange[0] and e.code <= ignoreCodeRange[1]:
                        ignoreCode = True
                        break
                
                if ignoreCode:
                    printDBG('!!!!!!!! %s: getURLRequestData - handled' % e.code)
                    if e.fp.info().get('Content-Encoding', '') == 'gzip':
                        gzip_encoding = True
                    try: 
                        metadata['url'] = e.fp.geturl()
                        self.fillHeaderItems(metadata, e.fp.info(), True, collectAllHeaders=params.get('collect_all_headers'))
                    except Exception: pass
                    data = e.fp.read(params.get('max_data_size', -1))
                    #e.msg
                    #e.headers
                elif e.code == 503:
                    if params.get('use_cookie', False):
                        new_cookie = e.fp.info().get('Set-Cookie', '')
                        printDBG("> new_cookie[%s]" % new_cookie)
                        cj.save(params['cookiefile'], ignore_discard = True)
                    raise e
                else:
                    if e.code in [300, 302, 303, 307] and params.get('use_cookie', False) and params.get('save_cookie', False):
                        new_cookie = e.fp.info().get('Set-Cookie', '')
                        printDBG("> new_cookie[%s]" % new_cookie)
                        #for cookieKey in params.get('cookie_items', {}).keys():
                        #    cj.clear('', '/', cookieKey)
                        cj.save(params['cookiefile'], ignore_discard = True)
                    raise e
            try:
                if gzip_encoding:
                    printDBG('Content-Encoding == gzip')
                    out_data = DecodeGzipped(data)
                else:
                    out_data = data
            except Exception as e:
                printExc()
                if params.get('max_data_size', -1) == -1: 
                    msg1 = _("Critical Error – Content-Encoding gzip cannot be handled!")
                    msg2 = _("Last error:\n%s" % str(e))
                    GetIPTVNotify().push('%s\n\n%s' % (msg1, msg2), 'error', 20)
                out_data = data
 
        if params.get('use_cookie', False) and params.get('save_cookie', False):
            try:
                cj.save(params['cookiefile'], ignore_discard = True)
            except Exception as e:
                printExc()
                raise e
        
        out_data, metadata = self.handleCharset(params, out_data, metadata)
        if params.get('with_metadata', False) and params.get('return_data', False):
            out_data = strwithmeta(out_data, metadata)
        
        return out_data 
        
    def handleCharset(self, params, data, metadata):
        try:
            if params.get('return_data', False) and params.get('convert_charset', True) :
                encoding = ''
                if 'content-type' in metadata:
                    encoding = self.ph.getSearchGroups(metadata['content-type'], '''charset=([A-Za-z0-9\-]+)''', 1, True)[0].strip().upper()
                
                if encoding == '' and params.get('search_charset', False):
                    encoding = self.ph.getSearchGroups(data, '''(<meta[^>]+?Content-Type[^>]+?>)''', ignoreCase=True)[0]
                    encoding = self.ph.getSearchGroups(encoding, '''charset=([A-Za-z0-9\-]+)''', 1, True)[0].strip().upper()
                if encoding not in ['', 'UTF-8']:
                    printDBG(">> encoding[%s]" % encoding)
                    try:
                        data = data.decode(encoding).encode('UTF-8')
                    except Exception:
                        printExc()
                    metadata['orig_charset'] = encoding
        except Exception:
            printExc()
        return data, metadata

    def urlEncodeNonAscii(self, b):
        return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

    def iriToUri(self, iri):
        try:
            parts = urlparse(iri.decode('utf-8'))
            encodedParts = []
            for parti, part in enumerate(parts):
                newPart = part
                try:
                    if parti == 1: newPart = part.encode('idna')
                    else: newPart = self.urlEncodeNonAscii(part.encode('utf-8'))
                except Exception:
                    printExc()
                encodedParts.append(newPart)
            return urlunparse(encodedParts)
        except Exception:
            printExc()
        return iri

    def makeABCList(self, tab = ['0 - 9']):
        strTab = list(tab)
        for i in range(65,91):
            strTab.append(str(unichr(i)))    
        return strTab
