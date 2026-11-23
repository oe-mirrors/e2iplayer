# -*- coding: utf-8 -*-
# Latest uploads of YouTube channels, used by the favourites groups
# ("sort channels by newest upload" and the merged "newest videos" list).
#
# Reads the public per-channel Atom feed
#   https://www.youtube.com/feeds/videos.xml?channel_id=UC...
# - no InnerTube request, no login, so it is not affected by the bot wall and
# is cheap enough to ask for a whole group of channels at once.
# The feed has no video length: the channel's uploads playlist page
#   https://www.youtube.com/playlist?list=UU...
# shows it for its newest 100 videos (one request per channel, not per video).
# Single videos (the Shorts of "My subscriptions" and of a favourites group): the InnerTube
# player answer (~6 KB, no login) has channel, upload date, length and views of one video.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
###################################################
# FOREIGN import
###################################################
import calendar
import re
import threading
import time
import xml.etree.ElementTree as ET
###################################################

FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id=%s"
UPLOADS_URL = "https://www.youtube.com/playlist?list=UU%s"  # channel id without its "UC"
PLAYER_URL = "https://www.youtube.com/youtubei/v1/player?prettyPrint=false"
PLAYER_CLIENT = {"clientName": "WEB", "clientVersion": "2.20251120.01.00", "hl": "en", "gl": "US"}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"

CACHE_TTL = 600  # seconds a fetched feed is reused
FAIL_TTL = 60  # seconds a failed channel is not asked again
MAX_WORKERS = 6
REQUEST_TIMEOUT = 10
TOTAL_TIMEOUT = 30  # upper bound for one getFeeds() call
DURATION_TIMEOUT = 15  # upper bound for one getDurations() call
DETAILS_TIMEOUT = 15  # upper bound for one getVideosDetails() call

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA = "{http://search.yahoo.com/mrss/}"

_CHANNEL_ID_RE = re.compile(r"/channel/(UC[A-Za-z0-9_-]{22})")
# the length badge of a video in the playlist page: {"text":"12:34", ... "animationActivationTargetId":"<video id>"}
_DURATION_RE = re.compile(r'"thumbnailBadgeViewModel":\{"text":"(\d{1,2}(?::\d{2}){1,2})"[^{}]*?"animationActivationTargetId":"([A-Za-z0-9_-]{11})"')
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?")

_lock = threading.Lock()
_idCache = {}  # channel url -> UC... id
_idFailed = {}  # channel url -> time of the failed lookup
_feedCache = {}  # UC... id -> (fetchedAt, info or None)
_durationCache = {}  # UC... id -> (fetchedAt, {video id: "12:34"} or None)
_detailsCache = {}  # video id -> (fetchedAt, details or None)


def parseTimestamp(text):
    # "2026-09-17T06:14:00+00:00" -> epoch seconds (UTC), 0 if unparsable
    m = _DATE_RE.match(str(text or "").strip())
    if not m:
        return 0
    try:
        ts = calendar.timegm(tuple(int(x) for x in m.groups()[:6]) + (0, 0, 0))
        tz = m.group(7)
        if tz and tz != "Z":
            sign = -1 if tz[0] == "-" else 1
            digits = tz[1:].replace(":", "")
            ts -= sign * (int(digits[:2]) * 3600 + int(digits[2:4]) * 60)
        return ts
    except Exception:
        printExc()
    return 0


def formatDate(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def formatAge(ts, now=None):
    # compact and language independent: "5 min", "3 h", "2 d", "4 w", "7 mo", "2 y"
    delta = int((now if now is not None else time.time()) - ts)
    if delta < 0:
        delta = 0
    if delta < 3600:
        return "%d min" % (delta // 60)
    if delta < 86400:
        return "%d h" % (delta // 3600)
    if delta < 7 * 86400:
        return "%d d" % (delta // 86400)
    if delta < 30 * 86400:
        return "%d w" % (delta // (7 * 86400))
    if delta < 365 * 86400:
        return "%d mo" % (delta // (30 * 86400))
    return "%d y" % (delta // (365 * 86400))


def describeDate(ts, now=None):
    return "%s (%s)" % (formatDate(ts), formatAge(ts, now))


def formatDuration(seconds):
    # 63 -> "1:03", 3725 -> "1:02:05", "" for no length
    try:
        seconds = int(seconds)
    except Exception:
        return ""
    if seconds <= 0:
        return ""
    if seconds >= 3600:
        return "%d:%02d:%02d" % (seconds // 3600, seconds // 60 % 60, seconds % 60)
    return "%d:%02d" % (seconds // 60, seconds % 60)


def describeVideo(channel, published, duration, short, views, now=None):
    # the short info of a video in the "newest videos" style:
    # channel / upload date (age) / length | Short | views
    lines = [line for line in (channel, describeDate(published, now) if published else "") if line]
    extra = []
    if duration:
        extra.append(_("Duration: %s") % duration)
    if short:
        extra.append("Short")
    if views:
        extra.append(views + " " + _("views"))
    if extra:
        lines.append(" | ".join(extra))
    return "\n".join(lines)


def _parseEntry(entry, channel):
    videoId = entry.findtext(_YT + "videoId") or ""
    published = parseTimestamp(entry.findtext(_ATOM + "published"))
    if not videoId or not published:
        return None
    link = entry.find(_ATOM + "link")
    thumb = entry.find(_MEDIA + "group/" + _MEDIA + "thumbnail")
    stats = entry.find(_MEDIA + "group/" + _MEDIA + "community/" + _MEDIA + "statistics")
    return {
        "video_id": videoId,
        "title": ensure_str(entry.findtext(_ATOM + "title") or ""),
        "published": published,
        "channel": ensure_str(entry.findtext(_ATOM + "author/" + _ATOM + "name") or "") or channel,
        "icon": thumb.get("url", "") if thumb is not None else "",
        "views": stats.get("views", "") if stats is not None else "",
        "short": link is not None and "/shorts/" in link.get("href", ""),
    }


def parseFeed(data):
    # -> {"channel": name, "entries": [newest first]} or None if the data is no feed
    if not data:
        return None  # the request failed, already logged by _getPage()
    try:
        if not isinstance(data, bytes):
            data = data.encode("utf-8")
        root = ET.fromstring(data)
    except Exception:
        printExc()
        return None
    if not root.tag.endswith("feed"):
        printDBG("ytchannelfeed.parseFeed not a feed: [%s]" % root.tag)
        return None
    channel = ensure_str(root.findtext(_ATOM + "title") or "")
    entries = []
    for entry in root.findall(_ATOM + "entry"):
        try:
            parsed = _parseEntry(entry, channel)
            if parsed:
                entries.append(parsed)
        except Exception:
            printExc()
    entries.sort(key=lambda e: e["published"], reverse=True)
    return {"channel": channel, "entries": entries}


def _getPage(cm, url, cookie=False, gzip=False):
    header = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    if cookie:
        header["Cookie"] = "SOCS=CAI"  # skips the EU consent redirect
    if gzip:
        header["Accept-Encoding"] = "gzip"  # the playlist page: ~2 MB, ~300 KB packed (pCommon unpacks it)
    sts, data = cm.getPage(url, {"header": header, "timeout": REQUEST_TIMEOUT})
    printDBG("ytchannelfeed._getPage sts[%s] status[%s] len[%d] url[%s]" % (sts, getattr(cm, "meta", {}).get("status_code", ""), len(data or ""), url))
    return (data if sts else "")


def resolveChannelId(cm, url):
    # channel url in any of its forms (/channel/UC.., /@handle, /c/x, /user/x) -> UC... id or ""
    url = str(url or "").split("?")[0]
    m = _CHANNEL_ID_RE.search(url)
    if m:
        return m.group(1)
    with _lock:
        cached = _idCache.get(url)
        failedAt = _idFailed.get(url, 0)
    if cached:
        return cached
    if time.time() - failedAt < FAIL_TTL:
        return ""
    base = re.sub(r"/(videos|streams|shorts|featured|live|playlists|community|about)/?$", "", url.rstrip("/"))
    data = _getPage(cm, base, cookie=True)
    channelId = ""
    for pattern in (r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[A-Za-z0-9_-]{22})"',
                    r'"externalId":"(UC[A-Za-z0-9_-]{22})"',
                    r'itemprop="(?:identifier|channelId)" content="(UC[A-Za-z0-9_-]{22})"'):
        m = re.search(pattern, data)
        if m:
            channelId = m.group(1)
            break
    if channelId:
        with _lock:
            _idCache[url] = channelId
    else:
        printDBG("ytchannelfeed.resolveChannelId no channel id found for [%s] (page length %d)" % (url, len(data or "")))
        with _lock:
            _idFailed[url] = time.time()
    return channelId


def getChannelFeed(url, cm=None):
    # newest-first upload info of one channel, or None when it could not be read
    cm = cm or common()
    channelId = resolveChannelId(cm, url)
    if not channelId:
        return None
    now = time.time()
    with _lock:
        cached = _feedCache.get(channelId)
    if cached and now - cached[0] < (CACHE_TTL if cached[1] else FAIL_TTL):
        return cached[1]
    info = parseFeed(_getPage(cm, FEED_URL % channelId))
    printDBG("ytchannelfeed.getChannelFeed channel[%s] id[%s] entries[%s]" % (url, channelId, len(info["entries"]) if info else "feed not readable"))
    with _lock:
        _feedCache[channelId] = (now, info)
    return info


def parseDurations(data):
    # {video id: "12:34"} from a playlist page (videos without a length badge - live, upcoming - are left out)
    durations = {}
    for m in _DURATION_RE.finditer(data or ""):
        durations.setdefault(m.group(2), m.group(1))
    return durations


def getChannelDurations(url, cm=None):
    # {video id: "12:34"} of the newest 100 uploads of one channel, {} when the page could not be read
    cm = cm or common()
    channelId = resolveChannelId(cm, url)
    if not channelId:
        return {}
    now = time.time()
    with _lock:
        cached = _durationCache.get(channelId)
    if cached and now - cached[0] < (CACHE_TTL if cached[1] else FAIL_TTL):
        return cached[1] or {}
    durations = parseDurations(_getPage(cm, UPLOADS_URL % channelId[2:], cookie=True, gzip=True))
    printDBG("ytchannelfeed.getChannelDurations channel[%s] id[%s] lengths[%d]" % (url, channelId, len(durations)))
    with _lock:
        _durationCache[channelId] = (now, durations or None)
    return durations


def parseVideoDetails(data):
    # the InnerTube player answer -> {"channel", "published", "duration", "views"} or None
    try:
        response = json_loads(data) if data else None
    except Exception:
        printExc()
        return None
    if not isinstance(response, dict):
        return None
    details = response.get("videoDetails") or {}
    micro = (response.get("microformat") or {}).get("playerMicroformatRenderer") or {}
    channel = ensure_str(details.get("author") or micro.get("ownerChannelName") or "")
    published = parseTimestamp(micro.get("publishDate") or micro.get("uploadDate") or "")
    if not channel and not published:
        return None  # no metadata (the video is gone, or YouTube answered with a bot check)
    return {
        "channel": channel,
        "published": published,
        "duration": formatDuration(details.get("lengthSeconds") or micro.get("lengthSeconds") or 0),
        "views": str(details.get("viewCount") or micro.get("viewCount") or ""),
    }


def getVideoDetails(videoId, cm=None):
    # channel, upload date, length and views of one video, or None when they could not be read
    cm = cm or common()
    now = time.time()
    with _lock:
        cached = _detailsCache.get(videoId)
    if cached and now - cached[0] < (CACHE_TTL if cached[1] else FAIL_TTL):
        return cached[1]
    header = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9", "Content-Type": "application/json",
              "Origin": "https://www.youtube.com", "Cookie": "SOCS=CAI"}
    postData = json_dumps({"context": {"client": PLAYER_CLIENT}, "videoId": videoId})
    sts, data = cm.getPage(PLAYER_URL, {"header": header, "timeout": REQUEST_TIMEOUT, "raw_post_data": True}, postData)
    info = parseVideoDetails(data if sts else "")
    printDBG("ytchannelfeed.getVideoDetails video[%s] sts[%s] len[%d] details[%s]" % (videoId, sts, len(data or ""), "ok" if info else "none"))
    with _lock:
        _detailsCache[videoId] = (now, info)
    return info


def clearCache():
    # forget every feed (a refresh should look for new uploads again)
    with _lock:
        _feedCache.clear()
        _durationCache.clear()
        _detailsCache.clear()
        _idFailed.clear()


def clearFailed():
    # forget only what failed, so the next request tries those channels again instead of waiting for FAIL_TTL
    with _lock:
        for cache in (_feedCache, _durationCache, _detailsCache):
            for channelId in [key for key, value in cache.items() if value[1] is None]:
                del cache[channelId]
        _idFailed.clear()


def _newWorkerThread(target):
    thread = threading.Thread(target=target)
    thread.daemon = True
    # pCommon's http code asks the current thread whether it was cancelled (asynccall.IsThreadTerminated)
    # and fails every request in a thread without this record - the same one AsyncCall gives its threads
    thread._iptvplayer_ext = {'kill_lock': threading.Lock(), 'killable': True, 'terminated': False, 'iptv_execute': None}
    return thread


def getFeeds(urls):
    # {url: info or None} for many channels, fetched by a few worker threads
    return _runParallel(urls, getChannelFeed, None, TOTAL_TIMEOUT)


def getDurations(urls):
    # {url: {video id: "12:34"}} for many channels, fetched by a few worker threads
    return _runParallel(urls, getChannelDurations, {}, DURATION_TIMEOUT)


def getVideosDetails(videoIds):
    # {video id: details or None} for many videos, fetched by a few worker threads
    return _runParallel(videoIds, getVideoDetails, None, DETAILS_TIMEOUT)


def describeShorts(items, idKey="video_id"):
    # items: dicts of YouTube Shorts; puts the "newest videos" style short info into their "desc"
    # (one player request per Short, cached); an item whose details could not be read keeps its desc
    ids = [item.get(idKey) for item in items if item.get(idKey)]
    if not ids:
        return
    details = getVideosDetails(ids)
    now = time.time()
    for item in items:
        info = details.get(item.get(idKey))
        if info:
            item["desc"] = describeVideo(info["channel"], info["published"], info["duration"], True, info["views"], now)


def _runParallel(urls, fetch, failed, timeout):
    # {url: fetch(url, cm)} - failed for an url whose fetch raised; an url not finished in time is missing
    urls = list(dict.fromkeys(urls))
    results = {}
    if not urls:
        return results
    state = {"next": 0}
    deadline = time.time() + timeout

    def worker():
        cm = common()
        while time.time() < deadline:
            with _lock:
                idx = state["next"]
                state["next"] += 1
            if idx >= len(urls):
                return
            try:
                info = fetch(urls[idx], cm)
            except Exception:
                printExc()
                info = failed
            with _lock:
                results[urls[idx]] = info

    threads = [_newWorkerThread(worker) for _ in range(min(MAX_WORKERS, len(urls)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(max(0.1, deadline - time.time()))
    with _lock:
        return dict(results)


def latestUpload(info):
    # newest entry of a feed info dict or None
    if info and info.get("entries"):
        return info["entries"][0]
    return None
