# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.youtube import YoutubeIE
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, IsExecutable
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import decorateUrl
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist, getMPDLinksWithMeta
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib
from urlparse import urlparse, urlunparse, parse_qsl
from datetime import timedelta
from Components.config import config, ConfigSelection, ConfigYesNo
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.ytformat        = ConfigSelection(default = "mp4", choices = [("flv, mp4", "flv, mp4"),("flv", "flv"),("mp4", "mp4")]) 
config.plugins.iptvplayer.ytDefaultformat = ConfigSelection(default = "720", choices = [("0", _("the worst")), ("144", "144p"), ("240", "240p"), ("360", "360p"),("720", "720p"), ("1080", "1080p"), ("1440", "1440p"), ("2160", "2160p"), ("9999", _("the best"))])
config.plugins.iptvplayer.ytUseDF         = ConfigYesNo(default = True)
config.plugins.iptvplayer.ytAgeGate       = ConfigYesNo(default = False)
config.plugins.iptvplayer.ytVP9           = ConfigYesNo(default = False)
config.plugins.iptvplayer.ytShowDash      = ConfigSelection(default = "auto", choices = [("auto", _("Auto")),("true", _("Yes")),("false", _("No"))])
config.plugins.iptvplayer.ytSortBy        = ConfigSelection(default = "", choices = [("", _("Relevance")),("video_date_uploaded", _("Upload date")),("video_view_count", _("View count")),("video_avg_rating", _("Rating"))]) 


class YouTubeParser():
    
    def __init__(self):
        self.cm = common()
        self.HTTP_HEADER = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
                            'X-YouTube-Client-Name': '1', 
                            'X-YouTube-Client-Version': '2.20200207.03.01', 
                            'X-Requested-With':'XMLHttpRequest'
                            }
        self.http_params={'header':self.HTTP_HEADER, 'return_data': True}
        self.postdata = {}
        self.sessionToken = ""
        
        return

    @staticmethod
    def isDashAllowed():
        value = config.plugins.iptvplayer.ytShowDash.value
        printDBG("ALLOW DASH: >> %s" % value)
        if value == "true" and IsExecutable('ffmpeg'):
            return True
        elif value == "auto" and IsExecutable('ffmpeg') and IsExecutable(config.plugins.iptvplayer.exteplayer3path.value):
            return True
        else:
            return False

    @staticmethod
    def isVP9Allowed():
        value = config.plugins.iptvplayer.ytVP9.value
        printDBG("1. ALLOW VP9: >> %s" % value)
        value = YouTubeParser.isDashAllowed() and value
        printDBG("2. ALLOW VP9: >> %s" % value)
        return value

    @staticmethod
    def isAgeGateAllowed():
        value = config.plugins.iptvplayer.ytAgeGate.value
        printDBG("ALLOW Age-Gate bypass: >> %s" % value)
        return value

    def checkSessionToken(self, data):
        if not self.sessionToken:
            token = self.cm.ph.getSearchGroups(data, '''"XSRF_TOKEN":"([^"]+?)"''')[0]
            if token:
                printDBG("Update session token: %s" % token)
                self.sessionToken = token
                self.postdata = {"session_token": token}
                
    def getDirectLinks(self, url, formats = 'flv, mp4', dash=True, dashSepareteList = False, allowVP9 = None, allowAgeGate = None):
        printDBG('YouTubeParser.getDirectLinks')
        list = []
        try:
            if self.cm.isValidUrl(url) and '/channel/' in url and url.endswith('/live'):
                sts, data = self.cm.getPage(url)
                if sts:
                    videoId = self.cm.ph.getSearchGroups(data, '''<meta[^>]+?itemprop=['"]videoId['"][^>]+?content=['"]([^'^"]+?)['"]''')[0]
                    if videoId == '': videoId = self.cm.ph.getSearchGroups(data, '''['"]REDIRECT_TO_VIDEO['"]\s*\,\s*['"]([^'^"]+?)['"]''')[0]
                    if videoId != '': url = 'https://www.youtube.com/watch?v=' + videoId
            list = YoutubeIE()._real_extract(url, allowVP9 = allowVP9, allowAgeGate = allowAgeGate)
        except Exception:
            printExc()
            if dashSepareteList:
                return [], []
            else: return []
        
        reNum = re.compile('([0-9]+)')
        retHLSList = []
        retList = []
        dashList = []
        # filter dash
        dashAudioLists = []
        dashVideoLists = []
        if dash:
            # separete audio and video links
            for item in list:
                if 'mp4a' == item['ext']:
                    dashAudioLists.append(item)
                elif item['ext'] in ('mp4v', 'webmv'):
                    dashVideoLists.append(item)
                elif 'mpd' == item['ext']:
                    tmpList = getMPDLinksWithMeta(item['url'], checkExt=False)
                    printDBG(tmpList)
                    for idx in range(len(tmpList)):
                        tmpList[idx]['format'] = "%sx%s" % (tmpList[idx].get('height', 0), tmpList[idx].get('width', 0))
                        tmpList[idx]['ext']  = "mpd"
                        tmpList[idx]['dash'] = True
                    dashList.extend(tmpList)
            # sort by quality -> format
            def _key(x):
                if x['format'].startswith('>'):
                     int(x['format'][1:-1])
                else:
                     int(ph.search(x['format'], reNum)[0])
                    
            dashAudioLists = sorted(dashAudioLists, key=_key, reverse=True)
            dashVideoLists = sorted(dashVideoLists, key=_key, reverse=True)

        for item in list:
            printDBG(">>>>>>>>>>>>>>>>>>>>>")
            printDBG( item )
            printDBG("<<<<<<<<<<<<<<<<<<<<<")
            if -1 < formats.find( item['ext'] ):
                if 'yes' == item['m3u8']:
                    format = re.search('([0-9]+?)p$', item['format'])
                    if format != None:
                        item['format'] = format.group(1) + "x"
                        item['ext']  = item['ext'] + "_M3U8"
                        item['url']  = decorateUrl(item['url'], {"iptv_proto":"m3u8"})
                        retHLSList.append(item)
                else:
                    format = re.search('([0-9]+?x[0-9]+?$)', item['format'])
                    if format != None:
                        item['format'] = format.group(1)
                        item['url']  = decorateUrl(item['url'])
                        retList.append(item)
        
        if len(dashAudioLists):
            # use best audio
            for item in dashVideoLists:
                item = dict(item)
                item["url"] = decorateUrl("merge://audio_url|video_url", {'audio_url':dashAudioLists[0]['url'], 'video_url':item['url']})
                dashList.append(item)
        
        # try to get hls format with alternative method 
        if 0 == len(retList):
            try:
                video_id = YoutubeIE()._extract_id(url)
                url = 'http://www.youtube.com/watch?v=%s&gl=US&hl=en&has_verified=1' % video_id
                sts, data = self.cm.getPage(url, {'header':{'User-agent':'Mozilla/5.0 (iPad; U; CPU OS 3_2 like Mac OS X; en-us) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10'}})
                if sts:
                    data = data.replace('\\"', '"').replace('\\\\\\/', '/')
                    hlsUrl = self.cm.ph.getSearchGroups(data, '''"hlsvp"\s*:\s*"(https?://[^"]+?)"''')[0]
                    hlsUrl= json_loads('"%s"' % hlsUrl)
                    if self.cm.isValidUrl(hlsUrl):
                        hlsList = getDirectM3U8Playlist(hlsUrl)
                        if len(hlsList):
                            dashList = []
                            for item in hlsList:
                                item['format'] = "%sx%s" % (item.get('with', 0), item.get('heigth', 0))
                                item['ext']  = "m3u8"
                                item['m3u8'] = True
                                retList.append(item)
            except Exception:
                printExc()
            if 0 == len(retList):
                retList = retHLSList
            
            if dash:
                try:
                    sts, data = self.cm.getPage(url, {'header':{'User-agent':'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'}})
                    data = data.replace('\\"', '"').replace('\\\\\\/', '/').replace('\\/', '/')
                    dashUrl = self.cm.ph.getSearchGroups(data, '''"dashmpd"\s*:\s*"(https?://[^"]+?)"''')[0]
                    dashUrl = json_loads('"%s"' % dashUrl)
                    if '?' not in dashUrl: dashUrl += '?mpd_version=5'
                    else: dashUrl += '&mpd_version=5'
                    printDBG("DASH URL >> [%s]" % dashUrl)
                    if self.cm.isValidUrl(dashUrl):
                        dashList = getMPDLinksWithMeta(dashUrl, checkExt=False)
                        printDBG(dashList)
                        for idx in range(len(dashList)):
                            dashList[idx]['format'] = "%sx%s" % (dashList[idx].get('height', 0), dashList[idx].get('width', 0))
                            dashList[idx]['ext']  = "mpd"
                            dashList[idx]['dash'] = True
                except Exception:
                    printExc()
        
        for idx in range(len(retList)):
            if retList[idx].get('m3u8', False):
                retList[idx]['url'] = strwithmeta(retList[idx]['url'], {'iptv_m3u8_live_start_index':-30})
        
        if dashSepareteList:
            return retList, dashList
        else:
            retList.extend(dashList)
            return retList
    
    def updateQueryUrl(self, url, queryDict):
        urlParts = urlparse(url)
        query = dict(parse_qsl(urlParts[4]))
        query.update(queryDict)
        new_query = urllib.urlencode(query)
        new_url = urlunparse((urlParts[0],urlParts[1],urlParts[2],urlParts[3], new_query, urlParts[5]))
        return new_url

    def findKeys(self, node, kv):
        if isinstance(node, list):
            for i in node:
                for x in self.findKeys(i, kv):
                    yield x
        elif isinstance(node, dict):
            if kv in node:
                yield node[kv]
            for j in node.values():
                for x in self.findKeys(j, kv):
                    yield x

    def getThumbnailUrl(self, thumbJson, maxWidth = 1000, hq=False):
        
        url = ''
        try:
            thumbJson2 = []
            try:
                thumbJson2 = thumbJson["thumbnail"]["thumbnails"]
            except Exception:
                pass
            if len(thumbJson2) == 0:
                thumbJson2 = thumbJson["thumbnails"][0]['thumbnails']
                print(thumbJson2)
            thumbJson = thumbJson2
            width = 0
            i = 0
        
            while i < len(thumbJson):
                img = thumbJson[i]
                width = img['width']
                if width < maxWidth:
                    url = img['url']
                i = i + 1
        
            if hq or (not config.plugins.iptvplayer.allowedcoverformats.value) or config.plugins.iptvplayer.allowedcoverformats.value !='all':
                if 'hqdefault' in url:
                    url = url.replace('hqdefault','hq720')
                if '?' in url:
                    url = url.split('?')[0]
        except Exception:
            printExc()

        return url
        
    def getVideoData(self, videoJson):
        
        videoId = videoJson.get("videoId","")
        if videoId:
            url = 'http://www.youtube.com/watch?v=%s' % videoId
            try:
                title = videoJson['title']['runs'][0]['text']
            except:
                title = videoJson['title']['simpleText']
            
            badges = []
            bb = videoJson.get("badges",[])
            for b in bb:
                try:
                    bLabel = b["metadataBadgeRenderer"]["label"]
                    badges.append(bLabel.upper())
                except:
                    pass
            
            if badges:
                title = title + " [" + (' , '.join(badges)) + "]"
                
            icon = self.getThumbnailUrl(videoJson)
            
            desc = []
            try:
                duration = videoJson["lengthText"]["simpleText"]
                if duration:
                    desc.append(_("Duration: %s") % duration)
            except:
                pass
            
            try:
                views = videoJson["viewCountText"]["simpleText"]
                if views:
                    desc.append(views)
            except:
                pass
            
            try:
                time = videoJson["publishedTimeText"]["simpleText"]
                if time:
                    desc.append(time)
            except:
                time = ''

            try:
                owner = videoJson["ownerText"]["runs"][0]["text"]
            except:
                try:
                    owner = videoJson["longBylineText"]["runs"][0]["text"]
                except:
                    owner = ""
                
            if desc:
                desc = " | ".join(desc) + "\n" + owner
            else:
                desc = owner
                            
            try:
                desc = desc + "\n"+ videoJson["descriptionSnippet"]["runs"][0]["text"]
            except:
                pass
        
            return {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': icon , 'time': time, 'desc': desc}
        else:
            return {}
        
    def getChannelData(self, chJson):

        chId = chJson.get("channelId","")
        if chId:
            url = 'https://www.youtube.com/channel/%s' % chId
            title = chJson['title']['simpleText'] 

            icon = self.getThumbnailUrl(chJson)

            try:
                desc = chJson["descriptionSnippet"]["runs"][0]["text"]
            except:
                desc = ""
                
            return {'type': 'category', 'category': 'channel', 'title': title, 'url': url, 'icon': icon, 'time': '' ,'desc': desc}

        else:
            return {}
    
    def getPlaylistData(self, plJson):
        
        plId = plJson.get("playlistId","")
        if plId:
            url = "https://www.youtube.com/playlist?list=%s" % plId
            title = plJson['title']['simpleText'] 
            icon = self.getThumbnailUrl(plJson)

            videoCount = plJson['videoCount']
            desc = _("videos: %s") % videoCount
            try:
                by = plJson["longBylineText"]["runs"][0]["text"]
                desc = desc + "\n" + by
            except:
                pass
            return {'type': 'category', 'category': 'playlist', 'title': title, 'url': url, 'icon': icon, 'time': '' ,'desc': desc}
        else:
            return {}
    
    def getMenuItemData(self, itemJson):
        
        try:
            title = itemJson['title']['simpleText'] 
            icon = self.getThumbnailUrl(itemJson)

            try:
                feedId = itemJson["navigationEndpoint"]["browseEndpoint"]["params"]
                url = "https://www.youtube.com/feed/trending?bp=%s&pbj=1" % feedId
                cat = "feeds_" + title
            except:
                try:
                    url = "https://www.youtube.com" + itemJson["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]["url"]
                except:
                    printExc()
                    return {}

            if '/channel/' in url:
                return {'type': 'category', 'category': 'channel', 'title': title, 'url': url, 'icon': icon, 'time': '' ,'desc': ''}
            else:
                return {'type': 'feed', 'category': cat, 'title': title, 'url': url, 'icon': icon, 'time': '' ,'desc': ''}
                
        except:
            printExc()
            return {}
        
    def getFeedsList(self, url):
        printDBG('YouTubeParser.getFeedList')
        
        currList = []
        try:
            sts,data =  self.cm.getPage(url, self.http_params)
            if sts:
                self.checkSessionToken(data)

                data2 = self.cm.ph.getDataBeetwenMarkers(data,"window[\"ytInitialData\"] =", "};", False)[1]
                
                try:
                    response = json_loads(data2 + "}")
                
                    submenu = response['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['subMenu']
                    for item in submenu["channelListSubMenuRenderer"]["contents"]:
                        menuJson = item.get("channelListSubMenuAvatarRenderer", '') 
                        if menuJson:
                            params = self.getMenuItemData(menuJson)
                            
                            if params:
                                printDBG(str(params))
                                currList.append(params)    
                except:
                    printExc()

        except Exception:
            printExc()
            
        return currList

    
    def getVideoFromFeed(self, url):
        printDBG('YouTubeParser.getVideosFromFeed')
        
        currList = []
        try:
            sts,data =  self.cm.getPage(url, self.http_params)
            if sts:
                self.checkSessionToken(data)

                try:
                    response = json_loads(data)
                    
                    rr = {}
                    for r in response:
                        if r.get("response",""):
                            rr = r
                            break

                    if not rr:
                        return []
                    
                    r1 = rr["response"]["contents"]['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents']
                    r2 = r1[0]['itemSectionRenderer']['contents'][0]["shelfRenderer"]["content"]["expandedShelfContentsRenderer"]["items"]
                    
                    for item in r2:
                        chJson = item.get('channelRenderer', '')
                        videoJson = item.get('videoRenderer','')
                        plJson = item.get('playlistRenderer','')
                        
                        params = {}
                        if videoJson:
                            # it is a video
                            params = self.getVideoData(videoJson)
                        elif chJson:
                            # it is a channel
                            params = self.getChannelData(chJson)
                        elif plJson:
                            # it is a playlist
                            params = self.getPlaylistData(plJson)
                            
                        if params:
                            printDBG(str(params))
                            currList.append(params)

                except:
                    printExc()

        except Exception:
            printExc()

        return currList
    
        
    ########################################################
    # Tray List PARSER
    ########################################################
    def getVideosFromTraylist(self, url, category, page, cItem):
        printDBG('YouTubeParser.getVideosFromTraylist')
        return self.getVideosApiPlayList(url, category, page, cItem)

        currList = []
        try:
            sts,data =  self.cm.getPage(url, {'host': self.HOST})
            if sts:
                sts,data = CParsingHelper.getDataBeetwenMarkers(data, 'class="playlist-videos-container', '<div class="watch-sidebar-body">', False)
                data = data.split('class="yt-uix-scroller-scroll-unit')
                del data[0]
                return 
        except Exception:
            printExc()
            return []
            
        return currList
    # end getVideosFromPlaylist
       
    ########################################################
    # PLAYLIST PARSER
    ########################################################
    def getVideosFromPlaylist(self, url, category, page, cItem):
        printDBG('YouTubeParser.getVideosFromPlaylist')
        currList = []
        try:
            sts,data =  self.cm.getPage(url, self.http_params)
            if sts:
                self.checkSessionToken(data)

                data2 = self.cm.ph.getDataBeetwenMarkers(data,"window[\"ytInitialData\"] =", "};", False)[1]
                
                response = json_loads(data2 + "}")
                
                r1 = response['contents']['twoColumnBrowseResultsRenderer']['tabs'][0]['tabRenderer']['content']['sectionListRenderer']['contents']

                r2 = []
                for i in range(len(r1)):
                    r2.extend(r1[i]['itemSectionRenderer']['contents'])

                for r3 in r2:
                    pl = r3.get('playlistVideoListRenderer','')
                    if pl:
                        pl2 = pl.get('contents',[])
                        
                        for p in pl2:
                            videoJson = p.get('playlistVideoRenderer','')
                            if videoJson:
                                params = self.getVideoData(videoJson)
                                if params:
                                    try:
                                        params['title'] = "%s. - %s " % (videoJson["index"]["simpleText"], params['title'])
                                    except:
                                        pass
                                    printDBG(str(params))
                                    currList.append(params)
                    
        
        except Exception:
            printExc()
            
        return currList

    ########################################################
    # CHANNEL LIST PARSER
    ########################################################
        
    def getVideosFromChannelList(self, url, category, page, cItem):
        printDBG('YouTubeParser.getVideosFromChannelList page[%s]' % (page) )
        currList = []

        try:
            sts,data =  self.cm.getPage(url, self.http_params, self.postdata)
            
            if sts:
                if 'browse_ajax' in url:
                    # next pages 
                    response = json_loads(data)
                    
                    rr = {}
                    for r in response:
                        if r.get("response",""):
                            rr = r
                            break

                    if not rr:
                        return []
                        
                    r1 = rr["response"]["continuationContents"]["gridContinuation"]
                    r4 = r1.get("items",[])
                    nP = r1.get('continuations','')
                    
                else:
                    # first page of videos
                    self.checkSessionToken(data)
                    data2 = self.cm.ph.getDataBeetwenMarkers(data,"window[\"ytInitialData\"] =", "};", False)[1]

                    response = json_loads(data2 + "}")

                    r1 = response['contents']['twoColumnBrowseResultsRenderer']['tabs']
                    
                    r2 = {}
                    for tab in r1:
                        try:
                            if tab['tabRenderer']['content']:
                                r2 = tab['tabRenderer']['content']
                        except:
                            pass
                        
                        if r2:
                            break
                
                    r3 = r2['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
                    r4 = r3[0]['gridRenderer'].get('items','')
                    nP = r3[0]['gridRenderer'].get('continuations','')
                
                for r5 in r4:
                    videoJson = r5.get("gridVideoRenderer","") 
                    if videoJson:
                        params = self.getVideoData(videoJson)
                        if params:
                            printDBG(str(params))
                            currList.append(params)
                
                if nP:
                    nextPage = nP[0]
                    ctoken = nextPage["nextContinuationData"]["continuation"]
                    ctit = nextPage["nextContinuationData"]["clickTrackingParams"]
                    try:
                        label = nextPage["nextContinuationData"]["label"]["runs"][0]["text"]
                    except:
                        label = _("Next Page")
                    
                    urlNextPage = "https://www.youtube.com/browse_ajax?ctoken=%s&continuation=%s&itct=%s" % (ctoken, ctoken, ctit)
                    
                    params = {'type':'more', 'category': category , 'title': label, 'page': str(int(page) + 1), 'url': urlNextPage}
                    printDBG(str(params))
                    currList.append(params)
                
        except Exception:
            printExc()

        return currList

    ########################################################
    # SEARCH PARSER
    ########################################################
    #def getVideosFromSearch(self, pattern, page='1'):
    def getSearchResult(self, pattern, searchType, page, nextPageCategory, sortBy='', url = ''):
        printDBG('YouTubeParser.getSearchResult pattern[%s], searchType[%s], page[%s]' % (pattern, searchType, page))
        currList = []
              
        try:
            #url = 'http://www.youtube.com/results?search_query=%s&filters=%s&search_sort=%s&page=%s' % (pattern, searchType, sortBy, page) 

            nextPage = {}
            nP = {}
            nP_new = {}
            r2 = []
            
            if url:
                # next page search
                sts, data =  self.cm.getPage(url, self.http_params, self.postdata)
                
                if sts:
                    response = json_loads(data)
                    
            else:
                # new search
                # url = 'http://www.youtube.com/results?search_query=%s&filters=%s&search_sort=%s' % (pattern, searchType, sortBy) 
                url = 'https://www.youtube.com/results?search_query=' + pattern + '&sp='
                if searchType == 'video':
                    url += 'EgIQAQ%253D%253D'
                if searchType == 'channel':
                    url += 'EgIQAg%253D%253D'
                if searchType == 'playlist':
                    url += 'EgIQAw%253D%253D'
                if searchType == 'live':
                    url += 'EgJAAQ%253D%253D'

                sts,data =  self.cm.getPage(url, self.http_params)

                if sts:
                    self.checkSessionToken(data)
                    data2 = self.cm.ph.getDataBeetwenMarkers(data,"window[\"ytInitialData\"] =", "};", False)[1]
                    if len(data2) == 0:
                        data2 = self.cm.ph.getDataBeetwenMarkers(data,"var ytInitialData =", "};", False)[1]

                    response = json_loads(data2 + "}")

            if not sts:
                return []
                    
            #printDBG("--------------------")
            #printDBG(json_dumps(response))
            #printDBG("--------------------")

            
            # search videos
            r2 = list(self.findKeys(response, 'videoRenderer'))
            
            printDBG("---------------------")
            printDBG(json_dumps(r2))
            printDBG("---------------------")

            for item in r2:
                params = self.getVideoData(item)
                    
                if params:
                    printDBG(str(params))
                    currList.append(params)

            # search channels

            r2 = list(self.findKeys(response, 'channelRenderer'))
            
            printDBG("---------------------")
            printDBG(json_dumps(r2))
            printDBG("---------------------")

            for item in r2:
                params = self.getChannelData(item)
                    
                if params:
                    printDBG(str(params))
                    currList.append(params)
            
            #search playlists 

            r2 = list(self.findKeys(response, 'playlistRenderer'))
            
            printDBG("---------------------")
            printDBG(json_dumps(r2))
            printDBG("---------------------")

            for item in r2:
                params = self.getPlaylistData(item)
                    
                if params:
                    printDBG(str(params))
                    currList.append(params)

            nP = list(self.findKeys(response, "nextContinuationData"))
            nP_new = list(self.findKeys(response, "continuationEndpoint"))


            if nP:
                nextPage = nP[0]
                #printDBG("-------------------------------------------------")
                #printDBG(json_dumps(nextPage))
                #printDBG("-------------------------------------------------")

                ctoken = nextPage["continuation"]
                itct = nextPage["clickTrackingParams"]
                try:
                    label = nextPage["label"]["runs"][0]["text"]
                except:
                    label = _("Next Page")
                
                urlNextPage = self.updateQueryUrl(url, {'pbj':'1', 'ctoken': ctoken, 'continuation': ctoken, 'itct': itct}) 
                params = {'type':'more', 'category': "search_next_page", 'title': label, 'page': str(int(page) + 1), 'url': urlNextPage}
                printDBG(str(params))
                currList.append(params)

            elif nP_new:
                printDBG("-------------------------------------------------")
                printDBG(json_dumps(nP_new))
                printDBG("-------------------------------------------------")
                nextPage = nP_new[0]
                
                ctoken = nextPage["continuationCommand"]["token"]
                itct = nextPage["clickTrackingParams"]
                label = _("Next Page")
                
                urlNextPage = self.updateQueryUrl(url, {'pbj':'1', 'ctoken': ctoken, 'continuation': ctoken, 'itct': itct}) 
                params = {'type':'more', 'category': "search_next_page", 'title': label, 'page': str(int(page) + 1), 'url': urlNextPage}
                printDBG(str(params))
                currList.append(params)
         
        except Exception:
            printExc()

        return currList
    
    ########################################################
    # PLAYLIST API
    ########################################################
    def getVideosApiPlayList(self, url, category, page, cItem):
        printDBG('YouTubeParser.getVideosApiPlayList url[%s]' % url)
        playlistID = self.cm.ph.getSearchGroups(url + '&', 'list=([^&]+?)&')[0]
        baseUrl = 'https://www.youtube.com/list_ajax?style=json&action_get_list=1&list=%s' % playlistID

        currList = []
        if baseUrl != '':
            sts, data =  self.cm.getPage(baseUrl, {'host': self.HOST})
            try:
                data = json_loads(data)['video']
                for item in data:
                    url   = 'http://www.youtube.com/watch?v=' + item['encrypted_id']
                    title = item['title']
                    img   = item['thumbnail']
                    time  = item['length_seconds']
                    if '' != time: time = str( timedelta( seconds = int(time) ) )
                    if time.startswith("0:"): time = time[2:]
                    desc  = item['description']
                    params = {'type': 'video', 'category': 'video', 'title': title, 'url': url, 'icon': img, 'time': time, 'desc': desc}
                    currList.append(params)
            except Exception:
                printExc()
        return currList    

