# -*- coding: utf-8 -*-
#
from urllib.parse import quote
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
        return _("Filmweb Suggestions")

    def getSuggestions(self, text, locale):
        url = 'https://www.filmweb.pl/api/v1/live/search?query=' + quote(text)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
#            printDBG(data)
            data = json.loads(data)['searchHits']
            for item in data:
                if item.get('matchedName', '') == '':
                    retList.append(ensure_str(item['matchedTitle']))
                else:
                    retList.append(ensure_str(item['matchedName']))
            return retList
        return None
