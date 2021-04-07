# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Screens.MessageBox import MessageBox
###################################################


class BeinmatchApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://www.beinmatch.com/'
        self.DEFAULT_ICON_URL = self.getFullIconUrl('/assets/images/bim/logo.png')
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer': self.getMainUrl()})
        self.http_params = {'header': self.HTTP_HEADER}
        self.getLinkJS = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.http_params)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getList(self, cItem):
        printDBG("BeinmatchApi.getChannelsList")

        channelsTab = []
        sts, data = self.getPage(self.getMainUrl(), self.http_params)
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])

        tmp = ph.findall(data, ('<script', '>', ph.check(ph.none, ('src=',))), '</script>', flags=0)
        for item in tmp:
            if 'goToMatch' in item:
                self.getLinkJS = item
                break

        if not self.getLinkJS:
            self.sessionEx.waitForFinishOpen(MessageBox, _('Data for link generation could not be found.\nPlease report this problem to %s') % 'iptvplayere2@gmail.com', type=MessageBox.TYPE_ERROR, timeout=10)

        data = ph.find(data, ('<table', '>', 'tabIndex'), ('<div', '>', 'Side'))[1]
        data = ph.rfindall(data, '</tr>', ('<table', '>', 'tabIndex'))
        for item in data:
            printDBG("+++++++++++++++++++++++++++++++++++++++++")
            printDBG(item)
            printDBG("+++++++++++++++++++++++++++++++++++++++++")
            icon = self.getFullIconUrl(ph.find(item, 'url(', ')', flags=0)[1].strip())
            title = ph.clean_html(' vs '.join(ph.findall(item, ('<td', '>', 'tdTeam'), '</td>', flags=0)))
            url = ph.getattr(item, 'onclick')
            desc = ph.clean_html(ph.find(item, ('<td', '>', 'compStl'), '</table>', flags=0)[1])
            channelsTab.append(MergeDicts(cItem, {'type': 'video', 'title': title, 'url': url, 'icon': icon, 'desc': desc}))

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("BeinmatchApi.getVideoLink")
        urlsTab = []

        jscode = ['window={open:function(){print(JSON.stringify(arguments));}};', self.getLinkJS, cItem['url']]
        ret = js_execute('\n'.join(jscode))
        try:
            data = json_loads(ret['data'])
            url = self.getFullUrl(data['0'])
        except Exception:
            printExc()
            return urlsTab

        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return urlsTab
        cUrl = self.cm.meta['url']
        printDBG(data)
        url = self.getFullUrl(ph.search(data, '''['"]([^'^"]+?\.m3u8(?:\?[^'^"]*?)?)['"]''')[0], cUrl)
        if url:
            url = strwithmeta(url, {'Referer': cUrl, 'Origin': self.cm.getBaseUrl(cUrl)[:-1], 'User-Agent': self.HTTP_HEADER['User-Agent']})
            return getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
        data = ph.find(data, ('<div', '>', 'video-container'), '</div>', flags=0)[1]
        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        if 0 == self.up.checkHostSupport(url): 
            sts, data = self.getPage(url, self.http_params)
            if not sts:
                return urlsTab
            url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        return self.up.getVideoLinkExt(url)
            
            
