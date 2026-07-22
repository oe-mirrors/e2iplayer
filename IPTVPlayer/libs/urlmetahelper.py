# -*- coding: utf-8 -*-
# Added: 20.07.2026 - URL meta helper for sidecar and MKV postprocess handling - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

###################################################
# FOREIGN import
###################################################
###################################################


def _safeStr(url):
    try:
        return str(url)
    except Exception:
        try:
            return "%s" % url
        except Exception:
            return ""


def getUrlMeta(url):
    try:
        return dict(strwithmeta(url).meta)
    except Exception:
        return {}


def setUrlMeta(url, meta):
    try:
        return strwithmeta(_safeStr(url), dict(meta))
    except Exception:
        printExc()
        return url


def _clearSidecarMeta(meta):
    meta.pop("e2i_sidecar_enabled", None)
    meta.pop("e2i_sidecar_txt", None)
    meta.pop("e2i_sidecar_img", None)
    return meta


def _setSidecarMeta(meta, enabled, txt, img):
    meta = dict(meta)
    if enabled:
        meta["e2i_sidecar_enabled"] = True
        meta["e2i_sidecar_txt"] = txt
        meta["e2i_sidecar_img"] = img
    else:
        _clearSidecarMeta(meta)
    return meta


def _clearMkvMeta(meta):
    meta.pop("e2i_download_ext", None)
    meta.pop("e2i_postprocess_ffmpeg", None)
    meta.pop("e2i_postprocess_container", None)
    return meta


def _setMkvMeta(meta, itemUrl, enabled):
    meta = dict(meta)
    if enabled:
        proto = _safeStr(meta.get("iptv_proto", "")).lower()
        testUrl = _safeStr(itemUrl).lower()
        cleanUrl = testUrl.split("?", 1)[0]

        isHls = (proto == "m3u8" or ".m3u8" in testUrl)
        isDirectHttp = (proto in ("http", "https"))
        hasKnownVideoExt = cleanUrl.endswith((".mp4", ".m4v", ".mov", ".ts", ".m2ts", ".webm", ".mkv"))

        if isHls or isDirectHttp:
            meta["e2i_download_ext"] = "mkv"
            meta["e2i_postprocess_ffmpeg"] = "1"
            meta["e2i_postprocess_container"] = "mkv"
            printDBG("urlmetahelper MKV meta enabled url[%s] proto[%s] hls[%s] direct[%s] ext[%s]" % (
                itemUrl, proto, isHls, isDirectHttp, hasKnownVideoExt
            ))
        else:
            _clearMkvMeta(meta)
    else:
        _clearMkvMeta(meta)
    return meta


def buildSidecar(enabled, txt, img):
    return {"enabled": bool(enabled), "txt": txt or "", "img": img or ""}


def mergeSidecar(baseSidecar, enabled=None, txt=None, img=None):
    sidecar = {"enabled": False, "txt": "", "img": ""}

    try:
        if isinstance(baseSidecar, dict):
            sidecar["enabled"] = bool(baseSidecar.get("enabled", False))
            sidecar["txt"] = baseSidecar.get("txt", "")
            sidecar["img"] = baseSidecar.get("img", "")

        if enabled is not None:
            sidecar["enabled"] = bool(enabled)
        if txt is not None:
            sidecar["txt"] = txt
        if img is not None:
            sidecar["img"] = img
    except Exception:
        printExc()

    return sidecar


def sidecarFromUrlMeta(url, cfgEnabled=True):
    sidecar = {"enabled": False, "txt": "", "img": ""}
    try:
        meta = getUrlMeta(url)
        enabled = cfgEnabled and bool(meta.get("e2i_sidecar_enabled", False))
        sidecar["enabled"] = enabled
        if enabled:
            sidecar["txt"] = meta.get("e2i_sidecar_txt", "")
            sidecar["img"] = meta.get("e2i_sidecar_img", "")
    except Exception:
        printExc()
    return sidecar


def sidecarFromMeta(url, cfgEnabled=True):
    return sidecarFromUrlMeta(url, cfgEnabled)


def decorateUrl(url, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None):
    try:
        meta = getUrlMeta(url)

        if referer is not None:
            meta["Referer"] = referer

        if sidecar is not None:
            meta = _setSidecarMeta(meta, sidecar.get("enabled", False), sidecar.get("txt", ""), sidecar.get("img", ""))

        meta = _setMkvMeta(meta, url, mkvEnabled)

        if isinstance(extraMeta, dict):
            meta.update(extraMeta)

        return setUrlMeta(url, meta)
    except Exception:
        printExc()
        return url


def decorateCachedLinkItem(item, sidecar=None):
    try:
        newItem = dict(item)
        itemUrl = newItem.get("url", "")
        itemMeta = getUrlMeta(itemUrl)

        if sidecar is not None:
            itemMeta = _setSidecarMeta(itemMeta, sidecar.get("enabled", False), sidecar.get("txt", ""), sidecar.get("img", ""))

        newItem["url"] = setUrlMeta(itemUrl, itemMeta)
        return newItem
    except Exception:
        printExc()
        return item


def decorateCachedLinkItems(items, sidecar=None):
    outTab = []
    for item in items:
        outTab.append(decorateCachedLinkItem(item, sidecar))
    return outTab


def decorateResolvedLinkItem(item, sidecar=None, mkvEnabled=False):
    try:
        newItem = dict(item)
        itemUrl = newItem.get("url", "")
        itemMeta = getUrlMeta(itemUrl)

        if sidecar is not None:
            itemMeta = _setSidecarMeta(itemMeta, sidecar.get("enabled", False), sidecar.get("txt", ""), sidecar.get("img", ""))

        itemMeta = _setMkvMeta(itemMeta, itemUrl, mkvEnabled)
        newItem["url"] = setUrlMeta(itemUrl, itemMeta)
        return newItem
    except Exception:
        printExc()
        return item


def decorateResolvedLinkItems(items, sidecar=None, mkvEnabled=False):
    outTab = []
    for item in items:
        outTab.append(decorateResolvedLinkItem(item, sidecar, mkvEnabled))
    return outTab


def decorateLinkItem(item, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None):
    try:
        newItem = dict(item)
        newItem["url"] = decorateUrl(newItem.get("url", ""), referer=referer, sidecar=sidecar, mkvEnabled=mkvEnabled, extraMeta=extraMeta)
        return newItem
    except Exception:
        printExc()
        return item


def decorateLinkItems(items, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None):
    outTab = []
    for item in items:
        outTab.append(decorateLinkItem(item, referer=referer, sidecar=sidecar, mkvEnabled=mkvEnabled, extraMeta=extraMeta))
    return outTab


def _clearYoutubeMeta(meta):
    meta.pop("e2i_mkv_chapters", None)
    meta.pop("e2i_cuts_chapters", None)
    meta.pop("e2i_channel_name", None)
    return meta


def _setYoutubeMeta(meta, mkvChaptersEnabled=False, cutsChaptersEnabled=False, channelName=""):
    meta = dict(meta)

    if mkvChaptersEnabled:
        meta["e2i_mkv_chapters"] = True
    else:
        meta.pop("e2i_mkv_chapters", None)

    if cutsChaptersEnabled:
        meta["e2i_cuts_chapters"] = True
    else:
        meta.pop("e2i_cuts_chapters", None)

    if channelName:
        meta["e2i_channel_name"] = channelName
    else:
        meta.pop("e2i_channel_name", None)

    return meta


def buildYoutubeOptions(mkvChaptersEnabled=False, cutsChaptersEnabled=False, channelName=""):
    return {
        "mkv_chapters": bool(mkvChaptersEnabled),
        "cuts_chapters": bool(cutsChaptersEnabled),
        "channel_name": channelName or ""
    }


def decorateYoutubeUrl(url, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None, youtubeOptions=None):
    try:
        meta = getUrlMeta(url)

        if referer is not None:
            meta["Referer"] = referer

        if sidecar is not None:
            meta = _setSidecarMeta(meta, sidecar.get("enabled", False), sidecar.get("txt", ""), sidecar.get("img", ""))

        meta = _setMkvMeta(meta, url, mkvEnabled)

        if isinstance(youtubeOptions, dict):
            meta = _setYoutubeMeta(
                meta,
                youtubeOptions.get("mkv_chapters", False),
                youtubeOptions.get("cuts_chapters", False),
                youtubeOptions.get("channel_name", "")
            )

        if isinstance(extraMeta, dict):
            meta.update(extraMeta)

        return setUrlMeta(url, meta)
    except Exception:
        printExc()
        return url


def decorateYoutubeLinkItem(item, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None, youtubeOptions=None):
    try:
        newItem = dict(item)
        newItem["url"] = decorateYoutubeUrl(
            newItem.get("url", ""),
            referer=referer,
            sidecar=sidecar,
            mkvEnabled=mkvEnabled,
            extraMeta=extraMeta,
            youtubeOptions=youtubeOptions
        )
        return newItem
    except Exception:
        printExc()
        return item


def decorateYoutubeLinkItems(items, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None, youtubeOptions=None):
    outTab = []
    for item in items:
        outTab.append(decorateYoutubeLinkItem(
            item,
            referer=referer,
            sidecar=sidecar,
            mkvEnabled=mkvEnabled,
            extraMeta=extraMeta,
            youtubeOptions=youtubeOptions
        ))
    return outTab
