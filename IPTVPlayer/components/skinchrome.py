# -*- coding: utf-8 -*-
###################################################
# Shared skin "chrome": the logo/title header and the OK/EXIT + color-key
# footer bar that PlayerSelectorWidget, SearchResultGridWidget,
# IPTVFavouritesMainWidget, YouTubeUserLinksEditorScreen and others all
# hand-duplicate today, once per resolution tier (skinHD/skinFHD/skinWQHD).
#
# NOT auto-scaled via resolution="1280,720": PlayerSelectorWidget's/
# SearchResultGridWidget's grid templates deliberately keep itemHeight/
# itemWidth and the marker-frame PNG (marker145/165/180.png, loaded via
# setSelectionPixmap() - which does NOT get auto-scaled by resolution=,
# unlike declared skin widgets) at a FIXED pixel size across all three
# tiers, so a higher resolution just fits more same-sized cells rather
# than fewer, bigger ones. Putting resolution="1280,720" on the whole
# <screen> would scale those "fixed" numbers too, so the marker frame
# would no longer match the (now bigger) cell size, and fewer cells
# would fit than before since the content area grows at the same rate
# as the cells instead of independently.
#
# So this stays per-tier like the old skinHD/skinFHD/skinWQHD trio, but
# the tier's scale factor (1.0/1.5/2.0) is a single argument instead of
# three fully copy-pasted blocks - only the six numbers below actually
# differ, everything else is generated from them. Every generated number
# reproduces the original tier's value from playerselector.py's old
# skinHD/skinFHD/skinWQHD exactly, except the color-key label font size,
# which was hand-tuned to 17/26/35 (not a clean x1.5/x2 progression) -
# kept as an explicit lookup for that reason.
#
# Bitmap icon SOURCES still don't scale up sharply on their own (a 20x20
# HD source stretched into a 40x40 WQHD box looks soft), so getIconBase()
# below still picks a higher-resolution source folder once the real
# screen is wide enough - same tier logic iptvchoicebox.py already uses,
# now shared here instead of copy-pasted per caller too.
#
# Everything below the header and above the footer (the actual grid/list/
# keyboard/... content) is deliberately NOT part of this file - that
# stays screen-specific, only the chrome around it is shared.
###################################################
from enigma import getDesktop

ICON_ROOT = "/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons"

# pitch (HD-reference px) between one footer color-key slot and the next.
# Each slot's own icon+label footprint is 190px, leaving a 5px buffer to
# the next slot. Slots are filled in order (red, green, yellow, blue) by
# whichever of those a caller's `keys` actually includes, so e.g. a
# blue-only footer lands on the first (leftmost) slot instead of leaving
# three empty slots in front of it.
KEY_PITCH = 195

# gap (HD-reference px) between the left icon cluster's last shown icon
# and the color-key row's first slot. _keyStartX() below computes the
# actual start from whatever's shown, so a footer with fewer left-cluster
# icons doesn't leave an oversized gap before the colors.
LEFT_TO_KEY_GAP = 12

# left-hand icon cluster (menu/nav/num/info/ok/exit) - same "compute at
# build time, slide left, no gaps" idea as the color keys above, just for
# the plain gray icon-only buttons instead of the icon+label color keys.
# 16 is MENU's own slot, matching its original standalone x position so a
# MENU-only footer still renders at the same spot. 54px spacing is a bit
# tighter than iptvchoicebox.py's 58px (that reference chrome only ever
# shows 2 of these icons at once). Slots 5-8 (232/286/340/394) cover
# IPTVPinWidget's numpad hint and callers that need extra plain
# repositionable icons on their own side (info/T9/page-up-down/play
# hints) - each caller places those itself via leftIconGeometry() rather
# than build_footer() owning them, since their visibility can depend on
# other icons being hidden too.
LEFT_ICON_SLOTS = [16, 70, 124, 178, 232, 286, 340, 394]
LEFT_ICON_W = 40


def _keyStartX(numLeftIcons):
    # HD-reference x where the color-key row begins, given how many of
    # the left icon cluster's slots are actually in use (0-4) - see
    # LEFT_TO_KEY_GAP above. With all 4 shown this works out to 230
    # (178 + 40 + 12), matching this layout's original fixed value
    # exactly - only a smaller cluster actually moves the start point.
    if numLeftIcons <= 0:
        return LEFT_ICON_SLOTS[0]
    return LEFT_ICON_SLOTS[numLeftIcons - 1] + LEFT_ICON_W + LEFT_TO_KEY_GAP


# the one set of numbers that doesn't reduce to a clean x1.5/x2 of the
# HD value (17 -> 26 -> 35, not 17/25.5/34) - explicit per the comment
# above, falls back to a plain scaled-and-rounded value for any other
# scale a future caller might pass.
_KEY_LABEL_FONT = {1.0: 17, 1.5: 26, 2.0: 35}


def _s(value, scale):
    return int(round(value * scale))


def scalePixels(value, scale):
    # public alias for _s() - a caller repositioning a widget at runtime
    # (e.g. E2iPlayerWidget's color-key reflow, see colorKeyGeometry()
    # below) needs to convert its own HD-reference numbers (like a
    # screen's declared HEIGHT constant) using the exact same rounding
    # this module uses internally everywhere else, not a second
    # reimplementation of it.
    return _s(value, scale)


def getIconBase(screenwidth=None):
    if screenwidth is None:
        screenwidth = getDesktop(0).size().width()
    tier = "WQHD" if screenwidth >= 2560 else ("FHD" if screenwidth >= 1920 else "HD")
    return "%s/%s" % (ICON_ROOT, tier)


def getScale(screenwidth=None):
    if screenwidth is None:
        screenwidth = getDesktop(0).size().width()
    if screenwidth >= 2560:
        return 2.0
    elif screenwidth >= 1920:
        return 1.5
    return 1.0


def isExternalSkin(skinNames):
    # True when the active Enigma2 skin already ships a <screen> for one of
    # these names (its own skin_plugins.xml, or /etc/enigma2/skin_user_*.xml)
    # - i.e. this screen won't fall back to E2iPlayer's embedded self.skin.
    # E2iPlayerWidget/ConfigBaseWidget use it to switch to the StaticText /
    # no-runtime-.move() footer path an external skin needs.
    try:
        import skin as _e2skin
    except Exception:
        return False
    dom = getattr(_e2skin, "domScreens", None)
    if dom is None:
        dom = getattr(_e2skin, "dom_screens", None)
    if not dom:
        return False
    if isinstance(skinNames, str):
        skinNames = [skinNames]
    for n in skinNames:
        if n in dom:
            return True
    return False


def forceInternalSkinName(names):
    # With config.plugins.iptvplayer.skinforceallinternal on, swap every
    # skinName entry for a "_"-prefixed variant no external skin defines, so
    # Enigma2 falls back to the screen's own embedded self.skin - the same
    # trick the older "main screen only" option uses for
    # "_E2iPlayerWidgetScreen", generalized. Accepts a str or list, returns
    # the same shape; config read lazily/defensively.
    try:
        from Components.config import config
        if not config.plugins.iptvplayer.skinforceallinternal.value:
            return names
    except Exception:
        return names
    if isinstance(names, (list, tuple)):
        return ["_" + n for n in names]
    return "_" + names


def tierRowHeight(hd, fhd, wqhd, screenwidth=None):
    # centralizes the (itemH, scale) pairing that popup-height helpers
    # all over the codebase (ConfigBaseWidget._getSelectionListHeight(),
    # playerselector.py, iptvfavouriteswidgets.py, youtubeuserlinks.py,
    # searchhistoryeditor.py, iptvextmovieplayer.py, iptvplayerwidget.py,
    # iptvdm/iptvdmui.py, e2ivk.py, ...) would otherwise each hand-copy
    # as the exact same if/elif/else tier-threshold block -
    # a future resolution/tier change only needs editing here instead of
    # every one of them individually. scale here is always identical to
    # getScale()'s own return value - callers additionally need a
    # tier-specific real pixel row height (which varies per caller
    # depending on what's being measured: a plain text row, a logo row, a
    # bigger icon row, ...) to go with it.
    scale = getScale(screenwidth)
    if scale >= 2.0:
        return wqhd, scale
    elif scale >= 1.5:
        return fhd, scale
    return hd, scale


def header_height(scale=1.0):
    return _s(60, scale)


def footer_height(scale=1.0):
    # fits a 2-line wrapped color-key label - some translations, e.g.
    # French "Gestionnaire de Téléchargement", run to 30 characters and
    # never fit a single 170px line at any font size that still reads
    # comfortably. Every caller that derives its own window height from
    # this (Legacy grid mode) or has it added to a fixed per-tier height
    # (GRIDSUPPORT grid/list, Legacy list, SearchResultGridWidget) grows
    # by exactly this same delta, so footerY (= screen height - footer
    # height) itself doesn't move - only the window gets taller, the
    # content area above the footer is completely unaffected.
    return _s(64, scale)


def build_header(scale=1.0, iconBase=None, logoWidgetName=None, showLogo=True):
    # logoWidgetName: opt-in - when given, the logo slot becomes a named
    # placeholder widget instead of the fixed iptvlogo.png ePixmap, so a
    # caller can bind its own Cover-family Python component there (e.g.
    # to show a per-call value like the host site's own logo instead of
    # the app's). Position/size are identical either way, so this doesn't
    # affect any other caller that leaves it at the default.
    #
    # showLogo=False: drops the logo slot entirely and pulls titleX back
    # to the logo's own left margin (12) since there's no logo left to
    # clear - for a header band with no logo, e.g. a transient full-screen
    # overlay rather than a navigable app screen. Ignored (kept for a
    # future caller, not currently combined) if logoWidgetName is also
    # given - showLogo=False takes precedence.
    if iconBase is None:
        iconBase = getIconBase()
    logoW, logoH = _s(100, scale), _s(40, scale)
    logoX, logoY = _s(12, scale), _s(10, scale)
    # logo ends at 12+100=112; title starts shortly after that
    titleX = logoX if not showLogo else _s(124, scale)
    # lines up with the rest of the chrome's own spacing (12px logo
    # padding, 16px footer menu icon padding) instead of being its own
    # arbitrary number.
    titleRightMargin = _s(16, scale)
    titleH = _s(40, scale)
    # matches statusFont's own size on the screens that use this chrome.
    titleFont = _s(20, scale)
    dividerY = _s(60, scale)
    dividerH = _s(2, scale)
    if not showLogo:
        logoPart = ""
    elif logoWidgetName is None:
        logoPart = """<ePixmap pixmap="%s/iptvlogo.png" position="%d,%d" size="%d,%d" zPosition="10" alphatest="blend" transparent="1" />""" % (iconBase, logoX, logoY, logoW, logoH)
    else:
        logoPart = """<widget name="%s" position="%d,%d" size="%d,%d" zPosition="10" alphatest="blend" transparent="1" />""" % (logoWidgetName, logoX, logoY, logoW, logoH)
    return """
                <eLabel name="BG_Title" position="0,0" size="e,%d" backgroundColor="#100d0f16" zPosition="-1" />
                %s
                <widget source="Title" render="Label" position="%d,%d" size="e-%d,%d" foregroundColor="white" backgroundColor="black" borderWidth="1" borderColor="black" transparent="1" zPosition="1" font="Regular;%d" valign="center" />
                <ePixmap pixmap="%s/smallshadowline.png" position="0,%d" size="e,%d" zPosition="2" />
    """ % (dividerY, logoPart, titleX, logoY, titleRightMargin, titleH, titleFont, iconBase, dividerY, dividerH)


def colorKeyGeometry(height, numLeftIcons, slotIdx, scale=1.0):
    # single source of truth for a color-key slot's icon/label geometry -
    # build_footer() below uses this to lay out red/green/yellow/blue at
    # skin-build time; a caller that needs a color key to slide into a
    # different slot at RUNTIME (e.g. E2iPlayerWidget repositioning
    # yellow/blue when green's download hint appears/disappears, since
    # ConditionalShowHide only hides a widget in place, it doesn't reflow
    # the others) can call this again with a different slotIdx and get
    # the exact same numbers build_footer() would have used, then
    # .move() the widgets there itself. `height`/`scale` must be real
    # (already-scaled) values for a runtime call, unlike a skin-XML-
    # declare-time call on an auto-scaled screen, which passes the plain
    # HD-reference height and scale=1.0 - resolution= auto-scaling is
    # only ever applied to declared skin XML, never to a later
    # programmatic .move().
    footerH = footer_height(scale)
    footerY = height - footerH
    iconSize = _s(20, scale)
    labelW, labelH = _s(165, scale), _s(44, scale)
    labelDx = _s(25, scale)
    iconY = footerY + _s(22, scale)
    labelY = footerY + _s(10, scale)
    keyLabelFont = _KEY_LABEL_FONT.get(scale, _s(17, scale))
    x = _s(_keyStartX(numLeftIcons) + slotIdx * KEY_PITCH, scale)
    return {
        'iconX': x, 'iconY': iconY, 'iconSize': iconSize,
        'labelX': x + labelDx, 'labelY': labelY, 'labelW': labelW, 'labelH': labelH,
        'font': keyLabelFont,
    }


def leftIconGeometry(height, slotIdx, scale=1.0):
    # same idea as colorKeyGeometry() above, for the plain gray left-hand
    # icon cluster (menu/nav/num/info/ok/exit) instead of the color keys
    # - a single source of truth build_footer() uses at skin-build time
    # and a caller can reuse at runtime to reflow icons whose slot
    # depends on which OTHER icons are currently hidden (e.g.
    # E2iPlayerWidget: nav/ok/exit sliding left when menu/info are
    # conditionally hidden). Same real-vs-HD-reference height/scale rule
    # as colorKeyGeometry().
    footerH = footer_height(scale)
    footerY = height - footerH
    return {
        'x': _s(LEFT_ICON_SLOTS[slotIdx], scale),
        'y': footerY + _s(19, scale),
        'w': _s(40, scale),
        'h': _s(26, scale),
    }


def build_footer(height, scale=1.0, iconBase=None, keys=('red', 'green', 'yellow', 'blue'), showMenu=True, showNav=True, showNum=False, showOk=True, showExit=True):
    # height: the screen's own true on-screen height for this tier (e.g.
    # 660/990/1320 for PlayerSelectorWidget's grid mode at HD/FHD/WQHD).
    # keys: which of the 4 standard ActionMap color names get a footer
    # slot - the actual label text is set in Python (self["key_red"] =
    # StaticText(...)) same as before, ConditionalShowHide already hides
    # a slot whose text is empty, so this only needs to list which colors
    # this screen ever uses at all (e.g. Simple list mode still declares
    # all 4 and blanks red/green in Python, so it still passes all 4 here).
    if iconBase is None:
        iconBase = getIconBase()
    footerH = footer_height(scale)
    footerY = height - footerH
    dividerH = _s(2, scale)
    parts = ["""
                <eLabel name="BG_Buttons" position="0,%d" size="e,%d" backgroundColor="#100d0f16" zPosition="-1" />
                <ePixmap pixmap="%s/smallshadowline.png" position="0,%d" size="e,%d" zPosition="2" />""" % (footerY, footerH, iconBase, footerY - dividerH, dividerH)]
    # left icon cluster (menu/nav/ok/exit) - plain gray button icons with
    # the label baked into the pixmap itself (ok.png/exit.png/menu.png),
    # same assets and look as iptvchoicebox.py's already-proven OK/EXIT
    # chrome; key_steuerkreuz.png is the d-pad-only nav hint, kept
    # alongside the explicit OK/EXIT buttons since it's the "how to move"
    # hint while they're "what this button does". MENU keeps its own
    # source="key_menu"/ConditionalShowHide wiring (some caller might
    # blank self["key_menu"] at runtime); nav/OK/EXIT are plain ePixmaps
    # since none of today's callers ever hide them conditionally -
    # whichever of the four are enabled slide into LEFT_ICON_SLOTS in
    # order, so e.g. an OK+EXIT-only footer (no menu, no nav) starts at
    # slot 0 instead of leaving it empty.
    slotIdx = 0
    if showMenu:
        g = leftIconGeometry(height, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <widget source="key_menu" render="Pixmap" pixmap="%s/menu.png" position="%d,%d" size="%d,%d" conditional="key_menu" alphatest="blend">
                    <convert type="ConditionalShowHide" />
                </widget>""" % (iconBase, g['x'], g['y'], g['w'], g['h']))
    if showNav:
        g = leftIconGeometry(height, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <ePixmap pixmap="%s/key_steuerkreuz.png" position="%d,%d" size="%d,%d" alphatest="blend" transparent="1" />""" % (iconBase, g['x'], g['y'], g['w'], g['h']))
    if showNum:
        # "how to type a value" hint, same idea as key_steuerkreuz.png's
        # "how to move"
        g = leftIconGeometry(height, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <ePixmap pixmap="%s/key_0-9.png" position="%d,%d" size="%d,%d" alphatest="blend" transparent="1" />""" % (iconBase, g['x'], g['y'], g['w'], g['h']))
    if showOk:
        g = leftIconGeometry(height, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <ePixmap pixmap="%s/ok.png" position="%d,%d" size="%d,%d" alphatest="blend" transparent="1" />""" % (iconBase, g['x'], g['y'], g['w'], g['h']))
    if showExit:
        g = leftIconGeometry(height, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <ePixmap pixmap="%s/exit.png" position="%d,%d" size="%d,%d" alphatest="blend" transparent="1" />""" % (iconBase, g['x'], g['y'], g['w'], g['h']))
    numLeftIcons = slotIdx
    # width/height and labelDx below are all tuned to the 2-line color-
    # key label (see footer_height()'s comment) and to fit alongside the
    # left icon cluster; the 5px buffer to the next slot's icon is part
    # of KEY_PITCH above. Checked every translation this plugin ships for
    # the 4 strings that actually land here (locale/*/LC_MESSAGES/
    # IPTVPlayer.po): the longest is French "Gestionnaire de
    # Téléchargement" at 30 characters, nowhere near fitting a single
    # 165px line at a legible font size. No `noWrap` attribute is set, so
    # this relies on Enigma2 Label's default wrap-when-it-doesn't-fit
    # behavior.
    #
    # labelDx=25 leaves a 5px gap after the 20px icon at HD.
    #
    # both centered against the taller 2-line label block: label spans
    # footerY+10 to footerY+54 (44 tall, 10px top/bottom margin in the
    # 64px footer); icon (20 tall) centers on that same midpoint.
    slotIdx = 0
    for color in ('red', 'green', 'yellow', 'blue'):
        if color not in keys:
            continue
        geom = colorKeyGeometry(height, numLeftIcons, slotIdx, scale)
        slotIdx += 1
        parts.append("""
                <widget source="key_%s" render="Pixmap" pixmap="%s/%s.png" position="%d,%d" size="%d,%d" alphatest="blend" objectTypes="key_%s,StaticText" transparent="1">
                    <convert type="ConditionalShowHide" />
                </widget>
                <widget source="key_%s" render="Label" position="%d,%d" size="%d,%d" backgroundColor="#000000" font="Regular;%d" foregroundColor="#ffffff" zPosition="+1" valign="center" halign="left" objectTypes="key_%s,StaticText" transparent="1" />""" % (
            color, iconBase, color, geom['iconX'], geom['iconY'], geom['iconSize'], geom['iconSize'], color,
            color, geom['labelX'], geom['labelY'], geom['labelW'], geom['labelH'], geom['font'], color,
        ))
    return "".join(parts)


###################################################
# Auto-scale variant for screens with no fixed-pixel-size content of
# their own (no grid cells/marker PNGs to fight normal auto-scaling) -
# unlike build_header()/build_footer() above, these don't take a `scale`
# argument at all. The caller's <screen> declares resolution="1280,720"
# once, and Enigma2 auto-scales every widget's position/size for FHD/
# WQHD from that single HD-reference block, so only one skin string is
# ever built instead of three per-tier copies.
#
# Both are thin wrappers around build_header()/build_footer() at
# scale=1.0 - that call already produces plain, un-multiplied HD-
# reference numbers (_s(value, 1.0) == value), which is exactly what an
# auto-scaled block needs. Delegating instead of hand-duplicating means
# an auto-scaled screen automatically inherits any future change to the
# tiered chrome too (narrower title, the OK/EXIT/nav/menu icon cluster,
# the 2-line color-key wrap, ...) instead of silently drifting from it.
###################################################

def build_header_auto(iconBase=None, logoWidgetName=None, showLogo=True):
    return build_header(scale=1.0, iconBase=iconBase, logoWidgetName=logoWidgetName, showLogo=showLogo)


def build_footer_auto(height, iconBase=None, keys=(), showMenu=False, showNav=True, showNum=False, showOk=True, showExit=True):
    # showMenu defaults to unavailable here since this auto-scale
    # variant's original caller (IPTVChoiceBoxWidget's chrome=True
    # branch) never bound a menu key. PlayerSelectorWidget's List-/
    # Simple-List mode passes showMenu=True explicitly since MENU is a
    # real, already-used feature there (opens Configuration).
    return build_footer(height, scale=1.0, iconBase=iconBase, keys=keys, showMenu=showMenu, showNav=showNav, showNum=showNum, showOk=showOk, showExit=showExit)
