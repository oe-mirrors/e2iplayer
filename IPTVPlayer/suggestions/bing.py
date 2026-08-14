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
        return _("Bing Suggestions")

    def getSuggestions(self, text, locale):
        # osjson.aspx returns the same [query, [suggestions...]] shape as
        # Google's own "output=firefox" suggest API. mkt expects exactly the
        # locale format we already have (e.g. "de-DE").
        url = 'https://api.bing.com/osjson.aspx?query=%s&mkt=%s' % (urllib_quote(text), locale)
        sts, data = self.cm.getPage(url)
        if sts:
            retList = []
            for item in json.loads(data)[1]:
                retList.append(ensure_str(item))
            return retList
        return None
