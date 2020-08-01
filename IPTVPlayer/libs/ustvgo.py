# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, GetCookieDir, GetJSScriptFile
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################

import re
import base64
###################################################

class UstvgoApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL = 'https://ustvgo.tv/'
        self.DEFAULT_ICON_URL = 'https://image.winudf.com/v2/image1/dXN0dmdvLmdvdHYudXNfaWNvbl8xNTcyNDU4Nzc3XzAzMg/icon.png?w=170&fakeurl=1'
        
        self.HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader(browser='chrome'), {'Referer':self.getMainUrl()})
        self.http_params = {'header':self.HTTP_HEADER, 'use_cookie': True, 'save_cookie': True, 'load_cookie':True, 'cookiefile': GetCookieDir("ustvgo.cookie")}

        
    def getChannelsList(self, cItem):
        printDBG("UstvgoApi.getChannelsList")

        channelsTab=[]
        sts, data = self.cm.getPage(self.MAIN_URL,self.http_params)
        if not sts: 
            return []

        chlist = self.cm.ph.getDataBeetwenNodes(data, ('<ol>'), ('</ol>'), False)[1]
        channels = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li>','</li>')
            
        for c in channels:
            title = title = ph.clean_html(c)
            url   = self.cm.ph.getSearchGroups(c, '''href=['"]([^'^"]+?)['"]''')[0]
            
            params = MergeDicts(cItem, {'type':'video', 'title':title, 'url': url})
            printDBG(str(params))
            channelsTab.append(params)
            
        return channelsTab
        
    def getVideoLink(self, cItem):
        printDBG("UstvgoApi.getVideoLink %s" % cItem)
        urlsTab = []
            
        url = cItem.get('url','')
        if url:
            
            sts, data = self.cm.getPage(url, self.http_params)
            if sts: 
                #<div class="iframe-container">
                #    <iframe src='/player.php?stream=ABC' scrolling="no" allowfullscreen></iframe>
                #</div>
                
                tmp = self.cm.ph.getDataBeetwenNodes(data, ('<div','>','iframe'), ('</div>'), False)[1]
                iframe_url = self.getFullUrl(self.cm.ph.getSearchGroups(tmp, '''src=['"]([^'^"]+?)['"]''')[0])
                printDBG("UstvgoApi - iframe url: %s" % iframe_url)
                
                params = MergeDicts(self.http_params, {'Referer': url})
                sts, data = self.cm.getPage(iframe_url, params)
                
                if sts: 
                    printDBG("------------- iframe player html code ----------")
                    printDBG(data)

                    #search for javascript
                    scripts = self.cm.ph.getAllItemsBeetwenMarkers(data, ('<script','>'),'</script>')
                    
                    for s in scripts:
                        base64Url = re.findall("filePath\s?=\s?atob\('([^']+?)'", s)
                        base64Url.extend(re.findall("hlsURL\s?=\s?atob\('([^']+?)'", s))
                        
                        if base64Url:
                            video_url = base64.b64decode(base64Url[0])
                            if self.cm.isValidUrl(video_url):
                                video_url = self.up.decorateUrl(video_url, {'iptv_proto':'m3u8', 'iptv_livestream':True, 'Referer':'https://ustvgo.tv',  'User-Agent': self.HTTP_HEADER['User-Agent']})
                                urlsTab.append({'name': 'link', 'url': video_url })
                                urlsTab.extend(getDirectM3U8Playlist(video_url, checkExt=False, checkContent=True))
                        
                        if 'Clappr.Player' in s:
                            # s is the right javascript code
                            #search span tags, name of function and useful code
                            spans = re.findall("<span style='display:none' id=([a-zA-Z]+)>(.*?)</span>",data)
                            fName = re.findall("source:\s?([a-zA-Z]+)\(\)",s)
                            code = re.findall("(function [a-zA-Z]{19,}\(.*?)var player",s, re.S)
                            if len(code)>0 and len(fName)>0:
                                code = code[0]
                                code = re.sub("\\blet\\b", "var", code)
                                fName = fName[0]
                                
                                code2 = ""
                                for num_span in range(len(spans)):
                                    code2 = code2 + "\ndocument.children.push ( new element('', '%s', 'div')); document.children[%d].innerHTML = \"%s\";" % (spans[num_span][0], num_span, spans[num_span][1])
                                
                                js_code = "%s\n%s\n\nconsole.log(%s()); " % (code2, code,fName)

                                printDBG("--------------- javascript code to get url ---------------------")
                                printDBG(js_code)

                                js_params = [{'path' : GetJSScriptFile('ustvgo_max.byte')}]
                                js_params.append({'code': js_code})
                                ret = js_execute_ext( js_params )
                                if ret['sts'] and 0 == ret['code']:
                                    video_url = ret['data'].replace("\n","")
                                    printDBG("Url found: %s" % video_url)
                                    video_url = self.up.decorateUrl(video_url, {'iptv_proto':'m3u8', 'iptv_livestream':True, 'Referer':'https://ustvgo.tv',  'User-Agent': self.HTTP_HEADER['User-Agent']})
                                    urlsTab.append({'name': 'link', 'url': video_url })
                                    urlsTab.extend(getDirectM3U8Playlist(video_url, checkExt=False, checkContent=True))

                                else:
                                    printDBG("Duktape wrong execution... check code")

        return urlsTab
