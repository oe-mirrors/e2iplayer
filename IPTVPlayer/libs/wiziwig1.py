# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

import re, datetime, time

class Wiziwig1Api(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://wiziwig1.com/'
        self.DEFAULT_ICON_URL = 'http://i.imgur.com/yBX7fZA.jpg'
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer':self.getMainUrl()})
        self.http_params = {'header':self.HTTP_HEADER}
        self.getLinkJS = ''

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}: addParams = dict(self.http_params)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getList(self, cItem):
        printDBG("Wiziwig1Api.getChannelsList")

        channelsTab = []
        sts, data = self.getPage(self.getFullUrl('/livesports'), self.http_params)
        if not sts: 
            return []
        #self.setMainUrl(self.cm.meta['url'])
        #self.http_params['header']['Referer'] = self.cm.meta['url']

        items = re.findall("(<tr>\n<td class='icon'(.|\n)*?</tr>)", data)

        for item in items:
            url=''
            anchors = re.findall("href=['\"](.*?)['\"]", item[0])
            if anchors:
                for a in anchors:
                    if a.startswith("http"):
                        url = a
                        break
            if url: 
                title = re.findall("<h4>(.*?)</h4>", item[0])
                if title:
                    title = ph.clean_html(title[0])

                    cat= re.findall("<td class='category'>(.*?)</td>", item[0])
                    if cat:
                        cat = ph.clean_html(cat[0])
                        title = cat + ' - ' + title
                    
                    time = re.findall("<td class='time'>(.*?)</td>", item[0])
                    if time:
                        time = time[0]
                        title = time + " - " + title
                    
                    icon = re.findall("src='(.*?)'",item[0])
                    if icon:
                        icon = self.getFullUrl(icon[0])
                    else:
                        icon = ''
                        
                    params = MergeDicts(cItem, {'type':'video', 'title':title, 'url':url, 'icon': icon})
                    printDBG(str(params))
                    channelsTab.append(params)

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("Wiziwig1Api.getVideoLink")
        urlsTab = []

        sts, data = self.getPage(cItem['url'], self.http_params)
        if not sts: return urlsTab
        self.http_params['header']['Referer'] = self.cm.meta['url']

        url = self.getFullUrl(ph.search(data, ph.IFRAME)[1])
        sts, data = self.getPage(url, self.http_params)
        if not sts: return []

        return self.up.getAutoDetectedStreamLink(self.cm.meta['url'], data)
