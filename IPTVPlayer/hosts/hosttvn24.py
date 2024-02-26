# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass, CDisplayListItem, ArticleContent, RetHost, CUrlItem
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetLogoDir
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, getConfigListEntry
###################################################


###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.TVN24httpType = ConfigSelection(default="http://", choices=[("http://", "http://"), ("https://", "https://")])


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Typ połączenia:", config.plugins.iptvplayer.TVN24httpType))
    return optionList
###################################################


def gettytul():
    return 'TVN 24'


class Tvn24(CBaseHostClass):
    HOST = 'Apache-HttpClient/UNAVAILABLE (java 1.4)'
    API_KEY = '70487a5562bef96d33225a1df16ec081'
    MAIN_URL = 'http://api.tvn24.pl'
    ITEMS_PER_PAGE = '20'

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'SeansikTV'})

    def getStr(self, v, default=''):
        if None == v:
            v = default
        return ensure_str(v)

    def converUrl(self, url):
        if "http://" == config.plugins.iptvplayer.TVN24httpType.value and url.startswith("https://"):
            return "http" + url[5:]
        return url

    def getIconFromRelated(self, item):
        # get icon
        icon = ''
        if None != item:
            try:
                icon = self.getStr(item['Main_Content_Photo']['url'])
            except Exception:
                pass
            if '' == icon:
                try:
                    icon = self.getStr(item['Photo_Photo']['url'])
                except Exception:
                    pass
            if '' == icon:
                try:
                    icon = self.getStr(item['Headbg_Photo']['url'])
                except Exception:
                    pass
        return icon

    def listsMainMenu(self):
        printDBG('listsMainMenu')

        VIDEO_PLAYLIST = Tvn24.MAIN_URL + '/video/playlists/' + Tvn24.API_KEY
        MAIN_CATEGORIES = [
            {'name': 'category', 'title': 'Najnowsze', 'category': 'end_cat', 'url': Tvn24.MAIN_URL + '/articles/newest/' + Tvn24.API_KEY + '/20'},
            {'name': 'category', 'title': 'Najważniejsze', 'category': 'end_cat', 'url': Tvn24.MAIN_URL + '/articles/important/' + Tvn24.API_KEY},
            {'name': 'category', 'title': 'Informacje', 'category': 'playlist', 'url': VIDEO_PLAYLIST + '/1'},
            {'name': 'category', 'title': 'Magazyny', 'category': 'magazines', 'url': Tvn24.MAIN_URL + '/magazines/' + Tvn24.API_KEY + '/', 'page': '1'},
            {'name': 'category', 'title': 'Kategorie', 'category': 'categories', 'url': Tvn24.MAIN_URL + '/categories/' + Tvn24.API_KEY},
            ]
        for item in MAIN_CATEGORIES:
            self.addDir(item)

    def listPlaylists(self, url):
        printDBG("listPlaylist url[%s]" % (url))
        try:
            sts, data = self.cm.getPage(url, {'host': Tvn24.HOST})
            data = json_loads(data)
            for item in data:
                title = self.getStr(item.get('title', ''))
                plot = self.getStr(item.get('description', ''))
                icon = self.getStr(item.get('pht_url', ''))
                videosNum = int(self.getStr(item.get('videos_count', '0'), '0'))

                if videosNum > 0:
                    videos = item.get('videos', [])
                    if len(videos) > 0:
                        params = {'name': 'category', 'title': title, 'plot': plot, 'icon': icon, 'videos': list(videos), 'category': 'end_playlist', 'url': ''}
                        self.addDir(params)
        except Exception:
            printExc()

    def listPlaylistVideos(self, videos):
        printDBG("listPlaylistVideos")
        try:
            for item in videos:
                title = self.getStr(item.get('title', ''))
                plot = self.getStr(item.get('description', ''))
                icon = self.getStr(item.get('still_url', ''))
                url = self.getStr(item.get('url', ''))

                if url != '':
                    params = {'title': title, 'url': url, 'icon': icon, 'plot': plot, 'tar_id': '', 'id': ''}
                    self.addVideo(params)
        except Exception:
            printExc()

    def listSubCategories(self, category, subCategiories):
        printDBG("listSubCategories")
        try:
            for item in subCategiories:
                title = self.getStr(item.get('name', ''))
                id = int(self.getStr(item.get('id', '-1'), '-1'))
                if id != -1:
                    url = Tvn24.MAIN_URL + '/categories/articles/' + Tvn24.API_KEY + '/' + str(id)
                    params = {'name': 'category', 'category': 'end_cat', 'parent_cat': category, 'title': title, 'url': url, 'page': '1'}
                    self.addDir(params)
        except Exception:
            printExc()

    def listCategories(self, category, baseUrl, page):
        printDBG("listCategories category[%s] url[%s] page[%s]" % (category, baseUrl, page))
        url = baseUrl
        pagination = False
        if '' != page:
            if url[-1] != '/':
                url + ','
            url += '%s,%s' % (page, Tvn24.ITEMS_PER_PAGE)
            if '' != category:
                pagination = True
        nextPage = None
        if 'magazines' == category and page == '1':
            STATIC_MAGAZINES = [{'id': 'FAKTY', 'name': 'Fakty', 'icon': 'http://www.tvnfakty.pl/assets/images/newsy_2012/nowaczolowka_big.jpg'},
                                {'id': 'SPORT', 'name': 'Sport', 'icon': ''}, ]
            for item in STATIC_MAGAZINES:
                sUrl = Tvn24.MAIN_URL + '/magazines/articles/' + Tvn24.API_KEY + '/' + item['id']
                params = {'name': 'category', 'category': 'end_cat', 'parent_cat': category, 'title': item['name'], 'url': sUrl, 'icon': item['icon'], 'page': '1'}
                self.addDir(params)
        try:
            sts, data = self.cm.getPage(url, {'host': Tvn24.HOST})
            data = json_loads(data)
            if pagination:
                if int(data['pageCount']) > int(data['currentPageNumber']):
                    nextPage = str(int(page) + 1)
                data = data['items']
            for item in data:
                title = self.getStr(item.get('title', ''))
                plot = self.getStr(item.get('lead', ''))
                icon = self.getIconFromRelated(item.get('related', None))
                id = int(self.getStr(item.get('tcg_id', '-1'), '-1'))
                if -1 == id:
                    id = int(self.getStr(item.get('id', '-1'), '-1'))

                if id != -1:
                    url = Tvn24.MAIN_URL + '/' + category + '/articles/' + Tvn24.API_KEY + '/' + str(id)
                    if len(item.get('items', [])):
                        currCat = 'sub_categiories'
                        subCategiories = item['items']
                    else:
                        currCat = 'end_cat'
                        subCategiories = []
                    params = {'name': 'category', 'category': currCat, 'parent_cat': category, 'title': title, 'url': url, 'icon': icon, 'plot': plot, 'page': '1', 'sub_categiories': subCategiories}
                    self.addDir(params)
            if None != nextPage:
                params = {'name': 'category', 'title': 'Następna strona', 'category': category, 'url': baseUrl, 'page': nextPage}
                self.addDir(params)
        except Exception:
            printExc()

    def listEndItems(self, parent_cat, baseUrl, page):
        printDBG("listEndItems parent_cat[%s] baseUrl[%s], page[%s]" % (parent_cat, baseUrl, page))
        url = baseUrl
        pagination = False
        if '' != page:
            url += ',%s,%s' % (page, Tvn24.ITEMS_PER_PAGE)
            if '' != parent_cat:
                pagination = True
        nextPage = None
        try:
            sts, data = self.cm.getPage(url, {'host': Tvn24.HOST})
            data = json_loads(data)
            if pagination:
                if int(data['pageCount']) > int(data['currentPageNumber']):
                    nextPage = str(int(page) + 1)
                data = data['items']

            for item in data:
                url = ''
                title = self.getStr(item.get('title', ''))
                plot = self.getStr(item.get('lead', ''))
                id = self.getStr(item.get('id', ''))
                tar_id = self.getStr(item.get('tar_id', ''))

                # get icon
                icon = self.getStr(item.get('pht_main_content_url', ''))
                if '' == icon:
                    icon = self.getStr(item.get('pht_url', ''))

                # get data from related
                item = item.get('related', None)
                if None != item:
                    if '' == icon:
                        icon = self.getIconFromRelated(item)
                    # get data from video url
                    videoItem = item.get('Video_Video', None)
                    if None != videoItem:
                        if '' == title:
                            title = self.getStr(videoItem.get('title', ''))
                        if '' == plot:
                            plot = self.getStr(videoItem.get('description', ''))
                        if '' == icon:
                            icon = self.getStr(videoItem.get('still_url', ''))
                        url = self.getStr(videoItem.get('url', ''))

                if url != '' or tar_id != '' or id != '':
                    params = {'title': title, 'url': url, 'icon': icon, 'plot': plot, 'tar_id': tar_id, 'id': id}
                    if '' != url:
                        self.addVideo(params)
                    else:
                        self.addArticle(params)

            if None != nextPage:
                params = {'name': 'category', 'title': 'Następna strona', 'category': 'end_cat', 'parent_cat': parent_cat, 'url': baseUrl, 'page': nextPage}
                self.addDir(params)
        except Exception:
            printExc()

    def getHostingTable(self, idx):
        url = self.currList[idx].get('url', '')
        printDBG("getHostingTable idx[%d] = url[%s]" % (idx, url))

        if url.startswith('http'):
            return [{'name': 'tvn24', 'url': self.converUrl(url)}]
        return []

    def getArticleContent(self, idx):
        printDBG('getArticleContent idx[%s]' % idx)
        retList = []
        articleID = self.currList[idx].get('tar_id', '')
        if '' == articleID:
            articleID = self.currList[idx].get('id', '')

        if '' != articleID:
            try:
                url = Tvn24.MAIN_URL + '/articles/' + Tvn24.API_KEY + '/%s,0,1,10' % articleID
                sts, data = self.cm.getPage(url, {'host': Tvn24.HOST})
                data = json_loads(data)
                data = data['getArticleDetail']
                item = {}
                item['title'] = self.getStr(data.get('title', ''), '')
                item['text'] = self.getStr(data.get('content', ''), '').strip()
                if '' == item['text']:
                    item['text'] = self.getStr(data.get('lead', ''), '').strip()
                img_title = self.getStr(data.get('pht_title', ''), '')
                img_author = self.getStr(data.get('pht_author', ''), '')
                img_url = self.getStr(data.get('pht_url', ''), '')

                item['images'] = [{'title': img_title, 'author': img_author, 'url': img_url}]
                retList.append(item)
            except Exception:
                printExc()

        return retList

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        title = self.currItem.get("title", '')
        category = self.currItem.get("category", '')
        parent_cat = self.currItem.get("parent_cat", '')
        page = self.currItem.get("page", '')
        icon = self.currItem.get("icon", '')
        url = self.currItem.get("url", '')
        plot = self.currItem.get("plot", '')
        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listsMainMenu()
    #VIDEO_PLAYLIST
        elif category == 'playlist':
            self.listPlaylists(url)
        elif category == 'end_playlist':
            self.listPlaylistVideos(self.currItem.get("videos", []))
    #LIST VIDEOS
        elif category == "end_cat":
            self.listEndItems(parent_cat, url, page)
    #LIST MAGAZINES
        elif category == "magazines":
            self.listCategories(category, url, page)
    #LIST CATEGORIES
        elif category == "categories":
              self.listCategories(category, url, page)
    #LIST SUB CATEGORIES
        elif category == "sub_categiories":
              self.listSubCategories(category, self.currItem.get("sub_categiories", []))


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Tvn24(), False) # without search history

    def getLogoPath(self):
        return RetHost(RetHost.OK, value=[GetLogoDir('tvn24logo.png')])

    def getLinksForVideo(self, Index=0, selItem=None):
        listLen = len(self.host.currList)
        if listLen < Index and listLen > 0:
            printDBG("ERROR getLinksForVideo - current list is to short len: %d, Index: %d" % (listLen, Index))
            return RetHost(RetHost.ERROR, value=[])

        if self.host.currList[Index]["type"] != 'video':
            printDBG("ERROR getLinksForVideo - current item has wrong type")
            return RetHost(RetHost.ERROR, value=[])

        retlist = []
        urlList = self.host.getHostingTable(Index)
        for item in urlList:
            need_resolve = 0
            retlist.append(CUrlItem(item["name"], item["url"], need_resolve))

        return RetHost(RetHost.OK, value=retlist)
    # end getLinksForVideo

    def getArticleContent(self, Index=0):
        listLen = len(self.host.currList)
        if listLen < Index and listLen > 0:
            printDBG("ERROR getArticleContent - current list is to short len: %d, Index: %d" % (listLen, Index))
            return RetHost(RetHost.ERROR, value=[])

        if self.host.currList[Index]["type"] != 'article':
            printDBG("ERROR getArticleContent - current item has wrong type")
            return RetHost(RetHost.ERROR, value=[])

        retlist = []
        hList = self.host.getArticleContent(Index)
        for item in hList:
            title = clean_html(item.get('title', ''))
            text = clean_html(item.get('text', ''))
            images = item.get("images", [])
            retlist.append(ArticleContent(title=title, text=text, images=images))

        return RetHost(RetHost.OK, value=retlist)

    def convertList(self, cList):
        hostList = []
        searchTypesOptions = [] # ustawione alfabetycznie
        #searchTypesOptions.append(("Seriale", "seriale"))
        searchTypesOptions.append(("Filmy", "filmy"))

        for cItem in cList:
            hostLinks = []
            type = CDisplayListItem.TYPE_UNKNOWN
            possibleTypesOfSearch = None

            if cItem['type'] == 'category':
                if cItem['title'] == 'Wyszukaj':
                    type = CDisplayListItem.TYPE_SEARCH
                    possibleTypesOfSearch = searchTypesOptions
                else:
                    type = CDisplayListItem.TYPE_CATEGORY
            elif cItem['type'] == 'video':
                type = CDisplayListItem.TYPE_VIDEO
                url = cItem.get('url', '')
                if '' != url:
                    hostLinks.append(CUrlItem("Link", url, 1))
            elif cItem['type'] == 'article':
                type = CDisplayListItem.TYPE_ARTICLE
                url = cItem.get('url', '')
                if '' != url:
                    hostLinks.append(CUrlItem("Link", url, 1))

            title = clean_html(cItem.get('title', ''))
            description = clean_html(cItem.get('plot', ''))
            icon = cItem.get('icon', '')

            hostItem = CDisplayListItem(name=title,
                                        description=description,
                                        type=type,
                                        urlItems=hostLinks,
                                        urlSeparateRequest=1,
                                        iconimage=icon,
                                        possibleTypesOfSearch=possibleTypesOfSearch)
            hostList.append(hostItem)

        return hostList
    # end convertList
