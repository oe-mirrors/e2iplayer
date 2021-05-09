# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import urllib
from hashlib import sha1
from datetime import timedelta
###################################################


def gettytul():
    return 'https://7tv.de/'


class C7tvDe(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': '7tv.de', 'cookie': '7tv.de.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL = 'https://www.7tv.de/'
        self.DEFAULT_ICON_URL = 'https://s.p7s1.io/xfiles/7tv/android-icon-192x192.png'

        self.cacheLinks = {}
        self.channelsMap = {'titles': {'kabel1doku': 'kabel eins Doku', 'pro7': 'ProSieben', 'kabel1': 'Kabeleins'}, 'order': {'kabel1doku': 10, 'pro7': 1, 'kabel1': 3}}

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, curUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace(' ', '%20'), curUrl)

    def listMain(self, cItem, nextCategory):
        printDBG("C7tvDe.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        MAIN_CAT_TAB = [{'category': 'programs', 'title': 'Sendungen A-Z', 'url': self.getFullUrl('/sendungen-a-z')},
                        {'category': 'missed', 'title': 'Sendung verpasst', 'url': self.getFullUrl('/sendung-verpasst')},
                        {'category': 'channels', 'title': 'Sender', 'url': self.getMainUrl()},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listMissed(self, cItem, nextCategory):
        printDBG("C7tvDe.listMissed")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = ph.find(data, ('<ul', '>', 'site-nav-submenu'), '</ul>', flags=0)[1]
        tmp = ph.findall(tmp, ('<li', '>'), '</li>', flags=0)
        for idx, item in enumerate(tmp, 1):
            channel = ph.getattr(item, 'href').rsplit('/', 1)[-1]
            self.channelsMap['titles'][channel] = ph.clean_html(item)
            self.channelsMap['order'][channel] = idx

        data = ph.find(data, ('<ul', '>', 'tab-list'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.getattr(item, 'data-href'))
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'url': url, 'title': title}))

    def listChannels(self, cItem, nextCategory):
        printDBG("C7tvDe.listChannels")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = ph.find(data, ('<ul', '>', 'brandgrid'), '</ul>', flags=0)[1]
        data = ph.findall(data, ('<li', '>'), '</li>', flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            self.addDir(MergeDicts(cItem, {'category': nextCategory, 'url': url, 'title': title}))

    def listProgramsMenu(self, cItem, nextCategory1, nextCategory2):
        printDBG("C7tvDe.listProgramsMenu")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = ph.find(data, ('<nav', '>', 'tvshow-nav'), '</nav>', flags=0)[1]
        data = data.split('</ul>')[:-1]
        for sData in data:
            subItems = []
            sTitle = ph.clean_html(ph.find(sData, ('<h3', '>'), '</h3>', flags=0)[1])
            sData = ph.findall(sData, ('<a', '>'), '</a>', flags=ph.START_S)
            for idx in range(1, len(sData), 2):
                url = self.getFullUrl(ph.getattr(sData[idx - 1], 'data-href'))
                title = ph.clean_html(sData[idx])
                if url:
                    subItems.append(MergeDicts(cItem, {'url': url, 'title': title, 'category': nextCategory2}))
                else:
                    subItems.append(MergeDicts(cItem, {'title': title, 'category': nextCategory1}))
            if not sTitle:
                self.currList.extend(subItems)
            else:
                self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'sub_items': subItems, 'title': sTitle}))

    def listABC(self, cItem, nextCategory):
        printDBG("C7tvDe.listABC")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        try:
            data = json_loads(data)
            for letter, value in data['facet'].iteritems():
                if letter == '#':
                    letter = '0-9'
                if value:
                    title = '%s (%s)' % (letter.upper(), value)
                    url = cUrl + '/(letter)/%s' % letter
                    self.addDir(MergeDicts(cItem, {'category': nextCategory, 'url': url, 'title': title, 'letter': letter}))
            self.currList.sort(key=lambda k: k['letter'].decode('utf-8'))
        except Exception:
            printExc()

    def listABCItems(self, cItem, nextCategory):
        printDBG("C7tvDe.listABCItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']
        try:
            data = json_loads(data)
            for item in data['entries']:
                if item['type'] == 'tvShow':
                    category = nextCategory
                else:
                    category = nextCategory
                try:
                    icon = self.getFullIconUrl(item['images'][0]['url'])
                except Exception:
                    icon = ''
                desc = ' | '.join(item.get('relatedProviders', []))
                self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': category, 'url': self.getFullUrl(item['url']), 'icon': icon, 'title': str(item['title']), 'desc': desc}))
        except Exception:
            printExc()

    def listMissedItems(self, cItem, nextCategory):
        printDBG("C7tvDe.listMissedItems")
        titlesMap = {} #{'pro7':'', 'sat1':'', 'kabel1':'', 'sixx':'', 'prosiebenmaxx':'', 'sat1gold':'', 'kabel1doku':'', 'dmax':'', 'tlc':'', 'eurosport':''}

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        cUrl = self.cm.meta['url']

        try:
            data = json_loads(data)
            channels = list(data['entries'].keys())
            channels.sort(key=lambda k: self.channelsMap['order'].get(k, 20))

            for channel in channels:
                cData = data['entries'][channel]
                sTitle = self.channelsMap['titles'].get(channel, channel)
                subItems = []
                for item in cData:
                    desc = [cItem['title'], item['airtime']]
                    try:
                        desc.append(str(timedelta(seconds=item['duration'] / 1000)))
                    except Exception:
                        pass
                    if item['subType'] == "episode":
                        title = '%s: ' % (item['metadata']['tvShowTitle'])
                    title += item['title']
                    icon = self.getFullIconUrl(item['url'] + '?fake=need_resolve.jpeg')
                    url = self.getFullUrl(item['url'])
                    params = MergeDicts(cItem, {'good_for_fav': True, 'url': url, 'icon': icon, 'title': title, 'desc': ' | '.join(desc)})
                    if item['type'] == 'video':
                        params['type'] = 'video'
                        subItems.append(params)
                    else:
                        params['category'] = nextCategory
                        subItems.append(params)

                if len(subItems):
                    self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'sub_items': subItems, 'title': sTitle}))
        except Exception:
            printExc()

    def listSubItems(self, cItem):
        printDBG("C7tvDe.listSubItems")
        self.currList = cItem['sub_items']

    def listItems(self, cItem, nextCategory):
        printDBG("C7tvDe.listItems")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])
        self.currList = self.getItems(cItem, nextCategory, data)

    def getItems(self, cItem, nextCategory, data):
        retList = []
        sTitle = ph.clean_html(ph.find(data, ('<span', '>', 'format-header_title'), '</span>', flags=0)[1])
        data = ph.findall(data, ('<article', '>', 'teaser'), '</article>', flags=ph.START_S)
        for idx in range(1, len(data), 2):
            item = data[idx]
            url = ph.search(item, ph.A)[1]
            icon = self.getFullIconUrl(ph.getattr(item, 'data-src'))
            desc = ph.clean_html(ph.find(item, ('<div', '>', 'caption'), '</div>', flags=0)[1])
            title = ph.clean_html(ph.find(item, ('<h5', '>', 'title'), '</h5>', flags=0)[1])
            if title == '':
                title = url.rsplit('/', 1)[-1].replace('-', ' ').decode('utf-8').title().encode('utf-8')
            desc = [desc] if desc else []
            desc.append(ph.clean_html(ph.find(item, ('<p', '>'), '</p>', flags=0)[1]))
            if sTitle:
                title = '%s: %s' % (sTitle, title)
            params = MergeDicts(cItem, {'good_for_fav': True, 'title': title, 'url': self.getFullUrl(url), 'icon': icon, 'desc': '[/br]'.join(desc)})
            if 'class-clip' in data[idx - 1]: # and '-clip' in url:
                params.update({'type': 'video'})
            else:
                params.update({'category': nextCategory})
            retList.append(params)
        return retList

    def exploreItem(self, cItem, nextCategory):
        printDBG("C7tvDe.exploreItem")
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        tmp = ph.find(data, 'var contentResources = [', '];', flags=0)[1]
        try:
            tmp = json_loads('[%s]' % tmp)
            for item in tmp:
                icon = self.getFullIconUrl(item.get('poster', ''))
                desc = []
                try:
                    desc.append(str(timedelta(seconds=item['duration'])))
                except Exception:
                    printExc()
                try:
                    desc.append(item['teaser']['description'])
                except Exception:
                    printExc()
                self.addVideo(MergeDicts(cItem, {'good_for_fav': False, 'title': item['title'], 'item_data': item, 'icon': icon, 'desc': '[/br]'.join(desc)}))
        except Exception:
            printExc()
            return []

        if not cItem.get('sub_menu_item'):
            tmp = ph.find(data, ('<article', '>', 'class-clip'))[1]
            if not tmp:
                return

            data = ph.find(data, ('<ul', '>', 'format-nav-list'), '</ul>', flags=0)[1]
            data = ph.findall(data, ('<a', '>'), '</a>', flags=ph.START_S)
            for idx in range(1, len(data), 2):
                url = self.getFullUrl(ph.getattr(data[idx - 1], 'href'))
                if '7tv.de' not in self.cm.getBaseUrl(url, True):
                    continue
                title = self.cleanHtmlStr(data[idx])
                self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'sub_menu_item': True, 'category': nextCategory, 'title': title, 'url': url}))

            if len(self.currList) == 1 and self.currList[0]['type'] != 'video':
                item = self.currList.pop()
                self.listItems(item, 'explore_item')

    def listSearchResult(self, cItem, searchPattern, searchType):
        url = self.getFullUrl('/7tvsearch/search/(query)/%s/(type)/%s/(offset)/{0}/(limit)/{0}' % (urllib.quote(searchPattern), searchType))
        cItem = MergeDicts(cItem, {'category': 'search_next', 'url': url})
        self.listSearchResultNext(cItem, 'explore_item')

    def listSearchResultNext(self, cItem, nextCategory):
        ITEMS_NUM = 6
        page = cItem.get('page', 0)
        url = cItem['url'].format(page * ITEMS_NUM, ITEMS_NUM)
        params = MergeDicts(cItem, {'url': url})
        self.listItems(params, nextCategory)
        if len(self.currList) == ITEMS_NUM:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'page': page + 1}))

    def getLinksForVideo(self, cItem, source_id=None):
        linksTab = []

        if 'item_data' not in cItem:
            sts, data = self.getPage(cItem['url'])
            if not sts:
                return
            client_location = self.cm.meta['url']
            data = ph.find(data, 'var contentResources = [', '];', flags=0)[1]
            try:
                data = json_loads('[%s]' % data)[0]
            except Exception:
                pass
        else:
            client_location = cItem['url']
            data = cItem['item_data']

        try:
            drm = data.get('drm')
            if drm:
                SetIPTVPlayerLastHostError(_('Link protected with DRM.'))
            video_id = data['id']
        except Exception:
            printExc()
            return []

        #dashLinks = self.doGetLinks(video_id, client_location, 'application/dash+xml')
        try:
            for it in (False, True):
                hlsLinks = self.doGetLinks(video_id, client_location, 'application/x-mpegURL', it)
                if hlsLinks:
                    linksTab.extend(getDirectM3U8Playlist(hlsLinks[0]['url'], checkExt=True, checkContent=True, sortWithMaxBitrate=999999999))
                    break

            for it in (True, False):
                mp4Links = self.doGetLinks(video_id, client_location, 'video/mp4', it)
                for item in mp4Links:
                    if item['mimetype'] == 'video/mp4':
                        linksTab.append({'name': '[MP4] bitrate: %s' % item['bitrate'], 'url': item['url'], 'bitrate': item['bitrate']})
                if mp4Links:
                    break
            if not mp4Links and drm:
                return []
            linksTab.sort(reverse=True, key=lambda k: int(k['bitrate']))
        except Exception:
            printExc()

        return linksTab

    def doGetLinks(self, video_id, client_location, mimetype, web=False):
        linksTab = []
        try:
            if web:
                access_token = 'h''b''b''t''v'
                salt = '0''1''r''e''e''6''e''L''e''i''w''i''u''m''i''e''7''i''e''V''8''p''a''h''g''e''i''T''u''i''3''B'
                client_name = 'h''b''b''t''v'
            else:
              access_token = 'seventv-web'
              salt = '01!8d8F_)r9]4s[qeuXfP%'
              client_name = ''

            json_url = 'http://vas.sim-technik.de/vas/live/v2/videos/%s?access_token=%s&client_location=%s&client_name=%s' % (video_id, access_token, client_location, client_name)
            sts, json_data = self.getPage(json_url)
            if not sts:
                return []
            printDBG(json_data)
            printDBG("++++++++++++++++++++")
            json_data = json_loads(json_data)

            source_id = -1
            for stream in json_data['sources']:
                if stream['mimetype'] == mimetype and int(source_id) < int(stream['id']):
                    source_id = stream['id']

            if source_id < 0:
                return []

            client_id_1 = salt[:2] + sha1(''.join([str(video_id), salt, access_token, client_location, salt, client_name]).encode('utf-8')).hexdigest()

            json_url = 'http://vas.sim-technik.de/vas/live/v2/videos/%s/sources?access_token=%s&client_location=%s&client_name=%s&client_id=%s' % (video_id, access_token, client_location, client_name, client_id_1)
            sts, json_data = self.getPage(json_url)
            if not sts:
                return []
            printDBG(json_data)
            printDBG("++++++++++++++++++++")
            json_data = json_loads(json_data)
            server_id = json_data['server_id']

            #client_name = 'kolibri-1.2.5'
            client_id = salt[:2] + sha1(''.join([salt, video_id, access_token, server_id, client_location, str(source_id), salt, client_name]).encode('utf-8')).hexdigest()
            url_api_url = 'http://vas.sim-technik.de/vas/live/v2/videos/%s/sources/url?%s' % (video_id, urllib.urlencode({
                'access_token': access_token,
                'client_id': client_id,
                'client_location': client_location,
                'client_name': client_name,
                'server_id': server_id,
                'source_ids': str(source_id),
            }))

            tries = 0
            while tries < 2:
                tries += 1
                if tries == 2:
                    url = 'http://savansec.de/browse.php?u={0}&b=0&f=norefer'.format(urllib.quote(url_api_url))
                    params = dict(self.defaultParams)
                    params['header'] = dict(params['header'])
                    params['header']['Referer'] = url
                else:
                    params = self.defaultParams
                    url = url_api_url

                sts, json_data = self.getPage(url, params)
                if not sts:
                    return []

                printDBG(json_data)
                printDBG("++++++++++++++++++++")
                printDBG(json_data)
                json_data = json_loads(json_data)
                if json_data.get("status_code") != 12:
                    break

            return json_data["sources"]
        except Exception:
            printExc()
        return linksTab

    def getVideoLinks(self, videoUrl):
        printDBG("C7tvDe.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']

        return [{'name': 'direct', 'url': videoUrl}]

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'list_items')

        elif category == 'programs':
            self.listProgramsMenu(self.currItem, 'list_items', 'list_abc')

        elif category == 'list_abc':
            self.listABC(self.currItem, 'list_abc_items')

        elif category == 'list_abc_items':
            self.listABCItems(self.currItem, 'explore_item')

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

        elif category == 'list_items':
            self.listItems(self.currItem, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem, 'list_items')

        elif category == 'channels':
            self.listChannels(self.currItem, 'list_items')

        elif category == 'missed':
            self.listMissed(self.currItem, 'list_missed_items')

        elif category == 'list_missed_items':
            self.listMissedItems(self.currItem, 'explore_item')
    #SEARCH
        elif category == 'search':
            self.listSearchResult(MergeDicts(self.currItem, {'search_item': False, 'name': 'category'}), searchPattern, searchType)
        elif category == 'search_next':
            self.listSearchResultNext(self.currItem, 'explore_item')
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, C7tvDe(), True, [])

    def getSearchTypes(self):
        searchTypesOptions = []
        searchTypesOptions.append(("Sendungen", "format"))
        searchTypesOptions.append(("Ganze Folgen", "episode"))
        searchTypesOptions.append(("Clips", "clip"))
        return searchTypesOptions
