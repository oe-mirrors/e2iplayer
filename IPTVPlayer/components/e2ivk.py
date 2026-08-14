# -*- coding: utf-8 -*-
#
#  E2iPlayer On Screen Keyboard based on Windows keyboard layouts
#
#  $Id$
#
#
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import NumberActionMap
from enigma import ePoint, eSize, gRGB, eListboxPythonMultiContent, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, getDesktop, getPrevAsciiCode, BT_SCALE
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from Components.Label import Label
from Components.Input import Input
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from Components.config import config, configfile
import skin

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetDefaultLang, GetIconDir, GetE2iPlayerVKLayoutDir, CSearchHistoryHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase
from Plugins.Extensions.IPTVPlayer.components.iptvchoicebox import IPTVChoiceBoxWidget, IPTVChoiceBoxItem
from Plugins.Extensions.IPTVPlayer.components.e2ivksuggestion import AutocompleteSearch

# Global, keyboard-wide search history shown inside the OSK itself (left/right
# arrow from the text field), independent of each host's own "Search history"
# menu item. Stored the same way as those (CSearchHistoryHelper -> SciezkaCache
# cache dir), just under its own file so it doesn't mix with per-host entries.
gVKSearchHistory = CSearchHistoryHelper('e2ivk')


def GetVKFontSize(baseSize):
    # shared by E2iVKSelectionList and E2iVirtualKeyBoard.prepareSkin so the
    # osk_font_size_offset clamp rule only has to live in one place
    offset = config.plugins.iptvplayer.osk_font_size_offset.value
    return max(8, baseSize + offset)


def GetVKOptionItem(text, value, icon=None):
    # IPTVChoiceBoxItem has no icon field of its own; E2iVKOptionsList reads
    # this extra attribute directly (see its buildEntry)
    item = IPTVChoiceBoxItem(text, privateData=value)
    item.icon = icon
    return item


class E2iInput(Input):
    def __init__(self, *args, **kwargs):
        self.e2iTimeoutCallback = None
        Input.__init__(self, *args, **kwargs)

    def timeout(self, *args, **kwargs):
        callCallback = False
        try:
            callCallback = True if self.lastKey != -1 else False
        except Exception:
            printExc()
        try:
            Input.timeout(self, *args, **kwargs)
        except Exception:
            printExc()
        if self.e2iTimeoutCallback:
            self.e2iTimeoutCallback()


class E2iVKSelectionList(IPTVListComponentBase):
    ICONS_FILESNAMES = {'on': 'radio_button_on.png', 'off': 'radio_button_off.png'}

    def __init__(self, withRatioButton=True, applyFontOffset=True):
        IPTVListComponentBase.__init__(self)
        screenwidth = getDesktop(0).size().width()
        # no dedicated WQHD flag set exists - reuse the FHD-tier flags,
        # stretched to the bigger WQHD flagSize by buildEntry()'s BT_SCALE
        if screenwidth >= 2560:
            fontSize = 32
            self.flagsDir = 'e2ivk_hd'
            self.flagSize = (80, 53)
        elif screenwidth == 1920:
            fontSize = 24
            self.flagsDir = 'e2ivk_hd'
            self.flagSize = (60, 40)
        else:
            fontSize = 16
            self.flagsDir = 'e2ivk'
            self.flagSize = (40, 27)
        # osk_font_size_offset is meant to size the on-screen keyboard itself;
        # applyFontOffset=False for uses outside it (the language picker
        # popup), same reasoning as E2iVKOptionsList never applying it
        if applyFontOffset:
            fontSize = GetVKFontSize(fontSize)
        # 14px of padding above the font size matches the original fixed
        # values (24->38, 16->30) and keeps rows from clipping as it scales
        itemHeight = fontSize + 14

        try:
            self.font = skin.fonts["e2ivklistitem"]
        except Exception:
            self.font = ("Regular", fontSize, itemHeight, 0)

        self.l.setFont(0, gFont("Regular", 60))
        self.l.setFont(1, gFont(self.font[0], self.font[1]))
        self.l.setItemHeight(self.font[2])
        self.dictPIX = {}
        # flag pixmaps are keyed by locale (e.g. 'de_DE'), lazily loaded on
        # first use since only ~1/3 of the ~100 layout locales have one
        self.flagPIX = {}
        self.withRatioButton = withRatioButton

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None
        self.flagPIX = {}

    def onCreate(self):
        printDBG('--- onCreate ---')

        if self.withRatioButton:
            self._nullPIX()
            for key in self.dictPIX:
                try:
                    pixFile = self.ICONS_FILESNAMES.get(key, None)
                    if None is not pixFile:
                        self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
                except Exception:
                    printExc()

    def onDestroy(self):
        printDBG('--- onDestroy ---')
        if self.withRatioButton:
            self._nullPIX()

    def _getFlagPixmap(self, locale):
        if locale not in self.flagPIX:
            path = GetIconDir('%s/%s.png' % (self.flagsDir, locale))
            if not fileExists(path):
                path = GetIconDir('%s/missing.png' % self.flagsDir)
            try:
                self.flagPIX[locale] = LoadPixmap(cached=True, path=path)
            except Exception:
                printExc()
                self.flagPIX[locale] = None
        return self.flagPIX[locale]

    def buildEntry(self, item):
        res = [None]
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        try:
            if self.withRatioButton and callable(getattr(item, "get", None)):
                if item['sel']:
                    sel_key = 'on'
                else:
                    sel_key = 'off'
                y = (height - 16) // 2
                flagW, flagH = self.flagSize
                flagX = 24
                flagY = (height - flagH) // 2
                textX = flagX + flagW + 8
                res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item['val'][0]))  # , item.get('color')
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, y, 16, 16, self.dictPIX.get(sel_key, None)))
                flagPix = self._getFlagPixmap(item['val'][1])
                if flagPix is not None:
                    # BT_SCALE stretches the FHD-tier flag asset to flagW/flagH
                    # instead of requiring a pre-rendered WQHD-sized flag set
                    res.append(MultiContentEntryPixmapAlphaBlend(pos=(flagX, flagY), size=(flagW, flagH), png=flagPix, flags=BT_SCALE))
            else:
                res.append((eListboxPythonMultiContent.TYPE_TEXT, 4, 0, width - 4, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item))
        except Exception:
            printExc()
        return res


class E2iVKLanguagePickerList(E2iVKSelectionList):
    # IPTVChoiceBoxWidget's list_class= instantiates with no arguments, so
    # the language-selection popup needs its own subclass rather than
    # passing applyFontOffset=False directly to E2iVKSelectionList
    def __init__(self):
        E2iVKSelectionList.__init__(self, applyFontOffset=False)


class E2iVKOptionsList(IPTVListComponentBase):
    # icon+text rows for the OSK's own MENU/INFO screens, opened through the
    # app's own IPTVChoiceBoxWidget (the same widget used e.g. for movie
    # player / mirror selection) via list_class=, so they match its
    # established look instead of a bespoke skin.
    #
    # The icons used here aren't uniformly sized (the red/green/yellow/blue
    # dots are square, menu.png/key_prevnext.png/etc. are wide rectangles),
    # and only HD/FHD assets exist. buildEntry() renders them via
    # MultiContentEntryPixmapAlphaBlend(flags=BT_SCALE), so every icon is
    # stretched to (iconW, iconH) regardless of its native size - the same
    # mechanism the download manager list uses, just called directly from
    # Python instead of a TemplatedMultiContent skin convert.
    def __init__(self):
        IPTVListComponentBase.__init__(self)
        # osk_font_size_offset intentionally does NOT apply here - it's meant
        # to size the on-screen keyboard itself, not the MENU/INFO popups
        screenwidth = getDesktop(0).size().width()
        if screenwidth >= 2560:
            self.iconW, self.iconH = (80, 51)
            fontSize = 38
            itemHeight = self.iconH + 32
        elif screenwidth == 1920:
            self.iconW, self.iconH = (60, 38)
            fontSize = 28
            itemHeight = self.iconH + 24
        else:
            self.iconW, self.iconH = (40, 26)
            fontSize = 20
            itemHeight = self.iconH + 18
        self.l.setFont(0, gFont("Regular", fontSize))
        self.l.setItemHeight(itemHeight)

    def onCreate(self):
        pass

    def onDestroy(self):
        pass

    def buildEntry(self, item):
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        res = [None]
        icon = getattr(item, 'icon', None)
        textX = self.iconW + 20 if icon is not None else 10
        res.append((eListboxPythonMultiContent.TYPE_TEXT, textX, 0, width - textX - 10, height, 0, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item.name))
        if icon is not None:
            iconY = (height - self.iconH) // 2
            # BT_SCALE stretches the source pixmap to (iconW, iconH) instead of
            # requiring a pre-rendered asset at that exact native size - lets a
            # single HD/FHD icon set cover every resolution tier, including WQHD.
            res.append(MultiContentEntryPixmapAlphaBlend(pos=(8, iconY), size=(self.iconW, self.iconH), png=icon, flags=BT_SCALE))
        return res


class E2iVirtualKeyBoard(Screen):
    FOCUS_KEYBOARD = 0
    FOCUS_SUGGESTIONS = 2
    FOCUS_SEARCH_HISTORY = 3
    SK_NONE = 0
    SK_SHIFT = 1
    SK_CTRL = 2
    SK_ALT = 4
    SK_CAPSLOCK = 8
    KEYIDMAP = [
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
        [16, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29],
        [30, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 42],
        [43, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 55],
        [56, 56, 57, 58, 59, 59, 59, 59, 59, 59, 59, 59, 60, 61, 62],
    ]
    LEFT_KEYS = [1, 16, 30, 43, 56]
    RIGHT_KEYS = [15, 29, 42, 55, 62]
    ALL_VK_LAYOUTS = [('Albanian', 'sq_AL', '0000041c'), ('Arabic (101)', 'ar_SA', '00000401'), ('Arabic (102)', 'ar_SA', '00010401'), ('Arabic (102) AZERTY', 'ar_SA', '00020401'), ('Armenian Eastern', 'hy_AM', '0000042b'), ('Armenian Western', 'hy_AM', '0001042b'), ('Assamese - INSCRIPT', 'as_IN', '0000044d'), ('Azeri Cyrillic', 'az_Cyrl-AZ', '0000082c'), ('Azeri Latin', 'az_Latn-AZ', '0000042c'), ('Bashkir', 'ba_RU', '0000046d'), ('Belarusian', 'be_BY', '00000423'), ('Belgian (Comma)', 'fr_BE', '0001080c'), ('Belgian (Period)', 'nl_BE', '00000813'), ('Belgian French', 'fr_BE', '0000080c'), ('Bengali', 'bn_IN', '00000445'), ('Bengali - INSCRIPT', 'bn_IN', '00020445'), ('Bengali - INSCRIPT (Legacy)', 'bn_IN', '00010445'), ('Bosnian (Cyrillic)', 'bs_Cyrl-BA', '0000201a'), ('Bulgarian', 'bg_BG', '00030402'), ('Bulgarian (Latin)', 'bg_BG', '00010402'), ('Bulgarian (Phonetic Traditional)', 'bg_BG', '00040402'), ('Bulgarian (Phonetic)', 'bg_BG', '00020402'), ('Bulgarian (Typewriter)', 'bg_BG', '00000402'), ('Canadian French', 'en_CA', '00001009'), ('Canadian French (Legacy)', 'fr_CA', '00000c0c'), ('Canadian Multilingual Standard', 'en_CA', '00011009'), ('Chinese (Simplified) - US Keyboard', 'zh_CN', '00000804'), ('Chinese (Simplified, Singapore) - US Keyboard', 'zh_SG', '00001004'), ('Chinese (Traditional) - US Keyboard', 'zh_TW', '00000404'), ('Chinese (Traditional, Hong Kong S.A.R.) - US Keyboard', 'zh_HK', '00000c04'), ('Chinese (Traditional, Macao S.A.R.) - US Keyboard', 'zh_MO', '00001404'), ('Croatian', 'hr_HR', '0000041a'), ('Czech', 'cs_CZ', '00000405'), ('Czech (QWERTY)', 'cs_CZ', '00010405'), ('Czech Programmers', 'cs_CZ', '00020405'), ('Danish', 'da_DK', '00000406'), ('Devanagari - INSCRIPT', 'hi_IN', '00000439'), ('Divehi Phonetic', 'dv_MV', '00000465'), ('Divehi Typewriter', 'dv_MV', '00010465'), ('Dutch', 'nl_NL', '00000413'), ('Estonian', 'et_EE', '00000425'), ('Faeroese', 'fo_FO', '00000438'), ('Finnish', 'fi_FI', '0000040b'), ('Finnish with Sami', 'se_SE', '0001083b'), ('French', 'fr_FR', '0000040c'), ('Gaelic', 'en_IE', '00011809'), ('Georgian', 'ka_GE', '00000437'), ('Georgian (Ergonomic)', 'ka_GE', '00020437'), ('Georgian (QWERTY)', 'ka_GE', '00010437'), ('German', 'de_DE', '00000407'), ('German (IBM)', 'de_DE', '00010407'), ('Greek', 'el_GR', '00000408'), ('Greek (220)', 'el_GR', '00010408'), ('Greek (220) Latin', 'el_GR', '00030408'), ('Greek (319)', 'el_GR', '00020408'), ('Greek (319) Latin', 'el_GR', '00040408'), ('Greek Latin', 'el_GR', '00050408'), ('Greek Polytonic', 'el_GR', '00060408'), ('Greenlandic', 'kl_GL', '0000046f'), ('Gujarati', 'gu_IN', '00000447'), ('Hausa', 'ha_Latn-NG', '00000468'), ('Hebrew', 'he_IL', '0000040d'), ('Hindi Traditional', 'hi_IN', '00010439'), ('Hungarian', 'hu_HU', '0000040e'), ('Hungarian 101-key', 'hu_HU', '0001040e'), ('Icelandic', 'is_IS', '0000040f'), ('Igbo', 'ig_NG', '00000470'), ('Inuktitut - Latin', 'iu_Latn-CA', '0000085d'), ('Inuktitut - Naqittaut', 'iu_Cans-CA', '0001045d'), ('Irish', 'en_IE', '00001809'), ('Italian', 'it_IT', '00000410'), ('Italian (142)', 'it_IT', '00010410'), ('Japanese', 'ja_JP', '00000411'), ('Kannada', 'kn_IN', '0000044b'), ('Kazakh', 'kk_KZ', '0000043f'), ('Khmer', 'km_KH', '00000453'), ('Korean', 'ko_KR', '00000412'), ('Kyrgyz Cyrillic', 'ky_KG', '00000440'), ('Lao', 'lo_LA', '00000454'), ('Latin American', 'es_MX', '0000080a'), ('Latvian', 'lv_LV', '00000426'), ('Latvian (QWERTY)', 'lv_LV', '00010426'), ('Lithuanian', 'lt_LT', '00010427'), ('Lithuanian IBM', 'lt_LT', '00000427'), ('Lithuanian Standard', 'lt_LT', '00020427'), ('Luxembourgish', 'lb_LU', '0000046e'), ('Macedonian (FYROM)', 'mk_MK', '0000042f'), ('Macedonian (FYROM) - Standard', 'mk_MK', '0001042f'), ('Malayalam', 'ml_IN', '0000044c'), ('Maltese 47-Key', 'mt_MT', '0000043a'), ('Maltese 48-Key', 'mt_MT', '0001043a'), ('Maori', 'mi_NZ', '00000481'), ('Marathi', 'mr_IN', '0000044e'), ('Mongolian (Mongolian Script)', 'mn_Mong-CN', '00000850'), ('Mongolian Cyrillic', 'mn_MN', '00000450'), ('Nepali', 'ne_NP', '00000461'), ('Norwegian', 'nb_NO', '00000414'), ('Norwegian with Sami', 'se_NO', '0000043b'), ('Oriya', 'or_IN', '00000448'), ('Pashto (Afghanistan)', 'ps_AF', '00000463'), ('Persian', 'fa_IR', '00000429'), ('Polish (214)', 'pl_PL', '00010415'), ('Polish (Programmers)', 'pl_PL', '00000415'), ('Portuguese', 'pt_PT', '00000816'), ('Portuguese (Brazilian ABNT)', 'pt_BR', '00000416'), ('Portuguese (Brazilian ABNT2)', 'pt_BR', '00010416'), ('Punjabi', 'pa_IN', '00000446'), ('Romanian (Legacy)', 'ro_RO', '00000418'), ('Romanian (Programmers)', 'ro_RO', '00020418'), ('Romanian (Standard)', 'ro_RO', '00010418'), ('Russian', 'ru_RU', '00000419'), ('Russian (Typewriter)', 'ru_RU', '00010419'), ('Sami Extended Finland-Sweden', 'se_SE', '0002083b'), ('Sami Extended Norway', 'se_NO', '0001043b'), ('Serbian (Cyrillic)', 'sr_Cyrl-CS', '00000c1a'), ('Serbian (Latin)', 'sr_Latn-CS', '0000081a'), ('Sesotho sa Leboa', 'nso_ZA', '0000046c'), ('Setswana', 'tn_ZA', '00000432'), ('Sinhala', 'si_LK', '0000045b'), ('Sinhala - Wij 9', 'si_LK', '0001045b'), ('Slovak', 'sk_SK', '0000041b'), ('Slovak (QWERTY)', 'sk_SK', '0001041b'), ('Slovenian', 'sl_SI', '00000424'), ('Sorbian Extended', 'hsb_DE', '0001042e'), ('Sorbian Standard', 'hsb_DE', '0002042e'), ('Sorbian Standard (Legacy)', 'hsb_DE', '0000042e'), ('Spanish', 'es_ES', '0000040a'), ('Spanish Variation', 'es_ES', '0001040a'), ('Swedish', 'sv_SE', '0000041d'), ('Swedish with Sami', 'se_SE', '0000083b'), ('Swiss French', 'fr_CH', '0000100c'), ('Swiss German', 'de_CH', '00000807'), ('Syriac', 'syr_SY', '0000045a'), ('Syriac Phonetic', 'syr_SY', '0001045a'), ('Tajik', 'tg_Cyrl-TJ', '00000428'), ('Tamil', 'ta_IN', '00000449'), ('Tatar', 'tt_RU', '00000444'), ('Telugu', 'te_IN', '0000044a'), ('Thai Kedmanee', 'th_TH', '0000041e'), ('Thai Kedmanee (non-ShiftLock)', 'th_TH', '0002041e'), ('Thai Pattachote', 'th_TH', '0001041e'), ('Thai Pattachote (non-ShiftLock)', 'th_TH', '0003041e'), ('Tibetan (PRC)', 'bo_CN', '00000451'), ('Turkish F', 'tr_TR', '0001041f'), ('Turkish Q', 'tr_TR', '0000041f'), ('Turkmen', 'tk_TM', '00000442'), ('US', 'en_US', '00000409'), ('US English Table for IBM Arabic 238_L', 'en_US', '00050409'), ('Ukrainian', 'uk_UA', '00000422'), ('Ukrainian (Enhanced)', 'uk_UA', '00020422'), ('United Kingdom', 'en_GB', '00000809'), ('United Kingdom Extended', 'cy_GB', '00000452'), ('United States-Dvorak', 'en_US', '00010409'), ('United States-Dvorak for left hand', 'en_US', '00030409'), ('United States-Dvorak for right hand', 'en_US', '00040409'), ('United States-International', 'en_US', '00020409'), ('Urdu', 'ur_PK', '00000420'), ('Uyghur', 'ug_CN', '00010480'), ('Uyghur (Legacy)', 'ug_CN', '00000480'), ('Uzbek Cyrillic', 'uz_Cyrl-UZ', '00000843'), ('Vietnamese', 'vi_VN', '0000042a'), ('Wolof', 'wo_SN', '00000488'), ('Yakut', 'sah_RU', '00000485'), ('Yoruba', 'yo_NG', '0000046a')]
    DEFAULT_VK_LAYOUT = {'layout': {2: {0: '`', 1: '~', 8: '`', 9: '~'}, 3: {0: '1', 1: '!', 6: '\xa1', 7: '\xb9', 8: '1', 9: '!', 14: '\xa1', 15: '\xb9'}, 4: {0: '2', 1: '@', 6: '\xb2', 8: '2', 9: '@', 14: '\xb2'}, 5: {0: '3', 1: '#', 6: '\xb3', 8: '3', 9: '#', 14: '\xb3'}, 6: {0: '4', 1: '$', 6: '\xa4', 7: '\xa3', 8: '4', 9: '$', 14: '\xa4', 15: '\xa3'}, 7: {0: '5', 1: '%', 6: '\\u20ac', 8: '5', 9: '%', 14: '\\u20ac'}, 8: {0: '6', 1: '^', 6: '\xbc', 8: '6', 9: '^', 14: '\xbc'}, 9: {0: '7', 1: '&', 6: '\xbd', 8: '7', 9: '&', 14: '\xbd'}, 10: {0: '8', 1: '*', 6: '\xbe', 8: '8', 9: '*', 14: '\xbe'}, 11: {0: '9', 1: '(', 6: '\\u2018', 8: '9', 9: '(', 14: '\\u2018'}, 12: {0: '0', 1: ')', 6: '\\u2019', 8: '0', 9: ')', 14: '\\u2019'}, 13: {0: '-', 1: '_', 6: '\xa5', 8: '-', 9: '_', 14: '\xa5'}, 14: {0: '=', 1: '+', 6: '\xd7', 7: '\xf7', 8: '=', 9: '+', 14: '\xd7', 15: '\xf7'}, 17: {0: 'q', 1: 'Q', 6: '\xe4', 7: '\xc4', 8: 'Q', 9: 'q', 14: '\xc4', 15: '\xe4'}, 18: {0: 'w', 1: 'W', 6: '\xe5', 7: '\xc5', 8: 'W', 9: 'w', 14: '\xc5', 15: '\xe5'}, 19: {0: 'e', 1: 'E', 6: '\xe9', 7: '\xc9', 8: 'E', 9: 'e', 14: '\xc9', 15: '\xe9'}, 20: {0: 'r', 1: 'R', 6: '\xae', 8: 'R', 9: 'r', 14: '\xae'}, 21: {0: 't', 1: 'T', 6: '\xfe', 7: '\xde', 8: 'T', 9: 't', 14: '\xde', 15: '\xfe'}, 22: {0: 'y', 1: 'Y', 6: '\xfc', 7: '\xdc', 8: 'Y', 9: 'y', 14: '\xdc', 15: '\xfc'}, 23: {0: 'u', 1: 'U', 6: '\xfa', 7: '\xda', 8: 'U', 9: 'u', 14: '\xda', 15: '\xfa'}, 24: {0: 'i', 1: 'I', 6: '\xed', 7: '\xcd', 8: 'I', 9: 'i', 14: '\xcd', 15: '\xed'}, 25: {0: 'o', 1: 'O', 6: '\xf3', 7: '\xd3', 8: 'O', 9: 'o', 14: '\xd3', 15: '\xf3'}, 26: {0: 'p', 1: 'P', 6: '\xf6', 7: '\xd6', 8: 'P', 9: 'p', 14: '\xd6', 15: '\xf6'}, 27: {0: '[', 1: '{', 2: '\x1b', 6: '\xab', 8: '[', 9: '{', 10: '\x1b', 14: '\xab'}, 28: {0: ']', 1: '}', 2: '\x1d', 6: '\xbb', 8: ']', 9: '}', 10: '\x1d', 14: '\xbb'}, 31: {0: 'a', 1: 'A', 6: '\xe1', 7: '\xc1', 8: 'A', 9: 'a', 14: '\xc1', 15: '\xe1'}, 32: {0: 's', 1: 'S', 6: '\xdf', 7: '\xa7', 8: 'S', 9: 's', 14: '\xa7', 15: '\xdf'}, 33: {0: 'd', 1: 'D', 6: '\xf0', 7: '\xd0', 8: 'D', 9: 'd', 14: '\xd0', 15: '\xf0'}, 34: {0: 'f', 1: 'F', 8: 'F', 9: 'f'}, 35: {0: 'g', 1: 'G', 8: 'G', 9: 'g'}, 36: {0: 'h', 1: 'H', 8: 'H', 9: 'h'}, 37: {0: 'j', 1: 'J', 8: 'J', 9: 'j'}, 38: {0: 'k', 1: 'K', 8: 'K', 9: 'k'}, 39: {0: 'l', 1: 'L', 6: '\xf8', 7: '\xd8', 8: 'L', 9: 'l', 14: '\xd8', 15: '\xf8'}, 40: {0: ';', 1: ':', 6: '\xb6', 7: '\xb0', 8: ';', 9: ':', 14: '\xb6', 15: '\xb0'}, 41: {0: "'", 1: '"', 6: '\xb4', 7: '\xa8', 8: "'", 9: '"', 14: '\xb4', 15: '\xa8'}, 44: {0: 'z', 1: 'Z', 6: '\xe6', 7: '\xc6', 8: 'Z', 9: 'z', 14: '\xc6', 15: '\xe6'}, 45: {0: 'x', 1: 'X', 8: 'X', 9: 'x'}, 46: {0: 'c', 1: 'C', 6: '\xa9', 7: '\xa2', 8: 'C', 9: 'c', 14: '\xa2', 15: '\xa9'}, 47: {0: 'v', 1: 'V', 8: 'V', 9: 'v'}, 48: {0: 'b', 1: 'B', 8: 'B', 9: 'b'}, 49: {0: 'n', 1: 'N', 6: '\xf1', 7: '\xd1', 8: 'N', 9: 'n', 14: '\xd1', 15: '\xf1'}, 50: {0: 'm', 1: 'M', 6: '\xb5', 8: 'M', 9: 'm', 14: '\xb5'}, 51: {0: ',', 1: '<', 6: '\xe7', 7: '\xc7'}, 52: {0: '.', 1: '>', 8: '.', 9: '>'}, 53: {0: '/', 1: '?', 6: '\xbf', 8: '/', 9: '?', 14: '\xbf'}, 54: {0: '\\', 1: '|', 2: '\x1c', 6: '\xac', 7: '\xa6', 8: '\\', 9: '|', 10: '\x1c', 14: '\xac', 15: '\xa6'}, 59: {0: ' ', 1: ' ', 2: ' ', 8: ' ', 9: ' ', 10: ' '}}, 'name': 'English (United States)', 'locale': 'en-US', 'id': '00020409', 'deadkeys': {'~': {'a': '\xe3', 'A': '\xc3', ' ': '~', 'O': '\xd5', 'N': '\xd1', 'o': '\xf5', 'n': '\xf1'}, '`': {'a': '\xe0', 'A': '\xc0', 'e': '\xe8', ' ': '`', 'i': '\xec', 'o': '\xf2', 'I': '\xcc', 'u': '\xf9', 'O': '\xd2', 'E': '\xc8', 'U': '\xd9'}, '"': {'a': '\xe4', 'A': '\xc4', 'e': '\xeb', ' ': '"', 'i': '\xef', 'o': '\xf6', 'I': '\xcf', 'u': '\xfc', 'O': '\xd6', 'y': '\xff', 'E': '\xcb', 'U': '\xdc'}, "'": {'a': '\xe1', 'A': '\xc1', 'c': '\xe7', 'e': '\xe9', ' ': "'", 'i': '\xed', 'C': '\xc7', 'o': '\xf3', 'I': '\xcd', 'u': '\xfa', 'O': '\xd3', 'y': '\xfd', 'E': '\xc9', 'U': '\xda', 'Y': '\xdd'}, '^': {'a': '\xe2', 'A': '\xc2', 'e': '\xea', ' ': '^', 'i': '\xee', 'o': '\xf4', 'I': '\xce', 'u': '\xfb', 'O': '\xd4', 'E': '\xca', 'U': '\xdb'}}, 'desc': 'United States-International'}

    def prepareSkin(self):
        # full screen
        sz_w = getDesktop(0).size().width()
        sz_h = getDesktop(0).size().height()

        self.fullHD = getDesktop(0).size().width() == 1920
        self.isWQHD = getDesktop(0).size().width() >= 2560

        if self.isWQHD:
            bw = bh = 95
            inputFontSize = GetVKFontSize(44)
            headerFontSize = GetVKFontSize(33)
            keyFontRegular, keyFontBig = GetVKFontSize(33), GetVKFontSize(47)
            # vkey_left/right/delete.png are cropped tight to their glyph
            # (no padding, like b.png), so these are real box sizes now, not
            # inflated to compensate for mostly-transparent source canvases -
            # arrowIcon's ~4:3, deleteIcon's ~6:5, matching the crops' shape
            arrowIconW, arrowIconH = 65, 49
            deleteIconW, deleteIconH = 65, 55
            # b.png is now vkey_delete.png rotated 180 degrees, so it shares
            # its box shape instead of the old wide-rectangle 43x27
            backspaceIconW, backspaceIconH = deleteIconW, deleteIconH
        elif self.fullHD:
            bw = bh = 70
            inputFontSize = GetVKFontSize(33)
            headerFontSize = GetVKFontSize(25)
            keyFontRegular, keyFontBig = GetVKFontSize(25), GetVKFontSize(35)
            arrowIconW, arrowIconH = 48, 36
            deleteIconW, deleteIconH = 48, 40
            backspaceIconW, backspaceIconH = deleteIconW, deleteIconH
        else:
            bw = bh = 50
            inputFontSize = GetVKFontSize(26)
            headerFontSize = GetVKFontSize(20)
            keyFontRegular, keyFontBig = GetVKFontSize(20), GetVKFontSize(30)
            arrowIconW, arrowIconH = 34, 26
            deleteIconW, deleteIconH = 34, 29
            backspaceIconW, backspaceIconH = deleteIconW, deleteIconH
        textAlign = config.plugins.iptvplayer.osk_searchfield_align.value

        # cached for _applyLanguageIconLayout()'s live osk_show_flags updates,
        # which need the same bw/bh this method used without recomputing them
        self._gridBW, self._gridBH = bw, bh
        langIconW, langIconH, langIconOffsetY, langAreaW = self._getLanguageIconGeometry()

        # top/bottom chrome bar (logo/title + color key hint footer, matching
        # the player's shared screen design - see iptvplayerwidget.py). Sized
        # independently of bw/bh since the button grid itself has no WQHD
        # tier yet (out of scope here).
        if self.isWQHD:
            chromeH, logoW, logoH, dotSize, chromeFontSize = 95, 200, 80, 40, GetVKFontSize(40)
        elif self.fullHD:
            chromeH, logoW, logoH, dotSize, chromeFontSize = 70, 150, 60, 30, GetVKFontSize(30)
        else:
            chromeH, logoW, logoH, dotSize, chromeFontSize = 50, 100, 40, 20, GetVKFontSize(22)

        x = (sz_w - 15 * bw) / 2
        # Shifted up by chromeH on top of the original "- 7 * bh" (not "- 6",
        # even though MENU/INFO no longer use the 7th row slot below the
        # grid - trying to reclaim that space made the grid math too fragile
        # to verify without a live device, so it's left as an unused gap
        # instead). This guarantees grid bottom (y + 7*bh) lines up exactly
        # with the bottom bar's top (sz_h - chromeH), with no overlap.
        y = sz_h - 7 * bh - chromeH
        self._gridX, self._gridY = x, y

        bg_color = config.plugins.iptvplayer.osk_background_color.value
        bg_color = ' backgroundColor="%s" ' % bg_color if bg_color else ''

        skinTab = ["""<screen position="center,center" flags="wfNoBorder" size="%d,%d" title="E2iPlayer virtual keyboard" %s >""" % (sz_w, sz_h, bg_color)]

        def _addPixmapWidget(name, x, y, w, h, p):
            # scale="1" stretches whatever source pixmap is loaded into this
            # box; a no-op when the box already matches the asset's native
            # size (the HD/FHD tiers), but lets WQHD reuse the FHD assets.
            skinTab.append('<widget name="%s" zPosition="%d" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" scale="1" />' % (name, p, x, y, w, h))

        def _addMarker(name, x, y, w, h, p, color):
            skinTab.append('<widget name="%s" zPosition="%d" position="%d,%d" size="%d,%d" noWrap="1" font="Regular;2" valign="center" halign="center" foregroundColor="%s" backgroundColor="%s" />' % (name, p, x, y, w, h, color, color))

        def _addButton(name, x, y, w, h, p):
            _addPixmapWidget(name, x, y, w, h, p)
            if name in [1, 16, 29, 30, 42, 43, 55, 57, 58, 60]:
                font = keyFontRegular
                color = '#1688b2'
                align = 'center'
            elif name in [61, 62]:
                font = keyFontBig
                color = '#1688b2'
                align = 'center'
            elif name == 56:
                font = keyFontRegular
                color = '#1688b2'
                align = 'left'
                x += langAreaW
                w -= langAreaW
            else:
                font = keyFontRegular
                color = '#404551'
                align = 'center'
            skinTab.append('<widget name="_%s" zPosition="%d" position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="%s" foregroundColor="#ffffff" backgroundColor="%s" />' % (name, p + 2, x, y, w, h, font, align, color))

        # Top bar: logo + title, matching the player's shared screen design.
        # smallshadowline is a static divider image, so it's a plain ePixmap
        # (like the rest of the player uses it) rather than a Python-bound
        # widget - only content that actually varies needs the latter.
        chromeResDir = 'FHD' if (self.fullHD or self.isWQHD) else 'HD'
        shadowline = '/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/icons/%s/smallshadowline.png' % chromeResDir
        skinTab.append('<eLabel name="vk_BG_Title" position="0,0" size="%d,%d" backgroundColor="#100d0f16" zPosition="-1" />' % (sz_w, chromeH))
        _addPixmapWidget('vk_logo', 12, (chromeH - logoH) // 2, logoW, logoH, 1)
        skinTab.append('<widget name="vk_title" zPosition="1" position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="left" foregroundColor="#ffffff" backgroundColor="#000000" />' % (logoW + 24, 0, sz_w - logoW - 44, chromeH, chromeFontSize))
        skinTab.append('<ePixmap pixmap="%s" position="0,%d" size="%d,2" scale="1" zPosition="2" />' % (shadowline, chromeH, sz_w))

        # NVK shows a titled box above the search field, search history and
        # suggestions panel alike, each sitting with a small visible gap
        # above the content below it rather than flush against it. Match
        # that look here for all three: same white-box style as
        # left_header/right_header below, and a few px shaved off the
        # bottom of each header's height (top position unchanged) to leave
        # that gap - reused by left_header/right_header further down.
        headerGap = 4
        headerBoxH = bh - 7 * 2 - headerGap
        skinTab.append('<widget name="header" zPosition="%d" position="%d,%d" size="%d,%d"  transparent="0" noWrap="1" font="Regular;%s" valign="center" halign="left" foregroundColor="#000000" backgroundColor="#ffffff" />' % (2, x + 5, y - (bh - 7 * 2), 15 * bw - 10, headerBoxH, headerFontSize))
        skinTab.append('<widget name="text"   zPosition="%d" position="%d,%d" size="%d,%d"  transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="%s" />' % (2, x + 5, y + 7, 15 * bw - 10, bh - 7 * 2, inputFontSize, textAlign))
        _addPixmapWidget(0, x, y, 15 * bw, bh, 1)
        _addPixmapWidget('e_m', 0, 0, 15 * bw, bh, 5)
        _addPixmapWidget('k_m', 0, 0, bw, bh, 5)
        _addPixmapWidget('k2_m', 0, 0, bw * 2, bh, 5)
        _addPixmapWidget('k3_m', 0, 0, bw * 8, bh, 5)

        for i in range(0, 15):
            _addButton(i + 1, x + bw * i, y + 10 + bh * 1, bw, bh, 1)
        _addPixmapWidget('b', x + bw * 14 + (bw - backspaceIconW) / 2, y + 10 + bh * 1 + (bh - backspaceIconH) / 2, backspaceIconW, backspaceIconH, 3)  # backspace icon

        _addButton(16, x, y + 10 + bh * 2, bw * 2, bh, 1)
        for i in range(0, 14):
            _addButton(i + 17, x + bw * (i + 2), y + 10 + bh * 2, bw, bh, 1)

        _addButton(30, x, y + 10 + bh * 3, bw * 2, bh, 1)
        for i in range(0, 13):
            _addButton(i + 31, x + bw * (i + 2), y + 10 + bh * 3, bw, bh, 1)
        _addButton(42, x + bw * 13, y + 10 + bh * 3, bw * 2, bh, 1)
        _addPixmapWidget('vkey_delete', x + bw * 14 + (bw - deleteIconW) / 2, y + 10 + bh * 2 + (bh - deleteIconH) / 2, deleteIconW, deleteIconH, 3)  # Del key (29) icon

        _addButton(43, x, y + 10 + bh * 4, bw * 2, bh, 1)
        for i in range(0, 13):
            _addButton(i + 44, x + bw * (i + 2), y + 10 + bh * 4, bw, bh, 1)
        _addButton(55, x + bw * 13, y + 10 + bh * 4, bw * 2, bh, 1)

        _addPixmapWidget('l', x + 10, y + 10 + bh * 5 + langIconOffsetY, langIconW, langIconH, 3)  # language icon (flag or globe)
        _addButton(56, x, y + 10 + bh * 5, bw * 2, bh, 1)
        _addButton(57, x + bw * 2, y + 10 + bh * 5, bw, bh, 1)
        _addButton(58, x + bw * 3, y + 10 + bh * 5, bw, bh, 1)
        _addButton(59, x + bw * 4, y + 10 + bh * 5, bw * 8, bh, 1)
        _addButton(60, x + bw * 12, y + 10 + bh * 5, bw, bh, 1)
        _addButton(61, x + bw * 13, y + 10 + bh * 5, bw, bh, 1)
        _addButton(62, x + bw * 14, y + 10 + bh * 5, bw, bh, 1)
        _addPixmapWidget('vkey_left', x + bw * 13 + (bw - arrowIconW) / 2, y + 10 + bh * 5 + (bh - arrowIconH) / 2, arrowIconW, arrowIconH, 3)  # left key (61) icon
        _addPixmapWidget('vkey_right', x + bw * 14 + (bw - arrowIconW) / 2, y + 10 + bh * 5 + (bh - arrowIconH) / 2, arrowIconW, arrowIconH, 3)  # right key (62) icon

        # Backspace
        _addMarker('m_0', x + bw * 14 + 10, y + 10 + bh * 1 + (bh - 10), bw - 20, 3, 2, '#ed1c24')

        # Shift
        _addMarker('m_1', x + 10, y + 10 + bh * 4 + (bh - 10), bw * 2 - 20, 3, 2, '#3f48cc')
        _addMarker('m_2', x + bw * 13 + 10, y + 10 + bh * 4 + (bh - 10), bw * 2 - 20, 3, 2, '#3f48cc')

        # Alt
        _addMarker('m_3', x + bw * 3 + 10, y + 10 + bh * 5 + (bh - 10), bw - 20, 3, 2, '#fff200')
        _addMarker('m_4', x + bw * 12 + 10, y + 10 + bh * 5 + (bh - 10), bw - 20, 3, 2, '#fff200')

        # Enter
        _addMarker('m_5', x + bw * 13 + 10, y + 10 + bh * 3 + (bh - 10), bw * 2 - 20, 3, 2, '#22b14c')

        # Bottom bar: MENU/INFO hints on the left, then this keyboard's own
        # RED/GREEN/YELLOW/BLUE bindings (Backspace/Enter/AltGr/Shift) - all
        # in the one bar, matching how the rest of the player groups its
        # generic key hints and color buttons together (see
        # iptvplayerwidget.py, iptvdmui.py) instead of a separate row.
        if self.isWQHD:
            hintIconW, hintIconH = (80, 51)
        elif self.fullHD:
            hintIconW, hintIconH = (60, 38)
        else:
            hintIconW, hintIconH = (40, 26)
        barY = sz_h - chromeH
        skinTab.append('<eLabel name="vk_BG_Buttons" position="0,%d" size="%d,%d" backgroundColor="#100d0f16" zPosition="-1" />' % (barY, sz_w, chromeH))
        skinTab.append('<ePixmap pixmap="%s" position="0,%d" size="%d,2" scale="1" zPosition="2" />' % (shadowline, barY, sz_w))

        hintIconY = barY + (chromeH - hintIconH) // 2
        infoIconX = 20 + hintIconW + 20
        _addPixmapWidget('menu_icon', 20, hintIconY, hintIconW, hintIconH, 3)
        _addPixmapWidget('info_icon', infoIconX, hintIconY, hintIconW, hintIconH, 3)

        colorStartX = infoIconX + hintIconW + 40
        segW = (sz_w - colorStartX) // 4
        dotY = barY + (chromeH - dotSize) // 2
        for i, color in enumerate(('red', 'green', 'yellow', 'blue')):
            segX = colorStartX + i * segW
            _addPixmapWidget('vk_key_%s_icon' % color, segX, dotY, dotSize, dotSize, 3)
            skinTab.append('<widget name="vk_key_%s" zPosition="3" position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="left" foregroundColor="#ffffff" backgroundColor="#000000" />' % (color, segX + dotSize + 10, barY, segW - dotSize - 30, chromeH, chromeFontSize))

        # Left list
        skinTab.append('<widget name="left_header" zPosition="2" position="%d,%d" size="%d,%d"  transparent="0" noWrap="1" font="Regular;%d" valign="center" halign="center" foregroundColor="#000000" backgroundColor="#ffffff" />' % (x - bw * 5 - 5, y - (bh - 7 * 2), bw * 5, headerBoxH, headerFontSize))
        skinTab.append('<widget name="left_list"   zPosition="1"  position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand" transparent="0"  backgroundColor="#3f4450" enableWrapAround="1" />' % (x - bw * 5 - 5, y, bw * 5, 6 * bh + 10))

        # Right list
        if self.autocomplete:
            skinTab.append('<widget name="right_header" zPosition="2" position="%d,%d" size="%d,%d"  transparent="0" noWrap="1" font="Regular;%d" valign="center" halign="center" foregroundColor="#000000" backgroundColor="#ffffff" />' % (x + bw * 15 + 5, y - (bh - 7 * 2), bw * 5, headerBoxH, headerFontSize))
            skinTab.append('<widget name="right_list"   zPosition="1"  position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand" transparent="0"  backgroundColor="#3f4450" enableWrapAround="1" />' % (x + bw * 15 + 5, y, bw * 5, 6 * bh + 10))

        skinTab.append('</screen>')
        return '\n'.join(skinTab)

    def __init__(self, session, title="", text="", additionalParams={}):
        self.session = session

        # autocomplete engine
        self.autocomplete = additionalParams.get('autocomplete')
        self.isAutocompleteEnabled = False
        # only set when the panel above was already built with a provider;
        # lets _refreshSuggestionsProvider() swap it live when the "Default
        # suggestions provider" / "Allow host to override suggestions
        # provider" settings change without closing the keyboard
        self.suggestionsProviderFactory = additionalParams.get('resolve_suggestions_provider')

        # None unless a caller explicitly supplies its own list; when set it
        # takes priority over the live config value (see the
        # searchHistoryEnabled/searchHistory properties below). Read live
        # rather than cached once so toggling "Show search history" in
        # Settings takes effect immediately on the already-open keyboard.
        self._explicitSearchHistory = additionalParams.get('search_history')

        self.skin = self.prepareSkin()

        Screen.__init__(self, session)
        self.onLayoutFinish.append(self.setGraphics)
        self.onShown.append(self.onWindowShow)
        self.onClose.append(self.__onClose)

        self["actions"] = NumberActionMap(["WizardActions", "DirectionActions", "ColorActions", "MenuActions", "E2iPlayerVKActions", "KeyboardInputActions", "InputBoxActions", "InputAsciiActions"],
        {
            "gotAsciiCode": self.keyGotAscii,
            "ok": self.keyOK,
            "ok_repeat": self.keyOK,
            "menu": self.keyMenu,
            "info": self.keyHelp,
            "back": self.keyBack,
            "left": self.keyLeft,
            "right": self.keyRight,
            "up": self.keyUp,
            "down": self.keyDown,
            "red": self.keyRed,
            "red_repeat": self.keyRed,
            "green": self.keyGreen,
            "yellow": self.keyYellow,
            "blue": self.keyBlue,
            "deleteBackward": self.backClicked,
            "deleteForward": self.forwardClicked,
            "pageUp": self.cursorRight,
            "pageDown": self.cursorLeft,
            "vk_prevpanel": self.cyclePanelPrev,
            "vk_nextpanel": self.cyclePanelNext,
            "vk_space": self.keyFastForward,
            "vk_cleartext": self.keyRewind,
            "1": self.keyNumberGlobal,
            "2": self.keyNumberGlobal,
            "3": self.keyNumberGlobal,
            "4": self.keyNumberGlobal,
            "5": self.keyNumberGlobal,
            "6": self.keyNumberGlobal,
            "7": self.keyNumberGlobal,
            "8": self.keyNumberGlobal,
            "9": self.keyNumberGlobal,
            "0": self.keyNumberGlobal,
        }, -2)

        # Left list
        self['left_header'] = Label(" ")
        self['left_list'] = E2iVKSelectionList()

        # Right list
        if self.autocomplete:
            self['right_header'] = Label(" ")
            self['right_list'] = E2iVKSelectionList(False)
        self.isSuggestionVisible = None

        self.graphics = {}
        # no dedicated WQHD button art exists - WQHD reuses the e2ivk_hd
        # (FHD-tier) set too, stretched to the bigger WQHD button boxes by
        # scale="1" on the pixmap widgets that display them
        keyArtDir = 'e2ivk_hd' if (self.fullHD or self.isWQHD) else 'e2ivk'
        for key in ['pb', 'pr', 'pg', 'py', 'l', 'b', 'e', 'e_m', 'k', 'k_m', 'k_s', 'k2_m', 'k2_s', 'k3', 'k3_m', 'vkey_left', 'vkey_right', 'vkey_delete']:
            self.graphics[key] = LoadPixmap(GetIconDir('%s/%s.png' % (keyArtDir, key)))
        # footer hints (MENU/INFO): shared icon set, not part of the e2ivk[_hd] set above
        # no dedicated WQHD assets exist - WQHD reuses FHD icons, stretched to
        # the target box by scale="1" (skin widgets) / BT_SCALE (option lists)
        resDir = 'FHD' if (self.fullHD or self.isWQHD) else 'HD'
        self.graphics['menu'] = LoadPixmap(GetIconDir('%s/menu.png' % resDir))
        self.graphics['info'] = LoadPixmap(GetIconDir('%s/info.png' % resDir))
        # top/bottom chrome bar: logo + color key hints, same icon set/resDir
        self.graphics['vk_logo'] = LoadPixmap(GetIconDir('%s/iptvlogo.png' % resDir))
        for color in ('red', 'green', 'yellow', 'blue'):
            self.graphics['vk_%s' % color] = LoadPixmap(GetIconDir('%s/%s.png' % (resDir, color)))

        for i in range(0, 63):
            self[str(i)] = Cover3()

        for key in ['l', 'b', 'e_m', 'k_m', 'k2_m', 'k3_m', 'vkey_left', 'vkey_right', 'vkey_delete']:
            self[key] = Cover3()

        # footer hints, showing that MENU/INFO can be used in this screen
        self['menu_icon'] = Cover3()
        self['info_icon'] = Cover3()

        # top/bottom chrome bar, matching the player's shared screen design
        # (logo/title bar + color key hint footer - see iptvplayerwidget.py)
        self['vk_logo'] = Cover3()
        self['vk_title'] = Label(_("E2iPlayer virtual keyboard"))
        self['vk_key_red_icon'] = Cover3()
        self['vk_key_green_icon'] = Cover3()
        self['vk_key_yellow_icon'] = Cover3()
        self['vk_key_blue_icon'] = Cover3()
        self['vk_key_red'] = Label(_("Backspace"))
        self['vk_key_green'] = Label(_("Enter"))
        self['vk_key_yellow'] = Label(_("AltGr"))
        self['vk_key_blue'] = Label(_("Shift"))

        for i in range(1, 63):
            self['_%s' % i] = Label(" ")

        for m in range(6):
            self['m_%d' % m] = Label(" ")

        self.graphicsMap = {'0': 'e', '1': 'k_s', '15': 'k_s', '29': 'k_s', '57': 'k_s', '58': 'k_s', '60': 'k_s', '61': 'k_s', '62': 'k_s', '59': 'k3',
                            '16': 'k2_s', '30': 'k2_s', '42': 'k2_s', '43': 'k2_s', '55': 'k2_s', '56': 'k2_s'}

        self.markerMap = {'0': 'e_m', '59': 'k3_m', '16': 'k2_m', '30': 'k2_m', '42': 'k2_m', '43': 'k2_m', '55': 'k2_m', '56': 'k2_m'}

        self.header = title if title else _('Enter the text')
        self.startText = text

        self["text"] = E2iInput(text="")
        self["header"] = Label(" ")

        self.colMax = len(self.KEYIDMAP[0])
        self.rowMax = len(self.KEYIDMAP)

        self.rowIdx = 0
        self.colIdx = 0

        self.colors = {'normal': gRGB(int('ffffff', 0x10)), 'selected': gRGB(int('39b54a', 0x10)), 'deadkey': gRGB(int('0275a0', 0x10)), 'ligature': gRGB(int('ed1c24', 0x10)), 'inactive': gRGB(int('979697', 0x10))}

        self.specialKeyState = self.SK_NONE
        self.currentVKLayout = self.DEFAULT_VK_LAYOUT
        self.selectedVKLayoutId = config.plugins.iptvplayer.osk_layout.value
        self.vkRequestedId = additionalParams.get('vk_layout_id', '')
        self.deadKey = ''
        self.focus = self.FOCUS_KEYBOARD

    @property
    def searchHistoryEnabled(self):
        if self._explicitSearchHistory is not None:
            return True
        return config.plugins.iptvplayer.osk_allow_search_history.value

    @property
    def searchHistory(self):
        if self._explicitSearchHistory is not None:
            return self._explicitSearchHistory
        if not self.searchHistoryEnabled:
            return []
        return gVKSearchHistory.getHistoryList()

    def __onClose(self):
        self.onClose.remove(self.__onClose)
        self["text"].e2iTimeoutCallback = None
        if self.autocomplete:
            self.autocomplete.term()

        if self.selectedVKLayoutId != config.plugins.iptvplayer.osk_layout.value:
            config.plugins.iptvplayer.osk_layout.value = self.selectedVKLayoutId
            config.plugins.iptvplayer.osk_layout.save()
            configfile.save()

    def getKeyboardLayoutItem(self, vkLayoutId):
        retItem = None
        for item in self.ALL_VK_LAYOUTS:
            if vkLayoutId == item[2]:
                retItem = item
                break
        return retItem

    def onWindowShow(self):
        self.onShown.remove(self.onWindowShow)
        self.setTitle(_('Virtual Keyboard'))
        # a couple of leading spaces, not a position change - keeps this
        # box's edges flush with the input field/left_header below it,
        # just nudges the text off the box's left edge a bit
        self["header"].setText("  " + self.header)

        # Left list
        self['left_list'].setSelectionState(False)
        self['left_header'].hide()
        self['left_list'].hide()
        self.showSearchHistory()

        # Right list
        if self.autocomplete:
            self['right_header'].setText(self.autocomplete.getProviderName())
            self['right_list'].setSelectionState(False)
            self['right_header'].hide()
            self['right_list'].hide()

        vkLayoutId = self.vkRequestedId if self.vkRequestedId else self.selectedVKLayoutId
        if vkLayoutId == '':
            e2Locale = GetDefaultLang(True)
            langMap = {'pl_PL': '00000415', 'en_EN': '00020409'}
            vkLayoutId = langMap.get(e2Locale, '')

            if vkLayoutId == '':
                for item in self.ALL_VK_LAYOUTS:
                    if e2Locale == item[1]:
                        vkLayoutId = item[2]
                        break

            if vkLayoutId == '':
                e2lang = GetDefaultLang() + '_'
                for item in self.ALL_VK_LAYOUTS:
                    if item[1].startswith(e2lang):
                        vkLayoutId = item[2]
                        break

        if not self.getKeyboardLayoutItem(vkLayoutId):
            vkLayoutId = self.DEFAULT_VK_LAYOUT['id']

        self.loadKeyboardLayout(vkLayoutId)
        self.isAutocompleteEnabled = self.autocomplete is not None
        self.setText(self.startText)

    def setText(self, text):
        self["text"].setText(text)
        self["text"].right()
        self["text"].currPos = len(text)
        self["text"].right()
        self.textUpdated()

    def setGraphics(self):
        self.onLayoutFinish.remove(self.setGraphics)
        self["text"].e2iTimeoutCallback = self.textUpdated

        for i in range(0, 63):
            key = self.graphicsMap.get(str(i), 'k')
            self[str(i)].setPixmap(self.graphics[key])

        for key in ['e_m', 'k_m', 'k2_m', 'k3_m']:
            self[key].hide()
            self[key].setPixmap(self.graphics[key])

        self['b'].setPixmap(self.graphics['b'])
        # 'l' (language icon) is set dynamically from setVKLayout() instead -
        # it depends on the active layout and the osk_show_flags setting
        self['vkey_left'].setPixmap(self.graphics['vkey_left'])
        self['vkey_right'].setPixmap(self.graphics['vkey_right'])
        self['vkey_delete'].setPixmap(self.graphics['vkey_delete'])
        self['menu_icon'].setPixmap(self.graphics['menu'])
        self['info_icon'].setPixmap(self.graphics['info'])
        self['vk_logo'].setPixmap(self.graphics['vk_logo'])
        for color in ('red', 'green', 'yellow', 'blue'):
            self['vk_key_%s_icon' % color].setPixmap(self.graphics['vk_%s' % color])

        self.currentKeyId = self.KEYIDMAP[self.rowIdx][self.colIdx]
        self.moveKeyMarker(-1, self.currentKeyId)

        self.setSpecialKeyLabels()

    def setSpecialKeyLabels(self):
        self['_1'].setText('Esc')
        self['_16'].setText(_('Clear'))
        # 29 (Del), 61 (Left), 62 (Right) use vkey_delete/vkey_left/vkey_right
        # icons instead of text, matching key 15's own icon-only Backspace
        self['_30'].setText('Caps')
        self['_42'].setText('Enter')
        self['_43'].setText('Shift')
        self['_55'].setText('Shift')
        self['_57'].setText('Ctrl')
        self['_58'].setText('Alt')
        self['_60'].setText('Alt')

    def handleArrowKey(self, dx=0, dy=0):
        oldKeyId = self.KEYIDMAP[self.rowIdx][self.colIdx]
        keyID = oldKeyId
        if dx != 0 and keyID == 0:
            return

        if dx != 0:  # left/right
            colIdx = self.colIdx
            while True:
                colIdx += dx
                if colIdx < 0:
                    colIdx = self.colMax - 1
                elif colIdx >= self.colMax:
                    colIdx = 0
                if keyID != self.KEYIDMAP[self.rowIdx][colIdx]:
                    self.colIdx = colIdx
                    break
        elif dy != 0:  # up/down
            rowIdx = self.rowIdx
            while True:
                rowIdx += dy
                if rowIdx < 0:
                    rowIdx = self.rowMax - 1
                elif rowIdx >= self.rowMax:
                    rowIdx = 0
                if keyID != self.KEYIDMAP[rowIdx][self.colIdx]:
                    self.rowIdx = rowIdx
                    break

        # center the cursor only when left/right
        if dx != 0:
            keyID = self.KEYIDMAP[self.rowIdx][self.colIdx]

            # find max
            maxKeyX = self.colIdx
            for idx in range(self.colIdx + 1, self.colMax):
                if keyID == self.KEYIDMAP[self.rowIdx][idx]:
                    maxKeyX = idx
                else:
                    break
            # find min
            minKeyX = self.colIdx
            for idx in range(self.colIdx - 1, -1, -1):
                if keyID == self.KEYIDMAP[self.rowIdx][idx]:
                    minKeyX = idx
                else:
                    break
            if maxKeyX - minKeyX > 2:
                self.colIdx = int((maxKeyX + minKeyX) / 2)

        self.currentKeyId = self.KEYIDMAP[self.rowIdx][self.colIdx]
        self.moveKeyMarker(oldKeyId, self.currentKeyId)

    def moveKeyMarker(self, oldKeyId, newKeyId):
        if oldKeyId == -1 and newKeyId == -1:
            for key in ['e_m', 'k_m', 'k2_m', 'k3_m']:
                self[key].hide()
            return

        if oldKeyId != -1:
            keyid = str(oldKeyId)
            marker = self.markerMap.get(keyid, 'k_m')
            self[marker].hide()

        if newKeyId != -1:
            keyid = str(newKeyId)
            marker = self.markerMap.get(keyid, 'k_m')
            self[marker].instance.move(ePoint(self[keyid].position[0], self[keyid].position[1]))
            self[marker].show()

    def handleKeyId(self, keyid):
        if keyid == 0:    # OK
            keyid = 42

        if keyid == 1:  # Escape
            if self.deadKey:
                self.deadKey = ''
                self.updateKeysLabels()
            else:
                self.close(None)
            return
        elif keyid == 15:  # Backspace
            self["text"].deleteBackward()
            self.textUpdated()
            return
        elif keyid == 29:  # Delete
            self["text"].delete()
            self.textUpdated()
            return
        elif keyid == 16:  # Clear
            self["text"].deleteAllChars()
            self["text"].update()
            self.textUpdated()
            return
        elif keyid == 56:  # Language
            self.switchToLanguageSelection()
            return
        elif keyid == 61:  # Left
            self["text"].left()
            return
        elif keyid == 62:  # Right
            self["text"].right()
            return
        elif keyid == 42:  # Enter
            try:
                # make sure that Input component return valid UTF-8 data
                text = self["text"].getText()
            except Exception:
                text = ''
                printExc()
            if text and config.plugins.iptvplayer.osk_allow_search_history.value:
                try:
                    gVKSearchHistory.addHistoryItem(text)
                except Exception:
                    printExc()
            self.close(text)
            return
        elif keyid == 30:       # Caps Lock
            self.specialKeyState ^= self.SK_CAPSLOCK
            self.updateKeysLabels()
            self.updateSpecialKey([30], self.specialKeyState & self.SK_CAPSLOCK)
            return
        elif keyid in [43, 55]:  # Shift
            self.specialKeyState ^= self.SK_SHIFT
            self.updateKeysLabels()
            self.updateSpecialKey([43, 55], self.specialKeyState & self.SK_SHIFT)
            return
        elif keyid in [58, 60]:  # ALT
            self.specialKeyState ^= self.SK_ALT
            self.updateKeysLabels()
            self.updateSpecialKey([58, 60], self.specialKeyState & self.SK_ALT)
            return
        elif keyid == 57:       # CTRL
            self.specialKeyState ^= self.SK_CTRL
            self.updateKeysLabels()
            self.updateSpecialKey([57], self.specialKeyState & self.SK_CTRL)
            return
        else:
            updateKeysLabels = False
            ret = 0
            text = ''
            val = self.getKeyValue(keyid)

            if val:
                for special in [(self.SK_CTRL, [57]), (self.SK_ALT, [58, 60]), (self.SK_SHIFT, [43, 55])]:
                    if self.specialKeyState & special[0]:
                        self.specialKeyState ^= special[0]
                        self.updateSpecialKey(special[1], 0)
                        ret = None
                        updateKeysLabels = True

            if val:
                if self.deadKey:
                    if val in self.currentVKLayout['deadkeys'].get(self.deadKey, {}):
                        text = self.currentVKLayout['deadkeys'][self.deadKey][val]
                    else:
                        text = self.deadKey + val
                    self.deadKey = ''
                    updateKeysLabels = True
                elif val in self.currentVKLayout['deadkeys']:
                    self.deadKey = val
                    updateKeysLabels = True
                else:
                    text = val

                self.insertText(text)
                ret = None

            if updateKeysLabels:
                self.updateKeysLabels()
            return ret
        return 0

    def loadKeyboardLayout(self, vkLayoutId):
        printDBG("loadKeyboardLayout vkLayoutId: %s" % vkLayoutId)
        filePath = GetE2iPlayerVKLayoutDir('%s.kle' % vkLayoutId)
        if vkLayoutId == self.DEFAULT_VK_LAYOUT['id']:
            self.setVKLayout(self.DEFAULT_VK_LAYOUT)
            return
        else:
            vkLayoutItem = self.getKeyboardLayoutItem(vkLayoutId)
            if fileExists(filePath):
                try:
                    from ast import literal_eval
                    import codecs
                    try:
                        with codecs.open(filePath, encoding='utf-16') as f:
                            data = f.read()
                    except UnicodeDecodeError:
                        # some .kle files may have been saved/edited as plain UTF-8
                        with codecs.open(filePath, encoding='utf-8') as f:
                            data = f.read()
                    data = literal_eval(data)
                    if data['id'] != vkLayoutId:
                        raise Exception(_('Locale ID mismatched! %s <> %s') % (data['id'], vkLayoutId))
                    self.setVKLayout(data)
                    return
                except Exception as e:
                    printExc()
                    errorMsg = _('Load of the Virtual Keyboard layout "%s" failed due to the following error: "%s"') % (vkLayoutItem[0], str(e))
            else:
                errorMsg = _('"%s" Virtual Keyboard layout not available.') % vkLayoutItem[0]
            self.session.open(MessageBox, errorMsg, type=MessageBox.TYPE_ERROR, timeout=5)

    def setVKLayout(self, layout=None):
        if layout is not None:
            self.currentVKLayout = layout
        self.updateKeysLabels()
        self['_56'].setText(self.currentVKLayout['locale'].split('-', 1)[0].upper())
        self['_56'].show()
        self._applyLanguageIconLayout()
        self.updateSuggestions()

    def _getCurrentLanguageIcon(self):
        # osk_show_flags off -> the plain globe icon, as before. On -> the
        # flag for the active layout's locale, reusing left_list's own
        # flag lookup/cache (keyed the same way as the language picker, by
        # ALL_VK_LAYOUTS' underscore-locale field, e.g. 'de_DE' - not
        # currentVKLayout['locale'], which is hyphenated, e.g. 'de-DE').
        # It already falls back to missing.png when a locale has no flag.
        if not config.plugins.iptvplayer.osk_show_flags.value:
            return self.graphics['l']
        layoutId = self.currentVKLayout.get('id')
        for entry in self.ALL_VK_LAYOUTS:
            if entry[2] == layoutId:
                flagPix = self['left_list']._getFlagPixmap(entry[1])
                if flagPix is not None:
                    return flagPix
                break
        return self.graphics['l']

    def _getLanguageIconGeometry(self):
        # osk_show_flags on: box sized for a flag (flagIconW/H, matching
        # E2iVKSelectionList's own flagSize per tier); off: the plain globe
        # (globeIconWH, unchanged from before this option existed). Read
        # live (not cached) so toggling the setting and returning from
        # Settings can restyle an already-open keyboard via
        # _applyLanguageIconLayout() instead of requiring a reopen.
        if self.isWQHD:
            globeIconWH, globeOffsetY = 35, 19
            flagIconW, flagIconH = 80, 53
        elif self.fullHD:
            globeIconWH, globeOffsetY = 26, 14
            flagIconW, flagIconH = 60, 40
        else:
            globeIconWH, globeOffsetY = 26, 14
            flagIconW, flagIconH = 40, 27

        if config.plugins.iptvplayer.osk_show_flags.value:
            langIconW, langIconH = flagIconW, flagIconH
            langIconOffsetY = (self._gridBH - flagIconH) // 2
        else:
            langIconW, langIconH = globeIconWH, globeIconWH
            langIconOffsetY = globeOffsetY
        # reserved width for the icon before key 56's "DE" text label starts;
        # was a flat 40 regardless of tier/icon, which the WQHD globe (35)
        # and any flag wider than 30px would already overflow
        langAreaW = langIconW + 18
        return langIconW, langIconH, langIconOffsetY, langAreaW

    def _applyLanguageIconLayout(self):
        # Live counterpart to the box sizing prepareSkin() bakes into the
        # initial skin - called after returning from the keyboard's own
        # Settings screen so toggling "Show flags" doesn't need a reopen.
        langIconW, langIconH, langIconOffsetY, langAreaW = self._getLanguageIconGeometry()
        # self._gridX/Y come from prepareSkin()'s "(sz_w - 15*bw) / 2" - true
        # division, so still a float here; int() it like the skin-string
        # "%d" formatting elsewhere already implicitly does
        gridX, gridY = int(self._gridX), int(self._gridY)
        iconX = gridX + 10
        iconY = gridY + 10 + self._gridBH * 5 + langIconOffsetY
        if self['l'].instance:
            self['l'].instance.resize(eSize(langIconW, langIconH))
            self['l'].instance.move(ePoint(iconX, iconY))

        textX = gridX + langAreaW
        textY = gridY + 10 + self._gridBH * 5
        textW = self._gridBW * 2 - langAreaW
        if self['_56'].instance:
            self['_56'].instance.resize(eSize(textW, self._gridBH))
            self['_56'].instance.move(ePoint(textX, textY))

        self['l'].setPixmap(self._getCurrentLanguageIcon())

    def updateSpecialKey(self, keysidTab, state):
        if state:
            color = self.colors['selected']
        else:
            color = self.colors['normal']

        for keyid in keysidTab:
            self['_%s' % keyid].instance.setForegroundColor(color)

    def getKeyValue(self, keyid):
        state = self.specialKeyState
        # we treat both Alt keys as AltGr
        if self.specialKeyState & self.SK_ALT and not (self.specialKeyState & self.SK_CTRL):
            state ^= self.SK_CTRL
        key = self.currentVKLayout['layout'].get(keyid, {})
        if state in key:
            val = key[state]
        else:
            val = ''
        return val

    def updateNormalKeyLabel(self, keyid):

        val = self.getKeyValue(keyid)
        if not self.deadKey:
            if len(val) > 1:
                color = self.colors['ligature']
            elif val in self.currentVKLayout['deadkeys']:
                color = self.colors['deadkey']
            else:
                color = self.colors['normal']
        elif val in self.currentVKLayout['deadkeys'].get(self.deadKey, {}):
            val = self.currentVKLayout['deadkeys'][self.deadKey][val]
            color = self.colors['normal']
        else:
            color = self.colors['inactive']

        skinKey = self['_%s' % keyid]
        skinKey.instance.setForegroundColor(color)
        skinKey.setText(val)

    def updateKeysLabels(self):
        for rangeItem in [(2, 14), (17, 28), (31, 41), (44, 54), (59, 59)]:
            for keyid in range(rangeItem[0], rangeItem[1] + 1):
                self.updateNormalKeyLabel(keyid)

    def showSearchHistory(self):
        if self.searchHistoryEnabled:
            self.refreshSearchHistory()
            self['left_list'].show()
            self['left_header'].setText(_('Search history'))
            self['left_header'].show()

    def refreshSearchHistory(self):
        # Like NewVirtualKeyBoard: re-sort (not filter/hide) the history
        # list on every keystroke, bubbling entries that start with what's
        # currently typed to the top, so the panel stays useful instead of
        # showing the same static list from when the keyboard was opened
        if not self.searchHistoryEnabled:
            return
        history = self.searchHistory
        try:
            word = self["text"].getText().strip().lower()
        except Exception:
            word = ''
        if word:
            matches = [h for h in history if h.lower().startswith(word)]
            others = [h for h in history if h not in matches]
            history = matches + others
        self['left_list'].setList([(x,) for x in history])
        self['left_list'].moveToIndex(0)

    def hideLefList(self):
        self['left_header'].hide()
        self['left_list'].hide()
        self['left_list'].setList([])

    def switchToLanguageSelection(self):
        # Popup (matching NewVirtualKeyBoard's own behaviour) instead of
        # overlaying the search-history panel in place - reuses
        # E2iVKSelectionList as-is (flags, selection highlight) via
        # IPTVChoiceBoxWidget's list_class=, so it gets our chrome design
        # (logo/title bar, footer) at the same HD/FHD/WQHD tiers for free.
        selIdx = 0
        listValue = []
        for i in range(len(self.ALL_VK_LAYOUTS)):
            x = self.ALL_VK_LAYOUTS[i]
            sel = self.currentVKLayout['id'] == x[2]
            if sel:
                selIdx = i
            listValue.append({'sel': sel, 'val': x})

        self.session.openWithCallback(self.languageSelectionClosed, IPTVChoiceBoxWidget,
            {'width': 900, 'height': 620, 'current_idx': selIdx, 'title': _('Select language'), 'options': listValue, 'list_class': E2iVKLanguagePickerList, 'chrome': True, 'footerMargin': 120})

    def languageSelectionClosed(self, ret=None):
        if not ret:
            return
        try:
            vkLayoutId = ret['val'][2]
            self.selectedVKLayoutId = vkLayoutId
            self.loadKeyboardLayout(vkLayoutId)
        except Exception:
            printExc()

    def switchToKayboard(self):
        self.setFocus(self.FOCUS_KEYBOARD)
        self.moveKeyMarker(-1, self.currentKeyId)

    def switchToSuggestions(self):
        self.setFocus(self.FOCUS_SUGGESTIONS)
        self['right_list'].moveToIndex(0)
        self['right_list'].setSelectionState(True)

    def switchSearchHistory(self):
        self.setFocus(self.FOCUS_SEARCH_HISTORY)
        self['left_list'].moveToIndex(0)
        self['left_list'].setSelectionState(True)

    def setFocus(self, focus):
        self['text'].timeout()
        if self.focus != focus:
            if self.focus == self.FOCUS_KEYBOARD:
                self.moveKeyMarker(-1, -1)
            elif self.focus == self.FOCUS_SUGGESTIONS:
                self['right_list'].setSelectionState(False)
            elif self.focus == self.FOCUS_SEARCH_HISTORY:
                self['left_list'].setSelectionState(False)
            self.focus = focus

    def keyRed(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(15)
        else:
            return 0

    def keyGreen(self):
        self.handleKeyId(42)

    def keyYellow(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(60)
        else:
            return 0

    def keyBlue(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(43)
        else:
            return 0

    def keyFastForward(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(59)  # Space
        else:
            return 0

    def keyRewind(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(16)  # Clear entered text
        else:
            return 0

    def _getAvailablePanels(self):
        panels = [self.FOCUS_KEYBOARD]
        if self.isSuggestionVisible:
            panels.append(self.FOCUS_SUGGESTIONS)
        if self.searchHistoryEnabled:
            panels.append(self.FOCUS_SEARCH_HISTORY)
        return panels

    def _switchToPanel(self, focus):
        if focus == self.FOCUS_KEYBOARD:
            self.switchToKayboard()
        elif focus == self.FOCUS_SUGGESTIONS:
            self.switchToSuggestions()
        elif focus == self.FOCUS_SEARCH_HISTORY:
            self.switchSearchHistory()

    def cyclePanelNext(self):
        panels = self._getAvailablePanels()
        if len(panels) < 2:
            return 0
        idx = panels.index(self.focus) if self.focus in panels else 0
        self._switchToPanel(panels[(idx + 1) % len(panels)])

    def cyclePanelPrev(self):
        panels = self._getAvailablePanels()
        if len(panels) < 2:
            return 0
        idx = panels.index(self.focus) if self.focus in panels else 0
        self._switchToPanel(panels[(idx - 1) % len(panels)])

    def _getOptionsPickerHeight(self, numItems):
        # IPTVChoiceBoxWidget's skin is declared in a fixed 1280x720
        # reference space and scaled per-axis to the real resolution by the
        # skin engine (2x on WQHD, 1.5x on FullHD, 1x on HD - matching
        # E2iVKOptionsList's own three size tiers). itemHeight there is real
        # pixels, so convert back to reference units. +60 was the fixed
        # title-bar/margin overhead for the plain (chrome=False) skin,
        # reverse-engineered from iptvplayerwidget.py's own tuned constants
        # for this same widget. Both our callers now use chrome=True, whose
        # logo/title bar and OK/EXIT footer bar need more room than that
        # margin ever did, so +160 (matching the widget's own e-150 list
        # bottom margin in chrome mode) so all rows fit without scrolling.
        if getDesktop(0).size().width() >= 2560:
            itemH, scale = 83, 2.0
        elif self.fullHD:
            itemH, scale = 62, 1.5
        else:
            itemH, scale = 44, 1.0
        return int(numItems * itemH / scale) + 160

    def keyMenu(self):
        if self.focus != self.FOCUS_KEYBOARD:
            return 0
        options = [GetVKOptionItem(_("Select language"), "LANGUAGE", self.graphics.get('l'))]
        if config.plugins.iptvplayer.osk_allow_search_history.value:
            options.append(GetVKOptionItem(_("Delete search history"), "CLEAR_HISTORY", LoadPixmap(GetIconDir('SearchHistoryDeleteItem.png'))))
        options.append(GetVKOptionItem(_("Settings"), "SETTINGS", LoadPixmap(GetIconDir('SettingsItem.png'))))
        height = self._getOptionsPickerHeight(len(options))
        self.session.openWithCallback(self.menuCallback, IPTVChoiceBoxWidget, {'width': 600, 'height': height, 'current_idx': 0, 'title': _("Options"), 'options': options, 'list_class': E2iVKOptionsList, 'chrome': True})

    def menuCallback(self, ret=None):
        if not isinstance(ret, IPTVChoiceBoxItem):
            return
        value = ret.privateData
        if value == "LANGUAGE":
            self.switchToLanguageSelection()
        elif value == "SETTINGS":
            from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import E2iVKQuickSettings
            self.session.openWithCallback(self.settingsClosed, E2iVKQuickSettings)
        elif value == "CLEAR_HISTORY":
            self.session.openWithCallback(self.clearSearchHistoryConfirmed, MessageBox, _('Are you sure you want to delete search history?'), type=MessageBox.TYPE_YESNO, default=True)

    def settingsClosed(self, ret=None):
        # restyles the language icon/text box for a live osk_show_flags
        # change instead of requiring the keyboard to be closed and reopened
        self._applyLanguageIconLayout()
        self._refreshSuggestionsProvider()

    def _refreshSuggestionsProvider(self):
        # right_list/right_header only exist when the keyboard was opened
        # with a provider already resolved (see prepareSkin()'s "if
        # self.autocomplete:") - that layout can't be added live, so this
        # only re-resolves WHICH provider is used, not whether the panel
        # is shown at all
        if not self.suggestionsProviderFactory or not self.autocomplete:
            return
        try:
            newProvider = self.suggestionsProviderFactory()
        except Exception:
            printExc()
            return
        if not newProvider:
            return
        self.autocomplete.term()
        self.autocomplete = AutocompleteSearch(newProvider)
        self['right_header'].setText(self.autocomplete.getProviderName())
        self['right_list'].setList([])
        self.updateSuggestions()

    def clearSearchHistoryConfirmed(self, ret=None):
        if not ret:
            return
        err, msg = gVKSearchHistory.doRemove()
        if self.searchHistoryEnabled:
            self.showSearchHistory()
        else:
            self.hideLefList()
        self.session.open(MessageBox, msg, type=MessageBox.TYPE_ERROR if err else MessageBox.TYPE_INFO, timeout=5)

    def keyHelp(self):
        resDir = 'FHD' if (self.fullHD or self.isWQHD) else 'HD'

        def icon(name):
            return LoadPixmap(GetIconDir('%s/%s.png' % (resDir, name)))

        options = [
            GetVKOptionItem(_("OK - type selected character / confirm selection"), None, icon('ok')),
            GetVKOptionItem(_("GREEN - Enter (confirm and close)"), None, icon('green')),
            GetVKOptionItem(_("RED - Backspace"), None, icon('red')),
            GetVKOptionItem(_("YELLOW - AltGr"), None, icon('yellow')),
            GetVKOptionItem(_("BLUE - Shift"), None, icon('blue')),
            GetVKOptionItem(_("MENU - Options (select language, clear search history, settings)"), None, icon('menu')),
            GetVKOptionItem(_("PREVIOUS/NEXT - switch between keyboard, suggestions and search history"), None, icon('key_prevnext')),
            GetVKOptionItem(_("LEFT/RIGHT at start/end of text - alternative way to switch panels"), None),
            GetVKOptionItem(_("PAGE UP/PAGE DOWN - move cursor right/left"), None, icon('key_updown')),
            GetVKOptionItem(_("FAST FORWARD - insert space"), None),
            GetVKOptionItem(_("REWIND - delete entered text"), None),
            GetVKOptionItem(_("0-9 - direct number input"), None),
        ]
        height = self._getOptionsPickerHeight(len(options))
        self.session.open(IPTVChoiceBoxWidget, {'width': 700, 'height': height, 'current_idx': 0, 'title': _("Help"), 'options': options, 'list_class': E2iVKOptionsList, 'selectable': False, 'chrome': True})

    def keyOK(self):
        if self.focus in (self.FOCUS_SUGGESTIONS, self.FOCUS_SEARCH_HISTORY):
            text = self['right_list' if self.focus == self.FOCUS_SUGGESTIONS else "left_list"].getCurrent()
            if text:
                self.setText(text)
            self.currentKeyId = 0
            self.rowIdx = 0
            self.colIdx = 7
            self.switchToKayboard()
        elif self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(self.currentKeyId)
        else:
            return 0

    def keyBack(self):
        if self.focus == self.FOCUS_KEYBOARD:
            if self.deadKey:
                self.deadKey = ''
                self.updateKeysLabels()
            else:
                self.close(None)
        elif self.focus in (self.FOCUS_SUGGESTIONS, self.FOCUS_SEARCH_HISTORY):
            self.switchToKayboard()
        else:
            return 0

    def keyUp(self):
        printDBG('keyUp')
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleArrowKey(0, -1)
        elif self.focus == self.FOCUS_SEARCH_HISTORY:
            item = self['left_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveUp)
        elif self.focus == self.FOCUS_SUGGESTIONS:
            item = self['right_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveUp)
        else:
            return 0

    def keyDown(self):
        printDBG('keyDown')
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleArrowKey(0, 1)
        elif self.focus == self.FOCUS_SEARCH_HISTORY:
            item = self['left_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveDown)
        elif self.focus == self.FOCUS_SUGGESTIONS:
            item = self['right_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveDown)
        else:
            return 0

    def keyLeft(self):
        printDBG('keyLeft')
        if self.focus == self.FOCUS_SEARCH_HISTORY:
            if self.isSuggestionVisible:
                self.switchToSuggestions()
            else:
                self.switchToKayboard()
                if self.currentKeyId in self.LEFT_KEYS:
                    self.handleArrowKey(-1, 0)
        elif self.focus == self.FOCUS_SUGGESTIONS:
            self.switchToKayboard()
            if self.currentKeyId in self.LEFT_KEYS:
                self.handleArrowKey(-1, 0)
        elif self.focus == self.FOCUS_KEYBOARD:
            if self.currentKeyId in self.LEFT_KEYS or (self.currentKeyId == 0 and self['text'].currPos == 0):
                if self.searchHistoryEnabled:
                    self.switchSearchHistory()
                    return
                elif self.isSuggestionVisible:
                    self.switchToSuggestions()
                    return

            if self.currentKeyId == 0:
                self["text"].left()
            else:
                self.handleArrowKey(-1, 0)
        else:
            return 0

    def keyRight(self):
        printDBG('keyRight')
        if self.focus == self.FOCUS_SEARCH_HISTORY:
            self.switchToKayboard()
            if self.currentKeyId in self.RIGHT_KEYS:
                self.handleArrowKey(1, 0)
        elif self.focus == self.FOCUS_SUGGESTIONS:
            if self.searchHistoryEnabled:
                self.switchSearchHistory()
            else:
                self.switchToKayboard()
                if self.currentKeyId in self.RIGHT_KEYS:
                    self.handleArrowKey(1, 0)
        elif self.focus == self.FOCUS_KEYBOARD:
            if self.currentKeyId in self.RIGHT_KEYS or (self.currentKeyId == 0 and self['text'].currPos == len(self['text'].text)):
                if self.isSuggestionVisible:
                    self.switchToSuggestions()
                    return
                elif self.searchHistoryEnabled:
                    self.switchSearchHistory()
                    return

            if self.currentKeyId == 0:
                self["text"].right()
            else:
                self.handleArrowKey(1, 0)
        else:
            return 0

    def cursorRight(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(62)
        else:
            return 0

    def cursorLeft(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(61)
        else:
            return 0

    def backClicked(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(15)
        else:
            return 0

    def forwardClicked(self):
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleKeyId(29)
        else:
            return 0

    def keyNumberGlobal(self, number):
        if self.currentKeyId == 0:
            try:
                self["text"].number(number)
            except Exception:
                printExc()

    def keyGotAscii(self):
        if self.currentKeyId == 0:
            try:
                self["text"].handleAscii(getPrevAsciiCode())
            except Exception:
                printExc()

    def setSuggestionVisible(self, visible):
        if self.isAutocompleteEnabled and self.isSuggestionVisible != visible:
            if visible:
                self['right_header'].show()
                self['right_list'].show()
            else:
                self['right_header'].hide()
                self['right_list'].hide()

            self.isSuggestionVisible = visible

    def insertText(self, text):
        for letter in text:
            try:
                self["text"].insertChar(letter, self["text"].currPos, False, True)
                # not innerRight(): Input's cursor-advance helper is named
                # innerRight on OpenATV but innerright (lowercase) on
                # OpenViX - calling the wrong one raised an AttributeError
                # there, silently caught below, so currPos never advanced
                # and every typed letter re-inserted at position 0, building
                # the string backwards ("home" -> "emoh"). right() is the
                # same cursor-forward move under a name both forks share,
                # and already calls update() internally.
                self["text"].right()
            except Exception:
                printExc()
        self.textUpdated()

    def textUpdated(self):
        self.updateSuggestions()
        self.refreshSearchHistory()
        # there is need to work to take position of cursor
        # if self['text'].getSize()[0] > 740:
        #    self['text'].instance.setHAlign(2)
        # else:
        #    self['text'].instance.setHAlign(0)

    def updateSuggestions(self):
        if self.isAutocompleteEnabled:
            if not self["text"].text:
                self.setSuggestionVisible(False)
                self['right_list'].setList([])
                # self.autocomplete.stop()
            else:
                self.autocomplete.start(self.setSuggestions)
                self.autocomplete.set(self["text"].getText(), self.currentVKLayout['locale'])

    def setSuggestions(self, list, stamp):
        # we would not want to modify list when user
        # is under selection item from it
        if self.focus != self.FOCUS_SUGGESTIONS and self["text"].text:
            if list:
                self['right_list'].setList([(x,) for x in list])
            self.setSuggestionVisible(True if list else False)
        else:
            printDBG("setSuggestions ignored")
