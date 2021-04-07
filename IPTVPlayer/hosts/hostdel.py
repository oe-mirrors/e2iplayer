# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
###################################################

def gettytul():
    return 'https://del.org/'

class Del(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'del.org', 'cookie': 'del.org.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='iphone_3_0')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://www.del.org/'
        self.MAIN_URL_2 = 'https://www.del-2.org/'
        self.DEFAULT_ICON_URL = self.MAIN_URL + 'assets/img/DEL_Logo.png'

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMain(self, cItem):
        printDBG("Del.listMain")
        MAIN_CAT_TAB = [{'category': 'del', 'title': self.MAIN_URL, 'url': self.MAIN_URL, 'icon': self.DEFAULT_ICON_URL},
                        {'category': 'del2', 'title': self.MAIN_URL_2, 'url': self.MAIN_URL_2, 'icon': self.MAIN_URL_2 + 'images/background/logo.png'}, ]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def del2Filters(self, cItem, nextCategory):
        printDBG("Del.fillCacheFilters")
        sts, data = self.getPage(cItem['url'] + 'videos/')
        if not sts:
            return

        data = ph.find(data, ('<div', '>', 'select_rechts'), '</div>', flags=0)[1]
        data = ph.findall(data, ('<option', '>'), '</option>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            url = self.cm.getFullUrl(ph.getattr(data[idx - 1], 'value'), self.cm.meta['url'])
            title = self.cleanHtmlStr(data[idx])
            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url}))

    def listDel2(self, cItem):
        printDBG("Del.listDel2")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        data = ph.find(data, ('<h3', '>', 'sectionHead'), ('<script', '>'))[1]
        data = ph.rfindall(data, '</div>', ('<h3', '>', 'sectionHead'))
        for section in data:
            sTitle = self.cleanHtmlStr(ph.find(section, ('<span', '>'), '</span>', flags=0)[1])
            section = ph.rfindall(section, '</div>', ('<div', '>', 'item'))
            subItems = []
            for item in section:
                url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
                icon = self.cm.getFullUrl(ph.getattr(item, 'src'), self.cm.meta['url'])
                title = self.cleanHtmlStr(ph.getattr(item, 'title'))

                desc = []
                tmp = [ph.find(item, ('<div', '>', 'duration'), '</div>', flags=0)[1]]
                tmp.extend(ph.findall(item, ('<p', '>'), '</p>', flags=0))
                for t in tmp:
                    t = self.cleanHtmlStr(t)
                    if t:
                        desc.append(t)

                subItems.append({'good_for_fav': True, 'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': ' | '.join(desc)})

            if len(subItems):
                self.addDir(MergeDicts(cItem, {'title': sTitle, 'category': 'sub_items', 'sub_items': subItems}))

    def listDel(self, cItem):
        printDBG("Del.listDel")
        page = cItem.get('page', 1)
        sts, data = self.getPage('https://www.del.org/ajax.php?cmd=loadmorevideos&videotype=5&page=%s' % page)
        if not sts:
            return

        data = ph.findall(data, ('<article ', '>'), '</article>', flags=0)
        for item in data:

            url = self.cm.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1], self.cm.meta['url'])
            icon = self.cm.getFullUrl(ph.getattr(item, 'src'), self.cm.meta['url'])
            title = self.cleanHtmlStr(ph.find(item, ('<h4', '>'), '</h4>', flags=0)[1])

            desc = []
            tmp = [ph.find(item, ('<h3', '>'), '</h3>', flags=0)[1], ph.find(item, ('<h3', '>', 'duration'), '</pretitle>', flags=0)[1]]
            for t in tmp:
                t = self.cleanHtmlStr(t)
                if t:
                    desc.append(t)
            desc = ' | '.join(desc) + '[/br]' + self.cleanHtmlStr(ph.find(item, ('<p', '>'), '</p>', flags=0)[1])

            self.addVideo({'good_for_fav': True, 'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': desc})

        if len(self.currList):
            self.addDir(MergeDicts(cItem, {'title': _('Next page'), 'page': page + 1}))

    def listSubItems(self, cItem):
        printDBG("Del.listSubItems")
        self.currList = cItem['sub_items']

    def getLinksForVideo(self, cItem):
        urlsTab = []

        rm(self.COOKIE_FILE)
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return []

        tmp = ph.find(data, ('<glomex-player', '>'))[1]
        if tmp:
            player_id = ph.getattr(tmp, 'data-player-id')
            playlist_id = ph.getattr(tmp, 'data-playlist-id')
            url = 'https://integration-cloudfront-eu-west-1.mes.glomex.cloud/?integration_id=%s&playlist_id=%s&current_url=' % (player_id, playlist_id)
            sts, data = self.getPage(url)
            if not sts:
                return []
            try:
                data = json_loads(data)['videos'][0]['source']
                if data.get('hls'):
                    hlsUrl = self.cm.getFullUrl(data['hls'], self.cm.meta['url'])
                    urlsTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999, mergeAltAudio=True)
                    if len(urlsTab):
                        urlsTab.append({'name': 'Variable M3U8/HLS', 'url': hlsUrl, 'need_resolve': 0})

                # progressive links seem do not work why?
                if False and data.get('progressive'):
                    mp4Url = self.cm.getFullUrl(data['progressive'], self.cm.meta['url'])
                    urlsTab.append({'name': 'progressive mp4', 'url': mp4Url, 'need_resolve': 0})
            except Exception:
                printExc()
        else:
            urlParams = dict(self.defaultParams)
            urlParams['header'] = MergeDicts(urlParams['header'], {'Referer': self.cm.meta['url']})
            urlParams['raw_post_data'] = True
            urlParams['use_new_session'] = True

            playerData = ph.find(data, 'getPlayer(', ');', flags=0)[1].split(',')
            printDBG("playerData <<< %s" % playerData)
            if len(playerData) == 6:
                url = self.cm.getFullUrl('/videoplayer/playerhls.php?play=%s&key=%d&identifier=web&v5partner=%s&autoplay=true&event' % (playerData[1].strip(), int(time.time() * 1000), playerData[3].strip()), self.cm.meta['url'])
                sts, data = self.getPage(url, urlParams)
                urlParams['header'] = MergeDicts(urlParams['header'], {'Referer': self.cm.meta['url']})

                url = self.cm.getFullUrl('/server/videoConfig.php?videoid=%s&partnerid=%s&language=%s&format=iphone' % (playerData[1].strip(), playerData[3].strip(), playerData[5].strip()[1:-1]), self.cm.meta['url'])
                sts, data = self.getPage(url, urlParams)
                try:
                    url = json_loads(data)['video']['streamAccess']
                    url = self.cm.getFullUrl(url, self.cm.meta['url'])
                    sts, data = self.getPage(url, urlParams, '[""]')
                    try:
                        printDBG("++++")
                        printDBG(data)
                        printDBG("++++")
                        data = json_loads(data)['data']['stream-access']
                        for url in data:
                            sts, streamData = self.getPage(self.cm.getFullUrl(url, self.cm.meta['url']), urlParams)
                            if not sts:
                                continue
                            printDBG("?----?")
                            printDBG(data)
                            printDBG("?----?")
                            token = ph.getattr(streamData, 'auth')
                            hlsUrl = self.cm.getFullUrl(ph.getattr(streamData, 'url'), self.cm.meta['url']) + '?hdnea=' + token
                            urlsTab = getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999, mergeAltAudio=True)
                            break
                    except Exception:
                        printExc()
                except Exception:
                    printExc()
        return urlsTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'})

        elif category == 'del':
            self.listDel(self.currItem)

        elif category == 'del2':
            self.del2Filters(self.currItem, 'list_del2')

        elif category == 'list_del2':
            self.listDel2(self.currItem)

        elif category == 'list_popular':
            self.listPopular(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Del(), False, [])

