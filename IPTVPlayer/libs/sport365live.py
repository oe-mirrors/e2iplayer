# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import unpackJSPlayerParams, VIDEOWEED_decryptPlayerParams, VIDEOWEED_decryptPlayerParams2,\
                                                                SAWLIVETV_decryptPlayerParams, getDirectM3U8Playlist

from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
import random
import base64
from time import time
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from binascii import a2b_hex
from hashlib import md5
from datetime import datetime
############################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList

###################################################


class Sport365LiveApi:
    MAIN_URL = 'http://www.sport365.live/'
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36', 'Accept-Encoding': 'gzip, deflate', 'Referer': MAIN_URL}
    CACHE_AES_PASSWORD = ''

    def __init__(self):
        self.COOKIE_FILE = GetCookieDir('sport365live.cookie')
        self.sessionEx = MainSessionWrapper()
        self.cm = common()
        self.up = urlparser()
        self.http_params = {'header': dict(self.HTTP_HEADER), 'use_cookie': True, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.needRefreshAdvert = True

    def getPage(self, url, params={}, post_data=None):
        sts, data = self.cm.getPage(url, params, post_data)
        if sts:
            #printDBG("---")
            #printDBG("url: %s" % url)
            #printDBG(data)
            #printDBG("---")
            return sts, data

    def getFullUrl(self, url):
        if url.startswith('http'):
            return url
        elif url.startswith('//'):
            return 'http:' + url
        elif url.startswith('/'):
            return self.MAIN_URL + url[1:]
        return self.MAIN_URL + url

    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)

    def cryptoJS_AES_decrypt(self, encrypted, password, salt):
        printDBG("cryptoJS_AES_decrypt")

        def derive_key_and_iv(password, salt, key_length, iv_length):
            d = d_i = ''
            while len(d) < key_length + iv_length:
                d_i = md5(d_i + password + salt).digest()
                d += d_i
            return d[:key_length], d[key_length:key_length + iv_length]
        bs = 16
        key, iv = derive_key_and_iv(password, salt, 32, 16)
        cipher = AES_CBC(key=key, keySize=32)
        return cipher.decrypt(encrypted, iv)

    def decryptUrl(self, linkData, aes):
        playerUrl = ''
        if linkData:
            try:
                linkData = json_loads(base64.b64decode(linkData))
                ciphertext = base64.b64decode(linkData['ct'])
                iv = a2b_hex(linkData['iv'])
                salt = a2b_hex(linkData['s'])

                playerUrl = json_loads(self.cryptoJS_AES_decrypt(ciphertext, aes, salt))
                printDBG("player Url -->  %s " % str(playerUrl))
            except Exception:
                printExc()

        return playerUrl

    def getMarketCookie(self, url, referer, num=1):
        try:
            id = url.split('.')[-2]
        except Exception:
            printExc()
            id = '403'

        printDBG(">> id[%s]\n" % id)
        xz = str(int(time() * 1000)) + id + str(int(random.random() * 1000)) + str(2 * int(random.random() * 4)) + str(num)
        xz = base64.b64encode(xz)
        return 'MarketGidStorage=%s; ' % urllib.quote('{"0":{"svspr":"%s","svsds":%s,"TejndEEDj":"%s"},"C%s":{"page":1,"time":%s}}' % (referer, num, xz, id, int(time() * 100)))

    def refreshAdvert(self):
        if not self.needRefreshAdvert:
            return

        self.sessionEx.open(MessageBox, _('Please remember to visit http://www.sport365.live/ and watch a few advertisements.\nThis will fix problem, if your playback is constantly interrupted.'), type=MessageBox.TYPE_INFO, timeout=10)
        self.needRefreshAdvert = False

        COOKIE_FILE = GetCookieDir('sport365live2.cookie')
        params = dict(self.http_params)
        params['cookiefile'] = COOKIE_FILE
        params['header'] = dict(params['header'])

        sts, data = self.getPage(self.MAIN_URL, params)
        if not sts:
            return

        baseUrl = self.cm.meta['url']

        sessionCookie = self.cm.getCookieHeader(COOKIE_FILE)
        params['header']['Referer'] = baseUrl

        awrapperUrls = re.compile('''['"]([^"^']*?/awrapper/[^'^"]*?)["']''').findall(data)

        D = datetime.now()
        timeMarker = '{0}{1}{2}{3}'.format(D.year - 1900, D.month - 1, D.day, D.hour)
        jscUrl = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?jsc\.mgid[^'^"]*?)['"]''')[0]
        printDBG(">> [%s]" % jscUrl)
        if jscUrl.endswith('t='):
            jscUrl += timeMarker
        adUrl = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?\.adshell\.[^'^"]*?)['"]''')[0]

        sts, data = self.getPage(self.getFullUrl(adUrl), params)
        if sts:
            adUrl = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?\.adshell\.[^'^"]*?)['"]''')[0]

        sts, data = self.getPage(self.getFullUrl(jscUrl), params)
        marketCookie = self.getMarketCookie(jscUrl, baseUrl)
        params['use_cookie'] = False
        params['header']['Cookie'] = marketCookie
        sts, data = self.getPage(self.getFullUrl(adUrl), params)

        return

        for awrapperUrl in awrapperUrls:
            awrapperUrl = self.getFullUrl(awrapperUrl)
            params['header']['Referer'] = baseUrl
            params['header']['Cookie'] = sessionCookie + marketCookie
            sts, data = self.getPage(awrapperUrl, params)
            if not sts:
                continue

            adUrl = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?\.adshell\.[^'^"]*?)['"]''')[0]
            params['header']['Referer'] = awrapperUrl
            params['header']['Cookie'] = marketCookie

            sts, data = self.getPage(self.getFullUrl(adUrl), params)
            if not sts:
                continue

            jscUrl = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?jsc\.mgid[^'^"]*?)['"]''')[0]
            if jscUrl.endswith('t='):
                jscUrl += timeMarker
            if jscUrl != '':
                sts, tmp = self.getPage(self.getFullUrl(jscUrl), params)
                if sts:
                    params['header']['Cookie'] = self.getMarketCookie(jscUrl, awrapperUrl)
            adUrls = re.compile('''['"]([^'^"]*?bannerid[^'^"]*?)['"]''').findall(data)
            for adUrl in adUrls:
                adUrl = adUrl.replace('&amp;', '&')
                sts, tmp = self.getPage(self.getFullUrl(adUrl), params)

        return

    def getMainCategories(self, cItem):
        printDBG("Sport365LiveApi.getMainCategories")
        channelsTab = []
        dt = datetime.now() - datetime.utcnow()
        OFFSET = (dt.microseconds + (dt.seconds + dt.days * 24 * 3600) * 10**6) / 10**6
        OFFSET /= 60
        if OFFSET % 10 == 9:
            OFFSET += 1
        url = self.getFullUrl('en/events/-/1/-/-/%s' % (OFFSET))
        sts, data = self.getPage(self.MAIN_URL, self.http_params)
        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return []

        date = ''
        data = self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            if '/types/' not in item:
                tmp = self.cm.ph.getSearchGroups(item, '''>([0-9]{2}\.[0-9]{2}\.[0-9]{4})<''')[0]
                if tmp != '':
                    date = tmp
            else:
                if '/types/dot-green-big.png' in item:
                    title = '[live] '
                else:
                    title = ''
                title += self.cleanHtmlStr(item)
                desc = self.cm.ph.getSearchGroups(item, '''alt=['"]([^'^"]+?)['"]''')[0]
                desc = date + ' ' + self.cleanHtmlStr(desc)
                linksData = []
                tmp = self.cm.ph.getSearchGroups(item, '''onClick=[^(]*?\(([^)]+?)\)''')[0].split(',')
                for t in tmp:
                    linksData.append(t.replace('"', '').strip())
                params = dict(cItem)
                params.update({'type': 'category', 'priv_cat': 'streams_links', 'links_data': linksData, 'title': title, 'desc': desc})
                printDBG(str(params))
                channelsTab.append(params)

        return channelsTab

    def getStreamsLinks(self, cItem):
        printDBG("Sport365LiveApi.getStreamsLinks")
        channelsTab = []

        linksData = cItem.get('links_data', [])
        if len(linksData) < 4 or not linksData[0].startswith('event_'):
            return []

        eventId = linksData[0].replace('event_', '')
        url = self.getFullUrl('en/links/{0}/{1}'.format(eventId, linksData[-1]))
        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return []

        desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<table', '</table>')[1]) + '[/br]' + cItem.get('desc', '')
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<tr', '</tr>')
        for item in data:
            sourceTitle = self.cleanHtmlStr(item.split('<span')[0])
            links = self.cm.ph.getAllItemsBeetwenMarkers(item, '<span ', '</span>')
            for link in links:
                linkTitle = self.cleanHtmlStr(link)
                if '{' in linkTitle:
                    continue
                linkData = self.cm.ph.getSearchGroups(link, '''onClick=[^(]*?\(([^)]+?)\)''')[0].split(',')[0].replace('"', '').replace("'", '').strip()
                if linkData != '':
                    params = dict(cItem)
                    params.update({'type': 'video', 'link_data': linkData, 'event_id': eventId, 'desc': desc, 'title': sourceTitle + ' ' + linkTitle})
                    printDBG(str(params))
                    channelsTab.append(params)

        return channelsTab

    def getChannelsList(self, cItem):
        printDBG("Sport365LiveApi.getChannelsList")
        self.refreshAdvert()

        category = cItem.get('priv_cat', None)
        if None == category:
            return self.getMainCategories(cItem)
        elif 'streams_links' == category:
            return self.getStreamsLinks(cItem)

        return []

    def _getAesPassword(self, cItem, forceRefresh=False):
        if Sport365LiveApi.CACHE_AES_PASSWORD != '' and not forceRefresh:
            return Sport365LiveApi.CACHE_AES_PASSWORD

        sts, data = self.getPage(self.getFullUrl('en/home/' + cItem['event_id']), self.http_params)
        if not sts:
            return []

        jsData = ''
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, '<script', '</script>')
        for item in tmp:
            if 'Contact' in item:
                item = self.cm.ph.getDataBeetwenReMarkers(item, re.compile('<script[^>]+?>'), re.compile('</script>'), False)[1]
                if 'Contact' in item:
                    jsData = 'try{ %s; } catch(e){ ; }\n' % (item)
                    break

        jsData2 = ''
        aes = ''
        data = re.compile('''src=['"](http[^"^']*?/js/[0-9a-fA-F]{32}\.js[^'^"]*?)["']''').findall(data)[::-1]
        for commonUrl in data:
            sts, tmpData = self.getPage(commonUrl, self.http_params)
            if not sts:
                continue
            if tmpData.startswith(';eval('):
                try:
                    jscode = base64.b64decode('''dmFyIGRvY3VtZW50ID0ge307DQp2YXIgd2luZG93ID0gdGhpczsNCmRvY3VtZW50LndyaXRlID0gZnVuY3Rpb24oKXt9Ow0Kd2luZG93LmF0b2IgPSBmdW5jdGlvbigpe3JldHVybiAiIjt9Ow0KDQpmdW5jdGlvbiBkZWNyeXB0KCl7DQogICAgdmFyIHRleHQgPSBKU09OLnN0cmluZ2lmeSh7YWVzOmFyZ3VtZW50c1sxXX0pOw0KICAgIHByaW50KHRleHQpOw0KICAgIHJldHVybiAiIjsNCn0NCg0KdmFyIENyeXB0b0pTID0ge307DQpDcnlwdG9KUy5BRVMgPSB7fTsNCkNyeXB0b0pTLkFFUy5kZWNyeXB0ID0gZGVjcnlwdDsNCkNyeXB0b0pTLmVuYyA9IHt9Ow0KQ3J5cHRvSlMuZW5jLlV0ZjggPSAidXRmLTgiOw0K''')
                    jscode = '%s %s %s' % (jscode, tmpData, jsData)
                    ret = js_execute(jscode)
                    if ret['sts'] and 0 == ret['code']:
                        decoded = ret['data'].strip()
                        aes = json_loads(decoded)['aes']
                except Exception:
                    printExc()
                if aes != '':
                    break

        if aes != '':
            Sport365LiveApi.CACHE_AES_PASSWORD = aes
        return aes

    def getAesPassword(self, cItem, forceRefresh=False):
        if Sport365LiveApi.CACHE_AES_PASSWORD != '' and not forceRefresh:
            return Sport365LiveApi.CACHE_AES_PASSWORD

        sts, data = self.getPage(self.getFullUrl('en/home/' + cItem['event_id']), self.http_params)
        if not sts:
            return []

        aes = ''
        data = re.compile('''src=['"](http[^"^']*?/js/[0-9a-fA-F]{32}\.js[^'^"]*?)["']''').findall(data)[::-1]
        num = 0
        deObfuscatedData = ''
        aes_password = []

        for commonUrl in data:
            num += 1
            printDBG("common url n. %s : %s " % (str(num), commonUrl))

            sts, tmpData = self.getPage(commonUrl, self.http_params)
            if not sts:
                continue
            aes = ''
            try:
                while ('eval' in tmpData) and (not aes):
                    tmp = tmpData.split('eval(')
                    if len(tmp):
                        del tmp[0]
                    tmpData = ''
                    for item in tmp:
                        for decFun in [VIDEOWEED_decryptPlayerParams, VIDEOWEED_decryptPlayerParams2, SAWLIVETV_decryptPlayerParams]:
                            if not (item.startswith('function(w,i,s,e){for') and decFun == VIDEOWEED_decryptPlayerParams):
                                tmpData = unpackJSPlayerParams('eval(' + item, decFun, 0)
                                if '' != tmpData:
                                    printDBG('**********************************')
                                    printDBG(tmpData)
                                    printDBG('**********************************')
                                    break

                        aes = self.cm.ph.getSearchGroups(tmpData, 'aes_key="([^"]+?)"')[0]
                        if '' == aes:
                            aes = self.cm.ph.getSearchGroups(tmpData, 'aes\(\)\{return "([^"]+?)"')[0]

                        if aes == '':
                            funname = self.cm.ph.getSearchGroups(tmpData, 'CryptoJS\.AES\.decrypt\([^\,]+?\,([^\,]+?)\,')[0].strip()
                            if funname != '':
                                printDBG("ZZZZZZZZZZZZZ")
                                printDBG("FUN NAME: [%s]" % funname)
                                printDBG("ZZZZZZZZZZZZZ")
                                tmp = self.cm.ph.getDataBeetwenMarkers(tmpData, 'function %s' % funname, '}')[1]
                                try:
                                    aes = self.cm.ph.getSearchGroups(tmp, '"([^"]+?)"')[0].encode('utf-8')
                                except Exception:
                                    printExc()

                aes = aes.encode('utf-8')
            except Exception:
                printExc()
                aes = ''

            if aes:
                printDBG("Added password %s" % aes)
                aes_password.append(aes)

        if aes_password:
            Sport365LiveApi.CACHE_AES_PASSWORD = aes_password
        return aes_password

    def getVideoLink(self, cItem):
        printDBG("Sport365LiveApi.getVideoLink")

        if Sport365LiveApi.CACHE_AES_PASSWORD != '':
            tries = 2
        else:
            tries = 1

        urlsTab = []
        for checkIdx in range(tries):
            if checkIdx > 0:
                aes_password = self.getAesPassword(cItem, True)
            else:
                aes_password = self.getAesPassword(cItem)

            if not aes_password:
                return []

            printDBG("aes -----> %s" % str(aes_password))
            for aes in aes_password:
                try:
                    printDBG("link_data -----> " + str(cItem['link_data']))

                    playerUrl = self.decryptUrl(cItem['link_data'], aes)

                    if not playerUrl.startswith('http'):
                        continue

                    sts, data = self.getPage(playerUrl, self.http_params)
                    if not sts:
                        return []

                    links = re.compile('(http://www.[^\.]+.pw/(?!&#)[^"]+)', re.IGNORECASE + re.DOTALL + re.MULTILINE + re.UNICODE).findall(data)
                    link = [x for x in links if '&#' in x]
                    if link:
                        link = re.sub(r'&#(\d+);', lambda x: chr(int(x.group(1))), link[0])
                        printDBG("Found *.pw link ------> %s " % link)

                        h = self.http_params
                        h['header']['Referer'] = playerUrl
                        sts, data = self.getPage(link, h)

                        if sts:
                            #printDBG("*****************")
                            #printDBG(data)
                            #printDBG("*****************")

                            # search form data in page
                            action = re.compile('[\'"]action[\'"][,\s]*[\'"](http.*?)[\'"]').findall(data)

                            r = re.compile('.*?name="r"\s*value=["\']([^"\']+)["\']').findall(data)
                            d = re.compile('.*?name="d"\s*value=["\']([^"\']+)["\']').findall(data)
                            f = re.compile('.*?name="f"\s*value=["\']([^"\']+)["\']').findall(data)

                            srcs = re.compile('src=[\'"](.*?)[\'"]').findall(data)

                            if f and r and d and action:
                                postData = {'r': r[0], 'd': d[0], 'f': f[0]}
                                h['header']['Referer'] = link
                                sts, data = self.getPage(action[0], h, postData)
                                if sts:
                                    #printDBG("*****************")
                                    #printDBG(data)
                                    #printDBG("*****************")

                                    try:
                                        #######ads banners#########
                                        # simulate ads viewing
                                        bheaders = h
                                        bheaders['header']['Referer'] = action[0]
                                        banner = re.findall(r'<script\s*src=[\'"](.+?)[\'"]', data)[-1]
                                        sts, bsrc = self.getPage(banner, bheaders)
                                        banner = re.findall(r"url:'([^']+)", bsrc)[0]
                                        sts, bsrc = self.getPage(banner, bheaders)
                                        bheaders['header']['Referer'] = banner
                                        banner = re.findall(r'window.location.replace\("([^"]+)"\);\s*}\)<\/script><div', bsrc)[0]
                                        banner = urllib.quote(banner, ':/()!@#$%^&;><?')
                                        sts, bsrc = self.getPage(banner, bheaders)
                                        ###########################
                                    except BaseException:
                                        pass

                                    link2 = re.compile('\([\'"][^"\']+[\'"], [\'"][^"\']+[\'"], [\'"]([^"\']+)[\'"], 1\)').findall(data)
                                    if link2:
                                        printDBG(link2[0])
                                        playerUrl = self.decryptUrl(link2[0], aes).replace("/i", "/master.m3u8")
                                        printDBG("Final player Url ----------->  %s " % str(playerUrl))

                                        playerUrl = strwithmeta(playerUrl, {'User-Agent': h['header']['User-Agent'], 'Referer': action[0]})

                                        COOKIE_FILE_M3U8 = GetCookieDir('sport365live.cookie')
                                        params = {'cookiefile': COOKIE_FILE_M3U8, 'use_cookie': True, 'load_cookie': False, 'save_cookie': True}

                                        urlsTab.extend(getDirectM3U8Playlist(playerUrl, checkExt=False, variantCheck=True, cookieParams=params, checkContent=True, sortWithMaxBitrate=99999999))

                    else:
                        # old system
                        playerUrl = self.cm.ph.getSearchGroups(data, '''location\.replace\(\s*?['"]([^'^"]+?)['"]''', 1, True)[0]
                        if playerUrl:
                            printDBG("player Url 2 ------> %s " % playerUrl)

                        else:
                            data = self.cm.ph.getDataBeetwenMarkers(data, 'document.write(', '(')[1]
                            playerUrl = self.cleanHtmlStr(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"](http[^"^']+?)['"]''', 1, True)[0])

                        urlsTab = self.up.getVideoLinkExt(strwithmeta(playerUrl, {'aes_key': aes}))
                        if len(urlsTab):
                            break

                except Exception:
                    printExc()

        return urlsTab
