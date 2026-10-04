# -*- coding: utf-8 -*-
# Last Modified: 03.10.2026 - revival for the current christusvincit-tv.pl (PHP-Fusion pages)
#   The own Kaltura media servers (mediaserwer3/mediaserver4) are gone; the recordings are
#   Vimeo showcases / Vimeo live events and a YouTube live embed. Main page sections + side
#   panels (favourites find a section again by its caption), article categories (cat_id 1-3) and
#   search with First page / Jump / Next page over the rowstart offset, article/page folders (iframes +
#   linked sub pages), Vimeo showcase/event lists (dataForPlayer, local paging), Vimeo HLS
#   (signed config from the embed page, alt-audio merge), live row, search, watched flag,
#   downloaded flag, sidecar, name normalisation, site-based INFO, favourites.
import json
import re

from Plugins.Extensions.IPTVPlayer.components.ihost import CBaseHostClass, CHostBase
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget, stripPagerKeys
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin


def GetConfigList():
    return []


def gettytul():
    return 'https://christusvincit-tv.pl/'


# viewpage.php pages linked from the main page that really carry recordings (the other ~55 are
# galleries, song texts, contact lists, ...); viewpages linked from inside an article are always listed
VIDEO_PAGES = ('2', '6', '7', '10', '15')
PER_PAGE = 40
# list state of a folder that must not reach the rows listed in it (besides the pager fields, see stripPagerKeys)
CHILD_DROP_KEYS = ('per_page', 'section_idx', 'section_title', 'section_nth', 'list_type')

# proper names of the site's section captions and of the image-only links (the image file name is the
# only label the site gives them); also used to repair captions where the site lost the Polish letters ("?")
SECTION_TITLES = ('Transmisja na żywo', 'Z ostatniej chwili', 'Informacje bieżące', 'Pozostałe retransmisje',
                  'Retransmisje', 'Kategorie', 'Für die Deutschen', 'Linki')

TITLES_MAP = {
    'wspolodkupicielka': 'Współodkupicielka i Pośredniczka Wszelkich Łask',
    'rekolkap': 'Rekolekcje kapłańskie',
    'medalionbogaojca': 'Medalion Boga Ojca',
    'mojkosciele': 'Mój Kościele co oni Tobie uczynili',
    'redemptorismater': 'Redemptoris Mater',
    'luter': 'Luter świadkiem Chrystusa ?',
    'bn2017': 'Boże Narodzenie w tajemnicy Trójcy Przenajświętszej',
    'synowielaski': 'Synowie łaski przywołajcie narody i miasta',
    'witajoblubienico': 'Witaj Oblubienico Ducha Świętego',
    'mowaboga': 'Orędzia-Mowa Boga',
    'chwalaboga': 'Chwała Boga-doszliśmy do absurdu',
    'maciewybor': 'Macie wybór między Niebem a Piekłem',
    'kontds': 'Kontemplacja Ducha Świętego',
    'listyp': 'Kontemplacja Ducha Świętego w listach św. Pawła',
    'prosby': 'Prośby Matki Bożej',
    'zyciesak': 'Życie sakramentalne wg. św. Agnieszki',
    'objquito': 'Objawienia w Quito',
    'poznajmy': 'Poznajmy Wroga',
    'tajemnicabn': 'Tajemnica Bożego Narodzenia',
    'lag2016': 'Mała Intronizacja 2016',
    'dsroz': 'Duchu Święty Rozpal',
    'kontemplacjajch': 'Kontemplacja Jezusa Chrystusa',
    'cierpienieo': 'Cierpienie Oblubienicy',
    'rekokap': 'Rekolekcje o kapłaństwie',
    'intronizacja': 'Intronizacja-może się zegną',
    'quito_nowe': 'Objawienia Matki Bożej z Quito',
    'bogmowi': 'Bóg mówi do swego kapłana',
    'rekolekcje': 'Rekolekcje o Mszy św.',
    'glebiamodlitwy': 'Głębia modlitwy Ojcze nasz',
    'tatojestem': 'Tato jestem',
    '30-lecieksp': '30-lecie kapłaństwa ks.P.M.Natanka',
    'gazetym': 'Gazety mówią o księdzu',
    'regulam': 'Reguła Mariańska',
    'bozatajemnica': 'Boża Tajemnica Maryja',
    'kochamkaplana': 'Kocham polskiego katolickiego kapłana',
    'bitwa_o_post': 'Bitwa o post',
    'tajemnice_glowny': 'Tajemnica różańca świętego',
    'bog_umacnia': 'Bóg umacnia',
    'bajka_sprawozdanie_komisarzy': 'Bajka sprawozdanie komisarzy',
    'istota_ojcostwa_boga': 'Istota Ojcostwa Boga',
    'potega_slowa': 'Potęga Słowa Bożego',
    'rozwazania_drogi_krzyzowej': 'Rozważania drogi krzyżowej',
    'uczynmnieniewolnikiemtwojejmilosci': 'Uczyń Mnie niewolnikiem Twojej miłości',
    'drogapojednania': 'Droga pojednania',
    'leniwiwwierze': 'Leniwi w wierze',
    'kazaniapogrzebowe': 'Kazania pogrzebowe',
    'czysciec': 'Tajemnica czyśćca',
    'cierpienieboga': 'Cierpienie Boga',
    'swiatduchaiswiatciala': 'Świat ducha i świat ciała',
    'triduum2012': 'Święte Triduum',
    'plomien': 'Kościół płonie',
    'niebianskie': 'Bóg powala z nóg - katechezy niebiańskie',
    'zertka': 'Polacy, Bóg chce się podeprzeć o Waszą ofiarę',
    'krol_b': 'Polsko, oto Król nadchodzi!',
    'kaplani1': 'Kapłani Chrystusowi czemu śpicie?',
    'polska1': 'Kocham Polskę',
    'encykliki': 'Encykliki papieskie',
    'kongresmaryjny': 'Kongres Maryjny',
    'czestochowa_kategoria': 'Pielgrzymki do Częstochowy',
    'czest102015': 'Częstochowa 2015',
    'jasna_gora': 'Jasna Góra',
    'krolowa2018': 'Królowa idzie do Sejmu 2018',
    'wars2017': 'Królowa idzie do Sejmu 2017',
    'marsz2016': 'Królowa idzie do Sejmu 2016',
    'kategoria_niepokalane_poczecie_nmp': 'Niepokalane Poczęcie NMP',
    'kategoria_chrystus_krol': 'Chrystus Król - Słowa do Rycerzy',
    'kategoria_bog_ojciec': 'Bóg Ojciec',
    'kategoria_dwa_serca': 'Dwa Serca',
    'kategoria_najdrozsza_krew': 'Najdroższa Krew Pana Jezusa',
    'reformalit': 'Reforma liturgiczna',
    'dwaserca2018': 'Dwa Serca 2018',
    'dwojgaserc2018': 'Uroczystość Dwojga Serc 29.09.2018r.',
    'sekretlasal': 'Sekret La Salette i kompleks księży saletynów',
    'kazkrew2018': 'O Krwi Najdroższa 2018',
    'koronacjamb2018': 'Koronacja Matki Bożej z Quito',
    'quito2018': 'Objawienia Matki Bożej w Quito',
    'cierboga': 'Cierpienie Boga w Trójcy Jedynego',
    'encyklikimaryjne': 'Encykliki Maryjne',
    'uczpm': 'Uczymy się Pieśni Maryjnych',
    'manifestacjazbiorcze': 'Królowa idzie do Sejmu',
    'kazschol': 'Pierwsze kazanie scholastyczne',
    'krolowanie': 'Królowanie Pana Jezusa i Królowanie Maryi',
    'postzbiorcze': 'Posty - Pomagamy Matce Bożej',
    'zesrocz': 'Zestawienie roczne',
    'domychk': 'Domy Chrystusa Króla',
    'zesl4062017': 'Zesłanie Ducha Świętego 04.06.2017r.',
    'kazaniawielkanocy': 'Kazanie Czasu Wielkanocy',
    'kfront': 'Kazanie frontowe',
    '24meki': '24 godziny Męki naszego Pana Jezusa Chrystusa',
    'kontsj': 'Kontemplacja Najświętszego Serca Jezusa',
    'boguzdrawia': 'Bóg czyni cuda i uzdrawia',
    'wdsnabw': 'Wieczernik Ducha Świętego nabożeństwo wieczorne',
    'rozwazaniacz': 'Rozważania czerwcowe',
    'adwokat': 'Nająłem Adwokata na godzinę śmierci',
    'inner': 'Inne retransmisje',
    'adwentglowne': 'Liturgiczne inicjacje adwentowe',
    'objawieniawakita1': 'Objawienia w Akita',
    'wieczornice': 'Wieczornice',
    'burzanadp': 'Burza nad pustelnią',
    'paninarodow': 'Pani Wszystkich Narodów',
    'blogjest': 'Błogosławiony jestem',
    'oduchuswietym': 'O Duchu Świętym',
    'miloscspraw': 'Miłość wypełnia się w sprawiedliwości',
    'refleksje': 'Refleksje betlejemskie',
    'nasza_matka-garabandal': 'Nasza Matka - Garabandal',
    'kazania_pasyjne_glowny': 'Kazania Pasyjne',
    'kazania_nabozenstwa_patriotyczne': 'Kazania i nabożeństwa patriotyczne',
    'w_obronie_garabandal': 'W obronie Garabandal',
    'nabozenstwouzdrawianiaiuwalniania': 'Nabożeństwa uzdrawiania i uwalniania',
    '25lecie_pustelni': '25-lecie Pustelni',
    'ratujcie_dusze': 'Ratujcie dusze',
    'quovadis': 'Quo Vadis',
    'bitwa_pod_wiedniem': 'Bitwa pod Wiedniem',
    'kosciele': 'Kościele obudź się!',
    'bruksela': 'Bruksela - współczesny Jeroboam',
    'wykrot': 'Słowa do pielgrzymów z Wykrotu',
    'galeria_bobola_prawy': 'Rotunda św.Boboli',
    'objawienia_prywatne': 'Objawienia prywatne',
    'przebaczenie': 'O naturze przebaczenia',
    'ktokrolem': 'Kogo wybierzemy Królem - 01.04.2012r.',
    'droga': 'Droga którą idę, jest...',
    'oni_nie_zrobia': 'Oni nie zrobią Intronizacji',
    'baal': "Wzywam proroków Baal'a na konfrontację",
    'katechezy': 'Katechezy czasów ostatecznych',
    'ogloszenia_biezace': 'Ogłoszenia bieżące',
    'slowodorycerzy1': 'Pilne! Słowa do Rycerzy Chrystusa Króla',
    'nowennabogojciec': 'Nowenna ku czci Boga Ojca',
    'zakon': 'Powstaje zakon',
    'banner_oferty_parafii': 'Oferty Parafii Internetowej',
    'wykrot_banner': 'Nocna Pielgrzymka do Wykrotu (1-2/03/2014)',
    'slowobozenacodzien': 'Słowo Boże na co dzień',
    'oredzianaczasyostateczne': 'Orędzia na Czasy Ostateczne - czyta ks. Piotr',
    'zywoty_swietych_panskich': 'Żywoty Świętych Pańskich',
    'msze_swiete': 'Całe msze święte - nowe okienko',
    'ewangeliawspol': 'Ewangelia współcześnie',
    'matka_swietych_polska': 'Matka Świętych Polska',
    'filozofiamyslenia': 'Filozofia myślenia',
    'slowobozevaltorta': 'Słowo Boże na co dzień - M. Valtorta',
    'dni_wiernych_parafii': 'Dni wiernych parafii',
    'medugorje2018': 'Medugorje 9-17.10.2018r.',
    'kongres2016': 'III-ci Kongres Maryjny 2016r.',
    'iikongresmaryjny': 'II-gi Kongres Maryjny 2015r.',
    '1kongresma': 'I-szy Kongres Maryjny 2014r.',
    '1roczek_ks_piotra': '1-szy Roczek ks. Piotra',
    '50teurodziny_ks_piotra': '50-te Urodziny ks. Piotra',
    'bogojciec2018': 'Uroczystość Boga Ojca 2018',
    'ubogojciec2017': 'Uroczystość Boga Ojca 2017',
    'bojciec2016': 'Uroczystość Boga Ojca 2016',
    'bogojciec2015': 'Uroczystość Boga Ojca 2015',
    'bogojciec2014': 'Uroczystość Boga Ojca 2014',
    'ojcostwoboga2014': 'Ojcostwo Boga 2014',
    'bogaojca2012': 'Uroczystość Boga Ojca 2012',
    '20110807': 'Uroczystość Boga Ojca 2011',
    'milosc_boga': 'Miłość Boga',
    'dwojgaserc2017': 'Uroczystość Dwojga Serc 2017',
    'ds2016': 'Uroczystość Dwojga Serc 2016',
    'dwojgaserc2015': 'Uroczystość Dwojga Serc 2015',
    'dwojgaserc2014': 'Uroczystość Dwojga Serc 2014',
    'niepokalaneserce2014': 'Niepokalane Serce NMP 2014',
    'dwojgaserc_28092013': 'Uroczystość Dwojga Serc 2013',
    'uroczkrwi2017': 'Uroczystość Najdroższej Krwi Pana Jezusa 2017',
    'krew2016': 'Uroczystość Najdroższej Krwi Pana Jezusa 2016',
    'najkrew2015': 'Uroczystość Najdroższej Krwi Pana Jezusa 2015',
    'najdrozszakrew2014': 'Uroczystość Najdroższej Krwi Pana Jezusa 2014',
    'najdrozszejkrwi_07072013': 'Uroczystość Najdroższej Krwi Pana Jezusa 2013',
    'npocz2017': 'Uroczystość Niepokalanego Poczęcia NMP 2017',
    'np2016': 'Uroczystość Niepokalanego Poczęcia NMP 2016',
    'npnmp2015': 'Uroczystość Niepokalanego Poczęcia NMP 2015',
    'npnmp2014': 'Uroczystość Niepokalanego Poczęcia NMP 2014',
    'niepokalanego_poczecia_08122013': 'Uroczystość Niepokalanego Poczęcia NMP 2013',
    'godzina_laski': 'Godzina łaski',
    'odpust2012': 'Odpust Parafialny 2012',
    'pielgrzymki_550x120': 'Pielgrzymki Odbijamy Europę',
    'chrystuskrol2018': 'Uroczystość Jezusa Chrystusa Króla Polski 2018',
    'podmianka': 'Podmianka - Atrapa Kościoła',
}
TITLES_MAP_LOWER = dict((key.lower(), value) for key, value in TITLES_MAP.items())


def _fixRun(m):
    raw = m.group(0)
    try:
        raw.decode('utf-8')
        return raw
    except Exception:
        try:
            return raw.decode('iso-8859-2').encode('utf-8')
        except Exception:
            return raw


def fixCharset(data):
    # the site mixes UTF-8 with old ISO-8859-2 bytes in one page - repair run by run
    try:
        if isinstance(data, bytes):
            data = re.sub(b'[\x80-\xff]+', _fixRun, data)
            if not isPY2():
                data = data.decode('utf-8', 'ignore')
    except Exception:
        printExc()
    return data


class Christusvincit(GenericFolderWatchedScraperMixin, CBaseHostClass):
    FAV_FIELDS = ('name', 'category', 'type', 'title', 'url', 'icon', 'clip_id', 'yt_id', 'is_live', 'section_idx', 'section_title',
                  'section_nth', 'list_type')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'christusvincit-tv.pl', 'cookie': 'christusvincit-tv.pl.cookie'})
        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.MAIN_URL = gettytul()
        self.DEFAULT_ICON_URL = self.getFullUrl('images/christusbg.jpg')
        self.oembedCache = {}
        self.vimeoCache = {}
        self.knownTitles = list(SECTION_TITLES) + list(TITLES_MAP.values())
        self.watchedHelper = IPTVWatchedHelper("christusvincit")
        self.wfInitFolderCache()

    ###################################################
    # watched flag / favourites
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            if cItem.get('type', '') in ('video', 'audio'):
                if cItem.get('is_live'):
                    return ''
                if cItem.get('clip_id'):
                    return 'video:vimeo:%s' % cItem['clip_id']
                if cItem.get('yt_id'):
                    return 'video:yt:%s' % cItem['yt_id']
                return ''
            category = cItem.get('category', '')
            url = str(cItem.get('url', '') or '').strip()
            # page 2+ of a Vimeo list keys like page 1, so its clips propagate to the same folder
            if url and category in ('list_page', 'vimeo_list'):
                return 'folder:%s' % self.wfNormalizeUrlKey(url)
        except Exception:
            printExc()
        return ''

    def getFavouriteData(self, cItem):
        # plays / duration in desc change between two loads - keep only what identifies and reopens the row
        try:
            return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # helpers
    ###################################################
    def getPage(self, url, addParams=None, post_data=None):
        if addParams is None:
            addParams = dict(self.defaultParams)
        # raw bytes: fixCharset repairs the mixed UTF-8 / ISO-8859-2 pages
        addParams['convert_charset'] = False
        sts, data = self.cm.getPage(url, addParams, post_data)
        if sts:
            data = fixCharset(data)
        return sts, data

    def getVimeoPage(self, url, referer=None):
        header = dict(self.HTTP_HEADER)
        header['Referer'] = referer or self.MAIN_URL
        return self.cm.getPage(url, {'header': header})

    def cleanTitle(self, title):
        title = self.cleanHtmlStr(title)
        if not isPY2():
            title = title.replace(u'�', '?')
        title = re.sub(r'\s+', ' ', title).strip()
        if '?' in title:
            # the site lost Polish letters as "?" - take the proper spelling when it is a known title
            pattern = '^%s$' % re.escape(title).replace(r'\?', '.{1,2}')
            for known in self.knownTitles:
                if re.match(pattern, known, re.I):
                    return known
        if not isPY2() and len(title) > 3 and title.isupper():
            title = title[:1] + title[1:].lower()
        return title

    def normTitle(self, title):
        title = self.cleanTitle(title)
        if IsMediaNamingNormalized():
            title = re.sub(r'(?i)\.(?:mp4|m4v|mov|mkv|avi|wmv|flv|mpe?g)$', '', title).strip()
            title = re.sub(r'(?i)\s*-?\s*nowe okienko\s*$', '', title)
            title = re.sub(r'^[-\s]+', '', title)
            title = re.sub(r'\s*\.{2,}\s*$', '', title).strip()
        return title

    def imageTitle(self, icon):
        base = icon.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        if base.lower() in TITLES_MAP_LOWER:
            return TITLES_MAP_LOWER[base.lower()]
        base = re.sub(r'[_\-]+', ' ', base).strip()
        return base[:1].upper() + base[1:] if base else ''

    def pageUrl(self, href):
        href = href.replace('&amp;', '&').strip()
        m = re.search(r'(articles|readarticle|viewpage)\.php\?(article_id|page_id)=(\d+)', href)
        if not m:
            return ''
        if m.group(1) == 'viewpage':
            return self.getFullUrl('viewpage.php?page_id=%s' % m.group(3))
        return self.getFullUrl('articles.php?article_id=%s' % m.group(3))

    def oembed(self, url):
        if url in self.oembedCache:
            return self.oembedCache[url]
        if 'youtube' in url:
            api = 'https://www.youtube.com/oembed?format=json&url=' + urllib_quote(url, safe='')
        else:
            api = 'https://vimeo.com/api/oembed.json?url=' + urllib_quote(url, safe='')
        ret = {}
        sts, data = self.getVimeoPage(api)
        if sts:
            try:
                ret = json_loads(data)
                if not isinstance(ret, dict):
                    ret = {}
            except Exception:
                printExc()
        self.oembedCache[url] = ret
        return ret

    def splitPage(self, data):
        # center column (sections with capmain) and the side panels (scapmain)
        start = data.find("class='capmain-left'")
        if start < 0:
            return [], []
        end = data.find('side-border-right', start)
        if end < 0:
            end = len(data)
        center = []
        for part in data[start:end].split("class='capmain-left'")[1:]:
            title = self.cm.ph.getSearchGroups(part, r"class='capmain'>(.*?)</td>", 1, True)[0]
            body = part.split("class='main-body'", 1)[-1]
            center.append((self.cleanTitle(title), body))
        sides = []
        for chunk in (data[:start], data[end:]):
            for part in chunk.split("class='scapmain-left'")[1:]:
                title = self.cm.ph.getSearchGroups(part, r"class='scapmain'>(.*?)</td>", 1, True)[0]
                body = part.split("class='side-body'", 1)[-1]
                sides.append((self.cleanTitle(title), body))
        return center, sides

    def parseContent(self, html, curUrl='', allPages=True):
        # iframes (YouTube / Vimeo) and links to other article pages, in page order
        entries = []
        seen = set()
        if curUrl:
            seen.add(curUrl)
        for m in re.finditer(r'''<iframe[^>]+?src=['"]([^'"]+)['"]|<a\s[^>]*?href=['"]([^'"]+)['"][^>]*>(.*?)</a>''', html, re.I | re.S):
            if m.group(1):
                src = m.group(1).replace('&amp;', '&').strip()
                if src.startswith('//'):
                    src = 'https:' + src
                yt = self.cm.ph.getSearchGroups(src, r'(?:youtube(?:-nocookie)?\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})')[0]
                vs = re.search(r'vimeo\.com/(showcase|event)/(\d+)', src)
                if yt:
                    key = 'yt:' + yt
                    if key not in seen:
                        seen.add(key)
                        entries.append({'kind': 'yt', 'id': yt})
                elif vs:
                    url = 'https://vimeo.com/%s/%s/embed' % (vs.group(1), vs.group(2))
                    if url not in seen:
                        seen.add(url)
                        entries.append({'kind': 'vimeo', 'list_type': vs.group(1), 'url': url})
                else:
                    # the old Kaltura servers (mediaserwer3 / mediaserver4) answer 404
                    printDBG("Christusvincit: iframe skipped [%s]" % src)
                continue
            url = self.pageUrl(m.group(2))
            if not url or url in seen or url.endswith('page_id=1'):
                continue
            if not allPages and 'viewpage.php' in url and url.rsplit('=', 1)[-1] not in VIDEO_PAGES:
                continue
            seen.add(url)
            inner = m.group(3)
            icon = self.cm.ph.getSearchGroups(inner, r'''<img[^>]+?src=['"]([^'"]+)['"]''')[0]
            icon = self.getFullUrl(icon) if icon else ''
            title = self.cleanTitle(inner)
            if not title and icon:
                title = self.imageTitle(icon)
            if not title:
                continue
            entries.append({'kind': 'page', 'url': url, 'title': title, 'icon': icon})
        return entries

    def addEntries(self, cItem, entries, fallbackTitle=''):
        for entry in entries:
            params = stripPagerKeys(dict(cItem), CHILD_DROP_KEYS)
            if entry['kind'] == 'page':
                params.update({'good_for_fav': True, 'category': 'list_page', 'title': self.normTitle(entry['title']),
                               'url': entry['url'], 'icon': entry['icon'] or self.DEFAULT_ICON_URL, 'desc': ''})
                self.addDir(params)
            elif entry['kind'] == 'yt':
                url = 'https://www.youtube.com/watch?v=%s' % entry['id']
                meta = self.oembed(url)
                title = self.normTitle(meta.get('title', '') or fallbackTitle or 'YouTube')
                icon = meta.get('thumbnail_url', '') or 'https://i.ytimg.com/vi/%s/hqdefault.jpg' % entry['id']
                params.update({'good_for_fav': True, 'category': 'yt_video', 'title': title, 'url': url, 'yt_id': entry['id'],
                               'icon': icon, 'desc': ('YouTube | %s' % meta.get('author_name', '')).strip(' |')})
                self.addVideo(params)
            else:
                meta = self.oembed(entry['url'].rsplit('/embed', 1)[0])
                title = self.normTitle(meta.get('title', '') or fallbackTitle or 'Vimeo')
                if entry['list_type'] == 'event':
                    desc = _('Vimeo live event: the live transmission (while on air) and the past transmissions.')
                else:
                    desc = _('Vimeo playlist with the recordings of this page.')
                if meta.get('author_name'):
                    desc += ' (%s)' % self.cleanTitle(meta['author_name'])
                if meta.get('description'):
                    desc += '\n' + self.cleanTitle(meta['description'])
                params.update({'good_for_fav': True, 'category': 'vimeo_list', 'title': title, 'url': entry['url'],
                               'list_type': entry['list_type'], 'icon': meta.get('thumbnail_url', '') or self.DEFAULT_ICON_URL,
                               'desc': desc})
                self.addDir(params)

    ###################################################
    # lists
    ###################################################
    def listMain(self, cItem):
        printDBG("Christusvincit.listMain")
        sts, data = self.getPage(self.getMainUrl())
        if sts:
            center, sides = self.splitPage(data)
            sections = center + sides
            used = set()
            for idx, (title, body) in enumerate(sections):
                if not title or title.lower() == 'linki':
                    continue
                if not self.parseContent(body, '', False):
                    continue
                label = title
                n = 2
                while label in used:
                    label = '%s %d' % (title, n)
                    n += 1
                used.add(label)
                # section_title (+ section_nth for repeated captions) finds the section again from a favourite
                # after the site added or removed a section; section_idx is only the fallback
                self.addDir({'name': 'category', 'category': 'list_section', 'good_for_fav': True, 'title': label,
                             'url': self.getMainUrl(), 'section_idx': idx, 'section_title': title,
                             'section_nth': len([1 for section in sections[:idx] if section[0] == title]),
                             'icon': self.DEFAULT_ICON_URL})
        for catId in ('1', '2', '3'):
            self.addDir({'name': 'category', 'category': 'list_cat', 'good_for_fav': True, 'title': '%s A-Z (%s)' % (_('Articles'), catId),
                         'url': self.getFullUrl('articles.php?cat_id=%s' % catId), 'icon': self.DEFAULT_ICON_URL})
        self.listsTab(self.searchItems(), cItem)

    def listSection(self, cItem):
        printDBG("Christusvincit.listSection [%s]" % cItem.get('section_idx'))
        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        center, sides = self.splitPage(data)
        sections = center + sides
        idx = int(cItem.get('section_idx', -1))
        if cItem.get('section_title'):
            matches = [i for i, section in enumerate(sections) if section[0] == cItem['section_title']]
            nth = int(cItem.get('section_nth', 0) or 0)
            idx = matches[nth] if nth < len(matches) else -1
        if not 0 <= idx < len(sections):
            SetIPTVPlayerLastHostError(_("This section is no longer on the main page."))
            return
        self.addEntries(cItem, self.parseContent(sections[idx][1], '', False), sections[idx][0])

    def listPage(self, cItem):
        printDBG("Christusvincit.listPage [%s]" % cItem['url'])
        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        center = self.splitPage(data)[0]
        if not center:
            SetIPTVPlayerLastHostError(_("No stream available"))
            return
        pageTitle = center[0][0]
        html = ''.join([body for _title, body in center])
        entries = self.parseContent(html, cItem['url'], True)
        if len(entries) == 1 and entries[0]['kind'] == 'vimeo':
            # a page with just one showcase: show its recordings directly
            params = dict(cItem)
            params.update({'url': entries[0]['url'], 'list_type': entries[0]['list_type']})
            self.listVimeo(params, cItem)
            return
        self.addEntries(cItem, entries, pageTitle)
        if not self.currList:
            # most older articles (the oldest search results) only embed the site's former Kaltura player
            if re.search(r'(?i)mediaserwer3\.|mediaserver4\.|kaltura', html):
                SetIPTVPlayerLastHostError(_("The recordings of this page were on the site's old media server, which is offline."))
            else:
                SetIPTVPlayerLastHostError(_("No stream available"))

    def listCategory(self, cItem):
        printDBG("Christusvincit.listCategory [%s]" % cItem['url'])
        sts, data, page = self.getRowstartPage(cItem)
        if not sts:
            return
        center = self.splitPage(data)[0]
        body = center[0][1] if center else ''
        seen = set()
        for aid, title in re.findall(r'''<a href=['"]articles\.php\?article_id=(\d+)['"]>([^<]+)</a>''', body):
            if aid in seen:
                continue
            seen.add(aid)
            title = self.normTitle(title)
            if not title:
                continue
            params = stripPagerKeys(dict(cItem), CHILD_DROP_KEYS)
            params.update({'good_for_fav': True, 'category': 'list_page', 'title': title,
                           'url': self.getFullUrl('articles.php?article_id=%s' % aid), 'icon': self.DEFAULT_ICON_URL, 'desc': ''})
            self.addDir(params)
        self.addRowstartPaging(cItem, data, page, bool(seen))

    def getRowstartPage(self, cItem):
        # PHP-Fusion lists page by item offset (&rowstart=N); the rows per page come from the page's own pager
        page = int(cItem.get('page', 1) or 1)
        rowstart = (page - 1) * int(cItem.get('per_page', 15) or 15)
        sts, data = self.getPage(cItem['url'] + ('&rowstart=%d' % rowstart if rowstart else ''))
        return sts, data, page

    def addRowstartPaging(self, cItem, data, page, hasItems):
        # pager "Strona 5 z 11: <a href='...&amp;rowstart=0'>1</a>..." -> rows per page and last page
        nav = self.cm.ph.getDataBeetwenMarkers(data, "class='pagenav'", '</div>', False)[1]
        perPage = 0
        lastPage = page
        for rowstart, num in re.findall(r"rowstart=(\d+)['\"][^>]*>(\d+)<", nav):
            rowstart, num = int(rowstart), int(num)
            lastPage = max(lastPage, num)
            if num > 1 and not perPage:
                perPage = rowstart // (num - 1)
        listItem = dict(cItem)
        if perPage:
            listItem['per_page'] = perPage
        # one url for all pages: the page number becomes the offset in getRowstartPage
        addPagingItems(self, listItem, page, hasItems and lastPage > page, lastPage, cItem['url'])

    def parseDataForPlayer(self, data):
        try:
            idx = data.find('var dataForPlayer = ')
            if idx < 0:
                return None
            idx += len('var dataForPlayer = ')
            end = json.JSONDecoder().raw_decode(data[idx:])[1]
            obj = json_loads(data[idx:idx + end])
            return (obj.get('playlist_data') or {}), (obj.get('clips') or [])
        except Exception:
            printExc()
        return None

    def listVimeo(self, cItem, baseItem=None):
        printDBG("Christusvincit.listVimeo [%s]" % cItem['url'])
        url = cItem['url']
        listType = cItem.get('list_type', 'showcase')
        page = int(cItem.get('page', 1))
        if baseItem is None:
            baseItem = cItem
        cached = self.vimeoCache.get(url)
        if cached is None:
            sts, data = self.getVimeoPage(url)
            if not sts:
                return
            cached = self.parseDataForPlayer(data)
            if cached is None:
                return
            # the big showcases carry ~2000 clips in one page - keep the last one for the next pages
            self.vimeoCache = {url: cached}
        playlist, clips = cached
        listId = self.cm.ph.getSearchGroups(url, r'/(?:showcase|event)/(\d+)')[0]
        plTitle = self.cleanTitle(playlist.get('title', '') or '')
        if listType == 'event':
            # the event's own entry (duration 00:00, is_live false) is the idle live player - it only plays while
            # the event is on air (then is_live is set); the rest are past transmissions. Live entries go first.
            clips = [c for c in clips if c.get('is_live')] + \
                    [c for c in clips if not c.get('is_live') and str(c.get('duration', '') or '') not in ('00:00', '')]
        start = (page - 1) * PER_PAGE
        for clip in clips[start:start + PER_PAGE]:
            vid = str(clip.get('id', '') or '')
            title = self.normTitle(clip.get('title', '') or '')
            if not vid or not title:
                continue
            icon = re.sub(r'-d_\d+(\?|$)', r'-d_640\1', str(clip.get('thumbnail', '') or ''))
            if listType == 'event':
                clipUrl = 'https://vimeo.com/event/%s/embed/%s' % (listId, vid)
            else:
                clipUrl = 'https://vimeo.com/showcase/%s/video/%s/embed' % (listId, vid)
            duration = str(clip.get('duration', '') or '')
            desc = [_('Live') if clip.get('is_live') else duration]
            if clip.get('plays'):
                desc.append('%s: %s' % (_('Views'), clip['plays']))
            if plTitle:
                desc.append(plTitle)
            params = stripPagerKeys(dict(baseItem), CHILD_DROP_KEYS)
            params.update({'good_for_fav': True, 'category': 'vimeo_video', 'title': title, 'url': clipUrl, 'clip_id': vid,
                           'icon': icon, 'duration': duration, 'plays': clip.get('plays', ''), 'playlist': plTitle,
                           'is_live': bool(clip.get('is_live')), 'desc': ' | '.join([d for d in desc if d])})
            self.addVideo(params)
        if not clips:
            SetIPTVPlayerLastHostError(_("The live stream is not available at the moment.") if listType == 'event' else _("No stream available"))
        listItem = dict(cItem)
        listItem.update({'url': url, 'list_type': listType, 'category': 'vimeo_list'})
        # paged locally out of the one cached clip list - one url for all pages
        addPagingItems(self, listItem, page, len(clips) > start + PER_PAGE, (len(clips) + PER_PAGE - 1) // PER_PAGE, url)

    def listSearchResult(self, cItem, searchPattern, searchType):
        printDBG("Christusvincit.listSearchResult [%s]" % searchPattern)
        # newest first (order=1): the oldest articles only embed the offline Kaltura player
        url = self.getFullUrl('search.php?stext=%s&search=Szukaj&method=AND&stype=articles&forum_id=0&datelimit=0&fields=2&sort=datestamp&order=1&chars=50' % urllib_quote_plus(searchPattern))
        params = dict(cItem)
        params.update({'category': 'list_search', 'url': url})
        self.listSearchItems(params)

    def listSearchItems(self, cItem):
        printDBG("Christusvincit.listSearchItems")
        sts, data, page = self.getRowstartPage(cItem)
        if not sts:
            return
        tmp = data.split("class='search_result'", 1)
        if len(tmp) < 2:
            return
        body = tmp[1].split('</td>', 1)[0]
        seen = set()
        for item in re.split(r'''(?=<a href=['"]readarticle\.php)''', body):
            aid = self.cm.ph.getSearchGroups(item, r'''readarticle\.php\?article_id=(\d+)''')[0]
            if not aid or aid in seen:
                continue
            seen.add(aid)
            title = self.normTitle(self.cm.ph.getSearchGroups(item, r'''readarticle\.php\?article_id=\d+['"]>(.*?)</a>''')[0])
            date = self.cleanHtmlStr(self.cm.ph.getSearchGroups(item, r'''</a>\s*(dnia[^<]+)''')[0])
            if not title:
                continue
            params = stripPagerKeys(dict(cItem), CHILD_DROP_KEYS)
            params.update({'good_for_fav': True, 'category': 'list_page', 'title': title, 'name': 'category',
                           'url': self.getFullUrl('articles.php?article_id=%s' % aid), 'icon': self.DEFAULT_ICON_URL, 'desc': date})
            self.addDir(params)
        self.addRowstartPaging(cItem, data, page, bool(seen))

    ###################################################
    # links
    ###################################################
    def getVimeoConfigUrl(self, cItem):
        # the player config needs the signature of the embedding page (player.vimeo.com itself is bot protected)
        sts, data = self.getVimeoPage(cItem['url'])
        if not sts:
            return ''
        clipId = str(cItem.get('clip_id', '') or '')
        if clipId and '/event/' in cItem['url']:
            parsed = self.parseDataForPlayer(data)
            if parsed:
                for clip in parsed[1]:
                    if str(clip.get('id', '')) == clipId:
                        return clip.get('config_no_autoplay') or clip.get('config') or ''
        url = self.cm.ph.getSearchGroups(data, r'''data-config-url=['"]([^'"]+)['"]''')[0].replace('&amp;', '&')
        if clipId and url and ('/video/%s/' % clipId) not in url:
            return ''
        return url

    def getLinksForVideo(self, cItem):
        printDBG("Christusvincit.getLinksForVideo [%s]" % cItem.get('url'))
        urlsTab = []
        if cItem.get('yt_id'):
            urlsTab.append({'name': 'YouTube', 'url': cItem['url'], 'need_resolve': 1})
            return applySidecarToLinks(urlsTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

        configUrl = self.getVimeoConfigUrl(cItem)
        if not configUrl:
            return []
        sts, data = self.getVimeoPage(configUrl)
        if not sts:
            return []
        hlsUrl = ''
        try:
            conf = json_loads(data)
            hls = ((conf.get('request') or {}).get('files') or {}).get('hls') or {}
            cdns = hls.get('cdns') or {}
            default = hls.get('default_cdn', '')
            for key in [default] + [k for k in cdns if k != default]:
                cdn = cdns.get(key) or {}
                hlsUrl = cdn.get('url') or cdn.get('avc_url') or ''
                if hlsUrl:
                    break
        except Exception:
            printExc()
        if not hlsUrl:
            if cItem.get('is_live'):
                SetIPTVPlayerLastHostError(_("The live stream is not available at the moment."))
            return []
        meta = {'Referer': 'https://player.vimeo.com/', 'Origin': 'https://player.vimeo.com', 'User-Agent': self.HTTP_HEADER['User-Agent']}
        if cItem.get('is_live'):
            meta['iptv_livestream'] = True
        for item in getDirectM3U8Playlist(strwithmeta(hlsUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
            item['name'] = 'Vimeo %s' % item.get('name', '')
            item['need_resolve'] = 0
            urlsTab.append(item)
        return applySidecarToLinks(urlsTab, buildSidecarFromItem(cItem, IsSidecarEnabled()))

    def getVideoLinks(self, videoUrl):
        printDBG("Christusvincit.getVideoLinks [%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
            return decorateResolvedLinkItems(self.up.getVideoLinkExt(videoUrl), sidecar)
        return []

    ###################################################
    # INFO
    ###################################################
    def getArticleContent(self, cItem):
        printDBG("Christusvincit.getArticleContent [%s]" % cItem.get('url', ''))
        title = cItem.get('title', '')
        text = cItem.get('desc', '')
        icon = cItem.get('icon', '')
        other = {}
        if cItem.get('category') == 'list_page':
            sts, data = self.getPage(cItem['url'])
            if sts:
                center = self.splitPage(data)[0]
                if center:
                    title = self.normTitle(center[0][0]) or title
                    body = center[0][1].split("class='capmain-right'", 1)[0]
                    body = re.sub(r'(?is)<(script|style|iframe)[^>]*>.*?</\1>', ' ', body)
                    body = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</tr>', '[/br]', body)
                    lines = [self.cleanHtmlStr(line) for line in body.split('[/br]')]
                    text = '\n'.join([line for line in lines if line])
                    if isPY2():
                        # py2 byte str: cut on characters, not inside a UTF-8 sequence
                        text = text.decode('utf-8', 'ignore')[:3000].encode('utf-8')
                    else:
                        text = text[:3000]
                    img = self.cm.ph.getSearchGroups(center[0][1], r'''<img[^>]+?src=['"]([^'"]+)['"]''')[0]
                    if img and (not icon or icon == self.DEFAULT_ICON_URL):
                        icon = self.getFullUrl(img)
        else:
            if cItem.get('duration'):
                other['duration'] = cItem['duration']
            if cItem.get('plays'):
                other['views'] = str(cItem['plays'])
            if cItem.get('playlist'):
                other['category'] = cItem['playlist']
            if cItem.get('yt_id'):
                other['source'] = 'YouTube'
            elif cItem.get('category', '') in ('vimeo_video', 'vimeo_list'):
                other['source'] = 'Vimeo'
        images = [{'title': '', 'url': icon}] if icon else []
        return [{'title': title, 'text': text or title, 'images': images, 'other_info': other}]

    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("Christusvincit.handleService name[%s] category[%s]" % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'list_section':
            self.listSection(self.currItem)
        elif category == 'list_cat':
            self.listCategory(self.currItem)
        elif category == 'list_page':
            self.listPage(self.currItem)
        elif category == 'vimeo_list':
            self.listVimeo(self.currItem)
        elif category == 'list_search':
            self.listSearchItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Christusvincit(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper("christusvincit")

    def withArticleContent(self, cItem):
        return cItem.get('category', '') in ('list_page', 'vimeo_list', 'vimeo_video', 'yt_video')
