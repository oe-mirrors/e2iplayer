# -*- coding: utf-8 -*-
# Last Modified: 26.09.2026
###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, GetIPTVPlayerVersion
from Plugins.Extensions.IPTVPlayer.components.configbase import COLORS_DEFINITONS
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_str
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
try:
    import json
except Exception:
    import simplejson as json
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
###################################################

###################################################
# Config options for HOST
###################################################
config.plugins.iptvplayer.e2iplayerinfo_currversion_color = ConfigSelection(default="#008000", choices=COLORS_DEFINITONS)
config.plugins.iptvplayer.e2iplayerinfo_merge_prs = ConfigYesNo(default=True)


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry(_("The color of the current version"), config.plugins.iptvplayer.e2iplayerinfo_currversion_color))
    optionList.append(getConfigListEntry(_("Combine pull request merges with their commit"), config.plugins.iptvplayer.e2iplayerinfo_merge_prs))
    return optionList
###################################################


# GitHub allows 60 anonymous API calls per hour and IP, so responses are kept for a
# few minutes; the module stays loaded while E2iPlayer runs.
CACHE_TTL = 300
_API_CACHE = {}

MERGE_PR_RE = re.compile(r'^Merge pull request #(\d+) from (\S+)')


def gettytul():
    return 'E2iPlayer info'


def markdownToText(text):
    # GitHub markdown (wiki pages, issues, release notes) to plain text for the article view
    if not isinstance(text, type(u'')):
        text = text.decode('utf-8', 'ignore')
    text = text.replace('\r\n', '\n')
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)

    def _link(m):
        if m.group(1).strip() == m.group(2).strip():
            return m.group(2)
        return '%s (%s)' % (m.group(1), m.group(2))
    text = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', _link, text)
    text = re.sub(r'(?m)^```.*$', '', text)
    text = re.sub(r'(?m)^\s*#{1,6}\s*', '', text)
    text = re.sub(r'(?m)^(\s*)[*+]\s+', r'\1- ', text)
    text = re.sub(r'(?m)^\s*(-{3,}|\*{3,}|_{3,})\s*$', '-' * 20, text)
    text = re.sub(r'(?m)^>\s?', '', text)
    text = text.replace('**', '').replace('__', '').replace('`', '')
    # emoji and symbols the skin fonts usually lack
    text = re.sub(u'[⌀-⏿☀-➿⬀-⯿️‍]', '', text)
    text = u''.join(c for c in text if ord(c) < 0xd800 or 0xe000 <= ord(c) < 0x10000)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return ensure_str(text.strip())


class E2iPlayerInfo(CBaseHostClass):
    REPO = 'oe-mirrors/e2iplayer'
    BRANCH = 'python3'
    API_URL = 'https://api.github.com/repos/%s/' % REPO
    WIKI_URL = 'https://github.com/%s/wiki/' % REPO
    WIKI_RAW_URL = 'https://raw.githubusercontent.com/wiki/%s/' % REPO
    COMMITS_PER_PAGE = 40
    ITEMS_PER_PAGE = 30

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'e2iplayerinfo', 'cookie': 'e2iplayerinfo.cookie'})
        self.DEFAULT_ICON_URL = 'https://github.githubassets.com/assets/GitHub-Mark-ea2971cee799.png'
        self.HEADER = {'User-Agent': common.HOST, 'Accept': 'application/vnd.github+json'}
        # 403 = API rate limit, 404 = no tag for the installed version; both carry a JSON 'message'
        self.defaultParams = {'header': self.HEADER, 'ignore_http_code_ranges': [(403, 404)]}
        self.MAIN_URL = 'https://github.com/'
        self.MAIN_CAT_TAB = [
                             {'category': 'new_commits', 'title': _('New since installed version'), },
                             {'category': 'commits', 'title': _('Commits'), },
                             {'category': 'releases', 'title': _('Releases'), },
                             {'category': 'issues', 'title': _('Open issues'), },
                             {'category': 'pulls', 'title': _('Open pull requests'), },
                             {'category': 'wiki', 'title': _('Wiki'), },
                             {'category': 'tutorial', 'title': _('Tutorials'), }
                            ]

        self.TUTORIALS_TAB = [{'title': _('Services management'), 'url': 'https://www.youtube.com/watch?v=pG-_csh2TDk'},
                             {'title': _('%s - service overview') % 'https://www.rte.ie/player/', 'url': 'https://www.youtube.com/watch?v=IhC8m8K1jkg'},
                             {'title': _('%s subtitles download - how to') % _('[en]'), 'url': 'https://www.youtube.com/watch?v=ZO6w6Pr5z_4'},
                             {'title': _('%s subtitles download - how to') % _('[pl]'), 'url': 'https://www.youtube.com/watch?v=3onH5vxlDcg'},
                             {'title': _('%s - subtitles provider') % 'https://www.prijevodi-online.org/', 'url': 'https://www.youtube.com/watch?v=lb8QvViUYq4'},
                            ]

        self.WIKI_TAB = [{'title': _('Install E2iPlayer'), 'wiki_page': 'Install'},
                         {'title': _('Create debug logs'), 'wiki_page': 'How-to-create-debug-logs'},
                         {'title': _('Solve Cloudflare, hCaptcha and reCAPTCHA with MyE2i'), 'wiki_page': 'Solve-Cloudflare-hCaptcha-reCAPTCHA-with-MyE2i'},
                         {'title': _('Solve Google reCAPTCHA v2 with My JDownloader'), 'wiki_page': 'Solve-Google-reCAPTCHA-v2'},
                         {'title': _('For developers'), 'category': 'wiki_dev', 'type': 'dir'},
                        ]

        self.WIKI_DEV_TAB = [{'title': 'Index on how to create hosts and handle urlparser', 'wiki_page': 'Index-on-how-to-create-hosts-and-handle-urlparser'},
                             {'title': 'Adding a new host in E2iplayer', 'wiki_page': 'Adding-a-new-host-in-E2iplayer'},
                             {'title': 'A more complex example of host: building item lists from HTML', 'wiki_page': 'A-more-complex-example-of-host-:-building-item-lists-from-HTML'},
                             {'title': 'Other example of host: config options, cookies, cloudflare protection and captchas', 'wiki_page': 'Other-example-of-host:-config-options,-cookies,-cloudflare-protection-and-captchas'},
                             {'title': 'Building a search function', 'wiki_page': 'Building-a-search-function'},
                             {'title': 'Understanding Urlparser', 'wiki_page': 'Understanding-Urlparser'},
                             {'title': 'Another new server in urlparser: typical strategies', 'wiki_page': 'Another-new-server-in-urlparser:-typical-strategies'},
                            ]

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getCachedPage(self, url):
        now = time.time()
        cached = _API_CACHE.get(url)
        if cached and now - cached[0] < CACHE_TTL:
            printDBG("getCachedPage cache hit [%s]" % url)
            return True, cached[1]
        sts, data = self.getPage(url)
        if not sts:
            return sts, data
        # never keep a rate-limit answer, the next call after the reset has to go out
        if 'rate limit' not in data[:300].lower():
            for key in [k for k, v in _API_CACHE.items() if now - v[0] >= CACHE_TTL]:
                del _API_CACHE[key]
            _API_CACHE[url] = (now, data)
        return sts, data

    def getApiJson(self, path):
        sts, data = self.getCachedPage(self.API_URL + path)
        if not sts:
            return None
        try:
            return json.loads(data)
        except Exception:
            printExc()
            return None

    def addApiError(self, data):
        message = data.get('message', '') if isinstance(data, dict) else ''
        self.addMarker({'title': _('GitHub API error'), 'desc': ensure_str(message)})

    def formatDate(self, value):
        return ensure_str(value or '').replace('T', ' ')[:16]

    def getInstalledState(self):
        # Every version.py bump on python3 gets a v<IPTV_VERSION> tag (tag_release.yml),
        # so comparing that tag with the branch gives the installed commit and the distance.
        version = GetIPTVPlayerVersion()
        data = self.getApiJson('compare/v%s...%s' % (version, self.BRANCH))
        if not isinstance(data, dict) or 'base_commit' not in data:
            printDBG("getInstalledState no tag for version[%s]: %s" % (version, data))
            return {'version': version, 'sha': '', 'status': '', 'ahead_by': 0, 'commits': []}
        return {'version': version,
                'sha': ensure_str(data.get('base_commit', {}).get('sha', '')),
                'status': ensure_str(data.get('status', '')),
                'ahead_by': data.get('ahead_by', 0),
                'commits': data.get('commits', [])}

    def addInstalledMarker(self, state):
        version = state['version']
        status = state['status']
        if status == 'identical':
            title = _('Installed: v%s - up to date') % version
        elif status == 'ahead':
            title = _('Installed: v%s - %d commits behind %s') % (version, state['ahead_by'], self.BRANCH)
        elif status:
            title = _('Installed: v%s') % version
        else:
            title = _('Installed: v%s - no matching release tag (local build?)') % version
        self.addMarker({'title': title, 'desc': ''})

    def addCommitItems(self, commits, installedSha, hiddenShas):
        # commits newest first; with the merge option a "Merge pull request #N" commit
        # takes over the message of the PR commit it merged (its 2nd parent), which is
        # then left out - also on the next page, hence the returned hidden list
        mergePrs = config.plugins.iptvplayer.e2iplayerinfo_merge_prs.value
        color = config.plugins.iptvplayer.e2iplayerinfo_currversion_color.value
        bySha = dict((ensure_str(c.get('sha', '')), c) for c in commits)
        hidden = set(hiddenShas)
        for item in commits:
            try:
                sha = ensure_str(item.get('sha', ''))
                if sha in hidden:
                    hidden.discard(sha)
                    continue
                commit = item.get('commit', {})
                author = commit.get('author', {})
                message = ensure_str(commit.get('message', '')).strip()
                title, _sep, body = message.partition('\n')
                title = title.strip()
                body = body.strip()
                shas = [sha]
                match = MERGE_PR_RE.match(title)
                parents = item.get('parents', [])
                if mergePrs and match and len(parents) == 2:
                    prSha = ensure_str(parents[1].get('sha', ''))
                    shas.append(prSha)
                    prItem = bySha.get(prSha)
                    if prItem is not None:
                        prMessage = ensure_str(prItem.get('commit', {}).get('message', '')).strip()
                    else:
                        prMessage = body
                    hidden.add(prSha)
                    prTitle, _sep, body = prMessage.partition('\n')
                    title = 'PR #%s: %s' % (match.group(1), prTitle.strip())
                    body = body.strip()
                    message = title + '\n\n' + body
                info = '%s | %s | %s' % (self.formatDate(author.get('date', '')), ensure_str(author.get('name', '')), sha[:9])
                params = {'title': title, 'url': ensure_str(item.get('html_url', '')), 'desc': (info + '\n' + body).strip(),
                          'article': 'text', 'article_text': info + '\n\n' + message + '\n\n' + ensure_str(item.get('html_url', ''))}
                if installedSha and installedSha in shas:
                    params['text_color'] = color
                    params['desc'] = _('Installed version') + '\n' + params['desc']
                self.addArticle(params)
            except Exception:
                printExc()
        return list(hidden)

    def listCommits(self, cItem):
        printDBG("listCommits [%s]" % cItem)

        page = cItem.get('page', 1)
        if page == 1:
            state = self.getInstalledState()
            self.addInstalledMarker(state)
            installedSha = state['sha']
        else:
            installedSha = cItem.get('installed_sha', '')

        data = self.getApiJson('commits?sha=%s&per_page=%d&page=%d' % (self.BRANCH, self.COMMITS_PER_PAGE, page))
        if not isinstance(data, list):
            self.addApiError(data)
            return

        hidden = self.addCommitItems(data, installedSha, cItem.get('hidden_shas', []))
        if len(data) >= self.COMMITS_PER_PAGE:
            params = dict(cItem)
            params.update({'installed_sha': installedSha, 'hidden_shas': hidden})
            self.apply_next_page(params, page + 1)

    def listNewCommits(self, cItem):
        printDBG("listNewCommits [%s]" % cItem)
        state = self.getInstalledState()
        self.addInstalledMarker(state)
        if not state['status']:
            return
        commits = list(reversed(state['commits']))
        if not commits:
            return
        if state['ahead_by'] > len(commits):
            self.addMarker({'title': _('Only the %d oldest new commits are shown') % len(commits), 'desc': ''})
        self.addCommitItems(commits, '', [])

    def listReleases(self, cItem):
        printDBG("listReleases [%s]" % cItem)
        page = cItem.get('page', 1)
        data = self.getApiJson('releases?per_page=%d&page=%d' % (self.ITEMS_PER_PAGE, page))
        if not isinstance(data, list):
            self.addApiError(data)
            return

        installedTag = 'v' + GetIPTVPlayerVersion()
        color = config.plugins.iptvplayer.e2iplayerinfo_currversion_color.value
        for item in data:
            try:
                tag = ensure_str(item.get('tag_name', ''))
                name = ensure_str(item.get('name', '')) or tag
                date = self.formatDate(item.get('published_at', ''))
                body = markdownToText(item.get('body', '') or '').replace('Changes in this release\n', '')
                url = ensure_str(item.get('html_url', ''))
                params = {'title': '%s  (%s)' % (name, date[:10]), 'url': url, 'desc': body,
                          'article': 'text', 'article_text': date + '\n\n' + body + '\n\n' + url}
                if tag == installedTag:
                    params['text_color'] = color
                    params['desc'] = _('Installed version') + '\n' + params['desc']
                self.addArticle(params)
            except Exception:
                printExc()

        if len(data) >= self.ITEMS_PER_PAGE:
            self.apply_next_page(cItem, page + 1)

    def listIssues(self, cItem, pulls):
        printDBG("listIssues [%s] pulls[%s]" % (cItem, pulls))
        page = cItem.get('page', 1)
        # the issues endpoint returns pull requests as well, the pulls one only those
        endpoint = 'pulls' if pulls else 'issues'
        data = self.getApiJson('%s?state=open&per_page=%d&page=%d' % (endpoint, self.ITEMS_PER_PAGE, page))
        if not isinstance(data, list):
            self.addApiError(data)
            return

        for item in data:
            try:
                if not pulls and 'pull_request' in item:
                    continue
                number = item.get('number', 0)
                title = ensure_str(item.get('title', ''))
                if item.get('draft'):
                    title = '[%s] %s' % (_('Draft'), title)
                info = '%s | %s' % (self.formatDate(item.get('created_at', '')), ensure_str(item.get('user', {}).get('login', '')))
                if 'comments' in item:
                    info += ' | %s: %d' % (_('Comments'), item.get('comments', 0))
                body = markdownToText(item.get('body', '') or '')
                params = {'title': '#%d %s' % (number, title), 'url': ensure_str(item.get('html_url', '')), 'desc': (info + '\n' + body).strip(),
                          'article': 'issue', 'issue_number': number, 'article_text': info + '\n\n' + body}
                self.addArticle(params)
            except Exception:
                printExc()

        if len(data) >= self.ITEMS_PER_PAGE:
            self.apply_next_page(cItem, page + 1)
        elif not self.currList:
            self.addMarker({'title': _('Nothing open'), 'desc': ''})

    def getIssueComments(self, number):
        data = self.getApiJson('issues/%d/comments?per_page=50' % number)
        if not isinstance(data, list):
            return ''
        text = ''
        for item in data:
            text += '\n\n%s\n%s | %s\n\n%s' % ('-' * 20, self.formatDate(item.get('created_at', '')),
                                             ensure_str(item.get('user', {}).get('login', '')), markdownToText(item.get('body', '') or ''))
        return text

    def getWikiText(self, page):
        sts, data = self.getCachedPage(self.WIKI_RAW_URL + page + '.md')
        if not sts or not data or data.startswith('404'):
            return _('Could not load the wiki page.')
        return markdownToText(data)

    def getArticleContent(self, cItem):
        printDBG("getArticleContent [%s]" % cItem)
        kind = cItem.get('article', '')
        if kind == 'wiki':
            url = self.WIKI_URL + cItem['wiki_page']
            text = self.getWikiText(cItem['wiki_page']) + '\n\n' + url
        elif kind == 'issue':
            text = cItem.get('article_text', '') + self.getIssueComments(cItem['issue_number']) + '\n\n' + cItem.get('url', '')
        else:
            text = cItem.get('article_text', '')
        return [{'title': cItem.get('title', ''), 'text': text, 'images': [{'title': '', 'url': self.DEFAULT_ICON_URL}]}]

    def listWiki(self, cItem, tab):
        for item in tab:
            params = dict(cItem)
            params.update(item)
            params['name'] = 'category'
            if item.get('type') == 'dir':
                self.addDir(params)
            else:
                params.update({'article': 'wiki', 'url': self.WIKI_URL + item['wiki_page'], 'desc': self.WIKI_URL + item['wiki_page']})
                self.addArticle(params)

    def getLinksForVideo(self, cItem):
        printDBG("getLinksForVideo [%s]" % cItem)
        return self.up.getVideoLinkExt(cItem['url'])

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')

        printDBG("handleService: |||||||||||||||||||||||||||||||||||| name[%s], category[%s] " % (name, category))
        self.currList = []

    # MAIN MENU
        if name is None:
            self.listsTab(self.MAIN_CAT_TAB, {'name': 'category'})
        elif category == 'new_commits':
            self.listNewCommits(self.currItem)
        elif category == 'commits':
            self.listCommits(self.currItem)
        elif category == 'releases':
            self.listReleases(self.currItem)
        elif category == 'issues':
            self.listIssues(self.currItem, False)
        elif category == 'pulls':
            self.listIssues(self.currItem, True)
        elif category == 'wiki':
            self.listWiki(self.currItem, self.WIKI_TAB)
        elif category == 'wiki_dev':
            self.listWiki(self.currItem, self.WIKI_DEV_TAB)
        elif category == 'tutorial':
            self.listsTab(self.TUTORIALS_TAB, self.currItem, 'video')
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, E2iPlayerInfo(), True, [])

    def withArticleContent(self, cItem):
        return 'article' in cItem
