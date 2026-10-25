# -*- coding: utf-8 -*-
# Added: 24.10.2026 - automatic link choice of the "Select link" list
#
# "Default video quality": the height a link name carries ("720p", "1280x720", "4K") and the link of a
# quality list closest to the wish. "Select link automatically": the order the mirrors are tried in (the
# preferred quality first, mirrors that already failed and trailers left out) and H.264 links too wide for
# the receiver. The list side lives in components/iptvplayerwidget.py; these functions have no enigma2 /
# host access (tests/test_linkpicker.py).
###################################################
# FOREIGN import
###################################################
import re
###################################################

# "1280x720" and YouTube's "720x1280" (height first): the shorter side, as "720p" counts it
_RE_WXH = re.compile(r'(?<!\d)(\d{3,4})\s*[xX\u00d7]\s*(\d{3,4})(?!\d)')
# "720p", "1080i" and YouTube's "720x" (a format given only as height)
_RE_P = re.compile(r'(?<!\d)(\d{3,4})(?:[pPiI](?![a-zA-Z])|[xX](?![a-zA-Z0-9]))')
_RE_4K = re.compile(r'(?<![a-zA-Z0-9])(4k|uhd)(?![a-zA-Z0-9])', re.I)
_RE_FHD = re.compile(r'(?<![a-zA-Z0-9])fhd(?![a-zA-Z0-9])', re.I)
# H.264 in a link name: the HLS codec ("avc1", "avc1.640028") or "h264" / "h.264"
_RE_H264 = re.compile(r'(?<![a-zA-Z0-9])(avc1?|h\.?264)(?![a-zA-Z0-9])', re.I)


def linkHeight(name):
    # video height a link name carries, 0 = none (or an audio only stream)
    name = name or ''
    if 'audio only' in name.lower():
        return 0
    for match in _RE_WXH.finditer(name):
        height = min(int(match.group(1)), int(match.group(2)))
        if 144 <= height <= 4320:
            return height
    for match in _RE_P.finditer(name):
        height = int(match.group(1))
        if 144 <= height <= 4320:
            return height
    if _RE_4K.search(name):
        return 2160
    if _RE_FHD.search(name):
        return 1080
    return 0


def isTooWideH264(name):
    # H.264 above 1920 pixels (e.g. "res: 2592x1080 mp4a,avc1"): the H.264 decoders of most receivers stay black
    # there (4K only for HEVC/VP9) - only the sound plays, the player itself reports no error
    name = name or ''
    if not _RE_H264.search(name):
        return False
    for match in _RE_WXH.finditer(name):
        if max(int(match.group(1)), int(match.group(2))) > 1920:
            return True
    return False


def _targetHeight(heights, preferred):
    # preferred: '' (ask), 'max' or a height as text ('720'); the highest height not above the wish,
    # the lowest one when all are above it
    heights = [h for h in heights if h > 0]
    if not heights or not preferred:
        return 0
    if preferred == 'max':
        return max(heights)
    try:
        wish = int(preferred)
    except ValueError:
        return 0
    below = [h for h in heights if h <= wish]
    return max(below) if below else min(heights)


def pickByQuality(links, preferred):
    # a list of qualities (every video link names its height): the link closest to the wish, else None
    heights = [linkHeight(link.name) for link in links]
    video = [h for link, h in zip(links, heights) if 'audio only' not in (link.name or '').lower()]
    if len(links) < 2 or not video or 0 in video:
        return None
    target = _targetHeight(heights, preferred)
    for link, height in zip(links, heights):
        if target and height == target:
            return link
    return None


def isTrailer(link):
    return 'trailer' in (link.name or '').lower()


def autoOrder(links, preferred, isFailed):
    # the order "Select link automatically" tries the links in: the preferred quality first, then the next
    # lower ones, links without a height, the higher ones last - the host's order within each step; links
    # that failed already are left out unless all of them failed, a trailer next to the video's own links
    # too (it is no replacement for the video)
    links = [link for link in links if not isTrailer(link)] or list(links)
    candidates = [link for link in links if not isFailed(link)] or list(links)
    target = _targetHeight([linkHeight(link.name) for link in candidates], preferred)
    if not target:
        return candidates

    def rank(link):
        height = linkHeight(link.name)
        if height == target:
            return (0, 0)
        if 0 < height < target:
            return (1, -height)
        if height == 0:
            return (2, 0)
        return (3, height)
    return sorted(candidates, key=rank)
