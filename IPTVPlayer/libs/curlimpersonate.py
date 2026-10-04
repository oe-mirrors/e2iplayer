# -*- coding: utf-8 -*-
# curl-impersonate backend for pCommon.getPage(..., {'impersonate': True}).
#
# Some Cloudflare setups only look at the TLS / HTTP2 fingerprint: urllib, curl and
# pycurl get the "Just a moment" challenge (HTTP 403), a client with Chrome's
# fingerprint gets the page - without any cookie or browser. curl-impersonate
# (lexiforest/curl-impersonate, a full curl command line tool) does exactly that:
# "--impersonate chrome150" sets Chrome's TLS settings, HTTP/2 settings and its default
# headers (User-Agent, Accept, Accept-Language, Accept-Encoding, sec-ch-ua...).
#
# This module only builds the command line, runs the binary and parses its answer.
# No enigma2 imports - covered by tests/test_impersonate.py. Python 2.7 compatible.
import math
import os
import subprocess
import tempfile
import time

try:
    from urllib.parse import urljoin
except ImportError:  # Python 2
    from urlparse import urljoin

# where the box has the binary (the OE-A recipe installs a static build to /usr/bin)
BINARY_CANDIDATES = ['/usr/bin/curl-impersonate', '/usr/local/bin/curl-impersonate']
BINARY_NAME = 'curl-impersonate'

# browser profiles, newest first: an older binary that does not know the first one
# rejects the option and the next one is tried (the working one is remembered)
PROFILES = ['chrome150', 'chrome146', 'chrome145', 'chrome142', 'chrome136', 'chrome131']

# request headers the impersonated browser sends itself - they belong to the fingerprint,
# a host's own values (Firefox User-Agent, Accept-Encoding: text, ...) would give it away.
# DNT / Connection / Keep-Alive: Chrome does not send them (HTTP/2 forbids the last two),
# Content-Length: curl sets it for the POST body
DROPPED_HEADERS = ('user-agent', 'accept', 'accept-language', 'accept-encoding', 'dnt', 'connection',
                   'keep-alive', 'content-length')
DROPPED_HEADER_PREFIXES = ('sec-ch-',)

DEFAULT_TIMEOUT = 30  # seconds: connection timeout and "stalled" time when the caller gives none
MAX_TIME = 300  # seconds: hard limit for one request
MAX_REDIRECTS = 10  # like urllib
CA_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'

WRITEOUT_MARKER = '@@E2I-IMPERSONATE@@'
# %{stderr} switches the -w output to stderr (curl >= 7.63), stdout carries the body only
WRITEOUT = '%{stderr}\n' + WRITEOUT_MARKER + ' %{http_code} %{url_effective}\n'

# curl exit codes that may mean "unknown --impersonate target": 2 (failed init),
# 43 (bad function argument), 48 (unknown option)
_BAD_TARGET_CODES = (2, 43, 48)


class ImpersonateUnavailable(Exception):
    """the binary is missing or cannot run on this box - use the normal HTTP path"""


_state = {'binary': None, 'profile': None}


def resetCache():
    _state['binary'] = None
    _state['profile'] = None


def _isExecutable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def getImpersonateBinary(candidates=None):
    """path of the curl-impersonate binary or '' (cached for the session)"""
    if _state['binary'] is None:
        found = ''
        paths = list(candidates or BINARY_CANDIDATES)
        for directory in os.environ.get('PATH', '').split(os.pathsep):
            directory = directory.strip('"')
            if directory:
                paths.append(os.path.join(directory, BINARY_NAME))
        for path in paths:
            if _isExecutable(path):
                found = path
                break
        _state['binary'] = found
    return _state['binary']


def markBinaryUnusable():
    _state['binary'] = ''


def getProfiles():
    """profiles to try, the one that worked before first"""
    if _state['profile']:
        return [_state['profile']] + [p for p in PROFILES if p != _state['profile']]
    return list(PROFILES)


def filterHeaders(headers):
    """the caller's headers as "Name: value" lines for -H, without the ones the browser sends itself"""
    out = []
    for key, value in (headers or {}).items():
        name = str(key).strip()
        lname = name.lower()
        if not name or lname in DROPPED_HEADERS or lname.startswith(DROPPED_HEADER_PREFIXES):
            continue
        if value is None:
            continue
        value = str(value)
        if '\r' in value or '\n' in value or '\r' in name or '\n' in name or ':' in name:
            continue  # would inject another header line
        if value == '':
            out.append('%s;' % name)  # curl: "Name;" sends an empty header, "Name:" would remove it
        else:
            out.append('%s: %s' % (name, value))
    return out


def cookieItemsString(cookieItems):
    return '; '.join('%s=%s' % (k, v) for k, v in (cookieItems or {}).items())


def prepareCookieFile(src, dst):
    """copy pCommon's cookie file (MozillaCookieJar format) for curl: Python writes session
    cookies with an empty "expires" field, curl drops such lines - it wants 0 there.
    Returns False when there is nothing to load."""
    try:
        with open(src, 'rb') as f:
            lines = f.read().decode('utf-8', 'replace').splitlines()
    except (IOError, OSError):
        return False
    out = []
    for line in lines:
        fields = line.split('\t')
        if len(fields) == 7 and fields[4] == '' and (not line.startswith('#') or line.startswith('#HttpOnly_')):
            fields[4] = '0'
            line = '\t'.join(fields)
        out.append(line)
    with open(dst, 'wb') as f:
        f.write(('\n'.join(out) + '\n').encode('utf-8'))
    return True


def normalizeCookieFile(path):
    """make the cookie file curl wrote (-c) readable by every MozillaCookieJar: curl marks HttpOnly
    cookies with a "#HttpOnly_" domain prefix (a comment line for Python < 3.13.16 and py2, so e.g.
    cf_clearance got lost) and writes 0 as "expires" of session cookies (= expired for Python)"""
    try:
        with open(path, 'rb') as f:
            lines = f.read().decode('utf-8', 'replace').splitlines()
    except (IOError, OSError):
        return False
    out = []
    for line in lines:
        fields = line.split('\t')
        if len(fields) == 7 and (not line.startswith('#') or line.startswith('#HttpOnly_')):
            if fields[0].startswith('#HttpOnly_'):
                fields[0] = fields[0][len('#HttpOnly_'):]
            if fields[4] == '0':
                fields[4] = ''
            line = '\t'.join(fields)
        out.append(line)
    with open(path, 'wb') as f:
        f.write(('\n'.join(out) + '\n').encode('utf-8'))
    return True


def buildArgs(binary, profile, url, headers=None, cookieIn='', cookieOut='', cookieString='', dataFile='',
              noRedirection=False, timeout=None, proxy='', insecure=False, cacert='', ipv4Only=False, headerFile='',
              outFile='', ipv6Only=False):
    """outFile: write the body to this file (downloads) instead of stdout.
    ipv4Only / ipv6Only: curl -4 / -6; ipv4Only wins when both are set"""
    # whole seconds: --speed-time takes an integer only (a host's 'timeout': 7.5 would make curl exit 2)
    try:
        timeout = int(math.ceil(float(timeout))) if timeout else DEFAULT_TIMEOUT
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT
    timeout = timeout if timeout > 0 else DEFAULT_TIMEOUT
    # --compressed: the profile sends Chrome's "Accept-Encoding: gzip, deflate, br, zstd", but the curl
    # tool only undoes a Content-Encoding with this option (the release's curl_chrome*.bat / .sh wrappers
    # pass it too) - without it the body is zstd / brotli / gzip bytes. It does not change the request
    # (same header, same fingerprint) and only decodes what the server marked with Content-Encoding.
    args = [binary, '--impersonate', profile, '--compressed', '-s', '-S',
            '--connect-timeout', str(timeout), '--speed-time', str(timeout), '--speed-limit', '10',
            '--max-time', str(max(MAX_TIME, timeout)),
            '-D', headerFile, '-o', outFile or '-', '-w', WRITEOUT]
    if not noRedirection:
        args.extend(['-L', '--max-redirs', str(MAX_REDIRECTS)])
    for line in filterHeaders(headers):
        args.extend(['-H', line])
    if cookieIn:
        args.extend(['-b', cookieIn])
    if cookieString:
        args.extend(['-b', cookieString])
    if cookieOut:
        args.extend(['-c', cookieOut])
    if dataFile:
        args.extend(['--data-binary', '@' + dataFile])
    if proxy:
        args.extend(['-x', proxy])
    if insecure:
        args.append('-k')
    elif cacert:
        args.extend(['--cacert', cacert])
    if ipv4Only:
        args.append('-4')
    elif ipv6Only:
        args.append('-6')
    args.extend(['--', url])
    return args


def parseHeaderFile(text):
    """-D output -> list of (status, {lower name: value}) blocks, one per response
    (redirects, 100 Continue, proxy CONNECT)"""
    blocks = []
    current = None
    for line in (text or '').splitlines():
        line = line.rstrip('\r')
        if line.startswith('HTTP/'):
            parts = line.split(None, 2)
            try:
                status = int(parts[1])
            except (IndexError, ValueError):
                status = 0
            current = (status, {})
            blocks.append(current)
        elif current is not None and ':' in line:
            name, value = line.split(':', 1)
            name = name.strip().lower()
            value = value.strip()
            if name in current[1]:
                current[1][name] = current[1][name] + ', ' + value
            else:
                current[1][name] = value
    return blocks


def finalResponse(blocks, url):
    """status, headers and final URL of the last real response (when -w gave nothing)"""
    real = [b for b in blocks if not (100 <= b[0] < 200)]
    if not real:
        return 0, {}, url
    effective = url
    for status, headers in real[:-1]:
        if 300 <= status < 400 and headers.get('location'):
            effective = urljoin(effective, headers['location'])
    status, headers = real[-1]
    return status, headers, effective


def dropEncodingHeaders(headers):
    """--compressed: the body (stdout or outFile) is already decoded, so the response's Content-Encoding
    and Content-Length (the encoded size) no longer describe it - remove them, a caller that sees
    "Content-Encoding: gzip" would decode a second time (curl fails with exit 61 on an encoding it
    cannot decode, so whatever arrives was decoded)"""
    encoding = headers.get('content-encoding', '').strip().lower()
    if encoding and encoding != 'identity':
        headers.pop('content-encoding', None)
        headers.pop('content-length', None)
    return headers


def parseWriteOut(text):
    """the -w line in curl's stderr -> (http_code, url_effective, the rest of stderr)"""
    code, effective, rest = 0, '', []
    for line in (text or '').splitlines():
        if line.startswith(WRITEOUT_MARKER):
            parts = line[len(WRITEOUT_MARKER):].strip().split(' ', 1)
            try:
                code = int(parts[0])
            except (IndexError, ValueError):
                code = 0
            effective = parts[1] if len(parts) > 1 else ''
        elif line.strip():
            rest.append(line.strip())
    return code, effective, '\n'.join(rest)


def _readFile(path):
    try:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8', 'replace')
    except (IOError, OSError):
        return ''


def _fileSize(path):
    try:
        return os.path.getsize(path)
    except (IOError, OSError):
        return 0


def _remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except (IOError, OSError):
        pass


def _kill(proc):
    try:
        proc.kill()
    except OSError:
        pass


def _waitAfterClose(proc, seconds=5.0):
    # our end of the pipe is closed: curl's next write fails (it ignores SIGPIPE), it stops
    # and still writes the cookie jar. Python 2 has no wait(timeout) - poll.
    deadline = time.time() + seconds
    while proc.poll() is None:
        if time.time() > deadline:
            _kill(proc)
            break
        time.sleep(0.05)
    return proc.wait()


def _runToFile(args, shouldAbort=None, stderrPath=''):
    """run curl that writes the body to a file itself (-o file). Returns (returncode, b'', stop),
    stop is None or 'abort' (shouldAbort())"""
    devnull = open(os.devnull, 'rb')
    outNull = open(os.devnull, 'wb')
    errFile = open(stderrPath, 'wb')
    try:
        try:
            proc = subprocess.Popen(args, stdin=devnull, stdout=outNull, stderr=errFile, close_fds=(os.name != 'nt'))
        except OSError as e:
            raise ImpersonateUnavailable('%s: %s' % (args[0], e))
        stop = None
        while proc.poll() is None:
            if shouldAbort is not None and shouldAbort():
                stop = 'abort'
                _kill(proc)
                break
            time.sleep(0.1)
        return proc.wait(), b'', stop
    finally:
        devnull.close()
        outNull.close()
        errFile.close()


def _run(args, maxDataSize=-1, shouldAbort=None, stderrPath=''):
    """run curl, the body comes from stdout. Returns (returncode, body, stop) - stop is
    None, 'limit' (maxDataSize bytes read, the rest not wanted) or 'abort' (shouldAbort())"""
    devnull = open(os.devnull, 'rb')
    errFile = open(stderrPath, 'wb')
    try:
        try:
            proc = subprocess.Popen(args, stdin=devnull, stdout=subprocess.PIPE, stderr=errFile, close_fds=(os.name != 'nt'))
        except OSError as e:
            # ENOENT / ENOEXEC: binary missing or built for another CPU
            raise ImpersonateUnavailable('%s: %s' % (args[0], e))
        chunks = []
        size = 0
        stop = None
        fd = proc.stdout.fileno()
        while True:
            # os.read returns what is there (no waiting for a full buffer); curl writes the
            # (flushed) -D header file before the first body byte, so even max_data_size 0
            # reads once to be sure the final response's headers are complete
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if shouldAbort is not None and shouldAbort():
                stop = 'abort'
                break
            if 0 <= maxDataSize <= size:
                stop = 'limit'
                break
        body = b''.join(chunks)
        if maxDataSize >= 0:
            body = body[:maxDataSize]
        if stop == 'abort':
            _kill(proc)
        try:
            proc.stdout.close()
        except Exception:
            pass
        if stop == 'limit':
            returncode = _waitAfterClose(proc)
        else:
            returncode = proc.wait()
        return returncode, body, stop
    finally:
        devnull.close()
        errFile.close()


def fetch(binary, url, tmpDir, headers=None, cookieFile='', loadCookie=False, saveCookie=False, cookieItems=None,
          postBody=None, noRedirection=False, timeout=None, proxy='', insecure=False, cacert=None, ipv4Only=False,
          maxDataSize=-1, shouldAbort=None, log=None, outFile='', ipv6Only=False):
    """one request through curl-impersonate. Returns a dict:
    status (int, 0 = no answer), url (final URL), headers ({lower name: value} of the last response),
    body (bytes), exitcode, error (curl's message), profile, size (bytes in outFile).
    outFile: curl writes the body to this file (body is then b'', maxDataSize is not used); the
    caller removes it when the answer is not wanted.
    Raises ImpersonateUnavailable when the binary cannot run at all."""
    if cacert is None:
        cacert = CA_BUNDLE if os.path.isfile(CA_BUNDLE) else ''
    # a unique name per request - several worker threads may fetch at the same time
    fd, base = tempfile.mkstemp(prefix='e2i_imp_', dir=tmpDir)
    os.close(fd)
    headerFile = base + '.hdr'
    stderrFile = base + '.err'
    cookieIn = ''
    dataFile = ''
    try:
        if cookieFile and loadCookie and prepareCookieFile(cookieFile, base + '.cookie'):
            cookieIn = base + '.cookie'
        if postBody is not None:
            dataFile = base + '.post'
            with open(dataFile, 'wb') as f:
                f.write(postBody)
        result = None
        for profile in getProfiles():
            _remove(headerFile)
            args = buildArgs(binary, profile, url, headers, cookieIn=cookieIn, cookieOut=cookieFile if (cookieFile and saveCookie) else '',
                             cookieString=cookieItemsString(cookieItems), dataFile=dataFile, noRedirection=noRedirection,
                             timeout=timeout, proxy=proxy, insecure=insecure, cacert=cacert, ipv4Only=ipv4Only, headerFile=headerFile,
                             outFile=outFile, ipv6Only=ipv6Only)
            if log is not None:
                log('curl-impersonate: %s' % ' '.join(args[1:-1]))
            if outFile:
                _remove(outFile)  # nothing of an earlier profile's attempt
                returncode, body, stop = _runToFile(args, shouldAbort, stderrFile)
            else:
                returncode, body, stop = _run(args, maxDataSize, shouldAbort, stderrFile)
            code, effective, error = parseWriteOut(_readFile(stderrFile))
            blocks = parseHeaderFile(_readFile(headerFile))
            status, respHeaders, derivedUrl = finalResponse(blocks, url)
            if code:
                status = code
            dropEncodingHeaders(respHeaders)
            if not blocks and returncode in _BAD_TARGET_CODES and 'imperson' in error.lower():
                if log is not None:
                    log('curl-impersonate: profile %s rejected (%s), trying the next one' % (profile, error))
                continue
            if returncode < 0 and stop is None and not blocks:
                # killed by a signal before any answer (e.g. illegal instruction on this CPU)
                raise ImpersonateUnavailable('%s died with signal %d' % (binary, -returncode))
            # 'limit': we closed the pipe on purpose, curl's write error (23) is no failure
            result = {'status': status, 'url': effective or derivedUrl, 'headers': respHeaders, 'body': body,
                      'exitcode': 0 if stop == 'limit' else returncode, 'error': error, 'profile': profile,
                      'aborted': stop == 'abort', 'size': _fileSize(outFile) if outFile else len(body)}
            _state['profile'] = profile
            break
        if result is None:
            raise ImpersonateUnavailable('%s accepts none of the profiles %s' % (binary, ', '.join(PROFILES)))
        if cookieFile and saveCookie:
            normalizeCookieFile(cookieFile)
        return result
    finally:
        for path in (base, headerFile, stderrFile, cookieIn, dataFile):
            _remove(path)
