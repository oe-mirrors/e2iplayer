# -*- coding: utf-8 -*-
#
# Backdrop (fanart) of a title behind E2iPlayer's panels: the INFO page of a list, the "Select link" list and the
# player's INFO pages, audio playback and pause.
#
# The picture is the host's own ("backdrop" of the list item or of its INFO page), else - setting "From the host,
# else online" - the 16:9 picture of the metadata services for the IMDb id of the title the item's INFO page found
# (matchedTitle): never a search by the title alone, which finds namesakes. backdropUrl() asks while the host builds
# the INFO page (CHostBase.getArticleContent, a worker thread). The picture is downloaded in a worker thread, cut
# to the screen and darkened once with PIL (Enigma2 can't dim a picture itself), and kept in the cache folder.

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.cover import Cover
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetCacheSubDir

###################################################
# FOREIGN import
###################################################
from Components.config import config
from Screens.Screen import Screen
from enigma import getDesktop
from hashlib import md5
import os

# how bright the picture stays (1.0 = as it is): the texts of the panels in front of it must stay readable
BACKDROP_BRIGHTNESS = 0.45
# prepared pictures kept in the cache folder (one per title and screen size)
BACKDROP_KEEP = 12
BACKDROP_DIR = 'backdrops'


def backdropMode():
    # 'off', 'host' (only the host's picture) or 'online' (else the metadata services)
    try:
        return config.plugins.iptvplayer.backdrop.value
    except Exception:
        return 'off'


def backdropOnPause():
    try:
        return backdropMode() != 'off' and config.plugins.iptvplayer.backdrop_pause.value
    except Exception:
        return False


def _hostBackdrop(item):
    url = (item or {}).get('backdrop', '') if isinstance(item, dict) else ''
    return url if isinstance(url, str) and url.startswith('http') else ''


def backdropUrl(cItem, hostItems=None):
    # blocking (network): the url of the item's backdrop, '' for none. cItem: the list item; hostItems: the dicts of
    # the host's INFO page (getArticleContent). Called right after the host built its INFO page, in the same thread:
    # libs/moviemeta knows then which lookup answered on it (getInfoQuery).
    mode = backdropMode()
    if mode == 'off':
        return ''
    for item in list(hostItems or []) + [cItem]:
        url = _hostBackdrop(item)
        if url:
            return url
    if mode != 'online' or not isinstance(cItem, dict):
        return ''
    try:
        mediaType, imdbId = matchedTitle(cItem)
        if mediaType not in ('movie', 'tv') or not imdbId:
            return ''
        from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getImage169
        # the title's backdrop by its IMDb id only (no search by title), not the still of an episode
        return getImage169(mediaType, '', '', '', '', imdbId, 1280) or ''
    except Exception:
        printExc()
        return ''


def _isImdbId(value):
    return isinstance(value, str) and value.startswith('tt') and value[2:].isdigit()


def _metaYear(meta):
    year = str(((meta or {}).get('info') or {}).get('year', '') or '')[:4]
    return int(year) if year.isdigit() else 0


def matchedTitle(cItem):
    # blocking (the lookups are cached by then): (media type, IMDb id) of the title the item's INFO page found,
    # ('', '') when that is not sure enough - then no backdrop rather than another title's picture (forum 25.11.:
    # "The Substitute" without a year showed a namesake series' backdrop)
    # - the host's own IMDb id of the item (meta_imdb)
    # - the lookup that answered on the INFO page (getInfoQuery): by an IMDb id, or by title AND year - the title
    #   it found must be within a year of the host's year (a title alone finds namesakes)
    from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getInfoQuery, getMeta
    if _isImdbId(cItem.get('meta_imdb', '')):
        return cItem.get('meta_type', ''), cItem['meta_imdb']
    query = getInfoQuery(cItem)
    if not query:
        return '', ''
    mediaType = query.get('type', '')
    if _isImdbId(query.get('imdb', '')):
        return mediaType, query['imdb']
    year = str(query.get('year', '') or '')
    if not year.isdigit() or not query.get('title'):
        return '', ''
    meta = getMeta(mediaType, query['title'], year, tuple(query.get('skip') or ()), query.get('maxYearDiff'))
    found = _metaYear(meta)
    imdbId = (meta or {}).get('imdb_id', '')
    if not found or abs(found - int(year)) > 1 or not _isImdbId(imdbId):
        printDBG("Backdrop: no sure match for %r (found year %r, imdb %r)" % (query, found, imdbId))
        return '', ''
    return mediaType, imdbId


def backdropPath(url, width, height):
    return GetCacheSubDir(BACKDROP_DIR, 'backdrop_%s_%dx%d.jpg' % (md5(url.encode('utf-8')).hexdigest()[:16], width, height))


def _prune(keep):
    folder = GetCacheSubDir(BACKDROP_DIR)
    try:
        # finished pictures only: the .src / .part files of a download running in another worker stay
        files = [os.path.join(folder, name) for name in os.listdir(folder) if name.startswith('backdrop_') and name.endswith('.jpg')]
        files.sort(key=os.path.getmtime, reverse=True)
        for path in files[keep:]:
            os.remove(path)
    except Exception:
        printExc()


def cutAndDim(source, target, width, height, brightness=BACKDROP_BRIGHTNESS):
    # the picture cut to the screen's aspect ratio (no black bars), scaled and darkened; False when PIL can't read it
    from PIL import Image, ImageEnhance
    with Image.open(source) as img:
        if img.format == 'JPEG':
            # decodes a big JPEG at a fraction of its size: much faster on the box
            img.draft('RGB', (width, height))
        img = img.convert('RGB')
        srcW, srcH = img.size
        if srcW <= 0 or srcH <= 0:
            return False
        scale = max(width / float(srcW), height / float(srcH))
        cropW, cropH = min(srcW, int(round(width / scale))), min(srcH, int(round(height / scale)))
        left, top = (srcW - cropW) // 2, (srcH - cropH) // 2
        img = img.crop((left, top, left + cropW, top + cropH)).resize((width, height), Image.BILINEAR)
        img = ImageEnhance.Brightness(img).enhance(brightness)
        img.save(target + '.part', format='JPEG', quality=85)
    os.rename(target + '.part', target)
    return True


def makeBackdropFile(target, url, width, height):
    # blocking: the prepared picture of url for a screen of width x height, '' when it can't be made. Runs in a
    # worker thread (Cover.decodeCoverMadeBy).
    if os.path.isfile(target):
        try:
            os.utime(target, None)  # the newest stay in the cache
        except Exception:
            pass
        return target
    raw = target + '.src'
    try:
        from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
        cm = common()
        params = {'header': {'User-Agent': cm.HOST, 'Accept': 'image/jpeg,image/png,image/*;q=0.8,*/*;q=0.5'}}
        ret = cm.saveWebFile(raw, url, addParams=params)
        if not ret.get('sts') or not os.path.isfile(raw) or 0 == os.path.getsize(raw):
            printDBG("Backdrop: download failed %s %s" % (url, ret.get('reason', '')))
            return ''
        if not cutAndDim(raw, target, width, height):
            return ''
        printDBG("Backdrop: prepared %s" % target)
        _prune(BACKDROP_KEEP)
        return target
    except Exception:
        printExc()
        return ''
    finally:
        try:
            if os.path.isfile(raw):
                os.remove(raw)
        except Exception:
            pass


class BackdropLoader(object):
    # shows the backdrop of a url in a Cover widget of the size of the screen; onReady(True / False) once it is
    # there or failed. Main thread only.
    def __init__(self, cover, onReady=None):
        self.cover = cover
        self.onReady = onReady
        self.url = ''
        self.ready = False
        self.path = ''
        self.closed = False

    def load(self, url):
        if self.closed or not url or url == self.url or self.cover.instance is None:
            return
        self.url = url
        self.ready = False
        size = self.cover.instance.size()
        width, height = size.width(), size.height()
        if width <= 0 or height <= 0:
            return
        target = backdropPath(url, width, height)
        try:
            self.cover.decodeCoverMadeBy(makeBackdropFile, (target, url, width, height), self._decoded, 'backdrop')
        except Exception:
            printExc()

    def _decoded(self, ret):
        if self.closed:
            return
        pixmap = ret.get('Pixmap')
        if pixmap is not None:
            self.cover.updatePixmap(pixmap, ret.get('FileName', ''))
            self.ready = True
            # the player's INFO panels lay a blurred piece of it under their texts
            self.path = ret.get('FileName', '') or ''
        if self.onReady is not None:
            try:
                self.onReady(self.ready)
            except Exception:
                printExc()

    def close(self):
        self.closed = True
        self.onReady = None


class E2iBackdropScreen(Screen):
    # a screen of only the backdrop, under the "Select link" list and the INFO page of a list: made with
    # session.instantiateDialog() just before that screen opens, so it lies above E2iPlayer's list and below
    # the new screen; transparent until the picture is there
    def __init__(self, session):
        desktop = getDesktop(0).size()
        width, height = desktop.width(), desktop.height()
        # zPosition -1: under every other screen (E2iPlayer's list is hidden while the INFO page / link list is open)
        self.skin = '''<screen name="E2iBackdropScreen" position="0,0" size="%d,%d" zPosition="-1" flags="wfNoBorder" backgroundColor="#ff000000">
            <widget name="backdrop" position="0,0" size="%d,%d" zPosition="1" transparent="1" />
        </screen>''' % (width, height, width, height)
        Screen.__init__(self, session)
        self['backdrop'] = Cover()
        self.loader = BackdropLoader(self['backdrop'], self._ready)
        self.pendingUrl = ''
        self.onLayoutFinish.append(self._layoutFinished)
        self.onClose.append(self._onClose)

    def _layoutFinished(self):
        self['backdrop'].hide()
        if self.pendingUrl:
            self.loader.load(self.pendingUrl)

    def load(self, url):
        if not url:
            return
        if self['backdrop'].instance is None:
            self.pendingUrl = url
        else:
            self.loader.load(url)

    def _ready(self, ok):
        if ok:
            self['backdrop'].show()

    def _onClose(self):
        self.loader.close()


class BackdropHolder(object):
    # the E2iBackdropScreen of a screen that opens over E2iPlayer's list: open() before the screen opens, load()
    # when the url is known (or loadFromArticle() to ask the host's INFO page for it), close() when that screen
    # closed. Main thread only.
    def __init__(self, session):
        self.session = session
        self.dialog = None
        self.article = None
        self.timer = None
        self.timer_conn = None
        # the url found for a list item by its INFO page: {item key: url}
        self.known = {}

    def open(self):
        self.close()
        if backdropMode() == 'off':
            return
        try:
            self.dialog = self.session.instantiateDialog(E2iBackdropScreen)
            self.dialog.show()
        except Exception:
            printExc()
            self.dialog = None

    def load(self, url):
        if self.dialog is not None and url:
            self.dialog.load(url)

    def remember(self, key, url):
        # url '' = the INFO page has no backdrop: the host is not asked again for this item
        if key:
            self.known[key] = url
            while len(self.known) > 200:
                del self.known[next(iter(self.known))]

    def loadFromArticle(self, key, startRequest):
        # the url of the item's INFO page: known already, else startRequest(callback) asks the host for it in a
        # worker thread (callback(RetHost) comes from that thread, a timer takes it over)
        if self.dialog is None:
            return
        if key in self.known:
            self.load(self.known[key])
            return
        from enigma import eTimer
        from Plugins.Extensions.IPTVPlayer.tools.iptvtools import eConnectCallback
        self.article = {'key': key, 'ret': None, 'done': False}
        article = self.article

        def done(ret):
            article['ret'] = ret
            article['done'] = True
        try:
            startRequest(done)
        except Exception:
            printExc()
            self.article = None
            return
        self.timer = eTimer()
        self.timer_conn = eConnectCallback(self.timer.timeout, self._checkArticle)
        self.timer.start(200)

    def _checkArticle(self):
        article = self.article
        if article is None or not article['done']:
            return
        self._stopTimer()
        self.article = None
        answered = False
        try:
            ret = article['ret']
            value = getattr(ret, 'value', None)
            url = getattr(value[0], 'backdrop', '') if value else ''
            answered = getattr(ret, 'status', None) == getattr(ret, 'OK', 'ok')  # RetHost.OK
        except Exception:
            printExc()
            url = ''
        printDBG("Backdrop: INFO page of the item [%s]" % url)
        if answered or url:
            # a failed request (site down for a moment) is asked again next time
            self.remember(article['key'], url)
        self.load(url)

    def _stopTimer(self):
        if self.timer is not None:
            self.timer.stop()
        self.timer = None
        self.timer_conn = None

    def close(self):
        self._stopTimer()
        self.article = None
        dialog, self.dialog = self.dialog, None
        if dialog is not None:
            try:
                dialog.hide()
                self.session.deleteDialog(dialog)
            except Exception:
                printExc()
