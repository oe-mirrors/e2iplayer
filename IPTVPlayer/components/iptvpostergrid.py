# -*- coding: utf-8 -*-
#
#  Poster grid for the main list
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.ihost import CDisplayListItem
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVMainNavigatorList, fitPixmapInBox
from Plugins.Extensions.IPTVPlayer.components.cover import PicLoadPara
from Plugins.Extensions.IPTVPlayer.tools.listselection import isMarked
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from enigma import eListboxPythonMultiContent, ePicLoad, eTimer, gFont, getDesktop, BT_SCALE, \
    RT_HALIGN_CENTER, RT_VALIGN_TOP, RT_WRAP
from collections import OrderedDict
import os
import struct
###################################################

# rows that only page through the list: shown as tiles, but they do not count when deciding on the grid
_PAGER_TYPES = (CDisplayListItem.TYPE_NEXT, CDisplayListItem.TYPE_JUMP, CDisplayListItem.TYPE_FIRST,
                CDisplayListItem.TYPE_PREVIOUS, CDisplayListItem.TYPE_LAST, CDisplayListItem.TYPE_MORE)


def _isPagerItem(item):
    return getattr(item, 'type', '') in _PAGER_TYPES or getattr(item, 'imageType', '') in _PAGER_TYPES


def ListHasPosters(items):
    # a list turns into a grid when most of its rows bring their own picture; a menu whose rows all show the
    # same picture (the host's logo) stays a list
    content = [item for item in items if not _isPagerItem(item)]
    urls = {getattr(item, 'iconimage', '') for item in content}
    urls.discard('')
    return 3 <= len(urls) and 2 * len(urls) >= len(content)


def PictureSize(path):
    # (width, height) from the header of a PNG, GIF or JPEG file (what the icon cache holds, WebP / AVIF are
    # converted to JPEG there), None when it is none of them or can't be read
    try:
        with open(path, 'rb') as f:
            head = f.read(65536)
    except Exception:
        return None
    if head[:8] == b'\x89PNG\r\n\x1a\n' and len(head) >= 24:
        return struct.unpack('>II', head[16:24])
    if head[:6] in (b'GIF87a', b'GIF89a') and len(head) >= 10:
        return struct.unpack('<HH', head[6:10])
    if head[:2] != b'\xff\xd8':
        return None
    # JPEG: the size is in the first SOFn segment, after APPn (EXIF ...) segments
    pos = 2
    while pos + 9 <= len(head):
        if head[pos] != 0xFF:
            pos += 1
            continue
        marker = head[pos + 1]
        if marker == 0xFF:
            pos += 1
            continue
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            pos += 2
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack('>HH', head[pos + 5:pos + 9])
            return (width, height) if width and height else None
        pos += 2 + struct.unpack('>H', head[pos + 2:pos + 4])[0]
    return None


def FitSizeInBox(width, height, boxX, boxY, boxW, boxH):
    # like fitPixmapInBox() for a picture of width x height
    scale = min(boxW / float(width), boxH / float(height))
    fitW, fitH = int(width * scale), int(height * scale)
    return boxX + (boxW - fitW) // 2, boxY + (boxH - fitH) // 2, fitW, fitH


class _PosterLoader:
    # decodes the grid's pictures to poster size, one at a time with one ePicLoad; the newest request first
    # (the rows painted last are the ones on screen), the decoded pixmaps in a small LRU cache. onFailed(path):
    # True when the caller has dealt with the file (removed it for a new download), it is then decoded again
    def __init__(self, onDecoded, onFailed):
        self.onDecoded = onDecoded
        self.onFailed = onFailed
        self.picload = ePicLoad()
        self.picload_conn = eConnectCallback(self.picload.PictureData, self._decodeCallBack)
        self.cache = OrderedDict()  # path -> pixmap, None: the picture can't be shown
        self.queue = []
        self.current = None
        self.width = self.height = 0
        self.maxCache = 40
        self.maxQueue = 40

    def setSize(self, width, height, tiles):
        self.maxCache = max(40, 3 * tiles)
        self.maxQueue = max(20, 2 * tiles)
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            self.cache.clear()
            self.queue = []

    def get(self, path):
        # the pixmap of path, None while it is decoded (the decode is started) or when it can't be shown
        if path in self.cache:
            self.cache.move_to_end(path)
            return self.cache[path]
        if path != self.current and path not in self.queue:
            self.queue.append(path)
            if len(self.queue) > self.maxQueue:
                del self.queue[0]
            if self.current is None:
                self._next()
        return None

    def _next(self):
        while self.queue:
            path = self.queue.pop()
            if path in self.cache:
                continue
            if os.path.isfile(path):
                self.picload.setPara(PicLoadPara(self.width, self.height, path))
                if 0 == self.picload.startDecode(path):
                    self.current = path
                    return
            self._failed(path)
        self.current = None

    def _failed(self, path):
        printDBG("PosterGrid: picture can not be decoded [%s]" % path)
        self._store(path, None)
        if self.onFailed(path):
            self.forget(path)

    def forget(self, path):
        self.cache.pop(path, None)

    def _store(self, path, pixmap):
        self.cache[path] = pixmap
        while len(self.cache) > self.maxCache:
            self.cache.popitem(last=False)

    def _decodeCallBack(self, picInfo=None):
        path = self.current
        if path is None:
            return
        pixmap = self.picload.getData()
        if pixmap is None:
            self._failed(path)
        else:
            self._store(path, pixmap)
        self._next()
        self.onDecoded()

    def close(self):
        self.picload_conn = None
        self.queue = []
        self.cache.clear()
        self.current = None


class IPTVPosterGridList(IPTVMainNavigatorList):
    # the main list as a grid of posters (option "Poster grid for lists with pictures"). Every row of the
    # listbox holds the items of one grid row and LEFT/RIGHT pick the column (the screen calls moveRow /
    # moveColumn), so it works with the plain eListbox of every image. Only lists whose rows bring their own
    # pictures become a grid (ListHasPosters), all others stay a normal list. Indexes and getCurrent() are
    # the ones of the items, in both modes. The tiles follow the pictures: portrait posters (2:3, about two
    # rows) or, when most pictures of the list are landscape (video thumbnails), 16:9 tiles in about three rows.
    TILE_COLOR = 0x00202830
    SELECTED_COLOR = 0x001b5a91
    # pictures of a list that decide the tile shape (fewer when the list has fewer)
    SHAPE_VOTES = 4

    def __init__(self):
        IPTVMainNavigatorList.__init__(self)
        self.gridMode = False
        self.posterPath = None  # function(url) -> the picture on disk, '' while it is downloaded
        self.posterFailed = None  # function(url, path) -> True: the file was dropped for a new download
        self.onModeChanged = []
        self.items = []
        # the list could show as grid (the option aside): the screen shows the TEXT key for it
        self.postersInList = False
        self.cols = 1
        self.col = 0
        # the selected row: the listbox's own index walks over the rows while it paints them
        self.selRow = 0
        self.listItemHeight = None
        self.urls = set()  # the pictures of the list
        self.paths = {}  # url -> picture on disk
        self.pending = set()  # urls asked for that are not on disk yet (posterChanged() asks again)
        self.errorPath = ''  # the red X: no vote for the tile shape
        self.sizes = {}  # picture on disk -> (width, height) or None
        # tile shape: the one of the list before until this list's pictures have decided
        self.landscape = False
        self.shapeVotes = {}  # url -> True: landscape picture
        self.shapeDecided = False
        self.relayoutPending = False
        self.loader = None
        self.redrawTimer = None
        self.redrawTimer_conn = None
        screenH = getDesktop(0).size().height()
        self.gridFontSize = max(int(self.font[1] * 0.72), 12)
        self.l.setFont(2, gFont(self.font[0], self.gridFontSize))
        self.pad = max(3, screenH // 240)
        self.gap = 2 * self.pad
        # row height to aim at: posters about two rows, landscape tiles about three
        self.rowHint = screenH * 0.27
        self.rowHintLandscape = screenH * 0.2

    def setPosterSource(self, posterPath, posterFailed=None, errorPath=''):
        # without one (no thumbnails) every list stays a list
        self.posterPath = posterPath
        self.posterFailed = posterFailed
        self.errorPath = errorPath

    def onCreate(self):
        IPTVMainNavigatorList.onCreate(self)
        self.loader = _PosterLoader(self._scheduleRedraw, self._posterNotShown)
        self.redrawTimer = eTimer()
        self.redrawTimer_conn = eConnectCallback(self.redrawTimer.timeout, self._redraw)

    def onDestroy(self):
        if self.redrawTimer is not None:
            self.redrawTimer.stop()
        self.redrawTimer_conn = None
        self.redrawTimer = None
        if self.loader is not None:
            self.loader.close()
            self.loader = None
        IPTVMainNavigatorList.onDestroy(self)

    ###################################################
    # list API in item indexes
    ###################################################
    def setList(self, list):
        items = [entry[0] for entry in list]
        self.postersInList = ListHasPosters(items)
        # the option is read for every list, a change in the settings counts at once
        grid = bool(config.plugins.iptvplayer.poster_grid.value and self.posterPath is not None
                    and self.instance is not None and self.postersInList)
        # the selected item index stays like in a plain list (a reordered list, the switch list <-> grid)
        keepIndex = self.getCurrentIndex() if (grid or self.gridMode) else None
        self.items = items
        # only the pictures of this list are remembered
        urls = {getattr(item, 'iconimage', '') for item in items}
        self.urls = urls
        self.paths = {url: path for url, path in self.paths.items() if url in urls}
        self.pending &= urls
        if len(self.sizes) > 1000:
            self.sizes = {}
        # the same list again (new order, markers) keeps its shape, a new list decides anew
        if not self.shapeDecided or not set(self.shapeVotes) <= urls:
            self.shapeVotes = {}
            self.shapeDecided = False
        self.relayoutPending = False
        if grid != self.gridMode:
            self._setMode(grid)
        if grid:
            self._layout()
            self.l.setList([(row,) for row in range(self._rowCount())])
            self.col = 0
            self.selRow = self.instance.getCurrentIndex()
        else:
            self.l.setList(list)
        if keepIndex is not None and items:
            self.moveToIndex(min(keepIndex, len(items) - 1))

    def _setMode(self, grid):
        printDBG("PosterGrid: %s" % ("grid" if grid else "list"))
        if grid and self.listItemHeight is None:
            self.listItemHeight = self.l.getItemSize().height()
        self.gridMode = grid
        # the grid draws its own highlight on the chosen tile
        self.instance.setSelectionEnable(0 if grid else 1)
        for fnc in self.onModeChanged:
            try:
                fnc(grid)
            except Exception:
                printExc()
        if not grid and self.listItemHeight:
            self.l.setItemHeight(self.listItemHeight)

    def getCurrent(self):
        if not self.gridMode:
            return IPTVMainNavigatorList.getCurrent(self)
        idx = self.getCurrentIndex()
        return self.items[idx] if 0 <= idx < len(self.items) else None

    def getCurrentIndex(self):
        if not self.gridMode:
            return IPTVMainNavigatorList.getCurrentIndex(self)
        return self.instance.getCurrentIndex() * self.cols + self.col

    def moveToIndex(self, index):
        if not self.gridMode:
            return IPTVMainNavigatorList.moveToIndex(self, index)
        if not self.items:
            return
        index = max(0, min(index, len(self.items) - 1))
        self._moveTo(index // self.cols, index % self.cols)

    def selectionChanged(self):
        if self.gridMode:
            # also a move of the listbox itself (its own keys): the highlight follows
            row = self.instance.getCurrentIndex()
            if row != self.selRow:
                self.l.invalidateEntry(self.selRow)
                self.l.invalidateEntry(row)
                self.selRow = row
        IPTVMainNavigatorList.selectionChanged(self)

    def invalidateItem(self, index):
        self.l.invalidateEntry(index // self.cols if self.gridMode else index)

    currentIndex = property(getCurrentIndex, moveToIndex)
    currentSelection = property(getCurrent)

    ###################################################
    # keys in the grid
    ###################################################
    def moveRow(self, step):
        rows = self._rowCount()
        if rows:
            self._moveTo((self.selRow + step) % rows, self.col)

    def moveColumn(self, step):
        if self.items:
            self.moveToIndex((self.getCurrentIndex() + step) % len(self.items))

    def _moveTo(self, row, col):
        oldCol = self.col
        # the last row can be shorter
        self.col = max(0, min(col, len(self.items) - row * self.cols - 1))
        if row != self.selRow:
            # the listbox reports the change itself (selectionChanged redraws both rows)
            self.instance.moveSelectionTo(row)
            if self.selRow != row:
                # no signal: the listbox was on that row already
                self.selectionChanged()
        elif self.col != oldCol:
            self.l.invalidateEntry(row)
            self.selectionChanged()

    ###################################################
    # pictures
    ###################################################
    def posterChanged(self, url):
        # the IconMenager has downloaded (or given up on) url - also one reported as not shown, which the grid
        # no longer has in paths / pending
        if url in self.urls:
            self.pending.discard(url)
            self.paths.pop(url, None)
            self._scheduleRedraw()

    def _posterNotShown(self, path):
        # a file on disk the picture loader can't show (e.g. an empty one left by a broken download): reported
        # like the cover does it, the IconMenager then shows the red X and downloads it again later
        handled = False
        for url in [url for url, urlPath in self.paths.items() if urlPath == path]:
            if self.posterFailed is not None and self.posterFailed(url, path):
                del self.paths[url]
                handled = True
        if handled:
            self._scheduleRedraw()
        return handled

    def _poster(self, item):
        url = getattr(item, 'iconimage', '')
        if not url or self.posterPath is None or self.loader is None:
            return None
        path = self.paths.get(url)
        if path is None:
            if url in self.pending:
                return None
            path = self.posterPath(url)
            if not path:
                self.pending.add(url)
                return None
            self.paths[url] = path
            self._voteShape(url, path)
        return self.loader.get(path)

    def _pictureSize(self, path):
        if path not in self.sizes:
            self.sizes[path] = PictureSize(path)
        return self.sizes[path]

    def _voteShape(self, url, path):
        # the first pictures of a list on disk decide portrait or landscape tiles (square ones and the red X
        # have no say); a change is laid out after the paint (_redraw), never while the listbox paints
        if self.shapeDecided or path == self.errorPath:
            return
        size = self._pictureSize(path)
        if not size or size[0] == size[1]:
            return
        self.shapeVotes[url] = size[0] > size[1]
        urls = {getattr(item, 'iconimage', '') for item in self.items}
        urls.discard('')
        if len(self.shapeVotes) < min(self.SHAPE_VOTES, len(urls)):
            return
        self.shapeDecided = True
        landscape = 2 * sum(self.shapeVotes.values()) > len(self.shapeVotes)
        if landscape != self.landscape:
            printDBG("PosterGrid: %s tiles" % ("landscape" if landscape else "portrait"))
            self.landscape = landscape
            self.relayoutPending = True
            self._scheduleRedraw()

    def _scheduleRedraw(self):
        if self.redrawTimer is not None and self.gridMode:
            self.redrawTimer.start(100, True)

    def _redraw(self):
        try:
            if self.relayoutPending:
                self.relayoutPending = False
                keepIndex = self.getCurrentIndex()
                self._layout()
                self.l.setList([(row,) for row in range(self._rowCount())])
                self.col = 0
                self.selRow = self.instance.getCurrentIndex()
                self.moveToIndex(min(keepIndex, len(self.items) - 1))
            else:
                self.l.invalidate()
        except Exception:
            printExc()

    ###################################################
    # drawing
    ###################################################
    def _rowCount(self):
        return (len(self.items) + self.cols - 1) // self.cols

    def _layout(self):
        size = self.instance.size()
        # a bit of room for the scrollbar, so the columns do not change when it shows up
        width = int(size.width() * 0.97)
        height = size.height()
        rows = max(1, round(height / (self.rowHintLandscape if self.landscape else self.rowHint)))
        self.rowH = height // rows
        self.titleH = int(self.gridFontSize * 2.6)
        self.posterH = max(self.rowH - self.titleH - 3 * self.pad - self.gap, 20)
        self.posterW = self.posterH * 16 // 9 if self.landscape else self.posterH * 2 // 3
        self.cols = max(1, width // (self.posterW + 2 * self.pad + self.gap))
        self.tileW = width // self.cols
        self.l.setItemHeight(self.rowH)
        self.loader.setSize(self.posterW, self.posterH, rows * self.cols)

    def buildEntry(self, item):
        # an entry of the other mode can still be painted while setList() switches
        if not self.gridMode:
            return [None] if isinstance(item, int) else IPTVMainNavigatorList.buildEntry(self, item)
        if not isinstance(item, int):
            return [None]
        row = item
        res = [None]
        currRow = self.selRow
        innerW = self.tileW - self.gap
        innerH = self.rowH - self.gap
        start = row * self.cols
        for col, entry in enumerate(self.items[start:start + self.cols]):
            x = col * self.tileW
            if row == currRow and col == self.col:
                # the highlight: a frame around the poster and the title on its colour
                res.append(self._rect(x, 0, innerW, innerH, self.SELECTED_COLOR))
            posterX = x + (innerW - self.posterW) // 2
            posterY = self.pad
            box = (posterX, posterY, self.posterW, self.posterH)
            pixmap = self._poster(entry)
            if pixmap is not None:
                self._appendPixmap(res, pixmap, fitPixmapInBox(pixmap, *box))
                # the markers go on the picture itself: ePicLoad pads it to the whole box on some images, its
                # own size comes from the file
                size = self._pictureSize(self.paths.get(entry.iconimage, ''))
                if size:
                    box = FitSizeInBox(size[0], size[1], *box)
            else:
                # no picture (yet): a dark tile with the item's type icon
                res.append(self._rect(posterX, posterY, self.posterW, self.posterH, self.TILE_COLOR))
                icon = self.dictPIX.get(entry.imageType, None)
                if icon is not None:
                    iconW = min(self.posterW // 2, self.ICON_W * 2)
                    iconX = posterX + (self.posterW - iconW) // 2
                    iconY = posterY + (self.posterH - iconW) // 2
                    self._appendPixmap(res, icon, fitPixmapInBox(icon, iconX, iconY, iconW, iconW))
            self._appendBadges(res, entry, box)
            color = entry.getTextColor()
            res.append((eListboxPythonMultiContent.TYPE_TEXT, x + self.pad, posterY + self.posterH + self.pad,
                        innerW - 2 * self.pad, self.titleH, 2, RT_HALIGN_CENTER | RT_VALIGN_TOP | RT_WRAP,
                        entry.getDisplayTitle(), color, color))
        return res

    @staticmethod
    def _rect(x, y, w, h, color):
        # a filled box: a text entry without text on its background colour (the framebuffer images draw it; the
        # GLES/EGL backend of the experimental openATV WQHD build does not, to be checked again with openATV 8.1)
        return (eListboxPythonMultiContent.TYPE_TEXT, x, y, w, h, 2, 0, '', None, None, color, color)

    @staticmethod
    def _appendPixmap(res, pixmap, box):
        x, y, w, h = box
        res.append(MultiContentEntryPixmapAlphaBlend(pos=(x, y), size=(w, h), png=pixmap, flags=BT_SCALE))

    def _appendBadges(self, res, entry, box):
        # the list's markers on the poster: favourite / download state top left, selection mark top right,
        # watched / started bottom right
        boxX, boxY, boxW, boxH = box
        # sized by the tile, not by the picture: the same size on every tile of the list (a flat logo of a
        # hostxxx site would get tiny markers)
        size = max(min(self.posterW, self.posterH) // 4, 14)
        x = boxX + 2
        for marker in self._getRowMarkers(entry):
            self._appendPixmap(res, marker, fitPixmapInBox(marker, x, boxY + 2, size, size))
            x += size + 2
        # the corner badges paint only a corner of their canvas (CheckBadge.png the top right 22 of 32 px,
        # Watched/StartedBadge.png the bottom right 17): the canvas grows so that corner is as big as the markers
        if self.selectMarkerPIX is not None and isMarked(entry):
            canvas = size * 32 // 22
            self._appendPixmap(res, self.selectMarkerPIX, (boxX + boxW - canvas - 2, boxY + 2, canvas, canvas))
        badge = None
        if getattr(entry, 'isWatched', False):
            badge = self.watchedBadgePIX
        elif getattr(entry, 'isStarted', False):
            badge = self.startedBadgePIX
        if badge is not None:
            canvas = size * 32 // 17
            self._appendPixmap(res, badge, (boxX + boxW - canvas - 2, boxY + boxH - canvas - 2, canvas, canvas))
