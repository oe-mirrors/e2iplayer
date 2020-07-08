# -*- coding: utf-8 -*-
# Based on techdealer-xbmc.googlecode.com/svn/trunk/plugin.audio.musicbox/

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVNotify
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, CSelOneLink
from Components.config import config, getConfigListEntry, ConfigYesNo, ConfigText
from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################
# FOREIGN import
###################################################
import re
import urllib
import HTMLParser
####################################################
# E2 GUI COMMPONENTS
####################################################
from Screens.MessageBox import MessageBox
####################################################
# Config options for HOST
####################################################
config.plugins.iptvplayer.MusicBox_premium = ConfigYesNo(default=False)
config.plugins.iptvplayer.MusicBox_login = ConfigText(default="", fixed_size=False)
config.plugins.iptvplayer.api_key_youtube = ConfigText(default = "", fixed_size = False)
config.plugins.iptvplayer.api_key_warning = ConfigYesNo(default=True)

####################################################
# Api keys
####################################################
audioscrobbler_api_key = "d49b72ffd881c2cb13b4595e67005ac4"

HEADER = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:33.0) Gecko/20100101 Firefox/33.0'}

def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry( _("%s API KEY") % 'http://youtube.com/', config.plugins.iptvplayer.api_key_youtube))
    optionList.append(getConfigListEntry( _("Show Youtube Api Key warnings"), config.plugins.iptvplayer.api_key_warning))
    optionList.append(getConfigListEntry("Użytkownik Last.fm", config.plugins.iptvplayer.MusicBox_premium))
    if config.plugins.iptvplayer.MusicBox_premium.value:
        optionList.append(getConfigListEntry(" Last.fm login:", config.plugins.iptvplayer.MusicBox_login))
    return optionList

def gettytul():
    return 'Music-Box'


class MusicBox(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.youtube_api_key = ""
        self.ytformats = config.plugins.iptvplayer.ytformat.value
        self.ytp = YouTubeParser()
        self.lastfm_username = config.plugins.iptvplayer.MusicBox_login.value
        self.usePremiumAccount = config.plugins.iptvplayer.MusicBox_premium.value
        
        self.DEFAULT_ICON_URL = 'http://www.darmowe-na-telefon.pl/uploads/tapeta_240x320_muzyka_23.jpg'
        self.BILLBOARD_URL = 'https://www.billboard.com/charts/'
        self.SERVICE_MENU_TABLE = [{'category':'itunes',    'title':"Itunes - Top songs by country",  'item':'song',  'url':'http://www.geonames.org/flags/x/'},
                                   {'category':'itunes',    'title':"Itunes - Top albums by country", 'item':'album', 'url':'http://www.geonames.org/flags/x/'},
                                   {'category':'beatport',  'title':"Beatport - Top 100",                             'url':'https://pro.beatport.com/top-100'},
                                   
                                   {'category':'billboard_charts', 'title':"Billboard - The Hot 100",                         'url':self.BILLBOARD_URL + 'hot-100'},
                                   {'category':'billboard_charts', 'title':"Billboard - 200",                                 'url':self.BILLBOARD_URL + 'billboard-200'},
                                   {'category':'billboard_charts', 'title':"Billboard - Heatseekers Songs",                   'url':self.BILLBOARD_URL + 'heatseekers-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Heatseekers Albums",                  'url':self.BILLBOARD_URL + 'heatseekers-albums'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot Pop Songs",                           'url':self.BILLBOARD_URL + 'pop-songs'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot Country Songs",                   'url':self.BILLBOARD_URL + 'country-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Hot Country Albums",                  'url':self.BILLBOARD_URL + 'country-albums'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot Rock Songs",                      'url':self.BILLBOARD_URL + 'rock-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Hot Rock Albums",                     'url':self.BILLBOARD_URL + 'rock-albums'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot R&B/Hip-Hop Songs",               'url':self.BILLBOARD_URL + 'r-b-hip-hop-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Hot R&B/Hip-Hop Albums",              'url':self.BILLBOARD_URL + 'r-b-hip-hop-albums'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot Dance/Electronic Songs",          'url':self.BILLBOARD_URL + 'dance-electronic-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Hot Dance/Electronic Albums",         'url':self.BILLBOARD_URL + 'dance-electronic-albums'},
                                   {'category':'billboard_charts', 'title':"Billboard - Hot Latin Songs",                     'url':self.BILLBOARD_URL + 'latin-songs'},
                                   {'category':'billboard_albums', 'title':"Billboard - Hot Latin Albums",                    'url':self.BILLBOARD_URL + 'latin-albums'},
                                   
                                   {'category':'lastfm', 'title':"Last.fm - " + _("My list")},
                                   ]
    
    def readYoutubeApiKey(self):
        if self.youtube_api_key != config.plugins.iptvplayer.api_key_youtube.value:
            apiKey = config.plugins.iptvplayer.api_key_youtube.value
            if len(apiKey)>0 and len(apiKey) != 39:
                if config.plugins.iptvplayer.api_key_warning.value == True: 
                    msg = _("Wrong Youtube Api Key length")
                    GetIPTVNotify().push(msg, 'error', 5)

            self.youtube_api_key = apiKey
        
        if not self.youtube_api_key:
            if config.plugins.iptvplayer.api_key_warning.value == True: 
                config.plugins.iptvplayer.api_key_warning.value = False
                msg = _("Youtube searches are quicker, if you fill API key in setting menu")
                msg = msg + "\n" + ("Search for 'how to create your own Youtube api key'") 
                GetIPTVNotify().push(msg, 'info', 5)
                    
            
    def listsMainMenu(self):
        printDBG("MusicBox - lists main menu")

        for item in self.SERVICE_MENU_TABLE:
            item['name'] = 'main-menu'
            self.addDir(item)

###############################################################################
# Itunes
###############################################################################
    def Itunes_countries_menu(self, url, mode):
        printDBG('MusicBox - Itunes countries menu')
        country_name = ["Albania", "Algeria", "Angola", "Anguilla", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bermuda", "Bhutan", "Bolivia", "Botswana", "Brazil", "British Virgin Islands", "Brunei Darussalam", "Bulgaria", "Burkina Faso", "Cambodia", "Canada", "Cape Verde", "Cayman Islands", "Chad", "Chile", "China", "Colombia", "Congo, Republic of the", "Costa Rica", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Estonia", "Fiji", "Finland", "France", "Gambia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea-Bissau", "Guyana", "Honduras", "Hong Kong", "Hungary", "Iceland", "India", "Indonesia", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Korea, Republic Of", "Kuwait", "Kyrgyzstan", "Lao, People's Democratic Republic", "Latvia", "Lebanon", "Liberia", "Lithuania", "Luxembourg", "Macau", "Macedonia", "Madagascar", "Malawi", "Malaysia", "Mali", "Malta", "Mauritania", "Mauritius", "Mexico", "Micronesia, Federated States of", "Moldova", "Mongolia", "Montserrat", "Mozambique", "Namibia", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "Norway", "Oman", "Pakistan", "Palau", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Saudi Arabia", "Senegal", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "South Africa", "Spain", "Sri Lanka", "St. Kitts and Nevis", "St. Lucia", "St. Vincent and The Grenadines", "Suriname", "Swaziland", "Sweden", "Switzerland", "São Tomé and Príncipe", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Turks and Caicos", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Venezuela", "Vietnam", "Yemen", "Zimbabwe"]
        country_code = ["al", "dz", "ao", "ai", "ag", "ar", "am", "au", "at", "az", "bs", "bh", "bb", "by", "be", "bz", "bj", "bm", "bt", "bo", "bw", "br", "vg", "bn", "bg", "bf", "kh", "ca", "cv", "ky", "td", "cl", "cn", "co", "cg", "cr", "hr", "cy", "cz", "dk", "dm", "do", "ec", "eg", "sv", "ee", "fj", "fi", "fr", "gm", "de", "gh", "gr", "gd", "gt", "gw", "gy", "hn", "hk", "hu", "is", "in", "id", "ie", "ir", "it", "jm", "jp", "jo", "kz", "ke", "kr", "kw", "kg", "la", "lv", "lb", "lr", "lt", "lu", "mo", "mk", "mg", "mw", "my", "ml", "mt", "mr", "mu", "mx", "fm", "md", "mn", "ms", "mz", "na", "np", "nl", "nz", "ni", "ne", "ng", "no", "om", "pk", "pw", "pa", "pg", "py", "pe", "ph", "pl", "pt", "qa", "ro", "ru", "sa", "sn", "sc", "sl", "sg", "sk", "si", "sb", "za", "es", "lk", "kn", "lc", "vc", "sr", "sz", "se", "ch", "st", "tw", "tj", "tz", "th", "tt", "tn", "tr", "tm", "tc", "ug", "ua", "ae", "gb", "us", "uy", "uz", "ve", "vn", "ye", "zw"]
        for x in range(0, len(country_name)):
            if country_code[x] not in ["al", "dz", "ao", "bj", "bt", "td", "cn", "cg", "gy", "is", "jm", "kr", "kw", "lr", "mk", "mg", "mw", "ml", "mr", "ms", "pk", "pw", "sn", "sc", "sl", "sb", "lc", "vc", "sr", "st", "tz", "tn", "tc", "uy", "ye"]: #Countries without music store
                url = country_code[x]
                title = country_name[x]
                icon = 'http://www.geonames.org/flags/x/' + country_code[x] + '.gif'
                desc = title
                if mode == 'song':
                    params = {'good_for_fav':True, 'name': 'Itunes_track_charts', 'title': title, 'page': url, 'icon': icon, 'desc': desc}
                    self.addDir(params)
                elif mode == 'album':
                    params = {'good_for_fav':True, 'good_for_fav':True, 'name': 'Itunes_album_charts', 'title': title, 'page': url, 'icon': icon, 'desc': desc}
                    self.addDir(params)

    def Itunes_track_charts(self, url):
        printDBG('MusicBox - Itunes track charts')
        country = url
        sts, data = self.cm.getPage('https://itunes.apple.com/%s/rss/topsongs/limit=100/explicit=true/json' % country, {'header': HEADER})
        if not sts:
            return
        try:
            data = json_loads(data)['feed']['entry']
            for x in range(len(data)):
                item = data[x]
                artist = item['im:artist']['label']
                track_name = item['im:name']['label']
                try:
                    iconimage = item['im:image'][2]['label']
                except Exception:
                    iconimage = ''
                plot = ''
                search_string = urllib.quote(artist + ' ' + track_name + ' music video')
                params = {'good_for_fav':True, 'title': str(x + 1) + '. ' + artist + '- ' + track_name, 'page': search_string, 'icon': iconimage, 'desc': plot}
                self.addVideo(params)
        except Exception:
            printExc()  # wypisz co poszło nie tak

    def Itunes_album_charts(self, url):
        printDBG('MusicBox - Itunes album charts')
        country = url
        sts, data = self.cm.getPage('https://itunes.apple.com/%s/rss/topalbums/limit=100/explicit=true/json' % country, {'header': HEADER})
        if not sts:
            return
        try:
            data = json_loads(data)['feed']['entry']
            for x in range(len(data)):
                item = data[x]
                artist = item['im:artist']['label']
                album_name = item['im:name']['label']
                idx = item['id']['attributes']['im:id']
                try:
                    iconimage = item['im:image'][2]['label']
                except Exception:
                    iconimage = ''
                params = {'good_for_fav':True, 'name': 'Itunes_list_album_tracks','title': str(x + 1) + '. ' + artist + '- ' + album_name, 'page': idx, 'album': album_name, 'country': country, 'icon': iconimage}
                self.addDir(params)
        except Exception:
            printExc()  # wypisz co poszło nie tak

    def Itunes_list_album_tracks(self, url, album, country):
        printDBG('MusicBox - Itunes album tracks')

        sts, data = self.cm.getPage('https://itunes.apple.com/lookup?id='+url+'&country='+country+'&entity=song&limit=200', {'header': HEADER})
        if not sts:
            return
        try:
            data = json_loads(data)['results']
            for x in range(1, len(data)):
                item = data[x]
                artist = item['artistName']
                track_name = item['trackName']
                try:
                    iconimage = item['artworkUrl100']
                except Exception:
                    iconimage = ''
                search_string = urllib.quote(artist + ' ' + track_name + ' music video')
                params = {'good_for_fav':True, 'title': artist + '- ' + track_name, 'page': search_string, 'icon': iconimage}
                self.addVideo(params)
        except Exception:
            printExc()
###############################################################################
# Beatport
###############################################################################

    def Beatport_top100(self, url):
        printDBG('MusicBox - beatbox top 100')

        sts, data = self.cm.getPage(url)
        if not sts: return
        
        data = self.cm.ph.getDataBeetwenNodes(data, ('<ul', '>', 'bucket-item'), ('</ul', '>'), False)[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li', '</li>')
        for item in data:
            track_number = self.cm.ph.getSearchGroups(item, '''position=['"]([^'^"]+?)['"]''')[0]
            title_primary = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'primary-title'), ('</span', '>'), False)[1])
            remixed = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<span', '>', 'remixed'), ('</span', '>'), False)[1])
            track_name = title_primary + ' ' + remixed
            artist = self.cleanHtmlStr(self.cm.ph.getDataBeetwenNodes(item, ('<p', '>', 'track-artists'), ('</p', '>'), False)[1] )
            icon = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, '''<img[^>]+?data\-src=['"]([^'^"]+?)['"]''')[0], self.cm.meta['url'])
            search_string = urllib.quote(artist + ' ' + track_name + ' music video')
            params = {'good_for_fav':True, 'title': track_number + '. ' + artist + '- ' + track_name, 'page': search_string, 'icon': icon}
            self.addVideo(params)

###############################################################################
# Billboard
###############################################################################

    def Billboard_charts(self, url):
        printDBG("MusicBox - Billboard charts")

        sts, data = self.cm.getPage(url, {'header': HEADER})
        if not sts:  
            return

        # top 100 - top 200
        tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<ol', '>', 'chart-list'), '</ol>')[1]
        songs = self.cm.ph.getAllItemsBeetwenMarkers(tmp, ('<li', '>'), '</li>' , False)
        
        for item in songs:
            
            rank = ph.clean_html(ph.find(item, ('<span', '>', '__rank'), '</span>', flags=0)[1])
            name = ph.clean_html(ph.find(item, ('<span', '>', '__song'), '</span>', flags=0)[1])
            artist = ph.clean_html(ph.find(item, ('<span', '>', '__artist'), '</span>', flags=0)[1])
            icon = self.cm.ph.getSearchGroups(item, "url\(['\"]([^\"^']+?)['\"]\)" )[0]
            track_name = name
            search_string = urllib.quote(artist + ' ' + track_name + ' music video')

            params = {'good_for_fav':True, 'title': rank + '. ' + name + ' - ' + artist, 'page': search_string, 'icon': icon}
            printDBG(str(params))
            self.addVideo(params)

        # other charts
        if not tmp:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, ('<main', '>'), ('</main', '>'))[1]
            songs = re.compile('<div[^>]*?data\-has\-content[^>]*?>').split(tmp)
        
            for item in songs:
                #printDBG("-------------- song ------------------")
                #printDBG(item)
                
                rank = ph.clean_html(ph.find(item, ('<div', '>', '__rank'), '</div>', flags=0)[1])

                if rank:
                    name = ph.clean_html(ph.find(item, ('<div', '>', '__title'), '</div>', flags=0)[1])
                    artist = ph.clean_html(ph.find(item, ('<div', '>', '__artist'), '</div>', flags=0)[1])

                    icon = self.cm.ph.getSearchGroups(item, '\s(https?://[^\s]+?\-174x174\.jpg)\s' )[0]

                    track_name = name
                    search_string = urllib.quote(artist + ' ' + track_name + ' music video')

                    params = {'good_for_fav':True, 'title': rank + '. ' + name + ' - ' + artist, 'page': search_string, 'icon': icon}
                    printDBG(str(params))
                    self.addVideo(params)
            

    def Billboard_chartsalbums(self, url):
        printDBG("MusicBox - Billboard charts album")

        sts, data = self.cm.getPage(url, {'header': HEADER})
        if not sts:  return

        data = ph.find(data, ('<div', '>', 'chart-number-one'), ('<div', '>', 'chart-list__expanded-header'))[1]
        data = re.compile('<div[^>]*?data\-has\-content[^>]*?>').split(data)
        for item in data:
            name = ph.clean_html(ph.find(item, ('<div', '>', '__title'), '</div>', flags=0)[1])
            artist = ph.clean_html(ph.find(item, ('<div', '>', '__artist'), '</div>', flags=0)[1])

            icon = ph.search(item, '\s(https?://[^\s]+?\-174x174\.jpg)\s')[0]
            if not icon: icon = ph.getattr(item, 'data-srcset').split(' ', 1)[0]
            if not icon: icon = ph.getattr(item, 'srcset').split(' ', 1)[0]
            album_name = name
            params = {'good_for_fav':True, 'name': 'List_album_tracks','title': name + ' - ' + artist, 'page': 0, 'artist': artist, 'album': album_name, 'icon':self.cm.getFullUrl(icon, self.cm.meta['url'])}
            self.addDir(params)

###############################################################################
# Szukanie tytułu z albumow
###############################################################################

    def List_album_tracks(self, url, artist, album, albumIcon):
        printDBG("MusicBox - list abum tracks")

        if url != 0:
            sts, data = self.cm.getPage('http://ws.audioscrobbler.com/2.0/?method=album.getInfo&mbid='+url+'&api_key=' + audioscrobbler_api_key + '&format=json', {'header': HEADER})
            if not sts: return
        else:
            sts, data = self.cm.getPage('http://ws.audioscrobbler.com/2.0/?method=album.getInfo&artist='+urllib.quote(artist)+'&album='+urllib.quote(album)+'&api_key=' + audioscrobbler_api_key + '&format=json', {'header': HEADER})
            if not sts: return
        try:
            data = json_loads(data)
            try:
                albumIcon = self.cm.getFullUrl(data['album']['image'][-1]['#text'], self.cm.meta['url'])
            except Exception:
                printExc()

            data = data['album']['tracks']['track']
            for x in range(0, len(data)):
                item = data[x]
                artist = item['artist']['name']
                track_name = item['name']
                search_string = urllib.quote(artist + ' ' + track_name + ' music video')
                params = {'good_for_fav':True, 'title': track_name + ' - ' + artist, 'page': search_string, 'icon': albumIcon}
                self.addVideo(params)
        except Exception:
            printExc()

###############################################################################
# Moja playlista z Last.fm
###############################################################################

    def Lastfmlist(self):
        printDBG("MusicBox - last.fm list")

        if False == self.usePremiumAccount:
            self.sessionEx.waitForFinishOpen(MessageBox, 'Wpisz login do last.fm.', type=MessageBox.TYPE_INFO, timeout=10)
        else:
            url = 'http://ws.audioscrobbler.com/2.0/?method=user.getPlaylists&user=' + self.lastfm_username + '&api_key=' + audioscrobbler_api_key + '&format=json'
            sts, data = self.cm.getPage(url, {'header': HEADER})
            if not sts:
                return
            try:
                data = json_loads(data)['playlists']['playlist']
                for x in range(len(data)):
                    item = data[x]
                    playlist_name = item['title']
                    playlist_id = item['id']
                    params = {'name': 'Lastfmlist_track', 'title': playlist_name, 'artist': playlist_id}
                    self.addDir(params)
            except Exception:
                printExc()  # wypisz co poszło nie tak

    def Lastfmlist_track(self, artist):
        printDBG("MusicBox - last.fm list track")

        playlist_id = "lastfm://playlist/" + artist
        url = 'http://ws.audioscrobbler.com/2.0/?method=playlist.fetch&playlistURL=' + playlist_id + '&api_key=' + audioscrobbler_api_key + '&format=json'
        print url
        sts, data = self.cm.getPage(url, {'header': HEADER})
        if not sts:
            return
        try:
            data = json_loads(data)['playlist']['trackList']['track']
            print data
            for x in range(len(data)):
                item = data[x]
                artist = item['creator']
                track_name = item['title']
                try:
                    iconimage = item['image']
                except Exception:
                    iconimage = ''
                search_string = urllib.quote(artist + ' ' + track_name + ' music video')
                params = {'title': track_name + ' - ' + artist, 'page': search_string, 'icon': iconimage}
                self.addVideo(params)
        except Exception:
            printExc()  # wypisz co poszło nie tak

###############################################################################
# Szukanie linku do materiału na youtube
###############################################################################
    def getLinksForVideo(self, cItem):
        printDBG("getLinksForVideo cItem[%s]" % cItem)
        
        videoUrls = []
        self.readYoutubeApiKey()
        if len(self.youtube_api_key) == 39:
            # quicker solution
        
            sts, data = self.cm.getPage("https://www.googleapis.com/youtube/v3/search?part=id%2Csnippet&q=" + cItem.get('page', '') + "&type=Music&maxResults=1&key=" + self.youtube_api_key)
            if sts: 
                match = re.compile('"videoId": "([^"]+?)"').findall(data)
     
                for item in match:
                    video_path = "https://www.youtube.com/watch?v=" + item
                    videoUrls = self._getLinksForVideo(video_path)
       
        if not videoUrls:
            # if apikey isn't present or previous search fails, use browser search (slower) 
        
            search_list = YouTubeParser().getSearchResult(cItem.get('page', ''), "music", 1 , '')
            if not search_list:
                return []
        
            video_path = search_list[0]['url']
            videoUrls = self._getLinksForVideo(video_path)
        
        return videoUrls

    def _getLinksForVideo(self, url):
        printDBG("_getLinksForVideo url[%s]" % url)

        if not url.startswith("http://") and not url.startswith("https://") :
            url = 'http://www.youtube.com/' + url

        return self.up.getVideoLinkExt(url)
    
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        title    = self.currItem.get("title", '')
        category = self.currItem.get("category", '')
        page = self.currItem.get("page", '')
        icon     = self.currItem.get("icon", '')
        album = self.currItem.get("album", '')
        country = self.currItem.get("country", '')
        artist = self.currItem.get("artist", '')
        printDBG( "handleService: |||||||||||||||||||||||||||||||||||| [%s] " % name )
        self.currList = []

        if str(page)=='None' or page=='': page = '0'

    #MAIN MENU
        if name is None:
            self.listsMainMenu()
    #LISTA
        elif category == 'itunes':
            self.Itunes_countries_menu(self.currItem['url'], self.currItem['item'])
        elif category == 'beatport':
            self.Beatport_top100(self.currItem['url'])
        elif category == 'billboard_charts':
            self.Billboard_charts(self.currItem['url'])
        elif category == 'billboard_albums':
            self.Billboard_chartsalbums(self.currItem['url'])
        elif category == 'lastfm':
            self.Lastfmlist()

    ###########
        elif name == 'Itunes_track_charts':
            self.Itunes_track_charts(page)
        elif name == 'Itunes_album_charts':
            self.Itunes_album_charts(page)
        elif name == 'Itunes_list_album_tracks':
            self.Itunes_list_album_tracks(page, album, country)
        elif name == 'List_album_tracks':
            self.List_album_tracks(page, artist, album, icon)
        elif name == 'Lastfmlist_track':
            self.Lastfmlist_track(artist)
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, MusicBox(), False)
