# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry
###################################################

###################################################
# E2 GUI COMMPONENTS
###################################################
from Screens.MessageBox import MessageBox
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.mediayou_language = ConfigSelection(default="pol", choices=[("pol", _("Polish")), ("eng", _("English")), ("ger", _("Deutsch")), ("rus", _("Russian")), ("ita", _("Italian")), ("fre", _("French"))])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("Language"), config.plugins.iptvplayer.mediayou_language))
    return optionList
###################################################


def gettytul():
    return 'https://mediayou.net/'


class MediayouNet(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'mediayou.net', 'cookie': 'mediayou.net.cookie'})

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})

        self.MAIN_URL = 'https://www.mediayou.net/'
        self.DEFAULT_ICON_URL = 'https://www.mediayou.net/web/images/mediaU_icon.png'

        self.defaultParams = {'header': self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheFilters = {}
        self.cacheFiltersKeys = []
        self.cacheLinks = {}

        self.countryCode = config.plugins.iptvplayer.mediayou_language.value

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def listMainMenu(self, cItem):
        printDBG("MediayouNet.listMainMenu")

        MAIN_CAT_TAB = [
                        {'category': 'list_items', 'title': 'TOP', 'url': self.getFullUrl('/web/getdata.php'), 'post_data': {'option': 'TOP', 'id': 'global'}},
                        {'category': 'list_items', 'title': 'Polskie', 'url': self.getFullUrl('/web/getdata.php'), 'post_data': {'option': 'RADIO_Country', 'id': '70'}},
                        {'category': 'categories', 'title': _('Countries'), 'url': self.getFullUrl('/web/getdata.php'), 'post_data': {'option': 'LOCATION', 'id': self.countryCode}, 'option': 'RADIO_Country'},
                        {'category': 'categories', 'title': _('Categories'), 'url': self.getFullUrl('/web/getdata.php'), 'post_data': {'option': 'GENRE', 'id': self.countryCode}, 'option': 'RADIO_Genre'},
                        {'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history')}]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def listCategories(self, cItem, nextCategory):
        printDBG("MediayouNet.listCategories [%s]" % cItem)

        option = cItem.get('option')
        sts, data = self.getPage(cItem['url'], post_data=cItem.get('post_data'))
        if not sts:
            return
#        printDBG("MediayouNet.listCategories data[%s]" % data)
        try:
            data = json_loads(data)['contents']
        except Exception:
            data = json_loads(data)
            printExc()

        for item in data:
            title = item['name']
            if option == 'RADIO_Country':
                post_data = {'option': option, 'id': item['loc_id']}
            elif option == 'RADIO_Genre':
                post_data = {'option': option, 'id': item['gen_id']}
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': title, 'url': cItem['url'], 'post_data': post_data})
            self.addDir(params)

    def listItems(self, cItem):
        printDBG("MediayouNet.listItems [%s]" % cItem)

        sts, data = self.getPage(cItem['url'], post_data=cItem.get('post_data'))
        if not sts:
            return
#        printDBG("MediayouNet.listItems data[%s]" % data)
        try:
            data = json_loads(data)['contents']
        except Exception:
            data = json_loads(data)
            printExc()

        for item in data:
            icon = self.getFullIconUrl('/logo/radio/%s.png' % item['rad_id'])
            title = item['rad_name']
            url = item['rad_id']

            desc = []
            params = dict(cItem)
            params.update({'good_for_fav': True, 'title': title, 'url': url, 'desc': desc, 'icon': icon})
            self.addAudio(params)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("MediayouNet.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/embedded/Search_Website.php')
        cItem['post_data'] = {'lan': 'pol', 'kw': searchPattern}
        cItem['category'] = 'list_items'
        self.listItems(cItem)

    def getLinksForVideo(self, cItem):
        printDBG("MediayouNet.getLinksForVideo [%s]" % cItem)

        cacheKey = cItem['url']
        cacheTab = self.cacheLinks.get(cacheKey, [])
        if len(cacheTab):
            return cacheTab

        self.cacheLinks = {}

        urlTab = []

        sts, data = self.getPage(self.getFullUrl('/embedded/GetUrlSub_Website.php'), post_data={'os': 'PCWEB', 'id': cItem['url']})
        if not sts:
            return []
#        printDBG("MediayouNet.getLinksForVideo data[%s]" % data)
        try:
            data = json_loads(data)['urls']
            for item in data:
                name = item['format_id']
                url = item['url']
                if url != '' and url.endswith('.pls'):
                    sts, tmp = self.getPage(url)
                    if not sts:
                        return []
                    if sts:
                        tmp = re.compile('''(File[0-9]+?)=(https?://.+)''').findall(tmp)
                        for pitem in tmp:
                            urlTab.append({'name': 'pls' + pitem[0], 'url': pitem[1], 'need_resolve': 0})
                else:
                    urlTab.append({'url': url, 'name': name, 'need_resolve': 0})
        except Exception:
            printExc()

        if len(urlTab):
            self.cacheLinks[cacheKey] = urlTab
        return urlTab

    def getVideoLinks(self, baseUrl):
        printDBG("eKinomaniak.getVideoLinks [%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        urlTab = []

        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if baseUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name'] + '*'
                        break

        return self.up.getVideoLinkExt(baseUrl)

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode = self.currItem.get("mode", '')

        printDBG("handleService: || name[%s], category[%s] " % (name, category))
        self.currList = []
        self.currItem = dict(self.currItem)
        self.currItem.pop('good_for_fav', None)

    #MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})

        elif category == 'categories':
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
        CHostBase.__init__(self, MediayouNet(), True, favouriteTypes=[])
