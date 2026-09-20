# -*- coding: utf-8 -*-
# Latest uploads of YouTube channels, used by the favourites groups
# ("sort channels by newest upload" and the merged "newest videos" list).
#
# Reads the public per-channel Atom feed
#   https://www.youtube.com/feeds/videos.xml?channel_id=UC...
# - no InnerTube request, no login, so it is not affected by the bot wall and
# is cheap enough to ask for a whole group of channels at once.
###################################################
# LOCAL import
###################################################
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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"

CACHE_TTL = 600  # seconds a fetched feed is reused
FAIL_TTL = 60  # seconds a failed channel is not asked again
MAX_WORKERS = 6
REQUEST_TIMEOUT = 10
TOTAL_TIMEOUT = 30  # upper bound for one getFeeds() call

_ATOM = "{http://www.w3.org/2005/Atom}"
_YT = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA = "{http://search.yahoo.com/mrss/}"

_CHANNEL_ID_RE = re.compile(r"/channel/(UC[A-Za-z0-9_-]{22})")
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?")

_lock = threading.Lock()
_idCache = {}  # channel url -> UC... id
_idFailed = {}  # channel url -> time of the failed lookup
_feedCache = {}  # UC... id -> (fetchedAt, info or None)


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


def _getPage(cm, url, cookie=False):
    header = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    if cookie:
        header["Cookie"] = "SOCS=CAI"  # skips the EU consent redirect
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


def clearCache():
    # forget every feed (a refresh should look for new uploads again)
    with _lock:
        _feedCache.clear()
        _idFailed.clear()


def clearFailed():
    # forget only what failed, so the next request tries those channels again instead of waiting for FAIL_TTL
    with _lock:
        for channelId in [key for key, value in _feedCache.items() if value[1] is None]:
            del _feedCache[channelId]
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
    urls = list(dict.fromkeys(urls))
    results = {}
    if not urls:
        return results
    state = {"next": 0}
    deadline = time.time() + TOTAL_TIMEOUT

    def worker():
        cm = common()
        while time.time() < deadline:
            with _lock:
                idx = state["next"]
                state["next"] += 1
            if idx >= len(urls):
                return
            try:
                info = getChannelFeed(urls[idx], cm)
            except Exception:
                printExc()
                info = None
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
