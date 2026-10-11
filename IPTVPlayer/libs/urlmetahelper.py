# -*- coding: utf-8 -*-
# Added: 20.07.2026 - URL meta helper for sidecar and MKV postprocess handling - Kamikaze24
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

import re

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
    meta.pop("e2i_sidecar_meta", None)
    return meta


def _setSidecarMeta(meta, sidecar):
    # sidecar: buildSidecar() dict; its "meta" (sidecarMetaQuery) goes along as e2i_sidecar_meta
    meta = dict(meta)
    if sidecar.get("enabled", False):
        meta["e2i_sidecar_enabled"] = True
        meta["e2i_sidecar_txt"] = sidecar.get("txt", "")
        meta["e2i_sidecar_img"] = sidecar.get("img", "")
        if sidecar.get("meta"):
            meta["e2i_sidecar_meta"] = dict(sidecar["meta"])
        else:
            meta.pop("e2i_sidecar_meta", None)
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


def _autoSkip(title):
    # LATIN_ONLY for a title in Arabic (or another script) only, as the hosts do
    from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, isLatinTitle
    return () if isLatinTitle(title) else LATIN_ONLY


def sidecarMetaQuery(mediaType, title="", year="", imdbId="", skip=None, maxYearDiff=None, altTitles=()):
    # what the download manager looks up in libs/moviemeta for the sidecar of a download (iptvdm/downloaderhelpers.py,
    # in a thread while the file downloads - playing a link costs no lookup). Give it the arguments of the host's own
    # getMeta() / getMetaByImdbId() call of its INFO view: an INFO opened before answers from the moviemeta cache.
    # skip None: _autoSkip() of each title. altTitles: the titles INFO tries next when the first one finds nothing
    # (original / local title). {} = no lookup.
    try:
        title = str(title or "").strip()
        imdbId = str(imdbId or "").strip()
        if not re.match(r"^tt\d+$", imdbId):
            imdbId = ""
        if mediaType not in ("movie", "tv") or not (title or imdbId):
            return {}
        query = {"type": mediaType, "title": title, "year": str(year or "").strip()[:4]}
        if imdbId:
            query["imdb"] = imdbId
        titleSkip = _autoSkip(title) if skip is None else skip
        if titleSkip:
            query["skip"] = list(titleSkip)
        if maxYearDiff is not None:
            query["maxYearDiff"] = int(maxYearDiff)
        alts = []
        for alt in altTitles or ():
            alt = str(alt or "").strip()
            if alt and alt != title and alt not in [a[0] for a in alts]:
                alts.append([alt, list(_autoSkip(alt) if skip is None else skip)])
        if alts:
            query["alt"] = alts
        return query
    except Exception:
        printExc()
        return {}


def sidecarMetaQueryFromItem(cItem):
    # the moviemeta convention of the list items: meta_type ("movie" / "tv"), meta_title, meta_year, meta_imdb
    try:
        cItem = cItem or {}
        return sidecarMetaQuery(cItem.get("meta_type", ""), cItem.get("meta_title", ""), cItem.get("meta_year", ""), cItem.get("meta_imdb", ""))
    except Exception:
        printExc()
        return {}


def infoSidecarMetaQuery(cItem, default=None):
    # the moviemeta lookup that answered on the INFO of cItem in this session (moviemeta.getInfoQuery), else default
    try:
        from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getInfoQuery
        query = getInfoQuery(cItem)
        if query:
            return query
    except Exception:
        printExc()
    return default


def buildSidecar(enabled, txt, img, meta=None):
    # meta: sidecarMetaQuery() - the download manager adds the moviemeta details to txt / img
    sidecar = {"enabled": bool(enabled), "txt": txt or "", "img": img or ""}
    if meta:
        sidecar["meta"] = dict(meta)
    return sidecar


def mergeSidecar(baseSidecar, enabled=None, txt=None, img=None, meta=None):
    sidecar = {"enabled": False, "txt": "", "img": ""}

    try:
        if isinstance(baseSidecar, dict):
            sidecar["enabled"] = bool(baseSidecar.get("enabled", False))
            sidecar["txt"] = baseSidecar.get("txt", "")
            sidecar["img"] = baseSidecar.get("img", "")
            if baseSidecar.get("meta"):
                sidecar["meta"] = dict(baseSidecar["meta"])

        if enabled is not None:
            sidecar["enabled"] = bool(enabled)
        if txt is not None:
            sidecar["txt"] = txt
        if img is not None:
            sidecar["img"] = img
        if meta is not None:
            sidecar.pop("meta", None)
            if meta:
                sidecar["meta"] = dict(meta)
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
            if isinstance(meta.get("e2i_sidecar_meta"), dict) and meta["e2i_sidecar_meta"]:
                sidecar["meta"] = dict(meta["e2i_sidecar_meta"])
    except Exception:
        printExc()
    return sidecar


# moviemeta info keys in the order of the sidecar's lines (labels: ArticleContent.RICH_DESC_LABELS, as on INFO)
SIDECAR_META_FIELDS = ("original_title", "imdb_rating", "tmdb_rating", "rating", "genres", "duration", "released", "first_air_date",
                       "seasons", "episodes", "age_limit", "country", "station", "directors", "creators", "writers", "cast", "awards")


def formatSidecarText(meta, siteTxt="", siteTextFirst=False):
    # sidecar text of a moviemeta answer: "Title (year)", one "Label: value" line per known field, a blank line,
    # the plot (the site's text when moviemeta has none). siteTextFirst: the site's text when there is one -
    # for a series, whose episodes have their own text while moviemeta knows the show's plot only
    try:
        from Plugins.Extensions.IPTVPlayer.components.ihost import ArticleContent
        from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
        info = meta.get("info") or {}
        title = _normSidecarText(meta.get("title", ""))
        year = _normSidecarText(info.get("year", ""))
        lines = []
        if title:
            lines.append("%s (%s)" % (title, year) if year else title)
        for key in SIDECAR_META_FIELDS:
            value = _normSidecarText(info.get(key, ""))
            if value:
                lines.append("%s %s" % (_(ArticleContent.RICH_DESC_LABELS.get(key, key)), value))
        plot, site = _normSidecarText(meta.get("plot", "")), _normSidecarText(siteTxt)
        text = (site or plot) if siteTextFirst else (plot or site)
        if text:
            lines.extend(["", text])
        return "\n".join(lines).strip()
    except Exception:
        printExc()
        return _normSidecarText(siteTxt)


def lookupSidecarMeta(query, siteTxt="", siteImg=""):
    # (txt, img) of a sidecar with the moviemeta details of query (sidecarMetaQuery); the poster replaces the
    # site's picture as on the INFO screen. Blocks (network): the download manager calls it in a thread.
    try:
        from Plugins.Extensions.IPTVPlayer.libs.moviemeta import getMeta, getMetaByImdbId
        meta = {}
        if query.get("imdb"):
            meta = getMetaByImdbId(query.get("type", ""), query["imdb"])
        if not meta and query.get("title"):
            meta = getMeta(query.get("type", ""), query["title"], query.get("year", ""), tuple(query.get("skip") or ()), query.get("maxYearDiff"))
        for alt, altSkip in query.get("alt") or ():
            if meta:
                break
            meta = getMeta(query.get("type", ""), alt, query.get("year", ""), tuple(altSkip or ()), query.get("maxYearDiff"))
        if not meta:
            printDBG("urlmetahelper sidecar: no moviemeta details for %r" % (query,))
            return siteTxt, siteImg
        return formatSidecarText(meta, siteTxt, query.get("type") == "tv"), meta.get("poster") or siteImg
    except Exception:
        printExc()
        return siteTxt, siteImg


def sidecarFromMeta(url, cfgEnabled=True):
    return sidecarFromUrlMeta(url, cfgEnabled)


def _normSidecarText(value):
    try:
        value = str(value or "").replace("\r", "\n")
        return re.sub(r"\n{3,}", "\n\n", value).strip()
    except Exception:
        printExc()
        return ""


def buildSidecarFromItem(cItem, enabled=True, extraText="", metaQuery=None):
    # convenience for hosts: assemble a sidecar straight from a list item's own
    # metadata - an optional richer text first (e.g. a real synopsis the host
    # already fetched), then the item's [/br]-joined desc, plus its icon as the
    # poster. Whether it is actually written is still governed by `enabled`.
    # metaQuery: the moviemeta lookup of the download (sidecarMetaQuery); None = from the
    # item's meta_type / meta_title / meta_year / meta_imdb, {} = none. The lookup that answered
    # on the item's INFO in this session goes first (infoSidecarMetaQuery).
    try:
        cItem = cItem or {}
        head = _normSidecarText(extraText)
        body = _normSidecarText(str(cItem.get("txt", "") or cItem.get("desc", "") or "").replace("[/br]", "\n"))
        if body and body not in head:
            txt = (head + "\n\n" + body).strip() if head else body
        else:
            txt = head
        if not enabled:
            metaQuery = {}
        else:
            metaQuery = infoSidecarMetaQuery(cItem, sidecarMetaQueryFromItem(cItem) if metaQuery is None else metaQuery)
        return buildSidecar(enabled, txt, str(cItem.get("icon", "") or ""), metaQuery)
    except Exception:
        printExc()
        return buildSidecar(False, "", "")


def applySidecarToLinks(links, sidecar):
    # decorate every link's url meta with the sidecar in place; safe no-op when
    # the sidecar is missing / disabled or there are no links
    try:
        if not links or not isinstance(sidecar, dict) or not sidecar.get("enabled"):
            return links
        for item in links:
            try:
                item["url"] = decorateUrl(item["url"], sidecar=sidecar)
            except Exception:
                printExc()
    except Exception:
        printExc()
    return links


def decorateUrl(url, referer=None, sidecar=None, mkvEnabled=False, extraMeta=None):
    try:
        meta = getUrlMeta(url)

        if referer is not None:
            meta["Referer"] = referer

        if sidecar is not None:
            meta = _setSidecarMeta(meta, sidecar)

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
            itemMeta = _setSidecarMeta(itemMeta, sidecar)

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
            itemMeta = _setSidecarMeta(itemMeta, sidecar)

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
            meta = _setSidecarMeta(meta, sidecar)

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
