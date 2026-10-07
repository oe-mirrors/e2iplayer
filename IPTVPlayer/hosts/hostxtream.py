# -*- coding: utf-8 -*-
# Last Modified: 06.10.2026
# hostxtream.py - Xtream Codes IPTV accounts (player_api.php)
# 17.10.2025 - popking (odem2014): live channels
# 03.10.2026 - live + movies + series + catch-up for up to 3 accounts
#   - up to 3 account slots (name / server / user / password, ConfigLogin + ConfigSecret); the server field also
#     takes a pasted get.php / M3U link (http://host:port/get.php?username=..&password=..) and is normalised
#     (missing scheme, trailing slash, default port, get.php / player_api.php path)
#   - wrong credentials: the panel answers {"user_info":{"auth":0}} - shown as a message instead of a crash;
#     expiry date formatted, status and max/active connections per account in the menu
#   - user name / password URL-quoted in API and stream URLs; the User-Agent is in the meta of every stream link
#   - movies (get_vod_categories / get_vod_streams) and series (get_series_categories / get_series /
#     get_series_info -> seasons -> episodes), play URL /movie|series/<u>/<p>/<id>.<ext> built only in
#     getLinksForVideo; the lists are cached in memory for the session
#   - INFO: get_vod_info / get_series_info, libs/moviemeta as fallback when the panel has no plot / cover;
#     live channels: now / next from get_short_epg, fetched only when INFO is pressed (one request per channel)
#   - catch-up: "Catch-up" folder in a live category for channels with tv_archive=1 -> days ->
#     get_simple_data_table programmes -> /timeshift/<u>/<p>/<minutes>/<YYYY-MM-DD:HH-MM>/<id>.ts in server time
#   - search per type (live / movies / series) in the account's full lists (downloaded once per session, filtered
#     locally, case-insensitive, Arabic/Persian digits normalised), search history
#   - watched flag for movies / episodes / seasons / series, download marker, favourites, sidecar and
#     "Title (Year)" / "Show - SxxExx - Name" naming; rows carry xtream://<account id>/... instead of the stream
#     URL, so no password ends up in favourites, marker files or the debug log
# 05.10.2026 - more accounts from playlists.txt in the X-Streamity format (one get.php line per
#   account, " #Name"): <ConfigDir>/IPTVAccounts/playlists.txt always, the X-Streamity plugin's file with the
#   option; read only, listed after the slots without a status request each
#   - "Show adult content" (default off): without it streams flagged is_adult, categories named "xxx", "adult",
#     "18+" ... and streams named "xxx", "porn", "18+" ... are left out
#   - "Title (Year)" naming also drops short tags in front like "NF - ", "AMZ - ", "4K - "
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _, SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsSidecarEnabled, IsMediaNamingNormalized
from Plugins.Extensions.IPTVPlayer.components.configsecret import ConfigLogin, ConfigSecret
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, b64Decode
try:
    from Plugins.Extensions.IPTVPlayer.tools.iptvtools import registerLogSecret
except ImportError:  # an older plugin without it: the host still runs
    def registerLogSecret(*values):
        pass
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.tools.iptvnaming import formatSxxExx, parseSxxExx
from Plugins.Extensions.IPTVPlayer.tools.iptvpaging import addPagingItems, isJumpItem, jumpTarget
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedhelper import IPTVWatchedHelper
from Plugins.Extensions.IPTVPlayer.tools.iptvwatchedfoldermixin import GenericFolderWatchedScraperMixin, GenericFolderWatchedHostMixin
from Plugins.Extensions.IPTVPlayer.libs.urlmetahelper import buildSidecarFromItem, applySidecarToLinks, sidecarFromUrlMeta, decorateResolvedLinkItems
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import urlparse, parse_qsl
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str, ensure_binary
from Components.config import config, ConfigText, ConfigYesNo, getConfigListEntry
import calendar
import hashlib
import os
import re
import time

###################################################
# config: account 1 keeps the old option names
###################################################
MAX_ACCOUNTS = 3


def _cfgName(base, slot):
    return base if slot == 1 else '%s%d' % (base, slot)


for _slot in range(1, MAX_ACCOUNTS + 1):
    setattr(config.plugins.iptvplayer, _cfgName('xtream_name', _slot), ConfigText(default='', fixed_size=False))
    setattr(config.plugins.iptvplayer, _cfgName('xtream_host', _slot), ConfigText(default='', fixed_size=False))
    setattr(config.plugins.iptvplayer, _cfgName('xtream_username', _slot), ConfigLogin(default='', fixed_size=False))
    setattr(config.plugins.iptvplayer, _cfgName('xtream_password', _slot), ConfigSecret(default='', fixed_size=False))
config.plugins.iptvplayer.xtream_useragent = ConfigText(default='', fixed_size=False)
config.plugins.iptvplayer.xtream_xstreamity = ConfigYesNo(default=True)
config.plugins.iptvplayer.xtream_adult = ConfigYesNo(default=False)
FILE_SLOT = 101  # accounts from the playlists.txt files


def _cfg(base, slot):
    return getattr(config.plugins.iptvplayer, _cfgName(base, slot))


def GetConfigList():
    optionList = []
    for slot in range(1, MAX_ACCOUNTS + 1):
        optionList.append(getConfigListEntry(_("Account %d - name (optional):") % slot, _cfg('xtream_name', slot)))
        optionList.append(getConfigListEntry(_("Account %d - server (http://host:port or get.php link):") % slot, _cfg('xtream_host', slot)))
        optionList.append(getConfigListEntry(_("Account %d - user name:") % slot, _cfg('xtream_username', slot)))
        optionList.append(getConfigListEntry(_("Account %d - password:") % slot, _cfg('xtream_password', slot)))
    optionList.append(getConfigListEntry(_("User-Agent (leave empty for the default):"), config.plugins.iptvplayer.xtream_useragent))
    optionList.append(getConfigListEntry(_("Also use the accounts of X-Streamity (%s)") % pluginFile(), config.plugins.iptvplayer.xtream_xstreamity))
    optionList.append(getConfigListEntry(_("Show adult content"), config.plugins.iptvplayer.xtream_adult))
    return optionList


def gettytul():
    return 'Xtream IPTV'


###################################################
# helpers without state
###################################################
# the host's own UA since the first version: IPTV panels often block browser UAs or bind the account to the
# player's UA - the config field overrides it
DEFAULT_UA = 'Enigma2-IPTV XtreamAPI/1.0'
PAGE_SIZE = 100
LIST_TTL = 30 * 60  # categories / streams / series info
ACCOUNT_TTL = 5 * 60  # status line, connections
EPG_TTL = 5 * 60
ARCHIVE_TTL = 10 * 60

KIND_ACTIONS = {'live': ('get_live_categories', 'get_live_streams'),
                'movie': ('get_vod_categories', 'get_vod_streams'),
                'series': ('get_series_categories', 'get_series')}
# rows with links / INFO -> what they are
ITEM_KINDS = {'xt_live': 'live', 'xt_movie': 'movie', 'xt_series': 'series', 'xt_season': 'season', 'xt_episode': 'episode',
              'xt_timeshift': 'timeshift', 'xt_archive_days': 'archive'}

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


def _md5(text):
    return hashlib.md5(ensure_binary(text)).hexdigest()


def _b64Text(value):
    value = _str(value)
    if value == '':
        return ''
    try:
        return b64Decode(value).strip()
    except Exception:
        return value  # some panels send plain text


def parseAccountInput(hostText, user='', pwd=''):
    # server field -> (server, user, password); a pasted get.php / player_api.php link fills an empty user / password
    hostText = _str(hostText)
    user, pwd = _str(user), _str(pwd)
    if hostText == '':
        return '', user, pwd
    if '://' not in hostText:
        hostText = 'http://' + hostText.lstrip('/')  # NOSONAR - Xtream panels mostly run on plain http
    try:
        parts = urlparse(hostText)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        if not user:
            user = _str(query.get('username', ''))
        if not pwd:
            pwd = _str(query.get('password', ''))
        scheme = (parts.scheme or 'http').lower()
        netloc = parts.netloc.rsplit('@', 1)[-1].strip().lower()
        if (scheme == 'http' and netloc.endswith(':80')) or (scheme == 'https' and netloc.endswith(':443')):
            netloc = netloc.rsplit(':', 1)[0]
        path = re.sub(r'/(?:get|player_api|panel_api|xmltv|c)(?:\.php)?/?$', '', parts.path or '').rstrip('/')
        if not netloc:
            return '', user, pwd
        return '%s://%s%s' % (scheme, netloc, path), user, pwd
    except Exception:
        printExc()
    return '', user, pwd


# X-Streamity's playlists.txt: one line per account, "#" in front switches it off
#   http://host:port/get.php?username=U&password=P&type=m3u_plus&output=ts #Name
ACCOUNTS_PLUGIN = ('XStreamity', '/etc/enigma2/xstreamity/', 'playlists.txt')
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


def readXtreamAccounts(withPlugin=True):
    """[{'name', 'url', 'user', 'pwd', 'file'}] - url is the line's get.php address (server part for the host)"""
    accounts = []
    for path in _accountFiles(withPlugin):
        for line in _accountLines(path):
            if not line.startswith(('http://', 'https://')):
                continue
            url, name = _splitMark(line, ' #')
            url = url.strip()
            try:
                query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
            except Exception:
                continue
            user, pwd = query.get('username', '').strip(), query.get('password', '').strip()
            if user and pwd:
                accounts.append({'name': name.strip(), 'url': url, 'user': user, 'pwd': pwd, 'file': path})
    return accounts


class XtreamApiHost(GenericFolderWatchedScraperMixin, CBaseHostClass):
    # stable identity of a row; never credentials - the account is looked up by acc_id at play time
    FAV_FIELDS = ('name', 'category', 'type', 'url', 'title', 's_title', 'icon', 'desc', 'acc', 'acc_id', 'x_kind',
                  'stream_id', 'ext', 'series_id', 'season', 'episode_id', 'ep_num', 'tv_archive', 'archive_days',
                  'ts_start', 'ts_stop', 'start_str', 'channel', 'meta_type', 'meta_title', 'meta_year', 'cat_id')

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'xtream', 'cookie': 'xtream.cookie'})
        self.MAIN_URL = ''
        self.DEFAULT_ICON_URL = 'https://raw.githubusercontent.com/oe-mirrors/e2iplayer/gh-pages/Thumbnails/xtream.png'
        self.cache = {}
        self.watchedHelper = IPTVWatchedHelper('xtream')
        self.wfInitFolderCache()

    ###################################################
    # accounts
    ###################################################
    def getAccounts(self):
        accounts = []
        ua = _str(config.plugins.iptvplayer.xtream_useragent.value) or DEFAULT_UA
        for slot in range(1, MAX_ACCOUNTS + 1):
            host, user, pwd = parseAccountInput(_cfg('xtream_host', slot).value, _cfg('xtream_username', slot).value, _cfg('xtream_password', slot).value)
            if not (host and user and pwd):
                continue
            name = _str(_cfg('xtream_name', slot).value) or re.sub(r'^https?://', '', host)
            accounts.append({'slot': slot, 'name': name, 'host': host, 'user': user, 'pwd': pwd, 'ua': ua,
                             # persistent (watched flag, favourites, markers): server + user, never the password
                             'id': _md5('%s|%s' % (host, user))[:12],
                             # memory cache only: changes with the password, so a corrected password is used at once
                             'ck': _md5('%s|%s|%s' % (host, user, pwd))})
        # playlists.txt in our own folder and (option) the X-Streamity plugin's file, after the slots
        known = set(acc['id'] for acc in accounts)
        for idx, entry in enumerate(readXtreamAccounts(config.plugins.iptvplayer.xtream_xstreamity.value)):
            host, user, pwd = parseAccountInput(entry['url'], entry['user'], entry['pwd'])
            accId = _md5('%s|%s' % (host, user))[:12]
            if not (host and user and pwd) or accId in known:
                continue
            known.add(accId)
            accounts.append({'slot': FILE_SLOT + idx, 'name': entry['name'] or re.sub(r'^https?://', '', host), 'host': host, 'user': user,
                             'pwd': pwd, 'ua': ua, 'id': accId, 'ck': _md5('%s|%s|%s' % (host, user, pwd)), 'file': entry['file']})
        # the stream urls (/live/<user>/<password>/...) also go into the player / downloader log lines
        for acc in accounts:
            registerLogSecret(acc['user'], acc['pwd'])
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
        # the server address changed (new domain of the provider): the slot the item came from (own slots only,
        # the position of a file entry is no identity)
        for acc in accounts:
            if acc['slot'] == slot and slot <= MAX_ACCOUNTS:
                printDBG('Xtream: account %s not found, using slot %d' % (accId, slot))
                return acc
        if not accId and accounts:
            return accounts[0]
        return None

    def accParams(self, acc, extra=None):
        params = {'acc': acc['slot'], 'acc_id': acc['id']}
        if extra:
            params.update(extra)
        return params

    def mask(self, url):
        # credentials out of anything that goes into the debug log
        url = _str(url)
        for acc in self.getAccounts():
            for secret in (_quote(acc['pwd']), acc['pwd'], _quote(acc['user']), acc['user']):
                if len(secret) > 1:
                    url = url.replace('/%s/' % secret, '/***/').replace('=%s' % secret, '=***')
        return url

    ###################################################
    # requests
    ###################################################
    def _httpParams(self, acc):
        return {'header': {'User-Agent': acc['ua'], 'Accept': 'application/json, */*', 'Connection': 'close'}}

    def apiUrl(self, acc, action='', extra=None):
        url = '%s/player_api.php?username=%s&password=%s' % (acc['host'], _quote(acc['user']), _quote(acc['pwd']))
        if action:
            url += '&action=%s' % action
        for key, value in (extra or []):
            url += '&%s=%s' % (key, _quote(value))
        return url

    def streamUrl(self, acc, kind, name):
        return '%s/%s/%s/%s/%s' % (acc['host'], kind, _quote(acc['user']), _quote(acc['pwd']), name)

    def api(self, acc, action='', extra=None):
        printDBG('Xtream.api [%s] action[%s] %s' % (acc['host'], action, extra or ''))
        sts, data = self.cm.getPage(self.apiUrl(acc, action, extra), self._httpParams(acc))
        if not sts or not data:
            return None
        try:
            return json_loads(data)
        except Exception:
            printDBG('Xtream.api: no JSON answer [%s]' % self.mask(_str(data)[:200]))
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

    def isAuthError(self, data):
        return isinstance(data, dict) and isinstance(data.get('user_info'), dict) and _int(data['user_info'].get('auth', 1), 1) == 0

    def apiList(self, acc, action, extra=None, ttl=LIST_TTL):
        # a JSON list, or None (message for the user set); some panels send {"0": {...}, "1": {...}}
        def fetch():
            data = self.api(acc, action, extra)
            if isinstance(data, list):
                return data
            if self.isAuthError(data):
                return 'auth'
            if isinstance(data, dict) and data and all(isinstance(v, dict) for v in data.values()) and 'user_info' not in data:
                try:
                    return [data[k] for k in sorted(data.keys(), key=lambda x: _int(x))]
                except Exception:
                    return list(data.values())
            return None
        data = self.cached((acc['ck'], action, tuple(extra or ())), ttl, fetch)
        if data == 'auth':
            self.cache.pop((acc['ck'], action, tuple(extra or ())), None)
            SetIPTVPlayerLastHostError(_("Failed to log in user \"%s\". Please check your login and password.") % acc['user'])
            return None
        if data is None:
            SetIPTVPlayerLastHostError(_("Failed to connect to server \"%s\".") % acc['host'])
        return data

    def getAccountData(self, acc):
        # player_api.php without an action: {"user_info": {...}, "server_info": {...}} or {} when unreachable
        key = (acc['ck'], 'account')
        entry = self.cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
        data = self.api(acc)
        data = data if isinstance(data, dict) else {}
        # an unreachable server is asked again after a minute, not on every list of the same menu
        self.cache[key] = (time.time() + (ACCOUNT_TTL if data else 60), data)
        return data

    def accountStatus(self, acc):
        # (ok, text for the menu)
        data = self.getAccountData(acc)
        if not data:
            return False, _("Failed to connect to host.")
        ui = _dict(data.get('user_info'))
        if _int(ui.get('auth', 0)) != 1:
            return False, _("Login or password is wrong.")
        parts = [_("Status: %s") % (_str(ui.get('status')) or '?')]
        exp = _int(ui.get('exp_date'), 0)
        parts.append(_("Expiry: %s") % (time.strftime('%d.%m.%Y', time.localtime(exp)) if exp > 0 else _("never")))
        if _str(ui.get('is_trial')) in ('1', 'true'):
            parts.append(_("Trial"))
        maxCons = _str(ui.get('max_connections'))
        if maxCons:
            parts.append(_("Connections: %s of %s") % (_str(ui.get('active_cons')) or '0', maxCons))
        return _str(ui.get('status')).lower() in ('active', ''), ' | '.join(parts)

    def serverOffset(self, acc):
        # server local time - UTC in seconds (the timeshift URL takes the start in server time), None if unknown
        si = _dict(self.getAccountData(acc).get('server_info'))
        try:
            nowTs = _int(si.get('timestamp_now'), 0)
            timeNow = _str(si.get('time_now'))
            if nowTs <= 0 or len(timeNow) < 16:
                return None
            serverTs = calendar.timegm(time.strptime(timeNow[:16], '%Y-%m-%d %H:%M'))
            return int(round((serverTs - nowTs) / 900.0)) * 900
        except Exception:
            printExc()
        return None

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
            if category == 'xt_movie' and cItem.get('stream_id'):
                return 'movie:%s|%s' % (accId, cItem['stream_id'])
            if category == 'xt_episode' and cItem.get('episode_id'):
                return 'episode:%s|%s|%s' % (accId, cItem.get('series_id', ''), cItem['episode_id'])
            if category == 'xt_season' and cItem.get('series_id'):
                return 'season:%s|%s|%s' % (accId, cItem['series_id'], cItem.get('season', ''))
            if category == 'xt_series' and cItem.get('series_id'):
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
            self.addMarker({'title': _("Please configure Xtream (blue button)"),
                            'desc': _("Server, user name and password in the host configuration. The server field also takes a get.php link. More accounts: %s with one get.php link per line (X-Streamity format).") % ownFile()})
            return
        if len(accounts) == 1:
            self.listAccount(self.accParams(accounts[0], {'name': 'category'}))
            return
        for acc in accounts:
            # the status is one request per account: only for the own slots, a long playlists.txt opens at once
            status = acc['file'] if acc.get('file') else self.accountStatus(acc)[1]
            self.addDir(self.accParams(acc, {'name': 'category', 'category': 'xt_account', 'title': acc['name'], 'desc': '%s[/br]%s' % (acc['host'], status)}))

    def listAccount(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        ok, status = self.accountStatus(acc)
        if not ok:
            SetIPTVPlayerLastHostError('%s: %s' % (acc['name'], status))
            self.addMarker({'title': '%s: %s' % (acc['name'], status), 'desc': acc['host']})
            data = self.getAccountData(acc)
            if not data or self.isAuthError(data):
                return
        base = self.accParams(acc, {'name': 'category'})
        for kind, title in (('live', _("Live channels")), ('movie', _("Movies")), ('series', _("Series"))):
            params = dict(base)
            params.update({'category': 'xt_cats', 'x_kind': kind, 'title': title, 'desc': status})
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
        data = self.apiList(acc, KIND_ACTIONS[kind][0])
        if data is None:
            return
        # url: a stable pseudo address of the list (favourites, "Jump" template) - never the credentials
        base = self.accParams(acc, {'name': 'category', 'category': 'xt_list', 'x_kind': kind, 'page': 1, 'good_for_fav': True})
        params = dict(base)
        params.update({'title': _("All"), 'cat_id': '', 'url': 'xtream://%s/%s/cat/' % (acc['id'], kind)})
        self.addDir(params)
        adultCats = self.adultCategories(acc, kind)
        for cat in data:
            cat = _dict(cat)
            title = _str(cat.get('category_name'))
            catId = _str(cat.get('category_id'))
            if not title or not catId or catId in adultCats:
                continue
            params = dict(base)
            params.update({'title': title, 'cat_id': catId, 'url': 'xtream://%s/%s/cat/%s' % (acc['id'], kind, _quote(catId))})
            self.addDir(params)

    def adultCategories(self, acc, kind):
        # ids of the categories hidden without "Show adult content" (by name, the panels flag only streams)
        if config.plugins.iptvplayer.xtream_adult.value:
            return set()
        return set(_str(_dict(cat).get('category_id')) for cat in (self.apiList(acc, KIND_ACTIONS[kind][0]) or [])
                   if _isAdultName(_dict(cat).get('category_name'), True))

    def getStreams(self, acc, kind, catId=''):
        extra = (('category_id', catId),) if catId else None
        data = self.apiList(acc, KIND_ACTIONS[kind][1], extra)
        if data is None or config.plugins.iptvplayer.xtream_adult.value:
            return data
        # without "Show adult content": streams flagged is_adult, in an adult category or with an adult name
        adultCats = self.adultCategories(acc, kind)
        return [elm for elm in data if not (_int(_dict(elm).get('is_adult'), 0) == 1 or _str(_dict(elm).get('category_id')) in adultCats or
                                            _isAdultName(_dict(elm).get('name')))]

    def listStreams(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        kind = cItem.get('x_kind', 'live')
        catId = cItem.get('cat_id', '')
        data = self.getStreams(acc, kind, catId)
        if data is None:
            return
        page = max(1, _int(cItem.get('page', 1), 1))
        if kind == 'live' and page == 1:
            archived = [x for x in data if _int(_dict(x).get('tv_archive'), 0) == 1]
            if archived:
                self.addDir(self.accParams(acc, {'name': 'category', 'category': 'xt_archive_channels', 'x_kind': 'live', 'cat_id': catId,
                                                 'title': _("Catch-up (%d channels)") % len(archived),
                                                 'desc': _("Programmes of the last days of the channels with an archive")}))
        for elm in data[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            self.addStreamItem(acc, kind, _dict(elm))
        # the whole list comes in one answer, paged here
        lastPage = (len(data) + PAGE_SIZE - 1) // PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, cItem.get('url', '').replace('{', '%7B').replace('}', '%7D'))

    def addStreamItem(self, acc, kind, elm):
        if kind == 'live':
            self.addLive(acc, elm)
        elif kind == 'movie':
            self.addMovie(acc, elm)
        else:
            self.addSeries(acc, elm)

    def addLive(self, acc, elm):
        sid = _str(elm.get('stream_id'))
        title = _str(elm.get('name'))
        if not sid or not title:
            return
        days = _int(elm.get('tv_archive_duration'), 0) if _int(elm.get('tv_archive'), 0) == 1 else 0
        desc = (_("Catch-up: %d days") % days) if days else ''
        self.addVideo(self.accParams(acc, {'name': 'category', 'category': 'xt_live', 'x_kind': 'live', 'title': title, 'channel': title,
                                           'url': 'xtream://%s/live/%s' % (acc['id'], sid), 'stream_id': sid,
                                           'icon': _str(elm.get('stream_icon')), 'desc': desc, 'tv_archive': 1 if days else 0,
                                           'archive_days': days, 'good_for_fav': True}))

    def addMovie(self, acc, elm):
        sid = _str(elm.get('stream_id'))
        rawTitle = _str(elm.get('name')) or _str(elm.get('title'))
        if not sid or not rawTitle:
            return
        cleanTitle, nameYear = _cleanName(rawTitle)
        cleanTitle = cleanTitle or rawTitle
        year = _yearOf(elm.get('year'), elm.get('releaseDate'), elm.get('releasedate')) or nameYear
        title = rawTitle
        if IsMediaNamingNormalized():
            title = '%s (%s)' % (cleanTitle, year) if year else cleanTitle
        descParts = [x for x in (year, _str(elm.get('genre')), (_("Rating: %s") % _str(elm.get('rating'))) if _str(elm.get('rating')) not in ('', '0') else '') if x]
        desc = ' | '.join(descParts)
        plot = _str(elm.get('plot'))
        if plot:
            desc = '%s[/br]%s' % (desc, plot) if desc else plot
        self.addVideo(self.accParams(acc, {'name': 'category', 'category': 'xt_movie', 'x_kind': 'movie', 'title': title, 's_title': cleanTitle,
                                           'url': 'xtream://%s/movie/%s' % (acc['id'], sid), 'stream_id': sid,
                                           'ext': _str(elm.get('container_extension')) or 'mp4', 'icon': _str(elm.get('stream_icon')),
                                           'desc': desc, 'meta_type': 'movie', 'meta_title': cleanTitle, 'meta_year': year, 'good_for_fav': True}))

    def addSeries(self, acc, elm):
        sid = _str(elm.get('series_id'))
        rawTitle = _str(elm.get('name')) or _str(elm.get('title'))
        if not sid or not rawTitle:
            return
        cleanTitle, nameYear = _cleanName(rawTitle)
        cleanTitle = cleanTitle or rawTitle
        year = _yearOf(elm.get('year'), elm.get('releaseDate'), elm.get('release_date')) or nameYear
        descParts = [x for x in (year, _str(elm.get('genre'))) if x]
        desc = ' | '.join(descParts)
        plot = _str(elm.get('plot'))
        if plot:
            desc = '%s[/br]%s' % (desc, plot) if desc else plot
        self.addDir(self.accParams(acc, {'name': 'category', 'category': 'xt_series', 'x_kind': 'series',
                                         'title': cleanTitle if IsMediaNamingNormalized() else rawTitle, 's_title': cleanTitle,
                                         'url': 'xtream://%s/series/%s' % (acc['id'], sid), 'series_id': sid,
                                         'icon': _str(elm.get('cover')), 'desc': desc,
                                         'meta_type': 'tv', 'meta_title': cleanTitle, 'meta_year': year, 'good_for_fav': True}))

    ###################################################
    # series
    ###################################################
    def getSeriesInfo(self, acc, seriesId):
        def fetch():
            data = self.api(acc, 'get_series_info', (('series_id', seriesId),))
            if self.isAuthError(data):
                SetIPTVPlayerLastHostError(_("Failed to log in user \"%s\". Please check your login and password.") % acc['user'])
                return None
            return data if isinstance(data, dict) else None
        return self.cached((acc['ck'], 'series_info', seriesId), LIST_TTL, fetch)

    def seriesEpisodes(self, info):
        # {"1": [...], "2": [...]} - some panels send a list of season lists instead
        episodes = (info or {}).get('episodes')
        seasons = {}
        if isinstance(episodes, dict):
            for key, eps in episodes.items():
                if isinstance(eps, list):
                    seasons[_str(key)] = [e for e in eps if isinstance(e, dict)]
        elif isinstance(episodes, list):
            for eps in episodes:
                for ep in (eps if isinstance(eps, list) else [eps]):
                    if isinstance(ep, dict):
                        seasons.setdefault(_str(ep.get('season')) or '1', []).append(ep)
        return seasons

    def listSeasons(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        seriesId = cItem.get('series_id', '')
        info = self.getSeriesInfo(acc, seriesId)
        if info is None:
            return
        seasons = self.seriesEpisodes(info)
        if not seasons:
            SetIPTVPlayerLastHostError(_("No episodes available yet."))
            return
        seasonInfo = {}
        for season in (info.get('seasons') or []):
            if isinstance(season, dict):
                seasonInfo[_str(season.get('season_number'))] = season
        show = cItem.get('s_title', '') or cItem.get('title', '')
        for key in sorted(seasons.keys(), key=lambda x: (_int(x, 9999), x)):
            sInfo = seasonInfo.get(key, {})
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'xt_season', 'x_kind': 'season', 'season': key,
                           'title': '%s - %s' % (show, _("Season %s") % key), 's_title': show,
                           'url': 'xtream://%s/series/%s/%s' % (acc['id'], seriesId, key),
                           'icon': _str(sInfo.get('cover_big')) or _str(sInfo.get('cover')) or cItem.get('icon', ''),
                           'desc': _str(sInfo.get('overview')) or cItem.get('desc', '')})
            self.addDir(params)

    def episodeTitle(self, show, season, epNum, rawTitle, epName):
        if not IsMediaNamingNormalized():
            return rawTitle or ('%s %s' % (_("Episode"), epNum))
        name = _str(epName) or _str(rawTitle)
        s, e = parseSxxExx(name)
        if s and e:
            season, epNum = s, e
            name = re.sub(r'^.*?S\s*\d+\s*[ .:/x_-]*\s*E\s*\d+', '', name, flags=re.I)
        if show and name.lower().startswith(show.lower()):
            name = name[len(show):]
        name = name.strip(' -|:').lstrip('.').strip()
        if re.match(r'^(?:episode|ep\.?|folge)?\s*\d+$', name, re.I) or name.lower() == show.lower():
            name = ''
        tag = formatSxxExx(season or '1', epNum or '0')
        return '%s - %s - %s' % (show, tag, name) if name else '%s - %s' % (show, tag)

    def listEpisodes(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        seriesId = cItem.get('series_id', '')
        season = cItem.get('season', '')
        info = self.getSeriesInfo(acc, seriesId)
        if info is None:
            return
        show = cItem.get('s_title', '') or cItem.get('title', '')
        for ep in self.seriesEpisodes(info).get(season, []):
            epId = _str(ep.get('id'))
            if not epId:
                continue
            epInfo = _dict(ep.get('info'))
            epNum = _str(ep.get('episode_num'))
            rawTitle = _str(ep.get('title'))
            title = self.episodeTitle(show, _str(ep.get('season')) or season, epNum, rawTitle, epInfo.get('name'))
            descParts = [x for x in (_str(epInfo.get('releasedate')) or _str(epInfo.get('air_date')), _str(epInfo.get('duration'))) if x]
            desc = ' | '.join(descParts)
            plot = _str(epInfo.get('plot')) or _str(epInfo.get('overview'))
            if plot:
                desc = '%s[/br]%s' % (desc, plot) if desc else plot
            params = dict(cItem)
            params.update({'good_for_fav': True, 'category': 'xt_episode', 'x_kind': 'episode', 'title': title, 's_title': show,
                           'url': 'xtream://%s/episode/%s' % (acc['id'], epId), 'episode_id': epId, 'ep_num': epNum,
                           'ext': _str(ep.get('container_extension')) or 'mp4',
                           'icon': _str(epInfo.get('movie_image')) or cItem.get('icon', ''), 'desc': desc})
            self.addVideo(params)

    ###################################################
    # catch-up
    ###################################################
    def listArchiveChannels(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        data = self.getStreams(acc, 'live', cItem.get('cat_id', ''))
        if data is None:
            return
        channels = [_dict(elm) for elm in data if _int(_dict(elm).get('tv_archive'), 0) == 1 and _str(_dict(elm).get('stream_id'))]
        page = max(1, _int(cItem.get('page', 1), 1))
        for elm in channels[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            days = _int(elm.get('tv_archive_duration'), 0)
            sid = _str(elm.get('stream_id'))
            self.addDir(self.accParams(acc, {'name': 'category', 'category': 'xt_archive_days', 'x_kind': 'archive', 'stream_id': sid,
                                             'title': _str(elm.get('name')), 'channel': _str(elm.get('name')),
                                             'archive_days': days, 'icon': _str(elm.get('stream_icon')),
                                             'desc': _("Catch-up: %d days") % days if days else ''}))
        lastPage = (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE
        addPagingItems(self, dict(cItem, desc=''), page, page < lastPage, lastPage, 'xtream://%s/live/archive/%s' % (acc['id'], _quote(cItem.get('cat_id', ''))))

    def listArchiveDays(self, cItem):
        days = max(1, min(_int(cItem.get('archive_days'), 0) or 7, 31))
        now = time.localtime()
        midnight = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1)))
        for idx in range(days + 1):
            # mktime with the day shifted: correct also over a daylight saving change
            dayStart = int(time.mktime((now.tm_year, now.tm_mon, now.tm_mday - idx, 0, 0, 0, 0, 0, -1))) if idx else midnight
            label = time.strftime('%a %d.%m.%Y', time.localtime(dayStart))
            if idx == 0:
                label = '%s (%s)' % (_("Today"), label)
            elif idx == 1:
                label = '%s (%s)' % (_("Yesterday"), label)
            params = dict(cItem)
            params.update({'good_for_fav': False, 'category': 'xt_archive_day', 'title': label, 'day_start': dayStart})
            self.addDir(params)

    def getEpgTable(self, acc, streamId):
        def fetch():
            data = self.api(acc, 'get_simple_data_table', (('stream_id', streamId),))
            return data.get('epg_listings') if isinstance(data, dict) and isinstance(data.get('epg_listings'), list) else None
        return self.cached((acc['ck'], 'epg_table', streamId), ARCHIVE_TTL, fetch)

    def listArchiveProgrammes(self, cItem):
        acc = self.getAccount(cItem)
        if acc is None:
            return
        streamId = cItem.get('stream_id', '')
        listings = self.getEpgTable(acc, streamId)
        if listings is None:
            SetIPTVPlayerLastHostError(_("No programme guide for this channel."))
            return
        dayStart = _int(cItem.get('day_start'), 0)
        dayEnd = int(time.mktime(time.localtime(dayStart)[:2] + (time.localtime(dayStart)[2] + 1, 0, 0, 0, 0, 0, -1)))
        now = int(time.time())
        channel = cItem.get('channel', '')
        normalize = IsMediaNamingNormalized()
        rows = []
        for prog in listings:
            prog = _dict(prog)
            start = _int(prog.get('start_timestamp'), 0)
            stop = _int(prog.get('stop_timestamp'), 0)
            if not (dayStart <= start < dayEnd) or stop <= start:
                continue
            # the archive holds what has finished; has_archive=1 marks it on panels that send the flag
            if start >= now or (stop > now and _int(prog.get('has_archive'), 0) != 1):
                continue
            rows.append((start, stop, prog))
        rows.sort(key=lambda x: x[0])
        for start, stop, prog in rows:
            name = _b64Text(prog.get('title')) or _("Program")
            span = '%s - %s' % (time.strftime('%H:%M', time.localtime(start)), time.strftime('%H:%M', time.localtime(stop)))
            if normalize:
                title = '%s - %s (%s)' % (channel, name, time.strftime('%Y-%m-%d %H.%M', time.localtime(start)))
            else:
                title = '%s  %s' % (span, name)
            desc = '%s %s[/br]%s' % (time.strftime('%d.%m.%Y', time.localtime(start)), span, _b64Text(prog.get('description')))
            self.addVideo(self.accParams(acc, {'name': 'category', 'category': 'xt_timeshift', 'x_kind': 'timeshift', 'title': title,
                                               'url': 'xtream://%s/timeshift/%s/%d' % (acc['id'], streamId, start),
                                               'stream_id': streamId, 'channel': channel, 'ts_start': start, 'ts_stop': stop,
                                               'start_str': _str(prog.get('start')), 'icon': cItem.get('icon', ''),
                                               'desc': desc, 'good_for_fav': False}))

    def timeshiftStart(self, acc, cItem):
        # "YYYY-MM-DD:HH-MM" in the time zone of the server
        start = _int(cItem.get('ts_start'), 0)
        offset = self.serverOffset(acc)
        if offset is not None:
            return time.strftime('%Y-%m-%d:%H-%M', time.gmtime(start + offset))
        m = re.match(r'(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})', cItem.get('start_str', ''))
        if m:
            # the guide's own start text is in server time on Xtream panels
            return '%s:%s-%s' % (m.group(1), m.group(2), m.group(3))
        return time.strftime('%Y-%m-%d:%H-%M', time.gmtime(start))

    ###################################################
    # search
    ###################################################
    def listSearchResult(self, cItem, searchPattern, searchType):
        kind = searchType if searchType in KIND_ACTIONS else 'live'
        words = _normSearchText(searchPattern).split()
        if not words:
            return
        if cItem.get('acc_id'):
            accounts = [self.getAccount(cItem)]
        else:
            # without an account (global search): the own slots, else the first file accounts - every account is
            # one download of its full list, a long playlists.txt would block for minutes
            accounts = self.getAccounts()
            accounts = [acc for acc in accounts if not acc.get('file')] or accounts[:MAX_ACCOUNTS]
        page = max(1, _int(cItem.get('page', 1), 1))
        found = []
        for acc in accounts:
            if acc is None:
                continue
            data = self.getStreams(acc, kind)
            for elm in (data or []):
                elm = _dict(elm)
                name = _normSearchText(elm.get('name') or elm.get('title'))
                if all(w in name for w in words):
                    found.append((acc, elm))
        for acc, elm in found[(page - 1) * PAGE_SIZE:page * PAGE_SIZE]:
            self.addStreamItem(acc, kind, elm)
        lastPage = (len(found) + PAGE_SIZE - 1) // PAGE_SIZE
        # constant pseudo url: only lets "Jump" through, the hits are cut by cItem['page']
        addPagingItems(self, dict(cItem, category='search_next_page', desc=''), page, page < lastPage, lastPage, 'xtream://search/')

    ###################################################
    # links
    ###################################################
    def getVodInfo(self, acc, streamId):
        def fetch():
            data = self.api(acc, 'get_vod_info', (('vod_id', streamId),))
            return data if isinstance(data, dict) and not self.isAuthError(data) else None
        return self.cached((acc['ck'], 'vod_info', streamId), LIST_TTL, fetch)

    def getLinksForVideo(self, cItem):
        printDBG('Xtream.getLinksForVideo [%s]' % cItem.get('url', ''))
        acc = self.getAccount(cItem)
        if acc is None:
            SetIPTVPlayerLastHostError(_("The Xtream account of this entry is not configured (any more)."))
            return []
        kind = ITEM_KINDS.get(cItem.get('category', ''), '')
        sid = cItem.get('stream_id', '')
        meta = {'User-Agent': acc['ua']}
        urltab = []
        if kind == 'live':
            formats = _dict(self.getAccountData(acc).get('user_info')).get('allowed_output_formats')
            formats = [_str(x).lower() for x in formats] if isinstance(formats, list) and formats else ['m3u8', 'ts']
            if 'm3u8' in formats:
                urltab.append({'name': 'HLS (m3u8)', 'url': strwithmeta(self.streamUrl(acc, 'live', '%s.m3u8' % sid), meta), 'need_resolve': 0})
            if 'ts' in formats or not urltab:
                urltab.append({'name': 'MPEG-TS', 'url': strwithmeta(self.streamUrl(acc, 'live', '%s.ts' % sid), meta), 'need_resolve': 0})
            return urltab
        if kind == 'timeshift':
            start = _int(cItem.get('ts_start'), 0)
            minutes = max(1, (_int(cItem.get('ts_stop'), 0) - start + 59) // 60)
            startStr = self.timeshiftStart(acc, cItem)
            urltab.append({'name': _("Catch-up"), 'url': strwithmeta(self.streamUrl(acc, 'timeshift', '%d/%s/%s.ts' % (minutes, startStr, sid)), meta), 'need_resolve': 0})
            # older panels only know streaming/timeshift.php
            oldUrl = '%s/streaming/timeshift.php?username=%s&password=%s&stream=%s&start=%s&duration=%d' % (acc['host'], _quote(acc['user']), _quote(acc['pwd']), sid, startStr, minutes)
            urltab.append({'name': _("Catch-up (timeshift.php)"), 'url': strwithmeta(oldUrl, meta), 'need_resolve': 0})
            printDBG('Xtream timeshift %s' % self.mask(urltab[0]['url']))
            return urltab
        sidecarTxt = ''
        if kind == 'movie':
            url = self.streamUrl(acc, 'movie', '%s.%s' % (sid, cItem.get('ext', '') or 'mp4'))
            if IsSidecarEnabled():
                info = _dict((self.getVodInfo(acc, sid) or {}).get('info'))
                sidecarTxt = _str(info.get('plot')) or _str(info.get('description'))
        elif kind == 'episode':
            url = self.streamUrl(acc, 'series', '%s.%s' % (cItem.get('episode_id', ''), cItem.get('ext', '') or 'mp4'))
        else:
            return []
        printDBG('Xtream stream %s' % self.mask(url))
        name = (cItem.get('ext', '') or 'mp4').upper()
        urltab.append({'name': name, 'url': strwithmeta(url, meta), 'need_resolve': 0})
        return applySidecarToLinks(urltab, buildSidecarFromItem(cItem, IsSidecarEnabled(), sidecarTxt))

    def getVideoLinks(self, videoUrl):
        sidecar = sidecarFromUrlMeta(videoUrl, IsSidecarEnabled())
        return decorateResolvedLinkItems([{'name': 'direct', 'url': videoUrl, 'need_resolve': 0}], sidecar)

    ###################################################
    # INFO
    ###################################################
    def getShortEpg(self, acc, streamId):
        def fetch():
            data = self.api(acc, 'get_short_epg', (('stream_id', streamId), ('limit', '2')))
            return data.get('epg_listings') if isinstance(data, dict) and isinstance(data.get('epg_listings'), list) else None
        return self.cached((acc['ck'], 'short_epg', streamId), EPG_TTL, fetch) or []

    def _moviemeta(self, mediaType, title, year):
        try:
            from Plugins.Extensions.IPTVPlayer.libs.moviemeta import LATIN_ONLY, getMeta, isLatinTitle
            # Arabic-only titles: only to the providers that know them (TMDb / TVmaze)
            return getMeta(mediaType, title, year, skip=() if isLatinTitle(title) else LATIN_ONLY) or {}
        except Exception:
            printExc()
        return {}

    def _article(self, cItem, title, text, icon, otherInfo):
        otherInfo = dict((k, _str(v)) for k, v in otherInfo.items() if _str(v))
        return [{'title': title or cItem.get('title', ''), 'text': text or cItem.get('desc', ''),
                 'images': [{'title': '', 'url': icon}] if icon else [], 'other_info': otherInfo}]

    def _enrich(self, mediaType, cItem, text, icon, otherInfo):
        # libs/moviemeta only when the panel itself has no plot or no picture
        if text and icon:
            return text, icon
        meta = self._moviemeta(mediaType, cItem.get('meta_title', '') or cItem.get('s_title', ''), cItem.get('meta_year', ''))
        for key, value in _dict(meta.get('info')).items():
            otherInfo.setdefault(key, value)
        return text or meta.get('plot', ''), icon or meta.get('poster', '')

    def getArticleContent(self, cItem):
        printDBG('Xtream.getArticleContent [%s]' % cItem.get('url', ''))
        acc = self.getAccount(cItem)
        kind = ITEM_KINDS.get(cItem.get('category', ''), '')
        icon = cItem.get('icon', '')
        if acc is None or kind in ('timeshift', 'archive'):
            return self._article(cItem, cItem.get('title', ''), cItem.get('desc', '').replace('[/br]', '\n'), icon, {})
        if kind == 'live':
            lines = []
            for idx, prog in enumerate(self.getShortEpg(acc, cItem.get('stream_id', ''))[:2]):
                prog = _dict(prog)
                start, stop = _int(prog.get('start_timestamp'), 0), _int(prog.get('stop_timestamp'), 0)
                span = '%s - %s' % (time.strftime('%H:%M', time.localtime(start)), time.strftime('%H:%M', time.localtime(stop))) if start and stop else ''
                head = '%s: %s  %s' % (_("Now") if idx == 0 else _("Next"), span, _b64Text(prog.get('title')))
                lines.append(head.strip())
                descr = _b64Text(prog.get('description'))
                if descr:
                    lines.append(descr)
                lines.append('')
            if not lines:
                lines.append(_("No programme guide for this channel."))
            if _int(cItem.get('archive_days'), 0):
                lines.append(_("Catch-up: %d days") % _int(cItem.get('archive_days'), 0))
            return self._article(cItem, cItem.get('title', ''), '\n'.join(lines).strip(), icon, {'station': cItem.get('channel', '')})
        if kind == 'movie':
            data = self.getVodInfo(acc, cItem.get('stream_id', '')) or {}
            info = _dict(data.get('info'))
            movieData = _dict(data.get('movie_data'))
            other = {'year': _yearOf(info.get('releasedate'), info.get('release_date'), cItem.get('meta_year')),
                     'released': _str(info.get('releasedate')) or _str(info.get('release_date')),
                     'genres': _str(info.get('genre')), 'director': _str(info.get('director')),
                     'cast': _str(info.get('cast')) or _str(info.get('actors')), 'country': _str(info.get('country')),
                     'duration': _str(info.get('duration')), 'rating': _str(info.get('rating')) if _str(info.get('rating')) not in ('0', '') else '',
                     'age_limit': _str(info.get('age')) or _str(info.get('mpaa_rating')),
                     'original_title': _str(info.get('o_name')) if _str(info.get('o_name')) != _str(movieData.get('name')) else ''}
            video = _dict(info.get('video'))
            if video.get('width') and video.get('height'):
                other['quality'] = '%sx%s %s' % (_str(video.get('width')), _str(video.get('height')), _str(video.get('codec_name')))
            text = _str(info.get('plot')) or _str(info.get('description'))
            cover = _str(info.get('movie_image')) or _str(info.get('cover_big'))
            text, cover = self._enrich('movie', cItem, text, cover or icon, other)
            return self._article(cItem, cItem.get('title', ''), text, cover or icon, other)
        if kind in ('series', 'season', 'episode'):
            data = self.getSeriesInfo(acc, cItem.get('series_id', '')) or {}
            info = _dict(data.get('info'))
            other = {'year': _yearOf(info.get('releaseDate'), info.get('release_date'), cItem.get('meta_year')),
                     'genres': _str(info.get('genre')), 'director': _str(info.get('director')), 'cast': _str(info.get('cast')),
                     'rating': _str(info.get('rating')) if _str(info.get('rating')) not in ('0', '') else '',
                     'duration': (_str(info.get('episode_run_time')) + ' min') if _str(info.get('episode_run_time')) not in ('', '0') else ''}
            seasons = self.seriesEpisodes(data)
            if seasons:
                other['seasons'] = str(len(seasons))
                other['episodes'] = str(sum(len(v) for v in seasons.values()))
            text = _str(info.get('plot'))
            cover = _str(info.get('cover'))
            if kind == 'episode':
                for ep in seasons.get(cItem.get('season', ''), []):
                    if _str(ep.get('id')) == cItem.get('episode_id', ''):
                        epInfo = _dict(ep.get('info'))
                        text = _str(epInfo.get('plot')) or text
                        cover = _str(epInfo.get('movie_image')) or cover
                        other['duration'] = _str(epInfo.get('duration')) or other['duration']
                        other['released'] = _str(epInfo.get('releasedate')) or _str(epInfo.get('air_date'))
                        break
            elif kind == 'season':
                cover = icon or cover
            text, cover = self._enrich('tv', cItem, text, cover or icon, other)
            return self._article(cItem, cItem.get('title', ''), text, cover or icon, other)
        return self._article(cItem, cItem.get('title', ''), cItem.get('desc', ''), icon, {})

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
        printDBG('Xtream.handleService name[%s] category[%s]' % (name, category))
        self.currList = []
        if name is None:
            self.listMain({'name': 'category'})
        elif category == 'xt_account':
            self.listAccount(self.currItem)
        elif category == 'xt_cats':
            self.listCategories(self.currItem)
        elif category == 'xt_list':
            self.listStreams(self.currItem)
        elif category == 'xt_series':
            self.listSeasons(self.currItem)
        elif category == 'xt_season':
            self.listEpisodes(self.currItem)
        elif category == 'xt_archive_channels':
            self.listArchiveChannels(self.currItem)
        elif category == 'xt_archive_days':
            self.listArchiveDays(self.currItem)
        elif category == 'xt_archive_day':
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
        if not self.currList and name is not None and category.startswith(('xt_', 'search')) and category != 'search_history':
            # a panel without movies / series in a category, an empty search: a marker instead of an empty list
            self.addMarker({'title': _("No items found")})
        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(GenericFolderWatchedHostMixin, CHostBase):
    def __init__(self):
        CHostBase.__init__(self, XtreamApiHost(), True, [])
        self.cachedRet = None
        self.refreshAfterWatchedFlagChange = False
        self.watchedHelper = IPTVWatchedHelper('xtream')

    def getSearchTypes(self):
        return [(_("Live channels"), 'live'), (_("Movies"), 'movie'), (_("Series"), 'series')]

    def withArticleContent(self, cItem):
        return bool(cItem.get('acc_id')) and cItem.get('category', '') in ITEM_KINDS
