# -*- coding: utf-8 -*-
#
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
import json

from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str


class SuggestionsProvider:

    def __init__(self):
        self.cm = common()

    def getName(self):
        return _("DuckDuckGo Suggestions")

    def getSuggestions(self, text, locale):
        url = 'https://duckduckgo.com/ac/?q=%s' % urllib_quote(text)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json.loads(data):
                phrase = item.get('phrase')
                if phrase:
                    retList.append(ensure_str(phrase))
            return retList
        return None
