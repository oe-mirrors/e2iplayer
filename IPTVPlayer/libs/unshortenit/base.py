#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from urllib.parse import urlsplit, urlparse, parse_qs, urljoin
except Exception:
    from urlparse import urlsplit, urlparse, parse_qs, urljoin

import re
import os
import time
from base64 import b64decode
import copy

try:
    import requests
except Exception:
    pass

from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import byteify, printExc, printDBG, GetCookieDir, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import SetIPTVPlayerLastHostError, GetIPTVSleep
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads

HTTP_HEADER = {
    "User-Agent": 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36',
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip,deflate,sdch",
    "Connection": "keep-alive",
    "Accept-Language": "nl-NL,nl;q=0.8,en-US;q=0.6,en;q=0.4",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}


def find_in_text(regex, text, flags=re.IGNORECASE | re.DOTALL):
    rec = re.compile(regex, flags=flags)
    match = rec.search(text)
    if not match:
        return False
    return match.group(1)


class UnshortenIt(object):

    _adfly_regex = r'adf\.ly|q\.gs|j\.gs|u\.bb|ay\.gy'
    _linkbucks_regex = r'linkbucks\.com|any\.gs|cash4links\.co|cash4files\.co|dyo\.gs|filesonthe\.net|goneviral\.com|megaline\.co|miniurls\.co|qqc\.co|seriousdeals\.net|theseblogs\.com|theseforums\.com|tinylinks\.co|tubeviral\.com|ultrafiles\.net|urlbeat\.net|whackyvidz\.com|yyv\.co'
    _adfocus_regex = r'adfoc\.us'
    _lnxlu_regex = r'lnx\.lu'
    _shst_regex = r'sh\.st|skiip\.me|clkmein\.com'
    _viidme_regex = r'viid\.me'
    _hrefli_regex = r'href\.li'
    _anonymz_regex = r'anonymz\.com'
    _iitvpl_regex = r'iiv\.pl'
    _short24_regex = r'short24\.pw'
    _rapidcrypt_regex = r'rapidcrypt\.net'
    _vcryptnet_regex = r'vcrypt\.net'

    _maxretries = 5

    _this_dir, _this_filename = os.path.split(__file__)
    _timeout = 10

    def __init__(self):
        self.cm = common()

    def unshorten(self, uri, type=None):

        domain = urlsplit(uri).netloc

        if not domain:
            return uri, "No domain found in URI!"

        had_google_outbound, uri = self._clear_google_outbound_proxy(uri)

        if re.search(self._adfly_regex, domain, re.IGNORECASE) or type == 'adfly':
            return self._unshorten_adfly(uri)
        if re.search(self._adfocus_regex, domain, re.IGNORECASE) or type == 'adfocus':
            return self._unshorten_adfocus(uri)
        if re.search(self._linkbucks_regex, domain, re.IGNORECASE) or type == 'linkbucks':
            return self._unshorten_linkbucks(uri)
        if re.search(self._lnxlu_regex, domain, re.IGNORECASE) or type == 'lnxlu':
            return self._unshorten_lnxlu(uri)
        if re.search(self._shst_regex, domain, re.IGNORECASE):
            return self._unshorten_shst(uri)
        if re.search(self._viidme_regex, domain, re.IGNORECASE):
            return self._unshorten_viidme(uri)
        if re.search(self._hrefli_regex, domain, re.IGNORECASE):
            return self._unshorten_hrefli(uri)
        if re.search(self._anonymz_regex, domain, re.IGNORECASE):
            return self._unshorten_anonymz(uri)
        if re.search(self._iitvpl_regex, domain, re.IGNORECASE):
            return self._unshorten_iivpl(uri)
        if re.search(self._short24_regex, domain, re.IGNORECASE):
            return self._unshorten_short24(uri)
        if re.search(self._rapidcrypt_regex, domain, re.IGNORECASE):
            return self._unshorten_rapidcrypt(uri)
        if re.search(self._vcryptnet_regex, domain, re.IGNORECASE):
            return self._unshorten_vcryptnet(uri)

        return uri, 200

    def unwrap_30x(self, uri, timeout=10):

        domain = urlsplit(uri).netloc
        self._timeout = timeout

        loop_counter = 0
        try:

            if loop_counter > 5:
                raise ValueError("Infinitely looping redirect from URL: '%s'" % (uri, ))

            # headers stop t.co from working so omit headers if this is a t.co link
            if domain == 't.co':
                r = requests.get(uri, timeout=self._timeout)
                return r.url, r.status_code
            # p.ost.im uses meta http refresh to redirect.
            if domain == 'p.ost.im':
                r = requests.get(uri, headers=HTTP_HEADER, timeout=self._timeout)
                uri = re.findall(r'.*url\=(.*?)\"\.*', r.text)[0]
                return uri, r.status_code
            else:

                while True:
                    try:
                        r = requests.head(uri, headers=HTTP_HEADER, timeout=self._timeout)
                    except (requests.exceptions.InvalidSchema, requests.exceptions.InvalidURL):
                        return uri, -1

                    retries = 0
                    if 'location' in r.headers and retries < self._maxretries:
                        r = requests.head(r.headers['location'])
                        uri = r.url
                        loop_counter += 1
                        retries = retries + 1
                    else:
                        return r.url, r.status_code
        except Exception as e:
            return uri, str(e)

    def _clear_google_outbound_proxy(self, url):
        '''
        So google proxies all their outbound links through a redirect so they can detect outbound links.
        This call strips them out if they are present.

        This is useful for doing things like parsing google search results, or if you're scraping google
        docs, where google inserts hit-counters on all outbound links.
        '''

        # This is kind of hacky, because we need to check both the netloc AND
        # part of the path. We could use urllib.parse.urlsplit, but it's
        # easier and just as effective to use string checks.
        if url.startswith("http://www.google.com/url?") or \
           url.startswith("https://www.google.com/url?"):

            qs = urlparse(url).query
            query = parse_qs(qs)

            if "q" in query:  # Google doc outbound links (maybe blogspot, too)
                return True, query["q"].pop()
            elif "url" in query:  # Outbound links from google searches
                return True, query["url"].pop()
            else:
                raise ValueError("Google outbound proxy URL without a target url ('%s')?" % url)
        return False, url

    def _unshorten_adfly(self, uri):

        try:
            r = requests.get(uri, headers=HTTP_HEADER, timeout=self._timeout)
            html = r.text
            ysmm = re.findall(r"var ysmm =.*\;?", html)

            if len(ysmm) > 0:
                ysmm = re.sub(r'var ysmm \= \'|\'\;', '', ysmm[0])

                left = ''
                right = ''

                for c in [ysmm[i:i + 2] for i in range(0, len(ysmm), 2)]:
                    left += c[0]
                    right = c[1] + right

                decoded_uri = b64decode(left.encode() + right.encode())[2:].decode()

                if re.search(r'go\.php\?u\=', decoded_uri):
                    decoded_uri = b64decode(re.sub(r'(.*?)u=', '', decoded_uri)).decode()

                return decoded_uri, r.status_code
            else:
                return uri, 'No ysmm variable found'

        except Exception as e:
            return uri, str(e)

    def _unshorten_linkbucks(self, uri):
        '''
        (Attempt) to decode linkbucks content. HEAVILY based on the OSS jDownloader codebase.
        This has necessidated a license change.

        '''

        r = requests.get(uri, headers=HTTP_HEADER, timeout=self._timeout)

        firstGet = time.time()

        baseloc = r.url

        if "/notfound/" in r.url or \
            "(>Link Not Found<|>The link may have been deleted by the owner|To access the content, you must complete a quick survey\.)" in r.text:
            return uri, 'Error: Link not found or requires a survey!'

        link = None

        content = r.text

        regexes = [
            r"<div id=\"lb_header\">.*?/a>.*?<a.*?href=\"(.*?)\".*?class=\"lb",
            r"AdBriteInit\(\"(.*?)\"\)",
            r"Linkbucks\.TargetUrl = '(.*?)';",
            r"Lbjs\.TargetUrl = '(http://[^<>\"]*?)'",
            r"src=\"http://static\.linkbucks\.com/tmpl/mint/img/lb\.gif\" /></a>.*?<a href=\"(.*?)\"",
            r"id=\"content\" src=\"([^\"]*)",
        ]

        for regex in regexes:
            if self.inValidate(link):
                link = find_in_text(regex, content)

        if self.inValidate(link):
            match = find_in_text(r"noresize=\"[0-9+]\" src=\"(http.*?)\"", content)
            if match:
                link = find_in_text(r"\"frame2\" frameborder.*?src=\"(.*?)\"", content)

        if self.inValidate(link):
            scripts = re.findall("(<script type=\"text/javascript\">[^<]+</script>)", content)
            if not scripts:
                return uri, "No script bodies found?"

            js = False

            for script in scripts:
                # cleanup
                script = re.sub(r"[\r\n\s]+\/\/\s*[^\r\n]+", "", script)
                if re.search(r"\s*var\s*f\s*=\s*window\['init'\s*\+\s*'Lb'\s*\+\s*'js'\s*\+\s*''\];[\r\n\s]+", script):
                    js = script

            if not js:
                return uri, "Could not find correct script?"

            token = find_in_text(r"Token\s*:\s*'([a-f0-9]{40})'", js)
            if not token:
                token = find_in_text(r"\?t=([a-f0-9]{40})", js)

            assert token

            authKeyMatchStr = r"A(?:'\s*\+\s*')?u(?:'\s*\+\s*')?t(?:'\s*\+\s*')?h(?:'\s*\+\s*')?K(?:'\s*\+\s*')?e(?:'\s*\+\s*')?y"
            l1 = find_in_text(r"\s*params\['" + authKeyMatchStr + r"'\]\s*=\s*(\d+?);", js)
            l2 = find_in_text(r"\s*params\['" + authKeyMatchStr + r"'\]\s*=\s?params\['" + authKeyMatchStr + r"'\]\s*\+\s*(\d+?);", js)

            if any([not l1, not l2, not token]):
                return uri, "Missing required tokens?"

            authkey = int(l1) + int(l2)

            p1_url = urljoin(baseloc, "/director/?t={tok}".format(tok=token))
            r2 = requests.get(p1_url, headers=HTTP_HEADER, timeout=self._timeout, cookies=r.cookies)

            p1_url = urljoin(baseloc, "/scripts/jquery.js?r={tok}&{key}".format(tok=token, key=l1))
            r2_1 = requests.get(p1_url, headers=HTTP_HEADER, timeout=self._timeout, cookies=r.cookies)

            time_left = 5.033 - (time.time() - firstGet)
            GetIPTVSleep().Sleep(max(time_left, 0))

            p3_url = urljoin(baseloc, "/intermission/loadTargetUrl?t={tok}&aK={key}&a_b=false".format(tok=token, key=str(authkey)))
            r3 = requests.get(p3_url, headers=HTTP_HEADER, timeout=self._timeout, cookies=r2.cookies)

            resp_json = json_loads(r3.text)
            if "Url" in resp_json:
                return resp_json['Url'], r3.status_code

        return "Wat", "wat"

    def inValidate(self, s):
        # Original conditional:
        # (s == null || s != null && (s.matches("[\r\n\t ]+") || s.equals("") || s.equalsIgnoreCase("about:blank")))
        if not s:
            return True

        if re.search("[\r\n\t ]+", s) or s.lower() == "about:blank":
            return True
        else:
            return False

    def _unshorten_adfocus(self, uri):
        orig_uri = uri
        try:

            r = requests.get(uri, headers=HTTP_HEADER, timeout=self._timeout)
            html = r.text

            adlink = re.findall("click_url =.*;", html)

            if len(adlink) > 0:
                uri = re.sub('^click_url = "|"\;$', '', adlink[0])
                if re.search(r'http(s|)\://adfoc\.us/serve/skip/\?id\=', uri):

                    http_header = copy.copy(HTTP_HEADER)
                    http_header["Host"] = "adfoc.us"
                    http_header["Referer"] = orig_uri

                    r = requests.get(uri, headers=http_header, timeout=self._timeout)

                    uri = r.url
                return uri, r.status_code
            else:
                return uri, 'No click_url variable found'
        except Exception as e:
            return uri, str(e)

    def _unshorten_lnxlu(self, uri):
        try:
            r = requests.get(uri, headers=HTTP_HEADER, timeout=self._timeout)
            html = r.text

            code = re.findall('/\?click\=(.*)\."', html)

            if len(code) > 0:
                payload = {'click': code[0]}
                r = requests.get('http://lnx.lu/', params=payload, headers=HTTP_HEADER, timeout=self._timeout)
                return r.url, r.status_code
            else:
                return uri, 'No click variable found'
        except Exception as e:
            return uri, str(e)

    def _unshorten_shst(self, uri):
        try:
            sts, html = self.cm.getPage(uri, {'header': HTTP_HEADER})

            session_id = re.findall(r'sessionId\:(.*?)\"\,', html)
            if len(session_id) > 0:
                session_id = re.sub(r'\s\"', '', session_id[0])

                http_header = copy.copy(HTTP_HEADER)
                http_header["Content-Type"] = "application/x-www-form-urlencoded"
                http_header["Host"] = "sh.st"
                http_header["Referer"] = uri
                http_header["Origin"] = "http://sh.st"
                http_header["X-Requested-With"] = "XMLHttpRequest"

                GetIPTVSleep().Sleep(5)

                payload = {'adSessionId': session_id, 'callback': 'c'}
                sts, response = self.cm.getPage('http://sh.st/shortest-url/end-adsession', {'header': http_header}, payload)

                resp_uri = json_loads(response[6:-2])['destinationUrl']
                if resp_uri is not None:
                    uri = resp_uri

            return uri, 'OK'

        except Exception as e:
            printExc()
            return uri, str(e)

    def _unshorten_iivpl(self, baseUri):
        baseUri = strwithmeta(baseUri)
        ref = baseUri.meta.get('Referer', baseUri)
        USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0'
        HTTP_HEADER = {'User-Agent': USER_AGENT, 'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'Referer': ref}
        HTTP_HEADER_AJAX = {'User-Agent': USER_AGENT, 'Accept': '*/*', 'Accept-Encoding': 'gzip, deflate', 'Referer': baseUri, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With': 'XMLHttpRequest'}

        COOKIE_FILE = GetCookieDir('iit.pl')
        tries = 0
        retUri, retSts = '', 'KO'
        while tries < 2 and retSts != 'OK':
            tries += 1
            rm(COOKIE_FILE)
            try:
                params = {'header': HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIE_FILE}

                sts, data = self.cm.getPage(baseUri, params)

                sts, headers = self.cm.getPage('http://iiv.pl/modules/system/assets/js/framework.js', params)

                headers = self.cm.ph.getDataBeetwenMarkers(headers, 'headers', '}')[1]
                headers = re.compile('''['"]([^'^"]+?)['"]''').findall(headers)
                salt = self.cm.ph.getSearchGroups(data, '''data\-salt="([^"]+?)"''')[0]
                time = self.cm.ph.getSearchGroups(data, '''data\-time="([^"]+?)"''')[0]
                action = self.cm.ph.getSearchGroups(data, '''data\-action="([^"]+?)"''')[0]
                banner = self.cm.ph.getSearchGroups(data, '''data\-banner="([^"]+?)"''')[0]
                component = self.cm.ph.getSearchGroups(data, '''data\-component="([^"]+?)"''')[0]
                if tries > 1:
                    GetIPTVSleep().Sleep(int(time))

                sts, partials = self.cm.getPage('http://iiv.pl/themes/cutso/assets/javascript/shortcut/shortcut.js', params)
                partials = self.cm.ph.getDataBeetwenMarkers(partials, 'update:', '}')[1]
                partials = self.cm.ph.getSearchGroups(partials, '''['"]([^'^"]+?)['"]''')[0]
                if partials == '':
                    partials = 'shortcut/link_show'
                for header in headers:
                    if 'HANDLER' in header:
                        HTTP_HEADER_AJAX[header] = action
                    elif 'PARTIALS' in header:
                        HTTP_HEADER_AJAX[header] = partials

                post_data = {'salt': salt, 'banner': banner, 'blocker': 0}
                params['header'] = HTTP_HEADER_AJAX
                sts, data = self.cm.getPage(baseUri, params, post_data)
                data = json_loads(data)
                printDBG(">>>%s<<<" % data)
                uri = self.cm.ph.getSearchGroups(data[partials], '''href="(https?://[^"]+?)"''')[0]
                retUri, retSts = uri, 'OK'

            except Exception as e:
                retUri, retSts = baseUri, str(e)
                printExc()

        return retUri, retSts

    def _unshorten_viidme(self, uri):
        try:
            sts, html = self.cm.getPage(uri, {'header': HTTP_HEADER})

            session_id = re.findall(r'sessionId\:(.*?)\"\,', html)
            if len(session_id) > 0:
                session_id = re.sub(r'\s\"', '', session_id[0])

                http_header = copy.copy(HTTP_HEADER)
                http_header["Content-Type"] = "application/x-www-form-urlencoded"
                http_header["Host"] = "viid.me"
                http_header["Referer"] = uri
                http_header["Origin"] = "http://viid.me"
                http_header["X-Requested-With"] = "XMLHttpRequest"

                GetIPTVSleep().Sleep(5)

                payload = {'adSessionId': session_id, 'callback': 'c'}
                sts, response = self.cm.getPage('http://viid.me/shortest-url/end-adsession', {'header': http_header}, payload)

                resp_uri = json_loads(response[6:-2])['destinationUrl']
                if resp_uri is not None:
                    uri = resp_uri

            return uri, 'OK'

        except Exception as e:
            printExc()
            return uri, str(e)

    def _unshorten_short24(self, uri):
        try:
            sts, data = self.cm.getPage(uri, {'header': HTTP_HEADER})
            uri = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, '''window\.location\s*?=\s*?['"]([^'^"]+?)['"]''')[0], self.cm.getBaseUrl(self.cm.meta['url']))
            return uri, 'OK'
        except Exception as e:
            printExc()
            return uri, str(e)

    def _unshorten_rapidcrypt(self, uri):
        try:
            COOKIE_FILE = GetCookieDir('rapidcrypt.net')
            params = {'header': HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIE_FILE}
            params['cloudflare_params'] = {'cookie_file': COOKIE_FILE, 'User-Agent': HTTP_HEADER['User-Agent']}
            sts, data = self.cm.getPageCFProtection(uri, params)
            uri = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'push_button'), ('</a', '>'))[1]
            printDBG(uri)
            uri = self.cm.ph.getSearchGroups(uri, '''href=([^>^\s]+?)[>\s]''')[0]
            if uri.startswith('"'):
                uri = self.cm.ph.getSearchGroups(uri, '"([^"]+?)"')[0]
            elif uri.startswith("'"):
                uri = self.cm.ph.getSearchGroups(uri, "'([^']+?)'")[0]

            uri = self.cm.getFullUrl(uri, self.cm.getBaseUrl(self.cm.meta['url']))
            return uri, 'OK'
        except Exception as e:
            printExc()
            return uri, str(e)

    def _unshorten_vcryptnet(self, uri):
        try:
            COOKIE_FILE = GetCookieDir('vcrypt.net')
            params = {'header': HTTP_HEADER, 'use_cookie': True, 'load_cookie': True, 'save_cookie': True, 'cookiefile': COOKIE_FILE}
            params['cloudflare_params'] = {'cookie_file': COOKIE_FILE, 'User-Agent': HTTP_HEADER['User-Agent']}
            sts, data = self.cm.getPageCFProtection(uri, params)
            uri = self.cm.ph.getDataBeetwenNodes(data, ('<a', '>', 'push_button'), ('</a', '>'))[1]

            printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            printDBG(self.cm.meta['url'])
            printDBG("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            uri = self.cm.meta['url']

            uri = self.cm.getFullUrl(uri, self.cm.getBaseUrl(self.cm.meta['url']))
            return uri, 'OK'
        except Exception as e:
            printExc()
            return uri, str(e)

    def _unshorten_hrefli(self, uri):
        try:
            # Extract url from query
            parsed_uri = urlparse(uri)
            extracted_uri = parsed_uri.query
            if not extracted_uri:
                return uri, 200
            # Get url status code
            r = requests.head(extracted_uri, headers=HTTP_HEADER, timeout=self._timeout)
            return r.url, r.status_code
        except Exception as e:
            return uri, str(e)

    def _unshorten_anonymz(self, uri):
        # For the moment they use the same system as hrefli
        return self._unshorten_hrefli(uri)


def unwrap_30x_only(uri, timeout=10):
    unshortener = UnshortenIt()
    uri, status = unshortener.unwrap_30x(uri, timeout=timeout)
    return uri, status


def unshorten_only(uri, type=None, timeout=10):
    unshortener = UnshortenIt()
    uri, status = unshortener.unshorten(uri, type=type)
    return uri, status


def unshorten(uri, type=None, timeout=10):
    unshortener = UnshortenIt()
    uri, status = unshortener.unshorten(uri, type=type)
    if status == 200:
        uri, status = unshortener.unwrap_30x(uri, timeout=timeout)
    return uri, status
