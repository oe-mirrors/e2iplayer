# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, byteify, rm, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if not isPY2():
    basestring = str
###################################################
# FOREIGN import
###################################################
import re
import random
from datetime import datetime, timedelta
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigText, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.rtbfbe_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.rtbfbe_password = ConfigText(default="", fixed_size=False)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("e-mail") + ":", config.plugins.iptvplayer.rtbfbe_login))
    optionList.append(getConfigListEntry(_("password") + ":", config.plugins.iptvplayer.rtbfbe_password))
    return optionList
###################################################


def gettytul():
    return 'https://www.rtbf.be/'


class RTBFBE(CBaseHostClass):
    CHECK_GEO_LOCK = True

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'rtbf.be', 'cookie': 'rtbf.be.cookie'})
        self.USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        self.MAIN_URL = 'https://www.rtbf.be/'
        self.DEFAULT_ICON_URL = 'https://www.mediaspecs.be/wp-content/uploads/RTBF_Auvio.png'
        self.HTTP_HEADER = {'User-Agent': self.USER_AGENT, 'DNT': '1', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate', 'Referer': self.getMainUrl(), 'Origin': self.getMainUrl()}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': 'application/json, text/javascript, */*; q=0.01'})

        self.defaultParams = {'header': self.HTTP_HEADER, 'with_metadata': True, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.login = ''
        self.password = ''
        self.loggedIn = None
        self.loginMessage = ''
        self.userGeoLoc = ''

        self.cacheChannels = []

        self.OFFSET = datetime.now() - datetime.utcnow()
        seconds = self.OFFSET.seconds + self.OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0:
            seconds += 1
        elif ((seconds - 1) % 10) == 0:
            seconds -= 1
        self.OFFSET = timedelta(seconds=seconds)

        self.partnerKey = ''
        self.partnerToken = ''
        self.dataKey = ''
        self.csrfToken = ''
        self.loginData = {}

    def setMainUrl(self, url):
        if self.cm.isValidUrl(url):
            self.MAIN_URL = self.cm.getBaseUrl(url)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem, nextCategory):
        printDBG("RTBFBE.listMainMenu")

        CAT_TAB = [{'category': 'sections', 'title': _('Main'), 'url': self.getFullUrl('/auvio/')},
                   {'category': 'live_categories', 'title': 'En Direct', 'url': self.getFullUrl('/auvio/direct')},
                   {'category': 'channels', 'title': 'Chaînes', 'url': self.getFullUrl('/news/api/menu?site=media')},
                   {'category': 'sections', 'title': 'Émissions', 'url': self.getFullUrl('/auvio/emissions')},
                   {'category': 'categories', 'title': 'Catégories', 'url': self.getFullUrl('/news/api/menu?site=media')},
                   {'category': 'search', 'title': _('Search'), 'search_item': True},
                   {'category': 'search_history', 'title': _('Search history')}, ]

        params = dict(cItem)
        params['desc'] = self.loginMessage
        self.listsTab(CAT_TAB, params)

    def getPartnerKey(self, data=None):
        if '' in [self.csrfToken, self.partnerKey]:
            if data == None:
                sts, data = self.getPage(self.getMainUrl())
                if not sts:
                    return ''
            tmp = re.compile('''<script[^>]+?src=['"]([^'^"]+?_ssl\.js)['"]''').findall(data)
            data = ''
            for item in tmp:
                sts, item = self.getPage(self.getFullUrl(item))
                if sts:
                    data += item
            self.partnerKey = self.cm.ph.getSearchGroups(data, '''partner_key\s*?:\s*?['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
            self.csrfToken = self.cm.ph.getSearchGroups(data, '''['"]?X-CSRF-Token['"]?\s*?:\s*?['"]([^'^"]+?)['"]''', ignoreCase=True)[0]
        return self.partnerKey

    def getPartnerToken(self):
        if self.partnerToken == '':
            url = 'https://www.rtbf.be/api/partner/generic/live/planninglist?target_site=media&origin_site=media&category_id=0&start_date&offset=0&limit=1&partner_key=' + self.getPartnerKey()
            sts, data = self.getPage(url)
            if not sts:
                return ''
            self.partnerToken = self.cm.ph.getSearchGroups(data, '''\.m3u8\?token=([0-9A-Za-z]+?)[^0-9^A-Z^a-z]''')[0]
        return self.partnerToken

    def listLiveCategories(self, cItem, nextCategory):
        printDBG("RTBFBE.listLiveCategories")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        partnerKey = self.getPartnerKey(data)

        data = self.cm.ph.getDataBeetwenMarkers(data, '<router-gateway', '</router-gateway>')[1]
        data = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'config="', '"', False)[1])
        try:
            data = byteify(json.loads(data))
            baseUrl = data['api']['planninglist']
            if not self.cm.isValidUrl(baseUrl):
                return
            for item in data['categories']:
                url = baseUrl + '?target_site=media&origin_site=media&category_id=' + item['id'] + '&start_date&offset={0}&limit={1}&partner_key=' + partnerKey
                title = self.cleanHtmlStr(item['label'])
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url})
                self.addDir(params)
        except Exception:
            printExc()

    def listLiveItems(self, cItem):
        printDBG("RTBFBE.listLiveItems")

        def _parseDate(dateStr):
            date = datetime.strptime(dateStr[:-7], "%Y-%m-%dT%H:%M:%S")
            offsetDir = dateStr[-6]
            offsetHours = int(dateStr[-5:-3])
            offsetMins = int(dateStr[-2:])
            if offsetDir == "+":
                offsetHours = -offsetHours
                offsetMins = -offsetMins
            utc_date = date + timedelta(hours=offsetHours, minutes=offsetMins) + self.OFFSET
            return utc_date

        currDate = datetime.now()
        NUM_ITEMS = 20
        page = cItem.get('page', 0)

        sts, data = self.getPage(cItem['url'].format(page * NUM_ITEMS, NUM_ITEMS))
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            for item in data:
                title = self.cleanHtmlStr(item['title'])
                subtitle = self.cleanHtmlStr(item['subtitle'])
                if subtitle != '':
                    title = '%s - %s' % (title, subtitle)
                url = self.getFullUrl(item['url_share'])
                try:
                    streamUrl = self.getFullUrl(item['url_streaming']['url_hls'])
                except Exception:
                    streamUrl = ''
                if not self.cm.isValidUrl(streamUrl):
                    continue
                desc = [self.cleanHtmlStr(item['geolock']['title'])]
                if item.get('drm', False):
                    desc.append('DRM')
                try:
                    icon = self.getFullIconUrl(item['images']['illustration']['16x9']['370x208'])
                    for k in ['channel', 'program', 'category', 'live']:
                        desc.append(item[k]['label'])
                except Exception:
                    icon = ''
                desc = [' | '.join(desc)]
                desc.append(self.cleanHtmlStr(item['description']))

                date = _parseDate(item['start_date'])
                if date.day == currDate.day:
                    timeHeader = date.strftime('%Hh%M')
                else:
                    timeHeader = date.strftime('%Y-%m-%d %Hh%M')
                timeHeader += ' - ' + _parseDate(item['end_date']).strftime('%Hh%M')
                desc.insert(0, timeHeader)

                params = {'good_for_fav': False, 'title': title, 'url': url, 'stream_url': streamUrl, 'icon': icon, 'desc': '[/br]'.join(desc)}
                self.addVideo(params)

            if NUM_ITEMS == len(self.currList):
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': _('Next page'), 'page': page + 1})
                self.addDir(params)
        except Exception:
            printExc()

    def listSubMenuItems(self, cItem, nextCategory, key):
        printDBG("RTBFBE.listSubMenuItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        try:
            data = byteify(json.loads(data))['item']
            for item in data:
                if item['@attributes']['id'] == key:
                    for it in item['item']:
                        it = it['@attributes']
                        if it['url'].startswith('.'):
                            continue
                        url = self.getFullUrl(it['url'])
                        title = self.cleanHtmlStr(it['name'])
                        params = dict(cItem)
                        params.update({'good_for_fav': False, 'url': url, 'title': title, 'category': nextCategory})
                        self.addDir(params)
                    break
        except Exception:
            printExc()

    def serParams(self, obj, data=''):
        newData = ''
        if isinstance(obj, list):
            for idx in range(len(obj)):
                newData += self.serParams(obj[idx], data + urllib_quote('[%d]' % idx))
        elif isinstance(obj, dict):
            for key in obj:
                newData += self.serParams(obj[key], data + urllib_quote('[%s]' % key))
        elif obj == True:
            newData += data + '=true&'
        elif obj == False:
            newData += data + '=false&'
        else:
            newData += data + '=%s&' % urllib_quote(str(obj))
        return newData

    def listSections(self, cItem, nextCategory1, nextCategory2):
        printDBG("RTBFBE.listSections")
        page = cItem.get('page', 0)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cItem = dict(cItem)
        defaultMediaType = cItem.pop('default_media_type', 'video')

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        nextPage = self.cm.ph.getSearchGroups(data, '''(<a[^>]+?pagination__link[^>]+?Next[^>]+?>)''')[0]
        nextPage = self.getFullUrl(self.cm.ph.getSearchGroups(nextPage, '''href=['"]([^'^"]+?)['"]''')[0], cUrl)

        sections = self.cm.ph.getAllItemsBeetwenNodes(data, ('<section', '>'), ('</section', '>'), False)
        if page == 0:
            sections.append(self.cm.ph.getDataBeetwenNodes(data, ('<div', '>', 'autocomplete--medias'), ('</section', '>'))[1])

        reObj = re.compile('\sdata\-([^=]+?)="([^"]+?)"')
        query = []
        uuids = []
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<b', '>', 'data-uuid'), ('</b', '>'))
        for item in data:
            item = reObj.findall(item)
            obj = {}
            for it in item:
                if it[0] == 'devices':
                    continue
                if it[0] == 'uuid':
                    uuids.append(it[1])
                try:
                    obj[it[0]] = byteify(json.loads(self.cleanHtmlStr(it[1])))
                except Exception:
                    obj[it[0]] = it[1]
            query.append(obj)

        if len(query):
            query = self.serParams(query, 'data')
            url = self.getFullUrl('/news/api/block?' + query)
            sts, data = self.getPage(url)
            if not sts:
                return

            try:
                data = byteify(json.loads(data))['blocks']
                for uuid in uuids:
                    if uuid not in data:
                        continue
                    sections.append(data[uuid])
            except Exception:
                printExc()

        for sectionItem in sections:
            sectionItem = sectionItem.split('<section', 1)[-1]
            sTitle = self.cm.ph.getDataBeetwenNodes(sectionItem, ('<h', '>', 'www-title'), ('</h', '>'))[1]
            sUrl = self.getFullUrl(self.cm.ph.getSearchGroups(sTitle, '''href=['"]([^'^"]+?)['"]''')[0])
            if sUrl == '' and '<article' not in sectionItem:
                sUrl = self.getFullUrl(self.cm.ph.getSearchGroups(sectionItem, '''<a[^>]+?href=['"]([^'^"]+?)['"]''')[0])
            sTitle = self.cleanHtmlStr(sTitle)
            if sTitle == '':
                continue
            sItems = []
            sectionItem = self.cm.ph.getAllItemsBeetwenMarkers(sectionItem, '<article', '</article>')
            for item in sectionItem:
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data\-srcset=['"]([^'^"^\s]+?)[\s'"]''')[0])
                if icon == '':
                    icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"^\s]+?(?:\.jpe?g|\.png)(?:\?[^'^"^\s]*?)?)[\s'"]''')[0])
                header = self.cm.ph.getDataBeetwenMarkers(item, '<header', '</header>')[1]
                url = self.cm.ph.getSearchGroups(header, '''href=['"]([^'^"]+?)['"]''')[0]
                if url == '' or url[0] in ['{', '[']:
                    continue
                url = self.getFullUrl(url)
                title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(header, ('<h', '>', '__title'), ('</h', '>'))[1])
                subTitle = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(header, ('<h', '>', '__subtitle'), ('</h', '>'))[1])
                duration = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'duration'), ('</span', '>'))[1])
                desc = []
                if subTitle != '':
                    if subTitle.decode('utf-8').lower() not in title.decode('utf-8').lower():
                        title = '%s - %s' % (title, subTitle)
                    else:
                        desc.append(subTitle)
                if duration != '':
                    desc.append(duration)
                desc.append(self.cleanHtmlStr(item.split('</header>', 1)[-1]))
                params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if 'ico-playlist' in item:
                    params.update({'type': 'category', 'category': 'list_playlist_items'})
                elif 'ico-volume' in item:
                    params['type'] = 'audio'
                elif 'ico-play' in item:
                    params['type'] = 'video'
                elif '/emissions/' in url:
                    params['type'] = 'video'
                else:
                    params['type'] = defaultMediaType
                sItems.append(params)

            if len(sItems):
                icon = sItems[0]['icon']
            else:
                icon = ''

            if sUrl != '' and sUrl != cItem['url']:
                if 0 == len(sItems):
                    title = sTitle
                else:
                    title = _('More')
                params = dict(cItem)
                params.update({'good_for_fav': False, 'url': sUrl, 'title': title, 'category': nextCategory2, 'icon': icon})
                sItems.append(params)

            if len(sItems) > 1:
                params = dict(cItem)
                params.update({'good_for_fav': False, 'title': sTitle, 'category': nextCategory1, 'sub_items': sItems, 'icon': icon})
                self.addDir(params)
            elif len(sItems) == 1:
                self.currList.append(sItems[0])

        if 1 == len(self.currList) and 'sub_items' in self.currList[0]:
            self.currList = self.currList[0]['sub_items']

        if nextPage != '' and len(self.currList):
            params = dict(cItem)
            params.update({'good_for_fav': False, 'default_media_type': defaultMediaType, 'category': nextCategory2, 'url': nextPage, 'title': _('Next page'), 'page': page + 1})
            self.addDir(params)

    def listSubItems(self, cItem):
        printDBG("RTBFBE.listSubItems")
        self.currList = cItem['sub_items']

    def listPlaylistItems(self, cItem):
        printDBG("RTBFBE.listPlaylistItems")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        cItem = dict(cItem)

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'chapter-list'), ('<div', '>', 'media-nav'))[1]
        data = re.compile('''<li[^>]+?js\-chapter\-entry[^>]+?>''').split(data)
        for item in data:
            icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''data\-srcset=['"]([^'^"^\s]+?)[\s'"]''')[0])
            if icon == '':
                icon = self.getFullIconUrl(self.cm.ph.getSearchGroups(item, '''src=['"]([^'^"^\s]+?(?:\.jpe?g|\.png)(?:\?[^'^"^\s]*?)?)[\s'"]''')[0])
            title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''\stitle=['"]([^'^"]+?)['"]''')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, '''href=['"]([^'^"]+?)['"]''')[0])
            desc = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', '-subtitle'), ('</span', '>'))[1])
            if '/auvio/' not in url:
                continue
            params = {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'desc': desc}
            self.addVideo(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("RTBFBE.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        params = {'name': 'category', 'type': 'category', 'default_media_type': searchType, 'url': self.getFullUrl('/auvio/recherche?q=%s&type=%s') % (urllib_quote_plus(searchPattern), searchType)}
        self.listSections(params, 'list_sub_items', 'sections')

    def getUserGeoLoc(self):
        if 0 == len(self.userGeoLoc):
            sts, data = self.getPage(self.getFullUrl('/api/geoloc'))
            try:
                byteify(json.loads(data), '', True)
                self.userGeoLoc = data['country']
            except Exception:
                printExc()
        return self.userGeoLoc

    def getLinksForVideo(self, cItem):
        printDBG("RTBFBE.getLinksForVideo [%s]" % cItem)
        self.tryTologin()

        retTab = []
        mp4Tab = []
        hlsTab = []
        dashTab = []
        subsTab = []
        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        cUrl = data.meta['url']
        self.setMainUrl(cUrl)

        url = self.getFullUrl(self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?)['"]''', 1, True)[0])
        urlParams = dict(self.defaultParams)
        urlParams['header'] = dict(urlParams['header'])
        urlParams['header']['Referer'] = cUrl

        sts, data = self.getPage(url, urlParams)
        if not sts:
            return []

        geoLocRestriction = ''
        data = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(data, 'data-media="', '"', False)[1])
        try:
            data = byteify(json.loads(data), '', True)
            printDBG("++++++++++++++++++++++++++++++++++++++++++++++")
            printDBG(data)
            geoLocRestriction = data.get('geoLocRestriction', '')

            # HLS LINKS
            hslUrls = [data.get('streamUrlHls', ''), cItem.get('stream_url', '')]
            hslUrls.append(data.get('urlHls', ''))
            for hslUrl in hslUrls:
                if not self.cm.isValidUrl(hslUrl):
                    continue
                hlsTab.append({'name': '[HLS/m3u8]', 'url': hslUrl, 'iptv_proto': 'm3u8'})
                if len(hlsTab):
                    break

            # DASH LINKS
            dashUrl = data.get('urlDash', '')
            if self.cm.isValidUrl(dashUrl):
                dashTab = [{'name': '[DASH/mpd]', 'url': dashUrl, 'iptv_proto': 'mpd'}]

            # MP4 LINKS
            if 'sources' in data:
                try:
                    tmp = []
                    for type in ['url', 'high', 'mobile', 'web']:
                        url = data['sources'][type]
                        if url in tmp:
                            continue
                        tmp.append(url)
                        name = self.cm.ph.getSearchGroups(url, '''[\-_]([0-9]+?)p\.mp4''')[0]
                        if name == '':
                            name = type
                        if self.cm.isValidUrl(url):
                            mp4Tab.append({'name': '[mp4] %sp' % name, 'url': url, 'quality': name})
                    mp4Tab = CSelOneLink(mp4Tab, lambda item: int(item['quality']), 999999999).getSortedLinks()
                except Exception:
                    printExc()

            # SUBTITLES
            for item in data['tracks']:
                if isinstance(item, basestring):
                    item = data['tracks'][item]
                subtitleUrl = item['url']
                if not self.cm.isValidUrl(subtitleUrl):
                    continue
                subsTab.append({'title': item['label'], 'url': subtitleUrl, 'lang': item['lang'], 'format': item['format']})

            printDBG("++++++++++++++++++++++++++++++++++++++++++++++")
            printDBG(subsTab)
        except Exception:
            printExc()

        retTab.extend(hlsTab)
        retTab.extend(mp4Tab)
        retTab.extend(dashTab)

        namePrefix = ''
        if geoLocRestriction != 'open' and geoLocRestriction == self.getUserGeoLoc():
            namePrefix = '!geo-blocked! '
        for idx in range(len(retTab)):
            meta = {'Referer': cItem['url'], 'external_sub_tracks': subsTab}
            if 'iptv_proto' in retTab[idx]:
                meta['iptv_proto'] = retTab[idx]['iptv_proto']
            retTab[idx]['url'] = strwithmeta(retTab[idx]['url'], meta)
            retTab[idx]['need_resolve'] = 1
            retTab[idx]['name'] = namePrefix + retTab[idx]['name']

        if len(retTab):
            self.cacheLinks[cacheKey] = retTab
        return retTab

    def getVideoLinks(self, videoUrl):
        printDBG("RTBFBE.getVideoLinks [%s]" % videoUrl)
        self.tryTologin()

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
                        break

        if 1 == self.up.checkHostSupport(videoUrl):
            videoUrl = videoUrl.replace('youtu.be/', 'youtube.com/watch?v=')
            return self.up.getVideoLinkExt(videoUrl)

        retTab = []
        meta = dict(videoUrl.meta)
        type = meta.pop('iptv_proto', 'mp4')
        printDBG("++++++++++++++++++++++++ type[%s]" % type)
        if self.loggedIn:
            urlParams = dict(self.defaultParams)
            urlParams['header'] = dict(urlParams['header'])
            urlParams['header']['Referer'] = videoUrl.meta['Referer']
            urlParams['raw_post_data'] = True

            url = 'https://token.rtbf.be/'
            sts, data = self.getPage(url, urlParams, self.serParams({type: videoUrl}, 'streams'))
            if not sts:
                return []

            try:
                data = byteify(json.loads(data))
                videoUrl = data['streams'][type]
                printDBG("+++++++++++++++++++++++++++++++++++++++++++++")
                printDBG(videoUrl)
            except Exception:
                printExc()
        elif 'token=' not in videoUrl and '?' not in videoUrl:
            videoUrl += '?token=' + self.getPartnerToken()

        if type == 'm3u8':
            retTab = getDirectM3U8Playlist(videoUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        elif type == 'mpd':
            retTab = getMPDLinksWithMeta(videoUrl, checkExt=False, sortWithMaxBandwidth=999999999)
        else:
            retTab = [{'name': 'mp4', 'url': videoUrl}]

        for idx in range(len(retTab)):
            retTab[idx]['url'] = strwithmeta(retTab[idx]['url'], meta)

        return retTab

    def tryTologin(self):
        printDBG('RTBFBE.tryTologin start')
        serverUnkResponse = _('Unknown server response.')
        message = serverUnkResponse

        if self.login == config.plugins.iptvplayer.rtbfbe_login.value and \
           self.password == config.plugins.iptvplayer.rtbfbe_password.value:
           return

        self.login = config.plugins.iptvplayer.rtbfbe_login.value
        self.password = config.plugins.iptvplayer.rtbfbe_password.value

        self.loginData = {}
        rm(self.COOKIE_FILE)
        self.loggedIn = False

        if '' == self.login.strip() or '' == self.password.strip():
            return False

        sts, data = self.getPage(self.getMainUrl())
        if sts:
            self.getPartnerKey(data)
            self.dataKey = self.cm.ph.getSearchGroups(data, '''data\-key=['"]([^'^"]+?)['"]''')[0]
            sts, data = self.getPage(self.getFullUrl('/api/sso/screenset?set=authentication'))
        if sts:
            requestId = 'R%s' % random.randint(1000000000, 9999999999)
            url = 'https://login.rtbf.be/accounts.login?context=%s&&saveResponseID=%s' % (requestId, requestId)
            post_data = {'loginID': self.login,
                         'password': self.password,
                         'sessionExpiration': '-2',
                         'targetEnv': 'jssdk',
                         'include': 'profile,data,emails,subscriptions,preferences,',
                         'includeUserInfo': 'true',
                         'loginMode': 'standard',
                         'APIKey': self.dataKey,
                         'source': 'showScreenSet',
                         'sdk': 'js_8.1.20',
                         'authMode': 'cookie',
                         'pageURL': self.getFullUrl('/auvio/'),
                         'format'              'json'
                         'context': requestId
                         }
            sts, data = self.getPage(url, post_data=post_data)
        if sts:
            url = 'https://login.rtbf.be/socialize.getSavedResponse?APIKey=%s&saveResponseID=%s&noAuth=true&sdk=js_8.1.20&format=jsonp&callback=gigya.callback&context=%s'
            sts, data = self.getPage(url % (self.dataKey, requestId, requestId), post_data=post_data)
        if sts:
            try:
                data = self.cm.ph.getDataBeetwenMarkers(data, 'gigya.callback(', ');', False)[1]
                data = byteify(json.loads(data))
                printDBG(data)
                printDBG("++++++++++++++++++++++++++++++++++++")
                if 200 == data['statusCode']:
                    self.loginData = data
                    url = 'https://www.rtbf.be/api/sso/login'
                    post_data = {'gigyaId': data['UID'],
                                 'signature': data['UIDSignature'],
                                 'timestamp': data['signatureTimestamp']}
                    urlParams = dict(self.defaultParams)
                    urlParams['header'] = dict(urlParams['header'])
                    urlParams['header']['X-CSRF-Token'] = self.csrfToken
                    sts, data = self.getPage(url, urlParams, post_data=post_data)
                else:
                    sts = False
                    message = self.cleanHtmlStr(data['errorMessage'])
            except Exception:
                printExc()
        if sts:
            url = 'https://www.rtbf.be/api/sso/fetch'
            sts, data = self.getPage(url, urlParams)
            printDBG(data)
            printDBG("++++++++++++++++++++++++++++++++++++")

        if sts:
            self.loggedIn = True
        else:
            self.loggedIn = False
            self.sessionEx.open(MessageBox, _('Login failed.') + '\n' + message, type=MessageBox.TYPE_ERROR, timeout=10)
        return self.loggedIn

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        self.tryTologin()

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        if RTBFBE.CHECK_GEO_LOCK:
            RTBFBE.CHECK_GEO_LOCK = False
            self.informAboutGeoBlockingIfNeeded('BE')

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||| name[%s], category[%s] " % (name, category))
        self.cacheLinks = {}
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'}, 'sub_menu')
    #LIVE
        elif category == 'live_categories':
            self.listLiveCategories(self.currItem, 'list_live_items')
        elif category == 'list_live_items':
            self.listLiveItems(self.currItem)
    #CATEGORIES
        elif category == 'categories':
            self.listSubMenuItems(self.currItem, 'sections', 'category')
    #CHANNELS
        elif category == 'channels':
            self.listSubMenuItems(self.currItem, 'sections', 'channel')
    #SECTIONS
        elif category == 'sections':
            self.listSections(self.currItem, 'list_sub_items', 'sections')
        elif category == 'list_sub_items':
            self.listSubItems(self.currItem)
        elif category == 'list_playlist_items':
            self.listPlaylistItems(self.currItem)
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
        CHostBase.__init__(self, RTBFBE(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Video"), "video"))
        searchTypesOptions.append((_("Audio"), "audio"))
        return searchTypesOptions
