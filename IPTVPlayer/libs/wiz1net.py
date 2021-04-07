# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

class Wiz1NetApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://www.wiz1.net/'
        self.DEFAULT_ICON_URL = 'http://i.imgur.com/yBX7fZA.jpg'
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer':self.getMainUrl()})
        self.http_params = {'header':self.HTTP_HEADER}
        self.getLinkJS = ''

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.http_params)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getList(self, cItem):
        printDBG("Wiz1NetApi.getChannelsList")

        channelsTab = []
        sts, data = self.getPage(self.getFullUrl('/schedule'), self.http_params)
        if not sts:
            return []
        self.setMainUrl(self.cm.meta['url'])
        self.http_params['header']['Referer'] = self.cm.meta['url']

        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return []

        desc = ph.clean_html(ph.find(data, ('<h4', '>'), ('<br', '>'), flags=0)[1])

        data = ph.rfindall(data, '</a>', ('<br', '>'), flags=0)
        for item in data:
            title = ph.clean_html(item)
            url = self.getFullUrl(ph.search(item, ph.A)[1])
            channelsTab.append(MergeDicts(cItem, {'type':'video', 'title':title, 'url':url, 'desc':desc}))

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("Wiz1NetApi.getVideoLink")
        urlsTab = []

        sts, data = self.getPage(cItem['url'], self.http_params)
        if not sts:
            return urlsTab
        self.http_params['header']['Referer'] = self.cm.meta['url']

        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        sts, data = self.getPage(url, self.http_params)
        if not sts:
            return []

        return self.up.getAutoDetectedStreamLink(self.cm.meta['url'], data)
