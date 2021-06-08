
#
#      Copyright (C) 2013 Tommy Winther
#      http://tommy.winther.nu
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
# https://docs.google.com/document/d/1_rs5BXklnLqGS6g6eAjevVHsPafv4PXDCi_dAM2b7G0/edit?pli=1
#
import urllib.request
import urllib.parse
import urllib.error
import re
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads


API_URL = 'http://api.yousee.tv/rest'
API_KEY = 'HCN2BMuByjWnrBF4rUncEfFBMXDumku7nfT3CMnn'

AREA_LIVETV = 'livetv'
AREA_MOVIE = 'movie'
AREA_PLAY = 'play'
AREA_USERS = 'users'
AREA_TVGUIDE = 'tvguide'
AREA_SYSTEM = 'system'
AREA_CONTENT = 'content'
AREA_ARCHIVE = 'archive'
AREA_PLAY = 'play'

METHOD_GET = 'get'
METHOD_POST = 'post'


class YouSeeApiException(Exception):
    pass


class YouSeeApi(object):
    def _invoke(self, area, function, params=None, method=METHOD_GET):
        url = API_URL + '/' + area + '/' + function
        if method == METHOD_GET and params:
            for key, value in list(params.items()):
                url += '/' + key + '/' + str(value)
        url += '/format/json'

        try:
            r = urllib.request.Request(url, headers={'X-API-KEY': API_KEY})
            if method == METHOD_POST and params:
                print("POST data: %s" % urllib.parse.urlencode(params))
                r.add_data(urllib.parse.urlencode(params))
            u = urllib.request.urlopen(r)
            data = u.read()
            u.close()
        except urllib.error.HTTPError as error:
            data = error.read()
        except Exception as ex:
            raise YouSeeApiException(ex)

        try:
            return json_loads(data)
        except Exception:
            return None


class YouSeeLiveTVApi(YouSeeApi):
    def channel(self, id):
        return self._invoke(AREA_LIVETV, 'channel', {
            'id': id
        })

    def popularChannels(self):
        return self._invoke(AREA_LIVETV, 'popularchannels')

    def allowedChannels(self):
        return self._invoke(AREA_LIVETV, 'allowed_channels', {
            'apiversion': 2
        })

    def suggestedChannels(self):
        return self._invoke(AREA_LIVETV, 'suggested_channels')

    def streamUrl(self, channelId, client='xbmc'):
        data = self._invoke(AREA_LIVETV, 'streamurl', {
            'channel_id': channelId,
            'client': client
        })
        return data
