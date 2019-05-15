# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from datetime import datetime, tzinfo
###################################################


def gettytul():
    return 'https://it.dplay.com/'

class Dplayit(CBaseHostClass):
 
    def __init__(self):

        CBaseHostClass.__init__(self)

        self.MAIN_URL = "http://it.dplay.com/"
        self.MAIN_SERVER_URL="https://dplayproxy.azurewebsites.net"
        self.TOKEN_URL = self.MAIN_SERVER_URL + "/api/config/init"

        self.CHANNEL_MENU_URL = self.MAIN_SERVER_URL + "/api/Channel/GetList"
        self.CHANNEL_URL = self.MAIN_SERVER_URL + "/api/Channel/GetById?id={0}"
        
        self.PROGRAMS_URL = self.MAIN_SERVER_URL + "/api/Show/GetList"
        self.SHOW_URL = self.MAIN_SERVER_URL + "/api/Show/GetById/?id={0}"
        self.SHOWBYGENRE_URL = self.MAIN_SERVER_URL + "/api/Show/GetByGenre?genreId={0}"

        self.VIDEO_URL = self.MAIN_SERVER_URL + "/api/Video/GetById/?id={0}"
        self.POPULAR_URL = self.MAIN_SERVER_URL + "/api/video/GetVideoPopolari"
        self.LAST_ADDED_URL = self.MAIN_SERVER_URL + "/api/video/GetUltimiVideoAggiunti"

        self.PLAYLIST_MENU_URL = self.MAIN_SERVER_URL + "/api/Playlist/GetList"
        self.PLAYLIST_URL = self.MAIN_SERVER_URL + "/api/Playlist/GetById/{0}"
        
        self.GENRE_URL = self.MAIN_SERVER_URL + "/api/genre/GetList"
        
        #self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')        
        #self.defaultParams = { 'header': {'User-Agent' : 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:53.0) Gecko/20100101 Firefox/53.0'}}
        self.defaultParams = {'header': {'User-Agent' : 'okhttp/3.3.0'}}
        self.AccessToken=""
        
    def getPage(self, url, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        #printDBG(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getHeader(self, add_bearer = False):
        if self.AccessToken == "":
            printDBG('Dplay init and get access token')
            
            sts, data = self.getPage(self.TOKEN_URL)
            if not sts: return
            
            response = json_loads(data)
            self.AccessToken = response['Data']['AccessToken']
            printDBG(' Dplay Access token %s ' % self.AccessToken)         
        
        if self.AccessToken != None and self.AccessToken != "":
            # create header with current access token
            headers = {'User-Agent' : 'okhttp/3.3.0', 
                       'Accept-Encoding' : 'gzip, deflate',
                       'AccessToken' : self.AccessToken}
            if add_bearer:
                headers['Authorization'] = 'Bearer {0}'.format(self.AccessToken[0 : self.AccessToken.index('__!__') - len(self.AccessToken)])
            
            return headers
    
    
    def getLinksForVideo(self, cItem):
        printDBG("Dplay getLinksForVideo [%s]" % cItem)
        linksTab=[]

        if cItem["category"] == 'video' :
            video_id = cItem["video_id"] if "video_id" in cItem else ''
            url=cItem["url"]
            h=self.getHeader(True)
        
            if h == None or h == "" :
                printDBG('Dplay wrong initialization')
                return linksTab
        
            sts, data = self.getPage(url, { 'header': h })
            if not sts: return
        
            #printDBG(data)
            response=json_loads(data)
            stream_url = response['data']['attributes']['streaming']['hls']['url']
            stream_url=strwithmeta(stream_url, h)
            linksTab.extend(getDirectM3U8Playlist(stream_url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))  
                        
        else: 
            printDBG("Dplay: video form category %s with url %s not handled" % (cItem["category"],cItem["url"]));
            linksTab.append({'url': cItem["url"], 'name': 'link1'})
        
        return linksTab

   
    def listMainMenu(self, cItem):
        MAIN_CAT_TAB = [{'category':'ondemand', 'title': 'Programmi on demand'},
                        {'category':'channel-menu', 'title': 'Canali'},
                        {'category':'genre-menu', 'title': 'Generi'}]
                        # these item are not working
                        #{'category':'popular', 'title': 'Video popolari'},
                        #{'category':'lastadded', 'title': 'Ultimi aggiunti'}]  
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def listChannels(self,cItem):
        printDBG("Dplay start channel list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.CHANNEL_MENU_URL, { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response=json_loads(data)

        for channel in response["Data"]:
            title = channel["Name"]
            desc = channel["Description"] if "Description" in channel else ''
            icon = channel['Images'][0]['Src']
            ch_id = channel['Id']
            params={'category':'channel', 'title': title , 'desc': desc, 'icon': icon, 'id': ch_id}
            self.addDir(params)     
    
    def listChannelById(self,cItem):
        
        printDBG("Dplay start single channel list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        ch_id=cItem["id"]
        sts, data = self.getPage(self.CHANNEL_URL.format(ch_id), { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response = json_loads(data)

        channel = response["Data"]
        for item in channel["MenuItems"]:
            title = item["Label"]
            if "ResourceId" in item:
                resource_id = item["ResourceId"] 
                self.addDir(MergeDicts(cItem, {'category':'playlist', 'title': title, 'id' : resource_id }))  
            else:
                url = item["Url"] if "Url" in item else ''
                if url!="/api/video/GetVideoPopolari" and url !="/api/video/GetUltimiVideoAggiunti":
                    self.addDir(MergeDicts(cItem, {'category':'channel_list', 'title': title, 'url' : url, 'id' : ch_id}))  
                
        
    def listPrograms(self,cItem,ch_id='0'):
        printDBG("Dplay start alphabetical index" )

        # 0-9
        self.addDir(MergeDicts(cItem, {'category':'programs_az', 'title': "0-9", 'ch_id': ch_id }))  
        
        #a-z
        for i in range(26):
            self.addDir(MergeDicts(cItem, {'category':'programs_az', 'title': chr(ord('A')+i) , 'ch_id': ch_id}))  

    
    def listProgramsByLetter(self,cItem):
        printDBG("Dplay start programs list")
        letter=cItem["title"]
        ch_id=cItem["ch_id"]
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.PROGRAMS_URL, { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response=json_loads(data)

        for show in response["Data"]:
            title = show["Name"]

            if (ch_id == "0") or (ch_id == show["Channel"]["Id"]):
                if title[:1].upper() == letter: 
                    desc = show["Description"] if "Description" in show else ''
                    icon = show['Images'][0]['Src']
                    show_id = show['Id']
                    params={'category':'program', 'title': title , 'desc': desc, 'icon': icon, 'id': show_id }
                    self.addDir(params)     
                elif letter == "0-9" and title[:1].isdigit():
                    desc = show["Description"] if "Description" in show else ''
                    icon = show['Images'][0]['Src']
                    show_id = show['Id']
                    params={'category':'program', 'title': title , 'desc': desc, 'icon': icon, 'id': show_id }
                    self.addDir(params)     

    
    def listProgramItems(self,cItem):
        title = cItem['title']
        show_id = cItem['id']
        printDBG("Dplay start item list of program '%s' with Id %s" % (title,show_id) )
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        url=self.SHOW_URL.format(show_id)
        sts, data = self.getPage(url, { 'header': h })
        if not sts: return

        #printDBG(data)
        response=json_loads(data)
        
        if len(response["Data"]["Sections"]) > 0:
            icon = response["Data"]['Images'][0]['Src']
            for season in response["Data"]["Sections"][0]["Items"]:
                season_number = season['SeasonNumber'] if 'SeasonNumber' in season else '0'
                if 'Episodes' in season:
                    for video in season['Episodes']:
                        name=video["Name"]
                        desc=video["Description"]
                        num_episode=video["EpisodeNumber"]
                        video_id=video["Id"]
                        if 'PublishEndDate' in video:
                            date = datetime.strptime(video['PublishEndDate'], '%Y-%m-%dT%H:%M:%SZ')
                            desc = '{0}\n\n{1} {2}'.format(desc, "Disponibile fino a ", date.strftime("%d/%m/%Y"))
                        title = '{0} ({1} {2} - {3} {4})'.format(name, _("Season"), season_number, _("Episode"), num_episode)
                        videoUrl=video["PlaybackInfoUrl"]
                        #printDBG ("add video '%s' with playback info url '%s'" % (title,videoUrl)) 
                        self.addVideo(MergeDicts(cItem, {'title': title,'name': title, 'desc': desc, 'video_id': video_id, 'url':videoUrl, 'icon': icon, 'category': 'video'}))  
    
    def listGenres (self, cItem):
        printDBG("Dplay start genres list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.GENRE_URL, { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response = json_loads(data)

        for genre in response ["Data"]:
            title = genre["Name"]
            icon = genre["Images"][0]["Src"]
            url = genre["Url"]
            gen_id = genre["Id"]
            params={'category':'genre', 'title': title, 'icon': icon, 'id': gen_id, 'url': url }
            self.addDir(params)     
        
    def listShowsByGenre(self, cItem):
        printDBG("Dplay start show list by genre")
        gen_id=cItem["id"]
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.SHOWBYGENRE_URL.format(gen_id), { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response=json_loads(data)
        
        for show in response["Data"]:
            title = show["Name"]
            desc = show["Description"] if "Description" in show else ''
            icon = show['Images'][0]['Src']
            show_id = show['Id']
            params={'category':'program', 'title': title , 'desc': desc, 'icon': icon, 'id': show_id }
            self.addDir(params)     
            
    def showPlaylist(self,cItem):
        printDBG("Dplay show playlist")
        list_id=cItem["id"]
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.PLAYLIST_URL.format(list_id), { 'header': h })
        if not sts: return
        
        #printDBG(data)
        response = json_loads(data)
        
        for video in response["Data"]["Items"]:
            icon = video['Images'][0]['Src']
            title = video["Name"]
            desc = video["Description"]
            video_id = video["Id"]
            videoUrl = video["PlaybackInfoUrl"]
            printDBG ("add video '%s' with playback info url '%s'" % (title,videoUrl)) 
            self.addVideo(MergeDicts(cItem, {'title': title,'name': title, 'desc': desc, 'video_id': video_id, 'url':videoUrl, 'icon': icon, 'category': 'video'}))  

        
    def listPopular(self, cItem, ch_id='0'):
        printDBG("Dplay start popular list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.POPULAR_URL, { 'header': h })
        if not sts: return
        
        printDBG(data)
        response = json_loads(data)
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('Dplay handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        self.informAboutGeoBlockingIfNeeded('IT')
        
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')
        subtype  = self.currItem.get("sub-type",'')
        
        printDBG( "handleService: >> name[%s], category[%s] " % (name, category) )
        self.currList = []
        
        #MAIN MENU
        if name == None:
            self.listMainMenu({'name':'category'})
        elif category == 'channel-menu':
            self.listChannels(self.currItem)
        elif category == 'ondemand':
            self.listPrograms(self.currItem)
        elif category == 'popular':
            self.listPopular(self.currItem)
        elif category == 'programs_az':
            self.listProgramsByLetter(self.currItem)
        elif category == 'program':
            self.listProgramItems(self.currItem)
        elif category == 'channel':
            self.listChannelById(self.currItem)
        elif category == 'genre-menu':
            self.listGenres(self.currItem)
        elif category == 'genre':
            self.listShowsByGenre(self.currItem)
        elif category == 'playlist':
            self.showPlaylist(self.currItem)
        elif category == 'channel_list':
            if self.currItem.get("url",'') == '/api/show/GetList':
                self.listPrograms(self.currItem, self.currItem.get("ch_id",'0'))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Dplayit(), True, [])
    
