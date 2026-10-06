# -*- coding: utf-8 -*-
# hoststalker.py - Stalker / Ministra middleware portals (MAG set-top box API, portal URL + MAC address)
# Last Modified: 05.10.2026 - first version
#   - up to 3 portal slots (name / portal URL / MAC, the MAC as ConfigSecret); the portal field takes the address
#     the provider gives out (http://host:port/c/, .../stalker_portal/c/, portal.php or load.php links)
#   - the API end point is found by trying portal.php / server/load.php / stalker_portal/server/load.php with a
#     handshake; token + get_profile per portal, a new handshake when the token expired
#   - the box is a MAG250: its User-Agent, X-User-Agent, mac / stb_lang / timezone cookie, serial number and
#     device ids derived from the MAC; portals that bind the account to a real box get its serial number /
#     device ID / device ID 2 / signature from the optional fields of the portal slot
#   - more portals from e-portals.txt in the EStalker format (portal URL line, then its MACs): always from
#     <ConfigDir>/IPTVAccounts/e-portals.txt, from the EStalker plugin's file with the option; read only, listed
#     after the slots without a handshake each
#   - catch-up: "Catch-up" -> genres -> channels with tv_archive (get_all_channels) -> days -> programmes of
#     epg get_simple_data_table (mark_archive) -> tv_archive create_link "auto /media/<programme id>.mpg"
#   - account status (expiry, block message) per portal in the menu
#   - live channels per genre, movies and series per category, server pages joined to longer lists with
#     First / Jump / Next page; adult genres / categories / entries (the portal's censored flag, or "xxx", "adult",
#     "18+" ... in the name) only with the option "Show adult content" (default off)
#   - "Title (Year)" naming also drops short tags in front like "NF - ", "AMZ - ", "4K - "
#   - series: the "series" API (series -> seasons -> episodes) and the old VOD series (is_series, episode
#     numbers); play links come from create_link at play time (the portals hand out one-time play tokens)
#   - search per type (live in the full channel list, movies / series on the portal), search history
#   - INFO: now / next from get_short_epg for channels, the portal's movie data, libs/moviemeta as fallback
#   - watched flag for movies / episodes / seasons / series, favourites, sidecar and "Title (Year)" naming;
#     rows carry stalker://<portal id>/... and never the MAC (also not in a stored channel cmd)
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigSecret
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIconDir
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvtools import registerLogSecret
except ImportError:  # an older plugin without it: the host still runs
    def registerLogSecret(*values):
        pass
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
from Components.config import config, ConfigText, ConfigYesNo, getConfigListEntry
import hashlib
import os
import re
import time

###################################################
# config
###################################################
MAX_ACCOUNTS = 3

# optional box identity for portals bound to a real MAG (empty: derived from the MAC)
DEVICE_FIELDS = (('stalker_sn', _("serial number")), ('stalker_devid', _("device ID")), ('stalker_devid2', _("device ID 2")),
                 ('stalker_sig', _("signature")))

for _slot in range(1, MAX_ACCOUNTS + 1):
    setattr(config.plugins.iptvplayer, 'stalker_name%d' % _slot, ConfigText(default='', fixed_size=False))
    setattr(config.plugins.iptvplayer, 'stalker_portal%d' % _slot, ConfigText(default='', fixed_size=False))
    setattr(config.plugins.iptvplayer, 'stalker_mac%d' % _slot, ConfigSecret(default='', fixed_size=False))
    for _base, _label in DEVICE_FIELDS:
        setattr(config.plugins.iptvplayer, '%s%d' % (_base, _slot), ConfigText(default='', fixed_size=False))
config.plugins.iptvplayer.stalker_censored = ConfigYesNo(default=False)
config.plugins.iptvplayer.stalker_estalker = ConfigYesNo(default=True)
FILE_SLOT = 101  # portals from the e-portals.txt files


def _cfg(base, slot):
    return getattr(config.plugins.iptvplayer, '%s%d' % (base, slot))


def GetConfigList():
    optionList = []
    for slot in range(1, MAX_ACCOUNTS + 1):
        optionList.append(getConfigListEntry(_("Portal %d - name (optional):") % slot, _cfg('stalker_name', slot)))
        optionList.append(getConfigListEntry(_("Portal %d - portal URL (http://host:port/c/):") % slot, _cfg('stalker_portal', slot)))
        optionList.append(getConfigListEntry(_("Portal %d - MAC address (00:1A:79:...):") % slot, _cfg('stalker_mac', slot)))
        for base, label in DEVICE_FIELDS:
            optionList.append(getConfigListEntry(_("Portal %d - %s (optional, from the MAG box):") % (slot, label), _cfg(base, slot)))
    optionList.append(getConfigListEntry(_("Also use the portals of EStalker (%s)") % pluginFile(), config.plugins.iptvplayer.stalker_estalker))
    optionList.append(getConfigListEntry(_("Show adult content"), config.plugins.iptvplayer.stalker_censored))
    return optionList


def gettytul():
    return 'Stalker Portal (MAG)'


###################################################
# helpers without state
###################################################
MAG_UA = 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG250 stbapp ver: 2 rev: 250 Safari/533.3'
MAG_X_UA = 'Model: MAG250; Link: WiFi'
SERVER_PAGES = 3  # portal pages (mostly 14 rows) joined to one list page
LIST_TTL = 30 * 60
ACCOUNT_TTL = 5 * 60
EPG_TTL = 5 * 60
SESSION_TTL = 60 * 60  # a new handshake at the latest after an hour, earlier when the portal rejects the token

KIND_TYPES = {'live': 'itv', 'movie': 'vod', 'series': 'series'}
# rows with links / INFO -> what they are
ITEM_KINDS = {'st_live': 'live', 'st_movie': 'movie', 'st_series': 'series', 'st_vodseries': 'series', 'st_season': 'season',
              'st_episode': 'episode', 'st_timeshift': 'timeshift', 'st_archive_days': 'archive'}

MAC_RE = re.compile(r'^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$')
# "ffmpeg http://...", "ffrt http://localhost/ch/1_", "auto /media/12.mpg": the word in front of the address
CMD_PREFIX_RE = re.compile(r'^\s*[a-z0-9_]+\s+(?=\w+://|/)', re.I)

# -- name / value helpers: the same code in hostxtream.py and hoststalker.py - change both copies the same
#    way; each host runs on its own
# Arabic-Indic and Persian (extended) digits -> ASCII, for the local search
_DIGIT_MAP = dict([(0x0660 + _i, 0x30 + _i) for _i in range(10)] + [(0x06F0 + _i, 0x30 + _i) for _i in range(10)])
# country / language tags panels put in front of names: "|EN| ", "[DE] ", "|AR-HD| " always, bare "AR - " / "EN| " only
# for the usual language codes (a real title like "SAS: Red Notice" stays)
_PREFIX_TAG_RE = re.compile(r'^\s*[\|\[\(]\s*[A-Z0-9]{2,4}(?:[\s\-/+][A-Z0-9]{1,4})?\s*[\|\]\)]\s*[\-:]?\s*')
_PREFIX_LANG_RE = re.compile(r'^\s*(?:AR|EN|DE|FR|IT|ES|TR|NL|PL|PT|RU|UK|US|IN|PK|FA|IR|KU|AL|GR|RO|BG|HU|CZ|SE|NO|DK|FI|EX|MULTI|4K|VOD)\s*(?:\||\s-\s|-\s)\s*')
# any short provider / quality tag in capitals before " - ": "NF - ", "AMZ - ", "D+ - ", "4K - " (with the spaced hyphen
# only, so "Spider-Man" stays); at least one letter or "+", so "300 - Rise of an Empire" / "1917 - ..." stay
_PREFIX_SHORT_RE = re.compile(r'^\s*(?=[A-Z0-9+]*[A-Z+])[A-Z0-9+]{2,4}\s+-\s+(?=\S)')
# adult categories / entries by name, for panels without an adult flag: "xxx" / "XXX" only (the film "xXx" stays),
# "adult" only in category / genre names and not in "Young Adult" / "Adult Swim", "18+" not inside a number ("Movies 2018+")
_ADULT_XXX_RE = re.compile(r'(?:^|[^A-Za-z0-9])(?:xxx|XXX)(?:[^A-Za-z0-9]|$)')
_ADULT_NAME_RE = re.compile(r'(?:^|[^a-z0-9])(?:porno?|18\s*\+|\+\s*18)(?:[^a-z0-9]|$)', re.I)
_ADULT_CAT_RE = re.compile(r'(?:^|[^a-z0-9])(?<!young )adults?(?!\s*swim)(?:[^a-z0-9]|$)', re.I)
_TRAILING_YEAR_RE = re.compile(r'\s*(?:\(\s*((?:19|20)\d{2})\s*\)|\[\s*((?:19|20)\d{2})\s*\]|-\s*((?:19|20)\d{2}))\s*$')


def _str(value):
    # panel / portal values: str, int, None, sometimes [] or {} for "empty"
    if value is None or isinstance(value, (list, dict)):
        return ''
    try:
        # numbers as text, also py2 long (big ids / timestamps on 32 bit boxes)
        return ensure_str(value).strip() if isinstance(value, (bytes, type(u''))) else ('%s' % value)
    except Exception:
        return ''


def _int(value, default=0):
    try:
        return int(float(_str(value)))
    except Exception:
        return default


def _dict(value):
    return value if isinstance(value, dict) else {}


def _quote(value):
    return urllib_quote(ensure_str(value), safe='')


def _normSearchText(text):
    # unicode on py2 too: the digit map and lower() need it for Arabic / Cyrillic names
    text = _str(text)
    try:
        if isinstance(text, bytes):
            text = text.decode('utf-8', 'ignore')
        text = text.translate(_DIGIT_MAP)
    except Exception:
        pass
    return u' '.join(text.lower().split())


def _cleanName(name):
    # "|EN| Movie Name (2020)" -> ("Movie Name", "2020"): the list title with the naming normalisation, always
    # the title for libs/moviemeta and the show name of the episodes
    name = _str(name)
    for _i in range(2):
        newName = _PREFIX_SHORT_RE.sub('', _PREFIX_LANG_RE.sub('', _PREFIX_TAG_RE.sub('', name)))
        if newName == name or not newName.strip():
            break
        name = newName
    year = ''
    m = _TRAILING_YEAR_RE.search(name)
    if m and m.start() > 0:
        year = m.group(1) or m.group(2) or m.group(3)
        name = name[:m.start()]
    return re.sub(r'\s{2,}', ' ', name).strip(' -|'), year


def _isAdultName(name, category=False):
    name = _str(name)
    return bool(_ADULT_XXX_RE.search(name) or _ADULT_NAME_RE.search(name) or (category and _ADULT_CAT_RE.search(name)))


def _yearOf(*values):
    for value in values:
        m = re.search(r'\b((?:19|20)\d{2})\b', _str(value))
        if m:
            return m.group(1)
    return ''


def _list(value):
    return value if isinstance(value, list) else []


def _hash(func, text):
    return func(ensure_binary(text)).hexdigest().upper()


def normalizeMac(mac):
    # "00-1a-79-..", "001A79......" -> "00:1A:79:..:..:.."; '' when it is no MAC
    mac = re.sub(r'[^0-9A-Fa-f]', '', _str(mac)).upper()
    if len(mac) != 12:
        return ''
    mac = ':'.join(mac[i:i + 2] for i in range(0, 12, 2))
    return mac if MAC_RE.match(mac) else ''


def parsePortalInput(text):
    # portal field -> (base "scheme://host:port", [(API url, Referer), ...] in the order to try)
    text = _str(text)
    if text == '':
        return '', []
    if '://' not in text:
        text = 'http://' + text.lstrip('/')  # NOSONAR - Stalker portals mostly run on plain http
    try:
        parts = urlparse(text)
        scheme = (parts.scheme or 'http').lower()
        netloc = parts.netloc.rsplit('@', 1)[-1].strip().lower()
        if (scheme == 'http' and netloc.endswith(':80')) or (scheme == 'https' and netloc.endswith(':443')):
            netloc = netloc.rsplit(':', 1)[0]
        if not netloc:
            return '', []
        base = '%s://%s' % (scheme, netloc)
        path = parts.path or ''
        given = ''
        if path.endswith('.php'):
            given = base + path
            path = re.sub(r'/(?:server/)?[^/]*\.php$', '', path)
        path = re.sub(r'/(?:c|c_|client)/?(?:index\.html)?$', '', path.rstrip('/')).rstrip('/')
        if 'stalker_portal' in path:
            path = path[:path.index('stalker_portal') + len('stalker_portal')]
        candidates = [given] if given else []
        if path.endswith('stalker_portal'):
            candidates += [base + path + '/server/load.php', base + '/portal.php']
        else:
            candidates += [base + path + '/portal.php', base + path + '/server/load.php', base + '/stalker_portal/server/load.php', base + '/portal.php']
        endpoints = []
        for url in candidates:
            # the Referer is the portal's web client next to the API: <prefix>/c/
            apiPath = url[len(base):]
            prefix = apiPath.rsplit('/server/', 1)[0] if '/server/' in apiPath else apiPath.rsplit('/', 1)[0]
            entry = (url, base + prefix + '/c/')
            if entry not in endpoints:
                endpoints.append(entry)
        return base, endpoints
    except Exception:
        printExc()
    return '', []


def archiveDays(elm):
    # days of catch-up of a channel, 0 without archive; Ministra keeps tv_archive_duration in hours (168 = a week),
    # some panels send days (up to 31); 24 is taken as hours (one day), a 24 days archive is unusual
    if _int(elm.get('tv_archive')) != 1 and _int(elm.get('enable_tv_archive')) != 1:
        return 0
    value = _int(elm.get('tv_archive_duration'))
    if value <= 0:
        return 7
    return max(1, min((value + 23) // 24 if value > 31 or value == 24 else value, 31))


def _localTimezone():
    try:
        with open('/etc/timezone') as f:
            tz = f.read().strip()
        if '/' in tz:
            return tz
    except Exception:
        pass
    try:
        target = os.path.realpath('/etc/localtime')
        if '/zoneinfo/' in target:
            return target.split('/zoneinfo/', 1)[1]
    except Exception:
        pass
    return 'Europe/London'


# EStalker's e-portals.txt: a portal URL line (" #Name" optional), then its MACs, one per line
# (" #Alias" optional); "#" in front switches a line off, in front of the URL the whole portal
ACCOUNTS_PLUGIN = ('EStalker', '/etc/enigma2/estalker/', 'e-portals.txt')
# -- account files: the same code in hostxtream.py and hoststalker.py up to "-- end of the shared part"
#    (change both copies the same way); read only, never written back. Files: our own folder
#    <ConfigDir>/IPTVAccounts/ (the plugin's file can be copied there as it is, also without the plugin) and,
#    with the option, the plugin's own file: its playlist_file setting, else location + playlist_name, from the
#    running config when the plugin is loaded, else /etc/enigma2/settings, else its default.
E2_SETTINGS = '/etc/enigma2/settings'
ACCOUNTS_DIR = 'IPTVAccounts'
_ACCOUNT_LINES_CACHE = {}


def ownFile():
    # <ConfigDir>/IPTVAccounts/<the plugin's file name>; the folder is made so the user finds it
    try:
        configDir = config.plugins.iptvplayer.ConfigDir.value
        if not configDir or not isinstance(configDir, (str, type(u''))):
            return ''
        path = os.path.join(configDir, ACCOUNTS_DIR)
        if not os.path.isdir(path):
            os.makedirs(path)
        return os.path.join(path, ACCOUNTS_PLUGIN[2])
    except Exception:
        printExc()
    return ''


def _pluginSetting(name):
    # the plugin's value: running config first (current after changes in its setup), then the settings file
    try:
        section = getattr(config.plugins, ACCOUNTS_PLUGIN[0], None)
        value = getattr(getattr(section, name, None), 'value', None) if section is not None else None
        if value and isinstance(value, (str, type(u''))):
            return ensure_str(value)
    except Exception:
        pass  # plugin not loaded: older ConfigSubsection raise KeyError for an unknown name (every list)
    key = 'config.plugins.%s.%s=' % (ACCOUNTS_PLUGIN[0], name)
    for line in _accountLines(E2_SETTINGS):
        if line.startswith(key):
            return line[len(key):].strip()
    return ''


def pluginFile():
    path = _pluginSetting('playlist_file')
    if not path or not path.lower().endswith('.txt'):
        path = os.path.join(_pluginSetting('location') or ACCOUNTS_PLUGIN[1],
                            os.path.basename(_pluginSetting('playlist_name') or ACCOUNTS_PLUGIN[2]))
    return path


def _accountFiles(withPlugin):
    files = [path for path in (ownFile(),) if path]
    if withPlugin:
        path = pluginFile()
        if not files or os.path.normpath(path) != os.path.normpath(files[0]):
            files.append(path)
    return files


def _accountLines(path):
    # read again only when the file changed (the host asks for its accounts on every list); native str lines
    # (utf-8 bytes on py2, so they mix with the host's other strings)
    try:
        if path and os.path.isfile(path):
            st = os.stat(path)
            key = (st.st_mtime, st.st_size)
            entry = _ACCOUNT_LINES_CACHE.get(path)
            if entry and entry[0] == key:
                return entry[1]
            with open(path, 'rb') as f:
                # utf-8-sig: a file saved by Windows Notepad starts with a BOM, its first account was lost
                lines = [ensure_str(line).strip() for line in f.read().decode('utf-8-sig', 'ignore').splitlines()]
            _ACCOUNT_LINES_CACHE[path] = (key, lines)
            return lines
    except Exception:
        printExc()
    return []


def _splitMark(text, mark):
    return text.split(mark, 1) if mark in text else (text, '')
# -- end of the shared part


def readStalkerPortals(withPlugin=True):
    """[{'name', 'portal', 'mac', 'file'}] - one entry per active MAC of an active portal"""
    portals = []
    for path in _accountFiles(withPlugin):
        portal, portalName, active = None, '', False
        for line in _accountLines(path):
            if not line:
                continue
            bare = line.lstrip('#').strip()
            if bare.startswith(('http://', 'https://')):
                url, name = _splitMark(bare, ' #')
                portal, portalName = url.strip(), name.strip()
                active = not line.startswith('#')
                continue
            if portal is None or not active or line.startswith('#'):
                continue
            mac, alias = _splitMark(line, '#')
            # also "00-1A-79-..." or without separators (own files); EStalker itself needs the colons
            mac = re.sub(r'[^0-9A-Fa-f]', '', mac).upper()
            mac = ':'.join(mac[i:i + 2] for i in range(0, 12, 2)) if len(mac) == 12 else ''
            if MAC_RE.match(mac):
                portals.append({'name': alias.strip(), 'portal': portal, 'portalName': portalName, 'mac': mac, 'file': path})
    _namePortals(portals)
    return portals


def _namePortals(portals):
    # without an alias: the portal's name, numbered when the portal has several MACs (no part of the MAC in a
    # title - users post screenshots and logs)
    count = {}
    for entry in portals:
        count[(entry['file'], entry['portal'])] = count.get((entry['file'], entry['portal']), 0) + 1
    number = {}
    for entry in portals:
        key = (entry['file'], entry['portal'])
        number[key] = number.get(key, 0) + 1
        if not entry['name']:
            name = entry.pop('portalName') or urlparse(entry['portal']).hostname or entry['portal']
            entry['name'] = '%s (%d)' % (name, number[key]) if count[key] > 1 else name
        entry.pop('portalName', None)


class StalkerPortalHost(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # stable identity of a row; never the MAC - the portal is looked up by acc_id at play time
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 's_title', 'icon', 'desc', 'acc', 'acc_id', 'x_kind',
                  'item_id', 'cmd', 'series_id', 'season', 'season_id', 'ep_num', 'meta_type', 'meta_title', 'meta_year',
                  'cat_id', 'st_info', 'episodes', 'ep_cmd_own', 'archive_days', 'channel')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'stalker', 'cookie': 'stalker.cookie'})
        self.MAIN_URL = ''
        self.DEFAULT_ICON_URL = 'file://' + GetIconDir('PlayerSelector/stalker135.png')
        self.cache = {}
        self.sessions = {}
        self.timezone = _localTimezone()
        self.watchedHelper = IPTVWatchedHelper('stalker')
        self.wfInitFolderCache()

    ###################################################
    # accounts
    ###################################################
    def makeAccount(self, slot, name, portalText, mac, sn='', devId='', devId2='', signature=''):
        base, endpoints = parsePortalInput(portalText)
        mac = normalizeMac(mac)
        if not (base and endpoints and mac):
            return None
        # the box identity: the values of the real box when entered, otherwise derived from the MAC
        sn = _str(sn) or _hash(hashlib.md5, mac)[:13]
        devId = _str(devId) or _hash(hashlib.sha256, mac)
        devId2 = _str(devId2) or _hash(hashlib.sha256, sn)
        signature = _str(signature) or _hash(hashlib.sha256, sn + mac)
        return {'slot': slot, 'name': _str(name) or re.sub(r'^https?://', '', base), 'host': base, 'endpoints': endpoints, 'mac': mac,
                'sn': sn, 'device_id': devId, 'device_id2': devId2, 'signature': signature,
                # persistent (watched flag, favourites): portal + MAC hash, never the MAC itself
                'id': _hash(hashlib.md5, '%s|%s' % (base, mac))[:12].lower(),
                # memory cache / session: changes with the portal field (other end point) or the box identity
                'ck': _hash(hashlib.md5, '|'.join((_str(portalText), mac, sn, devId, devId2, signature)))}

    def getAccounts(self):
        accounts = []
        for slot in range(1, MAX_ACCOUNTS + 1):
            acc = self.makeAccount(slot, _cfg('stalker_name', slot).value, _cfg('stalker_portal', slot).value, _cfg('stalker_mac', slot).value,
                                   _cfg('stalker_sn', slot).value, _cfg('stalker_devid', slot).value, _cfg('stalker_devid2', slot).value,
                                   _cfg('stalker_sig', slot).value)
            if acc:
                accounts.append(acc)
        # e-portals.txt in our own folder and (option) the EStalker plugin's file, after the slots; slots from FILE_SLOT on
        known = set(acc['id'] for acc in accounts)
        for idx, entry in enumerate(readStalkerPortals(config.plugins.iptvplayer.stalker_estalker.value)):
            acc = self.makeAccount(FILE_SLOT + idx, entry['name'], entry['portal'], entry['mac'])
            if acc and acc['id'] not in known:
                known.add(acc['id'])
                acc['file'] = entry['file']
                accounts.append(acc)
        # the box identity also goes into the player / downloader log lines (stream urls, cookies)
        for acc in accounts:
            registerLogSecret(acc['mac'], acc['sn'], acc['device_id'], acc['device_id2'], acc['signature'])
        return accounts

    def getAccount(self, cItem):
        accounts = self.getAccounts()
        accId = cItem.get('acc_id', '')
        slot = _int(cItem.get('acc', 0))
        matches = [acc for acc in accounts if accId and acc['id'] == accId]
        for acc in matches:
            if acc['slot'] == slot:
                return acc
        if matches:
            return matches[0]
        # the portal address changed (new domain of the provider): the slot the item came from (own slots only,
        # the position of a file entry is no identity)
        for acc in accounts:
            if acc['slot'] == slot and slot <= MAX_ACCOUNTS:
                printDBG('Stalker: portal %s not found, using slot %d' % (accId, slot))
                return acc
        if not accId and accounts:
            return accounts[0]
        return None

    def accParams(self, acc, extra=None):
        params = {'acc': acc['slot'], 'acc_id': acc['id']}
        if extra:
            params.update(extra)
        return params

    def mask(self, acc, text):
        # MAC, box identity and token of the portal out of anything that goes into the debug log
        text = _str(text)
        for secret in (acc['mac'], _quote(acc['mac']), acc['mac'].lower(), _quote(acc['mac'].lower())):
            text = text.replace(secret, '**:**:**:**:**:**')
        for secret in (acc['sn'], acc['device_id'], acc['device_id2'], acc['signature']):
            if len(secret) > 4:  # a very short value entered by hand would mask half the line
                text = text.replace(secret, '***')
        token = _dict(self.sessions.get(acc['ck'])).get('token', '')
        if len(token) > 4:
            text = text.replace(token, '***')
        return text

    def hideMac(self, acc, cmd):
        # a channel cmd may carry the MAC (".../play/live.php?mac=00:1A:..&stream=1"): stored with a place holder
        cmd = _str(cmd)
        for secret in (acc['mac'], _quote(acc['mac']), acc['mac'].lower(), _quote(acc['mac'].lower())):
            cmd = cmd.replace(secret, '{MAC}')
        return cmd

    ###################################################
    # requests
    ###################################################
    def _httpParams(self, acc, referer, token=''):
        header = {'User-Agent': MAG_UA, 'X-User-Agent': MAG_X_UA, 'Referer': referer, 'Accept': '*/*',
                  'Cookie': 'mac=%s; stb_lang=en; timezone=%s' % (_quote(acc['mac']), _quote(self.timezone))}
        if token:
            header['Authorization'] = 'Bearer %s' % token
        return {'header': header, 'use_cookie': False}

    def _call(self, acc, api, referer, token, query):
        url = '%s?%s' % (api, '&'.join('%s=%s' % (key, _quote(value)) for key, value in list(query) + [('JsHttpRequest', '1-xml')]))
        printDBG('Stalker.call %s' % self.mask(acc, url))
        sts, data = self.cm.getPage(url, self._httpParams(acc, referer, token))
        if not sts or not data:
            return False, None
        try:
            data = json_loads(data)
            if isinstance(data, dict) and 'js' in data:
                return True, data['js']
        except Exception:
            pass
        printDBG('Stalker.call: no API answer [%s]' % self.mask(acc, _str(data)[:200]))
        return True, None

    def _handshake(self, acc, api, referer):
        js = self._call(acc, api, referer, '', [('type', 'stb'), ('action', 'handshake'), ('token', ''), ('prehash', '0')])[1]
        token = _str(_dict(js).get('token'))
        if not token:
            return None
        query = [('type', 'stb'), ('action', 'get_profile'), ('hd', '1'), ('ver', 'ImageDescription: 0.2.18-r23-250; ImageDate: Wed Aug 29 10:49:53 EEST 2018; PORTAL version: 5.6.2; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c'),
                 ('num_banks', '2'), ('sn', acc['sn']), ('stb_type', 'MAG250'), ('client_type', 'STB'), ('image_version', '218'),
                 ('video_out', 'hdmi'), ('device_id', acc['device_id']), ('device_id2', acc['device_id2']),
                 ('signature', acc['signature']), ('auth_second_step', '1'), ('hw_version', '1.7-BD-00'),
                 ('not_valid_token', '0'), ('metrics', json_dumps({'mac': acc['mac'], 'sn': acc['sn'], 'type': 'STB', 'model': 'MAG250', 'uid': '', 'random': ''})),
                 ('hw_version_2', _hash(hashlib.sha1, acc['mac']).lower()), ('timestamp', '%d' % int(time.time())),
                 ('api_signature', '262'), ('prehash', '')]
        profile = self._call(acc, api, referer, token, query)[1]
        registerLogSecret(token)
        return {'api': api, 'referer': referer, 'token': token, 'profile': _dict(profile), 'until': time.time() + SESSION_TTL}

    def session(self, acc, renew=False):
        sess = self.sessions.get(acc['ck'])
        if sess and not renew and sess['until'] > time.time():
            return sess
        endpoints = list(acc['endpoints'])
        if sess:
            # the end point that worked first, a new token only
            known = (sess['api'], sess['referer'])
            endpoints = [known] + [x for x in endpoints if x != known]
        self.sessions.pop(acc['ck'], None)
        for api, referer in endpoints:
            sess = self._handshake(acc, api, referer)
            if sess:
                printDBG('Stalker: portal API %s' % api)
                self.sessions[acc['ck']] = sess
                return sess
        SetIPTVPlayerLastHostError(_("Failed to connect to server \"%s\".") % acc['host'])
        return None

    def api(self, acc, query):
        # the "js" part of the answer, or None; a rejected token gets one new handshake
        for attempt in (0, 1):
            sess = self.session(acc, renew=(attempt == 1))
            if not sess:
                return None
            sts, js = self._call(acc, sess['api'], sess['referer'], sess['token'], query)
            if not sts:
                return None
            if js is not None:
                return js
        return None

    def cached(self, key, ttl, func):
        now = time.time()
        entry = self.cache.get(key)
        if entry and entry[0] > now:
            return entry[1]
        value = func()
        if value is not None:
            self.cache[key] = (now + ttl, value)
        return value

    def apiCached(self, acc, query, ttl=LIST_TTL):
        return self.cached((acc['ck'],) + tuple(query), ttl, lambda: self.api(acc, query))

    def accountStatus(self, acc):
        # (ok, text for the menu)
        def fetch():
            sess = self.session(acc)
            if not sess:
                return None
            info = _dict(self.api(acc, [('type', 'account_info'), ('action', 'get_main_info')]))
            return {'profile': sess.get('profile', {}), 'info': info}
        data = self.cached((acc['ck'], 'status'), ACCOUNT_TTL, fetch)
        if not data:
            return False, _("Failed to connect to host.")
        profile, info = data['profile'], data['info']
        blockMsg = _str(profile.get('block_msg'))
        if blockMsg:
            return False, blockMsg
        parts = []
        # the expiry date: end_date, or the "phone" field many panels use for it
        expiry = _str(info.get('end_date')) or _str(info.get('phone')) or _str(profile.get('expire_billing_date'))
        if expiry and expiry not in ('0000-00-00 00:00:00', '0'):
            parts.append(_("Expiry: %s") % expiry)
        tariff = _str(profile.get('tariff_plan_name')) or _str(info.get('tariff_plan'))
        if tariff:
            parts.append(tariff)
        return True, ' | '.join(parts)

    ###################################################
    # lists from the portal, joined from several server pages
    ###################################################
    def pagedList(self, acc, query, page):
        # (rows, last list page) or (None, 0)
        rows = []
        serverPages = 0
        first = (page - 1) * SERVER_PAGES + 1
        for p in range(first, first + SERVER_PAGES):
            js = self.apiCached(acc, list(query) + [('p', '%d' % p)])
            if js is None and p == first:
                return None, 0
            # an empty answer ([] / {}) is an empty list, not an error
            js = _dict(js)
            data = _list(js.get('data'))
            total = _int(js.get('total_items'))
            perPage = _int(js.get('max_page_items')) or len(data) or 1
            if total:
                serverPages = (total + perPage - 1) // perPage
            else:
                # no total_items: one more server page as long as this one was full
                serverPages = p + 1 if len(data) >= perPage else p
            rows.extend(_dict(x) for x in data)
            if not data or p >= serverPages:
                break
        return rows, (serverPages + SERVER_PAGES - 1) // SERVER_PAGES

    def showCensored(self):
        return config.plugins.iptvplayer.stalker_censored.value

    def hidden(self, elm, nameKey='name'):
        # adult entries without "Show adult content": the portal's censored flag or the name; nameKey 'title' =
        # a genre / category (there also "adult")
        return not self.showCensored() and (_int(elm.get('censored')) == 1 or _isAdultName(elm.get(nameKey), nameKey == 'title'))

    ###################################################
    # watched flag
    ###################################################
    def _getWatchedKeyForItem(self, cItem):
        try:
            if not isinstance(cItem, dict):
                return ''
            accId = cItem.get('acc_id', '')
            category = cItem.get('category', '')
            if not accId:
                return ''
            if category == 'st_movie' and cItem.get('item_id'):
                return 'movie:%s|%s' % (accId, cItem['item_id'])
            if category == 'st_episode' and cItem.get('series_id'):
                return 'episode:%s|%s|%s|%s' % (accId, cItem['series_id'], cItem.get('season_id', ''), cItem.get('ep_num', ''))
            if category == 'st_season' and cItem.get('series_id'):
                return 'season:%s|%s|%s' % (accId, cItem['series_id'], cItem.get('season_id', ''))
            if category in ('st_series', 'st_vodseries') and cItem.get('series_id'):
                return 'series:%s|%s' % (accId, cItem['series_id'])
        except Exception:
            printExc()
        return ''

    ###################################################
    # menus
    ###################################################
    def listMain(self, cItem):
        accounts = self.getAccounts()
        if not accounts:
            self.addMarker({'title': _("Please configure the Stalker portal (blue button)"),
                            'desc': _("Portal URL and MAC address in the host configuration, as the provider gives them out. More portals: %s in the EStalker format (portal URL, then its MAC addresses, one per line).") % ownFile()})
            return
        if len(accounts) == 1:
            self.listAccount(self.accParams(accounts[0], {'name': 'category'}))
            return
        for acc in accounts:
            # the status needs a handshake per portal: only for the own slots, a long EStalker list opens at once
            status = acc['file'] if acc.get('file') else self.accountStatus(acc)[1]
            self.addDir(self.accParams(acc, {'name': 'category', 'category': 'st_account', 'title': acc['name'], 'desc': '%s[/br]%s' % (acc['host'], status)}))

    def listAccount(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        ok, status = self.accountStatus(acc)
        if not ok:
            SetIPTVPlayerLastHostError('%s: %s' % (acc['name'], status))
            self.addMarker({'title': '%s: %s' % (acc['name'], status), 'desc': acc['host']})
            return
        base = self.accParams(acc, {'name': 'category'})
        for kind, title in (('live', _("Live channels")), ('movie', _("Movies")), ('series', _("Series"))):
            params = dict(base)
            params.update({'category': 'st_cats', 'x_kind': kind, 'title': title, 'desc': status})
            self.addDir(params)
        params = dict(base)
        params.update({'category': 'st_archive_genres', 'title': _("Catch-up"), 'desc': _("Programmes of the last days of the channels with an archive")})
        self.addDir(params)
        for item in self.searchItems():
            params = dict(base)
            params.update(item)
            self.addDir(params)

    def listCategories(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        kind = cItem.get('x_kind', 'live')
        action = 'get_genres' if kind == 'live' else 'get_categories'
        data = self.apiCached(acc, [('type', KIND_TYPES[kind]), ('action', action)])
        if data is None:
            return
        base = self.accParams(acc, {'name': 'category', 'category': 'st_list', 'x_kind': kind, 'page': 1, 'good_for_fav': True})
        for cat in _list(data):
            cat = _dict(cat)
            title = _str(cat.get('title'))
            catId = _str(cat.get('id'))
            if not title or not catId:
                continue
            if self.hidden(cat, 'title'):
                continue
            params = dict(base)
            params.update({'title': title, 'cat_id': catId, 'url': 'stalker://%s/%s/cat/%s' % (acc['id'], kind, _quote(catId))})
            self.addDir(params)
        if not self.currList:
            self.addMarker({'title': _("No items found")})

    def listQuery(self, kind, catId):
        if kind == 'live':
            return [('type', 'itv'), ('action', 'get_ordered_list'), ('genre', catId or '*'), ('force_ch_link_check', ''), ('fav', '0'), ('sortby', 'number')]
        query = [('type', KIND_TYPES[kind]), ('action', 'get_ordered_list'), ('category', catId or '*'), ('genre', '*'), ('sortby', 'added')]
        if kind == 'series':
            query += [('movie_id', '0'), ('season_id', '0'), ('episode_id', '0')]
        return query

    def listStreams(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        kind = cItem.get('x_kind', 'live')
        page = max(1, _int(cItem.get('page', 1), 1))
        rows, lastPage = self.pagedList(acc, self.listQuery(kind, cItem.get('cat_id', '')), page)
        if rows is None:
            return
        hiddenGenres = self.hiddenGenres(acc) if kind == 'live' else set()
        for elm in rows:
            self.addStreamItem(acc, kind, elm, hiddenGenres)
        if page == 1 and not rows:
            self.addMarker({'title': _("No items found")})
        addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, cItem.get('url', '').replace('{', '%7B').replace('}', '%7D'))

    def addStreamItem(self, acc, kind, elm, hiddenGenres):
        # hiddenGenres: self.hiddenGenres(acc) for live, once per list
        if self.hidden(elm) or (kind == 'live' and _str(elm.get('tv_genre_id')) in hiddenGenres):
            return
        if kind == 'live':
            self.addLive(acc, elm)
        elif kind == 'movie':
            self.addMovie(acc, elm)
        else:
            self.addSeries(acc, elm, 'st_series')

    def addLive(self, acc, elm):
        cid = _str(elm.get('id'))
        title = _str(elm.get('name'))
        cmd = _str(elm.get('cmd'))
        if not cmd:
            cmds = _list(elm.get('cmds'))
            cmd = _str(_dict(cmds[0]).get('url')) if cmds else ''
        if not cid or not title or not cmd:
            return
        number = _str(elm.get('number'))
        days = archiveDays(elm)
        desc = ' | '.join([x for x in ((_("Channel: %s") % number) if number else '', (_("Catch-up: %d days") % days) if days else '') if x])
        self.addVideo(self.accParams(acc, {'name': 'category', 'category': 'st_live', 'x_kind': 'live', 'title': title,
                                           'url': 'stalker://%s/live/%s' % (acc['id'], cid), 'item_id': cid,
                                           'cmd': self.hideMac(acc, cmd), 'icon': _str(elm.get('logo')),
                                           'desc': desc, 'archive_days': days, 'good_for_fav': True}))

    def movieInfo(self, elm):
        # the portal's movie data, kept in the row for INFO (no extra request)
        duration = _int(elm.get('time'))
        rating = _str(elm.get('rating_imdb')) or _str(elm.get('rating_kinopoisk'))
        return {'year': _yearOf(elm.get('year')), 'genres': _str(elm.get('genres_str')), 'director': _str(elm.get('director')),
                'cast': _str(elm.get('actors')), 'country': _str(elm.get('country')), 'age_limit': _str(elm.get('age')),
                'duration': ('%d min' % duration) if duration > 0 else '', 'rating': rating if rating not in ('0', 'N/A') else '',
                'original_title': _str(elm.get('o_name')) if _str(elm.get('o_name')) != _str(elm.get('name')) else ''}

    def describe(self, info, plot):
        parts = [x for x in (info.get('year', ''), info.get('genres', ''), (_("Rating: %s") % info['rating']) if info.get('rating') else '') if x]
        desc = ' | '.join(parts)
        if plot:
            desc = '%s[/br]%s' % (desc, plot) if desc else plot
        return desc

    def titles(self, elm, info):
        # (title in the list, clean title, year)
        rawTitle = _str(elm.get('name')) or _str(elm.get('o_name'))
        cleanTitle, nameYear = _cleanName(rawTitle)
        cleanTitle = cleanTitle or rawTitle
        year = info.get('year', '') or nameYear
        title = rawTitle
        if IsMediaNamingNormalized():
            title = '%s (%s)' % (cleanTitle, year) if year else cleanTitle
        return title, cleanTitle, year

    def addMovie(self, acc, elm):
        mid = _str(elm.get('id'))
        if not mid or not _str(elm.get('name')):
            return
        info = self.movieInfo(elm)
        title, cleanTitle, year = self.titles(elm, info)
        params = self.accParams(acc, {'name': 'category', 'x_kind': 'movie', 'title': title, 's_title': cleanTitle,
                                      'icon': _str(elm.get('screenshot_uri')), 'desc': self.describe(info, _str(elm.get('description'))),
                                      'st_info': info, 'meta_title': cleanTitle, 'meta_year': year, 'good_for_fav': True})
        if _int(elm.get('is_series')) == 1:
            # old VOD series: one item, the episodes are numbers for create_link
            params.update({'category': 'st_vodseries', 'meta_type': 'tv', 'series_id': mid, 'cmd': self.hideMac(acc, elm.get('cmd')),
                           'episodes': [_str(x) for x in _list(elm.get('series')) if _str(x)],
                           'url': 'stalker://%s/vodseries/%s' % (acc['id'], mid)})
            self.addDir(params)
            return
        if not _str(elm.get('cmd')):
            return
        params.update({'category': 'st_movie', 'meta_type': 'movie', 'item_id': mid, 'cmd': self.hideMac(acc, elm.get('cmd')),
                       'url': 'stalker://%s/movie/%s' % (acc['id'], mid)})
        self.addVideo(params)

    def addSeries(self, acc, elm, category):
        sid = _str(elm.get('id'))
        if not sid or not _str(elm.get('name')):
            return
        info = self.movieInfo(elm)
        title, cleanTitle, year = self.titles(elm, info)
        if IsMediaNamingNormalized():
            title = cleanTitle
        self.addDir(self.accParams(acc, {'name': 'category', 'category': category, 'x_kind': 'series', 'title': title, 's_title': cleanTitle,
                                         'url': 'stalker://%s/series/%s' % (acc['id'], _quote(sid)), 'series_id': sid,
                                         'icon': _str(elm.get('screenshot_uri')), 'desc': self.describe(info, _str(elm.get('description'))),
                                         'st_info': info, 'meta_type': 'tv', 'meta_title': cleanTitle, 'meta_year': year, 'good_for_fav': True}))

    ###################################################
    # series
    ###################################################
    def allPages(self, acc, query, maxPages=20, ttl=LIST_TTL):
        rows = []
        for p in range(1, maxPages + 1):
            js = _dict(self.apiCached(acc, list(query) + [('p', '%d' % p)], ttl))
            data = _list(js.get('data'))
            if not data:
                break
            rows.extend(_dict(x) for x in data)
            total = _int(js.get('total_items'))
            if total:
                if len(rows) >= total:
                    break
            elif len(data) < (_int(js.get('max_page_items')) or len(data) + 1):
                # no total_items: the next page only after a full one
                break
        return rows

    def listSeasons(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        seriesId = cItem.get('series_id', '')
        seasons = self.allPages(acc, [('type', 'series'), ('action', 'get_ordered_list'), ('movie_id', seriesId), ('season_id', '0'), ('episode_id', '0')])
        show = cItem.get('s_title', '') or cItem.get('title', '')
        for season in seasons:
            seasonId = _str(season.get('id'))
            if not seasonId:
                continue
            name = _str(season.get('name')) or seasonId
            m = re.search(r'(\d+)\s*$', name)
            num = _str(season.get('season_number')) or (m.group(1) if m else '')
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'st_season', 'x_kind': 'season', 'season_id': seasonId, 'season': num,
                           'title': '%s - %s' % (show, (_("Season %s") % num) if num else name), 's_title': show,
                           'url': 'stalker://%s/series/%s/%s' % (acc['id'], _quote(seriesId), _quote(seasonId)),
                           'cmd': self.hideMac(acc, season.get('cmd')), 'episodes': [_str(x) for x in _list(season.get('series')) if _str(x)],
                           'icon': _str(season.get('screenshot_uri')) or cItem.get('icon', ''),
                           'desc': _str(season.get('description')) or cItem.get('desc', '')})
            self.addDir(params)
        if not self.currList:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))

    def episodeTitle(self, show, season, epNum, name):
        if not IsMediaNamingNormalized():
            return name or '%s %s' % (_("Episode"), epNum)
        return '%s - %s' % (show, formatSxxExx(season or '1', epNum or '0'))

    def listEpisodes(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        show = cItem.get('s_title', '') or cItem.get('title', '')
        season = cItem.get('season', '') or '1'
        base = dict(cItem)
        base.update({'good_for_fav': True, 'category': 'st_episode', 'x_kind': 'episode', 's_title': show})
        base.pop('episodes', None)
        episodes = cItem.get('episodes') or []
        if episodes:
            # season / old VOD series with episode numbers: create_link with the season cmd + series=<number>;
            # seasons without a cmd are /media/<season id>.mpg on these portals
            cmd = cItem.get('cmd') or '/media/%s.mpg' % (cItem.get('season_id') or cItem.get('series_id', ''))
            for epNum in episodes:
                params = dict(base)
                params.update({'title': self.episodeTitle(show, season, epNum, '%s %s' % (_("Episode"), epNum)), 'ep_num': epNum,
                               'cmd': cmd, 'url': '%s/%s' % (cItem.get('url', ''), _quote(epNum))})
                self.addVideo(params)
            return
        if cItem.get('category') != 'st_season':
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        # newer portals: the episodes of a season are their own list with a cmd each
        rows = self.allPages(acc, [('type', 'series'), ('action', 'get_ordered_list'), ('movie_id', cItem.get('series_id', '')),
                                   ('season_id', cItem.get('season_id', '')), ('episode_id', '0')])
        for ep in rows:
            cmd = _str(ep.get('cmd'))
            if not cmd:
                continue
            epNum = _str(ep.get('series_number')) or _str(ep.get('episode_number')) or _str(ep.get('id'))
            params = dict(base)
            params.update({'title': self.episodeTitle(show, season, epNum, _str(ep.get('name'))), 'ep_num': epNum,
                           'cmd': self.hideMac(acc, cmd), 'ep_cmd_own': 1,
                           'url': '%s/%s' % (cItem.get('url', ''), _quote(_str(ep.get('id')) or epNum)),
                           'icon': _str(ep.get('screenshot_uri')) or cItem.get('icon', ''),
                           'desc': _str(ep.get('description')) or cItem.get('desc', '')})
            self.addVideo(params)
        if not rows:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))

    ###################################################
    # catch-up
    ###################################################
    def allChannels(self, acc):
        # the full channel list (one request, cached): search and catch-up
        data = _dict(self.apiCached(acc, [('type', 'itv'), ('action', 'get_all_channels'), ('force_ch_link_check', '')]))
        return [_dict(x) for x in _list(data.get('data'))]

    def archiveChannels(self, acc, genreId=''):
        hiddenGenres = self.hiddenGenres(acc)
        return [elm for elm in self.allChannels(acc) if archiveDays(elm) and _str(elm.get('id')) and
                (not genreId or _str(elm.get('tv_genre_id')) == genreId) and not self.hidden(elm) and
                _str(elm.get('tv_genre_id')) not in hiddenGenres]

    def hiddenGenres(self, acc):
        # live genres hidden without "Show adult content" (their channels then also leave catch-up / "All")
        if self.showCensored():
            return set()
        return set(_str(_dict(g).get('id')) for g in _list(self.apiCached(acc, [('type', 'itv'), ('action', 'get_genres')]))
                   if self.hidden(_dict(g), 'title'))

    def listArchiveGenres(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        channels = self.archiveChannels(acc)
        if not channels:
            self.addMarker({'title': _("No channels with an archive on this portal.")})
            return
        counts = {}
        for elm in channels:
            genreId = _str(elm.get('tv_genre_id'))
            counts[genreId] = counts.get(genreId, 0) + 1
        base = self.accParams(acc, {'name': 'category', 'category': 'st_archive_channels', 'x_kind': 'live', 'page': 1})
        params = dict(base)
        params.update({'title': '%s (%d)' % (_("All"), len(channels)), 'cat_id': ''})
        self.addDir(params)
        for genre in _list(self.apiCached(acc, [('type', 'itv'), ('action', 'get_genres')])):
            genre = _dict(genre)
            genreId = _str(genre.get('id'))
            if not counts.get(genreId) or self.hidden(genre, 'title'):
                continue
            params = dict(base)
            params.update({'title': '%s (%d)' % (_str(genre.get('title')), counts[genreId]), 'cat_id': genreId})
            self.addDir(params)

    def listArchiveChannels(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        channels = self.archiveChannels(acc, cItem.get('cat_id', ''))
        page = max(1, _int(cItem.get('page', 1), 1))
        pageSize = 100
        for elm in channels[(page - 1) * pageSize:page * pageSize]:
            days = archiveDays(elm)
            title = _str(elm.get('name'))
            self.addDir(self.accParams(acc, {'name': 'category', 'category': 'st_archive_days', 'x_kind': 'archive', 'item_id': _str(elm.get('id')),
                                             'title': title, 'channel': title, 'archive_days': days, 'icon': _str(elm.get('logo')),
                                             'desc': _("Catch-up: %d days") % days}))
        lastPage = (len(channels) + pageSize - 1) // pageSize
        addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, 'stalker://%s/live/archive/%s' % (acc['id'], _quote(cItem.get('cat_id', ''))))

    def listArchiveDays(self, cItem):
        days = max(1, min(_int(cItem.get('archive_days'), 0) or 7, 31))
        now = time.localtime()
        for idx in range(days + 1):
            # mktime with the day shifted: correct also over a daylight saving change
            dayStart = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday - idx, 0, 0, 0, 0, 0, -1)))
            label = time.strftime('%a %d.%m.%Y', time.localtime(dayStart))
            if idx == 0:
                label = '%s (%s)' % (_("Today"), label)
            elif idx == 1:
                label = '%s (%s)' % (_("Yesterday"), label)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'st_archive_day', 'title': label, 'day_start': dayStart})
            self.addDir(params)

    def listArchiveProgrammes(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        dayStart = _int(cItem.get('day_start'), 0)
        now = int(time.time())
        # the portal's day table, all its pages (mostly 10 rows each); today's only for a few minutes (its
        # mark_archive flags change as the programmes end)
        rows = self.allPages(acc, [('type', 'epg'), ('action', 'get_simple_data_table'), ('ch_id', cItem.get('item_id', '')),
                                   ('date', time.strftime('%Y-%m-%d', time.localtime(dayStart)))], maxPages=30,
                             ttl=EPG_TTL if now - dayStart < 86400 else LIST_TTL)
        channel = cItem.get('channel', '')
        normalize = IsMediaNamingNormalized()
        progs = []
        for prog in rows:
            start = _int(prog.get('start_timestamp'), 0)
            stop = _int(prog.get('stop_timestamp'), 0)
            progId = _str(prog.get('id')) or _str(prog.get('real_id'))
            if not progId or not start or stop <= start or start >= now:
                continue
            # the archive holds what has finished; mark_archive=1 marks it on portals that send the flag
            if ('mark_archive' in prog and _int(prog.get('mark_archive')) != 1) or ('mark_archive' not in prog and stop > now):
                continue
            progs.append((start, stop, progId, prog))
        progs.sort(key=lambda x: x[0])
        for start, stop, progId, prog in progs:
            name = _str(prog.get('name')) or _("Program")
            span = '%s - %s' % (time.strftime('%H:%M', time.localtime(start)), time.strftime('%H:%M', time.localtime(stop)))
            if normalize:
                title = '%s - %s (%s)' % (channel, name, time.strftime('%Y-%m-%d %H.%M', time.localtime(start)))
            else:
                title = '%s  %s' % (span, name)
            desc = '%s %s[/br]%s' % (time.strftime('%d.%m.%Y', time.localtime(start)), span, _str(prog.get('descr')))
            self.addVideo(self.accParams(acc, {'name': 'category', 'category': 'st_timeshift', 'x_kind': 'timeshift', 'title': title,
                                               'url': 'stalker://%s/timeshift/%s/%s' % (acc['id'], cItem.get('item_id', ''), _quote(progId)),
                                               'item_id': cItem.get('item_id', ''), 'prog_id': progId, 'channel': channel,
                                               'icon': cItem.get('icon', ''), 'desc': desc, 'good_for_fav': False}))
        if not progs:
            self.addMarker({'title': _("No recorded programmes on this day.")})

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        kind = searchType if searchType in KIND_TYPES else 'live'
        words = _normSearchText(searchPattern).split()
        if not words:
            return
        acc = self.getAccount(cItem)
        if acc is None:
            return
        page = max(1, _int(cItem.get('page', 1), 1))
        if kind == 'live':
            # the full channel list once, filtered here
            hiddenGenres = self.hiddenGenres(acc)
            # adult channels out before the paging, so the page count matches what is shown
            found = [x for x in self.allChannels(acc) if all(w in _normSearchText(x.get('name')) for w in words) and
                     not self.hidden(x) and _str(x.get('tv_genre_id')) not in hiddenGenres]
            pageSize = 100
            for elm in found[(page - 1) * pageSize:page * pageSize]:
                self.addStreamItem(acc, kind, elm, hiddenGenres)
            lastPage = (len(found) + pageSize - 1) // pageSize
        else:
            query = [('type', KIND_TYPES[kind]), ('action', 'get_ordered_list'), ('search', ' '.join(words)), ('genre', '*'), ('sortby', 'added')]
            rows, lastPage = self.pagedList(acc, query, page)
            for elm in (rows or []):
                self.addStreamItem(acc, kind, elm, ())
        # constant pseudo url: only lets "Jump" through, the hits are cut by cItem['page']
        addPagingItems(self, dict(cItem, category='search_next_page', desc=''), page, page < lastPage, lastPage, 'stalker://search/')

    ###################################################
    # links
    ###################################################
    def createLink(self, acc, linkType, cmd, series=''):
        js = self.api(acc, [('type', linkType), ('action', 'create_link'), ('cmd', cmd), ('series', series), ('forced_storage', '0'),
                            ('disable_ad', '0'), ('download', '0'), ('force_ch_link_check', '0')])
        url = CMD_PREFIX_RE.sub('', _str(_dict(js).get('cmd')))
        return url if url.startswith(('http://', 'https://', 'rtmp://', 'rtsp://', 'udp://')) else ''

    def getLinksForVideo(self, cItem):
        printDBG('Stalker.getLinksForVideo [%s]' % cItem.get('url', ''))
        acc = self.getAccount(cItem)
        if acc is None:
            SetIPTVPlayerLastHostError(_("The Stalker portal of this entry is not configured (any more)."))
            return []
        kind = ITEM_KINDS.get(cItem.get('category', ''), '')
        cmd = _str(cItem.get('cmd')).replace('{MAC}', acc['mac'])
        url = ''
        if kind == 'live':
            url = self.createLink(acc, 'itv', cmd)
            if url and cItem.get('item_id'):
                # some portals leave the stream id out of the link
                url = re.sub(r'([?&]stream=)(?=&|$)', lambda m: m.group(1) + _quote(cItem['item_id']), url)
            direct = CMD_PREFIX_RE.sub('', cmd)
            if not url and direct.startswith(('http://', 'https://')) and '//localhost' not in direct:
                url = direct
        elif kind == 'timeshift':
            url = self.createLink(acc, 'tv_archive', 'auto /media/%s.mpg' % cItem.get('prog_id', ''))
        elif kind == 'movie':
            url = self.createLink(acc, 'vod', cmd)
        elif kind == 'episode':
            url = self.createLink(acc, 'vod', cmd, '' if cItem.get('ep_cmd_own') else cItem.get('ep_num', ''))
        if not url:
            SetIPTVPlayerLastHostError(_("The portal did not hand out a link for this entry."))
            return []
        printDBG('Stalker stream %s' % self.mask(acc, url))
        urltab = [{'name': 'MAG', 'url': strwithmeta(url, {'User-Agent': MAG_UA}), 'need_resolve': 0}]
        if kind in ('live', 'timeshift'):
            return urltab
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), ''))

    def getVideoLinks(self, videoUrl):
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems([{'name': 'direct', 'url': videoUrl, 'need_resolve': 0}], sidecar)

    ###################################################
    # INFO
    ###################################################
    def getShortEpg(self, acc, channelId):
        return _list(self.cached((acc['ck'], 'short_epg', channelId), EPG_TTL,
                                 lambda: self.api(acc, [('type', 'itv'), ('action', 'get_short_epg'), ('ch_id', channelId), ('size', '2')])))

    def _moviemeta(self, mediaType, title, year):
        try:
            from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
            # Arabic-only titles: only to the providers that know them (TMDb / TVmaze)
            return getMeta(mediaType, title, year, skip=() if isLatinTitle(title) else LATIN_ONLY) or {}
        except Exception:
            printExc()
        return {}

    def _article(self, cItem, text, icon, otherInfo):
        otherInfo = dict((k, _str(v)) for k, v in otherInfo.items() if _str(v))
        return [{'title': cItem.get('title', ''), 'text': text or cItem.get('desc', '').replace('[/br]', '\n'),
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def getArticleContent(self, cItem):
        printDBG('Stalker.getArticleContent [%s]' % cItem.get('url', ''))
        acc = self.getAccount(cItem)
        kind = ITEM_KINDS.get(cItem.get('category', ''), '')
        icon = cItem.get('icon', '')
        if acc is None or kind in ('timeshift', 'archive'):
            return self._article(cItem, '', icon, {'station': cItem.get('channel', '')})
        if kind == 'live':
            lines = []
            for idx, prog in enumerate(self.getShortEpg(acc, cItem.get('item_id', ''))[:2]):
                prog = _dict(prog)
                span = '%s - %s' % (_str(prog.get('t_time')), _str(prog.get('t_time_to'))) if _str(prog.get('t_time')) else ''
                lines.append(('%s: %s  %s' % (_("Now") if idx == 0 else _("Next"), span, _str(prog.get('name')))).strip())
                if _str(prog.get('descr')):
                    lines.append(_str(prog.get('descr')))
                lines.append('')
            if not lines:
                lines.append(_("No programme guide for this channel."))
            if _int(cItem.get('archive_days'), 0):
                lines.append(_("Catch-up: %d days") % _int(cItem.get('archive_days'), 0))
            return self._article(cItem, '\n'.join(lines).strip(), icon, {'station': cItem.get('title', '')})
        other = dict(_dict(cItem.get('st_info')))
        # desc: "year | genres | rating[/br]plot" of describe() for movies / series, the own plot of a season or
        # an episode (which carry the st_info of their series)
        desc = cItem.get('desc', '')
        head = self.describe(other, '')
        text = desc[len(head):] if head and desc.startswith(head) else desc
        text = text.replace('[/br]', '\n').strip()
        if not (text and icon) and cItem.get('meta_title'):
            # libs/moviemeta only when the portal itself has no plot or no picture
            meta = self._moviemeta('movie' if kind == 'movie' else 'tv', cItem.get('meta_title', ''), cItem.get('meta_year', ''))
            for key, value in _dict(meta.get('info')).items():
                other.setdefault(key, value)
            text = text or meta.get('plot', '')
            icon = icon or meta.get('poster', '')
        if kind in ('series', 'season') and cItem.get('episodes'):
            other['episodes'] = str(len(cItem['episodes']))
        return self._article(cItem, text, icon, other)

    def getFavouriteData(self, cItem):
        try:
            if cItem.get('acc_id'):
                return json_dumps(dict((key, cItem[key]) for key in self.FAV_FIELDS if key in cItem))
        except Exception:
            printExc()
        return CBaseHostClass.getFavouriteData(self, cItem)

    ###################################################
    # Handle Service
    ###################################################
    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)
        if isJumpItem(self.currItem):
            self.currItem = jumpTarget(self, self.currItem)
        name = self.currItem.get('name', '')
        category = self.currItem.get('category', '')
        printDBG('Stalker.handleService name[%s] category[%s]' % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'st_account':
            self.listAccount(self.currItem)
        elif category == 'st_cats':
            self.listCategories(self.currItem)
        elif category == 'st_list':
            self.listStreams(self.currItem)
        elif category == 'st_series':
            self.listSeasons(self.currItem)
        elif category in ('st_season', 'st_vodseries'):
            self.listEpisodes(self.currItem)
        elif category == 'st_archive_genres':
            self.listArchiveGenres(self.currItem)
        elif category == 'st_archive_channels':
            self.listArchiveChannels(self.currItem)
        elif category == 'st_archive_days':
            self.listArchiveDays(self.currItem)
        elif category == 'st_archive_day':
            self.listArchiveProgrammes(self.currItem)
        elif category in ('search', 'search_next_page'):
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
        elif category == 'search_history':
            base = {'name': 'history', 'category': 'search'}
            for key in ('acc', 'acc_id'):
                if key in self.currItem:
                    base[key] = self.currItem[key]
            self.listsHistory(base, 'desc', _("Type: "))
        else:
            printExc()
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, StalkerPortalHost(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('stalker')

    def getSearchTypes(self):
        return [(_("Live channels"), 'live'), (_("Movies"), 'movie'), (_("Series"), 'series')]

    def withArticleContent(self, cItem):
        return bool(cItem.get('acc_id')) and cItem.get('category', '') in ITEM_KINDS
