# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, GetIPTVSleep, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, GetJSScriptFile, PrevDay
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

from Screens.MessageBox import MessageBox

###################################################
# FOREIGN import
###################################################
import urllib
import re
import uuid
import time
import datetime
import math
import cookielib
import datetime
from datetime import timedelta
###################################################


def gettytul():
    return 'https://mediasetplay.it/'

class MediasetPlay(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history':'mediasetplay.it', 'cookie':'mediasetplay.it.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='firefox')
        self.HTTP_HEADER.update({'Referer':'https://www.mediasetplay.mediaset.it/', 'Accept':'application/json', 'Content-Type':'application/json'})
        self.defaultParams = {'header':self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

        self.MAIN_URL    = 'https://www.mediasetplay.mediaset.it/'
        self.INDEX_URL = "https://static3.mediasetplay.mediaset.it/cataloglisting/azListing.json"
        self.API_BASE_URL = 'https://api-ott-prod-fe.mediaset.net/PROD/play'
        
        self.FEED_URL = 'https://feed.entertainment.tv.theplatform.eu/f/PR1GhC'
        self.FEED_EPG_URL = self.FEED_URL + '/mediaset-prod-all-listings?byListingTime=%interval%&byCallSign=%cs%'
        self.FEED_CHANNELS_URL = self.FEED_URL + '/mediaset-prod-all-stations?fields=title,callsign,thumbnails&sort=mediasetstation$comscoreVodChId'
        self.FEED_CHANNEL_URL = self.FEED_URL + '/mediaset-prod-all-stations?byCallSign=%cs%'
        self.FEED_SHOW_URL = self.FEED_URL + '/mediaset-prod-all-brands?byCustomValue={brandId}{%brandId%}&sort=mediasetprogram$order'
        self.FEED_SHOW_COUNT = self.FEED_URL + '/mediaset-prod-all-brands?byTags=%cat%&count=true&entries=false'
        self.FEED_SHOW_INDEX_URL = self.FEED_URL + '/mediaset-prod-all-brands?byTags=%cat%&fields=title,description,thumbnails,mediasetprogram$brandId,mediasetprogram$seasonTitle,mediasetprogram$brandChannelCode&sort=title,mediasetprogram$seasonTitle&range=%range%'       
        self.FEED_SHOW_SUBITEM_URL = self.FEED_URL + '/mediaset-prod-all-programs?byCustomValue={brandId}{%brandId%},{subBrandId}{%subBrandId%}&sort=mediasetprogram$publishInfo_lastPublished|desc&count=true&entries=true&range=0-200'
        self.FEED_EPISODE_URL = self.FEED_URL + '/mediaset-prod-all-programs?byGuid={0}'
        self.DEFAULT_ICON_URL = 'https://i.pinimg.com/originals/34/67/9b/34679b83e426516b478ba9d63dcebfa2.png' #'http://www.digitaleterrestrefacile.it/wp-content/uploads/2018/07/mediaset-play.jpg' #'https://cdn.one.accedo.tv/files/5b0d3b6e23eec6000dd56c7f'

        self.cacheLinks = {}
        self.initData = {}
        
    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}: addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)


    def getBestThumb(self, thumbnails, vertical=False):
        # get best thumbnail available
        if vertical:
            target = 'image_vertical-'
        else:
            target = 'image_keyframe_poster-'

        thumbs = [];        
        for t in thumbnails:
            if t.find(target) != -1:
                t = t.replace(target, '')
                thumbs.append({'x': int(t.split('x')[0]) , 'y': int(t.split('x')[1]) })

        thumbs.sort(reverse=True)

        if len(thumbs)> 0:
                label = target + str(thumbs[0]["x"]) + 'x' + str(thumbs[0]["y"])
                return thumbnails[label]['url']
        else:          
            if vertical:
                return self.getBestThumb(thumbnails, False)
            else:
                return ""
    
    def getVideoLinks(self, videoUrl):
        printDBG("MediasetPlay.getVideoLinks [%s]" % videoUrl)
        # mark requested link as used one
        if len(self.cacheLinks.keys()):
            for key in self.cacheLinks:
                for idx in range(len(self.cacheLinks[key])):
                    if videoUrl in self.cacheLinks[key][idx]['url']:
                        if not self.cacheLinks[key][idx]['name'].startswith('*'):
                            self.cacheLinks[key][idx]['name'] = '*' + self.cacheLinks[key][idx]['name']
        
        type = strwithmeta(videoUrl).meta.get('priv_type', '')
        if type == 'DASH/MPD':
            return getMPDLinksWithMeta(videoUrl, checkExt=False, sortWithMaxBandwidth=999999999)
        elif type == 'HLS/M3U8':
            return getDirectM3U8Playlist(videoUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=999999999)

        return []
    
    def getLinksForVideo(self, cItem):
        printDBG(": %s" % cItem)
        #self.initApi()

        linksTab=[]

        if cItem['category'] == 'onair':
            channelId = cItem.get('call_sign')
            url = self.FEED_CHANNEL_URL.replace("%cs%", channelId)
            sts, data = self.getPage(url)
            if not sts: return

            data = json_loads(data)
            for tuningInstructions in data['entries'][0]['tuningInstruction'].itervalues():
                for item in tuningInstructions:
                    printDBG(" ------------>>>>>> " + str(item))
                    url = item['publicUrls'][0]
                    if 'mpegurl' in item['format'].lower():
                        f = 'HLS/M3U8'
                        req=urllib.urlopen(url)
                        videoUrl=req.geturl()                        
                        
                        linksTab.append({'name':f, 'url': videoUrl})
                        #linksTab.extend(getDirectM3U8Playlist(videoUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=999999999))
                        
        elif cItem['category'] == 'epg_video':
            url = self.FEED_EPISODE_URL.format(cItem["guid"])
            
            sts, data = self.getPage(url)
            if not sts: return

            url = json_loads(data)['entries'][0]['media'][0]['publicUrl']
            req=urllib.urlopen(url)
            videoUrl=req.geturl()                        
            
            linksTab.append({'name': 'link', 'url': videoUrl})

        elif cItem['category'] == 'program_video':
            req=urllib.urlopen(cItem["url"])
            videoUrl=req.geturl()                        

            linksTab.append({'name': 'link', 'url': videoUrl})
            
        elif cItem["category"] == 'no_video':
            printDBG('no video for %s' % str(cItem))
        
        else:
            linksTab.append({'name': 'link', 'url': cItem["url"]})

        printDBG(str(linksTab))
        return linksTab
    
    def initApi(self):
        if self.initData: return 
        url = self.API_BASE_URL + '/idm/anonymous/login/v1.0'
        params = MergeDicts(self.defaultParams, {'raw_post_data':True, 'collect_all_headers':True})
        cid = str(uuid.uuid4())
        post_data = '{"cid":"%s","platform":"pc","appName":"web/mediasetplay-web/2e96f80"}' % cid

        sts, data = self.getPage(url, params, post_data=post_data)
        if not sts: return
        printDBG(data)
        printDBG(self.cm.meta)
        try:
            headers = {'t-apigw':self.cm.meta['t-apigw'], 't-cts':self.cm.meta['t-cts']}
            data = json_loads(data)
            if data['isOk']:
                tmp = data['response']
                self.initData.update({'traceCid':tmp['traceCid'], 'cwId':tmp['cwId'], 'cid':cid})
                self.HTTP_HEADER.update(headers)
        except Exception:
            printExc()
        
        if not self.initData: self.sessionEx.waitForFinishOpen(MessageBox, _("API initialization failed!"), type=MessageBox.TYPE_ERROR, timeout=20)
    
    def listMain(self, cItem):
        printDBG("MediasetPlay.listMain")
        MAIN_CAT_TAB = [{'category':'ondemand', 'title': 'Programmi on demand'},
                        {'category':'onair', 'title': 'Dirette tv'},
                        {'category':'channels', 'title': 'Replay/EPG'}]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def getChannelList(self):
        printDBG("MediasetPlay.getChannelList")
        channels = []

        sts, data = self.getPage(self.FEED_CHANNELS_URL)
        if sts: 
            data = json_loads(data)
            for item in data['entries']:
                icon = self.getFullIconUrl( item['thumbnails']['channel_logo-100x100']['url']) #next(iter(item['thumbnails']))['url'] )
                title = item['title']
                channels.append ( {'title':title, 'icon':icon, 'call_sign':item['callSign']})
            
        return channels
    
    def listOnAir(self, cItem):
        printDBG("MediasetPlay.listOnAir")

        channels = self.getChannelList()
        for item in channels:
            self.addVideo(MergeDicts(cItem, {'category': 'onair', 'good_for_fav':True, 'title': item["title"], 'icon': item["icon"], 'call_sign': item['call_sign']}))

    def listChannels(self,cItem):
        printDBG("MediasetPlay.listChannels")
        channels=self.getChannelList()
        for item in channels:
            self.addDir(MergeDicts(cItem, {'category': 'list_time', 'title': item["title"] , 'icon': item["icon"], 'call_sign': item['call_sign']}))

    def listDates(self, cItem):
        printDBG("MediasetPlay.listDates")

        days = ["Domenica", "Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
        months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    
        for i in range(7):
            day = datetime.date.today() - datetime.timedelta(days = i)
            start = datetime.datetime(day.year,day.month,day.day,0,0,0) 
            end = start + datetime.timedelta(days=1, hours=2)
            s = int (time.mktime(start.timetuple())* 1000)
            e = int(time.mktime(end.timetuple()) * 1000)
            interval = "%s~%s" % (s, e)
            printDBG("Ricerca fra i tempi unix : " + interval)
            day_str = days[int(day.strftime("%w"))] + " " + day.strftime("%d") + " " + months[int(day.strftime("%m"))-1]
            self.addDir(MergeDicts(cItem, {'good_for_fav':False, 'category':'date', 'title': day_str , 'name': day.strftime("%d-%m-%Y"), 'interval': interval}))              
   
    def getDateTimeFromStr(self,s):
        sec=int(s)/1000
        t=time.localtime(sec)
        return t
    
    def listEPG(self,cItem):
        printDBG("MediasetPlay.listEPG")
        url = self.FEED_EPG_URL.replace('%interval%',cItem['interval']).replace('%cs%',cItem['call_sign'])
        
        sts, data = self.getPage(url)
        if not sts: return
        
        data=json_loads(data)
        for item2 in data['entries'][0]['listings']:
            d1 = self.getDateTimeFromStr(item2["startTime"])
            d2 = self.getDateTimeFromStr(item2["endTime"])
            title = "%02d:%02d-%02d:%02d     " % (d1[3],d1[4],d2[3],d2[4]) + item2["mediasetlisting$epgTitle"] 

            item = item2['program']
            guid = item['guid']
            icon = self.getBestThumb(item['thumbnails'], True)
            if item["mediasetprogram$hasVod"]:
                # video on demand available
                desc = []
                desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0]) 
                desc.append(item['mediasetprogram$publishInfo']['description']) 
                desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
                if 'mediasetprogram$numberOfViews' in item:
                    desc.append(_('%s views') % item['mediasetprogram$numberOfViews'] )
                desc = [' | '.join(desc)]
                desc.append(item['title'])
                if item.get('description', ''):
                    desc.append(item.get('description', ''))
                printDBG(str(desc))
                desc= '\n'.join(desc)
                params = {'good_for_fav':True, 'category': 'epg_video', 'title':title, 'desc': desc, 'icon':icon, 'guid':guid}
                printDBG(str(params))
                self.addVideo( params)
            else:
                # no video on demand
                title = title + "\c00??8800 [" + _("not available") + "]"
                params = {'good_for_fav': False, 'category': 'no_video', 'title':title, 'icon':icon, 'guid':guid, 'desc' : 'Non disponibile'}
                printDBG(str(params))
                self.addVideo(params)
                
    def listOnDemand(self, cItem):
        printDBG("MediasetPlay.listMain")
        
        MAIN_CAT_TAB = [{'category':'az', 'title': 'Programmi on demand'},
                        {'category':'onair', 'title': 'Dirette tv'},
                        {'category':'channels', 'title': 'Canali'}]
        self.listsTab(MAIN_CAT_TAB, cItem)  

    def listAZFilters(self, cItem, nextCategory):
        printDBG('MediasetPlay.listAZFilters')
        idx = cItem.get('az_filter_idx', 0)
        cItem = MergeDicts(cItem, {'az_filter_idx':idx + 1})
        if idx == 0:
            # create first choice list (categories)
            sts, data = self.getPage(self.INDEX_URL)
            if not sts: return
            
            categories = json_loads(data)["metadata"]["categories"]
            filtersTab = [{'title': 'Tutti generi'}]
            for c in categories:
                filtersTab.append({'title': c, 'f_category':c})

        elif idx == 1:
            filtersTab = [{'title': 'Tutti'},
                          {'title': 'In onda',      'f_onair':True},]
        elif idx == 2:
            filtersTab = []
            cItem['category'] = nextCategory

            sts, data = self.getPage(self.INDEX_URL)
            if not sts: return
            data = json_loads(data)

            if "f_category" in cItem:
                label = cItem["f_category"]
            else:
                label = "nofilter"
            
            if "f_onair" in cItem:
                # only on air programs
                label = label + "_onair"
            else:
                label = label 

            filtersTab.append({'title': 'Tutti',  'f_query':'*'})
            for l in data["data"][label]:
                filtersTab.append({'title': l.upper(), 'f_query': l.upper() })

        self.listsTab(filtersTab, cItem)

    def listAZItems(self, cItem, page=0):
        printDBG('MediasetPlay.listAZItems')

        if 'f_category' in cItem: 
            url = self.FEED_SHOW_INDEX_URL.replace("%cat%", cItem['f_category'].replace(" ", "%20"))
            url_count = self.FEED_SHOW_COUNT.replace("%cat%", cItem['f_category'].replace(" ", "%20"))
        else:
            url = self.FEED_SHOW_INDEX_URL.replace("%cat%", "Brand")
            url_count = self.FEED_SHOW_COUNT.replace("%cat%", "Brand")
        
        sts, data = self.getPage(url_count)
        if not sts: return
        
        data = json_loads(data)
        number_of_entries = data["totalResults"]
        printDBG("entries: %s " % number_of_entries)
        
        range_start = 1 
        while range_start < number_of_entries:
            range_end = range_start + 299
            range_str = "%s-%s" % (range_start,range_end)

            sts, data = self.getPage(url.replace("%range%", range_str))
            if sts: 

                data = json_loads(data)

                for item in data['entries']:
                    # control if program is on air now, if requested 
                    title = item['title']
                    f_query = cItem.get('f_query','*')
                    if (not ('f_onair' in cItem)) or (('f_onair' in cItem) and ("mediasetprogram$brandChannelCode" in item)) : 
                        # control starting letter
                        if (f_query == '*') or ((f_query == '0') and title[:1].isdigit() ) or ( not(f_query in ['0','*']) and title[:1] == f_query ) :  
                            # can add program to list    
                            printDBG(title)
                            icon = self.getBestThumb(item['thumbnails'], True)
                            brandId = item.get("mediasetprogram$brandId",'')
                            desc = ["Id:" + brandId, item.get('description', '')]
                            if desc[1] == None:
                                desc = "Id:" + brandId
                            else:
                                desc = '\n'.join(desc)
                            if "mediasetprogram$seasonTitle" in item:
                                if item["mediasetprogram$seasonTitle"] != "0":
                                    title = item["mediasetprogram$seasonTitle"]
                            params = {'good_for_fav':True, 'title':title, 'url':url, 'icon': icon, 'desc': desc, 'category': 'program', 'brandId': brandId}
                            self.addDir(MergeDicts(cItem, params))

            range_start= range_start + 300
                                     
    def listProgramItems(self, cItem):
        brandId=cItem["brandId"]    
        url = self.FEED_SHOW_URL.replace('%brandId%',brandId)
        sts, data = self.getPage(url)
        if not sts: return
        
        data = json_loads(data)
        for entry in data['entries']:
            if 'mediasetprogram$subBrandId' in entry:
                desc = entry['description']
                subBrandId=entry['mediasetprogram$subBrandId']
                self.addDir(MergeDicts(cItem, {"title": desc, "subBrandId": subBrandId, "category": "program_item"}))

    
    def listProgramSubItems(self, cItem):

        brandId = cItem["brandId"]
        subBrandId = cItem["subBrandId"]
        url = self.FEED_SHOW_SUBITEM_URL.replace('%brandId%', brandId).replace('%subBrandId%', subBrandId)
    
        sts, data = self.getPage(url)
        if not sts: return
        
        data = json_loads(data)
        for item in data['entries']:
            desc = []
            desc.append(item['mediasetprogram$publishInfo']['last_published'].split('T', 1)[0]) 
            if 'description' in item['mediasetprogram$publishInfo']:
                desc.append(item['mediasetprogram$publishInfo']['description']) 
            desc.append(str(timedelta(seconds=int(item['mediasetprogram$duration']))))
            desc.append(_('%s views') % item['mediasetprogram$numberOfViews'] )
            
            desc = [' | '.join(desc)]
            desc.append(item.get('description', ''))
            icon = item['thumbnails']['image_keyframe_poster-292x165']['url']
            url = item['media'][0]['publicUrl']
            title = item ["title"]
            self.addVideo ({'category': 'program_video', 'title' : title , 'desc': '\n'.join(desc) , 'url' : url, 'icon' : icon})                
        
    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):
        printDBG('handleService start')
        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG( "handleService: ||| name[%s], category[%s] " % (name, category) )
        self.currList = []
        #self.initApi()

        #MAIN MENU
        if name == None:
            self.listMain(self.currItem)
        elif category == 'onair':
            self.listOnAir(self.currItem)
        elif category == 'ondemand':
            self.listAZFilters(self.currItem, 'list_az_item')
        elif category == 'list_az_item':
            self.listAZItems(self.currItem)
        elif category == 'list_az_item_next':
            self.listAZItems(self.currItem, self.currItem["page_number"])
        elif category == 'channels':
            self.listDates(self.currItem)
        elif category == 'date':
            self.listChannels(self.currItem)
        elif category == 'list_time':
            self.listEPG(self.currItem)
        elif category == 'program':
            self.listProgramItems(self.currItem)
        elif category == 'program_item':
            self.listProgramSubItems(self.currItem)
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, MediasetPlay(), True, [])

