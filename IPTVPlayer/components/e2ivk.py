# -*- coding: utf-8 -*-
#
#  E2iPlayer On Screen Keyboard based on Windows keyboard layouts
#
#  $Id$
#
#
from Screens.Screen import Screen
from Components.ActionMap import NumberActionMap
from enigma import ePoint, gFont, gRGB, eListboxPythonMultiContent, eListbox, gFont, RT_HALIGN_LEFT, RT_HALIGN_RIGHT, RT_VALIGN_CENTER, getDesktop
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from Tools.BoundFunction import boundFunction
from Components.Label import Label
from Components.Input import Input
from Components.config import config, configfile
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox

from Plugins.Extensions.IPTVPlayer.components.cover import Cover3
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, mkdirs, GetDefaultLang, GetIconDir, GetE2iPlayerVKLayoutDir, GetResourcesServerUri
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase
from Plugins.Extensions.IPTVPlayer.components.e2isimpledownloader import SingleFileDownloaderWidget


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

    def __init__(self, withRatioButton=True):
        IPTVListComponentBase.__init__(self)
        if getDesktop(0).size().width() == 1920:
            fontSize = 24
            itemHeight = 38
        else:
            fontSize = 16
            itemHeight = 30

        try:
            self.font = skin.fonts["e2ivklistitem"]
        except Exception:
            self.font = ("Regular", fontSize, itemHeight, 0)

        self.l.setFont(0, gFont("Regular", 60))
        self.l.setFont(1, gFont(self.font[0], self.font[1]))
        self.l.setItemHeight(self.font[2])
        self.dictPIX = {}
        self.withRatioButton = withRatioButton

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None

    def onCreate(self):
        printDBG('--- onCreate ---')

        if self.withRatioButton:
            self._nullPIX()
            for key in self.dictPIX:
                try:
                    pixFile = self.ICONS_FILESNAMES.get(key, None)
                    if None != pixFile:
                        self.dictPIX[key] = LoadPixmap(cached=True, path=GetIconDir(pixFile))
                except Exception:
                    printExc()

    def onDestroy(self):
        printDBG('--- onDestroy ---')
        if self.withRatioButton:
            self._nullPIX()

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
                y = (height - 16) / 2
                res.append((eListboxPythonMultiContent.TYPE_TEXT, 20, 0, width - 20, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item['val'][0])) #, item.get('color')
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, 3, y, 16, 16, self.dictPIX.get(sel_key, None)))
            else:
                res.append((eListboxPythonMultiContent.TYPE_TEXT, 4, 0, width - 4, height, 1, RT_HALIGN_LEFT | RT_VALIGN_CENTER, item))
        except Exception:
            printExc()
        return res


class E2iVirtualKeyBoard(Screen):
    FOCUS_LANGUAGES = 1
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
    DEFAULT_VK_LAYOUT = {'layout': {2: {0: u'`', 1: u'~', 8: u'`', 9: u'~'}, 3: {0: u'1', 1: u'!', 6: u'\xa1', 7: u'\xb9', 8: u'1', 9: u'!', 14: u'\xa1', 15: u'\xb9'}, 4: {0: u'2', 1: u'@', 6: u'\xb2', 8: u'2', 9: u'@', 14: u'\xb2'}, 5: {0: u'3', 1: u'#', 6: u'\xb3', 8: u'3', 9: u'#', 14: u'\xb3'}, 6: {0: u'4', 1: u'$', 6: u'\xa4', 7: u'\xa3', 8: u'4', 9: u'$', 14: u'\xa4', 15: u'\xa3'}, 7: {0: u'5', 1: u'%', 6: u'\u20ac', 8: u'5', 9: u'%', 14: u'\u20ac'}, 8: {0: u'6', 1: u'^', 6: u'\xbc', 8: u'6', 9: u'^', 14: u'\xbc'}, 9: {0: u'7', 1: u'&', 6: u'\xbd', 8: u'7', 9: u'&', 14: u'\xbd'}, 10: {0: u'8', 1: u'*', 6: u'\xbe', 8: u'8', 9: u'*', 14: u'\xbe'}, 11: {0: u'9', 1: u'(', 6: u'\u2018', 8: u'9', 9: u'(', 14: u'\u2018'}, 12: {0: u'0', 1: u')', 6: u'\u2019', 8: u'0', 9: u')', 14: u'\u2019'}, 13: {0: u'-', 1: u'_', 6: u'\xa5', 8: u'-', 9: u'_', 14: u'\xa5'}, 14: {0: u'=', 1: u'+', 6: u'\xd7', 7: u'\xf7', 8: u'=', 9: u'+', 14: u'\xd7', 15: u'\xf7'}, 17: {0: u'q', 1: u'Q', 6: u'\xe4', 7: u'\xc4', 8: u'Q', 9: u'q', 14: u'\xc4', 15: u'\xe4'}, 18: {0: u'w', 1: u'W', 6: u'\xe5', 7: u'\xc5', 8: u'W', 9: u'w', 14: u'\xc5', 15: u'\xe5'}, 19: {0: u'e', 1: u'E', 6: u'\xe9', 7: u'\xc9', 8: u'E', 9: u'e', 14: u'\xc9', 15: u'\xe9'}, 20: {0: u'r', 1: u'R', 6: u'\xae', 8: u'R', 9: u'r', 14: u'\xae'}, 21: {0: u't', 1: u'T', 6: u'\xfe', 7: u'\xde', 8: u'T', 9: u't', 14: u'\xde', 15: u'\xfe'}, 22: {0: u'y', 1: u'Y', 6: u'\xfc', 7: u'\xdc', 8: u'Y', 9: u'y', 14: u'\xdc', 15: u'\xfc'}, 23: {0: u'u', 1: u'U', 6: u'\xfa', 7: u'\xda', 8: u'U', 9: u'u', 14: u'\xda', 15: u'\xfa'}, 24: {0: u'i', 1: u'I', 6: u'\xed', 7: u'\xcd', 8: u'I', 9: u'i', 14: u'\xcd', 15: u'\xed'}, 25: {0: u'o', 1: u'O', 6: u'\xf3', 7: u'\xd3', 8: u'O', 9: u'o', 14: u'\xd3', 15: u'\xf3'}, 26: {0: u'p', 1: u'P', 6: u'\xf6', 7: u'\xd6', 8: u'P', 9: u'p', 14: u'\xd6', 15: u'\xf6'}, 27: {0: u'[', 1: u'{', 2: u'\x1b', 6: u'\xab', 8: u'[', 9: u'{', 10: u'\x1b', 14: u'\xab'}, 28: {0: u']', 1: u'}', 2: u'\x1d', 6: u'\xbb', 8: u']', 9: u'}', 10: u'\x1d', 14: u'\xbb'}, 31: {0: u'a', 1: u'A', 6: u'\xe1', 7: u'\xc1', 8: u'A', 9: u'a', 14: u'\xc1', 15: u'\xe1'}, 32: {0: u's', 1: u'S', 6: u'\xdf', 7: u'\xa7', 8: u'S', 9: u's', 14: u'\xa7', 15: u'\xdf'}, 33: {0: u'd', 1: u'D', 6: u'\xf0', 7: u'\xd0', 8: u'D', 9: u'd', 14: u'\xd0', 15: u'\xf0'}, 34: {0: u'f', 1: u'F', 8: u'F', 9: u'f'}, 35: {0: u'g', 1: u'G', 8: u'G', 9: u'g'}, 36: {0: u'h', 1: u'H', 8: u'H', 9: u'h'}, 37: {0: u'j', 1: u'J', 8: u'J', 9: u'j'}, 38: {0: u'k', 1: u'K', 8: u'K', 9: u'k'}, 39: {0: u'l', 1: u'L', 6: u'\xf8', 7: u'\xd8', 8: u'L', 9: u'l', 14: u'\xd8', 15: u'\xf8'}, 40: {0: u';', 1: u':', 6: u'\xb6', 7: u'\xb0', 8: u';', 9: u':', 14: u'\xb6', 15: u'\xb0'}, 41: {0: u"'", 1: u'"', 6: u'\xb4', 7: u'\xa8', 8: u"'", 9: u'"', 14: u'\xb4', 15: u'\xa8'}, 44: {0: u'z', 1: u'Z', 6: u'\xe6', 7: u'\xc6', 8: u'Z', 9: u'z', 14: u'\xc6', 15: u'\xe6'}, 45: {0: u'x', 1: u'X', 8: u'X', 9: u'x'}, 46: {0: u'c', 1: u'C', 6: u'\xa9', 7: u'\xa2', 8: u'C', 9: u'c', 14: u'\xa2', 15: u'\xa9'}, 47: {0: u'v', 1: u'V', 8: u'V', 9: u'v'}, 48: {0: u'b', 1: u'B', 8: u'B', 9: u'b'}, 49: {0: u'n', 1: u'N', 6: u'\xf1', 7: u'\xd1', 8: u'N', 9: u'n', 14: u'\xd1', 15: u'\xf1'}, 50: {0: u'm', 1: u'M', 6: u'\xb5', 8: u'M', 9: u'm', 14: u'\xb5'}, 51: {0: u',', 1: u'<', 6: u'\xe7', 7: u'\xc7'}, 52: {0: u'.', 1: u'>', 8: u'.', 9: u'>'}, 53: {0: u'/', 1: u'?', 6: u'\xbf', 8: u'/', 9: u'?', 14: u'\xbf'}, 54: {0: u'\\', 1: u'|', 2: u'\x1c', 6: u'\xac', 7: u'\xa6', 8: u'\\', 9: u'|', 10: u'\x1c', 14: u'\xac', 15: u'\xa6'}, 59: {0: u' ', 1: u' ', 2: u' ', 8: u' ', 9: u' ', 10: u' '}}, 'name': u'English (United States)', 'locale': u'en-US', 'id': u'00020409', 'deadkeys': {u'~': {u'a': u'\xe3', u'A': u'\xc3', u' ': u'~', u'O': u'\xd5', u'N': u'\xd1', u'o': u'\xf5', u'n': u'\xf1'}, u'`': {u'a': u'\xe0', u'A': u'\xc0', u'e': u'\xe8', u' ': u'`', u'i': u'\xec', u'o': u'\xf2', u'I': u'\xcc', u'u': u'\xf9', u'O': u'\xd2', u'E': u'\xc8', u'U': u'\xd9'}, u'"': {u'a': u'\xe4', u'A': u'\xc4', u'e': u'\xeb', u' ': u'"', u'i': u'\xef', u'o': u'\xf6', u'I': u'\xcf', u'u': u'\xfc', u'O': u'\xd6', u'y': u'\xff', u'E': u'\xcb', u'U': u'\xdc'}, u"'": {u'a': u'\xe1', u'A': u'\xc1', u'c': u'\xe7', u'e': u'\xe9', u' ': u"'", u'i': u'\xed', u'C': u'\xc7', u'o': u'\xf3', u'I': u'\xcd', u'u': u'\xfa', u'O': u'\xd3', u'y': u'\xfd', u'E': u'\xc9', u'U': u'\xda', u'Y': u'\xdd'}, u'^': {u'a': u'\xe2', u'A': u'\xc2', u'e': u'\xea', u' ': u'^', u'i': u'\xee', u'o': u'\xf4', u'I': u'\xce', u'u': u'\xfb', u'O': u'\xd4', u'E': u'\xca', u'U': u'\xdb'}}, 'desc': u'United States-International'}

    def prepareSkin(self):
        # full screen
        sz_w = getDesktop(0).size().width()
        sz_h = getDesktop(0).size().height()

        self.fullHD = getDesktop(0).size().width() == 1920

        bw = 70 if self.fullHD else 50
        bh = 70 if self.fullHD else 50
        inputFontSize = 33 if self.fullHD else 26
        headerFontSize = 25 if self.fullHD else 20

        x = (sz_w - 15 * bw) / 2
        y = sz_h - 7 * bh

        bg_color = config.plugins.iptvplayer.osk_background_color.value
        bg_color = ' backgroundColor="%s" ' % bg_color if bg_color else ''

        skinTab = ["""<screen position="center,center" size="%d,%d" title="E2iPlayer virtual keyboard" %s >""" % (sz_w, sz_h, bg_color)]

        def _addPixmapWidget(name, x, y, w, h, p):
            skinTab.append('<widget name="%s" zPosition="%d" position="%d,%d" size="%d,%d" transparent="1" alphatest="blend" />' % (name, p, x, y, w, h))

        def _addMarker(name, x, y, w, h, p, color):
            skinTab.append('<widget name="%s" zPosition="%d" position="%d,%d" size="%d,%d" noWrap="1" font="Regular;2" valign="center" halign="center" foregroundColor="%s" backgroundColor="%s" />' % (name, p, x, y, w, h, color, color))

        def _addButton(name, x, y, w, h, p):
            _addPixmapWidget(name, x, y, w, h, p)
            if name in [1, 16, 29, 30, 42, 43, 55, 57, 58, 60]:
                font = 25 if self.fullHD else 20
                color = '#1688b2'
                align = 'center'
            elif name in [61, 62]:
                font = 35 if self.fullHD else 30
                color = '#1688b2'
                align = 'center'
            elif name == 56:
                font = 25 if self.fullHD else 20
                color = '#1688b2'
                align = 'left'
                x += 40
                w -= 40
            else:
                font = 25 if self.fullHD else 20
                color = '#404551'
                align = 'center'
            skinTab.append('<widget name="_%s" zPosition="%d" position="%d,%d" size="%d,%d" transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="%s" foregroundColor="#ffffff" backgroundColor="%s" />' % (name, p + 2, x, y, w, h, font, align, color))

        skinTab.append('<widget name="header" zPosition="%d" position="%d,%d" size="%d,%d"  transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="left" foregroundColor="#ffffff" backgroundColor="#000000" />' % (2, x + 5, y - (bh - 7 * 2), 15 * bw - 10, bh - 7 * 2, headerFontSize))
        skinTab.append('<widget name="text"   zPosition="%d" position="%d,%d" size="%d,%d"  transparent="1" noWrap="1" font="Regular;%s" valign="center" halign="left" />' % (2, x + 5, y + 7, 15 * bw - 10, bh - 7 * 2, inputFontSize))
        _addPixmapWidget(0, x, y, 15 * bw, bh, 1)
        _addPixmapWidget('e_m', 0, 0, 15 * bw, bh, 5)
        _addPixmapWidget('k_m', 0, 0, bw, bh, 5)
        _addPixmapWidget('k2_m', 0, 0, bw * 2, bh, 5)
        _addPixmapWidget('k3_m', 0, 0, bw * 8, bh, 5)

        for i in range(0, 15):
            _addButton(i + 1, x + bw * i, y + 10 + bh * 1, bw, bh, 1)
        _addPixmapWidget('b', x + bw * 14 + (bw - 32) / 2, y + 10 + bh * 1 + (bh - 20) / 2, 32, 20, 3) # backspace icon

        _addButton(16, x, y + 10 + bh * 2, bw * 2, bh, 1)
        for i in range(0, 14):
            _addButton(i + 17, x + bw * (i + 2), y + 10 + bh * 2, bw, bh, 1)

        _addButton(30, x, y + 10 + bh * 3, bw * 2, bh, 1)
        for i in range(0, 13):
            _addButton(i + 31, x + bw * (i + 2), y + 10 + bh * 3, bw, bh, 1)
        _addButton(42, x + bw * 13, y + 10 + bh * 3, bw * 2, bh, 1)

        _addButton(43, x, y + 10 + bh * 4, bw * 2, bh, 1)
        for i in range(0, 13):
            _addButton(i + 44, x + bw * (i + 2), y + 10 + bh * 4, bw, bh, 1)
        _addButton(55, x + bw * 13, y + 10 + bh * 4, bw * 2, bh, 1)

        _addPixmapWidget('l', x + 10, y + 10 + bh * 5 + 14, 26, 26, 3) # language icon
        _addButton(56, x, y + 10 + bh * 5, bw * 2, bh, 1)
        _addButton(57, x + bw * 2, y + 10 + bh * 5, bw, bh, 1)
        _addButton(58, x + bw * 3, y + 10 + bh * 5, bw, bh, 1)
        _addButton(59, x + bw * 4, y + 10 + bh * 5, bw * 8, bh, 1)
        _addButton(60, x + bw * 12, y + 10 + bh * 5, bw, bh, 1)
        _addButton(61, x + bw * 13, y + 10 + bh * 5, bw, bh, 1)
        _addButton(62, x + bw * 14, y + 10 + bh * 5, bw, bh, 1)

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

        # Left list
        skinTab.append('<widget name="left_header" zPosition="2" position="%d,%d" size="%d,%d"  transparent="0" noWrap="1" font="Regular;%d" valign="center" halign="center" foregroundColor="#000000" backgroundColor="#ffffff" />' % (x - bw * 5 - 5, y - (bh - 7 * 2), bw * 5, bh - 7 * 2, headerFontSize))
        skinTab.append('<widget name="left_list"   zPosition="1"  position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand" transparent="0"  backgroundColor="#3f4450" enableWrapAround="1" />' % (x - bw * 5 - 5, y, bw * 5, 6 * bh + 10))

        # Right list
        if self.autocomplete:
            skinTab.append('<widget name="right_header" zPosition="2" position="%d,%d" size="%d,%d"  transparent="0" noWrap="1" font="Regular;%d" valign="center" halign="center" foregroundColor="#000000" backgroundColor="#ffffff" />' % (x + bw * 15 + 5, y - (bh - 7 * 2), bw * 5, bh - 7 * 2, headerFontSize))
            skinTab.append('<widget name="right_list"   zPosition="1"  position="%d,%d" size="%d,%d" scrollbarMode="showOnDemand" transparent="0"  backgroundColor="#3f4450" enableWrapAround="1" />' % (x + bw * 15 + 5, y, bw * 5, 6 * bh + 10))

        skinTab.append('</screen>')
        return '\n'.join(skinTab)

    def __init__(self, session, title="", text="", additionalParams={}):
        self.session = session

        # autocomplete engine
        self.autocomplete = additionalParams.get('autocomplete')
        self.isAutocompleteEnabled = False

        self.searchHistory = additionalParams.get('search_history', [])

        self.skin = self.prepareSkin()

        Screen.__init__(self, session)
        self.onLayoutFinish.append(self.setGraphics)
        self.onShown.append(self.onWindowShow)
        self.onClose.append(self.__onClose)

        self["actions"] = NumberActionMap(["WizardActions", "DirectionActions", "ColorActions", "E2iPlayerVKActions", "KeyboardInputActions", "InputBoxActions", "InputAsciiActions"],
        {
            "gotAsciiCode": self.keyGotAscii,
            "ok": self.keyOK,
            "ok_repeat": self.keyOK,
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
        for key in ['pb', 'pr', 'pg', 'py', 'l', 'b', 'e', 'e_m', 'k', 'k_m', 'k_s', 'k2_m', 'k2_s', 'k3', 'k3_m']:
            self.graphics[key] = LoadPixmap(GetIconDir('e2ivk_hd/%s.png' if self.fullHD else 'e2ivk/%s.png') % key)

        for i in range(0, 63):
            self[str(i)] = Cover3()

        for key in ['l', 'b', 'e_m', 'k_m', 'k2_m', 'k3_m']:
            self[key] = Cover3()

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
        self.deadKey = u''
        self.focus = self.FOCUS_KEYBOARD

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
        self["header"].setText(self.header)

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
        self.isAutocompleteEnabled = self.autocomplete != None
        self.setText(self.startText)

    def setText(self, text):
        self["text"].setText(text)
        self["text"].right()
        self["text"].currPos = len(text.decode('utf-8'))
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
        self['l'].setPixmap(self.graphics['l'])

        self.currentKeyId = self.KEYIDMAP[self.rowIdx][self.colIdx]
        self.moveKeyMarker(-1, self.currentKeyId)

        self.setSpecialKeyLabels()

    def setSpecialKeyLabels(self):
        self['_1'].setText('Esc')
        self['_16'].setText(_('Clear'))
        self['_29'].setText('Del')
        self['_30'].setText('Caps')
        self['_42'].setText('Enter')
        self['_43'].setText('Shift')
        self['_55'].setText('Shift')
        self['_57'].setText('Ctrl')
        self['_58'].setText('Alt')
        self['_60'].setText('Alt')
        self['_61'].setText(u'\u2190'.encode('utf-8'))
        self['_62'].setText(u'\u2192'.encode('utf-8'))

    def handleArrowKey(self, dx=0, dy=0):
        oldKeyId = self.KEYIDMAP[self.rowIdx][self.colIdx]
        keyID = oldKeyId
        if dx != 0 and keyID == 0:
            return

        if dx != 0: # left/right
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
        elif dy != 0: # up/down
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
                self.colIdx = (maxKeyX + minKeyX) / 2

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
                self.deadKey = u''
                self.updateKeysLabels()
            else:
                self.close(None)
            return
        elif keyid == 15: # Backspace
            self["text"].deleteBackward()
            self.textUpdated()
            return
        elif keyid == 29: # Delete
            self["text"].delete()
            self.textUpdated()
            return
        elif keyid == 16: # Clear
            self["text"].deleteAllChars()
            self["text"].update()
            self.textUpdated()
            return
        elif keyid == 56: # Language
            self.switchToLanguageSelection()
            return
        elif keyid == 61: # Left
            self["text"].left()
            return
        elif keyid == 62: # Right
            self["text"].right()
            return
        elif keyid == 42: # Enter
            try:
                # make sure that Input component return valid UTF-8 data
                text = self["text"].getText().decode('UTF-8').encode('UTF-8')
            except Exception:
                text = ''
                printExc()
            self.close(text)
            return
        elif keyid == 30:       # Caps Lock
            self.specialKeyState ^= self.SK_CAPSLOCK
            self.updateKeysLabels()
            self.updateSpecialKey([30], self.specialKeyState & self.SK_CAPSLOCK)
            return
        elif keyid in [43, 55]: # Shift
            self.specialKeyState ^= self.SK_SHIFT
            self.updateKeysLabels()
            self.updateSpecialKey([43, 55], self.specialKeyState & self.SK_SHIFT)
            return
        elif keyid in [58, 60]: # ALT
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
            text = u''
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
                    self.deadKey = u''
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

    def loadKeyboardLayout(self, vkLayoutId, allowDownload=True):
        printDBG("loadKeyboardLayout vkLayoutId: %s" % vkLayoutId)
        errorMsg = ''
        askForDowanload = 0
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
                    with codecs.open(filePath, encoding='utf-16') as f:
                        data = f.read()
                    data = literal_eval(data)
                    if data['id'] != vkLayoutId:
                        raise Exception(_('Locale ID mismatched! %s <> %s') % (data['id'], vkLayoutId))
                    self.setVKLayout(data)
                    return
                except ImportError as e:
                    printExc()
                    errorMsg = _('Load of the Virtual Keyboard layout "%s" failed due to the following error: "%s"') % (vkLayoutItem[0], str(e))
                except Exception as e:
                    printExc()
                    errorMsg = _('Load of the Virtual Keyboard layout "%s" failed due to the following error: "%s"') % (vkLayoutItem[0], str(e))
                    askForDowanload = 2
            else:
                errorMsg = _('"%s" Virtual Keyboard layout not available.') % vkLayoutItem[0]
                askForDowanload = 1

            if errorMsg != '':
                if askForDowanload and allowDownload:
                    if askForDowanload == 1:
                        errorMsg += '\n' + _('Do you want to download "%s" Virtual Keyboard layout now?') % vkLayoutItem[0]
                    else:
                        errorMsg += '\n' + _('Do you want to try to re-download "%s" Virtual Keyboard layout?') % vkLayoutItem[0]
                    self.session.openWithCallback(boundFunction(self.askForVKLayoutDownload, vkLayoutId), MessageBox, text=errorMsg, type=MessageBox.TYPE_YESNO)
                else:
                    self.session.open(MessageBox, text=errorMsg, type=MessageBox.TYPE_ERROR)

    def setVKLayout(self, layout=None):
        if layout != None:
            self.currentVKLayout = layout
        self.updateKeysLabels()
        self['_56'].setText(self.currentVKLayout['locale'].encode('UTF-8').split('-', 1)[0].upper())
        self['_56'].show()
        self.updateSuggestions()

    def askForVKLayoutDownload(self, vkLayoutId, ret=None):
        if ret:
            file = '%s.kle' % vkLayoutId
            path = GetE2iPlayerVKLayoutDir()
            mkdirs(path)
            self.session.openWithCallback(boundFunction(self.vkLayoutDownloadCallback, vkLayoutId), SingleFileDownloaderWidget, GetResourcesServerUri('vk/' + file), path + file)
        else:
            self.setVKLayout()

    def vkLayoutDownloadCallback(self, vkLayoutId, ret=None):
        if ret:
            self.loadKeyboardLayout(vkLayoutId, False)
        else:
            self.setVKLayout()

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
            val = u''
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
        skinKey.setText(val.encode('utf-8'))

    def updateKeysLabels(self):
        for rangeItem in [(2, 14), (17, 28), (31, 41), (44, 54), (59, 59)]:
            for keyid in range(rangeItem[0], rangeItem[1] + 1):
                self.updateNormalKeyLabel(keyid)

    def showSearchHistory(self):
        if self.searchHistory:
            leftList = self['left_list']
            leftList.setList([(x,) for x in self.searchHistory])
            leftList.moveToIndex(0)
            leftList.show()
            self['left_header'].setText(_('Search history'))
            self['left_header'].show()

    def hideLefList(self):
        self['left_header'].hide()
        self['left_list'].hide()
        self['left_list'].setList([])

    def switchToLanguageSelection(self):
        self.setFocus(self.FOCUS_LANGUAGES)

        leftList = self['left_list']

        selIdx = None
        listValue = []
        for i in range(len(self.ALL_VK_LAYOUTS)):
            x = self.ALL_VK_LAYOUTS[i]
            if self.currentVKLayout['id'] == x[2]:
                sel = True
                selIdx = i
            else:
                sel = False
            listValue.append(({'sel': sel, 'val': x}, ))

        leftList.setList(listValue)
        if selIdx != None:
            leftList.moveToIndex(selIdx)
        leftList.setSelectionState(True)
        leftList.show()

        self['left_header'].setText(_('Select language'))
        self['left_header'].show()

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
            if self.focus == self.FOCUS_LANGUAGES:
                self['left_list'].setSelectionState(False)
                if self.searchHistory:
                    self.showSearchHistory()
                else:
                    self.hideLefList()
            elif self.focus == self.FOCUS_KEYBOARD:
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
        elif self.focus == self.FOCUS_LANGUAGES:
            try:
                selIdx = self['left_list'].getCurrentIndex()
                vkLayoutId = self.ALL_VK_LAYOUTS[selIdx][2]
                self.selectedVKLayoutId = vkLayoutId
                self.switchToKayboard()
                self.loadKeyboardLayout(vkLayoutId)
            except Exception:
                printExc()
        else:
            return 0

    def keyBack(self):
        if self.focus == self.FOCUS_KEYBOARD:
            if self.deadKey:
                self.deadKey = u''
                self.updateKeysLabels()
            else:
                self.close(None)
        elif self.focus in (self.FOCUS_LANGUAGES, self.FOCUS_SUGGESTIONS, self.FOCUS_SEARCH_HISTORY):
            self.switchToKayboard()
        else:
            return 0

    def keyUp(self):
        printDBG('keyUp')
        if self.focus == self.FOCUS_KEYBOARD:
            self.handleArrowKey(0, -1)
        elif self.focus in (self.FOCUS_LANGUAGES, self.FOCUS_SEARCH_HISTORY):
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
        elif self.focus in (self.FOCUS_LANGUAGES, self.FOCUS_SEARCH_HISTORY):
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
                if self.searchHistory:
                    self.switchSearchHistory()
                    return
                elif self.isSuggestionVisible:
                    self.switchToSuggestions()
                    return

            if self.currentKeyId == 0:
                self["text"].left()
            else:
                self.handleArrowKey(-1, 0)
        elif self.focus == self.FOCUS_LANGUAGES:
            item = self['left_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.pageUp)
        else:
            return 0

    def keyRight(self):
        printDBG('keyRight')
        if self.focus == self.FOCUS_SEARCH_HISTORY:
            self.switchToKayboard()
            if self.currentKeyId in self.RIGHT_KEYS:
                self.handleArrowKey(1, 0)
        elif self.focus == self.FOCUS_SUGGESTIONS:
            if self.searchHistory:
                self.switchSearchHistory()
            else:
                self.switchToKayboard()
                if self.currentKeyId in self.RIGHT_KEYS:
                    self.handleArrowKey(1, 0)
        elif self.focus == self.FOCUS_KEYBOARD:
            if self.currentKeyId in self.RIGHT_KEYS or (self.currentKeyId == 0 and self['text'].currPos == len(self['text'].Text)):
                if self.isSuggestionVisible:
                    self.switchToSuggestions()
                    return
                elif self.searchHistory:
                    self.switchSearchHistory()
                    return

            if self.currentKeyId == 0:
                self["text"].right()
            else:
                self.handleArrowKey(1, 0)
        elif self.focus == self.FOCUS_LANGUAGES:
            item = self['left_list']
            if item.instance is not None:
                item.instance.moveSelection(item.instance.pageDown)
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
                self["text"].innerright()
                self["text"].update()
            except Exception:
                printExc()
        self.textUpdated()

    def textUpdated(self):
        self.updateSuggestions()
        # there is need to work to take position of cursor
        #if self['text'].getSize()[0] > 740:
        #    self['text'].instance.setHAlign(2)
        #else:
        #    self['text'].instance.setHAlign(0)

    def updateSuggestions(self):
        if self.isAutocompleteEnabled:
            if not self["text"].Text:
                self.setSuggestionVisible(False)
                self['right_list'].setList([])
                #self.autocomplete.stop()
            else:
                self.autocomplete.start(self.setSuggestions)
                self.autocomplete.set(self["text"].getText(), self.currentVKLayout['locale'].encode('UTF-8'))

    def setSuggestions(self, list, stamp):
        # we would not want to modify list when user
        # is under selection item from it
        if self.focus != self.FOCUS_SUGGESTIONS and self["text"].Text:
            if list:
                self['right_list'].setList([(x,) for x in list])
            self.setSuggestionVisible(True if list else False)
        else:
            printDBG("setSuggestions ignored")
