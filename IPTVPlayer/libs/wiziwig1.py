# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

import re
import datetime
import time

class Wiziwig1Api(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://wiziwig1.eu/'
        self.DEFAULT_ICON_URL = 'http://i.imgur.com/yBX7fZA.jpg'
        self.HTTP_HEADER = {}
        self.http_params = {'header': self.HTTP_HEADER}
        self.getLinkJS = ''
        self.timeoffset = datetime.datetime.now() - datetime.datetime.utcnow() + datetime.timedelta(milliseconds=500)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.http_params)
        origBaseUrl = baseUrl
        baseUrl = self.cm.iriToUri(baseUrl)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def localTime(self, date_time_str):
        date_time_obj = datetime.datetime.strptime(date_time_str, '%H:%M') + self.timeoffset #"2020-06-09T15:55:00.000Z"
        time2 = date_time_obj.strftime("%H:%M")
        
        return time2
        
        
    def getList(self, cItem):
        printDBG("Wiziwig1Api.getChannelsList")

        channelsTab = []
        sts, data = self.getPage(self.getFullUrl('/livesports'), self.http_params)
        if not sts: 
            return []
        #self.setMainUrl(self.cm.meta['url'])
        #self.http_params['header']['Referer'] = self.cm.meta['url']

        items = re.findall("(<tr>\n<td class='icon'.*?</tr>)", data, re.S)

        for item in items:
            urls = []
            n_link = 0
            anchors = re.findall("href=['\"](.*?)['\"]", item, re.S)
            if anchors:
                for a in anchors:
                    if a.startswith("http"):
                        n_link = n_link + 1
                        name = "Link %s " % n_link
                        urls.append({"name": name, "url": a})

            if urls: 
                title = re.findall("<h4>(.*?)</h4>", item)
                if title:
                    title = ph.clean_html(title[0])

                    cat = re.findall("<td class='category'>(.*?)</td>", item)
                    if cat:
                        cat = ph.clean_html(cat[0])
                        title = cat + ' - ' + title
                    
                    time = re.findall("<td class='time'>(.*?)</td>", item)
                    if time:
                        time = self.localTime(time[0])
                        title = time + " - " + title
                    
                    icon = re.findall("src='(.*?)'", item)
                    if icon:
                        icon = self.getFullUrl(icon[0])
                    else:
                        icon = ''
                        
                    params = MergeDicts(cItem, {'type': 'video', 'title': title, 'url_list': urls, 'icon': icon})
                    printDBG(str(params))
                    channelsTab.append(params)

        return channelsTab

    def getVideoLink(self, cItem):
        printDBG("Wiziwig1Api.getVideoLink")
        urlsTab = []

        for u in cItem.get("url_list", []):

            sts, data = self.getPage(u['url'], self.http_params)
            if not sts: 
                continue
            
            iframes = re.findall("<iframe width='650' height='500' src='(.*?)'", data, re.S)
            
            if iframes:
                url = self.getFullUrl(iframes[0])
                name = u["name"] + " - " + self.up.getDomain(url, onlyDomain=True)
                if self.up.checkHostSupport(url): 
                    if len(name) > 18:
                        name = name[:18] + "..."
                    uuu = self.up.getVideoLinkExt(url)
                    printDBG("getVideoLinkExt %s " % str(uuu))
                    urlsTab2 = [] 
                    for u2 in uuu:
                        printDBG(str(u2))
                        u2['name'] = name + ' ' + u2.get('name', '')
                        urlsTab2.append(u2)
                        
                    urlsTab.extend(urlsTab2)
                else:
                    urlsTab.append({"name": name + " (not in urlparser)", "url": url})
        return urlsTab
    
