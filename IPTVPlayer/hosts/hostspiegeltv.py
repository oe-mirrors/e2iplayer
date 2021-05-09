# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import urlparse
import time
import re
import hashlib
import urllib
import random
from datetime import datetime
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


def gettytul():
    return 'http://spiegel.tv/'


class SpiegelTv(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'spiegel.tv', 'cookie': 'spiegel.tv.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'http://www.spiegel.tv/'
        self.DEFAULT_ICON_URL = 'https://images-na.ssl-images-amazon.com/images/I/31bnL4xLAkL.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Accept-Encoding': 'gzip, deflate', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.cacheLinks = {}
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.oneconfig = {'client_id': '748'}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullIconUrl(self, icon, baseUrl=None):
        return CBaseHostClass.getFullIconUrl(self, icon.replace('.webp', '.jpg'), baseUrl)

    def listMainMenu(self, cItem):
        printDBG("SpiegelTv.listMainMenu")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            data = self.cm.ph.getDataBeetwenNodes(data, ('<nav', '>', 'innerheader'), ('</nav', '>'))[1]
            data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
            if len(data) > 1:
                try:
                    cTree = self.listToDir(data[1:-1], 0)[0]
                    params = dict(cItem)
                    params['c_tree'] = cTree['list'][0]
                    params['category'] = 'list_categories'
                    self.listCategories(params, 'list_items')
                except Exception:
                    printExc()
        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}, ]

        params = dict(cItem)
        params.update({'type': 'category', 'good_for_fav': False, 'category': 'list_main_items', 'title': _('Main'), 'url': self.getMainUrl()})
        self.currList.insert(0, params)
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("SpiegelTv.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat']) #self.cm.ph.getDataBeetwenNodes(item['dat'], ('<div', '>', 'title'), ('</div', '>'))[1]
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                if 'livestreams' in url:
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url})
                        self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    params = dict(cItem)
                    params.update({'good_for_fav': False, 'c_tree': item['list'][0], 'title': title, 'url': url})
                    self.addDir(params)
        except Exception:
            printExc()

    def listMainItems(self, cItem, nextCategory):
        printDBG("SpiegelTv.listMainItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<h2', '>', 'h1'), ('<div', '>', 'cleared'))
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''', 1, True)[0])
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<div', '>', 'header-text'), ('</div', '>'))[1])
            method = self.cm.ph.getSearchGroups(item, '''data\-navigateto=['"]([^'^"]+?)['"]''')[0]
            param = self.cm.ph.getSearchGroups(item, '''data\-navigateparam=['"]([^'^"]+?)['"]''')[0]
            url = self.getFullUrl('/%s/%s' % (method, param))
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'f_method': method, 'f_param': param})
            self.addDir(params)

    def _fillOneConfig(self, cItem, data=None):
        if data == None:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return

        jscode = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<script', '>'), ('</script', '>'), False)
        for item in data:
            if '_oneconfig' in item:
                jscode.append(item)
                break
        jscode.append('print(JSON.stringify(_oneconfig));')
        ret = js_execute('\n'.join(jscode))
        if ret['sts'] and 0 == ret['code']:
            try:
                self.oneconfig.update(json_loads(ret['data'].strip(), '', True))
            except Exception:
                printExc()

    def _initiSession(self, cItem):
        try:
            deviceId = '%d:%d:%d%d' % (random.randint(1, 4), int(time.time()), random.randint(1e4, 99999), random.randint(1, 9))

            urlParams = dict(self.defaultParams)
            urlParams['header'] = dict(self.AJAX_HEADER)
            urlParams['header'].update({'Referer': cItem['url'], 'X-Request-Enable-Auth-Fallback': '1'})

            post_data = {'nxp_devh': deviceId,
                         'nxp_userh': '',
                         'precid': '0',
                         'playlicense': '0',
                         'screenx': '1920',
                         'screeny': '1080',
                         'playerversion': '6.0.00',
                         'gateway': self.oneconfig['gw'],
                         'adGateway': '',
                         'explicitlanguage': self.oneconfig['language'],
                         'addTextTemplates': '1',
                         'addDomainData': '1',
                         'addAdModel': '1',
                        }
            url = 'https://api.nexx.cloud/v3/%s/session/init' % (self.oneconfig['client_id'], )
            sts, data = self.getPage(url, urlParams, post_data)
            if not sts:
                return

            self.oneconfig['session_data'] = json_loads(data, '', True)['result']
            self.oneconfig['session_data']['device_id'] = deviceId
        except Exception:
            printExc()

    def listLiveVideos(self, cItem):
        playlistId = cItem['url'].split('/livestreams/', 1)[-1].split('-')[0]

        self._fillOneConfig(cItem)
        self._initiSession(cItem)

        if playlistId == '':
            return

        try:
            cid = self.oneconfig['session_data']['general']['cid']
            clientToken = self.oneconfig['session_data']['device']['clienttoken']
            clientId = self.oneconfig['session_data']['general']['clid']
            deviceId = self.oneconfig['session_data']['device_id']

            secret = clientToken[int(deviceId[0]):]
            secret = secret[0:len(secret) - int(deviceId[-1])]
            op = 'byid'
            requestToken = hashlib.md5(''.join((op, clientId, secret))).hexdigest()

            urlParams = dict(self.defaultParams)
            urlParams['header'] = dict(self.AJAX_HEADER)
            urlParams['header'].update({'Referer': cItem['url'], 'X-Request-Enable-Auth-Fallback': '1', 'X-Request-CID': cid, 'X-Request-Token': requestToken})
            post_data = {'additionalfields': 'language,channel,actors,studio,licenseby,slug,fileversion,subtitle,teaser,description,releasedate',
                         'addInteractionOptions': '1',
                         'addStatusDetails': '1',
                         'addStreamDetails': '1',
                         'addFeatures': '1',
                         'addCaptions': '1',
                         'addScenes': '1',
                         'addHotSpots': '1',
                         'addBumpers': '1',
                         'captionFormat': 'data',
                         'addItemData': '1', }

            url = 'https://api.nexx.cloud/v3/%s/playlists/%s/%s' % (self.oneconfig['client_id'], op, playlistId)
            sts, data = self.getPage(url, urlParams, post_data)
            data = json_loads(data)
            for item in data['result']['itemdata']:
                icon = item['imagedata']['thumb']
                url = self.getFullUrl('/videos/%s-%s' % (item['general']['ID'], item['general']['slug']))
                title = self.cleanHtmlStr(item['general']['title'])
                # item['general']['year']
                date = datetime.fromtimestamp(int(item['general']['releasedate'])).strftime('%d.%m.%Y')
                desc = ['%s | %s | %s' % (item['general']['runtime'], item['general']['studio'], date)]
                desc.append(self.cleanHtmlStr(item['general']['subtitle']))
                desc.append(self.cleanHtmlStr(item['general']['teaser']))
                desc.append(self.cleanHtmlStr(item['general']['description']))
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                self.addVideo(params)
        except Exception:
            printExc()

    def listItems(self, cItem):
        printDBG("SpiegelTv.listItems [%s]" % cItem)

        if '/videos/' in cItem.get('url', ''):
            sts, data = self.getPage(cItem['url'])
            if sts and 'playerholder' in data:
                data = self.cm.ph.getDataBeetwenNodes(data, ('<section', '>', 'innercontent'), ('<span', '>', 'vtiledetails'))[1]
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h1', '</h1>')[1])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(data, '''<img[^>]*?\ssrc=['"]([^'^"]+?)['"]''', 1, True)[0])
                if icon:
                    desc = []
                    tmp = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, '<h2', '</h2>')[1])
                    if tmp:
                        desc.append(tmp)

                    tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'vreddesc'), ('</div', '>'), False)
                    for t in tmp:
                        t = self.cleanHtmlStr(t)
                        if t:
                            desc.append(t)

                    self.addVideo(MergeDicts(cItem, {'title': title, 'icon': icon, 'desc': '[/br]'.join(desc)}))
                    return

        page = cItem.get('page', 0)
        if page == 0:
            if cItem.get('url', '').endswith('-livestream'):
                self.listLiveVideos(cItem)
            self._fillOneConfig(cItem)
            urlPath = urlparse.urlparse(cItem['url']).path[1:].split('/')
            method = cItem.get('f_method', urlPath[0])
            param = cItem.get('f_param', urlPath[-1])
            start = 0
        else:
            method = cItem.get('f_method', '')
            param = cItem.get('f_param', '')
            start = cItem.get('f_start', page * 20)

        try:
            url = self.getFullUrl('/gateway/service.php')
            post_data = {'cid': self.oneconfig['cid'], 'client': self.oneconfig['client_id'], 'method': method, 'param': param, 'start': start, 'cgw': self.oneconfig['gw'], 'isu': '0', 'uhs': '0', 'agc': '0', 'wbp': '0', 'cdlang': self.oneconfig['language']}
            sts, data = self.getPage(url, post_data=post_data)
            if not sts:
                return
            data = json_loads(data)['contents']
            printDBG(data)
            nextPageParams = []
            tmp = self.cm.ph.getDataBeetwenMarkers(data, 'navigatemore(', ')', False)[1].split(',')
            for item in tmp:
                nextPageParams.append(item.strip()[1:-1])

            data = self.cm.ph.getAllItemsBeetwenMarkers(data.split('</h1>', 1)[-1], '<a', '</a>')
            for item in data:
                url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''\shref=['"]([^'^"]+?)['"]''', 1, True)[0])
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''\ssrc=['"]([^'^"]+?)['"]''', 1, True)[0])
                title = ''
                desc = []
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(item, '<div', '</div>')
                for it in tmp:
                    t = self.cleanHtmlStr(it)
                    if t == '':
                        continue
                    if 'cardtitle' in it:
                        title = t
                    if 'tholderbottom' in it:
                        desc.insert(0, t)
                    else:
                        desc.append(t)
                params = {'good_for_fav': True, 'category': cItem['category'], 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if '/videos/' in url:
                    self.addVideo(params)
                else:
                    self.addDir(params)

            if 3 == len(nextPageParams):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _("Next page"), 'page': page + 1, 'f_method': nextPageParams[0], 'f_param': nextPageParams[1], 'f_start': nextPageParams[2]})
                self.addDir(params)
        except Exception:
            printExc()

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("SpiegelTv.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search/') + urllib.quote_plus(searchPattern)
        cItem['category'] = 'list_items'
        cItem['f_method'] = 'search'
        cItem['f_param'] = searchPattern
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("SpiegelTv.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}
        retTab = []

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        self._fillOneConfig(cItem, data)
        self._initiSession(cItem)

        videoId = self.cm.ph.getDataBeetwenMarkers(data, 'video.start(', ')', False)[1].split(',')[0].strip()
        if videoId == '':
            videoId = cItem['url'].split('/videos/', 1)[-1].split('-')[0]

        try:
            cid = self.oneconfig['session_data']['general']['cid']
            clientToken = self.oneconfig['session_data']['device']['clienttoken']
            clientId = self.oneconfig['session_data']['general']['clid']
            deviceId = self.oneconfig['session_data']['device_id']

            secret = clientToken[int(deviceId[0]):]
            secret = secret[0:len(secret) - int(deviceId[-1])]
            op = 'byid'
            requestToken = hashlib.md5(''.join((op, clientId, secret))).hexdigest()

            urlParams = dict(self.defaultParams)
            urlParams['header'] = dict(self.AJAX_HEADER)
            urlParams['header'].update({'Referer': cItem['url'], 'X-Request-Enable-Auth-Fallback': '1', 'X-Request-CID': cid, 'X-Request-Token': requestToken})
            post_data = {'additionalfields': 'language,channel,actors,studio,licenseby,slug,subtitle,teaser,description',
                         'addInteractionOptions': '1',
                         'addStatusDetails': '1',
                         'addStreamDetails': '1',
                         'addCaptions': '1',
                         'addScenes': '1',
                         'addHotSpots': '1',
                         'addBumpers': '1',
                         'captionFormat': 'data', }

            url = 'https://api.nexx.cloud/v3/%s/videos/%s/%s' % (clientId, op, videoId)
            sts, data = self.getPage(url, urlParams, post_data)
            if not sts:
                return

            data = json_loads(data, '', True)['result']
            try:
                protectionToken = data['protectiondata']['token']
            except Exception:
                protectionToken = None
            language = data['general'].get('language_raw') or ''
            printDBG(data)

            cdn = data['streamdata']['cdnType']

            if cdn == 'azure':
                data = data['streamdata']
                azureLocator = data['azureLocator']
                AZURE_URL = 'http://nx%s%02d.akamaized.net/'

                def getCdnShieldBase(shieldType='', prefix='-p'):
                    for secure in ('', 's'):
                        cdnShield = data.get('cdnShield%sHTTP%s' % (shieldType, secure.upper()))
                        if cdnShield:
                            return 'http%s://%s' % (secure, cdnShield)
                    else:
                        return AZURE_URL % (prefix, int(data['azureAccount'].replace('nexxplayplus', '')))
                azureStreamBase = getCdnShieldBase()
                isML = ',' in language
                azureManifestUrl = '%s%s/%s_src%s.ism/Manifest' % (azureStreamBase, azureLocator, videoId, ('_manifest' if isML else '')) + '%s'

                if protectionToken:
                    azureManifestUrl += '?hdnts=%s' % protectionToken

                try:
                    azureProgressiveBase = getCdnShieldBase('Prog', '-d')
                    azureFileDistribution = data.get('azureFileDistribution')
                    if azureFileDistribution:
                        fds = azureFileDistribution.split(',')
                        if fds:
                            for fd in fds:
                                ss = fd.split(':')
                                if len(ss) != 2:
                                    continue
                                tbr = int(ss[0] or 0)
                                if not tbr:
                                    continue
                                retTab.append({'name': '[%s] %s' % (tbr, ss[1]), 'tbr': tbr, 'url': '%s%s/%s_src_%s_%d.mp4' % (azureProgressiveBase, azureLocator, videoId, ss[1], tbr)})
                except Exception:
                    printExc()
                retTab.sort(key=lambda item: item['tbr'], reverse=True)
                if len(retTab) == 0:
                    retTab = getMPDLinksWithMeta(azureManifestUrl % '(format=mpd-time-csf)', checkExt=False, sortWithMaxBandwidth=999999999)
                if len(retTab) == 0:
                    retTab = getDirectM3U8Playlist(azureManifestUrl % '(format=m3u8-aapl)', checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            else:
                streamData = data['streamdata']
                hash = data['general']['hash']

                ps = streamData['originalDomain']
                if streamData['applyFolderHierarchy'] == '1':
                    s = ('%04d' % int(videoId))[::-1]
                    ps += '/%s/%s' % (s[0:2], s[2:4])
                ps += '/%s/%s_' % (videoId, hash)
                t = 'http://%s' + ps
                azureFileDistribution = streamData['azureFileDistribution'].split(',')
                cdnProvider = streamData['cdnProvider']

                def p0(p):
                    return '_%s' % p if streamData['applyAzureStructure'] == '1' else ''

                formats = []
                if cdnProvider == 'ak':
                    t += ','
                    for i in azureFileDistribution:
                        p = i.split(':')
                        t += p[1] + p0(int(p[0])) + ','
                    t += '.mp4.csmil/master.%s'
                elif cdnProvider == 'ce':
                    k = t.split('/')
                    h = k.pop()
                    httpBase = t = '/'.join(k)
                    httpBase = httpBase % streamData['cdnPathHTTP']
                    t += '/asset.ism/manifest.%s?dcp_ver=aos4&videostream='
                    for i in azureFileDistribution:
                        p = i.split(':')
                        tbr = int(p[0])
                        filename = '%s%s%s.mp4' % (h, p[1], p0(tbr))
                        retTab.append({'name': '[%s] %s' % (tbr, p[1]), 'tbr': tbr, 'url': httpBase + '/' + filename})
                        a = filename + ':%s' % (tbr * 1000)
                        t += a + ','
                    t = t[:-1] + '&audiostream=' + a.split(':')[0]
                else:
                    printDBG("Unknwon cdnProvider [%s]" % cdnProvider)
                    assert False

                retTab.sort(key=lambda item: item['tbr'], reverse=True)
                if len(retTab) == 0:
                    retTab.extend(getMPDLinksWithMeta(t % (streamData['cdnPathDASH'], 'mpd'), checkExt=False, sortWithMaxBandwidth=999999999))
                if len(retTab) == 0:
                    retTab.extend(getDirectM3U8Playlist(t % (streamData['cdnPathHLS'], 'm3u8'), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))

        except Exception:
            printExc()

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        for idx in range(len(retTab)):
            retTab[idx]['need_resolve'] = 1
        return retTab

    def getVideoLinks(self, baseUrl):
        printDBG("SpiegelTv.getVideoLinks [%s]" % baseUrl)
        videoUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return [{'name': 'sel', 'url': videoUrl}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'list_main_items':
            self.listMainItems(self.currItem, 'list_items')
        elif category == 'list_categories':
            self.listCategories(self.currItem, 'list_items')
        elif category == 'list_items':
            self.listItems(self.currItem)
    #SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, SpiegelTv(), True, [])
