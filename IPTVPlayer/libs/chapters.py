# -*- coding: utf-8 -*-
#
#  Chapters from a video description ("0:00 Intro" lists like YouTube): the player (chapter in the infobar, marks on
#  the progress bar, >|/|< jumps) and the merge downloader (MKV chapters, Enigma2 cuts) read them here, so both find
#  the same chapters. No enigma2 imports.
#
import re

MIN_CHAPTERS = 2
# like YouTube: a chapter is at least 10 s long; a shorter step is no chapter (dropped, not the whole list)
MIN_CHAPTER_MS = 10000

_TS = r'(?<!\d)(?<!\d:)(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})(?!\d|:\d)'
# a markdown link of the time: [0:00](https://www.youtube.com/watch?v=...&t=0s)
_LINK = r'(?:\]\s*\([^)\s]*\))?'
# time first: "0:00 Intro", "- 00:00 - Intro", "• 0:00 | Intro", "[0:00] Intro", "(0:00) Intro", "[0:00](url) Intro"
_TS_FIRST_RE = re.compile(r'^[\s\-–—•●►▶*>]*[\[(]?\s*' + _TS + r'\s*' + _LINK + r'[\])]?[\s\-–—:|•.]*(?P<title>\S.*)$')
# time last: "Intro 0:00", "Intro - 0:00", "Intro (0:00)" - only used when no list with the time first is there
_TS_LAST_RE = re.compile(r'^[\s\-–—•●►▶*>]*(?P<title>\S.*?)[\s\-–—:|•]*[\[(]?\s*' + _TS + r'\s*' + _LINK + r'[\])]?\s*$')
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)\s]*\)')
_TITLE_STRIP = ' \t-–—:|•'


def timeToMs(ts):
    # "1:02:03" / "02:03" / "75:30" -> ms; None for seconds over 59, or minutes over 59 next to hours
    try:
        parts = [int(x) for x in ts.split(':')]
    except (ValueError, AttributeError):
        return None
    if len(parts) == 2:
        minutes, seconds = parts
        return (minutes * 60 + seconds) * 1000 if seconds <= 59 else None
    if len(parts) != 3 or parts[1] > 59 or parts[2] > 59:
        return None
    return (parts[0] * 3600 + parts[1] * 60 + parts[2]) * 1000


def formatTime(ms):
    sec = max(0, int(ms // 1000))
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    if h:
        return '%d:%02d:%02d' % (h, m, s)
    return '%d:%02d' % (m, s)


def _cleanTitle(title):
    title = _MD_LINK_RE.sub(r'\1', title)
    return re.sub(r'\s+', ' ', title).strip(_TITLE_STRIP)


def _chapterList(entries, requireStartAtZero):
    # the list starts at its 0:00 line and runs on as long as the times rise: a second list further down (other
    # language) or a time in the running text that goes back does not get mixed in
    out = []
    for ms, title in entries:
        if not out:
            if ms == 0 or not requireStartAtZero:
                out.append({'start': ms, 'title': title})
        elif ms >= out[-1]['start'] + MIN_CHAPTER_MS:
            out.append({'start': ms, 'title': title})
        elif ms < out[-1]['start'] and len(out) >= MIN_CHAPTERS:
            break
        elif ms == 0 and len(out) < MIN_CHAPTERS:
            # a lone 0:00 earlier in the text was no list: start over
            out = [{'start': ms, 'title': title}]
    return out if len(out) >= MIN_CHAPTERS else []


def parseChapters(text, requireStartAtZero=True):
    # [{'start': ms, 'title': '...'}, ...] or [] - like YouTube: the first chapter at 0:00, at least 2 chapters
    if not text:
        return []
    if isinstance(text, bytes):
        text = text.decode('utf-8', 'ignore')
    first, last = [], []
    for line in text.replace('\r', '\n').split('\n'):
        line = line.strip()
        if not line:
            continue
        m = _TS_FIRST_RE.match(line)
        target = first
        if not m:
            m = _TS_LAST_RE.match(line)
            target = last
        if not m:
            continue
        ms = timeToMs(m.group('ts'))
        title = _cleanTitle(m.group('title'))
        if ms is None or not title:
            continue
        target.append((ms, title))
    return _chapterList(first, requireStartAtZero) or _chapterList(last, requireStartAtZero)


def chapterIndexAt(chapters, posMs):
    idx = 0
    for i, chapter in enumerate(chapters):
        if chapter['start'] <= posMs:
            idx = i
        else:
            break
    return idx


def chapterLabel(chapter):
    return '%s • %s' % (formatTime(chapter['start']), chapter['title'])
