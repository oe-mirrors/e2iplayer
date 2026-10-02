# -*- coding: utf-8 -*-
# Shared helpers for the subtitle providers (subproviders/subprov_*.py): title / year matching,
# language names and codes, season / episode filters and release name ranking.
# Ported from the SubsSupport seekers (seekers/utilities.py). No Enigma2 imports, so the tests can load it.
import re
import unicodedata

# (language name, ISO 639-1, ISO 639-2/B) - the names the subtitle sites use
LANGUAGES = (
    ("Albanian", "sq", "alb"), ("Arabic", "ar", "ara"), ("Armenian", "hy", "arm"), ("Basque", "eu", "baq"),
    ("Bengali", "bn", "ben"), ("Bosnian", "bs", "bos"), ("Bulgarian", "bg", "bul"), ("Catalan", "ca", "cat"),
    ("Chinese", "zh", "chi"), ("Croatian", "hr", "hrv"), ("Czech", "cs", "cze"), ("Danish", "da", "dan"),
    ("Dutch", "nl", "dut"), ("English", "en", "eng"), ("Estonian", "et", "est"), ("Persian", "fa", "per"),
    ("Finnish", "fi", "fin"), ("French", "fr", "fre"), ("Galician", "gl", "glg"), ("Georgian", "ka", "geo"),
    ("German", "de", "ger"), ("Greek", "el", "ell"), ("Hebrew", "he", "heb"), ("Hindi", "hi", "hin"),
    ("Hungarian", "hu", "hun"), ("Icelandic", "is", "ice"), ("Indonesian", "id", "ind"), ("Italian", "it", "ita"),
    ("Japanese", "ja", "jpn"), ("Korean", "ko", "kor"), ("Kurdish", "ku", "kur"), ("Latvian", "lv", "lav"),
    ("Lithuanian", "lt", "lit"), ("Macedonian", "mk", "mac"), ("Malay", "ms", "may"), ("Norwegian", "no", "nor"),
    ("Polish", "pl", "pol"), ("Portuguese", "pt", "por"), ("Brazilian Portuguese", "pt-br", "pob"),
    ("Romanian", "ro", "rum"), ("Russian", "ru", "rus"), ("Serbian", "sr", "scc"), ("Sinhala", "si", "sin"),
    ("Slovak", "sk", "slo"), ("Slovenian", "sl", "slv"), ("Spanish", "es", "spa"), ("Swedish", "sv", "swe"),
    ("Tamil", "ta", "tam"), ("Thai", "th", "tha"), ("Turkish", "tr", "tur"), ("Ukrainian", "uk", "ukr"),
    ("Urdu", "ur", "urd"), ("Vietnamese", "vi", "vie"),
)

_NAME_TO_CODE = dict((re.sub(r'[^a-z0-9]+', ' ', n.lower()).strip(), c) for n, c, _b in LANGUAGES)
_CODE_TO_NAME = dict((c, n) for n, c, _b in LANGUAGES)
_ISO2_TO_CODE = dict((b, c) for _n, c, b in LANGUAGES)
_ISO2_TO_CODE.update({'deu': 'de', 'fra': 'fr', 'nld': 'nl', 'ces': 'cs', 'slk': 'sk', 'ron': 'ro', 'sqi': 'sq',
                      'hye': 'hy', 'eus': 'eu', 'zho': 'zh', 'fas': 'fa', 'kat': 'ka', 'isl': 'is', 'mkd': 'mk',
                      'msa': 'ms', 'srp': 'sr', 'gre': 'el', 'nob': 'no', 'nno': 'no', 'pob': 'pt-br'})

# site language names (normalized) that the table above does not know
LANG_ALIASES = {
    'farsi': 'fa', 'farsi persian': 'fa', 'brazilian': 'pt-br', 'portuguese brazil': 'pt-br',
    'portuguese brazilian': 'pt-br', 'brazillian portuguese': 'pt-br', 'portuguese br': 'pt-br', 'pb': 'pt-br',
    'pt br': 'pt-br', 'chinese bg code': 'zh', 'chinese simplified': 'zh', 'chinese traditional': 'zh',
    'big 5 code': 'zh', 'spanish spain': 'es', 'spanish latin america': 'es', 'espanol': 'es',
    'spanish latin american': 'es', 'ukranian': 'uk', 'serbian latin': 'sr', 'serbian cyrillic': 'sr',
    'bosnian latin': 'bs', 'norwegian bokmal': 'no', 'deutsch': 'de', 'francais': 'fr', 'english us': 'en',
    'english uk': 'en', 'srpski': 'sr', 'hrvatski': 'hr', 'slovenscina': 'sl', 'cestina': 'cs', 'slovencina': 'sk',
}

# Subscene-style season page names
SEASONS = ["Specials", "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth", "Ninth", "Tenth",
           "Eleventh", "Twelfth", "Thirteenth", "Fourteenth", "Fifteenth", "Sixteenth", "Seventeenth", "Eighteenth",
           "Nineteenth", "Twentieth", "Twenty-first", "Twenty-second", "Twenty-third", "Twenty-fourth", "Twenty-fifth"]

ROMAN = (('xx', 20), ('xix', 19), ('xviii', 18), ('xvii', 17), ('xvi', 16), ('xv', 15), ('xiv', 14), ('xiii', 13),
         ('xii', 12), ('xi', 11), ('x', 10), ('ix', 9), ('viii', 8), ('vii', 7), ('vi', 6), ('v', 5), ('iv', 4),
         ('iii', 3), ('ii', 2))
ROMAN_TO_INT = dict((r, str(n)) for r, n in ROMAN)
INT_TO_ROMAN = dict((str(n), r) for r, n in ROMAN)

# release name parts that say something about the source - the more a subtitle shares with the
# release the user plays, the better it fits (timing is the same for the same source)
_RELEASE_TAGS = ('bluray', 'bdrip', 'brrip', 'bdremux', 'remux', 'webrip', 'webdl', 'web', 'hdtv', 'dvdrip', 'dvd',
                 'hdrip', 'amzn', 'nf', 'dsnp', 'hmax', 'atvp', 'hulu', '2160p', '1080p', '720p', '480p', 'x264',
                 'x265', 'h264', 'h265', 'hevc', 'xvid', 'proper', 'repack', 'extended', 'unrated', 'directors',
                 'imax', 'hdr', 'dv')


def _u(text):
    # site values may be None, bytes, numbers or a list of release names
    if text is None:
        return u''
    if isinstance(text, bytes):
        return text.decode('utf-8', 'ignore')
    if isinstance(text, (list, tuple)):
        return u' '.join(_u(t) for t in text)
    if not isinstance(text, type(u'')):
        return u'%s' % text
    return text


def stripYear(title):
    """'The Matrix (1999)' -> 'The Matrix'"""
    return re.sub(r"\s*\(\d{4}\)$", "", _u(title)).strip()


def yearMatch(found, year):
    """True when a year is unknown or both differ by one at most (release years differ between countries)."""
    try:
        return abs(int(found) - int(year)) <= 1
    except (TypeError, ValueError):
        return True


def normalizeTitle(title):
    """'Fate of the Furious, The' -> 'the fate of the furious', 'Amélie' -> 'amelie'"""
    title = re.sub(r'^(.*), (the|a|an)$', r'\2 \1', _u(title).strip(), flags=re.I)
    title = unicodedata.normalize('NFKD', re.sub(r"['`’]", '', title.lower()).replace('&', ' and '))
    return ' '.join(re.findall(r'[^\W_]+', ''.join(c for c in title if not unicodedata.combining(c)), re.U))


def matchTitle(title, year, results):
    """Value of the (name, year, value) result that fits title and year best, or None.

    Exact titles win over the main title before a colon ('Dune: Part One') and whole-word partial
    matches, then the same year and the closest length. Results more than one year off are skipped
    (an exact title only when it is not the only one), partial matches need a year.
    """
    wanted = normalizeTitle(title)
    if not wanted:
        return None
    partial_re = re.compile(r'\b%s\b' % re.escape(wanted))
    ranked, exact = [], []
    for name, found_year, value in results:
        name = _u(name)
        found = normalizeTitle(name)
        if found == wanted:
            rank = 0
            exact.append(value)
        elif year and found_year and normalizeTitle(re.split(r':| - ', name)[0]) == wanted:
            rank = 1
        elif year and found_year and partial_re.search(found):
            rank = 2
        else:
            continue
        if yearMatch(found_year, year):
            same_year = not year or str(found_year) == str(year)
            ranked.append((rank, not same_year, abs(len(found) - len(wanted)), len(ranked), value))
    if ranked:
        return min(ranked)[-1]
    return exact[0] if len(exact) == 1 else None


def langCode(name):
    """Language name, ISO 639-1 or ISO 639-2 code (ours or a site's) -> ISO 639-1 code
    ('pt-br' for Brazilian Portuguese) or None."""
    name = _u(name).strip()
    if not name:
        return None
    low = name.lower()
    if low in _CODE_TO_NAME:
        return low
    if low in _ISO2_TO_CODE:
        return _ISO2_TO_CODE[low]
    norm = re.sub(r'[^a-z0-9]+', ' ', normalizeTitle(name)).strip()
    return LANG_ALIASES.get(norm) or _NAME_TO_CODE.get(norm) or _NAME_TO_CODE.get(norm.split(' ')[0])


def langName(code):
    """ISO 639-1 code -> English language name, the code itself when unknown."""
    return _CODE_TO_NAME.get(langCode(code) or code, code)


def langIso2(code):
    """ISO 639-1 code -> ISO 639-2/B ('de' -> 'ger'), '' when unknown."""
    code = langCode(code)
    for _n, c, b in LANGUAGES:
        if c == code:
            return b
    return ''


def parseTitle(text):
    """'Breaking Bad S02E05' -> ('Breaking Bad', None, 2, 5), 'Inception (2010)' / 'Inception 2010' ->
    ('Inception', '2010', None, None). Season / episode are ints, the year a string."""
    text = _u(text).strip()
    season = episode = None
    m = re.search(r'(?i)[\s._\-\[(]*(?<![a-z0-9])s(\d{1,2})\s*[\s._\-]?e(\d{1,3})\b', text) or re.search(r'(?i)[\s._\-\[(]+(\d{1,2})x(\d{1,3})\b', text)
    if m:
        season, episode = int(m.group(1)), int(m.group(2))
        text = text[:m.start()]
    year = None
    # 19xx / 2000-2039 only, so 'Blade Runner 2049' keeps its number
    m = re.search(r'[\s._\-\[(]+(19\d{2}|20[0-3]\d)[)\]]?\s*$', text) or re.search(r'[\s._\-\[(]+(19\d{2}|20[0-3]\d)[)\]]?[\s._\-]', text)
    if m and m.start() > 0:
        year = m.group(1)
        text = text[:m.start()]
    text = re.sub(r'[._]+', ' ', text).strip(' -([')
    return text, year, season, episode


def episodeFilters(season, episode):
    """Regexes for release names: (this episode, any episode, this season)."""
    season, episode = int(season), int(episode)
    ordinal = SEASONS[season] if season < len(SEASONS) else None
    this_episode = re.compile(r'(?:s0*%d[ ._-]*e0*%d|\b0*%dx0*%d)(?!\d)' % (season, episode, season, episode), re.I)
    any_episode = re.compile(r's\d+[ ._-]*e\d+|\b\d+x\d+\b|\be(?:p|pisode)?[ ._-]*\d+\b', re.I)
    this_season = r'(?<![a-z])s0*%d(?!\d)|season[ ._-]*0*%d(?!\d)' % (season, season)
    if ordinal:
        this_season += '|%s season' % ordinal
    return this_episode, any_episode, re.compile(this_season, re.I)


def episodeFits(name, season, episode):
    """True when a release name is this episode, or a season pack of this season without another episode in it.
    Without season / episode every name fits."""
    if not season or not episode:
        return True
    this_episode, any_episode, this_season = episodeFilters(season, episode)
    name = _u(name)
    if this_episode.search(name):
        return True
    return not any_episode.search(name) and bool(this_season.search(name))


def romanVariations(words):
    """Word list with Roman numerals as digits and vice versa (['rocky', 'ii'] -> ['rocky', '2']),
    the first word is kept ('V for Vendetta', '5 Card Stud') and 'I' is left alone."""
    variations = [words]
    for table in (ROMAN_TO_INT, INT_TO_ROMAN):
        variant = words[:1] + [table.get(w, w) for w in words[1:]]
        if variant not in variations:
            variations.append(variant)
    return variations


def downloadRating(downloads, per_point=50):
    """Rating 1-10 (as string) from a download count."""
    try:
        downloads = int(downloads or 0)
    except (TypeError, ValueError):
        downloads = 0
    return str(min(10, downloads // per_point + 1))


def _releaseTokens(name):
    return set(re.findall(r'[a-z0-9]+', normalizeTitle(name).replace('web dl', 'webdl')))


def releaseScore(release, wanted):
    """How well a subtitle's release name fits the release the user plays (file / stream name):
    shared source tags (bluray, web-dl, 1080p, ...) and the release group count. 0 when nothing is known."""
    release, wanted = _u(release), _u(wanted)
    if not release or not wanted:
        return 0
    a, b = _releaseTokens(release), _releaseTokens(wanted)
    score = 2 * len(a & b & set(_RELEASE_TAGS))
    group = re.search(r'-([a-z0-9]+)(?:\.[a-z0-9]{2,4})?$', wanted.strip(), re.I)
    if group and group.group(1).lower() in a:
        score += 5
    return score


def sortByRelease(items, wanted, key='title'):
    """Stable sort of provider list items (dicts) by releaseScore of item[key] against wanted, best first."""
    if not wanted:
        return items
    scored = [(-releaseScore(it.get(key, ''), wanted), idx, it) for idx, it in enumerate(items)]
    scored.sort(key=lambda x: (x[0], x[1]))
    return [it for _s, _i, it in scored]


def langSortKey(code, default=None):
    """sort key for language lists: the user's language, English, then by name"""
    code = langCode(code) or _u(code).lower()
    return (code != (langCode(default) or default), code != 'en', langName(code))


def sortByEpisode(items, season, episode, key='title'):
    """Stable sort: releases of this episode first, then season packs of this season, then the rest."""
    if not season or not episode:
        return items
    this_episode, any_episode, this_season = episodeFilters(season, episode)

    def rank(item):
        name = _u(item.get(key, ''))
        if this_episode.search(name):
            return 0
        return 1 if (not any_episode.search(name) and this_season.search(name)) else 2
    return sorted(items, key=rank)
