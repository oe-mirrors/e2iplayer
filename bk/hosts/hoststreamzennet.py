# -*- coding: utf-8 -*-

#
#
# @Codermik release, based on @Samsamsam's E2iPlayer public.
# Released with kind permission of Samsamsam.
# All code developed by Samsamsam is the property of the Samsamsam and the E2iPlayer project,  
# all other work is ï¿½ E2iStream Team, aka Codermik.  TSiPlayer is ï¿½ Rgysoft, his group can be
# found here:  https://www.facebook.com/E2TSIPlayer/
#
# https://www.facebook.com/e2iStream/
#
#

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs import ph
###################################################

###################################################
# FOREIGN import
###################################################
import re
import urllib

def gettytul():
    return 'https://streamzen.net/'

class StreamZenNet(CBaseHostClass):

    def __init__(self):
        printDBG("..:: E2iStream ::..   __init__(self):")
        CBaseHostClass.__init__(self, {'history':'streamzen.net', 'cookie':'streamzen.net.cookie'})
        
        self.MAIN_URL = 'https://streamzen.net'
        self.MAIN_SEARCH_URL = '/?s='

        self.USER_AGENT = 'Mozilla/5.0'
        self.HEADER = {'User-Agent': self.USER_AGENT, 'DNT':'1', 'Accept': 'text/html', 'Accept-Encoding':'gzip, deflate', 'Referer':self.getMainUrl(), 'Origin':self.getMainUrl()}       
        self.DEFAULT_ICON_URL = 'https://streamzen.net/wp-content/uploads/2019/01/StreamZen.png'

        self.defaultParams = {'header':self.HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}     
        
        self.HOST_VER = '1.0 (22/08/2019)'
        self.HOST_AUTHOR = 'Codermik'

        self.MAIN_CAT_TAB =     [
                                    {'category':'movies',         'title': _('Films'),       'url':self.MAIN_URL + '/films/', 'desc': '\c00????00 Info: \c00??????Movies\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'tvseries',       'title': _('TV Series'),    'url':self.MAIN_URL + '/series/?tr_post_type=2', 'desc': '\c00????00 Info: \c00??????TV Series\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'byyears',       'title': _('Filter By Year'),    'url':self.MAIN_URL, 'desc': '\c00????00 Info: \c00??????Show all films or series by year.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'bygenres',       'title': _('Filter By Genre'),    'url':self.MAIN_URL, 'desc': '\c00????00 Info: \c00??????Show all films or series by genre.\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????Codermik\\n', 'icon':self.DEFAULT_ICON_URL},
                                    {'category':'search',   'title': _('Search'), 'desc': '\c00????00 Info: \c00??????Search\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????'+self.HOST_AUTHOR+'\\n', 'search_item':True},
                                    {'category':'search_history', 'desc': '\c00????00 Info: \c00??????Select from your search history\\n \c00????00Version: \c00??????'+self.HOST_VER+'\\n \c00????00Developer: \c00??????'+self.HOST_AUTHOR+'\\n', 'title': _('Search history')} 
                                ]
 
    def _getFullUrl(self, url):
        if 0 < len(url) and not url.startswith('http'):
            url = self.MAIN_URL + url
        return url

    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        def _getFullUrl(url):
            if self.cm.isValidUrl(url):
                return url
            else:
                return urljoin(baseUrl, url)             
        addParams['cloudflare_params'] = {'domain':self.up.getDomain(baseUrl), 'cookie_file':self.COOKIE_FILE, 'User-Agent':self.USER_AGENT, 'full_url_handle':_getFullUrl}
        return self.cm.getPageCFProtection(baseUrl, addParams, post_data)

    def cleanupShit(self, data):    # quite a fitting name  :)
        data = data.replace('&quot;','"')
        data = data.replace('&amp;', '&')
        data = data.replace('#038;','')
        return data

    def buildYears(self, cItem):
        year = 2019
        while year >= 2005:
            tmpyear = '%s' % year
            params = dict(cItem)
            url = 'https://streamzen.net/?s=trfilter&trfilter=1&years[]=%s' % year
            params.update({'category':'listyears', 'title':tmpyear, 'url':url})
            self.addDir(params)
            year-=1

    def buildGenre(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        block = self.cm.ph.getAllItemsBeetwenNodes(data, ('<ul class="sub-menu">', 'category'), '</ul>')[0]
        block = self.cm.ph.getAllItemsBeetwenNodes(block,'<li', ('</li>'))
        for genres in block:
            if '<a href="' in genres:
                genreUrl = self.cleanupShit(self.cm.ph.getAllItemsBeetwenNodes(genres,'<a href="', ('"'),False)[0])
                genreTitle = self.cleanupShit(self.cm.ph.getAllItemsBeetwenNodes(genres,'/">', ('</a>'),False)[0])
                desc = 'Show films or series under %s' % genreTitle
                params = dict(cItem) 
                params.update({'category':'listgenres', 'title':genreTitle, 'url':genreUrl, 'desc':desc})
                self.addDir(params)

    def listEpisodes(self, cItem):
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        block = self.cm.ph.getAllItemsBeetwenNodes(data,'<tr>', ('</tr>'))
        for episodes in block:
            if 'href="' in episodes: 
                episodeUrl = self.cm.ph.getSearchGroups(episodes, 'href="([^"]+?)"')[0] 
                episode = re.findall('([0-9]?x.[0-9]*)', episodeUrl)[0]
                title = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(episodes,episodeUrl+'">', ('</a>'),False)[0])
                title = '%s  \c00????00[%s]'%(title, episode)
                desc = '\c00????00 Title: \c00??????%s\\n \c00????00Season/Episode: \c00??????%s\\n' %(title, episode)
                params = dict(cItem) 
                params.update({'good_for_fav':True, 'title':title, 'url':episodeUrl, 'desc':desc})
                self.addVideo(params)

    def listItems(self, cItem):   
        page = cItem.get('page', 1)        
        sts, data = self.getPage(cItem['url'])
        if not sts: return
        self.setMainUrl(self.cm.meta['url']) 
        nextPage = ''
        tmpurl = self.cm.meta['url']
        try:
            if '<a class="next page-numbers"' in data:
                nextPage = self.cm.ph.getAllItemsBeetwenNodes(data,'<a class="next page-numbers" href="', '">Next',False)[0] 
            block = self.cm.ph.getAllItemsBeetwenNodes(data,'<section>', ('</section>'))[0]
            block = self.cm.ph.getAllItemsBeetwenNodes(block,'<li class="TPostMv">', ('</li>'))
            for items in block:
                if '/?=' in tmpurl: title = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(items,'<h3 class="Title">', '</h3>',False)[0])
                else: title = self.cleanHtmlStr(self.cm.ph.getAllItemsBeetwenNodes(items,'<div class="Title">', '</div>',False)[0])
                imgUrl = 'http://' + self.cm.ph.getAllItemsBeetwenNodes(items,'<img src="//', '"',False)[0]
                vidUrl = self.cm.ph.getAllItemsBeetwenNodes(items,'<a href="', ('"'),False)[0]
                if '<span class="Qlty">' in items: quality = '   \c00????00['+ self.cm.ph.getAllItemsBeetwenNodes(items,'<span class="Qlty">', '</span>',False)[0] + ']'
                else: quality = ''
                title += quality
                params = dict(cItem) 
                if '/films' in tmpurl: 
                    params.update({'good_for_fav':True, 'title':title, 'url':vidUrl, 'icon':imgUrl, 'desc':title})
                    self.addVideo(params)
                elif '/series' in tmpurl: 
                    params.update({'category':'listepisodes', 'title':title, 'url':vidUrl, 'icon':imgUrl, 'desc':title})
                    self.addDir(params)
                else:
                    # need to check if this url is a series or film since series requires a folder
                    if '<span class="TpTv BgA">TV</span>' in items:
                        params.update({'category':'listepisodes', 'title':title, 'url':vidUrl, 'icon':imgUrl, 'desc':title})
                        self.addDir(params)
                    else:
                        params.update({'category':'listepisodes', 'title':title, 'url':vidUrl, 'icon':imgUrl, 'desc':title})
                        self.addVideo(params)                
        except:
            printDBG('Failure to parse data >>>> oops!')

        if nextPage != '':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'title': _('Next Page'), 'page': cItem.get('page', 1) + 1, 'url': self._getFullUrl(nextPage)})
            self.addDir(params)
           
    def listSearchResult(self, cItem, searchPattern, searchType):   
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl(self.MAIN_SEARCH_URL) + urllib.quote(searchPattern) 
        cItem['category'] = 'list_items'
        self.listItems(cItem)
        
    def getVideoLinks(self, videoUrl):
        return  self.up.getVideoLinkExt(videoUrl)

    def getLinksForVideo(self, cItem):
        urlTab = []
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        self.setMainUrl(self.cm.meta['url'])  
        if '/episode' in cItem['url']:
            if '<div class="TPlayer">' in data:
                block = self.cm.ph.getAllItemsBeetwenNodes(data,'<div class="TPlayer">', ('<span class="lgtbx"'))[0]
                block = self.cleanupShit(block)
                block = self.cm.ph.getAllItemsBeetwenNodes(block,'<div class="TPlayerTb', ('</div>'))
                mirror = 1
                for mirrors in block:
                    if 'Opt' in mirrors: 
                        mirrorUrl = self.cm.ph.getSearchGroups(mirrors, '[\'"](http[^\'^"]+?)[\'"]')[0]
                        mirrorDesc = 'Mirror %d' % mirror
                        mirror+=1
                        sts, data = self.getPage(mirrorUrl)
                        block = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div class="Video"><iframe', 'https'), ('</iframe>'))[0]
                        videoUrl = self.cm.ph.getSearchGroups(block, '[\'"](https[^\'^"]+?)[\'"]')[0]
                        urlTab.append({'name': mirrorDesc, 'url': videoUrl, 'need_resolve': 1})
        else:
            # not a tv series episode, assume to be a movie.
            block = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div class="TPlayerTb Current"', 'trembed'), ('</iframe>'))[0]
            tmpUrl = self.cm.ph.getSearchGroups(block, '[\'"](https[^\'^"]+?)[\'"]')[0]
            tmpUrl = self.cleanupShit(tmpUrl)
            sts, data = self.getPage(tmpUrl)
            if not sts: return []
            block = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div class="Video"><iframe', 'https'), ('</iframe>'))[0]
            videoUrl = self.cm.ph.getSearchGroups(block, '[\'"](https[^\'^"]+?)[\'"]')[0]
            urlTab.append({'name': 'videofeed', 'url': videoUrl, 'need_resolve': 1})        
        return urlTab

    def handleService(self, index, refresh = 0, searchPattern = '', searchType = ''):        
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        name     = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        mode     = self.currItem.get("mode", '')           
        self.currList = []        
        if name == None:
            self.listsTab(self.MAIN_CAT_TAB, self.currItem)        
        elif category == 'movies': self.listItems(self.currItem)
        elif category == 'tvseries': self.listItems(self.currItem)
        elif category == 'listepisodes': self.listEpisodes(self.currItem)
        elif category == 'byyears': self.buildYears(self.currItem)
        elif category == 'bygenres': self.buildGenre(self.currItem)
        elif category == 'listyears' or category == 'listgenres': self.listItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item':False, 'name':'category'}) 
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name':'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        
        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):
    def __init__(self):
        CHostBase.__init__(self, StreamZenNet(), True, favouriteTypes=[]) 

