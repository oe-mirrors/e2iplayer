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
from datetime import datetime, tzinfo, timedelta
###################################################


def gettytul():
    return 'https://it.dplay.com/'

class Dplayit(CBaseHostClass):
 
    def __init__(self):

        CBaseHostClass.__init__(self)

        
        # for i18n: 
        #   _VALID_URL = r'''(?x)https?://
        #   (?P<domain>
        #       (?:www\.)?(?P<host>dplay\.(?P<country>dk|fi|jp|se|no))|
        #       (?P<subdomain_country>es|it)\.dplay\.com
        #   )/[^/]+/(?P<id>[^/]+/[^/?#]+)'''
        # 
        #
        # host = 'disco-api.' + domain if domain.startswith('dplay.') else 'eu2-prod.disco-api.com'
        # realm = 'dplay' + country

        # dk|fi|jp|se|no :
        # main url : dplay.(dk|fi|jp|se|no)
        # api url: disco-api.dplay.(dk|fi|jp|se|no)

        # it|es:
        # main url : (it|es).dplay.com
        # api url: eu2-prod.disco-api.com
        
        ################ italian version #################
        
        self.MAIN_URL = "http://it.dplay.com/"
        self.API_URL = "https://eu2-prod.disco-api.com"
        self.TOKEN_URL = self.API_URL  + "/token?realm=dplayit"
        
        ######################################

        self.CHANNEL_MENU_URL = self.API_URL  + "/content/channels?sort=name&page[size]=50&include=images"
        self.SHOWBYCHANNEL_URL = self.API_URL  +  "/content/shows?sort=name&filter[primaryChannel.id]={0}&page[size]=100&include=images"
        
        self.PROGRAMS_URL = self.API_URL  + "/content/shows"
        self.PROGRAMSBYLETTER_URL = self.PROGRAMS_URL  + "?sort=name&page[size]=100&include=images&filter[name.startsWith]={0}"
        self.SHOW_URL = self.PROGRAMS_URL + "/{0}?include=seasons"
        self.VIDEOBYSEASON_URL = self.API_URL  + "/content/videos?filter[show.id]={0}&filter[seasonNumber]={1}&page[size]=100&include=images&sort=episodeNumber&filter[videoType]=EPISODE"
        self.VIDEOBYSHOW_URL = self.API_URL  + "/content/videos?filter[show.id]={0}&page[size]=100&include=images"
        
        self.VIDEO_URL = self.API_URL  + "/content/videos/{0}"
        self.PLAY_URL= self.API_URL  + "/playback/videoPlaybackInfo/{0}"
        
        self.GENRE_URL = "https://eu2-prod.disco-api.com/content/genres?sort=name&page[size]=50&include=images"
        self.SHOWBYGENRE_URL = "https://eu2-prod.disco-api.com/content/shows?filter[genre.id]={0}&page[size]=100&include=images"

        self.defaultParams = {'header': {'User-Agent' : 'okhttp/4.2.1'}}
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
            if not sts: 
                return
            
            printDBG("-----------")
            printDBG(data)
            printDBG("-----------")

            try:
                response = json_loads(data)
            
                self.AccessToken = response['data']['attributes']['token']
                printDBG(' Dplay Access token %s ' % self.AccessToken)         
            except:
                printExc()
            
        if self.AccessToken != None and self.AccessToken != "":
            # create header with current access token
            headers = {'User-Agent' : 'okhttp/4.2.1', 
                       'Accept-Encoding' : 'gzip, deflate',
                       'Authorization' : 'Bearer {0}'.format(self.AccessToken)
                       }
            
            return headers
    
    def loadImagesFromJson(self, jsonIncluded):
        printDBG("Dplay.loadImagesFromJson")
        images = {}
        
        #printDBG("---------------------")
        #printDBG(str(jsonIncluded))
        #printDBG("---------------------")

        for img in jsonIncluded:
            #printDBG(str(img))
            try:
                if img.get("type","") == "image":
                    img_id = img.get("id","")
                    if img_id:
                        img_path = img["attributes"]["src"]
            
                        images[img_id] = img_path
            except:
                pass
        #printDBG(str(images))
        return images

    def loadSeasonsFromJson(self, jsonIncluded):
        printDBG("Dplay.loadSeasonsFromJson")
        seasons = []
        
        for s in jsonIncluded:
            #printDBG(str(s))
            try:
                if s.get("type","") == "season":
                    season_id = s.get("id","")
                    if season_id:
                        seasons.append ( {
                            "seasonId": season_id,
                            "seasonNumber" : s["attributes"]["seasonNumber"],
                            "videoCount": s["attributes"]["videoCount"],
                            'episodeCount': s["attributes"]['episodeCount']                            
                        })
            except:
                pass
        
        #printDBG(str(seasons))
        return seasons
    
    def getLinksForVideo(self, cItem):
        printDBG("Dplay getLinksForVideo [%s]" % cItem)
        linksTab=[]

        if cItem["category"] == 'video' :
            video_id = cItem.get("video_id", "")
            
            if not video_id:
                return linksTab
            
            url = self.PLAY_URL.format(video_id) 
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
        
        try:
            response=json_loads(data)
            
            imgList = self.loadImagesFromJson(response.get("included",[]))
            
            for channel in response["data"]:
                ch_id = channel["id"]
                attr = channel["attributes"]
                title = attr.get("name","")
                desc = attr.get("description", "")
                packages = attr.get("packages", [])
                
                if packages[0] != "Free":
                    title = title + " [%s]" % packages[0]
                                    
                rel = channel.get("relationships",{})
                images = rel.get("images",[])
                if images:
                    icon_code = images["data"][0]["id"] 
                    
                    if icon_code in imgList:
                        icon = imgList[icon_code]
                    else:
                        icon = ""
                else:
                    icon = ""
                    
                params={'category':'channel', 'title': title , 'desc': desc, 'icon': icon, 'id': ch_id}
                #printDBG(str(params))
                self.addDir(params)

        except:
            printExc()

    
    def listChannelById(self,cItem):
        
        printDBG("Dplay start single channel list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        ch_id=cItem["id"]
        sts, data = self.getPage(self.SHOWBYCHANNEL_URL.format(ch_id), { 'header': h })
        if not sts: 
            return
        
        #printDBG(data)
        response = json_loads(data)

        self.listShows(data)
        
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
        
        if letter == "0-9":
            n = True
            url = self.PROGRAMS_URL  + "?sort=name&page[size]=50&include=images"
        else:
            n = False
            url = self.PROGRAMSBYLETTER_URL.format(letter)
        
        sts, data = self.getPage(url, { 'header': h })
        if not sts: 
            return
        
        self.listShows(data, number=n)
    
    def listProgramItems(self,cItem):
        title = cItem['title']
        show_id = cItem['id']
        printDBG("Dplay start item list of program '%s' with Id %s" % (title,show_id) )
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        url = self.SHOW_URL.format(show_id)
        sts, data = self.getPage(url, { 'header': h })
        if not sts: 
            return

        #printDBG(data)
        try:
            response=json_loads(data)
            
            #attr = response["data"]["attributes"]
            
            seasonsList = self.loadSeasonsFromJson(response.get("included",[]))
            
            for s in seasonsList:
                season_number = s["seasonNumber"]
                
                # search videos for each season
                videosForSeason=[]
                url = self.VIDEOBYSEASON_URL.format(show_id, season_number)
                
                sts, data = self.getPage(url, { 'header': h })
                
                if sts:
                    try:
                        resp_season = json_loads(data) 
                        
                        imgList = self.loadImagesFromJson(resp_season.get("included",[]))
                        
                        for video in resp_season["data"]:
                            video_id = video.get("id","")
                            if not video_id:
                                continue
                                
                            attr = video["attributes"]

                            name = attr.get("name","")
                            desc = attr.get("description","")
                            num_episode = attr.get("episodeNumber","")

                            if 'videoDuration' in attr:
                                desc = _("Duration") + ": %s" % str(timedelta(seconds = int(attr['videoDuration'] / 1000))) + "\n" + desc
                            
                            plus = False
                            
                            if 'packages' in attr:
                                desc = desc + "\n" + _("Packages") + ":"
                                for p in attr['packages']:
                                    if p == "Premium" :
                                        pp = "Dplay plus"
                                        plus = True
                                    else:
                                        pp = p
                                    
                                    desc = desc + " " + pp
                                    
                                    
                            if 'publishEnd' in attr:
                                date = datetime.strptime(attr['publishEnd'], '%Y-%m-%dT%H:%M:%SZ')
                                desc = '{0}\n{1} {2}'.format(desc, "Disponibile fino a ", date.strftime("%d/%m/%Y"))
                                    
                            title = '{0} ({1} {2} - {3} {4})'.format(name, _("Season"), season_number, _("Episode"), num_episode)
                            if plus:
                                title = title + " (PLUS)"
                            
                            rel = video.get("relationships",{})
                            images = rel.get("images",[])
                            if images:
                                icon_code = images["data"][0]["id"] 
                                
                                if icon_code in imgList:
                                    icon = imgList[icon_code]
                                else:
                                    icon = ""
                            else:
                                icon = ""
                                
                            params = {'title': title, 'name': name, 'desc': desc, 'video_id': video_id, 'icon': icon, 'category': 'video'} 
                            #printDBG(str(params))
                            videosForSeason.append(params)

                        if len(videosForSeason)>0:
                            # add seasons
                            params = dict(cItem)
                            params.update({'category': 'season', 'title': _("Season") + " %s (%s)" % (season_number, len(videosForSeason)), 'subitems': videosForSeason})
                            self.addDir(params)
                        
                    except:
                        printExc()
                    
                
        except:
            printExc()
        
    def listGenres (self, cItem):
        printDBG("Dplay start genres list")
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.GENRE_URL, { 'header': h })
        if not sts: return
        
        #printDBG(data)
        try:
            response = json_loads(data)

            imgList = self.loadImagesFromJson(response.get("included",[]))

            for genre in response["data"]:

                gen_id = genre["id"]
                attr = genre["attributes"]
                title = attr.get("name","")
                                    
                rel = genre.get("relationships",{})
                images = rel.get("images",[])
                if images:
                    icon_code = images["data"][0]["id"] 
                    
                    if icon_code in imgList:
                        icon = imgList[icon_code]
                    else:
                        icon = ""
                else:
                    icon = ""

                params={'category':'genre', 'title': title, 'icon': icon, 'id': gen_id}
                #printDBG(str(params))
                self.addDir(params)     
        except:
            printExc()
            
    def listShows(self, data, number=False):
        printDBG("Dplay listShows")
            
        try:
            response=json_loads(data)
            
            imgList = self.loadImagesFromJson(response.get("included",[]))
            
            for show in response["data"]:
                show_id = show['id']
                attrib = show.get("attributes",{})
                
                title = attrib.get("name","")
                if number and title[0]>="A":
                    continue
                
                desc = attrib.get("description","")
                
                rel = show.get("relationships",{})
                images = rel.get("images",[])
                if images:
                    icon_code = images["data"][0]["id"] 
                    
                    if icon_code in imgList:
                        icon = imgList[icon_code]
                    else:
                        icon = ""
                else:
                    icon = ""

                params={'category':'program', 'title': title , 'desc': desc, 'icon': icon, 'id': show_id }
                #printDBG(str(params))
                self.addDir(params)     
        except:
            printExc()

            
    def listShowsByGenre(self, cItem):
        printDBG("Dplay start show list by genre")
        gen_id=cItem["id"]
        h=self.getHeader()
        
        if h == None or h == "" :
            printDBG('Dplay wrong initialization')
            return
        
        sts, data = self.getPage(self.SHOWBYGENRE_URL.format(gen_id), { 'header': h })
        if not sts: 
            return
        
        self.listShows(data)
            
    
    def showSeason(self, cItem):
        printDBG('Dplay showSeason [%s]' % cItem)
        videoList = cItem.get("subitems",[]) 
        
        for v in videoList:
            self.addVideo(v)
        
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
        elif category == 'channel_list':
            if self.currItem.get("url",'') == '/api/show/GetList':
                self.listPrograms(self.currItem, self.currItem.get("ch_id",'0'))
        elif category == 'season':
            self.showSeason(self.currItem)
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Dplayit(), True, [])
    
