# -*- coding: utf-8 -*-
#
#  IPTV IMAGE SELECTOR
#
#  $Id$
#
#
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir, eConnectCallback
from Plugins.Extensions.IPTVPlayer.components.iptvlist import IPTVListComponentBase, fitPixmapInBox
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components import skinchrome

###################################################

###################################################
# FOREIGN import
###################################################
from skin import parseColor
from enigma import eListboxPythonMultiContent, getDesktop, ePicLoad, BT_SCALE, eTimer
from Components.MultiContent import MultiContentEntryPixmapAlphaBlend
from Tools.LoadPixmap import LoadPixmap
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.StaticText import StaticText
###################################################


class IPTVImagesSelectionList(IPTVListComponentBase):
    # WQHD copy used as the single source (32x32, highest res of the 3
    # per-tier variants) - buildEntry() scales it down cleanly via
    # fitPixmapInBox()/BT_SCALE for HD/FHD, so no separate flat-root copy
    # is needed alongside the per-tier ones the plain-widget users need
    ICONS_FILESNAMES = {'on': 'WQHD/radio_button_on.png', 'off': 'WQHD/radio_button_off.png'}

    def __init__(self, height):
        IPTVListComponentBase.__init__(self)

        self.l.setItemHeight(height)
        self.dictPIX = {}
        printDBG('IPTVImagesSelectionList.__init__ height: %d' % height)

    def _nullPIX(self):
        for key in self.ICONS_FILESNAMES:
            self.dictPIX[key] = None

    def onCreate(self):
        printDBG('--- onCreate ---')
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
        self._nullPIX()

    def buildEntry(self, item):
        res = [None]
        width = self.l.getItemSize().width()
        height = self.l.getItemSize().height()
        try:
            printDBG('--- buildEntry ---')
            printDBG('%s: ' % (item['id']))
            # "//" not "/": x/y feed straight into a raw
            # TYPE_PIXMAP_ALPHABLEND tuple for eListboxPythonMultiContent,
            # not a "%d"-format string, so a float here would risk a
            # native-side TypeError once a row actually renders.
            x = (width - item['width']) // 2
            y = (height - item['height']) // 2
            # skip the blit for a missing pixmap (empty cell or a decode
            # that failed) - a None png in this raw
            # TYPE_PIXMAP_ALPHABLEND tuple is a native-side crash risk.
            if item['pixmap'] is not None:
                res.append((eListboxPythonMultiContent.TYPE_PIXMAP_ALPHABLEND, x, y, item['width'], item['height'], item['pixmap']))
            if item['id'] is not None:
                if item['selected']:
                    sel_key = 'on'
                else:
                    sel_key = 'off'
                # on/off dot box - uses fitPixmapInBox()/BT_SCALE, same
                # approach as IPTVRadioButtonList's/E2iVKSelectionList's
                # own dot, so radio_button_on/off.png is properly scaled
                # to fit the declared box. There's no resolution-tier
                # concept in this class (row
                # height comes from the caller's own image_height, not
                # screenwidth), so this scales proportionally to the
                # row's real height instead, anchored to reproduce the
                # exact original 16px at the class's own default height
                # (image_height=160 -> row height 180)
                dotSize = max(int(round(height * 16.0 / 180.0)), 12)
                dotIcon = self.dictPIX.get(sel_key, None)
                if dotIcon is not None:
                    dx, dy, dw, dh = fitPixmapInBox(dotIcon, 3, 3, dotSize, dotSize)
                    res.append(MultiContentEntryPixmapAlphaBlend(pos=(dx, dy), size=(dw, dh), png=dotIcon, flags=BT_SCALE))
        except Exception:
            printExc()
        return res


class IPTVMultipleImageSelectorWidget(Screen):

    def __prepareSkin(self):
        if None is self.iptv_width:
            self.iptv_width = getDesktop(0).size().width()
        if None is self.iptv_height:
            self.iptv_height = getDesktop(0).size().height()
        if self.iptv_title is None:
            self.iptv_title = _('Select pictures')

        if self.iptv_message is not None and self.iptv_message_height is None:
            self.iptv_message_height = self.iptv_height / 10
        if self.iptv_accep_label is not None and self.iptv_accep_height is None:
            self.iptv_accep_height = self.iptv_height / 20

        # top/bottom chrome band. Uses the tiered `scale=` build_header()/
        # build_footer() (not the `_auto()` variants) since this screen
        # computes every position/size directly from `getDesktop()` pixels
        # rather than a fixed `resolution=` reference block - same
        # reasoning as E2iVirtualKeyBoard/E2iPlayerBufferingWidget.
        #
        # Footer: `showMenu=False` (no "menu" action bound), NAV/OK/EXIT
        # all shown (arrow keys/ok/cancel are all genuinely live -
        # build_footer()'s own built-in slots cover exactly this
        # combination, no custom "info"-style extra icon needed unlike
        # E2iVirtualKeyBoard). `keys=('red',)` only - RED (`key_read`,
        # `self.close(None)`) is real, same action `cancel`/EXIT already
        # does (redundant on purpose, same as every other screen here that
        # binds the same handler to two keys); GREEN (`key_green`) is a
        # permanent no-op stub (`pass`, never overridden - no subclasses
        # exist), so it gets no color-key hint at all, matching this
        # branch's policy of never hinting a dead action.
        # deliberately not self.iptv_width - that's this window's own
        # width (defaults to the full desktop, but a future caller could
        # pass something smaller), while tier detection has to stay tied
        # to the real device resolution regardless
        scale = skinchrome.getScale()
        iconBase = skinchrome.getIconBase()
        footerH = skinchrome.footer_height(scale)
        y = skinchrome.header_height(scale) + skinchrome.scalePixels(10, scale)
        # flags="wfNoBorder" - without it, Enigma2 draws its own default
        # bordered-window chrome (title bar reserved above, border
        # reserved around) on top of/around our own header+footer, which
        # are sized assuming the full, unbordered `getDesktop()`
        # dimensions - same as every other migrated screen (e.g.
        # IPTVPinWidget).
        skin = ['<screen position="center,center" title="%s" size="%d,%d" flags="wfNoBorder">' % (self.iptv_title, self.iptv_width, self.iptv_height)]
        skin.append(skinchrome.build_header(scale=scale, iconBase=iconBase, showLogo=True))
        skin.append(skinchrome.build_footer(self.iptv_height, scale=scale, iconBase=iconBase, keys=('red',), showMenu=False, showNav=True, showNum=False, showOk=True, showExit=True))
        if self.iptv_message is not None:
            # was a hardcoded "10,10" - fine back when content started at
            # the very top of the screen, but now has to start at the
            # header's own bottom edge (`y`) instead, or it would sit
            # underneath/behind the new header band
            skin.append('<widget name="message" position="10,%d" zPosition="1" size="%d,%d" valign="center" halign="center" font="Regular;22"  transparent="1"  backgroundColor="#00000000"/>' % (y, self.iptv_width - 20, self.iptv_message_height))
            y += 10 + self.iptv_message_height

        list_width = self.iptv_image_width + 40
        # was "- 20" (flat bottom margin to the raw screen edge) - now has
        # to also clear the new footer band, leaving the same 10px gap
        # above it that "20" used to leave above the screen edge
        list_height = (self.iptv_height - y) - footerH - 10
        if self.iptv_accep_label is not None:
            list_height -= self.iptv_accep_height + 10

        x = (self.iptv_width - (10 * (self.iptv_col_num + 1) + list_width * self.iptv_col_num)) / 2
        for idx in range(self.iptv_col_num):
            if idx != self.iptv_col_num - 1:
                scrollbar_mode = 'showNever'
            else:
                scrollbar_mode = 'showOnDemand'
                list_width += 30  # added for scrollbar
            skin.append('<widget name="col_%d" position="%d,%d" zPosition="1" size="%d,%d" scrollbarMode="%s" transparent="1"  backgroundColor="#00000000" enableWrapAround="1" />' % (idx, x, y, list_width, list_height, scrollbar_mode))
            x += 10 + list_width
        y += list_height + 10

        if self.iptv_accep_label is not None:
            # backgroundColor matches the runtime setBackgroundColor()
            # call below - keeps the initial paint consistent with every
            # later update instead of flashing a different color first.
            skin.append('<widget name="accept_button"  position="10,%d"  zPosition="1" size="%d,%d"  valign="center" halign="center" font="Regular;22" foregroundColor="#00FFFFFF" backgroundColor="#3A3A3A" />' % (y, self.iptv_width - 20, self.iptv_accep_height))
        skin.append('</screen>')
        skin = '\n'.join(skin)
        printDBG(">>>")
        printDBG(skin)
        printDBG("<<<")
        return skin

    def __init__(self, session, title=None, width=None, height=None, message=None, message_height=None, accep_label=None, accep_height=None, col_num=4, images=[], image_width=160, image_height=160, max_sel_items=None):
        self.iptv_title = title
        self.iptv_width = width
        self.iptv_height = height
        self.iptv_message = message
        self.iptv_message_height = message_height

        self.iptv_accep_label = accep_label
        self.iptv_accep_height = accep_height

        self.iptv_col_num = col_num
        # integer division: this feeds straight into range(self.iptv_row_num)
        # below (and 5 more call sites) - range() requires an int, so a
        # plain "/" here would crash with "TypeError: 'float' object
        # cannot be interpreted as an integer".
        self.iptv_row_num = len(images) // col_num
        if len(images) % col_num > 0:
            self.iptv_row_num += 1

        self.iptv_images = images
        self.iptv_image_width = image_width
        self.iptv_image_height = image_width
        self.iptv_max_sel_items = max_sel_items
        self.iptv_num_sel_items = 0
        self.iptv_images_data = None

        self.iptv_grid = []
        for x in range(self.iptv_col_num):
            self.iptv_grid.append([])
            for y in range(self.iptv_row_num):
                self.iptv_grid[x].append(None)

        self.skin = self.__prepareSkin()
        Screen.__init__(self, session)
        # self.skinName = "IPTVMultipleImageSelectorWidget"

        # bound to build_header()'s "Title" source, not a standalone
        # Label widget - see __prepareSkin()'s build_header() comment
        self.setTitle(self.iptv_title)

        # matches build_footer()'s own "source=key_red"/ConditionalShowHide
        # convention - see __prepareSkin()'s build_footer() comment for
        # why only RED gets a color-key hint here
        self["key_red"] = StaticText(_("Cancel"))

        self.onShown.append(self.onStart)
        self.onClose.append(self.__onClose)

        # create controls
        if self.iptv_message is not None:
            self["message"] = Label(str(self.iptv_message))

        for idx in range(self.iptv_col_num):
            self["col_%d" % idx] = IPTVImagesSelectionList(self.iptv_image_height + 20)

        if self.iptv_accep_label:
            self["accept_button"] = Label(self.iptv_accep_label)

        self["actions"] = ActionMap(["SetupActions", "ColorActions", "WizardActions", "ListboxActions"],
            {
                "cancel": self.key_cancel,
                "ok": self.key_ok,
                "green": self.key_green,
                "red": self.key_read,
                "up": self.key_up,
                "down": self.key_down,
                "moveUp": self.key_up,
                "moveDown": self.key_down,
                "moveTop": self.key_home,
                "moveEnd": self.key_end,
                "home": self.key_home,
                "end": self.key_end,
                "pageUp": self.key_page_up,
                "pageDown": self.key_page_down,
                "left": self.key_left,
                "right": self.key_right,
            }, -2)

        self.column_index = 0
        self.row_index = 0
        self.picload = ePicLoad()
        self.picload.setPara((self.iptv_image_width, self.iptv_image_height, 1, 1, False, 1, "#FF000000"))
        self.picload_conn = None
        # Images are decoded one at a time, and each next startDecode() is
        # kicked off from a timer (see __decodedCB()'s 100ms interval
        # below) - i.e. from a fresh mainloop iteration - never straight
        # from inside the PictureData callback. Chaining startDecode()
        # right after getData() in the same callstack is not safe:
        # getData() frees ePicLoad's m_filepara, so the native decode
        # thread would then run ePicLoad::decodePic() on a NULL
        # m_filepara and segfault the whole box.
        self.decode_timer = eTimer()
        self.decode_timer_conn = eConnectCallback(self.decode_timer.timeout, self.__decodeNext)
        # awaitingDecode/gridBuilt guard against ePicLoad's PictureData
        # signal firing more than once for a single startDecode() call on
        # real hardware. Every extra firing would otherwise re-enter
        # __decodedCB, appending another (possibly None, since getData()
        # only has real data to hand back once per decode) entry to
        # iptv_images_data and restarting decode_timer - which, once all
        # real images were already in, would just re-run __buildGrid()
        # again each time instead of advancing to the next image. Not a
        # length problem by itself (indices stay put once written), but a
        # genuine ORDERING one: a duplicate firing for image N appends an
        # extra entry before image N+1's real one arrives, shifting every
        # later image one slot late - explains specific, seemingly-random
        # missing/wrong images instead of e.g. only the last ones being
        # empty.
        self.awaitingDecode = False
        self.gridBuilt = False

    def __onClose(self):
        self.decode_timer.stop()
        self.decode_timer_conn = None
        self.picload_conn = None

    def onStart(self):
        printDBG('-- ON START --')
        self.onShown.remove(self.onStart)
        self.setMarker()
        self.iptv_images_data = []
        self.__decodeNext()

    def __decodeNext(self):
        # decode the next not-yet-decoded image; when all are done, build
        # the grid. Only ever entered from onStart() or the decode_timer,
        # so startDecode() never re-enters ePicLoad from its own callback.
        while len(self.iptv_images_data) < len(self.iptv_images):
            idx = len(self.iptv_images_data)
            self.awaitingDecode = True
            self.picload_conn = eConnectCallback(self.picload.PictureData, self.__decodedCB)
            ret = self.picload.startDecode(self.iptv_images[idx]['path'])
            if ret != 0:
                self.awaitingDecode = False
                printDBG('startDecode failed for "%s"' % self.iptv_images[idx]['path'])
                self.picload_conn = None
                self.iptv_images_data.append(None)
                continue
            return
        # idempotent - see the __init__ comment for why this can otherwise
        # get entered again (and re-run) after the real 8 already landed
        if not self.gridBuilt:
            self.gridBuilt = True
            self.__buildGrid()

    def __decodedCB(self, picInfo=None):
        if not self.awaitingDecode:
            # spurious extra PictureData firing for a decode this screen
            # already consumed (see __init__'s comment) - getData() would
            # return None/stale data for it (the real data was already
            # handed back on the first, real firing), so ignore it
            # outright instead of letting it corrupt iptv_images_data's
            # ordering
            printDBG('__decodedCB: ignoring spurious extra PictureData firing')
            return
        self.awaitingDecode = False
        self.picload_conn = None
        self.iptv_images_data.append(self.picload.getData())
        # 100ms, not 0: a 0ms timer only guarantees a fresh mainloop tick,
        # not that the native decode thread from the previous
        # startDecode() has actually finished releasing its resources
        # yet - a real race that shows up as empty grid cells.
        # iptvplayerwidget.py's own decodeCoverTimer (the pattern this was
        # modeled after) never uses 0 either - 100ms is its default retry
        # interval for the same class of "give the native decoder a
        # moment" situation.
        self.decode_timer.start(100, True)

    def __buildGrid(self):
        i = 0
        for y in range(self.iptv_row_num):
            for x in range(self.iptv_col_num):
                item = {'pixmap': None, 'id': None, 'width': self.iptv_image_width, 'height': self.iptv_image_height, 'selected': False}
                if i < len(self.iptv_images):
                    item['id'] = self.iptv_images[i]['id']
                    item['pixmap'] = self.iptv_images_data[i]
                self.iptv_grid[x][y] = item
                i += 1

        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            item.setList([(x,) for x in self.iptv_grid[i]])
        self.changeColumnSelection()

    def changeColumnSelection(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if i != self.column_index:
                item.instance.setSelectionEnable(0)
            else:
                item.instance.setSelectionEnable(1)

    def key_ok(self):
        maxItemsSelected = False
        if self.row_index < self.iptv_row_num:
            try:
                item = self["col_%d" % self.column_index]
                itemContent = item.l.getCurrentSelection()[0]
                if itemContent['id'] is None:  # do not allow to select empty cell
                    return
                if itemContent['selected']:
                    self.iptv_num_sel_items -= 1
                else:
                    self.iptv_num_sel_items += 1
                itemContent['selected'] = not itemContent['selected']
                item.instance.setSelectionEnable(0)
                item.instance.setSelectionEnable(1)
            except Exception:
                printExc()

            if self.iptv_num_sel_items is not None and self.iptv_num_sel_items >= self.iptv_max_sel_items:
                maxItemsSelected = True
            else:
                return

        if self.iptv_accep_label is not None or maxItemsSelected:
            ret = []
            for y in range(self.iptv_row_num):
                for x in range(self.iptv_col_num):
                    if self.iptv_grid[x][y]['selected']:
                        ret.append(self.iptv_grid[x][y]['id'])
            self.close(ret)

    def key_read(self):
        self.close(None)

    def key_cancel(self):
        self.close(None)

    def key_green(self):
        pass

    def setMarker(self, prevIdx=None):
        if self.iptv_accep_label is not None:
            if self.row_index == self.iptv_row_num:
                self['accept_button'].instance.setForegroundColor(parseColor("#000000"))
                self['accept_button'].instance.setBackgroundColor(parseColor("#32CD32"))
                for i in range(self.iptv_col_num):
                    item = self["col_%d" % i]
                    item.instance.setSelectionEnable(0)
            else:
                self['accept_button'].instance.setForegroundColor(parseColor("#FFFFFF"))
                # opaque mid-gray, not a translucent near-black - the
                # same accept-button pattern in captchapuzzlegridwidget.py
                # uses this color since a translucent one is nearly
                # invisible over dark video.
                self['accept_button'].instance.setBackgroundColor(parseColor("#3A3A3A"))
                self.changeColumnSelection()

    def move_list_up(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveUp)

    def move_list_down(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelection(item.instance.moveDown)

    def set_list_index(self):
        for i in range(self.iptv_col_num):
            item = self["col_%d" % i]
            if item.instance is not None:
                item.instance.moveSelectionTo(self.row_index)

    def key_up(self):
        prev_row_index = self.row_index
        if self.row_index == 0:
            if self.iptv_accep_label is not None:
                self.row_index = self.iptv_row_num
            else:
                self.row_index = self.iptv_row_num - 1
        elif self.row_index == self.iptv_row_num:
            self.row_index = self.iptv_row_num - 1
        else:
            self.row_index -= 1

        if self.row_index < self.iptv_row_num:
            if prev_row_index == self.iptv_row_num:
                self.setMarker()
                self.set_list_index()
            else:
                self.move_list_up()

        if self.iptv_row_num == self.row_index:
            self.setMarker()

    def key_down(self):
        prev_row_index = self.row_index
        if self.row_index + 1 == self.iptv_row_num:
            if self.iptv_accep_label is not None:
                self.row_index = self.iptv_row_num
            else:
                self.row_index = 0
        elif self.row_index == self.iptv_row_num:
            self.row_index = 0
        else:
            self.row_index += 1

        if self.row_index < self.iptv_row_num:
            if prev_row_index == self.iptv_row_num:
                self.setMarker()
                self.set_list_index()
            else:
                self.move_list_down()

        if self.iptv_row_num == self.row_index:
            self.setMarker()

    def key_home(self):
        pass

    def key_end(self):
        pass

    def key_page_up(self):
        pass

    def key_page_down(self):
        pass

    def key_left(self):
        if self.row_index < self.iptv_row_num:
            if self.column_index == 0:
                self.column_index = self.iptv_col_num - 1
            else:
                self.column_index -= 1
            self.changeColumnSelection()

    def key_right(self):
        if self.row_index < self.iptv_row_num:
            if self.column_index == self.iptv_col_num - 1:
                self.column_index = 0
            else:
                self.column_index += 1
            self.changeColumnSelection()
