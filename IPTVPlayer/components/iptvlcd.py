# -*- coding: utf-8 -*-
#
# IPTVLcd -- all LCD / VFD summary screens of E2iPlayer: the colour summary of the external player, the buffering
# screen and the download manager, the small summary of the player, the summary of the main list, the screen title
# with the marked row and a picture for choice boxes, the article view, the favourites, the search history, the
# search result grid and the picture viewer (IPTVPlayerInfoLCDScreen), and which screen of the image the internal
# player (InfoBarMoviePlayerSummary) and the settings (SetupSummary) get
#
# Layouts: small 16:9 picture or a column beside the title, a large picture with the title below ("poster") or
# with up to four rows of information on the right ("side"); rolling titles stop after a set number of runs; the
# picture is fitted to its field (Pillow, in a worker thread); colours of the progress bar; margins per display
# size (LCD_MARGINS). lcdGeometry() and infoLcdGeometry() are plain arithmetic and can be tested on a PC.
#
# $Id$

from Plugins.Extensions.IPTVPlayer.components.cover import Cover
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, eConnectCallback, StripColorCodes, GetTmpDir, mkdirs
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from enigma import getDesktop, eTimer, eLabel, gFont, ePoint, eSize
from Screens.Screen import Screen
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from Components.config import config
from Components.Sources.StaticText import StaticText
from Components.Sources.Progress import Progress
import time
from datetime import timedelta
from hashlib import md5
from os import path as os_path, listdir as os_listdir, remove as os_remove, rename as os_rename

# smallest display for the layout below; mono LCDs/OLEDs (132x64 etc.) and text VFDs are smaller, the check knows the size only
LARGE_LCD_MIN_WIDTH = 220
LARGE_LCD_MIN_HEIGHT = 176

# ---------------------------------------------------------------------------------------------------------------
# Things that are meant to be changed per receiver / display. Nothing here is needed for the automatic layout
# (the size comes from getDesktop(1)); the values below only override it.
# ---------------------------------------------------------------------------------------------------------------
# font of all texts of the layout; "Regular" exists in every image, a skin font such as "VFD" or "RegularLCD" can be used too
LCD_FONT = 'Regular'
# progress bar: the colour of the fill and of the frame come from the settings lcd_bar_color and lcd_bar_frame; the
# values below are used when a setting does not exist (older setup file). The frame gets thicker with the display
# height (1 px up to 3 px)
LCD_BAR_FILL = '#ff0000'
LCD_BAR_BACK = '#000000'
LCD_BAR_BORDER = '#ffffff'
LCD_BAR_COLORS = {'red': '#ff0000', 'green': '#00c000', 'blue': '#2a6bff', 'yellow': '#ffd800', 'orange': '#ff8000',
                  'cyan': '#00d0ff', 'magenta': '#ff40ff', 'white': '#ffffff'}
LCD_BAR_FRAMES = {'white': '#ffffff', 'grey': '#a0a0a0'}   # 'same' = the colour of the fill, 'none' = no frame
# border that the housing of a receiver hides, per display size: {(width, height): (left, right, top, bottom)}
# example: {(800, 480): (20, 20, 10, 10)}; sizes that are not listed use IPTVExtMoviePlayerColorSummary.LCD_MARGIN_*
LCD_MARGINS = {}
# how many times a title that is too long rolls through when the setting "lcd_title_runs" does not exist
# (0 = endless); after the last run the title stands still. LCD_TITLE_REST_MS: how long a rolling title stands at its
# beginning (readable) before it rolls again (the Ultimo4K skin uses 20000 to 60000)
LCD_TITLE_RUNS_DEFAULT = 2
LCD_TITLE_REST_MS = 8000
# The picture is prepared before it is shown (lcdPrepareCover): a uniform border (the black bars of YouTube's
# hqdefault.jpg) is cut, and the picture is made to fit the cover field (setting lcd_cover_fit). Needs PIL
# (Pillow); without it the picture is shown as it is.
# lcd_cover_fit = auto: a picture that needs a cut of at most this part of itself to fill the field is cut (a 3:2 photo in
# a 16:9 field loses 16 %), a taller one (4:3, portrait) is shown whole over a blurred copy of itself
LCD_COVER_MAX_CROP = 0.16
# width of the picture beside the title in per cent of the usable width: 'small' = a 16:9 picture of this width,
# 'column' = a column of this width over the whole height of the title area (the picture is fitted into it)
LCD_COVER_SMALL_PERCENT = 30
LCD_COVER_COLUMN_PERCENT = 45
# 'poster': the picture gets everything the other rows leave over. The gaps are half as large as in the other layouts,
# the rows are one font line high (LCD_POSTER_LINE_EM em), the bar is thin (a 1/LCD_POSTER_BAR_DIV of the height, frame
# at most 2 px). The size of the times below the bar (per cent of their size in the other layouts) and of the single
# title line below the picture (per cent of the title size of the other layouts) come from the settings lcd_poster_time
# and lcd_poster_title; these are the values when a setting does not exist. The bigger the texts, the smaller the picture.
LCD_POSTER_TIME_DEFAULT = 70
LCD_POSTER_TITLE_DEFAULT = 100
LCD_POSTER_LINE_EM = 1.25
LCD_POSTER_BAR_DIV = 28
# the single title line below the picture sits this much lower in its line (part of the line height): the letters are in
# the upper part of a line of text, so the text looks centred between the picture and the bar
LCD_POSTER_TEXT_SHIFT = 0.07
# 'side' (picture left as large as possible, information on the right, like the EMC screen of the Ultimo4K skin): the
# column on the right keeps at least this part of the usable width; the rows in it come from the settings
# lcd_side_row1 .. lcd_side_row4 (these are the rows when a setting does not exist)
LCD_SIDE_MIN_RIGHT_PERCENT = 28
LCD_SIDE_ROWS_DEFAULT = ('clock', 'end', 'remaining', 'percent')


# the scrolling title needs the RunningText renderer of the image: "RunningText" (openATV, openPLi, ...) or
# "VRunningText" (VTi); the skin of the layout uses the name that exists
RUNNING_TEXT_RENDERER = None
for _lcdRendererName in ('RunningText', 'VRunningText'):
    try:
        __import__('Components.Renderer.%s' % _lcdRendererName)
        RUNNING_TEXT_RENDERER = _lcdRendererName
        break
    except Exception:
        pass
HAVE_RUNNING_TEXT = RUNNING_TEXT_RENDERER is not None


def lcdSetting(name, default):
    # a setting of the external player setup; a missing one (older setup file) gives the default
    try:
        return getattr(config.plugins.iptvplayer, name).value
    except Exception:
        return default


def lcdPercentSetting(name, default):
    # a setting that holds a number in per cent ("70"); a missing or wrong one gives the default
    try:
        return max(10, min(300, int(lcdSetting(name, default))))
    except Exception:
        return default


def lcdXml(text):
    # text for an XML attribute
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def lcdSideItem(kind, shortTimes):
    # what a row of the layout "side" shows: (label, source, converter or None, characters of the value) or None.
    # 'clock', 'date': the clock of the receiver; 'end': the time when the film ends (computed by the summary screen from
    # position and length); the others are the sources of the player: parent.lcd*
    if kind == 'clock':
        return (_('Time').upper(), 'global.CurrentTime', 'Format:%H:%M', 5)
    if kind == 'date':
        return (_('Date').upper(), 'global.CurrentTime', 'Format:%a %d.%m.', 9)
    if kind == 'end':
        return (_('ENDS'), 'lcdEndTime', None, 5)
    if kind == 'remaining':
        return (_('REMAINING'), 'parent.lcdRemainedShort' if shortTimes else 'parent.lcdRemained', None, 8 if shortTimes else 9)
    if kind == 'elapsed':
        return (_('PLAYED'), 'parent.lcdCurrTimeHM' if shortTimes else 'parent.lcdCurrTime', None, 7 if shortTimes else 9)
    if kind == 'length':
        return (_('LENGTH'), 'parent.lcdLengthHM' if shortTimes else 'parent.lcdLength', None, 7 if shortTimes else 9)
    if kind == 'percent':
        return (_('DONE'), 'parent.lcdPercent', None, 4)
    return None


def lcdBorderBox(img):
    # the picture without a uniform border (letterbox / pillarbox): (left, top, right, bottom). Black borders are cut
    # always (YouTube's hqdefault.jpg has a black bar above and below the 16:9 picture); a border of another colour only
    # when it is there on BOTH opposite sides (a flat sky or a studio background is not a border). A side never loses
    # more than 20 %.
    from PIL import Image, ImageChops
    w, h = img.size
    background = img.getpixel((0, 0))
    corners = [img.getpixel((w - 1, 0)), img.getpixel((0, h - 1)), img.getpixel((w - 1, h - 1))]
    if sum(1 for cc in corners if max(abs(cc[i] - background[i]) for i in range(3)) <= 24) < 2:
        return (0, 0, w, h)
    diff = ImageChops.difference(img, Image.new('RGB', img.size, background)).convert('L').point(lambda p: 255 if p > 24 else 0)
    box = diff.getbbox()
    if not box:
        return (0, 0, w, h)
    left, top, right, bottom = box
    black = max(background) <= 40
    sideX = (left, w - right)
    sideY = (top, h - bottom)
    cut = [0, 0, 0, 0]
    if sideX[0] >= w * 0.04 or sideX[1] >= w * 0.04:
        if black or (sideX[0] >= w * 0.04 and sideX[1] >= w * 0.04 and max(sideX) <= 2 * min(sideX)):
            cut[0], cut[2] = left, w - right
    if sideY[0] >= h * 0.04 or sideY[1] >= h * 0.04:
        if black or (sideY[0] >= h * 0.04 and sideY[1] >= h * 0.04 and max(sideY) <= 2 * min(sideY)):
            cut[1], cut[3] = top, h - bottom
    if cut[0] > w * 0.2 or cut[2] > w * 0.2 or cut[1] > h * 0.2 or cut[3] > h * 0.2:
        return (0, 0, w, h)
    return (cut[0], cut[1], w - cut[2], h - cut[3])


# prepared pictures are copies in the temporary folder (never next to the original: the download manager's picture lies
# next to the film); only the newest LCD_PREPARED_KEEP stay
LCD_PREPARED_DIR = 'lcd_cover'
LCD_PREPARED_KEEP = 20


def lcdIsLogo(img):
    # a picture with transparency is a logo (a host or channel logo), not a photo: it is shown as it is
    if img.mode in ('RGBA', 'LA', 'PA'):
        try:
            return img.getchannel('A').getextrema()[0] < 255
        except Exception:
            return True
    return img.mode == 'P' and 'transparency' in img.info


def lcdPreparedPath(path, width, height, mode):
    # the name holds the size and the time of the source: a picture written anew under the same name (the picture
    # viewer always uses one file) gets a new copy, also where the file system keeps the time in 2 s steps (FAT)
    name = md5(('%s|%d|%d' % (path, os_path.getsize(path), int(os_path.getmtime(path) * 1000))).encode('utf-8')).hexdigest()
    folder = GetTmpDir(LCD_PREPARED_DIR)
    if not os_path.isdir(folder):
        mkdirs(folder)
    return os_path.join(folder, '%s_%dx%d_%s.jpg' % (name, width, height, mode))


def lcdTrimPrepared(keep):
    # the oldest prepared pictures go, the one just made (keep) stays; a file another worker removed already is skipped
    try:
        folder = os_path.dirname(keep)
        files = [os_path.join(folder, item) for item in os_listdir(folder) if item.endswith('.jpg')]
        if len(files) <= LCD_PREPARED_KEEP:
            return
        files.sort(key=lambda item: os_path.getmtime(item) if os_path.isfile(item) else 0)
        for item in files[:len(files) - LCD_PREPARED_KEEP]:
            if item != keep and os_path.isfile(item):
                os_remove(item)
    except Exception:
        printExc()


def lcdSavePrepared(img, prepared):
    # written under a temporary name first: a second worker for the same picture, or the decoder, never reads a
    # half-written file
    temp = '%s.%d.tmp' % (prepared, id(img))
    img.save(temp, 'JPEG', quality=92)
    os_rename(temp, prepared)
    lcdTrimPrepared(prepared)


def lcdCoverFitMode():
    mode = lcdSetting('lcd_cover_fit', 'auto')
    return mode if mode in ('auto', 'crop', 'fit') else 'auto'


def lcdPrepareCover(path, width, height, mode=None):
    # The picture for the cover field of width x height pixels, as a copy in the temporary folder, or the original path.
    # mode (setting lcd_cover_fit, read in the main thread when this runs in a worker, see lcdDecodeCover):
    #   auto = cut a uniform border, then fill the field (cut the picture to its shape) when that takes at most
    #          LCD_COVER_MAX_CROP of the picture, otherwise show the whole picture over a blurred, darkened copy of itself
    #   crop = always fill the field        fit = only the border is cut, the picture is shown whole (black bars)
    # auto and crop make the picture exactly as large as the field, so the scaling of the image does not have to do
    # it; fit keeps the size of the cut picture. A logo (picture with transparency) is shown as it is.
    mode = mode or lcdCoverFitMode()
    try:
        if width < 32 or height < 32:
            return path
        prepared = lcdPreparedPath(path, width, height, mode)
        if os_path.isfile(prepared) and os_path.getsize(prepared) > 0:
            return prepared
        from PIL import Image
        resample = Image.LANCZOS
        img = Image.open(path)
        if lcdIsLogo(img):
            printDBG("IPTVLcd.lcdPrepareCover logo with transparency, shown as it is [%s]" % path)
            return path
        # a JPEG is decoded at a reduced size right away (much faster on the receiver), still at least twice the field
        try:
            img.draft('RGB', (width * 2, height * 2))
        except Exception:
            pass
        img.load()
        img = img.convert('RGB')
        w, h = img.size
        if w < 64 or h < 64:
            return path
        box = lcdBorderBox(img)
        if box != (0, 0, w, h):
            img = img.crop(box)
            w, h = img.size
        elif mode == 'fit':
            return path   # nothing to cut and the picture is shown whole anyway
        if mode == 'fit':
            lcdSavePrepared(img, prepared)
            return prepared
        fieldRatio = width / float(height)
        ratio = w / float(h)
        loss = 1.0 - min(ratio, fieldRatio) / max(ratio, fieldRatio)   # the part of the picture a cut to the field takes
        if mode == 'crop' or loss <= LCD_COVER_MAX_CROP:
            if ratio > fieldRatio:
                newW = int(h * fieldRatio)
                left = (w - newW) // 2
                img = img.crop((left, 0, left + newW, h))
            else:
                newH = int(w / fieldRatio)
                top = (h - newH) // 2
                img = img.crop((0, top, w, top + newH))
            img = img.resize((width, height), resample)
        else:
            scale = max(width / float(w), height / float(h))
            bgW, bgH = int(w * scale) + 1, int(h * scale) + 1
            background = img.resize((max(2, bgW // 10), max(2, bgH // 10)), Image.BILINEAR).resize((bgW, bgH), Image.BICUBIC)
            left, top = (bgW - width) // 2, (bgH - height) // 2
            background = background.crop((left, top, left + width, top + height))
            try:
                from PIL import ImageEnhance
                background = ImageEnhance.Brightness(background).enhance(0.55)
            except Exception:
                pass
            scale = min(width / float(w), height / float(h))
            front = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), resample)
            background.paste(front, ((width - front.size[0]) // 2, (height - front.size[1]) // 2))
            img = background
        lcdSavePrepared(img, prepared)
        printDBG("IPTVLcd.lcdPrepareCover [%s] %dx%d mode[%s] loss[%.2f] -> %dx%d" % (path, w, h, mode, loss, width, height))
        return prepared
    except Exception:
        printExc()
        return path


def lcdDecodeCover(cover, path, callBackFun, ident):
    # the picture fitted to the Cover widget (lcdPrepareCover) in a worker thread - Pillow takes a moment for a large
    # picture and the GUI must not stand still meanwhile -, then decoded; callBackFun gets what Cover.decodeCover
    # gives. The picture is decoded even when the widget had the same file before (it was hidden in the meantime,
    # or a new picture of the same size and time).
    size = cover.instance.size()
    cover.decodeCoverMadeBy(lcdPrepareCover, (path, size.width(), size.height(), lcdCoverFitMode()), callBackFun, ident)


def lcdBarColors():
    # (fill, frame, frame width factor) of the progress bar from the settings lcd_bar_color and lcd_bar_frame
    fill = LCD_BAR_COLORS.get(lcdSetting('lcd_bar_color', ''), LCD_BAR_FILL)
    frame = lcdSetting('lcd_bar_frame', 'white')
    if frame == 'none':
        return fill, LCD_BAR_BORDER, 0
    if frame == 'same':
        return fill, fill, 1
    return fill, LCD_BAR_FRAMES.get(frame, LCD_BAR_BORDER), 1


def lcdDisplaySize(default):
    # (width, height) of the front display; default without one (or outside enigma2)
    try:
        size = getDesktop(1).size()
        return size.width(), size.height()
    except Exception:
        return default


def isLargeLcd():
    width, height = lcdDisplaySize((0, 0))
    return width >= LARGE_LCD_MIN_WIDTH and height >= LARGE_LCD_MIN_HEIGHT


def lcdTimeHM(seconds):
    return str(timedelta(seconds=seconds))[:-3]


def addLcdSources(screen, title, currTime="", remained="", length="", percent="", currTimeHM="", remainedHM="", lengthHM="", remainedMin="", remainedShort="", shortTimes=False, coverFile=None):
    # what IPTVExtMoviePlayerColorSummary reads from its parent as parent.lcd*
    screen['lcdTitle'] = StaticText(StripColorCodes(title))
    # the second parameter is named range or valuerange, depending on the image
    screen['lcdProgress'] = Progress(0, 100)
    screen['lcdCurrTime'] = StaticText(currTime)
    screen['lcdRemained'] = StaticText(remained)
    screen['lcdLength'] = StaticText(length)
    screen['lcdPercent'] = StaticText(percent)
    # only for LCD skins, filled by the player: the buffering screen and the download manager have no such times
    screen['lcdCurrTimeHM'] = StaticText(currTimeHM)
    screen['lcdRemainedHM'] = StaticText(remainedHM)
    screen['lcdLengthHM'] = StaticText(lengthHM)
    screen['lcdRemainedMin'] = StaticText(remainedMin)
    # the compact right column (+73 min); shortTimes = the screen fills the HM sources, the layout then uses them
    screen['lcdRemainedShort'] = StaticText(remainedShort)
    screen.lcdShortTimes = shortTimes
    screen.lcdCoverFile = coverFile or ''


def colorSummaryIfWanted():
    # createSummary() of the screens that have nothing to show on a small display
    if config.plugins.iptvplayer.extplayer_summary.value != 'no' and isLargeLcd():
        return IPTVExtMoviePlayerColorSummary
    return None


def runningTextLabel(renderer):
    # the eLabel inside a RunningText renderer: "textLabel" in current openATV, "scroll_label" in older images; None for
    # any other renderer
    return getattr(renderer, 'textLabel', None) or getattr(renderer, 'scroll_label', None)


def lcdSetTitle(screen, text):
    # the title of the colour LCD summary: the source and the summary's font fit (and the pages of a long title)
    screen['lcdTitle'].setText(text)
    for summary in getattr(screen, 'summaries', []):
        # the download manager sets the title with every state change (about once a second): a title that is fitted
        # already stays, or the paging and the scrolling would start over each time
        if hasattr(summary, 'fitLcdTitle') and getattr(summary, 'lcdFittedText', None) != text:
            summary.lcdFittedText = text
            summary.fitLcdTitle(text)


class IPTVExtMoviePlayerColorSummary(Screen):
    # Colour front display during playback: title, progress bar, played time | percent | remaining time.
    # The layout scales with the display size (220x176 up to 800x480 and more) and the setting "LCD font size":
    # the times are as large as the width allows (the player shows 1:46 | +73 min, the buffering screen and the
    # download manager their position / size / speed), the title is fitted to its area, a title that does not fit
    # even then is shown page by page (setting "Long titles on the LCD").
    # The buffering screen and the download manager use it too, with sources of the same names (addLcdSources).
    # Can be replaced in the LCD skin with <screen name="IPTVExtMoviePlayerColorSummary"> using the
    # sources parent.lcdTitle, parent.lcdProgress (0-100, render="Progress"), parent.lcdCurrTime,
    # parent.lcdRemained, parent.lcdLength and parent.lcdPercent. For times without seconds also
    # parent.lcdCurrTimeHM, parent.lcdRemainedHM and parent.lcdLengthHM (1:46), for the remaining minutes
    # parent.lcdRemainedMin (106, in the last minute +45s), both without the minus of parent.lcdRemained,
    # and parent.lcdRemainedShort (+73 min, +45s) for a compact right column.
    # The cover is a widget of this screen, not a source: <widget name="lcdCover" position="..." size="..." alphatest="blend" />
    # The layout below shows it itself from 320 px width (setting "Cover on the LCD"): the picture
    # of the list row (player, buffering) or the download's sidecar .jpg / cached sidecar picture (download
    # manager): the layouts of the setting "Cover size" (see lcdGeometry);
    # without a picture the title has the whole width as before.

    # free border in pixels, e.g. when the receiver housing covers the display edge
    LCD_MARGIN_LEFT = 10
    LCD_MARGIN_RIGHT = 10
    LCD_MARGIN_TOP = 0
    LCD_MARGIN_BOTTOM = 10
    LCD_COVER_MIN_WIDTH = 320
    # average width of a character of the font in em (the layout must not clip a time) and the height of a line
    CHAR_EM = 0.56
    LINE_EM = 1.35  # measured on the Uno 4K SE LCD: the font's line is about 1.33 em high
    PAGE_MS = 3000

    w, h = lcdDisplaySize((LARGE_LCD_MIN_WIDTH, LARGE_LCD_MIN_HEIGHT))

    def __init__(self, session, parent):
        Screen.__init__(self, session, parent=parent)
        self['lcdCover'] = Cover()
        self.lcdParent = parent
        self.lcdCoverFile = ''
        self.lcdCoverShown = None  # the title was not placed yet
        self.titleRuns = LCD_TITLE_RUNS_DEFAULT
        self.sideMode = False
        self.lcdTitleRenderer = None
        self.lcdPages = []
        self.lcdPageIdx = 0
        self.lcdPageTimer = eTimer()
        self.lcdPageTimer_conn = eConnectCallback(self.lcdPageTimer.timeout, self.nextLcdPage)
        self.onClose.append(self.lcdPageTimer.stop)
        self.computeLayout(bool(getattr(parent, 'lcdShortTimes', False)))
        # the row ENDS of the layout "side": own source, refreshed every second while that layout is shown
        self['lcdEndTime'] = StaticText('')
        self.lcdEndTimeText = None
        self.lcdEndTimer = eTimer()
        self.lcdEndTimer_conn = eConnectCallback(self.lcdEndTimer.timeout, self.updateLcdEndTime)
        self.onClose.append(self.lcdEndTimer.stop)
        if self.sideMode:
            self.updateLcdEndTime()
            self.lcdEndTimer.start(1000, False)
        self.skin = self.skinCover if self.coverWanted() else self.skinPlain
        self.onLayoutFinish.append(self.showLcdCover)

    @classmethod
    def snapLines(cls, rect, font):
        # a rolling title shows whole lines only: the height of the rectangle is a multiple of the line height (so no
        # line is cut off at the top or at the bottom, and the first line is complete when the title starts) and the
        # rectangle is centred in the free area
        x, y, w, h = rect
        lineH = font * cls.LINE_EM
        lines = max(1, int(h / lineH))
        newH = min(h, int(lines * lineH + 0.999))
        return (x, y + (h - newH) // 2, w, newH)

    @classmethod
    def lcdGeometry(cls, w, h, mode='large', coverMode='small', shortTimes=False, margins=None, timePct=None, titlePct=None):
        # Pure arithmetic (no enigma2 needed, so it can be tested on a PC): every rectangle of the layout for a display
        # of w x h pixels. Returns a dict; rectangles are (x, y, width, height). timePct / titlePct: size of the times and
        # of the title line of the layouts "poster" and "side" in per cent (settings lcd_poster_time / lcd_poster_title)
        ml, mr, mt, mb = margins or (cls.LCD_MARGIN_LEFT, cls.LCD_MARGIN_RIGHT, cls.LCD_MARGIN_TOP, cls.LCD_MARGIN_BOTTOM)
        timePct = timePct or LCD_POSTER_TIME_DEFAULT
        titlePct = titlePct or LCD_POSTER_TITLE_DEFAULT
        percentColumn = mode == 'normal'
        titleFactor = {'normal': 100, 'large': 115, 'xlarge': 130}.get(mode, 115)
        barDiv = {'normal': 12, 'large': 14, 'xlarge': 16}.get(mode, 14)
        charEm = 0.5 if mode == 'xlarge' else cls.CHAR_EM
        x0 = ml
        y0 = mt
        uw = w - ml - mr   # usable width
        uh = h - mt - mb   # usable height
        pad = max(4, uw // 60)
        cw = uw - 2 * pad
        # times: the left and the right column hold at most 8 characters (+106 min), the downloader's speed 9 (999.9KB/s);
        # the percent column (setting "normal") 4, without it the bar shows the progress and the times get the width
        chars = 8 if shortTimes else 9
        denom = (2 * chars + (4 if percentColumn else 0)) * charEm + 0.2
        fTime = max(12, min(int(cw / denom), uh // (6 if percentColumn else 5)))
        # poster / side: thin bar, small gaps, rows one font line high; the times (poster) have the size of the setting
        wide = w >= cls.LCD_COVER_MIN_WIDTH
        side = coverMode == 'side' and wide
        poster = (coverMode == 'poster' or side) and wide
        if poster and not side:
            fTime = max(12, fTime * timePct // 100)
        gap = max(2, pad // 2) if poster else pad
        if percentColumn:
            midW = int(4 * charEm * fTime) + pad
            colW = (cw - midW) // 2
        else:
            colW = cw // 2
            midW = 0
        barH = max(6, uh // (LCD_POSTER_BAR_DIV if poster else barDiv))
        if side:
            # nothing below the bar: the times are in the column on the right
            timeH = 0
            timeY = y0 + uh
            barY = timeY - barH
        else:
            timeH = (int(fTime * LCD_POSTER_LINE_EM) + 2) if poster else fTime + fTime // 3
            timeY = y0 + uh - timeH
            barY = timeY - gap - barH
        titleY = y0 + gap
        titleH = barY - gap - titleY
        barBorder = max(1, uh // 120)
        if poster:
            barBorder = min(2, barBorder)
        # the title starts as large as the area allows and is fitted to the text (fitLcdTitle); the smallest readable
        # size is the former fixed one
        fTitleMin = min(max(14, uh // 8) * titleFactor // 100, titleH)
        fTitle = min(max(14, uh // 5) * titleFactor // 100, titleH)
        rectFull = cls.snapLines((x0 + pad, titleY, cw, titleH), fTitleMin)
        sideRect = None
        # with a cover: "small" = a 16:9 picture (LCD_COVER_SMALL_PERCENT of the width) beside the title; "column" = a
        # column (LCD_COVER_COLUMN_PERCENT of the width, the whole height of the title area) beside the title;
        # "poster" = a 16:9 picture as large as everything else leaves room for, and ONE line of title right below it;
        # "side" = the same on the left, a column with information on the right
        fTitleMinBeside = fTitleMin
        cover = None
        if poster:
            fLine = max(12, fTitleMin * titlePct // 100)
            fTitleMinBeside = fLine
            lineH = int(fLine * LCD_POSTER_LINE_EM) + 2
            if side:
                areaH = titleH
                picH = areaH - gap - lineH
                picW = picH * 16 // 9
                maxLeftW = cw - cw * LCD_SIDE_MIN_RIGHT_PERCENT // 100 - pad
                if picW > maxLeftW:
                    picW = maxLeftW
                    picH = picW * 9 // 16
                if picH >= 20:
                    # the picture at the top, the title line centred in the space between the picture and the bar
                    # (when the picture is limited by the width this space is larger than the line plus a gap)
                    picBottom = titleY + picH
                    lineY = picBottom + max(gap, (barY - picBottom - lineH) // 2)
                    # the letters sit in the upper part of their line: a little lower looks centred
                    lineY = min(lineY + int(lineH * LCD_POSTER_TEXT_SHIFT), barY - lineH - 1)
                    cover = {'cover': (x0 + pad, titleY, picW, picH),
                             'beside': (x0 + pad, lineY, picW, lineH), 'align': 'center', 'fCover': fTitle}
                    sideRect = (x0 + pad + picW + pad, titleY, cw - picW - pad, areaH)
                    rectFull = cls.snapLines((x0 + pad, titleY, picW, areaH), fTitleMin)
                else:
                    return cls.lcdGeometry(w, h, mode, 'poster', shortTimes, margins, timePct, titlePct)
            else:
                coverH = titleH - gap - lineH
                coverW = coverH * 16 // 9
                if coverW > cw:
                    coverW = cw
                    coverH = coverW * 9 // 16
                if coverH >= 20:
                    belowY = titleY + coverH + gap
                    # the letters sit in the upper part of their line: a little lower looks centred (at most the gap)
                    shiftY = min(int(lineH * LCD_POSTER_TEXT_SHIFT), gap)
                    cover = {'cover': (x0 + pad + (cw - coverW) // 2, titleY, coverW, coverH),
                             'beside': (x0 + pad, belowY + shiftY, cw, titleY + titleH - belowY), 'align': 'center', 'fCover': fTitle}
            if cover is None:
                fTitleMinBeside = fTitleMin
        if cover is None and coverMode == 'column':
            coverW = cw * LCD_COVER_COLUMN_PERCENT // 100
            cover = {'cover': (x0 + pad, titleY, coverW, titleH),
                     'beside': cls.snapLines((x0 + pad + coverW + pad, titleY, cw - coverW - pad, titleH), fTitleMin),
                     'align': 'left', 'fCover': max(14, fTitle * 6 // 7)}
        if cover is None:
            coverH = titleH
            coverW = coverH * 16 // 9
            maxW = cw * LCD_COVER_SMALL_PERCENT // 100
            if coverW > maxW:
                coverW = maxW
                coverH = coverW * 9 // 16
            coverY = titleY + (titleH - coverH) // 2
            cover = {'cover': (x0 + pad, coverY, coverW, coverH),
                     'beside': cls.snapLines((x0 + pad + coverW + pad, titleY, cw - coverW - pad, titleH), fTitleMin),
                     'align': 'left', 'fCover': fTitle}
        return {'w': w, 'h': h, 'x0': x0, 'y0': y0, 'uw': uw, 'uh': uh, 'pad': pad, 'gap': gap, 'cw': cw, 'percentColumn': percentColumn,
                'fTime': fTime, 'colW': colW, 'midW': midW, 'barY': barY, 'barH': barH, 'barBorder': barBorder,
                'timeY': timeY, 'timeH': timeH, 'titleY': titleY, 'titleH': titleH, 'fTitleMin': fTitleMin, 'fTitle': fTitle,
                'rectFull': rectFull, 'coverRect': cover['cover'], 'rectBeside': cover['beside'], 'side': side and sideRect is not None,
                'sideRect': sideRect, 'besideAlign': cover['align'], 'besideOneLine': cover['align'] == 'center',
                'fTitleCover': cover['fCover'], 'fTitleMinBeside': fTitleMinBeside}

    def sideRows(self):
        # the rows of the column on the right of the layout "side" from the settings lcd_side_row1 .. 4
        rows = []
        for idx in range(4):
            kind = lcdSetting('lcd_side_row%d' % (idx + 1), LCD_SIDE_ROWS_DEFAULT[idx])
            if kind and kind != 'none' and lcdSideItem(kind, True) is not None:
                rows.append(kind)
        return rows or ['clock']

    def sideRowsXml(self, L, rows, shortTimes):
        # label (small, grey) above the value (large, white) for every row of the column on the right
        x, y, w, h = L['sideRect']
        rowH = h // len(rows)
        parts = []
        for idx, kind in enumerate(rows):
            label, source, converter, chars = lcdSideItem(kind, shortTimes)
            ry = y + idx * rowH
            labelH = max(10, rowH // 4)
            valueH = rowH - labelH
            valueFont = max(12, min(int(valueH / LCD_POSTER_LINE_EM), int(w / (chars * self.CHAR_EM))))
            # the label fits the width of the column too (REMAINING / VERBLEIBEND) and stays smaller than the value
            labelFont = max(10, min(int(labelH / self.LINE_EM), int(w / (max(1, len(label)) * self.CHAR_EM)), valueFont * 2 // 3))
            parts.append('<eLabel text="%s" position="%d,%d" size="%d,%d" font="%s;%d" halign="center" valign="bottom" noWrap="1" foregroundColor="#a0a0a0" backgroundColor="#000000" transparent="1" />' % (
                lcdXml(label), x, ry, w, labelH, LCD_FONT, labelFont))
            widget = '<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="%s;%d" halign="center" valign="top" noWrap="1" foregroundColor="#ffffff" backgroundColor="#000000" transparent="1"' % (
                source, x, ry + labelH, w, valueH, LCD_FONT, valueFont)
            if converter:
                widget += '><convert type="ClockToText">%s</convert></widget>' % lcdXml(converter)
            else:
                widget += ' />'
            parts.append(widget)
        return '\n            '.join(parts)

    def lineTooLong(self, rect, font, text=None):
        # estimate: does the title not fit into ONE line of this width? (then it rolls; the beginning must stay at the left
        # edge, centred text would lose its beginning). A little margin because the width of the characters is an average.
        if text is None:
            text = self.currentLcdTitle()
        return len((text or '').strip()) * font * self.CHAR_EM * 1.15 > rect[2]

    def computeLayout(self, shortTimes):
        mode = lcdSetting('lcd_font_size', 'large')
        # without a cover the layouts "poster" / "side" would only narrow the title (the setup hides their rows then)
        coverMode = lcdSetting('lcd_cover_size', 'small') if self.coverWanted() else 'small'
        if coverMode == 'side' and not hasattr(getattr(self, 'lcdParent', None), 'playback'):
            coverMode = 'poster'   # the buffering screen and the download manager have no playing time to show
        longTitles = lcdSetting('lcd_long_titles', 'scroll')
        # the player's seconds (1:46:12 | -0:12:03) are the generic sources, the minutes the compact ones
        shortTimes = shortTimes and lcdSetting('lcd_time_format', 'minutes') != 'seconds'
        try:
            self.titleRuns = max(0, int(lcdSetting('lcd_title_runs', LCD_TITLE_RUNS_DEFAULT)))
        except Exception:
            self.titleRuns = LCD_TITLE_RUNS_DEFAULT
        timePct = lcdPercentSetting('lcd_poster_time', LCD_POSTER_TIME_DEFAULT)
        titlePct = lcdPercentSetting('lcd_poster_title', LCD_POSTER_TITLE_DEFAULT)
        # long titles: scrolling (RunningText), page by page (own timer) or smaller text; no RunningText = pages
        self.titleScroll = longTitles == 'scroll' and HAVE_RUNNING_TEXT
        self.titlePages = longTitles == 'pages' or (longTitles == 'scroll' and not HAVE_RUNNING_TEXT)
        L = self.lcdGeometry(self.w, self.h, mode, coverMode, shortTimes, LCD_MARGINS.get((self.w, self.h)), timePct, titlePct)
        self.sideMode = L['side']
        self.fTitleMin, self.fTitle, self.fTitleCover, self.fTitleMinBeside = L['fTitleMin'], L['fTitle'], L['fTitleCover'], L['fTitleMinBeside']
        self.rectFull, self.rectBeside, self.besideAlign, self.besideOneLine = L['rectFull'], L['rectBeside'], L['besideAlign'], L['besideOneLine']
        barFill, barBorderColor, barFrame = lcdBarColors()
        rows = self.sideRows() if self.sideMode else []
        printDBG("IPTVExtMoviePlayerColorSummary.computeLayout display[%dx%d] mode[%s] cover[%s] fit[%s] side[%s] rows%r runs[%d] renderer[%s] font[%s] fTime[%d] title[%d] pct time[%d] title[%d] bar[%s/%s/%d h%d y%d] full%r beside%r cover%r right%r" % (
            self.w, self.h, mode, coverMode, lcdSetting('lcd_cover_fit', 'auto'), self.sideMode, rows, self.titleRuns, RUNNING_TEXT_RENDERER, LCD_FONT,
            L['fTime'], L['fTitleMinBeside'], timePct, titlePct, barFill, barBorderColor, barFrame, L['barH'], L['barY'],
            self.rectFull, self.rectBeside, L['coverRect'], L['sideRect']))
        left = 'lcdCurrTimeHM' if shortTimes else 'lcdCurrTime'
        right = 'lcdRemainedShort' if shortTimes else 'lcdRemained'
        percentWidget = ''
        if L['percentColumn']:
            percentWidget = '<widget source="parent.lcdPercent" render="Label" position="%d,%d" size="%d,%d" font="%s;%d" halign="center" foregroundColor="#c0c0c0" backgroundColor="#000000" transparent="1" noWrap="1" valign="bottom" />' % (
                L['x0'] + L['pad'] + L['colW'], L['timeY'], L['midW'], L['timeH'], LCD_FONT, L['fTime'])
        if self.sideMode:
            timeWidgets = self.sideRowsXml(L, rows, shortTimes)
        else:
            timeWidgets = """<widget source="parent.%(left)s" render="Label" position="%(x)d,%(timeY)d" size="%(colW)d,%(timeH)d" font="%(fn)s;%(fTime)d" halign="left" foregroundColor="#ffffff" backgroundColor="#000000" transparent="1" noWrap="1" valign="bottom" />
            %(percentWidget)s
            <widget source="parent.%(right)s" render="Label" position="%(rightX)d,%(timeY)d" size="%(colW)d,%(timeH)d" font="%(fn)s;%(fTime)d" halign="right" foregroundColor="#ffffff" backgroundColor="#000000" transparent="1" noWrap="1" valign="bottom" />""" % {
                'x': L['x0'] + L['pad'], 'timeY': L['timeY'], 'colW': L['colW'], 'timeH': L['timeH'], 'fn': LCD_FONT, 'fTime': L['fTime'],
                'left': left, 'right': right, 'rightX': L['x0'] + L['pad'] + L['cw'] - L['colW'], 'percentWidget': percentWidget}
        self.skinPlain = """
        <screen position="0,0" size="%(w)d,%(h)d" backgroundColor="#000000">
            %(titleWidget)s
            <widget source="parent.lcdProgress" render="Progress" position="%(x)d,%(barY)d" size="%(cw)d,%(barH)d" foregroundColor="%(barFill)s" backgroundColor="%(barBack)s" borderWidth="%(barBorder)d" borderColor="%(barBorderColor)s" />
            %(timeWidgets)s
        </screen>""" % {'w': L['w'], 'h': L['h'], 'x': L['x0'] + L['pad'], 'cw': L['cw'],
                        'titleWidget': self.titleWidgetXml(self.rectFull, L['fTitleMin'], 'center'),
                        'barY': L['barY'], 'barH': L['barH'], 'barBorder': L['barBorder'] * barFrame, 'barFill': barFill, 'barBack': LCD_BAR_BACK,
                        'barBorderColor': barBorderColor, 'timeWidgets': timeWidgets}
        # the scrolling title is a renderer that cannot be moved like a label: one per place, the unused one is suspended
        besideTitle = ''
        if self.titleScroll:
            if self.besideOneLine:
                lineFont = self.oneLineFont(self.rectBeside)
                # a title that rolls starts at the LEFT edge (a centred one would lose its beginning), a short one is
                # centred; a later title gets its alignment from alignScrollLine
                self.lcdLineLeft = self.lineTooLong(self.rectBeside, lineFont)
                besideTitle = self.titleWidgetXml(self.rectBeside, lineFont, 'left' if self.lcdLineLeft else 'center', True)
            else:
                besideTitle = self.titleWidgetXml(self.rectBeside, L['fTitleMinBeside'], self.besideAlign)
        self.skinCover = self.skinPlain.replace('</screen>', """<widget name="lcdCover" position="%d,%d" size="%d,%d" alphatest="blend" />
        %s</screen>""" % (L['coverRect'] + (besideTitle,)))

    @classmethod
    def oneLineFont(cls, rect):
        # the largest font whose line fits into the height of the rectangle (the single title line below a poster)
        return max(12, int((rect[3] - 2) / LCD_POSTER_LINE_EM))

    def titleWidgetXml(self, rect, font, halign, oneLine=False):
        x, y, w, h = rect
        if self.titleScroll:
            if oneLine:
                # one line that rolls sideways (like the title of the Ultimo4K skin); a title that fits stands still.
                # It starts at the beginning, stands there LCD_TITLE_REST_MS (readable), rolls, and after titleRuns runs
                # it stays at the beginning for good (oneshot = the pause at the beginning; repeat counts the starts)
                options = 'movetype=running,direction=left,startpoint=0,step=3,steptime=60,startdelay=3000,always=0,repeat=%d,oneshot=%d' % (
                    self.titleRuns + 1 if self.titleRuns > 0 else 0, LCD_TITLE_REST_MS)
                return ('<widget source="parent.lcdTitle" render="%s" options="%s" noWrap="1" '
                        'position="%d,%d" size="%d,%d" font="%s;%d" halign="%s" valign="center" foregroundColor="#ffffff" '
                        'backgroundColor="#000000" transparent="1" />' % (RUNNING_TEXT_RENDERER, options, x, y, w, h, LCD_FONT, font, halign))
            # text that fits stays still (always=0); a longer one stands 3 s, rolls up and starts again from below.
            # The rectangle holds whole lines only (snapLines) and the text starts at its top.
            # titleRuns > 0: after that many runs it stands still (RunningText: repeat counts the starts, the first
            # one is the standing text; oneshot is the pause at the standing position and must be > 0 for repeat)
            options = 'movetype=running,direction=top,startpoint=0,startdelay=3000,steptime=60,pause=1500,wrap=1,always=0'
            if self.titleRuns > 0:
                options += ',repeat=%d,oneshot=%d' % (self.titleRuns + 1, LCD_TITLE_REST_MS)
            return ('<widget source="parent.lcdTitle" render="%s" '
                    'options="%s" '
                    'position="%d,%d" size="%d,%d" font="%s;%d" halign="%s" valign="top" foregroundColor="#ffffff" '
                    'backgroundColor="#000000" transparent="1" />' % (RUNNING_TEXT_RENDERER, options, x, y, w, h, LCD_FONT, font, halign))
        return ('<widget source="parent.lcdTitle" render="Label" position="%d,%d" size="%d,%d" font="%s;%d" '
                'halign="%s" valign="center"%s foregroundColor="#ffffff" backgroundColor="#000000" transparent="1" />' % (
                    x, y, w, h, LCD_FONT, font, halign, ' noWrap="1"' if oneLine else ''))

    def updateLcdEndTime(self):
        # the time when the film ends (now + remaining time) for the row "ENDS" of the layout "side"; empty without a
        # known length and for live streams
        text = ''
        try:
            playback = getattr(self.lcdParent, 'playback', None)
            if isinstance(playback, dict):
                length = playback.get('Length') or 0
                curr = playback.get('CurrentTime') or 0
                live = playback.get('IsLive') or playback.get('LiveDetected')
                if length > 0 and 0 <= curr <= length and not live:
                    text = time.strftime('%H:%M', time.localtime(time.time() + length - curr))
        except Exception:
            printExc()
        if text != self.lcdEndTimeText:
            self.lcdEndTimeText = text
            self['lcdEndTime'].setText(text)

    @classmethod
    def coverWanted(cls):
        # the setting and a display wide enough for the picture beside the title (an own LCD skin decides itself)
        try:
            return cls.w >= cls.LCD_COVER_MIN_WIDTH and config.plugins.iptvplayer.lcd_cover.value
        except Exception:
            return False

    def showLcdCover(self):
        self.setLcdCover(getattr(self.lcdParent, 'lcdCoverFile', ''), force=True)

    def setLcdCover(self, path, force=False):
        # the parent's picture: shown in the lcdCover widget when it is a picture file, the title moves beside it;
        # without one the title gets the whole width. Called at layout finish and by the download manager when
        # the shown row or its state changes (updateLcdCover)
        path = path or ''
        if path == self.lcdCoverFile and not force:
            return
        self.lcdCoverFile = path
        try:
            size = self['lcdCover'].instance.size()
            if size.width() > 0 and size.height() > 0 and os_path.isfile(path) and os_path.getsize(path) > 0:
                # the title beside the picture first: a decode that fails puts it back (lcdCoverDecoded)
                self.placeLcdTitle(True)
                # the ident is the source: a result for a row that is no longer shown is dropped (lcdCoverDecoded)
                lcdDecodeCover(self['lcdCover'], path, self.lcdCoverDecoded, path)
                return
            self['lcdCover'].hide()
        except Exception:
            printExc()
        self.placeLcdTitle(False)

    def lcdCoverDecoded(self, ret):
        if ret.get('Ident') != self.lcdCoverFile:
            return   # the download manager shows another row by now
        pixmap = ret.get('Pixmap', None)
        self['lcdCover'].updatePixmap(pixmap, ret.get('FileName', self.lcdCoverFile))
        try:
            if pixmap is not None:
                self['lcdCover'].show()  # hidden since a row without a picture
            else:
                self['lcdCover'].hide()
        except Exception:
            printExc()
        if pixmap is None:
            # the picture could not be decoded: the title gets the whole width back
            self.placeLcdTitle(False)

    def placeLcdTitle(self, besideCover):
        # the title of the layout above beside the cover or over the whole width; a title placed somewhere
        # else (an own LCD skin) is left alone
        if besideCover == self.lcdCoverShown:
            return
        try:
            if self.titleScroll:
                self.switchScrollTitle(besideCover)
            elif self.lcdTitleRenderer is None:
                self.lcdTitleRenderer = self.findLcdTitleRenderer() or False
            if not self.titleScroll and self.lcdTitleRenderer:
                instance = self.lcdTitleRenderer.instance
                if besideCover:
                    x, y, w, h = self.rectBeside
                    instance.move(ePoint(x, y))
                    instance.resize(eSize(w, h))
                    instance.setHAlign(eLabel.alignCenter if self.besideAlign == 'center' else eLabel.alignLeft)
                else:
                    x, y, w, h = self.rectFull
                    instance.move(ePoint(x, y))
                    instance.resize(eSize(w, h))
                    instance.setHAlign(eLabel.alignCenter)
            self.lcdCoverShown = besideCover
            self.fitLcdTitle(self.currentLcdTitle())
        except Exception:
            printExc()

    def currentLcdTitle(self):
        try:
            return self.lcdParent['lcdTitle'].getText() or ''
        except Exception:
            return ''

    @classmethod
    def wrapLcdText(cls, text, width, size):
        # greedy word wrap with the average character width; a word wider than a line is cut
        charW = size * cls.CHAR_EM
        perLine = max(1, int(width / charW))
        lines = []
        cur = ''
        for word in text.split():
            while len(word) > perLine:
                if cur:
                    lines.append(cur)
                    cur = ''
                lines.append(word[:perLine])
                word = word[perLine:]
            if not cur:
                cur = word
            elif len(cur) + 1 + len(word) <= perLine:
                cur += ' ' + word
            else:
                lines.append(cur)
                cur = word
        if cur or not lines:
            lines.append(cur)
        return lines

    def fitLcdTitle(self, text):
        # the largest font in which the title fits its area; a title that needs more than the smallest readable font
        # is shown in that font page by page (a timer), unless the setting says to shrink it further
        self.lcdPageTimer.stop()
        self.lcdPages = []
        try:
            if self.lcdCoverShown is None:
                return
            if self.titleScroll:
                self.fitScrollTitle(text)
                return
            renderer = self.lcdTitleRenderer
            if renderer is None:
                renderer = self.lcdTitleRenderer = self.findLcdTitleRenderer() or False
            if not renderer:
                return
            instance = renderer.instance
            text = (text or '').strip()
            beside = bool(self.lcdCoverShown)
            if beside and self.besideOneLine:
                # poster / side: ONE line below the picture, as large as its height and the width allow; a title that
                # does not fit even in the smallest font is shown line by line ("pages") or cut ("shrink")
                width = self.rectBeside[2]
                size = self.oneLineFont(self.rectBeside)
                while size > 12 and len(text) * size * self.CHAR_EM > width:
                    size = max(12, size - max(1, size // 12))
                instance.setNoWrap(1)
                instance.setFont(gFont(LCD_FONT, size))
                lines = self.wrapLcdText(text, width, size)
                if len(lines) > 1 and self.titlePages:
                    self.showLcdPages(instance, lines)
                elif len(lines) > 1:
                    instance.setText(lines[0].rstrip() + '...')
                else:
                    instance.setText(text)
                return
            width, height = (self.rectBeside if beside else self.rectFull)[2:4]
            size = min(self.fTitleCover if beside else self.fTitle, height)
            readable = min(self.fTitleMinBeside if beside else self.fTitleMin, size)
            size, lines = self.fitFont(text, width, height, size, readable if self.titlePages else 12)
            instance.setNoWrap(0)   # one line below the picture before
            instance.setFont(gFont(LCD_FONT, size))
            perPage = max(1, int(height / (size * self.LINE_EM)))
            if self.titlePages and len(lines) > perPage:
                self.showLcdPages(instance, ['\n'.join(lines[i:i + perPage]) for i in range(0, len(lines), perPage)])
            else:
                instance.setText(text)
        except Exception:
            printExc()

    @classmethod
    def fitFont(cls, text, width, height, size, minSize):
        # the largest font from size down to minSize in which the wrapped text fits the height: (size, lines)
        while True:
            lines = cls.wrapLcdText(text, width, size)
            if len(lines) * size * cls.LINE_EM <= height or size <= minSize:
                return size, lines
            size = max(minSize, size - max(1, size // 12))

    def showLcdPages(self, instance, pages):
        # a long title page by page, one page every PAGE_MS
        self.lcdPages = pages
        self.lcdPageIdx = 0
        instance.setText(pages[0])
        self.lcdPageTimer.start(self.PAGE_MS, False)

    def nextLcdPage(self):
        try:
            if len(self.lcdPages) > 1:
                self.lcdPageIdx = (self.lcdPageIdx + 1) % len(self.lcdPages)
                self.lcdTitleRenderer.instance.setText(self.lcdPages[self.lcdPageIdx])
        except Exception:
            printExc()

    def scrollRenderers(self):
        # the RunningText renderers of parent.lcdTitle by place: 'full' (whole width) and 'beside' (next to / below the
        # cover). Only the renderers of the title count (a display skin may roll other texts too); a rolling one is
        # known by its class (RunningText / VRunningText) or its label, the internals differ between the images
        found = {}
        try:
            source = self.lcdParent['lcdTitle']
            candidates = []
            for renderer in getattr(self, 'renderer', []):
                if getattr(renderer, 'source', None) is not source:
                    continue
                if renderer.__class__.__name__ not in ('RunningText', 'VRunningText') and runningTextLabel(renderer) is None:
                    continue
                if getattr(renderer, 'instance', None) is None:
                    continue
                candidates.append(renderer)
                position, size = renderer.instance.position(), renderer.instance.size()
                printDBG("IPTVExtMoviePlayerColorSummary.scrollRenderers renderer[%s] pos[%r,%r] size[%r,%r] full%r beside%r" % (
                    renderer.__class__.__name__, position.x(), position.y(), size.width(), size.height(), self.rectFull, self.rectBeside))
                if (position.x(), position.y(), size.width()) == (self.rectFull[0], self.rectFull[1], self.rectFull[2]):
                    found['full'] = renderer
                elif (position.x(), position.y(), size.width()) == (self.rectBeside[0], self.rectBeside[1], self.rectBeside[2]):
                    found['beside'] = renderer
            if len(found) < 2 and len(candidates) == 2:
                # the renderers report another position than the skin gave (the RunningText moves its widget itself):
                # the skin lists the whole-width one first, the one beside the cover second
                found = {'full': candidates[0], 'beside': candidates[1]}
            printDBG("IPTVExtMoviePlayerColorSummary.scrollRenderers candidates[%d] found%r" % (len(candidates), sorted(found.keys())))
        except Exception:
            printExc()
        return found

    def switchScrollTitle(self, besideCover):
        # only the renderer of the current place runs: the other one is hidden (and suspended, where the renderer can)
        renderers = self.scrollRenderers()
        self.lcdScrollRenderers = renderers
        active = renderers.get('beside' if besideCover else 'full')
        for renderer in renderers.values():
            try:
                shown = renderer is active
                if shown:
                    renderer.instance.show()
                else:
                    renderer.instance.hide()
                if hasattr(renderer, 'doSuspend'):
                    renderer.doSuspend(0 if shown else 1)
            except Exception:
                printExc()

    def fitScrollTitle(self, text):
        # the largest font in which the title fits stays still; a longer one gets the smallest readable font and
        # the renderer scrolls it (the renderer only knows the skin's font: it is set again and the text recalculated)
        renderer = getattr(self, 'lcdScrollRenderers', {}).get('beside' if self.lcdCoverShown else 'full')
        label = runningTextLabel(renderer) if renderer is not None else None
        if label is None or not hasattr(renderer, 'txfont'):
            return
        beside = bool(self.lcdCoverShown)
        if beside and self.besideOneLine:
            self.alignScrollLine(renderer, label, text)
            return
        width, height = (self.rectBeside if beside else self.rectFull)[2:4]
        size = min(self.fTitleCover if beside else self.fTitle, height)
        readable = min(self.fTitleMinBeside if beside else self.fTitleMin, size)
        size = self.fitFont((text or '').strip(), width, height, size, readable)[0]
        font = gFont(LCD_FONT, size)
        renderer.txfont = font
        label.setFont(font)
        renderer.changed((renderer.CHANGED_DEFAULT,))

    def alignScrollLine(self, renderer, label, text):
        # the single rolling line below the picture: a title that rolls starts at the left edge, one that fits is
        # centred. The skin gave the alignment for the title at its start; the download manager changes the title
        # later. RunningText and VRunningText keep it in halign (eLabel) and txtflags (RT_HALIGN_*).
        left = self.lineTooLong(self.rectBeside, self.oneLineFont(self.rectBeside), text)
        if getattr(self, 'lcdLineLeft', None) == left:
            return
        self.lcdLineLeft = left
        try:
            from enigma import RT_HALIGN_LEFT, RT_HALIGN_CENTER, RT_HALIGN_RIGHT, RT_HALIGN_BLOCK
            if hasattr(renderer, 'txtflags'):
                renderer.txtflags = (renderer.txtflags & ~(RT_HALIGN_LEFT | RT_HALIGN_CENTER | RT_HALIGN_RIGHT | RT_HALIGN_BLOCK)) | (RT_HALIGN_LEFT if left else RT_HALIGN_CENTER)
            align = eLabel.alignLeft if left else eLabel.alignCenter
            if hasattr(renderer, 'halign'):
                renderer.halign = align
            label.setHAlign(align)
            renderer.changed((renderer.CHANGED_DEFAULT,))
        except Exception:
            printExc()

    def findLcdTitleRenderer(self):
        # the Label of parent.lcdTitle, and only where the layout above put it
        try:
            source = self.lcdParent['lcdTitle']
        except Exception:
            return None
        for renderer in getattr(self, 'renderer', []):
            if getattr(renderer, 'source', None) is not source:
                continue
            try:
                position, size = renderer.instance.position(), renderer.instance.size()
                if (position.x(), position.y(), size.width()) == (self.rectFull[0], self.rectFull[1], self.rectFull[2]):
                    return renderer
            except Exception:
                printExc()
            return None
        return None


class IPTVExtMoviePlayerSummary(Screen):
    summary_screenwidth, summary_screenheight = lcdDisplaySize((132, 64))
    if summary_screenwidth > 132 and summary_screenheight > 64:
        skin = """
            <screen position="0,0" size="%s,%s">
                <widget source="parent.Title" render="Label" position="6,4" size="%s,%s" font="Regular;42" />
            </screen>""" % (summary_screenwidth, summary_screenheight, summary_screenwidth - 12, summary_screenheight - 8)
    else:
        skin = """
            <screen position="0,0" size="132,64">
                <widget source="global.CurrentTime" render="Label" position="0,0" size="120,42" font="Regular;18" noWrap="1">
                        <convert type="ClockToText"></convert>
                </widget>
            </screen>"""

    def __init__(self, session, parent):
        Screen.__init__(self, session, parent=parent)


def listSummaryIfWanted():
    # createSummary() of the main list and the PlayerSelector
    return IPTVPlayerLCDScreen if config.plugins.iptvplayer.extplayer_summary.value != 'no' else None


def setupSummaryIfWanted():
    # createSummary() of the settings (ConfigBaseWidget): the SetupSummary of the image, every display skin
    # has it (title, marked setting, its value); None shows the SimpleSummary with the title only
    if config.plugins.iptvplayer.extplayer_summary.value == 'no':
        return None
    try:
        from Screens.Setup import SetupSummary
        return SetupSummary
    except Exception:
        printExc()
        return None


def movieSummaryIfWanted():
    # createSummary() of the internal player ("mini"): the InfoBarMoviePlayerSummary of the image, like the
    # enigma2 movie player and EMC, every display skin has it (title, progress bar, times); None shows the
    # SimpleSummary with the skin title of the MoviePlayer screen ("InfoBar")
    if config.plugins.iptvplayer.extplayer_summary.value == 'no':
        return None
    try:
        from Screens.InfoBarGenerics import InfoBarMoviePlayerSummary
        return InfoBarMoviePlayerSummary
    except Exception:
        return None  # an image without it


class IPTVPlayerLCDScreen(Screen):
    summary_screenwidth, summary_screenheight = lcdDisplaySize((132, 64))
    if summary_screenwidth >= LARGE_LCD_MIN_WIDTH and summary_screenheight >= LARGE_LCD_MIN_HEIGHT:
        # colour LCD: the layout follows the display size, the logo keeps the 3:1 of the host logos
        margin = summary_screenwidth // 40
        textW = summary_screenwidth - 2 * margin
        logoH = min(textW // 3, summary_screenheight // 2)
        logoW = logoH * 3
        logoY = summary_screenheight - logoH - margin
        text1H = (logoY - margin) * 2 // 5
        text2H = logoY - margin - text1H
        # a tall display has the height, "E2iPlayer" must still fit the width
        font1 = min(text1H * 3 // 4, textW // 7)
        skin = """
    <screen position="0,0" size="%(w)d,%(h)d" title="E2iPlayer">
        <widget name="text1" position="%(m)d,%(text1Y)d" size="%(textW)d,%(text1H)d" font="Regular;%(font1)d" halign="center" valign="center" foregroundColor="#05F7F3"/>
        <widget name="text2" position="%(m)d,%(text2Y)d" size="%(textW)d,%(text2H)d" font="Regular;%(font2)d" halign="center" valign="center" foregroundColor="#FFFF00"/>
        <widget name="LCDlogo" position="%(logoX)d,%(logoY)d" zPosition="4" size="%(logoW)d,%(logoH)d" alphatest="blend" />
    </screen>""" % {'w': summary_screenwidth, 'h': summary_screenheight, 'm': margin, 'textW': textW,
                    'text1Y': margin // 2, 'text1H': text1H, 'font1': font1,
                    'text2Y': margin // 2 + text1H, 'text2H': text2H, 'font2': font1 * 4 // 5,
                    'logoX': (summary_screenwidth - logoW) // 2, 'logoY': logoY, 'logoW': logoW, 'logoH': logoH}
    else:
        skin = """
    <screen position="0,0" size="132,64" title="E2iPlayer">
        <widget name="text1" position="4,0" size="132,14" font="Regular;12" halign="center" valign="center"/>
        <widget name="text2" position="4,14" size="132,49" font="Regular;10" halign="center" valign="center"/>
        <widget name="LCDlogo" zPosition="4" position="4,70" size="240,80" alphatest="blend" />
    </screen>"""

    def __init__(self, session, parent):
        Screen.__init__(self, session)
        self.hostText = ""
        try:
            self["text1"] = Label("E2iPlayer")
            self["text2"] = Label("")
            self["LCDlogo"] = Pixmap()
        except Exception:
            pass

    def setText(self, text):
        try:
            self.hostText = text[0:39]
            self["text2"].setText(self.hostText)
        except Exception:
            pass

    def setItem(self, text):
        # the marked row of a host: the host moves up to the first line, without a row "E2iPlayer" and the host
        try:
            self["text1"].setText(self.hostText if text and self.hostText else "E2iPlayer")
            self["text2"].setText(text[0:120] if text else self.hostText)
        except Exception:
            pass

    def LCD_showPic(self, widgetName, picPath):
        try:
            self[widgetName].instance.setScale(1)
            self[widgetName].instance.setPixmap(LoadPixmap(picPath, cached=True))
            self[widgetName].show()
        except Exception:
            pass

    def LCD_hide(self, widgetName):
        try:
            self[widgetName].hide()
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------------------------
# IPTVPlayerInfoLCDScreen: the LCD of the choice boxes / context menus, the article view, the favourites, the search
# history, the search result grid and the picture viewer - the screen title, the marked row and a picture


def infoLcdGeometry(width, height, hasText, hasPicture):
    # rectangles (x, y, w, h) and font sizes of IPTVPlayerInfoLCDScreen; plain arithmetic, testable on a PC.
    # A picture only on a colour display (the size of isLargeLcd); without text and picture the title gets the
    # whole display
    large = width >= LARGE_LCD_MIN_WIDTH and height >= LARGE_LCD_MIN_HEIGHT
    hasPicture = hasPicture and large
    m = width // 40 if large else 0
    W = width - 2 * m
    if not hasText and not hasPicture:
        font = max(10, min(height // 5, W // 8)) if large else max(10, height // 4)
        return {'title': (m, m, W, height - 2 * m), 'titleFont': font, 'text': None, 'textFont': font, 'picture': None}
    titleH = max(12, height // 6) if large else max(12, height // 4)
    titleFont = max(10, titleH * 3 // 4)
    y0 = m + titleH + m // 2
    areaH = height - y0 - m
    g = {'title': (m, m, W, titleH), 'titleFont': titleFont, 'text': None, 'textFont': titleFont, 'picture': None}
    if hasPicture and hasText:
        picW = W * 2 // 5
        textW = W - picW - m
        g['picture'] = (m, y0, picW, areaH)
        g['text'] = (m + picW + m, y0, textW, areaH)
        g['textFont'] = max(10, min(areaH // 5, textW // 7))
    elif hasPicture:
        g['picture'] = (m, y0, W, areaH)
    else:
        g['text'] = (m, y0, W, areaH)
        g['textFont'] = max(10, min(areaH // 4, W // 9)) if large else max(10, areaH // 3)
    return g


def skinHasScreen(name):
    # a display skin with a screen of its own for it: its widget positions stay, the built-in layout is not used
    try:
        from skin import dom_screens
        return name in dom_screens
    except Exception:
        return False


def addInfoLcd(screen, title=None):
    # what IPTVPlayerInfoLCDScreen shows of its parent, set with lcdSetInfo(): the marked row / text and a picture
    # file; title replaces the screen title (for a screen whose title is a Label of its own)
    screen.lcdInfoTitle = title
    screen.lcdInfoText = ''
    screen.lcdInfoPicture = ''


def lcdListText(listWidget):
    # the name of the marked row: IPTV lists hold (IPTVChoiceBoxItem / CDisplayListItem,), a MenuList strings or
    # (text, value)
    try:
        sel = listWidget.l.getCurrentSelection()
        item = sel[0] if isinstance(sel, (tuple, list)) and sel else sel
        name = getattr(item, 'name', None)
        if name is None and isinstance(item, str):
            name = item
        return name or ''
    except Exception:
        return ''


def lcdFollowList(screen, listName='list'):
    # the marked row of the list on the LCD while the screen is open (IPTV list or MenuList)
    widget = screen[listName]

    def changed():
        lcdSetInfo(screen, text=lcdListText(widget))

    try:
        if hasattr(widget, 'connectSelChanged'):
            widget.connectSelChanged(changed)
            screen.onClose.append(lambda: widget.disconnectSelChanged(changed))
        else:
            widget.onSelectionChanged.append(changed)
    except Exception:
        printExc()
    return changed


def lcdSetInfo(screen, text=None, picture=None, title=None, refresh=False):
    # the marked row / text, the picture (a local file, '' = none) and the title on IPTVPlayerInfoLCDScreen; None
    # leaves a value as it is, refresh shows the same picture file again (a picture that was loaded anew)
    try:
        if not hasattr(screen, 'lcdInfoText'):
            addInfoLcd(screen)
        changed = False
        if text is not None:
            text = StripColorCodes(text)
            if text != screen.lcdInfoText:
                screen.lcdInfoText = text
                changed = True
        if title is not None:
            title = StripColorCodes(title)
            if title != screen.lcdInfoTitle:
                screen.lcdInfoTitle = title
                changed = True
        newPicture = False
        if picture is not None and (picture != screen.lcdInfoPicture or refresh):
            screen.lcdInfoPicture = picture
            newPicture = True
        if changed or newPicture:
            for summary in getattr(screen, 'summaries', []):
                if hasattr(summary, 'showInfo'):
                    summary.showInfo(newPicture)
    except Exception:
        printExc()


def infoSummaryIfWanted():
    # createSummary() of the screens with IPTVPlayerInfoLCDScreen; None shows the SimpleSummary with the title only
    return IPTVPlayerInfoLCDScreen if config.plugins.iptvplayer.extplayer_summary.value != 'no' else None


class IPTVPlayerInfoLCDScreen(Screen):
    # Can be replaced in the LCD skin with <screen name="IPTVPlayerInfoLCDScreen">: the Labels "title" (screen title)
    # and "text" (marked row) and the widget "picture" (alphatest="blend"); such a skin keeps its positions. The
    # built-in layout (infoLcdGeometry) moves the widgets for text / picture / both / only the title.
    w, h = lcdDisplaySize((132, 64))
    # the colours of IPTVPlayerLCDScreen on a colour display
    colors = ('foregroundColor="#05F7F3" ', 'foregroundColor="#FFFF00" ') if w >= LARGE_LCD_MIN_WIDTH and h >= LARGE_LCD_MIN_HEIGHT else ('', '')
    skin = """
    <screen name="IPTVPlayerInfoLCDScreen" position="0,0" size="%(w)d,%(h)d" title="E2iPlayer">
        <widget name="title" position="0,0" size="%(w)d,%(h)d" font="%(fn)s;12" halign="center" valign="center" %(c1)stransparent="1" />
        <widget name="text" position="0,0" size="%(w)d,%(h)d" font="%(fn)s;12" halign="center" valign="center" %(c2)stransparent="1" />
        <widget name="picture" position="0,0" size="%(w)d,%(h)d" zPosition="2" alphatest="blend" />
    </screen>""" % {'w': w, 'h': h, 'c1': colors[0], 'c2': colors[1], 'fn': LCD_FONT}

    def __init__(self, session, parent):
        Screen.__init__(self, session, parent=parent)
        self.infoParent = parent
        self['title'] = Label('')
        self['text'] = Label('')
        self['picture'] = Cover()
        self.ownSkin = skinHasScreen('IPTVPlayerInfoLCDScreen')
        self.infoLayout = None
        self.pictureFile = ''
        self.pictureShown = False  # a picture file is placed (a decode that fails takes it back)
        self.onLayoutFinish.append(self.infoStart)

    def infoStart(self):
        try:
            self['picture'].hide()
        except Exception:
            printExc()
        self.showInfo(True)

    def parentTitle(self):
        title = getattr(self.infoParent, 'lcdInfoTitle', None)
        if not title:
            try:
                title = self.infoParent.getTitle()
            except Exception:
                title = ''
        return StripColorCodes(title or '')

    def showInfo(self, newPicture=False):
        # called by lcdSetInfo() of the parent and once at the start
        try:
            self['title'].setText(self.parentTitle())
            self['text'].setText(getattr(self.infoParent, 'lcdInfoText', '') or '')
            if newPicture:
                path = getattr(self.infoParent, 'lcdInfoPicture', '') or ''
                self.pictureFile = path
                self.pictureShown = bool(path) and isLargeLcd() and os_path.isfile(path) and os_path.getsize(path) > 0
                if not self.pictureShown:
                    self['picture'].hide()
            moved = self.placeInfo()
            if self.pictureShown and (newPicture or moved):
                self.decodePicture()
        except Exception:
            printExc()

    def decodePicture(self):
        size = self['picture'].instance.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        lcdDecodeCover(self['picture'], self.pictureFile, self.pictureDecoded, self.pictureFile)

    def pictureDecoded(self, ret):
        if ret.get('Ident') != self.pictureFile:
            return   # another row / picture is marked by now
        pixmap = ret.get('Pixmap', None)
        try:
            if pixmap is not None and self.pictureShown:
                self['picture'].updatePixmap(pixmap, ret.get('FileName', ''))
                self['picture'].show()
            elif pixmap is None:
                printDBG("IPTVPlayerInfoLCDScreen picture can not be shown [%s]" % self.pictureFile)
                self.pictureShown = False
                self['picture'].hide()
                self.placeInfo()
        except Exception:
            printExc()

    def placeInfo(self):
        # the layout of the four cases; True when the widgets were moved
        hasText = bool(self['text'].getText())
        if self.ownSkin:
            # the display skin's positions: only what is empty is hidden
            if hasText:
                self['text'].show()
            else:
                self['text'].hide()
            return False
        layout = (hasText, self.pictureShown)
        if layout == self.infoLayout:
            return False
        self.infoLayout = layout
        g = infoLcdGeometry(self.w, self.h, hasText, self.pictureShown)
        for name, font in (('title', g['titleFont']), ('text', g['textFont']), ('picture', None)):
            rect = g[name]
            widget = self[name]
            if rect is None:
                widget.hide()
                continue
            widget.instance.move(ePoint(rect[0], rect[1]))
            widget.instance.resize(eSize(rect[2], rect[3]))
            if font:
                widget.instance.setFont(gFont(LCD_FONT, font))
                widget.show()
        return True
