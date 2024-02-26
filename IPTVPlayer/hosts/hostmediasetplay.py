# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetJSScriptFile, PrevDay
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
if isPY2():
    import cookielib
else:
    import http.cookiejar as cookielib
###################################################

from Screens.MessageBox import MessageBox

###################################################
# FOREIGN import
###################################################
import re
import uuid
import time
import datetime
import math
from datetime import timedelta
###################################################

def GetConfigList():
    optionList = []
    return optionList


def gettytul():
    return 'https://mediasetplay.it/'


class MediasetPlay(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mediasetplay.it', 'cookie': 'mediasetplay.it.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='firefox')
        self.HTTP_HEADER.update({'Referer': 'https://www.mediasetplay.mediaset.it/', 'Accept': 'application/json', 'Content-Type': 'application/json'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://www.mediasetplay.mediaset.it/'
        self.API_BASE_URL = 'https://api-ott-prod-fe.mediaset.net/PROD/play/'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/34/67/9b/34679b83e426516b478ba9d63dcebfa2.png' #'http://www.digitaleterrestrefacile.it/wp-content/uploads/2018/07/mediaset-play.jpg' #'https://cdn.one.accedo.tv/files/5b0d3b6e23eec6000dd56c7f'

        self.cacheLinks = {}
        self.initData = {}

        self.OFFSET = datetime.datetime.now() - datetime.datetime.utcnow()
        seconds = self.OFFSET.seconds + self.OFFSET.days * 24 * 3600
        if ((seconds + 1) % 10) == 0:
            seconds += 1
        elif ((seconds - 1) % 10) == 0:
            seconds -= 1
        self.OFFSET = timedelta(seconds=seconds)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def dateRange(self, d):
        d1 = d.replace(minute=0, hour=0, second=0, microsecond=0)
        d2 = d.replace(minute=59, hour=23, second=59, microsecond=999999)
        return (d1, d2)

    def initApi(self):
        if self.initData:
            return
        url = self.API_BASE_URL + 'idm/anonymous/login/v1.0'
        params = MergeDicts(self.defaultParams, {'raw_post_data': True, 'collect_all_headers': True})
        cid = str(uuid.uuid4())
        post_data = '{"cid":"%s","platform":"pc","appName":"web/mediasetplay-web/18be850"}' % cid

        sts, data = self.getPage(url, params, post_data=post_data)
        if not sts:
            return
        printDBG(data)
        try:
            headers = {'t-apigw': self.cm.meta['t-apigw'], 't-cts': self.cm.meta['t-cts']}
            data = json_loads(data)
            if data['isOk']:
                tmp = data['response']
                self.initData.update({'traceCid': tmp['traceCid'], 'cwId': tmp['cwId'], 'cid': cid})
                self.HTTP_HEADER.update(headers)
        except Exception:
            printExc()
        if not self.initData:
            self.sessionEx.waitForFinishOpen(MessageBox, _("API initialization failed!"), type=MessageBox.TYPE_ERROR, timeout=20)

    def listMain(self, cItem, nextCategory):
        printDBG("MediasetPlay.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        subItems = []
        subItems.append(MergeDicts(cItem, {'category': 'cat_az', 'title': 'Tutto A-Z'}))
        subItems.append(MergeDicts(cItem, {'category': 'cat_series', 'title': 'Fiction e Serie TV', 'url': self.getFullUrl('/fiction')}))
        subItems.append(MergeDicts(cItem, {'category': 'cat_movies', 'title': 'Film', 'url': self.getFullUrl('/film')}))

        self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': 'On Demand', 'sub_items': subItems, }))
        self.addDir(MergeDicts(cItem, {'category': 'on_air', 'title': 'Ora in onda', 'url': self.getMainUrl()}))
        self.addDir(MergeDicts(cItem, {'category': 'cat_channels', 'title': 'Canali', 'url': self.getMainUrl()}))
        self.addDir(MergeDicts(cItem, {'category': 'list_catalog_items', 'title': _('Top day'), 'f_ref': 'CWTOPVIEWEDDAY'}))

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listSubItems(self, cItem):
        printDBG("MediasetPlay.listSubItems")
        self.currList = cItem['sub_items']

    def listOnAir(self, cItem):
        printDBG("MediasetPlay.listOnAir")
        sts, data = self.getPage('https://feed.entertainment.tv.theplatform.eu/f/PR1GhC/mediaset-prod-all-stations?bycallsign')
        if not sts:
            return
        try:
            data = json_loads(data)
            for item in data['entries']:
                if 'vip' in item['mediasetstation$pageUrl']:
                    continue
                icon = self.getFullIconUrl(item['thumbnails']['channel_logo-100x100']['url']) #next(iter(item['thumbnails']))['url'] )
                title = item['title']
                url = self.getFullIconUrl(item['mediasetstation$pageUrl'])
                self.addVideo(MergeDicts(cItem, {'good_for_fav': True, 'title': title, 'url': url, 'icon': icon, 'call_sign': item['callSign'], 'is_live': True}))
        except Exception:
            printExc()

    def listChannels(self, cItem, nextCategory):
        printDBG("MediasetPlay.listChannels")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']

        data = ph.find(data, '<span>Canali</span>', '>On Demand<', flags=0)[1]
        data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            url = self.getFullUrl(ph.getattr(data[idx - 1], 'href'), cUrl)
            title = ph.clean_html(data[idx])
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))

    def listChannelItems(self, cItem, nextCategory):
        printDBG("MediasetPlay.listChannelItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        channelId = ph.search(data, '''/diretta/[^'^"]+?_c([^'^"]+?)['"][^>]*?>\s*?diretta\s*?<''', flags=ph.I)[0]

        self.listCatalog(cItem, 'list_catalog_items', 'video_mixed', data)

        ABBREVIATED_DAYS_NAME_TAB = ['LUN', 'MAR', 'MER', 'GIO', 'VEN', 'SAB', 'DOM']
        subItems = []
        today = datetime.datetime.utcnow()
        r = self.dateRange(today)
        start = r[0] + self.OFFSET
        end = r[1] + self.OFFSET
        for i in range(8):
            s = int(time.mktime(start.timetuple()) * 1000)
            e = int(time.mktime(end.timetuple()) * 1000)
            title = 'Oggi' if i == 0 else ABBREVIATED_DAYS_NAME_TAB[start.weekday()] + ' ' + str(start.day).zfill(2)
            url = self.API_BASE_URL + 'alive/allListingFeedFilter/v1.0?byListingTime=%s~%s&byVod=true&byCallSign=%s' % (s, e, channelId)

            subItems.append(MergeDicts(cItem, {'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': url}))
            start = PrevDay(start)
            end = PrevDay(end)
        self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': 'Ultima settimana', 'sub_items': subItems, }))

    def listTime(self, cItem, nextCategory):
        printDBG("MediasetPlay.listTime")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        try:
            data = json_loads(data)['response']
            for item in data['entries'][0]['listings']:
                item = item['program']
                title = item['title']
                desc = []
                videoUrl = item.get('mediasetprogram$videoPageUrl', '')
                if videoUrl:
                    desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0])
                    desc.append(item['mediasetprogram$publishInfo']['description'])
                    desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
                    desc.append(_('%s views') % item['mediasetprogram$numberOfViews'])
                    desc = [' | '.join(desc)]
                    icon = item['thumbnails']['image_keyframe_poster-292x165']['url']
                    url = self.getFullUrl(videoUrl)
                    guid = item['guid']
                else:
                    icon = item['thumbnails']['image_vertical-264x396']['url']
                    url = self.getFullUrl(item['mediasetprogram$pageUrl'])
                desc.append(item.get('description', ''))
                params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if videoUrl:
                    self.addVideo(MergeDicts(cItem, params, {'guid': guid}))
                else:
                    self.addDir(MergeDicts(cItem, params))
        except Exception:
            printExc()

    def listAZFilters(self, cItem, nextCategory):
        printDBG('MediasetPlay.listAZFilters')
        idx = cItem.get('az_filter_idx', 0)
        cItem = MergeDicts(cItem, {'az_filter_idx': idx + 1})
        if idx == 0:
            filtersTab = [{'title': 'Tutti generi'},
                          {'title': 'Cinema', 'f_category': 'Cinema'},
                          {'title': 'Fiction', 'f_category': 'Fiction'},
                          {'title': 'Documentari', 'f_category': 'Documentari'},
                          {'title': 'Programmi Tv', 'f_category': 'Programmi Tv'}, ]
        elif idx == 1:
            filtersTab = [{'title': 'Tutti'},
                          {'title': 'In onda', 'f_onair': True}, ]
        elif idx == 2:
            cItem['category'] = nextCategory
            filtersTab = []
            filtersTab.append({'title': 'Tutti', 'f_query': '*:*'})
            for i in range(0, 24):
                filtersTab.append({'title': chr(ord('A') + i), 'f_query': 'TitleFullSearch:%s*' % chr(ord('a') + i)})
            filtersTab.append({'title': '#', 'f_query': '-(TitleFullSearch:{A TO *})'})
        self.listsTab(filtersTab, cItem)

    def listAZItems(self, cItem, nextCategory):
        printDBG('MediasetPlay.listAZItems')

        query = {'hitsPerPage': 50}
        if 'f_onair' in cItem:
            query['inOnda'] = 'true'
        url = self.API_BASE_URL + 'rec/azlisting/v1.0?' + urllib_urlencode(query)
        if 'f_query' in cItem:
            url += '&query=%s' % cItem['f_query'] #query['query'] = cItem['f_query']
        if 'f_category' in cItem:
            url += '&categories=%s' % cItem['f_category'] #query['categories'] = cItem['f_category']

        cItem = MergeDicts(cItem, {'category': 'list_items', 'url': url})
        self.listItems(cItem, nextCategory)

    def listItems(self, cItem, nextCategory):
        printDBG('MediasetPlay.listItems')
        page = cItem.get('page', 1)
        url = cItem['url'] + '&page=%s' % page
        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)['response']
            for item in data['entries']:
                title = item['title']
                desc = []
                videoUrl = item.get('mediasetprogram$videoPageUrl', '')
                if videoUrl:
                    desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0])
                    desc.append(item['mediasetprogram$publishInfo']['description'])
                    desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
                    desc.append(_('%s views') % item['mediasetprogram$numberOfViews'])
                    desc = [' | '.join(desc)]
                    icon = item['thumbnails']['image_keyframe_poster-292x165']['url']
                    url = self.getFullUrl(videoUrl)
                    guid = item['guid']
                else:
                    icon = item['thumbnails']['image_vertical-264x396']['url']
                    url = self.getFullUrl(item['mediasetprogram$pageUrl'])
                desc.append(item.get('description', ''))
                params = {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': '[/br]'.join(desc)}
                if videoUrl:
                    self.addVideo(MergeDicts(cItem, params, {'guid': guid}))
                else:
                    self.addDir(MergeDicts(cItem, params))

            if data.get('hasMore'):
                self.addDir(MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1}))
        except Exception:
            printExc()

    def listCatalog(self, cItem, nextCategory1, nextCategory2, data=None):
        printDBG("MediasetPlay.listCatalog")
        if not data:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            self.setMainUrl(self.cm.meta['url'])

        exports = {"button-special": "_1u_k9 _3Pqi-", "wrapper": "C6FJZ", "description": "_3XiTc", "sub-title-banner": "_1tNlk", "title-banner": "_1KV50", "airing-time": "_3pYTW", "description-wrapper": "glxlH", "title-hero": "dTamS", "title-hero-small": "_1AN7g"}

        data = ph.find(data, ('<article', '>'), '</article>', flags=0)[1]
        data = ph.findall(data, ('<section', '>'), '</section>', flags=0)
        for sectionItem in data:
            sectionItem = sectionItem.split('</header>', 1)
            sIcon = self.getFullUrl(ph.search(sectionItem[0], ph.IMAGE_SRC_URI_RE)[1])
            sTitle = ph.clean_html(ph.find(sectionItem[0], ('<h2', '>'), '</h2>', flags=0)[1])
            if not sTitle:
                sTitle = ph.clean_html(ph.getattr(sectionItem[0], 'title'))
            subItems = []
            item = ph.rfind(sectionItem[0], '</div>', ('<div', '>', exports['wrapper']), flags=0)[1]
            url = self.getFullUrl(ph.getattr(item, 'href'))
            desc = ph.clean_html(ph.find(item, ('<div', '>', exports['description']), '</div>', flags=0)[1])
            title = ph.clean_html(ph.find(item, ('<div', '>', exports['button-special']), '</div>', flags=0)[1])
            if url and title:
                subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory2, 'url': url, 'title': title, 'icon': sIcon, 'desc': desc}))

            sectionItem = ph.rfindall(sectionItem[-1], '</div>', ('<a', '>'), flags=ph.END_S)
            for idx in range(1, len(sectionItem), 2):
                url = self.getFullUrl(ph.getattr(sectionItem[idx - 1], 'href'))
                item = sectionItem[idx]
                icon = self.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1])
                title1 = ph.clean_html(ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1])
                title2 = ph.clean_html(ph.find(item, ('<h4', '>'), '</h4>', flags=0)[1])
                if not title1:
                    title1 = ph.clean_html(ph.find(item, ('<p', '>', exports['title-banner']), '</p>', flags=0)[1])
                if not title2:
                    title2 = ph.clean_html(ph.find(item, ('<p', '>', exports['sub-title-banner']), '</p>', flags=0)[1])
                if not title1:
                    title1 = ph.clean_html(ph.find(item, ('<p', '>', exports['title-hero']), '</p>', flags=0)[1])
                if not title2:
                    title2 = ph.clean_html(ph.find(item, ('<p', '>', exports['title-hero-small']), '</p>', flags=0)[1])
                if not title1:
                    title1 = ph.clean_html(ph.find(item, ('<h2', '>'), '</h2>', flags=0)[1])

                title = []
                if title1:
                    title.append(title1)
                if title2:
                    title.append(title2)
                desc = []
                desc.append(ph.clean_html(ph.find(item, ('<div', '>', exports['airing-time']), '</div>', flags=0)[1]))
                desc.append(ph.clean_html(ph.find(item, ('<div', '>', exports['description-wrapper']), '</div>', flags=0)[1]))
                params = {'good_for_fav': True, 'url': url, 'title': ' - '.join(title), 'icon': icon, 'desc': '[/br]'.join(desc)}
                if '/diretta/' in url:
                    subItems.append(MergeDicts(params, {'type': 'video', 'is_live': True, 'desc': _('live')}))
                elif '/video' in url:
                    subItems.append(MergeDicts(params, {'type': 'video'}))
                else:
                    subItems.append(MergeDicts(cItem, params, {'category': nextCategory2}))
            if len(subItems) == 1:
                self.currList.extend(subItems)
            elif len(subItems) > 1:
                self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': 'sub_items', 'title': sTitle, 'icon': sIcon, 'sub_items': subItems}))

        if len(self.currList) == 1 and self.currList[0].get('category') == 'sub_items':
            self.currList = self.currList[0]['sub_items']

        tab = []
        category = cItem['category']
        cItem = MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory1})
        if category == 'cat_movies':
            tab = [{'title': 'Film più visti', 'f_ref': 'CWFILMTOPVIEWED'},
                   {'title': 'Commedia', 'f_ref': 'CWFILMCOMEDY'},
                   {'title': 'Drammatico', 'f_ref': 'CWFILMDRAMATIC'},
                   {'title': 'Thriller, Azione e Avventura', 'f_ref': 'CWFILMACTION'},
                   {'title': 'Documentari', 'f_ref': 'CWFILMDOCU'}, ]
        elif category == 'cat_series':
            tab = [{'title': 'Poliziesco', 'f_ref': 'CWFICTIONPOLICE'},
                   {'title': 'Sentimentale', 'f_ref': 'CWFICTIONSENTIMENTAL'},
                   {'title': 'Commedia', 'f_ref': 'CWFICTIONCOMEDY'},
                   {'title': 'Thriller, Azione e Avventura', 'f_ref': 'CWFICTIONACTION'},
                   {'title': 'Biografico', 'f_ref': 'CWFICTIONBIOGRAPHICAL'},
                   {'title': 'Sit-Com', 'f_ref': 'CWFICTIONSITCOM'},
                   {'title': 'Drammatico', 'f_ref': 'CWFICTIONDRAMATIC'},
                   {'title': 'Avventura', 'f_ref': 'CWFICTIONADVENTURE'}, ]
        self.listsTab(tab, cItem)

    def listCatalogItems(self, cItem, nextCategory):
        printDBG("MediasetPlay.listCatalogItems")
        query = {'uxReference': cItem['f_ref'], 'platform': 'pc'}
        query.update(self.initData)
        url = self.API_BASE_URL + 'rec/cataloguelisting/v1.0?' + urllib_urlencode(query)

        sts, data = self.getPage(url)
        if not sts:
            return
        try:
            data = json_loads(data)['response']
            for item in data['entries']:
                title = item['title']
                desc = item['description']
                icon = item['thumbnails']['image_vertical-264x396']['url']
                url = self.getFullUrl(item['mediasetprogram$pageUrl'])
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon, 'desc': desc}))

            if data.get('hasMore'):
                self.addDir(MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1}))
        except Exception:
            printExc()

    def listVideoMixed(self, cItem):
        printDBG("MediasetPlay.listVideoMixed")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        self.setMainUrl(cUrl)

        exports = {"airing-time": "_3pYTW", "description-wrapper": "glxlH"}

        data = ph.find(data, ('<article', '>'), '</article>', flags=0)[1]
        data = ph.findall(data, ('<section', '>', 'videoMixed'), '</section>', flags=0)
        for sectionItem in data:
            sectionItem = sectionItem.split('</header>', 1)
            sTitle = ph.clean_html(ph.find(sectionItem[0], ('<h2', '>'), '</h2>', flags=0)[1])
            subItems = []
            sectionItem = ph.findall(sectionItem[-1], ('<a', '>'), '</a>', flags=ph.START_S)
            for idx in range(1, len(sectionItem), 2):
                url = self.getFullUrl(ph.getattr(sectionItem[idx - 1], 'href'))
                item = sectionItem[idx]
                icon = self.getFullUrl(ph.search(item, ph.IMAGE_SRC_URI_RE)[1])
                title = ph.clean_html(ph.find(item, ('<h4', '>'), '</h4>', flags=0)[1])
                desc = [ph.clean_html(ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1])]
                desc.append(ph.clean_html(ph.find(item, ('<div', '>', exports['airing-time']), '</div>', flags=0)[1]))
                desc.append(ph.clean_html(ph.find(item, ('<div', '>', exports['description-wrapper']), '</div>', flags=0)[1]))
                subItems.append({'type': 'video', 'good_for_fav': True, 'url': url, 'title': title, 'icon': icon, 'desc': '[/br]'.join(desc)})
            if len(subItems) == 1:
                self.currList.extend(subItems)
            elif len(subItems) > 1:
                self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'category': 'sub_items', 'title': sTitle, 'sub_items': subItems}))

        if len(self.currList) == 1 and self.currList[0].get('category') == 'sub_items':
            self.currList = self.currList[0]['sub_items']

        # https://feed.entertainment.tv.theplatform.eu/f/PR1GhC/mediaset-prod-all-brands?byCustomValue={brandId}{100000513}&sort=mediasetprogram$order
        # https://feed.entertainment.tv.theplatform.eu/f/PR1GhC/mediaset-prod-all-programs?byCustomValue={brandId}{100000513},{subBrandId}{100000722}&sort=mediasetprogram$publishInfo_lastPublished|desc
        # https://feed.entertainment.tv.theplatform.eu/f/PR1GhC/mediaset-prod-all-programs?byCustomValue={brandId}{100000513}&sort=mediasetprogram$publishInfo_lastPublished|desc

    def listSearchResult(self, cItem, searchPattern, searchType):
        self.initApi()

        query = {'uxReference': 'CWSEARCH%s' % searchType.upper(), 'query': searchPattern, 'platform': 'pc'}
        query.update(self.initData)

        url = self.API_BASE_URL + 'rec/search/v1.0?' + urllib_urlencode(query)
        if 'clip' == searchType:
            url += '&sort=Viewers=DESC'

        cItem = MergeDicts(cItem, {'category': 'list_items', 'url': url})
        self.listItems(cItem, 'video_mixed')

        #'CWSEARCHBRAND'
        #'CWSEARCHCLIP',
        #'CWSEARCHEPISODE'
        #'CWSEARCHMOVIE'

        #https://api-ott-prod-fe.mediaset.net/PROD/play/rec/search/v1.0?uxReference=CWSEARCHBRAND&query=shrek&platform=pc&traceCid=73dd1614-f553-4851-ace3-bd01e34bdd26&page=1
        #https://api-ott-prod-fe.mediaset.net/PROD/play/rec/search/v1.0?uxReference=CWSEARCHCLIP&query=shrek&platform=pc&traceCid=73dd1614-f553-4851-ace3-bd01e34bdd26&sort=Viewers=DESC&page=1
        #https://api-ott-prod-fe.mediaset.net/PROD/play/rec/search/v1.0?uxReference=CWSEARCHEPISODE&query=shrek&platform=pc&traceCid=73dd1614-f553-4851-ace3-bd01e34bdd26&page=1
        #https://api-ott-prod-fe.mediaset.net/PROD/play/rec/search/v1.0?uxReference=CWSEARCHMOVIE&query=shrek&platform=pc&traceCid=73dd1614-f553-4851-ace3-bd01e34bdd26&page=1

    def getLinksForVideo(self, cItem):
        printDBG(": %s" % cItem)
        self.initApi()

        linksTab = self.cacheLinks.get(cItem['url'], [])
        if linksTab:
            return linksTab

        if cItem.get('is_live'):
            channelId = cItem.get('call_sign')
            if not channelId:
                sts, data = self.getPage(cItem['url'])
                if not sts:
                    return
                channelId = ph.search(data, '''/diretta/[^'^"]+?_c([^'^"]+?)['"][^>]*?>\s*?diretta\s*?<''', flags=ph.I)[0]

            url = self.API_BASE_URL + 'alive/nownext/v1.0?channelId=' + channelId
            sts, data = self.getPage(url)
            if not sts:
                return
            try:
                data = json_loads(data)
                for tuningInstructions in data['response']['tuningInstruction'].itervalues():
                    for item in tuningInstructions:
                        printDBG(item)
                        url = item['streamingUrl'].split('?', 1)[0].replace('t-mediaset-it', '-mediaset-it')
                        if 'mpegurl' in item['format'].lower():
                            f = 'HLS/M3U8'
                        elif 'dash' in item['format'].lower():
                            f = 'DASH/MPD'
                        else:
                            continue
                        linksTab.append({'name': f, 'url': strwithmeta(url, {'priv_type': f}), 'need_resolve': 1})
            except Exception:
                printExc()
        else:
            guid = cItem.get('guid', '')
            if not guid:
                guid = ph.search(cItem['url'], r'''https?://(?:(?:www|static3)\.)?mediasetplay\.mediaset\.it/(?:(?:video|on-demand)/(?:[^/]+/)+[^/]+_|player/index\.html\?.*?\bprogramGuid=)([0-9A-Z]{16})''')[0]
            if not guid:
                return linksTab

            tp_path = 'PR1GhC/media/guid/2702976343/' + guid

            uniqueUrls = set()
            for asset_type in ('SD', 'HD'):
                for f in (('MPEG4', 'MP4', 0), ('MPEG-DASH', 'DASH/MPD', 1), ('M3U', 'HLS/M3U8', 1)):
                    url = 'http://link.theplatform.%s/s/%s?mbr=true&formats=%s&assetTypes=%s' % ('eu', tp_path, f[0], asset_type)
                    sts, data = self.cm.getPage(url, post_data={'format': 'SMIL'})
                    if not sts:
                        continue
                    if 'GeoLocationBlocked' in data:
                        SetIPTVPlayerLastHostError(ph.getattr(data, 'abstract'))
                    printDBG("++++++++++++++++++++++++++++++++++")
                    printDBG(data)
                    tmp = ph.findall(data, '<video', '>')
                    for item in tmp:
                        url = ph.getattr(item, 'src')
                        if not self.cm.isValidUrl(url):
                            continue
                        if url not in uniqueUrls:
                            uniqueUrls.add(url)
                            linksTab.append({'name': '%s - %s' % (f[1], asset_type), 'url': strwithmeta(url, {'priv_type': f[1]}), 'need_resolve': f[2]})
        if len(linksTab):
            self.cacheLinks[cItem['url']] = linksTab

        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("MediasetPlay.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        type = strwithmeta(videoUrl).meta.get('priv_type', '')
        if type == 'DASH/MPD':
            return getMPDLinksWithMeta(videoUrl, sortWithMaxBandwidth=999999999)
        elif type == 'HLS/M3U8':
            return getDirectM3U8Playlist(videoUrl, variantCheck=True, checkContent=True, sortWithMaxBitrate=999999999)

        return []

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []
        self.initApi()

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'list_items')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'on_air':
            self.listOnAir(self.currItem)

        elif category == 'cat_channels':
            self.listChannels(self.currItem, 'list_channel_items')

        elif category == 'list_channel_items':
            self.listChannelItems(self.currItem, 'list_time')

        elif category == 'list_time':
            self.listTime(self.currItem, 'video_mixed')

        elif category == 'cat_az':
            self.listAZFilters(self.currItem, 'list_az_items')

        elif category == 'list_az_items':
            self.listAZItems(self.currItem, 'video_mixed')

        elif category == 'list_items':
            self.listItems(self.currItem, 'video_mixed')

        elif category in ('cat_movies', 'cat_series'):
            self.listCatalog(self.currItem, 'list_catalog_items', 'video_mixed')

        elif category == 'list_catalog_items':
            self.listCatalogItems(self.currItem, 'video_mixed')

        elif category == 'video_mixed':
            self.listVideoMixed(self.currItem)

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
        CHostBase.__init__(self, MediasetPlay(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append((_("Brand"), "brand"))
        searchTypesOptions.append((_("Clip"), "clip"))
        searchTypesOptions.append((_("Episode"), "episode"))
        searchTypesOptions.append((_("Movie"), "movie"))
        return searchTypesOptions
