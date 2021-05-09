# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, GetCookieDir, GetPyScriptCmd, MergeDicts, GetDukPath, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import duktape_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigInteger, getConfigListEntry
import base64
import re
from binascii import hexlify
from hashlib import md5
############################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.bilasportpw_port = ConfigInteger(8193, (1024, 65535))


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_('PORT') + ": ", config.plugins.iptvplayer.bilasportpw_port))
    return optionList

###################################################


class BilaSportPwApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://bilasport.net/'
        self.DEFAULT_ICON_URL = 'https://projects.fivethirtyeight.com/2016-mlb-predictions/images/logos.png'
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})
        self.COOKIE_FILE = GetCookieDir('bilasport.pw.cookie')
        self.defaultParams = {'header': self.HTTP_HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, baseUrl, params={}, post_data=None):
        if params == {}:
            params = dict(self.defaultParams)
        params['cloudflare_params'] = {'cookie_file': self.COOKIE_FILE, 'User-Agent': self.HTTP_HEADER['User-Agent']}
        return self.cm.getPageCFProtection(baseUrl, params, post_data)

    def getFullIconUrl(self, url, currUrl=None):
        url = CBaseHostClass.getFullIconUrl(self, url.strip(), currUrl)
        if url == '':
            return ''
        cookieHeader = self.cm.getCookieHeader(self.COOKIE_FILE, ['PHPSESSID', 'cf_clearance'])
        return strwithmeta(url, {'Cookie': cookieHeader, 'User-Agent': self.HTTP_HEADER['User-Agent']})

    def getList(self, cItem):
        printDBG("BilaSportPwApi.getChannelsList")
        mainItemsTab = []

        sts, data = self.getPage(self.getFullUrl('/schedule.html'))
        if not sts:
            return mainItemsTab
        cUrl = self.cm.meta['url']

        data = ph.find(data, ('<table', '>'), '</table>', flags=0)[1]
        data = ph.findall(data, ('<tr', '>'), '</tr>')
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A)[1], cUrl)
            icon = self.getFullIconUrl(ph.search(item, ph.IMG)[1], cUrl)
            item = item.split('</td>', 1)
            title = ph.clean_html(item[0])
            start = ph.getattr(item[-1], 'data-gamestart')
            end = ph.getattr(item[-1], 'data-gameends')
            if start and end:
                title = '[%s - %s] %s' % (start, end, title)
            desc = ph.clean_html(item[-1].split('</div>', 1)[-1])
            mainItemsTab.append(MergeDicts(cItem, {'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': desc}))
        return mainItemsTab

    def getVideoLink(self, cItem):
        printDBG("BilaSportPwApi.getVideoLink")
        urlsTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']
        baseUrl = cUrl

        url = self.getFullUrl(ph.search(data, '''['"]([^'^"]*?/iframes/[^'^"]+?)['"]''')[0], cUrl)
        if not url:
            return urlsTab
        sts, data = self.getPage(url)
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']

        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1], cUrl)
        if url:
            sts, data = self.getPage(url)
            if not sts:
                return urlsTab
            cUrl = self.cm.meta['url']

        replaceTab = self.cm.ph.getDataBeetwenMarkers(data, 'prototype.open', '};', False)[1]
        printDBG(replaceTab)
        replaceTab = re.compile('''\.replace\(['"](\s*[^'^"]+?)['"]\s*\,\s*['"]([^'^"]+?)['"]''').findall(replaceTab)
        printDBG(replaceTab)
        if len(replaceTab):
            scriptUrl = '|' + base64.b64encode(json_dumps(replaceTab).encode('utf-8'))
        else:
            scriptUrl = ''
            tmp = ph.findall(data, ('<script', '>', ph.check(ph.none, ('jsdelivr',))))
            for item in tmp:
                scriptUrl = self.getFullUrl(ph.getattr(item, 'src'), cUrl)
                break

        hlsTab = []
        hlsUrl = re.compile('''(https?://[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]''', re.IGNORECASE).findall(data)
        if len(hlsUrl):
            hlsUrl = hlsUrl[-1]
            hlsTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=9000000)
            for idx in range(len(hlsTab)):
                hlsTab[idx]['need_resolve'] = 1
                hlsTab[idx]['url'] = strwithmeta(hlsTab[idx]['url'], {'name': cItem['name'], 'Referer': url, 'priv_script_url': scriptUrl})

        if hlsTab:
            return hlsTab

        if 1 == self.up.checkHostSupport(cUrl):
            return self.up.getVideoLinkExt(strwithmeta(cUrl, {'Referer': baseUrl}))

        return []

    def getResolvedVideoLink(self, videoUrl):
        printDBG("BilaSportPwApi.getResolvedVideoLink [%s]" % videoUrl)
        urlsTab = []

        meta = strwithmeta(videoUrl).meta

        baseUrl = self.cm.getBaseUrl(videoUrl.meta.get('Referer', ''))
        scriptUrl = videoUrl.meta.get('priv_script_url', '')
        if scriptUrl:
            sts, data = self.getPage(scriptUrl)
            if not sts:
                return []
            hash = '/tmp/%s' % hexlify(md5(data).digest())
            data = 'btoa=function(t){return Duktape.enc("base64",t)},XMLHttpRequest=function(){},XMLHttpRequest.prototype.open=function(t,e,n,o,p){print(e)};' + data + 'tmp = new XMLHttpRequest();'
            try:
                with open(hash + '.js', 'w') as f:
                    f.write(data)
            except Exception:
                printExc()
                return []
            duktape_execute('-c "%s.byte" "%s.js" ' % (hash, hash))
            rm(hash + '.js')
            scriptUrl = hash

        sts, data = self.getPage(videoUrl)
        if not sts or '#EXTM3U' not in data:
            return urlsTab

        keyUrl = set(re.compile('''#EXT\-X\-KEY.*?URI=['"](https?://[^"]+?)['"]''').findall(data))
        if len(keyUrl):
            keyUrl = keyUrl.pop()
            proto = keyUrl.split('://', 1)[0]
            pyCmd = GetPyScriptCmd('livesports') + ' "%s" "%s" "%s" "%s" "%s" "%s" "%s" ' % (config.plugins.iptvplayer.bilasportpw_port.value, videoUrl, baseUrl, scriptUrl, self.HTTP_HEADER['User-Agent'], self.COOKIE_FILE, GetDukPath())
            meta = {'iptv_proto': 'em3u8'}
            meta['iptv_m3u8_key_uri_replace_old'] = '%s://' % proto
            meta['iptv_m3u8_key_uri_replace_new'] = 'http://127.0.0.1:{0}/{1}/'.format(config.plugins.iptvplayer.bilasportpw_port.value, proto)
            meta['iptv_refresh_cmd'] = pyCmd
            videoUrl = urlparser.decorateUrl("ext://url/" + videoUrl, meta)
        else:
            videoUrl = urlparser.decorateUrl(videoUrl, meta)
        return [{'name': 'direct', 'url': videoUrl}]
