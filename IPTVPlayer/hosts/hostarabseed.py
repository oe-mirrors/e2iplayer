# -*- coding: utf-8 -*-
# typical import for a standard host
###################################################
# LOCAL import
###################################################
# localization library
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
# host main class
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
# tools - write on log, write exception infos and merge dicts
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts
# add metadata to url
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
# library for json (instead of standard json.loads and json.dumps)
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
# library for parsing html
from Plugins.Extensions.IPTVPlayer.libs import ph
# read informations in m3u8
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urljoin, urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote_plus, urllib_unquote
###################################################
# FOREIGN import
###################################################
import re
import datetime
import base64
###################################################


def gettytul():
    return 'https://a.asd.homes/'  # main url of host


class ArabSeed(CBaseHostClass):

    def __init__(self):
        # init global variables for this class

        CBaseHostClass.__init__(self, {'history': 'arabseed', 'cookie': 'arabseed.cookie'})  # names for history and cookie files in cache

        # vars default values

        # various urls
        self.MAIN_URL = 'https://a.asd.homes/'
        self.SEARCH_URL = 'https://a.asd.homes/search'

        # url for default icon
        self.DEFAULT_ICON_URL = "https://raw.githubusercontent.com/popking159/softcam/refs/heads/master/arabseedlogo.png"

        # default header and http params
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}

    def getPage(self, url, addParams={}, post_data=None):
        # default use: call function getPage in pCommon lib
        # if needed, last line can become self.cm.getPageCF(url, addParams, post_data)
        # if site is protected with cloudflare
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(url, addParams, post_data)

    def getLinksForVideo(self, cItem):
        printDBG("ArabSeed.getLinksForVideo [%s]" % cItem)
        linksTab = []
        sts, data = self.getPage(cItem['url'], self.defaultParams)
        if not sts:
            return []

        # Try to find embedded iframes or direct <source> links, as fallback
        # (You can keep or remove this section depending on the site)
        iframes = self.cm.ph.getAllItemsBeetwenMarkers(data, '<iframe', '>')
        for iframe in iframes:
            url = self.cm.ph.getSearchGroups(iframe, 'src="([^"]+)"')[0]
            if url and ('youtube' in url or 'vimeo' in url or 'embed' in url):
                linksTab.append({'name': self.up.getHostName(url).capitalize(),
                                 'url': strwithmeta(url, {'Referer': self.MAIN_URL}),
                                 'need_resolve': 1})

        video_links = self.cm.ph.getAllItemsBeetwenMarkers(data, 'source', '>')
        for link in video_links:
            url = self.cm.ph.getSearchGroups(link, 'src="([^"]+)"')[0]
            if url:
                linksTab.append({'name': self.up.getHostName(url).capitalize(),
                                 'url': strwithmeta(url, {'Referer': self.MAIN_URL}),
                                 'need_resolve': 1})

        # **If no links found by parsing the page, fallback to urlparser**
        if not linksTab:
            printDBG("ArabSeed.getLinksForVideo: no direct links found, calling getVideoLinks()")
            # Delegate to getVideoLinks for parser-based resolution
            resolved = self.getVideoLinks(cItem['url'])
            printDBG("ArabSeed.getLinksForVideo: resolved via parser: %s" % str(resolved))
            # The parser returns list of dicts or a list of playable links
            # We should ensure they have consistent keys
            for entry in resolved:
                # If entry is a dict already
                if isinstance(entry, dict):
                    linksTab.append(entry)
                else:
                    # If it's just a URL or something else
                    linksTab.append({'url': entry, 'name': self.up.getHostName(cItem['url'])})

        return linksTab

    def getVideoLinks(self, url):
        printDBG("ArabSeed.getVideoLinks [%s]" % url)
        urlTab = []
        if self.cm.isValidUrl(url):
            return self.up.getVideoLinkExt(url)
        return urlTab

    def listMainMenu(self, cItem):
        # items of main menu
        printDBG('ArabSeed.listMainMenu')
        
        # Define main categories statically like FilmPalast does
        self.MAIN_CAT_TAB = [
            {'category': 'mainpage', 'title': _('الرئيسية'), 'url': self.getFullUrl('/main0/')},
            {'category': 'movies_folder', 'title': _('الافلام')},
            {'category': 'series_folder', 'title': _('المسلسلات')},
            {'category': 'ramadan_folder', 'title': _('رمضان')},
            {'category': 'anime_folder', 'title': _('انمي')},
            {'category': 'other_folder', 'title': _('اخري')},
            {'category': 'search', 'title': _('Search'), 'search_item': True},
            {'category': 'search_history', 'title': _('Search history')}
        ]
        
        # Define subcategories for each folder
        self.MOVIES_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام Netfilx'), 'url': self.getFullUrl('/category/netfilx/%d8%a7%d9%81%d9%84%d8%a7%d9%85-netfilx/')},
            {'category': 'list_items', 'title': _('افلام اجنبي'), 'url': self.getFullUrl('/category/foreign-movies-6/')},
            {'category': 'list_items', 'title': _('افلام اسيوية'), 'url': self.getFullUrl('/category/asian-movies/')},
            {'category': 'list_items', 'title': _('افلام تركية'), 'url': self.getFullUrl('/category/turkish-movies/')},
            {'category': 'list_items', 'title': _('افلام عربي'), 'url': self.getFullUrl('/category/arabic-movies-6/')},
            {'category': 'list_items', 'title': _('افلام كلاسيكيه'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%83%d9%84%d8%a7%d8%b3%d9%8a%d9%83%d9%8a%d9%87/')},
            {'category': 'list_items', 'title': _('افلام مدبلجة'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'list_items', 'title': _('افلام هندى'), 'url': self.getFullUrl('/category/indian-movies/')}
        ]
        
        self.SERIES_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات Netfilx'), 'url': self.getFullUrl('/category/netfilx/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-netfilz/')},
            {'category': 'series', 'title': _('مسلسلات اجنبي'), 'url': self.getFullUrl('/category/foreign-series-2/')},
            {'category': 'series', 'title': _('مسلسلات تركيه'), 'url': self.getFullUrl('/category/turkish-series-2/')},
            {'category': 'series', 'title': _('مسلسلات عربي'), 'url': self.getFullUrl('/category/arabic-series-3/')},
            {'category': 'series', 'title': _('مسلسلات كرتون'), 'url': self.getFullUrl('/category/cartoon-series/')},
            {'category': 'series', 'title': _('مسلسلات كوريه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%83%d9%88%d8%b1%d9%8a%d9%87/')},
            {'category': 'series', 'title': _('مسلسلات مدبلجة'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%af%d8%a8%d9%84%d8%ac%d8%a9/')},
            {'category': 'series', 'title': _('مسلسلات مصريه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%85%d8%b5%d8%b1%d9%8a%d9%87/')},
            {'category': 'series', 'title': _('مسلسلات هندية'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d9%87%d9%86%d8%af%d9%8a%d8%a9/')}
        ]
        
        self.RAMADAN_CAT_TAB = [
            {'category': 'series', 'title': _('مسلسلات رمضان 2025'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2025/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2024'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2024/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2023'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/ramadan-series-2023/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2022'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2022/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2021'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2021/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2020'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2020-hd/')},
            {'category': 'series', 'title': _('مسلسلات رمضان 2019'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86/%d9%85%d8%b3%d9%84%d8%b3%d9%84%d8%a7%d8%aa-%d8%b1%d9%85%d8%b6%d8%a7%d9%86-2019/')}
        ]
        
        self.ANIME_CAT_TAB = [
            {'category': 'list_items', 'title': _('افلام انيميشن'), 'url': self.getFullUrl('/category/%d8%a7%d9%81%d9%84%d8%a7%d9%85-%d8%a7%d9%86%d9%8a%d9%85%d9%8a%d8%b4%d9%86/')},
            {'category': 'series', 'title': _('مسلسلات كرتون'), 'url': self.getFullUrl('/category/cartoon-series/')}
        ]
        
        self.OTHER_CAT_TAB = [
            {'category': 'list_items', 'title': _('اغاني عربي'), 'url': self.getFullUrl('/category/%d8%a7%d8%ba%d8%a7%d9%86%d9%8a-%d8%b9%d8%b1%d8%a8%d9%8a/')},
            {'category': 'list_items', 'title': _('مصارعه'), 'url': self.getFullUrl('/category/wwe-shows/')},
            {'category': 'list_items', 'title': _('برامج تلفزيونية'), 'url': self.getFullUrl('/category/%d8%a8%d8%b1%d8%a7%d9%85%d8%ac-%d8%aa%d9%84%d9%81%d8%b2%d9%8a%d9%88%d9%86%d9%8a%d8%a9/')},
            {'category': 'list_items', 'title': _('مسرحيات عربيه'), 'url': self.getFullUrl('/category/%d9%85%d8%b3%d8%b1%d8%ad%d9%8a%d8%a7%d8%aa-%d8%b9%d8%b1%d8%a8%d9%8a/')}
        ]
        
        # Display main categories
        self.listsTab(self.MAIN_CAT_TAB, cItem)

    def listMoviesFolder(self, cItem):
        printDBG('ArabSeed.listMoviesFolder')
        self.listsTab(self.MOVIES_CAT_TAB, cItem)

    def listSeriesFolder(self, cItem):
        printDBG('ArabSeed.listSeriesFolder')
        self.listsTab(self.SERIES_CAT_TAB, cItem)

    def listRamadanFolder(self, cItem):
        printDBG('ArabSeed.listRamadanFolder')
        self.listsTab(self.RAMADAN_CAT_TAB, cItem)

    def listAnimeFolder(self, cItem):
        printDBG('ArabSeed.listAnimeFolder')
        self.listsTab(self.ANIME_CAT_TAB, cItem)

    def listOtherFolder(self, cItem):
        printDBG('ArabSeed.listOtherFolder')
        self.listsTab(self.OTHER_CAT_TAB, cItem)

    def listMainItems(self, cItem, nextCategory=''):
        printDBG("ArabSeed.listMainItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        if sts:
            # Save a sample of the data for debugging
            sample = data[:2000] if len(data) > 2000 else data
            printDBG("Page sample: %s" % sample)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="menu__bar hide__md">' , '</div>', False)[1]
        printDBG('|||||||||||||||||||||||||||||||||||||||||||tmp|||||||||||||||')
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')
        #printDBG(data_items)

        for m in data_items:
                   title = self.cleanHtmlStr(m)
                   pureurl = self.cm.ph.getSearchGroups(m, "href=['\"]([^'^\"]+?)['\"]")[0]
                   baseurl, filenameurl = pureurl.rsplit('/', 1)
                   fixedfilenameurl = urllib_quote_plus(filenameurl)
                   url = baseurl + "/" + fixedfilenameurl
                   pureicon = self.cm.ph.getSearchGroups(m, "src=['\"]([^'^\"]+?)['\"]")[0]
                   baseicon, filenameicon = pureicon.rsplit('/', 1)
                   fixedfilenameicon = urllib_quote_plus(filenameicon)
                   icon = baseicon + "/" + fixedfilenameicon
                   params = {'category':'explore_item','title':title, 'icon': icon , 'url': url}
                   printDBG(str(params))
                   self.addDir(params)

    def listItems(self, cItem):
        printDBG("ArabSeed.listItems [%s]" % cItem)
        sts, data = self.getPage(cItem['url'])
        #printDBG('listitems data print:')
        #printDBG(data)
        if not sts:
            return
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="movie__blocks" id="ajax__area">' , '<div class="paginate">', False)[1]
        printDBG('listitems tmp print:')
        printDBG(tmp)
        data_items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li class="box__xs__2 box__sm__2 box__md__3 box__lg__4 box__xl__5"> <div class="item__contents ">', '</li></ul></div></div></div></li>')
        #printDBG('listitems data_items print:')
        #printDBG(data_items)

        for m in data_items:
                   title = self.cm.ph.getSearchGroups(m, r'title=[\'"]([^\'"]+)[\'"]')[0]
                   pureurl = self.cm.ph.getSearchGroups(m, r'href=[\'"]([^\'"]+)[\'"]')[0]
                   baseurl, filenameurl = pureurl.rsplit('/', 1)
                   fixedfilenameurl = urllib_quote_plus(filenameurl)
                   url = baseurl + "/" + fixedfilenameurl + "watch/"
                   pureicon = self.cm.ph.getSearchGroups(m, r'data-src=[\'"]([^\'"]+)[\'"]')[0]
                   baseicon, filenameicon = pureicon.rsplit('/', 1)
                   fixedfilenameicon = urllib_quote_plus(filenameicon)
                   icon = baseicon + "/" + fixedfilenameicon
                   params = {'category':'explore_item','title':title, 'icon': icon , 'url': url}
                   printDBG(str(params))
                   self.addDir(params)

    def listSeriesItems(self, cItem):
        printDBG("ArabSeed.listSeriesItems ----------")

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return

        seriesDict = {}  # Use to avoid duplicates

        blocks = self.cm.ph.getAllItemsBeetwenMarkers(data, '<li class="box__xs__2', '</li>')
        for block in blocks:
            pureurl = self.getFullUrl(self.cm.ph.getSearchGroups(block, 'href="([^"]+?)"')[0])
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            fixedfilenameurl = urllib_quote_plus(filenameurl)
            baseurl, filenameurl = pureurl.rsplit('/', 1)
            url = baseurl + "/" + fixedfilenameurl
            if not url:
                continue

            pureicon = self.cm.ph.getSearchGroups(block, 'data-src="([^"]+?)"')[0]
            baseicon, filenameicon = pureicon.rsplit('/', 1)
            fixedfilenameicon = urllib_quote_plus(filenameicon)
            icon = baseicon + "/" + fixedfilenameicon
            desc = self.cm.ph.getSearchGroups(block, '<p[^>]*?>([^<]+?)</p>')[0]
            fullTitle = self.cm.ph.getSearchGroups(block, '<h3[^>]*?>([^<]+?)</h3>')[0].strip()

            # Remove episode numbers like "الحلقة 30" using regex
            title = re.sub(r'الحلقة\s*\d+', '', fullTitle, flags=re.UNICODE).strip()

            # Avoid duplicates
            if title in seriesDict:
                continue
            seriesDict[title] = True

            params = dict(cItem)
            params.update({
                'title': title,
                'url': url,
                'icon': icon,
                'desc': desc,
                'category': 'explore_episodes',  # You’ll handle this in handleService()
            })

            self.addDir(params)


    def listCats(self, cItem, nextCategory, marker_start, marker_end):
        printDBG('ArabSeed.listCats')
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return
            
        data = self.cm.ph.getDataBeetwenMarkers(data, marker_start, marker_end, False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, '<a', '</a>')
        
        for item in items:
            url = self.getFullUrl(self.cm.ph.getSearchGroups(item, 'href="([^"]+)"')[0])
            title = self.cleanHtmlStr(item)
            if url and title:
                params = dict(cItem)
                params.update({'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url})
                self.addDir(params)

    def listSeriesABC(self, cItem, nextCategory):
        printDBG('ArabSeed.listSeriesABC')
        # Add alphabet letters for series
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': nextCategory, 'title': letter, 'url': self.getFullUrl('/serien/view?l=' + letter)})
            self.addDir(params)

    def listSeriesByLetter(self, cItem, nextCategory):
        printDBG('ArabSeed.listSeriesByLetter')
        self.listItems(cItem, nextCategory)


    def exploreItems(self, cItem):
        printDBG('ArabSeed.exploreItems')
        url = cItem['url']
        sts, data = self.getPage(url)
        if not sts:
            return

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div class="servers__list', '</ul>', False)[1]
        items = self.cm.ph.getAllItemsBeetwenMarkers(tmp, '<li', '</li>')

        for item in items:
            # Extract the label (e.g. "سيرفر 1") and quality (data-qu="480")
            label = self.cm.ph.getSearchGroups(item, '<span>([^<]+)</span>')[0].strip()
            quality = self.cm.ph.getSearchGroups(item, 'data-qu="([^"]+)"')[0]
            link = self.cm.ph.getSearchGroups(item, 'data-link="([^"]+?)"')[0]

            if not link:
                continue

            # Decode if it's a base64-encoded redirect link (ArabSeed server)
            if '/asd.php?url=' in link:
                try:
                    b64 = self.cm.ph.getSearchGroups(link, 'url=([^&"]+)')[0]
                    decoded_link = self.safe_b64decode(b64)
                    if 'gamehub.cam' in decoded_link:  # skip broken ones
                        continue
                    link = 'https://a.asd.homes/asd.php?url=' + b64  # use working ArabSeed server proxy
                    label = 'سيرفر عرب سيد'
                except Exception as e:
                    printDBG('Base64 decode failed: %s' % str(e))
                    continue

            # Add quality to title
            if quality:
                label = '%s [%sp]' % (label, quality)

            printDBG("Found server link: %s" % link)

            params = MergeDicts(cItem, {
                'title': label,
                'url': link,
                'type': 'video',
                'category': 'video',
                'need_resolve': 1
            })
            self.addVideo(params)


    def exploreSeriesItems(self, cItem):
        printDBG('ArabSeed.exploreSeriesItems')
        url = cItem['url']
        sts, data = self.getPage(url)

        if not sts:
            return

        # Extract the block that contains episodes
        episodes_block = self.cm.ph.getDataBeetwenMarkers(data,
            '<ul class="episodes__list', '</ul>', False)[1]

        printDBG('Episodes block:')
        printDBG(episodes_block)

        episodes = self.cm.ph.getAllItemsBeetwenMarkers(episodes_block, '<li', '</li>')
        episodes.reverse()

        for item in episodes:
            episode_url = self.cm.ph.getSearchGroups(item, 'href="([^"]+?)"')[0]
            if not episode_url:
                continue
            episode_url = self.getFullUrl(episode_url).rstrip('/') + '/watch'

            # Extract episode number only, and prepend "الحلقة"
            episode_number = self.cm.ph.getSearchGroups(item, '<div class="epi__num">.*?<b>([^<]+)</b>')[0]
            if episode_number:
                title = 'الحلقة %s' % episode_number.strip()
            else:
                title = self.cleanHtmlStr(item)  # or fallback to generic title

            params = dict(cItem)
            params.update({
                'title': title,
                'url': episode_url,
                'icon': cItem.get('icon', ''),
                'desc': cItem.get('desc', ''),
                'category': 'explore_item',
            })

            printDBG('Adding episode: %s' % str(params))
            self.addDir(params)


    def safe_b64decode(self, data):
        """Base64 decode with automatic padding fix."""
        data += '=' * (-len(data) % 4)
        return base64.b64decode(data).decode('utf-8')

    def listEpisodes(self, cItem):
        printDBG('ArabSeed.listEpisodes')
        # For now, just redirect to video
        cItem['category'] = 'video'
        self.addDir(cItem)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("ArabSeed.listSearchResult cItem[%s], searchPattern[%s] searchType[%s]" % (cItem, searchPattern, searchType))
        cItem = dict(cItem)
        cItem['url'] = self.getFullUrl('/search?q=') + urllib_quote(searchPattern)
        self.listItems(cItem, 'explore_item')

    def getFavouriteData(self, cItem):
        printDBG('ArabSeed.getFavouriteData')
        return json_dumps(cItem)

    def getLinksForFavourite(self, fav_data):
        printDBG('ArabSeed.getLinksForFavourite')
        links = []
        try:
            cItem = json_loads(fav_data)
            links = self.getLinksForVideo(cItem)
        except Exception:
            printExc()
        return links

    def setInitListFromFavouriteItem(self, fav_data):
        printDBG('ArabSeed.setInitListFromFavouriteItem')
        try:
            cItem = json_loads(fav_data)
        except Exception:
            cItem = {}
            printExc()
        return cItem

    def listSubMenuFolder(self, cItem):
        """List submenu items from a folder"""
        printDBG('ArabSeed.listSubMenuFolder')
        
        sub_items = cItem.get('sub_items', [])
        main_category = cItem.get('main_category', 'list_items')
        
        for sub_item in sub_items:
            # Extract title from submenu item
            title = self.cm.ph.getDataBeetwenMarkers(sub_item, '<span>', '</span>', False)[1]
            if not title:
                title = self.cleanHtmlStr(sub_item)
            
            # Extract URL
            url = self.cm.ph.getSearchGroups(sub_item, 'href="([^"]+)"')[0]
            if not url:
                continue
                
            # Make sure URL is absolute
            if not url.startswith('http'):
                url = self.getFullUrl(url)
            
            # Use the main category type for subitems, or determine from title
            category_type = main_category
            if any(word in title for word in ['مسلسلات', 'رمضان', 'انمي', 'كرتون']):
                category_type = 'series'
            elif any(word in title for word in ['افلام']):
                category_type = 'list_items'
            
            params = {
                'category': category_type,
                'title': title,
                'url': url
            }
            printDBG("Adding submenu item: %s" % str(params))
            self.addDir(params)

    def searchItems(self):
        searchItem = [
            {'category': 'search', 'title': _('Search'), 'search_item': True},
            {'category': 'search_history', 'title': _('Search history')}
        ]
        return searchItem

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('ArabSeed.handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: >> name[%s], category[%s] " % (name, category))
        self.currList = []

        # MAIN MENU
        if name == None:
            self.listMainMenu({'name': 'category'})
        elif category == 'mainpage':
            self.listMainItems(self.currItem)
        elif category == 'list_items':
            self.listItems(self.currItem)
        elif category == 'series':
            self.listSeriesItems(self.currItem)
        # FOLDERS
        elif category == 'movies_folder':
            self.listMoviesFolder(self.currItem)
        elif category == 'series_folder':
            self.listSeriesFolder(self.currItem)
        elif category == 'ramadan_folder':
            self.listRamadanFolder(self.currItem)
        elif category == 'anime_folder':
            self.listAnimeFolder(self.currItem)
        elif category == 'other_folder':
            self.listOtherFolder(self.currItem)
        elif category == 'explore_item':
            self.exploreItems(self.currItem)
        elif category == 'explore_episodes':
            self.exploreSeriesItems(self.currItem)
        # SEARCH
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        # HISTORY SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)

class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, ArabSeed(), True, [])

    def withArticleContent(self, cItem):
        if 'video' == cItem.get('type', '') or 'explore_item' == cItem.get('category', ''):
            return True
        return False