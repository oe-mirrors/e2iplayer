# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
try:
    import json
except Exception:
    import simplejson as json

############################################


###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList

###################################################


class DjingComApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://www.djing.com/'
        self.DEFAULT_ICON_URL = 'https://www.djing.com/newimages/content/c01.jpg'
        self.HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36', 'Accept': 'text/html', 'Accept-Encoding': 'gzip, deflate'}
        self.AJAX_HEADER = dict(self.HTTP_HEADER)
        self.AJAX_HEADER.update({'X-Requested-With': 'XMLHttpRequest'})

        self.COOKIE_FILE = GetCookieDir('viortv.cookie')

        self.defaultParams = {}
        self.defaultParams.update({'header': self.HTTP_HEADER, 'cookiefile': self.COOKIE_FILE})  # 'save_cookie': True, 'load_cookie': True,
        self.loggedIn = False
        self.accountInfo = ''

    # the old 24/7 "venue music channels" (server-rendered <ul bgImages> with
    # <source> HLS) are gone - djing.com is a DJ-booking SPA now. The one
    # browsable public feed left is api/v14/public-dj-sets.php: the latest
    # public DJ radio shows, almost all direct .mp3 podcast episodes.
    API_URL = 'https://djing.com/api/v14/public-dj-sets.php'

    def getList(self, cItem):
        printDBG("DjingComApi.getList")
        channelsTab = []

        sts, data = self.cm.getPage(self.API_URL, {'header': dict(self.HTTP_HEADER, Referer=self.MAIN_URL)})
        if not sts:
            return channelsTab
        try:
            rows = json.loads(data).get('data', [])
        except Exception:
            printExc()
            return channelsTab

        for row in rows:
            url = row.get('external_url', '')
            if not self.cm.isValidUrl(url):
                continue
            title = self.cleanHtmlStr(row.get('title', '')) or self.cleanHtmlStr(row.get('stage_name', ''))
            stage = self.cleanHtmlStr(row.get('stage_name', ''))
            if stage and stage.lower() not in title.lower():
                title = '%s - %s' % (stage, title)
            channelsTab.append({'name': cItem['name'], 'type': 'audio', 'title': title,
                                'url': strwithmeta(url, {'User-Agent': self.HTTP_HEADER['User-Agent'], 'Referer': self.MAIN_URL}),
                                'icon': row.get('picture', '') or self.DEFAULT_ICON_URL,
                                'desc': ' | '.join(x for x in (row.get('platform', ''), row.get('created_at', '')) if x)})
        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("DjingComApi.getVideoLink")
        url = cItem.get('url', '')
        if not url:
            return []
        if '.m3u8' in url:
            try:
                return getDirectM3U8Playlist(url, checkContent=True)
            except Exception:
                printExc()
                return []
        if self.up.checkHostSupport(url):
            return self.up.getVideoLinkExt(url)
        return [{'name': 'djing.com', 'url': url}]
