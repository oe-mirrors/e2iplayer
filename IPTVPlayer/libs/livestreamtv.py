# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
import re
try:
    import json
except Exception:
    import simplejson
############################################


class LiveStreamTvApi(CBaseHostClass):
    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'http://live-stream.tv/'

    def getChannelsList(self, cItem):
        printDBG("LiveStreamTvApi.getChannelsList cItem[%s]" % cItem)
        channelsList = []
        sts, data = self.cm.getPage(self.MAIN_URL)
        if not sts:
            return channelsList
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<div id="channel', '</a>')
        desc = ''
        for item in data:
            title = self.cleanHtmlStr(self.cm.ph.getDataBeetwenMarkers(item, '<strong', '</strong>')[1])
            if title == '':
                title = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''channame=['"]([^'^"]+?)['"]''')[0])
            # desc
            epgstart = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''epgstart=['"]([^'^"]+?)['"]''')[0])
            epgend = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''epgend=['"]([^'^"]+?)['"]''')[0])
            epgtitle = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''epgtitle=['"]([^'^"]+?)['"]''')[0])
            epgdesc = re.sub("</?br\s*/?>", "[/br]", self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, '''epgdesc=['"]([^'^"]+?)['"]''')[0]))
            
            desc = '%s - %s %s' % (epgstart, epgend, epgtitle) + '[/br]' + epgdesc
            
            icon = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'src="([^"]+?)"')[0])
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0])
            if 'filterGray' in item:
                desc = '[offline] ' + title
            else:
                desc = '[online] ' + desc
            if self.cm.isValidUrl(url):
                channelsList.append({'name': 'live-stream.tv', 'title': title, 'url': url, 'desc': desc, 'icon': icon})
        return channelsList
    
    def getVideoLink(self, cItem):
        printDBG("LiveStreamTvApi.getVideoLink cItem[%s]" % cItem)
        return self.up.getVideoLinkExt(cItem.get('url', ''))
