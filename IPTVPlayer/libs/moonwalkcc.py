# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getF4MLinksWithMeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import base64
import copy
import urllib
from binascii import unhexlify
from urlparse import urlparse, parse_qsl
from Components.config import config, ConfigSelection, ConfigYesNo
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.moonwalk_format = ConfigSelection(default="m3u8", choices=[("hls/m3u8", "m3u8"), ("f4m", "f4m/hds")])
config.plugins.iptvplayer.moonwalk_df_format = ConfigSelection(default=9999, choices=[(0, _("the worst")), (360, "360p"), (480, "480p"), (720, "720"), (9999, _("the best"))])
config.plugins.iptvplayer.moonwalk_use_df = ConfigYesNo(default=False)


class MoonwalkParser():
    USER_AGENT = 'Mozilla/5.0'

    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'Referer': ''}
        self.COOKIEFILE = GetCookieDir("moonwalkcc.cookie")
        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'save_cookie': True, 'load_cookie': False, 'cookiefile': self.COOKIEFILE}
        self.baseUrl = ''

    def _setBaseUrl(self, url):
        self.baseUrl = 'http://' + self.cm.ph.getDataBeetwenMarkers(url, '://', '/', False)[1]

    def cryptoJS_AES_decrypt(self, encrypted, key, iv):
        cipher = AES_CBC(key=key, keySize=32)
        return cipher.decrypt(encrypted, iv)

    def cryptoJS_AES_encrypt(self, decrypted, key, iv):
        cipher = AES_CBC(key=key, keySize=32)
        return cipher.encrypt(decrypted, iv)

    def _getFunctionCode(self, data):
        funData = ''
        start = data.find('function(')
        idx = data.find('{', start) + 1
        num = 1
        while idx < len(data):
            if data[idx] == '{':
                num += 1
            elif data[idx] == '}':
                num -= 1
            if num == 0:
                funData = data[start:idx + 1]
                break
            idx += 1
        return funData

    def _getSecurityData(self, data, params):
        printDBG('MoonwalkParser._getSecurityData')
        baseUrl = ''
        sec_header = {'Referer': data.meta['url']}
        post_data = {}

        scriptUrl = self.cm.ph.getSearchGroups(data, '''<script[^>]+?src=['"]([^'^"]+?)['"]''')[0]
        if scriptUrl.startswith('/'):
            scriptUrl = self.baseUrl + scriptUrl

        jscode = ['var iptv={onGetManifestSuccess:"",onGetManifestError:""},_={bind:function(){}},window=this;window._mw_adb=false,CryptoJS={AES:{},enc:{Utf8:{},Hex:{}}},CryptoJS.AES.encrypt=function(n,t,r){return JSON.stringify({data:n,password:t,salt:r})},CryptoJS.enc.Hex.parse=function(n){return{data:n,type:"hex"}},CryptoJS.enc.Utf8.parse=function(n){return{data:n,type:"utf-8"}};var $={ajax:function(n){return print(JSON.stringify(n)),{done:function(){},fail:function(){}}}},VideoBalancer=function(n){iptv.options=n};']
        jscode.append('var navigator={userAgent:"%s"};' % self.HTTP_HEADER['User-Agent'])
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
        for item in data:
            jscode.append(item)

        sts, data = self.cm.getPage(scriptUrl, params)
        if sts:
            jscode.insert(0, '''window=this;var document={};function setTimeout(e,t){}window.document=document,location={},Object.defineProperty(location,"href",{get:function(){return""},set:function(e){}}),window.location=location,document.on=function(){return document},document.constructor=document.on,document.ready=document.on,document.off=document.on,document.bind=document.on;var element=function(e){this.getElementsByTagName=function(){return elem=new element(""),[elem]},this.attributes={},this.expando=function(){return new element("")},this.firstChild={nodeType:3},this.cloneNode=function(){return new element("")},this.appendChild=function(){return new element("")},this.lastChild=function(){return new element("")},this.setAttribute=function(){this.attributes[arguments[0]]={expando:1}},this.getAttribute=function(){return new element("")},Object.defineProperty(this,"style",{get:function(){return{display:"",animation:""}},set:function(e){}})};document.documentElement=new element(""),document.nodeType=9,document.body=document,document.createDocumentFragment=function(){return new element("")},document.getElementById=function(e){return new element(e)},document.createElement=document.getElementById,document.getElementsByTagName=document.getElementById;\n''')
            #jscode.insert(1, data)
            try:
                endIdx = data.rfind('}')
                idx = endIdx
                num = 1
                while num > 0:
                    idx -= 1
                    if data[idx] == '{':
                        num -= 1
                    elif data[idx] == '}':
                        num += 1
                tabVars = []
                cData = self.cm.ph.getSearchGroups(data[endIdx:], '''\(([^\)]+?)\)''')[0].split(',')
                vData = self.cm.ph.getSearchGroups(data[:idx].rsplit('function', 1)[-1], '''\(([^\)]+?)\)''')[0].split(',')
                for idx in range(len(cData)):
                    tabVars.append('%s=%s;' % (vData[idx].strip(), cData[idx].strip()))
                jscode.append('\n'.join(tabVars))
            except Exception:
                printExc()
            item = "iptv.call = %s;iptv['call']();" % self._getFunctionCode(data.split('getVideoManifests:', 1)[-1]).replace('while(true)', 'while(false)').replace('while (true)', 'while(false)').replace('"gger"', '"zgger"')
            jscode.append(item)

        jscode = '\n'.join(jscode)
        printDBG('Code start:')
        printDBG(jscode)
        printDBG('Code end:')
        ret = js_execute(jscode, {'timeout_sec': 30})
        if ret['sts'] and 0 == ret['code']:
            printDBG(ret['data'])
            try:
                data = json_loads(ret['data'])
                baseUrl = data['url']
                if baseUrl.startswith('/'):
                    baseUrl = self.baseUrl + baseUrl

                for itemKey in data['data'].keys():
                    try:
                        tmp = json_loads(data['data'][itemKey])
                        decrypted = tmp['data']['data']
                        key = tmp['password']['data']
                        iv = tmp['salt']['iv']['data']
                        printDBG('>>>> key: [%s]' % key)
                        printDBG('>>>> iv: [%s]' % iv)
                        if tmp['password']['type'] == 'hex':
                            key = unhexlify(key)
                        if tmp['salt']['iv']['type'] == 'hex':
                            iv = unhexlify(iv)
                        post_data[itemKey] = base64.b64encode(self.cryptoJS_AES_encrypt(decrypted, key, iv)) #.replace('+', ' ')
                    except Exception:
                        post_data[itemKey] = data['data'][itemKey]
            except Exception:
                printExc()

        return baseUrl, sec_header, post_data

    def getDirectLinks(self, url):
        printDBG('MoonwalkParser.getDirectLinks')
        linksTab = []
        try:
            self._setBaseUrl(url)
            params = copy.deepcopy(self.defaultParams)
            params['header']['Referer'] = url
            sts, data = self.cm.getPage(url, params)
            if not sts:
                return []

            url, sec_header, post_data = self._getSecurityData(data, params)
            params['header'].update(sec_header)
            params['header']['X-Requested-With'] = 'XMLHttpRequest'
            params['load_cookie'] = True
            if not self.cm.isValidUrl(url):
                url = self.baseUrl + url
            sts, data = self.cm.getPage(url, params, post_data)
            printDBG("=======================================================")
            printDBG(data)
            printDBG("=======================================================")
            if not sts:
                return []

            try:
                data = json_loads(data)
                data = data['mans']
            except Exception:
                printExc()
            try:
                mp4Url = strwithmeta(data["mp4"], {'User-Agent': 'Mozilla/5.0', 'Referer': url})
                sts, tmp = self.cm.getPage(mp4Url, {'User-Agent': 'Mozilla/5.0', 'Referer': url})
                tmpTab = []
                tmp = json_loads(tmp)
                printDBG(tmp)
                for key in tmp:
                    mp4Url = tmp[key]
                    if mp4Url.split('?')[0].endswith('.mp4'):
                        tmpTab.append({'url': mp4Url, 'heigth': key})

                def __getLinkQuality(itemLink):
                    return int(itemLink['heigth'])

                maxRes = config.plugins.iptvplayer.moonwalk_df_format.value
                tmpTab = CSelOneLink(tmpTab, __getLinkQuality, maxRes).getSortedLinks()
                if config.plugins.iptvplayer.moonwalk_use_df.value:
                    tmpTab = [tmpTab[0]]
                for item in tmpTab:
                    linksTab.append({'name': '[mp4] %sp' % __getLinkQuality(item), 'url': item['url']})
            except Exception:
                printExc()

            if 'm3u8' == config.plugins.iptvplayer.moonwalk_format.value:
                hlsUrl = strwithmeta(data['m3u8'], {'User-Agent': 'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10', 'Referer': url})
                tmpTab = getDirectM3U8Playlist(hlsUrl)

                def __getLinkQuality(itemLink):
                    return int(itemLink['heigth'])
                maxRes = config.plugins.iptvplayer.moonwalk_df_format.value
                tmpTab = CSelOneLink(tmpTab, __getLinkQuality, maxRes).getSortedLinks()
                if config.plugins.iptvplayer.moonwalk_use_df.value:
                    tmpTab = [tmpTab[0]]
                for item in tmpTab:
                    linksTab.append({'name': '[hls/m3u8] %sp' % __getLinkQuality(item), 'url': item['url']})
            else:
                tmpTab = getF4MLinksWithMeta(data["manifest_f4m"])

                def __getLinkQuality(itemLink):
                    printDBG(itemLink)
                    bitrate = int(self.cm.ph.getDataBeetwenMarkers(itemLink['name'], 'bitrate[', ']', False)[1])
                    if bitrate < 400:
                        return 360
                    elif bitrate < 700:
                        return 480
                    elif bitrate < 1200:
                        return 720
                    return 1080
                maxRes = config.plugins.iptvplayer.moonwalk_df_format.value
                tmpTab = CSelOneLink(tmpTab, __getLinkQuality, maxRes).getSortedLinks()
                if config.plugins.iptvplayer.moonwalk_use_df.value:
                    tmpTab = [tmpTab[0]]
                for item in tmpTab:
                    linksTab.append({'name': '[f4m/hds] %sp' % __getLinkQuality(item), 'url': item['url']})
        except Exception:
            printExc()
        return linksTab

    def getSeasonsList(self, url):
        printDBG('MoonwalkParser.getSeasonsList')
        seasonsTab = []
        try:
            self._setBaseUrl(url)
            params = copy.deepcopy(self.defaultParams)
            params['header']['Referer'] = url
            params['with_metadata'] = True
            sts, data = self.cm.getPage(url, params)
            if not sts:
                return []

            url = data.meta['url']
            parsedUri = urlparse(url)
            baseUrl = '{uri.scheme}://{uri.netloc}{uri.path}'.format(uri=parsedUri)
            query = dict(parse_qsl(parsedUri.query))

            printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            printDBG(data)
            printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

            seasonData = self.cm.ph.getSearchGroups(data, '''seasons\s*:\s*\[([^\]]+?)\]''')[0]
            ref = self.cm.ph.getSearchGroups(data, '''ref\s*:[^'^"]*?['"]([^'^"]+?)['"]''')[0]
            if 'ref' != '':
                query['ref'] = ref
            query.pop('episode', None)

            printDBG(seasonData)

            seasonData = seasonData.split(',')
            for item in seasonData:
                item = item.strip()
                if item[0] in ['"', "'"]:
                    item = item[1:-1]
                query['season'] = item
                seasonsTab.append({'title': _('Season') + ' ' + item, 'id': int(item), 'url': '%s?%s' % (baseUrl, urllib.urlencode(query))})
            seasonsTab.sort(key=lambda item: item['id'])
        except Exception:
            printExc()
        return seasonsTab

    def getEpiodesList(self, url, seasonIdx):
        printDBG('MoonwalkParser.getEpiodesList')
        episodesTab = []
        try:
            self._setBaseUrl(url)
            params = copy.deepcopy(self.defaultParams)
            params['header']['Referer'] = url
            params['with_metadata'] = True
            sts, data = self.cm.getPage(url, params)
            if not sts:
                return []

            url = data.meta['url']
            parsedUri = urlparse(url)
            baseUrl = '{uri.scheme}://{uri.netloc}{uri.path}'.format(uri=parsedUri)
            query = dict(parse_qsl(parsedUri.query))

            printDBG("+++")
            printDBG(data)
            printDBG("+++")

            episodeData = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('''episodes\s*:'''), re.compile(']]'))[1]
            if episodeData != '':
                episodeData = re.compile('''\[\s*[0-9]+?\s*\,\s*([0-9]+?)[^0-9]''').findall(episodeData)
                for item in episodeData:
                    item = item.strip()
                    query['episode'] = item
                    url = '%s?%s' % (baseUrl, urllib.urlencode(query))

                    episodesTab.append({'title': _('Episode') + ' ' + item, 'id': int(item), 'url': strwithmeta(url, {'host_name': 'moonwalk.cc'})})

            else:
                episodeData = self.cm.ph.getSearchGroups(data, '''episodes\s*:\s*\[([^\]]+?)\]''')[0]
                episodeData = episodeData.split(',')
                for item in episodeData:
                    item = item.strip()
                    if item[0] in ['"', "'"]:
                        item = item[1:-1]
                    query['episode'] = item
                    url = '%s?%s' % (baseUrl, urllib.urlencode(query))
                    episodesTab.append({'title': _('Episode') + ' ' + item, 'id': int(item), 'url': strwithmeta(url, {'host_name': 'moonwalk.cc'})})
            episodesTab.sort(key=lambda item: item['id'])
        except Exception:
            printExc()
        return episodesTab
