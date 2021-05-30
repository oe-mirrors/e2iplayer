# -*- coding: utf-8 -*-
#
import urllib
try:
    import json
except Exception:
    import simplejson as json

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc


class SuggestionsProvider:

    def __init__(self):
        self.cm = common()

    def getName(self):
        return _("Filmstarts Suggestions")

    def getSuggestions(self, text, locale):
        url = 'http://essearch.allocine.net/de/autocomplete?q=' + urllib.quote(text)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json.loads(data):
                if 'title1' in item:
                    retList.append(item['title1'].encode('UTF-8'))
                if 'title2' in item and item['title2'] != item.get('title1'):
                    retList.append(item['title2'].encode('UTF-8'))

            return retList
        return None
