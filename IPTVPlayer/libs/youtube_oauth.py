# -*- coding: utf-8 -*-
#
# Google account sign-in for the YouTube host, via the OAuth 2.0 "limited
# input device" (device-code) flow - the same flow the YouTube app on a TV
# uses, so it needs no browser on the box.
#
# It uses the long-known public YouTube-on-TV client credentials (the same
# ones yt-dlp / Kodi's YouTube plugin / invidious use). A box can override
# them with /etc/enigma2/YouTube.key:
#     API_KEY = ...
#     CLIENT_ID = ...
#     CLIENT_SECRET = ...
#
# The bearer token is sent as `Authorization: Bearer ...` on the InnerTube
# requests - that is what unlocks age-restricted videos and the personal
# feeds (subscriptions / liked / watch later / playlists).

import time
from os.path import isfile

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_urlencode
from Components.config import config, ConfigText, configfile

config.plugins.iptvplayer.youtube_oauth_refresh_token = ConfigText(default="", fixed_size=False)

_CLIENT_ID = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"  # NOSONAR
# public "installed app" OAuth credential for Google's TV/limited-input-device
# flow - the OAuth 2.0 device-flow spec has no mechanism for these clients to
# keep a secret confidential, so Google issues them expecting exactly this;
# yt-dlp, Kodi's YouTube plugin and others ship this identical pair
_CLIENT_SECRET = "SboVhoG9s0rNafixCSGGKXAT"  # NOSONAR
# OAuth scope identifiers, not fetched URLs - "http://gdata.youtube.com" is
# Google's own legacy scope name (same string yt-dlp / Kodi use)
_SCOPE = "http://gdata.youtube.com https://www.googleapis.com/auth/youtube"  # NOSONAR

_DEVICE_CODE_URL = "https://oauth2.googleapis.com/device/code"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
# the legacy TV client only accepts the old device grant type (a URN-style
# identifier defined by the OAuth device-flow spec, never dereferenced)
_DEVICE_GRANT = "http://oauth.net/grant_type/device/1.0"  # NOSONAR
_KEY_FILE = "/etc/enigma2/YouTube.key"


def _loadKeyFile():
    global _CLIENT_ID, _CLIENT_SECRET
    if not isfile(_KEY_FILE):
        return
    try:
        with open(_KEY_FILE) as keyFile:
            lines = keyFile.read().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _sep, value = line.partition("=")
            name = name.strip().upper()
            value = value.strip().strip('"').strip("'")
            if len(value) < 10:
                continue
            if name == "CLIENT_ID":
                _CLIENT_ID = value
            elif name == "CLIENT_SECRET":
                _CLIENT_SECRET = value
    except Exception:
        printExc()


_loadKeyFile()


class YouTubeOAuth(object):
    # process-wide access-token cache: (token, expiry_epoch)
    _accessToken = ("", 0)

    HEADER = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/x-www-form-urlencoded"}

    def __init__(self):
        self._cm = None

    # ---------------------------------------------------------------- helpers
    def _post(self, url, data):
        # google returns the JSON body with a 4xx too (authorization_pending
        # is a 428), so parse it regardless of the sts flag
        if self._cm is None:
            self._cm = common()
        params = {"header": dict(self.HEADER), "raw_post_data": True}
        sts, out = self._cm.getPage(url, params, urllib_urlencode(data))
        try:
            return json_loads(out)
        except Exception:
            if not sts:
                printDBG("YouTubeOAuth._post failed: %s" % url)
            else:
                printExc()
            return {}

    @staticmethod
    def isLoggedIn():
        return bool(config.plugins.iptvplayer.youtube_oauth_refresh_token.value)

    @staticmethod
    def logout():
        YouTubeOAuth._accessToken = ("", 0)
        YouTubeOAuth._storeRefreshToken("")

    @staticmethod
    def _storeRefreshToken(value):
        # written to the settings file right away - with .save() alone it would only reach the
        # disk when Enigma2 shuts down cleanly, a power cut would lose the sign-in (or the sign-out)
        config.plugins.iptvplayer.youtube_oauth_refresh_token.value = value
        config.plugins.iptvplayer.youtube_oauth_refresh_token.save()
        try:
            configfile.save()
        except Exception:
            printExc()

    # ---------------------------------------------------------------- device flow
    def requestDeviceCode(self):
        # -> dict with verification_url, user_code, device_code, interval, expires_in
        res = self._post(_DEVICE_CODE_URL, {"client_id": _CLIENT_ID, "scope": _SCOPE})
        return {
            "verification_url": res.get("verification_url") or "https://www.google.com/device",
            "user_code": res.get("user_code", ""),
            "device_code": res.get("device_code", ""),
            "interval": int(res.get("interval", 5) or 5),
            "expires_in": int(res.get("expires_in", 1800) or 1800),
        }

    def pollForToken(self, deviceCode, interval, expiresIn, shouldStop=None):
        # blocks until the user approves on another device (or it expires).
        # shouldStop() may be passed to bail out early. Returns True on success.
        deadline = time.time() + min(int(expiresIn or 1800), 1800)
        wait = max(int(interval or 5), 5)
        while time.time() < deadline:
            if shouldStop is not None and shouldStop():
                return False
            time.sleep(wait)
            res = self._post(_TOKEN_URL, {
                "client_id": _CLIENT_ID,
                "client_secret": _CLIENT_SECRET,
                "code": deviceCode,
                "grant_type": _DEVICE_GRANT,
            })
            err = res.get("error", "")
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                wait += 5
                continue
            if res.get("refresh_token"):
                YouTubeOAuth._storeRefreshToken(res["refresh_token"])
                if res.get("access_token"):
                    YouTubeOAuth._accessToken = (res["access_token"], time.time() + int(res.get("expires_in", 3600)) - 60)
                return True
            # access_denied / expired_token / anything else -> give up
            printDBG("YouTubeOAuth.pollForToken stop: %s" % (err or res))
            return False
        return False

    # ---------------------------------------------------------------- token use
    def getAccessToken(self):
        token, expiry = YouTubeOAuth._accessToken
        if token and time.time() < expiry:
            return token
        refresh = config.plugins.iptvplayer.youtube_oauth_refresh_token.value
        if not refresh:
            return ""
        res = self._post(_TOKEN_URL, {
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "refresh_token": refresh,
            "grant_type": "refresh_token",
        })
        if res.get("access_token"):
            YouTubeOAuth._accessToken = (res["access_token"], time.time() + int(res.get("expires_in", 3600)) - 60)
            return res["access_token"]
        if res.get("error") in ("invalid_grant", "unauthorized_client"):
            # refresh token revoked / no longer valid - drop it
            printDBG("YouTubeOAuth: refresh token rejected (%s), signing out" % res.get("error"))
            YouTubeOAuth.logout()
        return ""

    def getAuthHeader(self):
        token = self.getAccessToken()
        return {"Authorization": "Bearer %s" % token} if token else {}
