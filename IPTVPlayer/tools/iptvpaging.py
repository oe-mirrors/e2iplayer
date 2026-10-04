# -*- coding: utf-8 -*-
# Pager rows for CBaseHostClass hosts: "First page", "Jump" (asks for a page number) and
# "Next page" - "Next page (2/12)" and "Page: 1/12" in the header when the last page is known
# (see CHostBase.converItem: 'page', 'last_page', 'image_type').
#
#   addPagingItems(self, cItem, page, hasNext, lastPage=0, pageUrlTpl='', nextParams=None)
#       after the list items; page = the page just listed (1-based). pageUrlTpl: the url of any page
#       with "{page}" in it (e.g. "https://site/movies/page/{page}/") - needed for "Jump" and used for
#       "First page"; without it the host's list function must build the url from cItem['page'].
#   in handleService, before dispatching on the category:
#       if isJumpItem(self.currItem):
#           self.currItem = jumpTarget(self, self.currItem)   # asks for the page, returns the list item
#           category = self.currItem.get("category", "")
#
# The rows keep the folder's own fields (url, watched key ...) so the watched/favourite logic of the
# host sees the same folder; they are never favourites.
#
#   stripPagerKeys(params, extraKeys=())
#       for rows built from the listed item (params = dict(cItem)): a pager row is the cItem of the
#       page it opens, so its page / last_page / image_type would reach every folder and video listed
#       there (wrong icon, a folder opened from page 5 starting at page 5). extraKeys: the host's own
#       paging state (base_url, page_tpl ...).
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc

JUMP_CATEGORY = "iptv_paging_jump"
PAGER_ROW_KEYS = ("page", "last_page", "image_type")
_PAGER_KEYS = ("image_type", "jump_category", "max_page", "current_page", "page_url_tpl")


def _toInt(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def stripPagerKeys(params, extraKeys=()):
    """removes the pager fields from params (in place) and returns it"""
    for key in PAGER_ROW_KEYS + _PAGER_KEYS + tuple(extraKeys):
        params.pop(key, None)
    return params


def _base(cItem):
    # every pager row sets its own page (and last_page only when known), nothing is inherited
    params = stripPagerKeys(dict(cItem))
    params["good_for_fav"] = False
    return params


def _pageUrl(pageUrlTpl, page):
    try:
        return pageUrlTpl.format(page=page) if pageUrlTpl else ""
    except Exception:
        printExc()
        return ""


def addPagingItems(host, cItem, page, hasNext, lastPage=0, pageUrlTpl="", nextParams=None):
    page = max(1, _toInt(page, 1))
    lastPage = _toInt(lastPage, 0)
    if lastPage and lastPage < page:
        lastPage = 0
    category = cItem.get("category", "")

    if page > 1:
        params = _base(cItem)
        params.update({"title": _("First Page"), "page": 1, "image_type": "FIRST"})
        url = _pageUrl(pageUrlTpl, 1)
        if url:
            params["url"] = url
        host.addDir(params)

    if pageUrlTpl and (hasNext or page > 1) and lastPage != 1:
        params = _base(cItem)
        params.update({"title": "%s %d/%d" % (_("Jump"), page, lastPage) if lastPage else _("Jump"),
                       "desc": _("Jump to a selected page, max: {}").format(lastPage) if lastPage else _("Jump to a selected page"),
                       "category": JUMP_CATEGORY, "jump_category": category, "max_page": lastPage, "current_page": page,
                       "page_url_tpl": pageUrlTpl, "image_type": "JUMP"})
        host.addDir(params)

    if hasNext:
        params = _base(cItem)
        params.update({"title": _("Next page"), "page": page + 1})
        if lastPage:
            params["last_page"] = lastPage
        url = _pageUrl(pageUrlTpl, page + 1)
        if url:
            params["url"] = url
        if nextParams:
            params.update(nextParams)
        host.addDir(params)


def isJumpItem(cItem):
    return isinstance(cItem, dict) and cItem.get("category") == JUMP_CATEGORY


def jumpTarget(host, cItem):
    """asks for the page number, returns the item to list that page with (category = the list's own)"""
    maxPage = _toInt(cItem.get("max_page"), 0)
    current = max(1, _toInt(cItem.get("current_page"), 1))
    title = _("Jump to a selected page, max: {}").format(maxPage) if maxPage else _("Jump to a selected page")
    page = current
    try:
        from Plugins.Extensions.IPTVPlayer.components.e2ivkselector import GetNumericKeyboard, GetVirtualKeyboard
        numKeyboard = GetNumericKeyboard()  # None when the keypad is off or the "System" keyboard is selected
        if numKeyboard is not None:
            ret = host.sessionEx.waitForFinishOpen(numKeyboard, title=title, text=str(current),
                                                   additionalParams={"min_value": 1, "max_value": maxPage or 9999})
        else:
            ret = host.sessionEx.waitForFinishOpen(GetVirtualKeyboard(), title=title, text=str(current))
        if isinstance(ret, tuple) and len(ret):
            ret = ret[0]
        ret = (ret or "").strip()
        if ret.isdigit():
            page = int(ret)
    except Exception:
        printExc()
    page = max(1, page)
    if maxPage:
        page = min(page, maxPage)
    target = dict(cItem)
    for key in _PAGER_KEYS:
        target.pop(key, None)
    target.update({"category": cItem.get("jump_category", ""), "page": page})
    url = _pageUrl(cItem.get("page_url_tpl", ""), page)
    if url:
        target["url"] = url
    printDBG("iptvpaging: jump %d -> %d [%s]" % (current, page, target.get("url", "")))
    host.currItem = target
    return target
