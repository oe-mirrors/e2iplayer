# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCookieDir, byteify
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparser import urlparser
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    return optionList
###################################################


class LivespottingTvApi:
    MAIN_URL = 'http://livespotting.com/'

    def __init__(self):
        self.COOKIE_FILE = GetCookieDir('livespottingtv.cookie')
        self.cm = common()
        self.up = urlparser()
        self.http_params = {}
        self.http_params.update({'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE})
        self.cache = {}

    def cleanHtmlStr(self, str):
        return CBaseHostClass.cleanHtmlStr(str)

    def getChannelsList(self, cItem):
        printDBG("WkylinewebcamsCom.getChannelsList")
        list = []
        sts, data = self.cm.getPage('https://livespotting.com/showroom.json')
        if not sts:
            return list
        printDBG("data: %s" % data)
        data = data.replace('Showroom.Load(', '').replace(');', '')
        try:
            data = json_loads(data)
            for item in data:
                try:
                    title = item['title']
                    icon = item['image']
                    desc = item['description']
                    url = str(item['sources'])
                    url = ph.search(url, '''file['"]:\s*['"]([^"^']+?)['"]''')[0]
                    list.append({'title': title, 'url': url, 'icon': icon, 'desc': desc})
                except Exception:
                    printExc()
        except Exception:
            printExc()

        return list
