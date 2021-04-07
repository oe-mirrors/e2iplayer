#
#      Copyright (C) 2012 Tommy Winther
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
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
import copy

class TV2RChannel():
    QUALITIES = [2000, 1000, 300]
    CHANNELS = [{'title': 'TV2 Fyn', 'type': 'fynskemedier.dk', 'id': 'tv2fyn'},
                {'title': 'TV2 Lorry', 'type': 'fynskemedier.dk', 'id': 'tv2lorry'},
                {'title': 'TV2 Syd', 'type': 'fynskemedier.dk', 'id': 'tvsyd'},
                {'title': 'TV2 Midtvest', 'type': 'direct', 'id': 'rtmp://live.tvmidtvest.dk/tvmv/live live=1'},
                {'title': 'TV2 Nor', 'type': 'fynskemedier.dk', 'id': 'tv2nord-plus'},
                {'title': 'TV2 East', 'type': 'direct', 'id': 'http://tv2east.live-s.cdn.bitgravity.com/cdn-live-c1/_definst_/tv2east/live/feed01/playlist.m3u8'},
                #{'title':'TV2 OJ',        'type':'fynskemedier.dk', 'id':'tv2oj'},
                {'title': 'TV Folketinget', 'type': 'direct', 'id': 'rtmp://ftflash.arkena.dk/webtvftlivefl/ playpath=mp4:live.mp4 pageUrl=http://www.ft.dk/webTV/TV_kanalen_folketinget.aspx live=1'},
                #{'title':'Kanalsport DK', 'type':'direct',          'id':'http://lswb-de-08.servers.octoshape.net:1935/live/kanalsport_1000k/playlist.m3u8'},
                ]

                
    def __init__(self):
        self.cm = common()
        
    def getChannels(self):
        return copy.deepcopy(self.CHANNELS)
        
    def __getFynskemedierIP(self):
        for attempt in range(0, 2):
            sts, data = self.cm.getPage('http://livestream.fynskemedier.dk/loadbalancer')
            if not sts:
                continue
            return data[9:]
        return None
        
    def getLinksForChannel(self, channelData):
        links = [] 
        if 'fynskemedier.dk' == channelData['type']:
            ip = self.__getFynskemedierIP()
            if None == ip:
                return links
            for qual in self.QUALITIES:
                url = 'rtmp://{0}:1935/live/_definst_/{1}_{2} live=1'.format(ip, channelData['id'], qual)
                name = 'livestream.fynskemedier.dk [{0}]'.format(qual)
                links.append({'name': name, 'url': url})
        elif 'direct' == channelData['type']:
                 links.append({'name': 'direct link', 'url': channelData['id']})
        return links

# TV2 OJ
#TV2RChannel(108, CATEGORY_TV2_REG, "TV2 OJ").add_urls(
#    best   = 'rtmp://<HOST>:1935/live/_definst_/tv2oj_2000 live=1',
#    high   = 'rtmp://<HOST>:1935/live/_definst_/tv2oj_1000 live=1',
#    medium = 'rtmp://<HOST>:1935/live/_definst_/tv2oj_300 live=1'
#)
# TV2 Bornholm
#Channel(109, CATEGORY_TV2_REG, "TV2 Bornholm").add_urls(
#    best   = 'mms://itv02.digizuite.dk/tv2b'
#)

# http://ft.arkena.tv/xml/core_player_clip_data_v2_REAL.php?wtve=187&wtvl=2&wtvk=012536940751284&as=1
# Folketinget

# danskespil lotto
#Channel(202, CATEGORY_MISC, "DanskeSpil Lotto").add_urls(
#    best   = 'rtmp://lvs.wowza.jay.net/webstream/lotto live=1'
#)
