# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, CSelOneLink, GetLogoDir, byteify
import Plugins.Extensions.IPTVPlayer.libs.urlparser as urlparser
###################################################

###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################


###################################################
# E2 GUI COMMPONENTS
###################################################
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.tvjworg_language = ConfigSelection(default="default", choices=[("default", _("Default")), ("P", _("Polish")), ("E", _("English"))])
config.plugins.iptvplayer.tvjworg_icontype = ConfigSelection(default="vertical", choices=[("vertical", _('vertical')), ("horizontal", _('horizontal'))])
config.plugins.iptvplayer.tvjworg_default_format = ConfigSelection(default="720", choices=[("0", _("the worst")),
                                                                                               ("240", "240p"),
                                                                                               ("360", "360p"),
                                                                                               ("480", "480p"),
                                                                                               ("720", "720p"),
                                                                                               ("99999999", "the best")])
config.plugins.iptvplayer.tvjworg_use_df = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language"), config.plugins.iptvplayer.tvjworg_language))
    optionList.append(getConfigListEntry(_("Default video quality"), config.plugins.iptvplayer.tvjworg_default_format))
    optionList.append(getConfigListEntry(_("Use default video quality"), config.plugins.iptvplayer.tvjworg_use_df))
    optionList.append(getConfigListEntry(_("Icon type"), config.plugins.iptvplayer.tvjworg_icontype))
    return optionList
###################################################


def gettytul():
    return 'https://tv.jw.org/'


class TVJWORG(CBaseHostClass):
    HTTP_HEADER = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}
    MAIN_URL = 'http://mediator.jw.org/v1/'
    DEFAULT_ICON = 'https://s-media-cache-ak0.pinimg.com/236x/3b/aa/32/3baa3268cdbc9dc5114bbe1ab0b00ce0.jpg'

    ICONS_KEYS = ["xl", "lg", "md", "sm", "xs"]
    ICONS_TYPES = {'vertical': ['pss', 'psr', 'sqr', 'sqs'], 'horizontal': ['lsr', 'lss', 'wss', 'wsr', 'pnr']}

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'filmydokumentalne.eu', 'cookie': 'filmydokumentalne.eu.cookie'})
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheCats = {}
        self.defaultLangCode = ''

    def _getFullUrl(self, url, api=True):
        baseUrl = self.MAIN_URL
        if 0 < len(url):
            if url.startswith('//'):
                url = 'http:' + url
            elif not url.startswith('http'):
                url = baseUrl + url
        if not baseUrl.startswith('https://'):
            url = url.replace('https://', 'http://')
        return url

    def cleanHtmlStr(self, data):
        data = data.replace('&nbsp;', ' ')
        data = data.replace('&nbsp', ' ')
        return CBaseHostClass.cleanHtmlStr(data)

    def listsTab(self, tab, cItem, type='dir'):
        printDBG("TVJWORG.listsTab")
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if type == 'dir':
                self.addDir(params)
            else:
                self.addVideo(params)

    def _getIcon(self, iconItem):
        icon = ''
        try:
            imageTypes = self.ICONS_TYPES.get(config.plugins.iptvplayer.tvjworg_icontype.value, [])
            images = iconItem['images']
            for icontype in imageTypes:
                if icontype not in images:
                    continue
                icons = images[icontype]
                for item in self.ICONS_KEYS:
                    if item not in icons:
                        continue
                    icon = str(icons[item])
                    if icon.startswith('http'):
                        break
                    else:
                        icon = ''
                if icon.startswith('http'):
                    break
        except Exception:
            printExc()
        if '' == icon:
            icon = self.DEFAULT_ICON
        return icon

    def _getLangCode(self):
        langCode = 'E'
        if config.plugins.iptvplayer.tvjworg_language.value == 'default':
            if self.defaultLangCode != '':
                return self.defaultLangCode
            else:
                sts, data = self.cm.getPage(self._getFullUrl('languages/E/web'))
                if sts:
                    try:
                        lang = GetDefaultLang()
                        data = byteify(json.loads(data))
                        for item in data['languages']:
                            if item['locale'] == lang:
                                self.defaultLangCode = str(item['code'])
                                langCode = self.defaultLangCode
                                break
                    except Exception:
                        printExc()
        else:
            langCode = config.plugins.iptvplayer.tvjworg_language.value
        return langCode

    def listCategories(self, cItem, sub=''):
        printDBG("TVJWORG.listCategories")

        if 'key' in cItem:
            baseUrl = 'categories/%s/%s?detailed=1' % (self._getLangCode(), cItem['key'])
        else:
            baseUrl = 'categories/' + self._getLangCode()
        url = self._getFullUrl(baseUrl)

        sts, data = self.cm.getPage(url)
        if not sts:
            return
        try:
            data = byteify(json.loads(data))
            if sub != '':
                data = data['category'][sub]
            else:
                data = data['categories']
            for item in data:
                icon = self._getIcon(item)
                key = item['key']
                title = item['name']
                category = item['type']
                desc = item['description']
                params = dict(cItem)
                params.update({'category': category, 'key': key, 'title': title, 'icon': icon, 'desc': desc})
                self.addDir(params)
        except Exception:
            printExc()

    def listMedia(self, cItem):
        printDBG("TVJWORG.listMedia")

        baseUrl = 'categories/%s/%s?detailed=1' % (self._getLangCode(), cItem['key'])
        url = self._getFullUrl(baseUrl)

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        try:
            data = byteify(json.loads(data))
            for item in data['category']['media']:
                icon = self._getIcon(item)
                title = item['title']
                duration = item['durationFormattedHHMM']
                if len(duration):
                    title += ' [%s]' % duration
                type = item['type']
                date = item['firstPublished']
                if len(date):
                    desc = date + '[/br]'
                else:
                    desc = ''
                desc += item['description']
                files = item['files']
                params = {'title': title, 'icon': icon, 'desc': desc, 'files': files}
                if type == 'video':
                    self.addVideo(params)
                elif type == 'audio':
                    self.addAudio(params)
                else:
                    params['title'] += '  COS ZLE SPRAWDZ type[%s]' % type
                    self.addVideo(params)
        except Exception:
            printExc()

    def listPseudoStreaming(self, cItem):
        printDBG("TVJWORG.listPseudoStreaming")

        baseUrl = 'schedules/%s/%s?utcOffset=60' % (self._getLangCode(), cItem['key'])
        url = self._getFullUrl(baseUrl)

        sts, data = self.cm.getPage(url)
        if not sts:
            return

        try:
            data = byteify(json.loads(data))
            for item in data['category']['media']:
                icon = self._getIcon(item)
                title = item['title']
                duration = item['durationFormattedHHMM']
                if len(duration):
                    title += ' [%s]' % duration
                type = item['type']
                date = item['firstPublished']
                if len(date):
                    desc = date + '[/br]'
                else:
                    desc = ''
                desc += item['description']
                files = item['files']
                params = {'title': title, 'icon': icon, 'desc': desc, 'files': files}
                if type == 'video':
                    self.addVideo(params)
                elif type == 'audio':
                    self.addAudio(params)
                else:
                    params['title'] += '  COS ZLE SPRAWDZ type[%s]' % type
                    self.addVideo(params)
        except Exception:
            printExc()

    def getLinksForVideo(self, cItem):
        printDBG("TVJWORG.getLinksForVideo [%s]" % cItem)
        urlTab = []

        try:
            tmpTab = cItem.get('files', [])
            for item in tmpTab:
                try:
                    linkVideo = item['progressiveDownloadURL']
                    linkVideo = urlparser.decorateUrl(linkVideo, {'Referer': 'http://tv.jw.org/'})
                    urlTab.append({'name': item['label'], 'url': linkVideo, 'need_resolve': 0})
                except Exception:
                    printExc()

            if 1 < len(urlTab):
                error = False
                max_bitrate = int(config.plugins.iptvplayer.tvjworg_default_format.value)

                def __getLinkQuality(itemLink):
                    try:
                        return int(itemLink['name'][0:-1])
                    except Exception:
                        error = True
                        return 0
                oneLink = CSelOneLink(urlTab, __getLinkQuality, max_bitrate)
                if not error and config.plugins.iptvplayer.tvjworg_use_df.value:
                    urlTab = oneLink.getOneLink()
                else:
                    urlTab = oneLink.getSortedLinks()
        except Exception:
            printExc()

        return urlTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listCategories({'name': 'category'})
        elif category == 'ondemand':
            self.listMedia(self.currItem)
        elif category == 'pseudostreaming':
            self.listPseudoStreaming(self.currItem)
        elif category == 'container':
            self.listCategories(self.currItem, 'subcategories')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, TVJWORG(), True, []) #[CDisplayListItem.TYPE_VIDEO, CDisplayListItem.TYPE_AUDIO]

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('tvjworglogo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        retCode = RetHost.ERROR
        retlist = []
        if not self.isValidIndex(Index):
            return RetHost(retCode, value=retlist)

        urlList = self.host.getLinksForVideo(self.host.currList[Index])
        for item in urlList:
            retlist.append(CUrlItem(item["name"], item["url"], item['need_resolve']))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def converItem(self, cItem):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie

        hostLinks = []
        type = CDisplayListItem.TYPE_UNKNOWN
        possibleTypesOfSearch = None

        if 'category' == cItem['type']:
            if cItem.get('search_item', False):
                type = CDisplayListItem.TYPE_SEARCH
                possibleTypesOfSearch = searchTypesOptions
            else:
                type = CDisplayListItem.TYPE_CATEGORY
        elif cItem['type'] == 'video':
            type = CDisplayListItem.TYPE_VIDEO
        elif 'more' == cItem['type']:
            type = CDisplayListItem.TYPE_MORE
        elif 'audio' == cItem['type']:
            type = CDisplayListItem.TYPE_AUDIO

        if type in [CDisplayListItem.TYPE_AUDIO, CDisplayListItem.TYPE_VIDEO]:
            url = cItem.get('url', '')
            if '' != url:
                hostLinks.append(CUrlItem("Link", url, 1))

        title = cItem.get('title', '')
        description = cItem.get('desc', '')
        icon = cItem.get('icon', '')

        return CDisplayListItem(name=title,
                                    description=description,
                                    type=type,
                                    urlItems=hostLinks,
                                    urlSeparateRequest=1,
                                    iconimage=icon,
                                    possibleTypesOfSearch=possibleTypesOfSearch)
    # end converItem

    def getSearchItemInx(self):
        try:
            list = self.host.getCurrList()
            for i in range(len(list)):
                if list[i]['category'] == 'search':
                    return i
        except Exception:
            printDBG('getSearchItemInx EXCEPTION')
            return -1

    def setSearchPattern(self):
        try:
            list = self.host.getCurrList()
            if 'history' == list[self.currIndex]['name']:
                pattern = list[self.currIndex]['title']
                search_type = list[self.currIndex]['search_type']
                self.host.history.addHistoryItem(pattern, search_type)
                self.searchPattern = pattern
                self.searchType = search_type
        except Exception:
            printDBG('setSearchPattern EXCEPTION')
            self.searchPattern = ''
            self.searchType = ''
        return
