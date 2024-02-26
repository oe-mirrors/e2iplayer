# -*- coding: utf-8 -*-
#
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
try:
    import json
except Exception:
    import simplejson as json

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str


class SuggestionsProvider:

    def __init__(self):
        self.cm = common()

    def getName(self):
        return _("Filmstarts Suggestions")

    def getSuggestions(self, text, locale):
        url = 'http://essearch.allocine.net/de/autocomplete?q=' + urllib_quote(text)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json.loads(data):
                if 'title1' in item:
                    retList.append(ensure_str(item['title1']))
                if 'title2' in item and item['title2'] != item.get('title1'):
                    retList.append(ensure_str(item['title2']))

            return retList
        return None
