# -*- coding: utf-8 -*-
# Shared media-server friendly title / download-name normalisation.
#
# Used by every host that emits normalised item titles - the mediathek hosts
# (ARD/ZDF/ARTE/ORF/SRG), serienstream.to and hdfilme. All of them honour the one
# global switch config.plugins.iptvplayer.normalize_media_names
# (IsMediaNamingNormalized); the download filename is derived from the item
# title, so normalising the title normalises the file name too.
#
# The sidecar .txt/.jpg helpers are producer-side too but live with the rest of
# that code in libs/urlmetahelper.py (buildSidecarFromItem / applySidecarToLinks);
# the consumer side is iptvdm/downloaderhelpers.py.
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printExc
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsMediaNamingNormalized
###################################################
import re


###################################################
# small SxxExx primitives (shared by all hosts)
###################################################
def extractNum(rawValue, default=0):
    # first run of digits in the value as int, else default
    try:
        m = re.search(r'\d+', str(rawValue))
        return int(m.group(0)) if m else default
    except Exception:
        return default


def formatSxxExx(seasonNum, episodeNum=None):
    # zero-padded "S02" / "S02E05" from already-resolved numbers
    sNum = extractNum(seasonNum, 0)
    if episodeNum is None:
        return 'S%02d' % sNum
    return 'S%02dE%02d' % (sNum, extractNum(episodeNum, 0))


def parseSxxExx(text):
    # 'S02E05' / 'S2 E5' / 'Staffel 2, Folge 5' / '2. Staffel Folge 5' -> ('2','5'); ('','') if none
    if not text:
        return '', ''
    try:
        m = re.search(r'S\s*0*(\d+)\s*[ .:/x_-]*\s*E\s*0*(\d+)', text, re.I)
        if m:
            return m.group(1), m.group(2)
        s = re.search(r'Staffel\s*0*(\d+)', text, re.I)
        e = re.search(r'(?:Folge|Episode)\s*0*(\d+)', text, re.I)
        if s and e:
            return s.group(1), e.group(1)
    except Exception:
        printExc()
    return '', ''


def stripLeadingSxxExx(label):
    # remove only a leading 'S<d> E<d>' run, keeping whatever separator the site
    # put after it untouched
    try:
        return re.sub(r'^\s*S\s*\d+\s*E\s*\d+\s*', '', label or '', flags=re.I)
    except Exception:
        printExc()
    return label or ''


def _pad2(num):
    n = extractNum(num, 0)
    return '%02d' % n if n > 0 else ''


def _hasSxE(title):
    return bool(re.search(r'S\d{1,3}E\d{1,3}', title.replace(' ', ''), re.I))


def _cleanText(value):
    try:
        value = str(value or '').replace('\r', '\n')
        return re.sub(r'\n{3,}', '\n\n', value).strip()
    except Exception:
        printExc()
    return ''


def _appendLang(title, lang):
    lang = str(lang or '').strip()
    if lang and lang.lower() not in title.lower():
        return '%s - %s' % (title, lang)
    return title


###################################################
# mediathek-style "augment the existing label" normaliser
###################################################
def normalizeMediathekTitle(classicTitle, date='', year='', sxeHint='', isMovie=False, lang=''):
    # Augments the host's already-decent "Show - Episode" label instead of
    # rebuilding it: drops a trailing "| ..." meta tail, inserts SxxExx after the
    # show when season/episode are known, otherwise appends (Year) for a movie
    # or (YYYY-MM-DD) for a dated episode. Returns classicTitle unchanged when
    # normalisation is off or nothing can be added.
    try:
        if not IsMediaNamingNormalized():
            return classicTitle
        title = _cleanText(classicTitle).replace('\n', ' ')
        # drop only a trailing "| ..." segment that is clearly a mediathek meta
        # tail, never a real subtitle that happens to use a pipe
        tail = title.rsplit('|', 1)[-1] if '|' in title else ''
        if tail and re.search(r'verf[uü]gbar|Video|UT\b|H[oö]rfassung|Audiodeskription|\bmin\b|\d{1,2}\.\d{1,2}\.\d{2,4}', tail, re.I):
            title = title.rsplit('|', 1)[0].strip() or classicTitle
        title = re.sub(r'\s{2,}', ' ', title)

        season, episode = parseSxxExx(sxeHint)
        if not (season and episode):
            season, episode = parseSxxExx(title)
        if season and episode and not _hasSxE(title):
            tag = 'S%sE%s' % (_pad2(season), _pad2(episode))
            if tag:
                if ' - ' in title:
                    show, rest = title.split(' - ', 1)
                    title = '%s - %s - %s' % (show.strip(), tag, rest.strip())
                else:
                    title = '%s - %s' % (title, tag)
                return _appendLang(title, lang)

        d = str(date)[:10] if date and len(str(date)) >= 10 and str(date)[4] == '-' else ''
        y = str(year).strip() if year else (d[:4] if d else '')
        if isMovie and y and not _hasSxE(title):
            if ('(%s)' % y) not in title:
                title = '%s (%s)' % (title.rstrip(), y)
        elif d and not _hasSxE(title):
            if d not in title and d.replace('-', '.') not in title and d[:4] not in title.split('(')[-1]:
                title = '%s (%s)' % (title, d)
        return _appendLang(title, lang)
    except Exception:
        printExc()
    return classicTitle
