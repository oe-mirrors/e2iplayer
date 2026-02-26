# -*- coding: utf-8 -*-
import base64
from binascii import unhexlify
import codecs
from hashlib import sha256
from random import choice as random_choice
import re
import string
import struct
import time
from Components.config import config
from Screens.MessageBox import MessageBox
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import GetIPTVSleep, SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.libs import ph, pyaes
from Plugins.Extensions.IPTVPlayer.libs.aesgcm import python_aesgcm
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import captchaParser, decorateUrl, getDirectM3U8Playlist, getMPDLinksWithMeta, TEAMCASTPL_decryptPlayerParams, unicode_escape, unpackJSPlayerParams, VIDUPME_decryptPlayerParams
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import parse_qs, urljoin, urlparse
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, GetCookieDir, GetDefaultLang, GetJSScriptFile, GetPluginDir, printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

if not isPY2():
    basestring = str
    xrange = range


def generate_vrf(movie_id, user_id):
    key = sha256(user_id.encode("utf-8")).digest()
    aes = pyaes.AESModeOfOperationCBC(key, iv=b"\x00" * 16)
    p_len = 16 - len(movie_id) % 16
    plaintext = movie_id + chr(p_len) * p_len
    ciphertext = aes.encrypt(plaintext)
    encoded = base64.b64encode(ciphertext).decode()
    url_safe = encoded.replace("+", "-").replace("/", "_").replace("=", "")
    return url_safe


def crsdiv(a, dec_id):
    def b64dec(t):
        return base64.b64decode(t).decode("latin1")

    def dec(a, shift):
        b64 = a[::-1].replace("-", "+").replace("_", "/")
        return "".join([chr(ord(ch) - shift) for ch in b64dec(b64)])

    if dec_id == "sXnL9MQIry":
        b = [ord(ch) for ch in "pWB9V)[*4I`nJpp?ozyB~dbr9yt!_n4u"]
        d = [int(x, 16) for x in re.findall(r".{2}", a)]
        decrypted = [(v ^ b[i % len(b)]) - 3 for i, v in enumerate(d)]
        return b64dec("".join(chr(v) for v in decrypted))
    if dec_id == "IhWrImMIGL":
        d = []
        for ch in a:
            if "a" <= ch <= "m" or "A" <= ch <= "M":
                d.append(chr(ord(ch) + 13))
            elif "n" <= ch <= "z" or "N" <= ch <= "Z":
                d.append(chr(ord(ch) - 13))
            else:
                d.append(ch)
        return b64dec("".join(d))
    if dec_id == "xTyBxQyGTA":
        b = a[::-1]
        c = "".join([b[i] for i in range(0, len(b), 2)])
        return b64dec(c)
    if dec_id == "ux8qjPHC66":
        rev = a[::-1]
        data = "".join([chr(int(rev[i: i + 2], 16)) for i in range(0, len(rev), 2)])
        key = "X9a(O;FMV2-7VO5x;Ao\x05:dN1NoFs?j,"
        res = []
        for i, ch in enumerate(data):
            res.append(chr(ord(ch) ^ ord(key[i % len(key)])))
        return "".join(res)
    if dec_id == "eSfH1IRMyL":
        rev = [ord(ch) - 1 for ch in reversed(a)]
        chunks = []
        i = 0
        while i < len(rev):
            val = int("".join([chr(rev[i]), chr(rev[i + 1])]), 16)
            chunks.append(val)
            i += 2
        return "".join(chr(v) for v in chunks)
    if dec_id == "KJHidj7det":
        c = [ord(ch) for ch in '3SAY~#%Y(V%>5d/Yg"$G[Lh1rK4a;7ok']
        decrypted = [v ^ c[i % len(c)] for i, v in enumerate([ord(ch) for ch in b64dec(a[10:-16])])]
        return "".join(chr(v) for v in decrypted)
    if dec_id == "o2VSUnjnZl":
        mapping = {"x": "a", "y": "b", "z": "c", "a": "d", "b": "e", "c": "f", "d": "g", "e": "h", "f": "i", "g": "j", "h": "k", "i": "l", "j": "m", "k": "n", "l": "o", "m": "p", "n": "q", "o": "r", "p": "s", "q": "t", "r": "u", "s": "v", "t": "w", "u": "x", "v": "y", "w": "z", "X": "A", "Y": "B", "Z": "C", "A": "D", "B": "E", "C": "F", "D": "G", "E": "H", "F": "I", "G": "J", "H": "K", "I": "L", "J": "M", "K": "N", "L": "O", "M": "P", "N": "Q", "O": "R", "P": "S", "Q": "T", "R": "U", "S": "V", "T": "W", "U": "X", "V": "Y", "W": "Z"}
        return "".join(mapping.get(ch, ch) for ch in a)
    if dec_id in ("JoAHUMCLXV", "Oi3v1dAlaM", "TsA2KGDGux"):
        shifts = {"JoAHUMCLXV": 3, "Oi3v1dAlaM": 5, "TsA2KGDGux": 7}
        return dec(a, shifts[dec_id])
    return ""


def rc4(cipher_text, key):
    def compat_ord(c):
        return ord(c) if isinstance(c, str) else c

    res = ensure_binary("")
    cipher_text = base64.b64decode(cipher_text)
    key_len = len(key)
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + ord(key[i % key_len])) % 256
        S[i], S[j] = S[j], S[i]
    i = 0
    j = 0
    for m in range(len(cipher_text)):
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        k = S[(S[i] + S[j]) % 256]
        res += struct.pack("B", k ^ compat_ord(cipher_text[m]))
    return ensure_str(res)


def random_seed(length=10, data=""):
    return data + "".join(random_choice(string.ascii_letters + string.digits) for x in range(length))


def girc(data, url, co=None):
    cm = common()
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0", "Referer": url}
    rurl = "https://www.google.com/recaptcha/api.js"
    aurl = "https://www.google.com/recaptcha/api2"
    key = re.search(r'(?:src="{0}\?.*?render|data-sitekey)="?([^"]+)'.format(rurl), data)
    if key:
        if co is None:
            co = base64.b64encode((url[:-1] + ":443").encode()).replace(b"=", b"")
        key = key.group(1)
        rurl = "{0}?render={1}".format(rurl, key)
        sts, data = cm.getPage(rurl, hdrs)
        if not sts:
            return ""
        v = re.findall("releases/([^/]+)", data)
        v = v[0]
        rdata = {"ar": 1, "k": key, "co": co, "hl": "en", "v": v, "size": "invisible", "cb": "123456789"}
        sts, data = cm.getPage("{0}/anchor?{1}".format(aurl, urllib_urlencode(rdata)), hdrs)
        if not sts:
            return ""
        rtoken = re.search('recaptcha-token.+?="([^"]+)', data)
        pdata = {"v": v, "reason": "q", "k": key, "c": rtoken.group(1), "sa": "", "co": co}
        hdrs.update({"Referer": aurl})
        sts, data = cm.getPage("{0}/reload?k={1}".format(aurl, key), hdrs, pdata)
        if not sts:
            return ""
        gtoken = re.search('rresp","([^"]+)', data)
        if gtoken:
            return gtoken.group(1)
    return ""


def InternalCipher(data, encrypt=True):
    tmp = sha256("|".join(GetPluginDir().split("/")[-2:])).digest()
    key = tmp[:16]
    iv = tmp[16:]
    cipher = AES_CBC(key=key, keySize=16)
    if encrypt:
        return cipher.encrypt(data, iv)
    return cipher.decrypt(data, iv)


class urlparser:
    def __init__(self):
        self.cm = common()
        self.pp = pageParser()
        self.hostMap = {
            "1azayf9w.xyz": self.pp.parserBYSE,
            "1fichier.com": self.pp.parser1FICHIERCOM,
            "222i8x.lol": self.pp.parserBYSE,
            "26efp.com": self.pp.parserJWPLAYER,
            "4yftwvrdz7.sbs": self.pp.parserJWPLAYER,
            "81u6xl9d.xyz": self.pp.parserBYSE,
            "8mhlloqo.fun": self.pp.parserBYSE,
            "96ar.com": self.pp.parserBYSE,
            # a
            "adblocktape.wiki": self.pp.parserSTREAMTAPE,
            "aiavh.com": self.pp.parserJWPLAYER,
            "aliez.me": self.pp.parserJWPLAYER,
            "all3do.com": self.pp.parserDOOD,
            "anime4low.sbs": self.pp.parserJWPLAYER,
            "antiadtape.com": self.pp.parserSTREAMTAPE,
            "arabveturk.com": self.pp.parserJWPLAYER,
            "archive.org": self.pp.parserARCHIVEORG,
            "ashortl.ink": self.pp.parserVIDMOLYME,
            "asnwish.com": self.pp.parserJWPLAYER,
            "awish.pro": self.pp.parserJWPLAYER,
            # b
            "bbc.co.uk": self.pp.parserBBC,
            "bestwish.lol": self.pp.parserJWPLAYER,
            "bf0skv.org": self.pp.parserBYSE,
            "bgwp.cc": self.pp.parserJWPLAYER,
            "bigshare.io": self.pp.parserJWPLAYER,
            "bigwarp.art": self.pp.parserJWPLAYER,
            "bigwarp.cc": self.pp.parserJWPLAYER,
            "bigwarp.io": self.pp.parserJWPLAYER,
            "bigwarp.pro": self.pp.parserJWPLAYER,
            "bigwings.io": self.pp.parserJWPLAYER,
            "bingezove.com": self.pp.parserJWPLAYER,
            "boosteradx.online": self.pp.parserBYSE,
            "bysebuho.com": self.pp.parserBYSE,
            "bysedikamoum.com": self.pp.parserBYSE,
            "bysefujedu.com": self.pp.parserBYSE,
            "bysejikuar.com": self.pp.parserBYSE,
            "bysekoze.com": self.pp.parserBYSE,
            "byseqekaho.com": self.pp.parserBYSE,
            "bysesayeveum.com": self.pp.parserBYSE,
            "bysesukior.com": self.pp.parserBYSE,
            "bysetayico.com": self.pp.parserBYSE,
            "bysevepoin.com": self.pp.parserBYSE,
            "bysewihe.com": self.pp.parserBYSE,
            "bysezejataos.com": self.pp.parserBYSE,
            # c
            "c1z39.com": self.pp.parserBYSE,
            "cavanhabg.com": self.pp.parserJWPLAYER,
            "cda.pl": self.pp.parserCDA,
            "cdn1.site": self.pp.parserJWPLAYER,
            "cdnwish.com": self.pp.parserJWPLAYER,
            "chuckle-tube.com": self.pp.parserVOESX,
            "cloud.mail.ru": self.pp.parserCOUDMAILRU,
            "coverapi.store": self.pp.parserCOVERAPI,
            "csst.online": self.pp.parserSST,
            "cybervynx.com": self.pp.parserJWPLAYER,
            # d
            "d0000d.com": self.pp.parserDOOD,
            "d000d.com": self.pp.parserDOOD,
            "d0o0d.com": self.pp.parserDOOD,
            "d-s.io": self.pp.parserDOOD,
            "dailymotion.com": self.pp.parserDAILYMOTION,
            "dancima.shop": self.pp.parserJWPLAYER,
            "davioad.com": self.pp.parserJWPLAYER,
            "dhcplay.com": self.pp.parserJWPLAYER,
            "dhtpre.com": self.pp.parserJWPLAYER,
            "dingtezuni.com": self.pp.parserJWPLAYER,
            "dintezuvio.com": self.pp.parserJWPLAYER,
            "do0od.com": self.pp.parserDOOD,
            "do7go.com": self.pp.parserDOOD,
            "dood.cx": self.pp.parserDOOD,
            "dood.la": self.pp.parserDOOD,
            "dood.li": self.pp.parserDOOD,
            "dood.pm": self.pp.parserDOOD,
            "dood.re": self.pp.parserDOOD,
            "dood.sh": self.pp.parserDOOD,
            "dood.so": self.pp.parserDOOD,
            "dood.stream": self.pp.parserDOOD,
            "dood.to": self.pp.parserDOOD,
            "dood.watch": self.pp.parserDOOD,
            "dood.wf": self.pp.parserDOOD,
            "dood.work": self.pp.parserDOOD,
            "dood.ws": self.pp.parserDOOD,
            "dood.yt": self.pp.parserDOOD,
            "doods.pro": self.pp.parserDOOD,
            "doods.to": self.pp.parserVEEV,
            "doodcdn.io": self.pp.parserDOOD,
            "doodstream.co": self.pp.parserDOOD,
            "doodstream.com": self.pp.parserDOOD,
            "dooodster.com": self.pp.parserDOOD,
            "dooood.com": self.pp.parserDOOD,
            "doply.net": self.pp.parserDOOD,
            "dpstream.fyi": self.pp.parserJWPLAYER,
            "dropload.io": self.pp.parserJWPLAYER,
            "dropload.pro": self.pp.parserJWPLAYER,
            "dropload.tv": self.pp.parserJWPLAYER,
            "ds2play.com": self.pp.parserDOOD,
            "ds2video.com": self.pp.parserDOOD,
            "dsvplay.com": self.pp.parserDOOD,
            "dumbalag.com": self.pp.parserJWPLAYER,
            # e
            "eb8gfmjn71.sbs": self.pp.parserJWPLAYER,
            "ebd.cda.pl": self.pp.parserCDA,
            "edbrdl7pab.sbs": self.pp.parserJWPLAYER,
            "egtpgrvh.sbs": self.pp.parserJWPLAYER,
            "embedwish.com": self.pp.parserJWPLAYER,
            "emturbovid.com": self.pp.parserJWPLAYER,
            "en.embedz.net": self.pp.parserJWPLAYER,
            # f
            "f16px.com": self.pp.parserBYSE,
            "f51rm.com": self.pp.parserBYSE,
            "fastream.to": self.pp.parserJWPLAYER,
            "fdewsdc.sbs": self.pp.parserJWPLAYER,
            "filecloud.io": self.pp.parserFILECLOUDIO,
            "filefactory.com": self.pp.parserFILEFACTORYCOM,
            "filelions.live": self.pp.parserJWPLAYER,
            "filelions.online": self.pp.parserJWPLAYER,
            "filelions.site": self.pp.parserJWPLAYER,
            "filelions.to": self.pp.parserJWPLAYER,
            "filemoon.art": self.pp.parserBYSE,
            "filemoon.eu": self.pp.parserBYSE,
            "filemoon.in": self.pp.parserBYSE,
            "filemoon.link": self.pp.parserBYSE,
            "filemoon.nl": self.pp.parserBYSE,
            "filemoon.sx": self.pp.parserBYSE,
            "filemoon.to": self.pp.parserBYSE,
            "filemoon.wf": self.pp.parserBYSE,
            "fileone.tv": self.pp.parserFILEONETV,
            "file-upload.org": self.pp.parserJWPLAYER,
            "flaswish.com": self.pp.parserJWPLAYER,
            "forafile.com": self.pp.parserJWPLAYER,
            "fsdcmo.sbs": self.pp.parserJWPLAYER,
            "fsst.online": self.pp.parserSST,
            # g
            "ghbrisk.com": self.pp.parserJWPLAYER,
            "goodstream.one": self.pp.parserJWPLAYER,
            "goodstream.uno": self.pp.parserJWPLAYER,
            "goofy-banana.com": self.pp.parserVOESX,
            "google.com": self.pp.parserGOOGLE,
            "govid.site": self.pp.parserJWPLAYER,
            "gscdn.cam": self.pp.parserJWPLAYER,
            "gsfqzmqu.sbs": self.pp.parserJWPLAYER,
            "gupload.xyz": self.pp.parserGUPLOAD,
            # h
            "haxloppd.com": self.pp.parserJWPLAYER,
            "hdbestvd.online": self.pp.parserJWPLAYER,
            "hexload.com": self.pp.parserHEXLOAD,
            "hexupload.net": self.pp.parserHEXLOAD,
            "hglink.to": self.pp.parserJWPLAYER,
            "hgplaycdn.com": self.pp.parserJWPLAYER,
            "hlsflast.com": self.pp.parserJWPLAYER,
            "hlsplayer.org": self.pp.parserJWPLAYER,
            "hlswish.com": self.pp.parserJWPLAYER,
            # i
            "iplayerhls.com": self.pp.parserJWPLAYER,
            # j
            "javsw.me": self.pp.parserJWPLAYER,
            "jodwish.com": self.pp.parserJWPLAYER,
            "justupload.io": self.pp.parserJWPLAYER,
            # k
            "kinoger.be": self.pp.parserVEEV,
            "kinoger.p2pplay.pro": self.pp.parserSBS,
            "kinoger.re": self.pp.parserSBS,
            "kinoger.ru": self.pp.parserVOESX,
            "kravaxxa.com": self.pp.parserJWPLAYER,
            # l
            "l1afav.net": self.pp.parserBYSE,
            "lulu.st": self.pp.parserJWPLAYER,
            "lulustream.com": self.pp.parserJWPLAYER,
            "luluvid.com": self.pp.parserJWPLAYER,
            "luluvdo.com": self.pp.parserJWPLAYER,
            "luluvdoo.com": self.pp.parserJWPLAYER,
            # m
            "m1xdrop.net": self.pp.parserJWPLAYER,
            "md3b0j6hj.com": self.pp.parserJWPLAYER,
            "mdbekjwqa.pw": self.pp.parserJWPLAYER,
            "mdfx9dc8n.net": self.pp.parserJWPLAYER,
            "mdy48tn97.com": self.pp.parserJWPLAYER,
            "mdzsmutpcvykb.net": self.pp.parserJWPLAYER,
            "mediafire.com": self.pp.parserMEDIAFIRECOM,
            "mediasetplay.mediaset.it": self.pp.parserMEDIASET,
            "minochinos.com": self.pp.parserJWPLAYER,
            "mivalyo.com": self.pp.parserJWPLAYER,
            "mixdrp.co": self.pp.parserJWPLAYER,
            "mixdrp.to": self.pp.parserJWPLAYER,
            "mixdroop.co": self.pp.parserJWPLAYER,
            "mixdrop21.net": self.pp.parserJWPLAYER,
            "mixdrop23.net": self.pp.parserJWPLAYER,
            "mixdrop.ag": self.pp.parserJWPLAYER,
            "mixdrop.bz": self.pp.parserJWPLAYER,
            "mixdrop.ch": self.pp.parserJWPLAYER,
            "mixdrop.club": self.pp.parserJWPLAYER,
            "mixdrop.co": self.pp.parserJWPLAYER,
            "mixdrop.my": self.pp.parserJWPLAYER,
            "mixdrop.nu": self.pp.parserJWPLAYER,
            "mixdrop.ps": self.pp.parserJWPLAYER,
            "mixdrop.sb": self.pp.parserJWPLAYER,
            "mixdrop.si": self.pp.parserJWPLAYER,
            "mixdrop.sn": self.pp.parserJWPLAYER,
            "mixdrop.sx": self.pp.parserJWPLAYER,
            "mixdrop.to": self.pp.parserJWPLAYER,
            "mixdrop.top": self.pp.parserJWPLAYER,
            "mixdropjmk.pw": self.pp.parserJWPLAYER,
            "moflix-stream.click": self.pp.parserJWPLAYER,
            "moflix-stream.fans": self.pp.parserJWPLAYER,
            "moflix-stream.link": self.pp.parserBYSE,
            "moflix.rpmplay.xyz": self.pp.parserSBS,
            "moflix.upns.xyz": self.pp.parserSBS,
            "movearnpre.com": self.pp.parserJWPLAYER,
            "mp4player.site": self.pp.parserSTREAMEMBED,
            "mp4upload.com": self.pp.parserJWPLAYER,
            "mxdrop.to": self.pp.parserJWPLAYER,
            "mysportzfy.com": self.pp.parserJWPLAYER,
            "myvidplay.com": self.pp.parserDOOD,
            # n
            "nova.upn.one": self.pp.parserSBS,
            # o
            "obeywish.com": self.pp.parserJWPLAYER,
            "odnoklassniki.ru": self.pp.parserOKRU,
            "odysee.com": self.pp.parserJWPLAYER,
            "ok.ru": self.pp.parserOKRU,
            # p
            "peytonepre.com": self.pp.parserJWPLAYER,
            "player.upn.one": self.pp.parserSBS,
            "playerwish.com": self.pp.parserJWPLAYER,
            "polsatsport.pl": self.pp.parserJWPLAYER,
            "poophq.com": self.pp.parserVEEV,
            "pqham.com": self.pp.parserJWPLAYER,
            # r
            "rapid-cloud.co": self.pp.parserVIDCLOUD,
            "rubystm.com": self.pp.parserJWPLAYER,
            "rubyvidhub.com": self.pp.parserJWPLAYER,
            "ryderjet.com": self.pp.parserJWPLAYER,
            # s
            "s3taku.pro": self.pp.parserJWPLAYER,
            "savefiles.com": self.pp.parserJWPLAYER,
            "scloud.online": self.pp.parserSTREAMTAPE,
            "sendvid.com": self.pp.parserJWPLAYER,
            "sfastwish.com": self.pp.parserJWPLAYER,
            "sharevideo.pl": self.pp.parserSHAREVIDEO,
            "shavetape.cash": self.pp.parserSTREAMTAPE,
            "shiid4u.upn.one": self.pp.parserSBS,
            "smoothpre.com": self.pp.parserJWPLAYER,
            "soundcloud.com": self.pp.parserSOUNDCLOUDCOM,
            "sportsonline.si": self.pp.parserJWPLAYER,
            "sportsonline.to": self.pp.parserJWPLAYER,
            "stape.fun": self.pp.parserSTREAMTAPE,
            "stmix.io": self.pp.parserSTREAMUP,
            "strcloud.club": self.pp.parserSTREAMTAPE,
            "strcloud.link": self.pp.parserSTREAMTAPE,
            "streamadblocker.xyz": self.pp.parserSTREAMTAPE,
            "streamadblockplus.com": self.pp.parserSTREAMTAPE,
            "streamhihi.com": self.pp.parserJWPLAYER,
            "streamhls.to": self.pp.parserJWPLAYER,
            "streamlyplayer.online": self.pp.parserBYSE,
            "streamix.so": self.pp.parserSTREAMUP,
            "streamnoads.com": self.pp.parserSTREAMTAPE,
            "streamruby.com": self.pp.parserJWPLAYER,
            "streamta.pe": self.pp.parserSTREAMTAPE,
            "streamta.site": self.pp.parserSTREAMTAPE,
            "streamtape.cc": self.pp.parserSTREAMTAPE,
            "streamtape.com": self.pp.parserSTREAMTAPE,
            "streamtape.net": self.pp.parserSTREAMTAPE,
            "streamtape.site": self.pp.parserSTREAMTAPE,
            "streamtape.to": self.pp.parserSTREAMTAPE,
            "streamtape.xyz": self.pp.parserSTREAMTAPE,
            "streamup.ws": self.pp.parserSTREAMUP,
            "streamvid.su": self.pp.parserJWPLAYER,
            "streamwish.fun": self.pp.parserJWPLAYER,
            "streamwish.to": self.pp.parserJWPLAYER,
            "strmup.cc": self.pp.parserSTREAMUP,
            "strmup.to": self.pp.parserSTREAMUP,
            "strtape.cloud": self.pp.parserSTREAMTAPE,
            "strtpe.link": self.pp.parserSTREAMTAPE,
            "supervideo.cc": self.pp.parserJWPLAYER,
            "supervideo.tv": self.pp.parserJWPLAYER,
            "swdyu.com": self.pp.parserJWPLAYER,
            "swhoi.com": self.pp.parserJWPLAYER,
            "swiftplayers.com": self.pp.parserJWPLAYER,
            "swishsrv.com": self.pp.parserJWPLAYER,
            # t
            "tapeadsenjoyer.com": self.pp.parserSTREAMTAPE,
            "tapeadvertisement.com": self.pp.parserSTREAMTAPE,
            "tapeblocker.com": self.pp.parserSTREAMTAPE,
            "tapewithadblock.org": self.pp.parserSTREAMTAPE,
            "tenstream.net": self.pp.parserJWPLAYER,
            "turboviplay.com": self.pp.parserJWPLAYER,
            "tusfiles.com": self.pp.parserUSERSCLOUDCOM,
            "tusfiles.net": self.pp.parserUSERSCLOUDCOM,
            "tvp.pl": self.pp.parserTVP,
            # u
            "ultrastream.online": self.pp.parserSBS,
            "up4fun.top": self.pp.parserJWPLAYER,
            "up4stream.com": self.pp.parserJWPLAYER,
            "updown.icu": self.pp.parserJWPLAYER,
            "upzone.cc": self.pp.parserUPZONECC,
            "uqload.bz": self.pp.parserJWPLAYER,
            "uqload.com": self.pp.parserJWPLAYER,
            "uqload.cx": self.pp.parserJWPLAYER,
            "uqload.io": self.pp.parserJWPLAYER,
            "uqload.ws": self.pp.parserJWPLAYER,
            "uqloads.xyz": self.pp.parserJWPLAYER,
            "userscloud.com": self.pp.parserUSERSCLOUDCOM,
            # v
            "v.turkvearab.com": self.pp.parserJWPLAYER,
            "veev.to": self.pp.parserVEEV,
            "vide0.net": self.pp.parserDOOD,
            "vidply.com": self.pp.parserDOOD,
            "videa.hu": self.pp.parserVIDEA,
            "videakid.hu": self.pp.parserVIDEA,
            "vidara.so": self.pp.parserSTREAMUP,
            "vidara.to": self.pp.parserSTREAMUP,
            "vidora.stream": self.pp.parserJWPLAYER,
            "videzz.net": self.pp.parserJWPLAYER,
            "vidhidehub.com": self.pp.parserJWPLAYER,
            "vidload.co": self.pp.parserVIDLOADCO,
            "vidmoly.biz": self.pp.parserVIDMOLYME,
            "vidmoly.me": self.pp.parserVIDMOLYME,
            "vidmoly.net": self.pp.parserVIDMOLYME,
            "vidmoly.to": self.pp.parserVIDMOLYME,
            "vidnest.io": self.pp.parserJWPLAYER,
            "vidoza.co": self.pp.parserJWPLAYER,
            "vidoza.net": self.pp.parserJWPLAYER,
            "vidoza.org": self.pp.parserJWPLAYER,
            "vidsonic.net": self.pp.parserVIDSONIC,
            "vidsrc.bz": self.pp.parserVIDSRC,
            "vidsrc.cc": self.pp.parserMEGAFILES,
            "vidsrc.do": self.pp.parserVIDSRC,
            "vidsrc.gd": self.pp.parserVIDSRC,
            "vidsrc.in": self.pp.parserVIDSRC,
            "vidsrc.io": self.pp.parserVIDSRC,
            "vidsrc.me": self.pp.parserVIDSRC,
            "vidsrc.mn": self.pp.parserVIDSRC,
            "vidsrc.net": self.pp.parserVIDSRC,
            "vidsrc.pm": self.pp.parserVIDSRC,
            "vidsrc.tw": self.pp.parserVIDSRC,
            "vidsrc.vc": self.pp.parserVIDSRC,
            "vidsrc.xyz": self.pp.parserVIDSRC,
            "vidsrc-embed.ru": self.pp.parserVIDSRC,
            "vidsrc-embed.su": self.pp.parserVIDSRC,
            "vidsrc-me.ru": self.pp.parserVIDSRC,
            "vidsrc-me.su": self.pp.parserVIDSRC,
            "vidsrcme.ru": self.pp.parserVIDSRC,
            "vidsrcme.su": self.pp.parserVIDSRC,
            "vsrc.su": self.pp.parserVIDSRC,
            "vidzy.org": self.pp.parserJWPLAYER,
            "vinovo.si": self.pp.parserVINOVO,
            "vinovo.to": self.pp.parserVINOVO,
            "vk.com": self.pp.parserVK,
            "vkvideo.ru": self.pp.parserVK,
            "voe.sx": self.pp.parserVOESX,
            "vsports.pt": self.pp.parserJWPLAYER,
            "vtbe.to": self.pp.parserJWPLAYER,
            "vtube.network": self.pp.parserJWPLAYER,
            "vtube.to": self.pp.parserJWPLAYER,
            "vvide0.com": self.pp.parserDOOD,
            # w
            "wasuytm.store": self.pp.parserSBS,
            "watch.ezplayer.me": self.pp.parserSBS,
            "watch.gxplayer.xyz": self.pp.parserSTREAMEMBED,
            "watchadsontape.com": self.pp.parserSTREAMTAPE,
            "wavehd.com": self.pp.parserJWPLAYER,
            "webcamera.mobi": self.pp.parserWEBCAMERAPL,
            "webcamera.pl": self.pp.parserWEBCAMERAPL,
            "wishembed.pro": self.pp.parserJWPLAYER,
            "wishonly.site": self.pp.parserJWPLAYER,
            # x
            "xcoic.com": self.pp.parserBYSE,
            # y
            "yourupload.com": self.pp.parserJWPLAYER,
            "youtu.be": self.pp.parserYOUTUBE,
            "youtube-nocookie.com": self.pp.parserYOUTUBE,
            "youtube.com": self.pp.parserYOUTUBE,
            # z
            "z1ekv717.fun": self.pp.parserJWPLAYER
        }

    @staticmethod
    def getDomain(url, onlyDomain=True):
        parsed_uri = urlparse(url)
        if onlyDomain:
            domain = "{uri.netloc}".format(uri=parsed_uri)
        else:
            domain = "{uri.scheme}://{uri.netloc}/".format(uri=parsed_uri)
        return domain

    @staticmethod
    def decorateUrl(url, metaParams={}):
        return decorateUrl(url, metaParams)

    @staticmethod
    def decorateParamsFromUrl(baseUrl, overwrite=False):
        printDBG("urlparser.decorateParamsFromUrl >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>" + baseUrl)
        tmp = baseUrl.split("|")
        baseUrl = strwithmeta(tmp[0].strip(), strwithmeta(baseUrl).meta)
        KEYS_TAB = list(DMHelper.HANDLED_HTTP_HEADER_PARAMS)
        KEYS_TAB.extend(["iptv_audio_url", "iptv_proto", "Host", "Accept", "MPEGTS-Live", "PROGRAM-ID"])
        if len(tmp) == 2:
            baseParams = tmp[1].strip()
            try:
                params = parse_qs(baseParams)
                printDBG("PARAMS FROM URL [%s]" % params)
                for key in params.keys():
                    if key not in KEYS_TAB:
                        continue
                    if not overwrite and key in baseUrl.meta:
                        continue
                    try:
                        baseUrl.meta[key] = params[key][0]
                    except Exception:
                        printExc()
            except Exception:
                printExc()
        baseUrl = urlparser.decorateUrl(baseUrl)
        return baseUrl

    def preparHostForSelect(self, v, resolveLink=False):
        urltab = []
        i = 0
        if len(v) > 0:
            for url in list(v.values()) if type(v) is dict else v:
                if self.checkHostSupport(url) == 1:
                    hostName = self.getHostName(url, True)
                    i = i + 1
                    if resolveLink:
                        url = self.getVideoLink(url)
                    if isinstance(url, basestring) and url.startswith("http"):
                        urltab.append({"name": (str(i) + ". " + hostName), "url": url})
        return urltab

    def getItemTitles(self, table):
        out = []
        for i in range(len(table)):
            value = table[i]
            out.append(value[0])
        return out

    def getHostName(self, url, nameOnly=False):
        hostName = strwithmeta(url).meta.get("host_name", "")
        if not hostName:
            match = re.search("https?://(?:www.)?(.+?)/", url)
            if match:
                hostName = match.group(1)
                if nameOnly:
                    n = hostName.split(".")
                    try:
                        hostName = n[-2]
                    except Exception:
                        printExc()
            hostName = hostName.lower()
        printDBG("_________________getHostName: [%s] -> [%s]" % (url, hostName))
        return hostName

    def getParser(self, url, host=None):
        if None is host:
            host = self.getHostName(url)
        parser = self.hostMap.get(host, None)
        if None is parser:
            host2 = host[host.find(".") + 1:]
            printDBG("urlparser.getParser II try host[%s]->host2[%s]" % (host, host2))
            parser = self.hostMap.get(host2, None)
        return parser

    def checkHostSupport(self, url):
        # -1 - not supported
        #  0 - unknown
        #  1 - supported
        host = self.getHostName(url)
        # quick fix
        if host == "facebook.com" and "likebox.php" in url or "like.php" in url or "/groups/" in url:
            return 0
        ret = 0
        parser = self.getParser(url, host)
        if None is not parser:
            return 1
        elif self.isHostsNotSupported(host):
            return -1
        return ret

    def isHostsNotSupported(self, host):
        return host in ["rapidgator.net", "oboom.com"]

    def getVideoLinkExt(self, url):
        urltab = []
        try:
            ret = self.getVideoLink(url, True)
            if isinstance(ret, basestring):
                if len(ret) > 0:
                    host = self.getHostName(url)
                    urltab.append({"name": host, "url": ret})
            elif isinstance(ret, (list, tuple)):
                urltab = ret
            for idx in range(len(urltab)):
                if not self.cm.isValidUrl(url):
                    continue
                url = strwithmeta(urltab[idx]["url"])
                if "User-Agent" not in url.meta:
                    url.meta["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0"
                    urltab[idx]["url"] = url
        except Exception:
            printExc()
        return urltab

    def getVideoLink(self, url, acceptsList=False):
        try:
            url = self.decorateParamsFromUrl(url)
            nUrl = ""
            parser = self.getParser(url)
            if None is not parser:
                nUrl = parser(url)
            else:
                host = self.getHostName(url)
                if self.isHostsNotSupported(host):
                    SetIPTVPlayerLastHostError(_('Hosting "%s" not supported.') % host)
                else:
                    SetIPTVPlayerLastHostError(_('Hosting "%s" unknown.') % host)
            if isinstance(nUrl, (list, tuple)):
                if acceptsList:
                    return nUrl
                if len(nUrl) > 0:
                    return nUrl[0]["url"]

            return nUrl
        except Exception:
            printExc()
        return False


class pageParser(CaptchaHelper):
    HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Content-type": "application/x-www-form-urlencoded"}
    FICHIER_DOWNLOAD_NUM = 0

    def __init__(self):
        self.cm = common()
        self.captcha = captchaParser()
        self.ytParser = None
        self.bbcIE = None
        self.sportStream365ServIP = None
        self.COOKIE_PATH = GetCookieDir("")
        self.jscode = {}
        self.jscode["jwplayer"] = "window=this; function stub() {}; function jwplayer() {return {setup:function(){print(JSON.stringify(arguments[0]))}, onTime:stub, onPlay:stub, onComplete:stub, onReady:stub, addButton:stub}}; window.jwplayer=jwplayer;"

    def getPageCF(self, baseUrl, addParams={}, post_data=None):
        addParams["cloudflare_params"] = {"cookie_file": addParams["cookiefile"], "User-Agent": addParams["header"]["User-Agent"]}
        sts, data = self.cm.getPageCFProtection(baseUrl, addParams, post_data)
        return sts, data

    def getYTParser(self):
        if self.ytParser is None:
            try:
                from Plugins.Extensions.IPTVPlayer.libs.youtubeparser import YouTubeParser

                self.ytParser = YouTubeParser()
            except Exception:
                printExc()
                self.ytParser = None
        return self.ytParser

    def getBBCIE(self):
        if self.bbcIE is None:
            try:
                from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE

                self.bbcIE = BBCCoUkIE()
            except Exception:
                self.bbcIE = None
                printExc()
        return self.bbcIE

    def parserCDA(self, inUrl):  # Need test
        printDBG("parserCDA inUrl[%r]" % inUrl)
        COOKIE_FILE = GetCookieDir("cdapl.cookie")
        self.cm.clearCookie(COOKIE_FILE, removeNames=["vToken"])
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (PlayStation 4 4.71) AppleWebKit/601.2 (KHTML, like Gecko)"}
        defaultParams = {"header": HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": COOKIE_FILE}

        def getPage(url, params={}, post_data=None):
            sts, data = False, None
            sts, data = self.cm.getPage(url, defaultParams, post_data)
            tries = 0
            while tries < 3:
                tries += 1
                if self.cm.meta["status_code"] == 429:
                    GetIPTVSleep().Sleep(61)
                    sts, data = self.cm.getPage(url, defaultParams, post_data)
            return sts, data

        def _decorateUrl(inUrl, referer):
            cookies = []
            cj = self.cm.getCookie(COOKIE_FILE)
            for cookie in cj:
                if (cookie.name == "vToken" and cookie.path in inUrl) or cookie.name == "PHPSESSID":
                    cookies.append("%s=%s;" % (cookie.name, cookie.value))
                    printDBG(">> \t%s \t%s \t%s \t%s" % (cookie.domain, cookie.path, cookie.name, cookie.value))
            # prepare extended link
            retUrl = strwithmeta(inUrl)
            retUrl.meta["User-Agent"] = HTTP_HEADER["User-Agent"]
            retUrl.meta["Referer"] = referer
            retUrl.meta["Cookie"] = " ".join(cookies)
            retUrl.meta["iptv_proto"] = "http"
            retUrl.meta["iptv_urlwithlimit"] = False
            retUrl.meta["iptv_livestream"] = False
            return retUrl

        vidMarker = "/video/"
        videoUrls = []
        uniqUrls = []
        tmpUrls = []
        if vidMarker not in inUrl:
            sts, data = getPage(inUrl, defaultParams)
            if sts:
                sts, match = self.cm.ph.getDataBeetwenMarkers(data, "Link do tego video:", "</a>", False)
                if sts:
                    match = self.cm.ph.getSearchGroups(match, 'href="([^"]+?)"')[0]
                else:
                    match = self.cm.ph.getSearchGroups(data, "link[ ]*?:[ ]*?'([^']+?/video/[^']+?)'")[0]
                if match.startswith("http"):
                    inUrl = match
        if vidMarker in inUrl:
            vid = self.cm.ph.getSearchGroups(inUrl + "/", "/video/([^/]+?)/")[0]
            inUrl = "https://ebd.cda.pl/620x368/" + vid
        sts, data = getPage(inUrl, defaultParams)
        if sts:
            qualities = ""
            tmp = self.cm.ph.getDataBeetwenMarkers(data, "player_data='", "'", False)[1].strip()
            if tmp == "":
                tmp = self.cm.ph.getDataBeetwenMarkers(data, 'player_data="', '"', False)[1].strip()
            try:
                tmp = clean_html(tmp).replace("&quot;", '"')
                if tmp != "":
                    data = json_loads(tmp)
                    qualities = data["video"]["qualities"]
            except Exception:
                printExc()
            printDBG("parserCDA qualities[%r]" % qualities)
            for item in qualities:
                tmpUrls.append({"name": "cda.pl " + item, "url": inUrl + "/vfilm?wersja=" + item + "&a=1&t=0"})
        if len(tmpUrls) == 0:
            tmpUrls.append({"name": "cda.pl", "url": inUrl})

        def __appendVideoUrl(params):
            if params["url"] not in uniqUrls:
                videoUrls.append(params)
                uniqUrls.append(params["url"])

        def __ca(dat):
            def rot47(s):
                x = []
                for i in range(len(s)):
                    j = ord(s[i])
                    if j >= 33 and j <= 126:
                        x.append(chr(33 + ((j + 14) % 94)))
                    else:
                        x.append(s[i])
                return "".join(x)

            def __replace(c):
                code = ord(c.group(1))
                if code <= ord("Z"):
                    tmp = 90
                else:
                    tmp = 122
                c = code + 13
                if tmp < c:
                    c -= 26
                return chr(c)

            if not self.cm.isValidUrl(dat):
                try:
                    if "uggcf" in dat:
                        dat = re.sub("([a-zA-Z])", __replace, dat)
                    else:
                        dat = rot47(urllib_unquote(dat))
                        dat = dat.replace(".cda.mp4", "").replace(".2cda.pl", ".cda.pl").replace(".3cda.pl", ".cda.pl")
                        dat = "https://" + str(dat) + ".mp4"
                    if not dat.endswith(".mp4"):
                        dat += ".mp4"
                    dat = dat.replace("0)sss", "").replace('0"d.', ".")
                except Exception:
                    dat = ""
                    printExc()
            return str(dat)

        def __jsplayer(dat):
            if self.jscode.get("data", "") == "":
                sts, self.jscode["data"] = getPage("https://ebd.cda.pl/js/player.js", defaultParams)
                if not sts:
                    return ""
            jsdata = self.jscode.get("data", "")
            jscode = self.cm.ph.getSearchGroups(jsdata, r"""var\s([a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,.*?);""")[0]
            tmp = jscode.split(",")
            jscode = ensure_str(base64.b64decode("""ZnVuY3Rpb24gbGEoYSl7fTs="""))
            jscode += self.cm.ph.getSearchGroups(jsdata, r"""(var\s[a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,[a-zA-Z]+?,.*?;)""")[0]
            for item in tmp:
                jscode += self.cm.ph.getSearchGroups(jsdata, r"(%s=function\(.*?};)" % item)[0]
            jscode += "file = '%s';" % dat
            tmp = self.cm.ph.getSearchGroups(jsdata, r"""\(this\.options,"video"\)&&\((.*?)=this\.options\.video\);""")[0] + "."
            jscode += self.cm.ph.getDataBeetwenMarkers(jsdata, "%sfile" % tmp, ";", True)[1].replace(tmp, "")
            jscode += "print(file);"
            ret = js_execute(jscode)
            if ret["sts"] and ret["code"] == 0:
                return ret["data"].strip("\n")
            return ""

        for urlItem in tmpUrls:
            if urlItem["url"].startswith("/"):
                inUrl = "https://www.cda.pl/" + urlItem["url"]
            else:
                inUrl = urlItem["url"]
            sts, pageData = getPage(inUrl, defaultParams)
            if not sts:
                continue
            tmpData = self.cm.ph.getDataBeetwenMarkers(pageData, "eval(", "</script>", False)[1]
            if tmpData != "":
                m1 = "$.get"
                if m1 in tmpData:
                    tmpData = tmpData[: tmpData.find(m1)].strip() + "</script>"
                try:
                    tmpData = unpackJSPlayerParams(tmpData, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                except Exception:
                    pass
            tmpData += pageData
            tmp = self.cm.ph.getDataBeetwenMarkers(tmpData, "player_data='", "'", False)[1].strip()
            if tmp == "":
                tmp = self.cm.ph.getDataBeetwenMarkers(tmpData, 'player_data="', '"', False)[1].strip()
            tmp = clean_html(tmp).replace("&quot;", '"')
            printDBG(">>")
            printDBG(tmp)
            printDBG("<<")
            try:
                if tmp != "":
                    _tmp = json_loads(tmp)
                    tmp = __jsplayer(_tmp["video"]["file"])
                    if "cda.pl" not in tmp and _tmp["video"]["file"]:
                        tmp = __ca(_tmp["video"]["file"])
            except Exception:
                tmp = ""
                printExc()
            if tmp == "":
                data = self.cm.ph.getDataBeetwenReMarkers(tmpData, re.compile(r"""modes['"]?[\s]*:"""), re.compile("]"), False)[1]
                data = re.compile(r"""file:[\s]*['"]([^'^"]+?)['"]""").findall(data)
            else:
                data = [tmp]
            if len(data) > 0 and data[0].startswith("http"):
                __appendVideoUrl({"name": urlItem["name"] + " flv", "url": _decorateUrl(data[0], urlItem["url"])})
            if len(data) > 1 and data[1].startswith("http"):
                __appendVideoUrl({"name": urlItem["name"] + " mp4", "url": _decorateUrl(data[1], urlItem["url"])})
            if len(data) == 0:
                data = self.cm.ph.getDataBeetwenReMarkers(tmpData, re.compile(r"video:[\s]*{"), re.compile("}"), False)[1]
                data = self.cm.ph.getSearchGroups(data, r"'(http[^']+?(?:\.mp4|\.flv)[^']*?)'")[0]
                if data != "":
                    typ = " flv "
                    if ".mp4" in data:
                        typ = " mp4 "
                    __appendVideoUrl({"name": urlItem["name"] + typ, "url": _decorateUrl(data, urlItem["url"])})
        self.jscode["data"] = ""
        return videoUrls[::-1]

    def parserDAILYMOTION(self, baseUrl):  # Partly fix 180226
        printDBG("parserDAILYMOTION %s" % baseUrl)
        COOKIE_FILE = self.COOKIE_PATH + "dailymotion.cookie"
        HTTP_HEADER = self.cm.getDefaultHeader()
        httpParams = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE, "collect_all_headers": True}
        video_id = re.search(r"(?:video=|/video/)([A-Za-z0-9]+)", baseUrl)
        if not video_id:
            printDBG("parserDAILYMOTION -- Video id not found")
            return []
        urlsTab = []
        sts, data = self.cm.getPage(baseUrl, httpParams)
        metadataUrl = "https://www.dailymotion.com/player/metadata/video/" + video_id.group(1)
        sts, data = self.cm.getPage(metadataUrl, httpParams)
        if sts:
            try:
                metadata = json_loads(data)
                error = metadata.get("error")
                if error:
                    title = error.get("title") or error["raw_message"]
                    printDBG("Error accessing metadata: %s " % title)
                    return []
                for quality, media_list in metadata["qualities"].items():
                    for m in media_list:
                        media_url = m.get("url")
                        media_type = m.get("type")
                        if not media_url or media_type == "application/vnd.lumberjack.manifest":
                            continue
                        media_url = urlparser.decorateUrl(media_url, {"Referer": baseUrl})
                        if media_type == "application/x-mpegURL":
                            tmpTab = getDirectM3U8Playlist(media_url, False, checkContent=True, sortWithMaxBitrate=99999999, cookieParams={"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True, "load_cookie": True})
                            cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
                            for tmp in tmpTab:
                                hlsUrl = self.cm.ph.getSearchGroups(tmp["url"], r"""(https?://[^'^"]+?\.m3u8[^'^"]*?)#?""")[0]
                                redirectUrl = strwithmeta(hlsUrl, {"iptv_proto": "m3u8", "Cookie": cookieHeader, "User-Agent": HTTP_HEADER["User-Agent"]})
                                urlsTab.append({"name": "dailymotion.com: %sp hls" % (tmp.get("heigth", "0")), "url": redirectUrl, "quality": tmp.get("heigth", "0")})
                        else:
                            urlsTab.append({"name": quality, "url": media_url})
            except Exception:
                printExc
        return urlsTab

    def parserVK(self, baseUrl):  # Partly work, Login not work
        printDBG("parserVK url[%s]" % baseUrl)
        COOKIE_FILE = GetCookieDir("vkcom.cookie")
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36"}
        params = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True, "load_cookie": True}

        def _doLogin(login, password):
            rm(COOKIE_FILE)
            loginUrl = "https://vk.com/login"
            sts, data = self.cm.getPage(loginUrl, params)
            if not sts:
                return False
            data = self.cm.ph.getDataBeetwenMarkers(data, '<form method="post"', "</form>", False, False)[1]
            action = self.cm.ph.getSearchGroups(data, """action=['"]([^'^"]+?)['"]""")[0]
            post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
            post_data.update({"email": login, "pass": password})
            if not self.cm.isValidUrl(action):
                return False
            params["header"]["Referr"] = loginUrl
            sts, data = self.cm.getPage(action, params, post_data)
            if not sts:
                return False
            sts, data = self.cm.getPage("https://vk.com/", params)
            if not sts:
                return False
            if "logout_link" not in data:
                return False
            return True

        if baseUrl.startswith("http://"):  # NOSONAR
            baseUrl = "https" + baseUrl[4:]
        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False
        login = config.plugins.iptvplayer.vkcom_login.value
        password = config.plugins.iptvplayer.vkcom_password.value
        try:
            vkcom_login = self.vkcom_login
            vkcom_pass = self.vkcom_pass
        except Exception:
            rm(COOKIE_FILE)
            vkcom_login = ""
            vkcom_pass = ""
            self.vkcom_login = ""
            self.vkcom_pass = ""
            printExc()
        if '<div id="video_ext_msg">' in data or vkcom_login != login or vkcom_pass != password:
            rm(COOKIE_FILE)
            self.vkcom_login = login
            self.vkcom_pass = password
            if login.strip() == "" or password.strip() == "":
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, _("To watch videos from https://vk.com/ you need to login.\nPlease fill your login and password in the IPTVPlayer configuration."), type=MessageBox.TYPE_INFO, timeout=10)
                return False
            elif not _doLogin(login, password):
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, _('Login user "%s" to https://vk.com/ failed!\nPlease check your login data in the IPTVPlayer configuration.' % login), type=MessageBox.TYPE_INFO, timeout=10)
                return False
            else:
                sts, data = self.cm.getPage(baseUrl, params)
                if not sts:
                    return False
        movieUrls = []
        item = self.cm.ph.getSearchGroups(data, r"""['"]?cache([0-9]+?)['"]?[=:]['"]?(http[^"]+?\.mp4[^;^"^']*)[;"']""", 2)
        if item[1] != "":
            cacheItem = {"name": "vk.com: " + item[0] + "p (cache)", "url": item[1].replace("\\/", "/").encode("UTF-8")}
        else:
            cacheItem = None
        tmpTab = re.findall(r"""['"]?url([0-9]+?)['"]?[=:]['"]?(http[^"]+?\.mp4[^;^"^']*)[;"']""", data)
        # prepare urls list without duplicates
        for item in tmpTab:
            item = list(item)
            if item[1].endswith("&amp"):
                item[1] = item[1][:-4]
            item[1] = item[1].replace("\\/", "/")
            found = False
            for urlItem in movieUrls:
                if item[1] == urlItem["url"]:
                    found = True
                    break
            if not found:
                movieUrls.append({"name": "vk.com: " + item[0] + "p", "url": item[1].encode("UTF-8")})
        # move default format to first position in urls list
        # default format should be a configurable
        DEFAULT_FORMAT = "vk.com: 720p"
        defaultItem = None
        for idx in range(len(movieUrls)):
            if movieUrls[idx]["name"] == DEFAULT_FORMAT:
                defaultItem = movieUrls[idx]
                del movieUrls[idx]
                break
        movieUrls = movieUrls[::-1]
        if None is not defaultItem:
            movieUrls.insert(0, defaultItem)
        if None is not cacheItem:
            movieUrls.insert(0, cacheItem)
        return movieUrls

    def parserYOUTUBE(self, url):
        def __getLinkQuality(itemLink):
            val = itemLink["format"].split("x", 1)[0].split("p", 1)[0]
            try:
                val = int(val) if "x" in itemLink["format"] else int(val) - 1
                return val
            except Exception:
                return 0

        if None is not self.getYTParser():
            try:
                formats = config.plugins.iptvplayer.ytformat.value
                height = config.plugins.iptvplayer.ytDefaultformat.value
                dash = self.getYTParser().isDashAllowed()
                vp9 = self.getYTParser().isVP9Allowed()
                age = self.getYTParser().isAgeGateAllowed()
            except Exception:
                printDBG("parserYOUTUBE default ytformat or ytDefaultformat not available here")
                formats = "mp4"
                height = "360"
                dash = False
                vp9 = False
                age = False
            tmpTab, dashTab = self.getYTParser().getDirectLinks(url, formats, dash, dashSepareteList=True, allowVP9=vp9, allowAgeGate=age)
            videoUrls = []
            for item in tmpTab:
                url = strwithmeta(item["url"], {"youtube_id": item.get("id", "")})
                videoUrls.append({"name": "YouTube | {0}: {1}".format(item["ext"], item["format"]), "url": url, "format": item.get("format", "")})
            for item in dashTab:
                url = strwithmeta(item["url"], {"youtube_id": item.get("id", "")})
                if item.get("ext", "") == "mpd":
                    videoUrls.append({"name": "YouTube | dash: " + item["name"], "url": url, "format": item.get("format", "")})
                else:
                    videoUrls.append({"name": "YouTube | custom dash: " + item["format"], "url": url, "format": item.get("format", "")})
            videoUrls = CSelOneLink(videoUrls, __getLinkQuality, int(height)).getSortedLinks()
            return videoUrls
        return False

    def parserFILEONETV(self, baseUrl):  # check 030126
        printDBG("parserFILEONETV baseUrl[%s]" % baseUrl)
        url = baseUrl.replace("show/player", "v")
        sts, data = self.cm.getPage(url)
        if not sts:
            return False
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "setup({", "});", True)[1]
        videoUrl = self.cm.ph.getSearchGroups(tmp, """file[^"^']+?["'](https?://[^"^']+?)['"]""")[0]
        if videoUrl == "":
            videoUrl = self.cm.ph.getSearchGroups(data, r"""<source[^>]+?src=([^'^"]+?)\s[^>]*?video/mp4""")[0]
        if videoUrl.startswith("//"):
            videoUrl = "https:" + videoUrl
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserUSERSCLOUDCOM(self, baseUrl):  # Need test
        printDBG("parserUSERSCLOUDCOM baseUrl[%s]\n" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"}
        COOKIE_FILE = GetCookieDir("userscloudcom.cookie")
        rm(COOKIE_FILE)
        params = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True, "load_cookie": True}
        sts, data = self.cm.getPage(baseUrl, params)
        cUrl = self.cm.meta["url"]
        errorTab = ["File Not Found", "File was deleted"]
        for errorItem in errorTab:
            if errorItem in data:
                SetIPTVPlayerLastHostError(_(errorItem))
                break
        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="player_code"', "</div>", True)[1]
        tmp = self.cm.ph.getDataBeetwenMarkers(tmp, ">eval(", "</script>")[1]
        # unpack and decode params from JS player script code
        tmp = unpackJSPlayerParams(tmp, VIDUPME_decryptPlayerParams)
        if tmp is not None:
            data = tmp + data
        videoUrl = self.cm.ph.getSearchGroups(data, r"""['"]?file['"]?[ ]*:[ ]*['"]([^"^']+)['"],""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        videoUrl = self.cm.ph.getSearchGroups(data, """<source[^>]+?src=['"]([^'^"]+?)['"][^>]+?["']video""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        sts, data = self.cm.ph.getDataBeetwenMarkers(data, 'method="POST"', "</Form>", False, False)
        if not sts:
            return False
        post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
        params["header"]["Referer"] = cUrl
        params["max_data_size"] = 0
        sts, data = self.cm.getPage(cUrl, params, post_data)
        if sts and "text" not in self.cm.meta["content-type"]:
            return self.cm.meta["url"]

    def parserUPZONECC(self, baseUrl):  # Need test
        printDBG("parserUPZONECC baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        if "/embed" not in cUrl:
            url = self.cm.getFullUrl("/embed/" + cUrl.rsplit("/", 1)[(-1)], cUrl)
            sts, tmp = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
            if not sts:
                return False
            data += tmp
            cUrl = self.cm.meta["url"]
        data = ph.search(data, """['"]([a-zA-Z0-9=]{128,512})['"]""")[0]
        js_params = [{"path": GetJSScriptFile("upzonecc.byte")}]
        js_params.append({"code": "print(cnc(atob('%s')));" % data})
        ret = js_execute_ext(js_params)
        url = self.cm.getFullUrl(ret["data"].strip(), cUrl)
        return strwithmeta(url, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})

    def parser1FICHIERCOM(self, baseUrl):  # Need test
        printDBG("parser1FICHIERCOM baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {
            "User-Agent": "Mozilla/%s%s" % (pageParser.FICHIER_DOWNLOAD_NUM, pageParser.FICHIER_DOWNLOAD_NUM),
            "Accept": "*/*",
            "Accept-Language": "pl,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
        }
        pageParser.FICHIER_DOWNLOAD_NUM += 1
        COOKIE_FILE = GetCookieDir("1fichiercom.cookie")
        params = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "load_cookie": True, "save_cookie": True}
        rm(COOKIE_FILE)
        login = config.plugins.iptvplayer.fichiercom_login.value
        password = config.plugins.iptvplayer.fichiercom_password.value
        logedin = False
        if login != "" and password != "":
            url = "https://1fichier.com/login.pl"
            post_data = {"mail": login, "pass": password, "lt": "on", "purge": "on", "valider": "Send"}
            params["header"]["Referer"] = url
            sts, data = self.cm.getPage(url, params, post_data)
            if sts:
                if "My files" in data:
                    logedin = True
                else:
                    error = clean_html(self.cm.ph.getDataBeetwenMarkers(data, '<div class="bloc2"', "</div>")[1])
                    sessionEx = MainSessionWrapper()
                    sessionEx.waitForFinishOpen(MessageBox, _("Login on {0} failed.").format("https://1fichier.com/") + "\n" + error, type=MessageBox.TYPE_INFO, timeout=5)
        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False
        error = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "bloc"), ("</div", ">"), False)[1])
        if error != "":
            SetIPTVPlayerLastHostError(error)
        data = self.cm.ph.getDataBeetwenNodes(data, ("<form", ">", "post"), ("</form", ">"), caseSensitive=False)[1]
        printDBG("++++")
        action = self.cm.ph.getSearchGroups(data, """action=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, "<input", ">", caseSensitive=False)
        all_post_data = {}
        for item in tmp:
            name = self.cm.ph.getSearchGroups(item, """name=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
            value = self.cm.ph.getSearchGroups(item, """value=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
            all_post_data[name] = value
        if "use_credits" in data:
            all_post_data["use_credits"] = "on"
            logedin = True
        else:
            logedin = False
        error = clean_html(self.cm.ph.getDataBeetwenMarkers(data, '<span style="color:red">', "</div>")[1])
        if error != "" and not logedin:
            timeout = self.cm.ph.getSearchGroups(error, r"""wait\s+([0-9]+)\s+([a-zA-Z]{3})""", 2, ignoreCase=True)
            printDBG(timeout)
            if timeout[1].lower() == "min":
                timeout = int(timeout[0]) * 60
            elif timeout[1].lower() == "sec":
                timeout = int(timeout[0])
            else:
                timeout = 0
            printDBG(timeout)
            if timeout > 0:
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, error, type=MessageBox.TYPE_INFO, timeout=timeout)
            else:
                SetIPTVPlayerLastHostError(error)
        else:
            SetIPTVPlayerLastHostError(error)
        post_data = {"dl_no_ssl": "on", "adzone": all_post_data["adzone"]}
        action = urljoin(baseUrl, action)
        if logedin:
            params["max_data_size"] = 0
            params["header"]["Referer"] = baseUrl
            sts = self.cm.getPage(action, params, post_data)[0]
            if not sts:
                return False
            if "text" not in self.cm.meta.get("content-type", ""):
                videoUrl = self.cm.meta["url"]
            else:
                SetIPTVPlayerLastHostError(error)
                videoUrl = ""
        else:
            params["header"]["Referer"] = baseUrl
            sts, data = self.cm.getPage(action, params, post_data)
            if not sts:
                return False
            videoUrl = self.cm.ph.getSearchGroups(data, """<a[^>]+?href=['"](https?://[^'^"]+?)['"][^>]+?ok btn-general""")[0]
        error = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "bloc"), ("</div", ">"), False)[1])
        if error != "":
            SetIPTVPlayerLastHostError(error)
        printDBG(">>> videoUrl[%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserFILECLOUDIO(self, baseUrl):  # Need test
        printDBG("parserFILECLOUDIO baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        referer = baseUrl.meta.get("Referer", baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        if referer != "":
            HTTP_HEADER["Referer"] = referer
        paramsUrl = {"header": HTTP_HEADER, "with_metadata": True}
        sts, data = self.cm.getPage(baseUrl, paramsUrl)
        if not sts:
            return False
        cUrl = data.meta["url"]
        sitekey = self.cm.ph.getSearchGroups(data, r"""['"]?sitekey['"]?\s*?:\s*?['"]([^"^']+?)['"]""")[0]
        if sitekey != "":
            obj = UnCaptchaReCaptcha(lang=GetDefaultLang())
            obj.HTTP_HEADER.update({"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            token = obj.processCaptcha(sitekey)
            if token == "":
                return False
        else:
            token = ""
        requestUrl = self.cm.ph.getSearchGroups(data, r"""requestUrl\s*?=\s*?['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
        requestUrl = self.cm.getFullUrl(requestUrl, self.cm.getBaseUrl(cUrl))
        data = self.cm.ph.getDataBeetwenMarkers(data, "$.ajax(", ")", caseSensitive=False)[1]
        data = self.cm.ph.getSearchGroups(data, r"""data['"]?:\s*?(\{[^\}]+?\})""", ignoreCase=True)[0]
        data = data.replace("response", '"%s"' % token).replace("'", '"')
        post_data = json_loads(data)
        paramsUrl["header"].update({"Referer": cUrl, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"})
        sts, data = self.cm.getPage(requestUrl, paramsUrl, post_data)
        if not sts:
            return False
        data = json_loads(data)
        if self.cm.isValidUrl(data["downloadUrl"]):
            return strwithmeta(data["downloadUrl"], {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
        return False

    def parserGOOGLE(self, baseUrl):  # Need test
        printDBG("parserGOOGLE baseUrl[%s]" % baseUrl)
        urltab = []
        _VALID_URL = r"https?://(?:(?:docs|drive)\.google\.com/(?:uc\?.*?id=|file/d/)|video\.google\.com/get_player\?.*?docid=)(?P<id>[a-zA-Z0-9_-]{28,})"
        mobj = re.match(_VALID_URL, baseUrl)
        try:
            video_id = mobj.group("id")
            linkUrl = "https://docs.google.com/file/d/" + video_id
        except Exception:
            linkUrl = baseUrl
        _FORMATS_EXT = {
            "5": "flv",
            "6": "flv",
            "13": "3gp",
            "17": "3gp",
            "18": "mp4",
            "22": "mp4",
            "34": "flv",
            "35": "flv",
            "36": "3gp",
            "37": "mp4",
            "38": "mp4",
            "43": "webm",
            "44": "webm",
            "45": "webm",
            "46": "webm",
            "59": "mp4",
        }
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = linkUrl
        COOKIE_FILE = GetCookieDir("google.cookie")
        defaultParams = {"header": HTTP_HEADER, "use_cookie": True, "load_cookie": False, "save_cookie": True, "cookiefile": COOKIE_FILE}
        sts, data = self.cm.getPage(linkUrl, defaultParams)
        if not sts:
            return False
        cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
        fmtDict = {}
        fmtList = self.cm.ph.getSearchGroups(data, '"fmt_list"[:,]"([^"]+?)"')[0]
        fmtList = fmtList.split(",")
        for item in fmtList:
            item = self.cm.ph.getSearchGroups(item, "([0-9]+?)/([0-9]+?x[0-9]+?)/", 2)
            if item[0] != "" and item[1] != "":
                fmtDict[item[0]] = item[1]
        data = self.cm.ph.getSearchGroups(data, '"fmt_stream_map"[:,]"([^"]+?)"')[0]
        data = data.split(",")
        for item in data:
            item = item.split("|")
            printDBG(">> type[%s]" % item[0])
            if "mp4" in _FORMATS_EXT.get(item[0], ""):
                try:
                    quality = int(fmtDict.get(item[0], "").split("x", 1)[-1])
                except Exception:
                    quality = 0
                urltab.append({"name": "drive.google.com: %s" % fmtDict.get(item[0], "").split("x", 1)[-1] + "p", "quality": quality, "url": strwithmeta(unicode_escape(item[1]), {"Cookie": cookieHeader, "Referer": "https://youtube.googleapis.com/", "User-Agent": HTTP_HEADER["User-Agent"]})})
        urltab.sort(key=lambda item: item["quality"], reverse=True)
        return urltab

    def parserARCHIVEORG(self, linkUrl):  # Need test
        printDBG("parserARCHIVEORG linkUrl[%s]" % linkUrl)
        urltab = []
        sts, data = self.cm.getPage(linkUrl)
        if sts:
            data = self.cm.ph.getSearchGroups(data, r'"sources":\[([^]]+?)]')[0]
            data = "[%s]" % data
            try:
                data = json_loads(data)
                for item in data:
                    if item["type"] == "mp4":
                        urltab.append({"name": "archive.org: " + item["label"], "url": "https://archive.org" + item["file"]})
            except Exception:
                printExc()
        return urltab

    def parserWEBCAMERAPL(self, baseUrl):  # Need test
        printDBG("parserWEBCAMERAPL baseUrl[%s]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        tmp = self.cm.ph.getSearchGroups(data, """stream-player__video['"] data-src=['"]([^"^']+?)['"]""")[0]
        if tmp == "":
            tmp = self.cm.ph.getSearchGroups(data, """STREAM_PLAYER_CONFIG[^}]+?['"]video_src['"]:['"]([^"^']+?)['"]""")[0].replace(r"\/", "/")
        if tmp != "":
            tmp = codecs.decode(tmp, "rot13")
            return getDirectM3U8Playlist(tmp, checkContent=True)
        return False

    def parserTVP(self, baseUrl):
        printDBG("parserTVP baseUrl[%s]" % baseUrl)
        vidTab = []
        try:
            from Plugins.Extensions.IPTVPlayer.hosts.hosttvpvod import TvpVod

            vidTab = TvpVod().getLinksForVideo({"url": baseUrl})
        except Exception:
            printExc()
        return vidTab

    def parserBBC(self, baseUrl):  # Need test
        printDBG("parserBBC baseUrl[%r]" % baseUrl)
        vpid = self.cm.ph.getSearchGroups(baseUrl, "/vpid/([^/]+?)/")[0]
        if vpid == "":
            data = self.getBBCIE()._real_extract(baseUrl)
        else:
            formats, subtitles = self.getBBCIE()._download_media_selector(vpid)
            data = {"formats": formats, "subtitles": subtitles}
        subtitlesTab = []
        for sub in data.get("subtitles", []):
            if self.cm.isValidUrl(sub.get("url", "")):
                subtitlesTab.append({"title": _(sub["lang"]), "url": sub["url"], "lang": sub["lang"], "format": sub["ext"]})
        videoUrls = []
        hlsLinks = []
        mpdLinks = []
        for vidItem in data["formats"]:
            if "url" in vidItem:
                url = self.getBBCIE().getFullUrl(vidItem["url"].replace("&amp;", "&"))
                if vidItem.get("ext", "") == "hls" and len(hlsLinks) == 0:
                    hlsLinks.extend(getDirectM3U8Playlist(url, False, checkContent=True))
                elif vidItem.get("ext", "") == "mpd" and len(mpdLinks) == 0:
                    mpdLinks.extend(getMPDLinksWithMeta(url, False))
        tmpTab = [hlsLinks, mpdLinks]
        if config.plugins.iptvplayer.bbc_prefered_format.value == "dash":
            tmpTab.reverse()
        max_bitrate = int(config.plugins.iptvplayer.bbc_default_quality.value)
        for item in tmpTab:

            def __getLinkQuality(itemLink):
                try:
                    return int(itemLink["height"])
                except Exception:
                    return 0

            item = CSelOneLink(item, __getLinkQuality, max_bitrate).getSortedLinks()
            if config.plugins.iptvplayer.bbc_use_default_quality.value:
                videoUrls.append(item[0])
                break
            videoUrls.extend(item)
        if subtitlesTab:
            for idx in range(len(videoUrls)):
                videoUrls[idx]["url"] = strwithmeta(videoUrls[idx]["url"], {"external_sub_tracks": subtitlesTab})
        return videoUrls

    def parserMEDIAFIRECOM(self, baseUrl):  # Need test
        printDBG("parserMEDIAFIRECOM baseUrl[%s]" % baseUrl)
        HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0", "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
        sts, data = self.cm.getPage(baseUrl, {"header": HEADER})
        if not sts:
            return False
        data = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", '"download_link"'), ("</div", ">"))[1]
        data = self.cm.ph.getDataBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)[1]
        jscode = """window=this;document={};document.write=function(){print(arguments[0]);}"""
        ret = js_execute(jscode + "\n" + data)
        if ret["sts"] and ret["code"] == 0:
            videoUrl = self.cm.ph.getSearchGroups(ret["data"], """href=['"]([^"^']+?)['"]""")[0]
            if self.cm.isValidUrl(videoUrl):
                return videoUrl
        return False

    def parserVIDLOADCO(self, baseUrl):  # Need test
        printDBG("parserVIDLOADCO baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        domain = self.cm.getBaseUrl(cUrl, True)
        urltab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "sources", "]", False)
        for sourceData in data:
            sourceData = self.cm.ph.getAllItemsBeetwenMarkers(sourceData, "{", "}")
            for item in sourceData:
                marker = item.lower()
                if "video/mp4" not in marker and "video/x-flv" not in marker and "x-mpeg" not in marker:
                    continue
                item = item.replace("\\/", "/")
                url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, r"""(?:src|file)['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0], self.cm.getBaseUrl(cUrl))
                types = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                label = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                printDBG(url)
                if url == "":
                    continue
                url = strwithmeta(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": cUrl})
                if "x-mpeg" in marker:
                    urltab.extend(getDirectM3U8Playlist(url, checkContent=True))
                else:
                    urltab.append({"name": "[%s] %s %s" % (types, domain, label), "url": url})
        return urltab

    def parserSOUNDCLOUDCOM(self, baseUrl):  # Need test
        printDBG("parserSOUNDCLOUDCOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"with_metadata": True, "header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = data.meta["url"]
        tarckId = self.cm.ph.getSearchGroups(data, r"""tracks\:([0-9]+)""")[0]
        url = self.cm.ph.getSearchGroups(data, r"""['"](https?://[^'^"]+?/widget\-[^'^"]+?\.js)""")[0]
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return False
        clinetIds = self.cm.ph.getSearchGroups(data, r'''client_id\:[A-Za-z]+?\?"([^"]+?)"\:"([^"]+?)"''', 2)
        baseUrl = "https://api.soundcloud.com/i1/tracks/%s/streams?client_id=" % tarckId
        jsData = None
        for clientId in clinetIds:
            url = baseUrl + clientId
            sts, data = self.cm.getPage(url, urlParams)
            if not sts:
                continue
            try:
                jsData = json_loads(data)
            except Exception:
                printExc()
        urls = []
        baseName = urlparser.getDomain(cUrl)
        for key in jsData:
            if "preview" in key:
                continue
            url = jsData[key]
            if self.cm.isValidUrl(url):
                urls.append({"name": baseName + " " + key, "url": url})
        return urls

    def parserFILEFACTORYCOM(self, baseUrl):  # Need test
        printDBG("parserFILEFACTORYCOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        domain = urlparser.getDomain(cUrl)
        videoUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, r"""data\-href=['"]([^'^"]+?)['"]""")[0], self.cm.meta["url"])
        if not videoUrl:
            return False
        sleep_time = self.cm.ph.getSearchGroups(data, r"""data\-delay=['"]([0-9]+?)['"]""")[0]
        try:
            GetIPTVSleep().Sleep(int(sleep_time))
        except Exception:
            printExc()
        sts, data = self.cm.getPage(videoUrl, {"max_data_size": 200 * 1024})
        if sts:
            if "text" not in self.cm.meta["content-type"]:
                return [{"name": domain, "url": videoUrl}]
            msg = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "box-message"), ("</div", ">"), False)[1])
            SetIPTVPlayerLastHostError(msg)
        return False

    def parserMEDIASET(self, baseUrl):  # Need test
        printDBG("parserMEDIASET baseUrl[%r]" % baseUrl)
        guid = ph.search(baseUrl, r"""https?://(?:(?:www|static3)\.)?mediasetplay\.mediaset\.it/(?:(?:video|on-demand)/(?:[^/]+/)+[^/]+_|player/index\.html\?.*?\bprogramGuid=)([0-9A-Z]{16})""")[0]
        if not guid:
            return
        tp_path = "PR1GhC/media/guid/2702976343/" + guid
        uniqueUrls = set()
        retTab = []
        for asset_type in ("SD", "HD"):
            for f in "MPEG4":
                url = "https://link.theplatform.%s/s/%s?mbr=true&formats=%s&assetTypes=%s" % ("eu", tp_path, f, asset_type)
                sts, data = self.cm.getPage(url, post_data={"format": "SMIL"})
                if not sts:
                    continue
                if "GeoLocationBlocked" in data:
                    SetIPTVPlayerLastHostError(ph.getattr(data, "abstract"))
                tmp = ph.findall(data, "<video", ">")
                for item in tmp:
                    url = ph.getattr(item, "src")
                    if not self.cm.isValidUrl(url):
                        continue
                    if url not in uniqueUrls:
                        uniqueUrls.add(url)
                        retTab.append({"name": "%s - %s" % (f, asset_type), "url": url})
        return retTab

    def parserVIDMOLYME(self, baseUrl):  # fix 150126
        printDBG("parserVIDMOLYME baseUrl[%r]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader()
        baseUrl = strwithmeta(baseUrl)
        if "embed" not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{12})[/.]")[0]
            baseUrl = "{}/embed-{}.html".format(urlparser.getDomain(baseUrl, False), video_id)
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        if "<title>Please wait</title>" in data:
            url_id = self.cm.ph.getSearchGroups(data, r"\?g=([a-fA-F0-9]+)")[0]
            url = "{}?g={}".format(baseUrl, url_id)
            HTTP_HEADER.update({"Referer": baseUrl, "Upgrade-Insecure-Requests": "1"})
            sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return False
        url = self.cm.ph.getSearchGroups(data, """sources[^'^"]*?['"]([^'^"]+?)['"]""")[0]
        if url:
            host = urlparser.getDomain(baseUrl, False)
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=999999999))
        return urltab

    def parserVOESX(self, baseUrl):
        def voe_decode(ct):
            txt = "".join(chr((ord(i) - 52) % 26 + 65) if 65 <= ord(i) <= 90 else chr((ord(i) - 84) % 26 + 97) if 97 <= ord(i) <= 122 else i for i in ct)
            lut = [r"#&", r"%?", r"\*~", r"~@", r"\^\^", r"!!", r"@$"]
            for pattern in lut:
                txt = re.sub(pattern, "_", txt)
            txt = "".join(txt.split("_"))

            def fix_b64_padding(s):
                return s + "=" * (-len(s) % 4)

            try:
                step1 = base64.b64decode(fix_b64_padding(txt)).decode()
                step2 = "".join(chr(ord(c) - 3) for c in step1)
                final = base64.b64decode(fix_b64_padding(step2[::-1])).decode()
                return json_loads(final)
            except Exception as e:
                printDBG(e)
                return ""

        printDBG("parserVOESX baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        if "const currentUrl" in data:
            url = ph.search(data, r"""window.location.href\s*=\s*['"]([^"^']+?)['"]""")[0]
            sts, data = self.cm.getPage(url)
            if not sts:
                return False
        r = re.search(r"""['"]?hls['"]?\s*?:\s*?['"]([^'^"]+?)['"]""", data)
        if r:
            hlsUrl = ensure_str(base64.b64decode(r.group(1)))
            if hlsUrl.startswith("//"):
                hlsUrl = "https:" + hlsUrl
            if self.cm.isValidUrl(hlsUrl):
                params = {"iptv_proto": "m3u8", "Referer": baseUrl, "Origin": urlparser.getDomain(baseUrl, False)}
                hlsUrl = urlparser.decorateUrl(hlsUrl, params)
                return getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        else:
            r = re.search(r'\w+="([^"]+)";function', data)
            if not r:
                r = re.search(r"""application/json">[^>]"([^"]+)""", data)
            urltab = []
            if r:
                r = voe_decode(ensure_str(r.group(1)))
                if r:
                    subtitles = [{"title": "", "lang": x.get("label"), "url": "https://{0}{1}".format(baseUrl.split("/")[2], x.get("file"))} for x in r.get("captions") if x.get("kind") == "captions"]
                    key_list = ["source", "file", "direct_access_url"]
                    for key in key_list:
                        if key in r:
                            url = r[key]
                            if ".m3u8" in url:
                                url = urlparser.decorateUrl(url, {"iptv_proto": "m3u8", "Referer": baseUrl, "Origin": urlparser.getDomain(baseUrl, False), "external_sub_tracks": subtitles})
                                urltab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
                            else:
                                if subtitles:
                                    url = urlparser.decorateUrl(url, {"external_sub_tracks": subtitles})
                                urltab.append({"name": "MP4", "url": url})
            return urltab

    def parserVEEV(self, baseUrl):  # update 211225
        printDBG("parserVEEV baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER.update({"Referer": baseUrl, "Origin": urlparser.getDomain(baseUrl, False), "Accept-Language": "en-US,en;q=0.5"})
        urlParams = {"header": HTTP_HEADER}

        def veev_decode(etext):
            result = []
            lut = {}
            n = 256
            c = etext[0]
            result.append(c)
            for char in etext[1:]:
                code = ord(char)
                nc = char if code < 256 else lut.get(code, c + c[0])
                result.append(nc)
                lut[n] = c + nc[0]
                n += 1
                c = nc
            return "".join(result)

        def js_int(x):
            return int(x) if x.isdigit() else 0

        def build_array(encoded_string):
            d = []
            c = list(encoded_string)
            count = js_int(c.pop(0))
            while count:
                current_array = []
                for x in range(count):
                    current_array.insert(0, js_int(c.pop(0)))
                d.append(current_array)
                count = js_int(c.pop(0))
            return d

        def decode_url(etext, tarray):
            ds = etext
            for t in tarray:
                if t == 1:
                    ds = ds[::-1]
                ds = unhexlify(ds).decode("utf8")
                ds = ds.replace("dXRmOA==", "")
            return ds

        urltab = []
        sub_tracks = []
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        url = self.cm.meta.get("url", "")
        if url != "":
            baseUrl = url
        items = re.findall(r"""[\.\s'](?:fc|_vvto\[[^\]]*)(?:['\]]+)?\s*[:=]\s*['"]([^'"]+)""", data)
        if items:
            for f in items[::-1]:
                ch = veev_decode(ensure_binary(f).decode("utf8"))
                if ch != f:
                    params = {"op": "player_api", "cmd": "gi", "file_code": baseUrl.split("/")[-1], "ch": ch, "ie": 1}
                    durl = self.cm.getFullUrl("/dl", baseUrl) + "?" + urllib_urlencode(params)
                    sts, jresp = self.cm.getPage(durl, urlParams)
                    if not sts:
                        return []
                    jresp = json_loads(jresp).get("file")
                    if jresp and jresp.get("file_status") == "OK":
                        sub_tracks = [{"title": sub.get("label"), "url": sub.get("src"), "lang": sub.get("language")} for sub in jresp.get("captions_list", [])]
                        url = decode_url(veev_decode(ensure_binary(jresp.get("dv")[0].get("s")).decode("utf8")), build_array(ch)[0])
                        if url:
                            url = strwithmeta(url, HTTP_HEADER)
                            urltab.append({"name": "MP4", "url": urlparser.decorateUrl(url, {"external_sub_tracks": sub_tracks})})
        return urltab

    def parserDOOD(self, baseUrl):  # update 240925
        urlsTab = []
        sub_tracks = []
        printDBG("parserDOOD baseUrl [%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        urlParams = {"header": HTTP_HEADER}
        urls = ["all3do.com", "d0000d.com", "d000d.com", "d0o0d.com", "d-s.io", "do0od.com", "dooodster.com", "doodstream.com", "doply.net", "dooood.com", "do7go.com", "ds2play.com", "ds2video.com", "dood.cx", "dood.la", "dood.li", "dood.pm", "dood.re", "dood.sh", "dood.so", "dood.stream", "dood.to", "dood.watch", "dood.work", "dood.wf", "dood.ws", "dood.yt", "doods.pro", "doodcdn.io", "vide0.net", "vidply.com", "vvide0.com"]
        for url in urls:
            if url in baseUrl:
                baseUrl = baseUrl.replace(url, "dsvplay.com")
        host = "https://%s" % urlparser.getDomain(baseUrl, True)
        if "/d/" in baseUrl:
            sts, data = self.cm.getPage(baseUrl, urlParams)
            if not sts:
                return []
            url = self.cm.ph.getSearchGroups(data, 'iframe src="([^"]+)')[0]
            baseUrl = host + url
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        sub = re.findall(r"""dsplayer\.addRemoteTextTrack\({src:'([^']+)',\s*label:'([^']*)',kind:'captions'""", data)
        if sub:
            sub_tracks = [{"title": "", "url": "https:" + src if src.startswith("//") else src, "lang": label} for src, label in sub if len(label) > 1]
        match = re.search(r"""dsplayer\.hotkeys[^']+'([^']+).+?function\s*makePlay.+?return[^?]+([^"]+)""", data, re.DOTALL)
        if match:
            token = match.group(2)
            sts, data = self.cm.getPage("%s%s" % (host, match.group(1)), urlParams)
            if not sts:
                return []
            url = data.strip() if "cloudflarestorage." in data else random_seed(10, data) + token + str(int(time.time() * 1000))
            url = urlparser.decorateUrl(url, {"external_sub_tracks": sub_tracks, "User-Agent": urlParams["header"]["User-Agent"], "Referer": baseUrl})
            urlsTab.append({"name": "mp4", "url": url})
        return urlsTab

    def parserSTREAMTAPE(self, baseUrl):  # check 150625
        printDBG("parserSTREAMTAPE baseUrl[%s]" % baseUrl)
        urltabs = []
        subTracks = []
        COOKIE_FILE = GetCookieDir("streamtape.cookie")
        httpParams = {"header": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0", "Accept": "*/*", "Accept-Encoding": "gzip", "Referer": baseUrl.meta.get("Referer", baseUrl)}, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": COOKIE_FILE}
        sts, data = self.cm.getPage(baseUrl, httpParams)
        code = self.cm.meta["status_code"]
        if sts and code != 404:
            subTracksData = self.cm.ph.getAllItemsBeetwenMarkers(data, "<track ", ">", False, False)
            for track in subTracksData:
                if 'kind="captions"' not in track:
                    continue
                subUrl = self.cm.ph.getSearchGroups(track, 'src="([^"]+?)"')[0]
                if subUrl.startswith("/"):
                    subUrl = urlparser.getDomain(baseUrl, False) + subUrl
                if subUrl.startswith("http"):
                    subLang = self.cm.ph.getSearchGroups(track, 'srclang="([^"]+?)"')[0]
                    subLabel = self.cm.ph.getSearchGroups(track, 'label="([^"]+?)"')[0]
                    subTracks.append({"title": subLabel + "_" + subLang, "url": subUrl, "lang": subLang, "format": "srt"})
            t = self.cm.ph.getSearchGroups(data, """innerHTML = ([^;]+?);""")[0] + ";"
            printDBG("parserSTREAMTAPE t[%s]" % t)
            t = t.replace(".substring(", "[", 1).replace(").substring(", ":][").replace(");", ":]") + "[1:]"
            t = eval(t)
            if t.startswith("/"):
                t = "https:/" + t
            if self.cm.isValidUrl(t):
                cookieHeader = self.cm.getCookieHeader(COOKIE_FILE, [], False)
                params = {"Cookie": cookieHeader, "Referer": httpParams["header"]["Referer"], "User-Agent": httpParams["header"]["User-Agent"]}
                params["external_sub_tracks"] = subTracks
                t = urlparser.decorateUrl(t, params)
                params = {"name": "link", "url": t}
                urltabs.append(params)
        return urltabs

    def parserSST(self, url):  # check 150625
        printDBG("parserSST baseUrl[%s]" % url)
        sts, data = self.cm.getPage(url)
        if not sts:
            return []
        urltab = []
        url = re.search('file:"([^"]+)', data)
        if url:
            url = url.group(1)
            if "[" in url:
                urls = re.findall(r"\[(\d+p)\](https?://[^\s,]+)", url)
                urltab.extend({"name": quality, "url": url} for quality, url in urls)
            else:
                urltab.append({"name": "360p", "url": url})
        return urltab

    def parserSBS(self, baseUrl):  # update 020126
        printDBG("parserSBS baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        referer = baseUrl.meta.get("Referer")
        HTTP_HEADER["Referer"] = "https://%s/" % baseUrl.split("/")[2]
        urlParams = {"header": HTTP_HEADER}
        if "#" in baseUrl and referer:
            host = referer.split("/")[2]
            url = urlparser.getDomain(baseUrl, False)
            baseUrl = "%sapi/v1/video?id=%s&w=1904&h=969&r=%s" % (url, baseUrl.split("#")[1], host)
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        data = unhexlify(data[:-1])
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(b"\x6b\x69\x65\x6d\x74\x69\x65\x6e\x6d\x75\x61\x39\x31\x31\x63\x61", b"\x31\x32\x33\x34\x35\x36\x37\x38\x39\x30\x6f\x69\x75\x79\x74\x72"))
        data = decrypter.feed(data)
        data += decrypter.feed()
        data = data.decode("utf-8")
        data = json_loads(data)
        hls = data.get("source")
        subTracks = []
        for lang, src in data.get("subtitle", {}).items():
            if src.startswith("/"):
                src = url[:-1] + src.split("#")[0]
            subTracks.append({"title": "", "url": src, "lang": lang})
        urltab = []
        if hls:
            hls = urlparser.decorateUrl(hls, {"iptv_proto": "m3u8", "User-Agent": HTTP_HEADER["User-Agent"], "Referer": url, "Origin": url[:-1], "external_sub_tracks": subTracks})
            urltab.extend(getDirectM3U8Playlist(hls))
        return urltab

    def parserVINOVO(self, baseUrl):  # fix 15.06.25
        printDBG("parserVINOVO baseUrl[%s]" % baseUrl)
        COOKIE_FILE = self.COOKIE_PATH + "vinovo.cookie"
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"}
        sts, data = self.cm.getPage(baseUrl.replace("/d/", "/e/"), {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE})
        if not sts:
            return []
        token = re.search(r'name="token"\s*content="([^"]+)', data)
        video_data = re.search(r'data-base="([^"]+)', data)
        filecode = re.search(r'file_code"\s*(?:content="([^"]*)"|\s*="([^"]*)")>', data)
        if token and video_data and filecode:
            rurl = urljoin(baseUrl, "/")
            recaptcha = girc(data, rurl)
            HTTP_HEADER.update({"Origin": rurl[:-1], "Referer": baseUrl, "X-Requested-With": "XMLHttpRequest"})
            post_data = {"token": token.group(1), "recaptcha": recaptcha}
            api_url = "https://vinovo.to/api/file/url/{0}".format(filecode.group(1))
            sts, data = self.cm.getPage(api_url, {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": False, "load_cookie": True, "cookiefile": COOKIE_FILE}, post_data)
            if not sts:
                return []
            resp_json = json_loads(data)
            if resp_json.get("status") == "ok":
                HTTP_HEADER.pop("X-Requested-With")
                vid_src = "{0}/stream/{1}".format(video_data.group(1), resp_json.get("token"))
                return [{"name": "MP4", "url": urlparser.decorateUrl(vid_src, HTTP_HEADER)}]
        return []

    def parserSTREAMEMBED(self, baseUrl):  # fix 191025
        urltab = []
        printDBG("parserSTREAMEMBED baseUrl[%s]" % baseUrl)
        headers = self.cm.getDefaultHeader()
        host = urlparser.getDomain(baseUrl, False)
        COOKIE_FILE = self.COOKIE_PATH + "streamembed.cookie"
        sts, data = self.cm.getPage(baseUrl, {"header": headers, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE})
        if not sts:
            return []
        data = re.search(r"var\s*video\s*=\s*(.*?);\s", data)
        if data:
            data = json_loads(data.group(1))
            url = "{}m3u8/{}/{}/master.txt?s=1&id={}&cache=1".format(host, data.get("uid"), data.get("md5"), data.get("id"))
            headers["Referer"] = host
            headers["Origin"] = host[:-1]
            headers["Accept"] = "*/*"
            urltab = getDirectM3U8Playlist(url, checkExt=False, checkContent=True, cookieParams={"header": headers, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True})
        return urltab

    def parserHEXLOAD(self, baseUrl):  # add 160625
        printDBG("parserHEXLOAD baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        urltab = []
        postdata = {"op": "download3", "id": urlparse(baseUrl).path.strip("/"), "ajax": "1", "method_free": "1", "dataType": "json"}
        sts, data = self.cm.getPage("https://hexload.com/download", HTTP_HEADER, postdata)
        if not sts:
            return []
        data = json_loads(data)
        url = data.get("result", {}).get("url")
        if url:
            urltab.append({"name": "mp4", "url": url})
        return urltab

    def parserVIDEA(self, baseUrl):  # add 180625
        printDBG("parserVIDEA baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        STATIC_SECRET = "xHb0ZvME5q8CBcoQi6AngerDu3FGO9fkUlwPmLVY_RTzj2hJIS4NasXWKy1td7p"
        sts, data = self.cm.getPage(baseUrl, HTTP_HEADER)
        if not sts:
            return []
        url = baseUrl if "/player" in baseUrl else urljoin(baseUrl, re.search(r'<iframe.*?src="(/player\?[^"]+)"', data).group(1))
        sts, nonce = self.cm.getPage(url, HTTP_HEADER)
        if not sts:
            return []
        nonce = re.search(r'_xt\s*=\s*"([^"]+)"', nonce).group(1)
        l, s = nonce[:32], nonce[32:]
        result = "".join(s[i - (STATIC_SECRET.index(l[i]) - 31)] for i in range(32))
        query = parse_qs(urlparse(url).query)
        _s = random_seed(8)
        _t = result[:16]
        _param = "f=%s" % query["f"][0] if "f" in query else "v=%s" % query["v"][0]
        hurl = "https://%s/player/xml?platform=desktop&%s&_s=%s&_t=%s" % (urlparser.getDomain(baseUrl), _param, _s, _t)
        sts, videaXml = self.cm.getPage(hurl, {"header": HTTP_HEADER, "collect_all_headers": True})
        if not sts:
            return []
        if not videaXml.startswith("<?xml"):
            key = result[16:] + _s + self.cm.meta.get("x-videa-xs", "")
            videaXml = rc4(videaXml, key)
        urltab = []
        source = re.findall(r'video_source\s*name="([^"]+).*?exp="([^"]+)">([^<]+)', videaXml)
        if source:
            for label, exp, url in source:
                url = "https:" + url if url.startswith("//") else url
                url = "%s?md5=%s&expires=%s" % (url, re.search(r"<hash_value_%s>([^<]+)<" % label, videaXml).group(1), exp)
                urltab.append({"name": label, "url": url})
            urltab.reverse()
        return urltab

    def parserSTREAMUP(self, baseUrl):  # fix 140226
        printDBG("parserSTREAMUP baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        filecode = self.cm.ph.getSearchGroups(data, r"filecode;let.*?`/((?:ajax|api)/stream\Wfilecode=)")[0]
        if not filecode:
            return []
        HTTP_HEADER["Referer"] = baseUrl
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        sts, data = self.cm.getPage(host + filecode + baseUrl.split("/")[-1], {"header": HTTP_HEADER})
        if not sts:
            return []
        data = json_loads(data)
        url = data.get("streaming_url")
        if isinstance(data.get("subtitles"), list):
            subTracks = [{"title": "", "url": sub.get("file_path"), "lang": sub.get("language")} for sub in data.get("subtitles", []) if sub.get("file_path") and sub.get("language")]
        if url:
            url = url.replace("\r", "").replace("\n", "")
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            if ".m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserSHAREVIDEO(self, url):  # add 160925
        printDBG("parserSHAREVIDEO baseUrl[%s]" % url)
        HTTP_HEADER = self.cm.getDefaultHeader()
        host = urlparser.getDomain(url, False)
        sts, data = self.cm.getPage("%sapi/v1/videos/%s" % (host, url.split("/")[-1]), HTTP_HEADER)
        if not sts:
            return []
        urltab = []
        url = self.cm.ph.getSearchGroups(data, 'playlistUrl":"([^"]+)')[0]
        if url:
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserBYSE(self, baseUrl):  # fix 200126
        def ft(e):
            t = e.replace("-", "+").replace("_", "/")
            r = 0 if len(t) % 4 == 0 else 4 - len(t) % 4
            n = t + "=" * r
            return base64.b64decode(n)

        def xn(e):
            return b"".join(list(map(ft, e)))

        printDBG("parserBYSE baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl
        HTTP_HEADER["X-Embed-Parent"] = baseUrl
        host = urlparser.getDomain(baseUrl.replace("boosteradx.online", "streamlyplayer.online"), False)
        mid = re.search(r"/(?:e|d|download)/([0-9a-zA-Z]+)", baseUrl).group(1)
        sts, data = self.cm.getPage("%sapi/videos/%s/embed/details" % (host, mid), {"header": HTTP_HEADER})
        if not sts:
            return []
        data = json_loads(data)
        code = data.get("code")
        baseUrl = data.get("embed_frame_url", baseUrl)
        HTTP_HEADER["Referer"] = baseUrl
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER["Origin"] = host[:-1]
        sts, data = self.cm.getPage("%sapi/videos/%s/embed/playback" % (host, code), {"header": HTTP_HEADER})
        if not sts:
            return []
        html = json_loads(data)
        pd = html.get("playback")
        if pd:
            iv = ft(pd.get("iv"))
            key = xn(pd.get("key_parts"))
            pl = ft(pd.get("payload"))
            cipher = python_aesgcm.new(key)
            ct = cipher.open(iv, pl)
            html = json_loads(ct.decode("latin-1"))
        sources = html.get("sources")
        if sources:
            for x in sources:
                url = urlparser.decorateUrl(x.get("url"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                if ".m3u8" in url:
                    urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
                else:
                    urltab.append({"name": x.get("label", ""), "url": url})
        return urltab

    def parserCOUDMAILRU(self, baseUrl):  # Fix 221125
        printDBG("parserCOUDMAILRU baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        urltab = []
        host = urlparser.getDomain(baseUrl, False)
        m = re.search(r'"weblink"\s*:\s*"([^"]+?)"', data)
        r = re.search(r'1","url":"([^"]+)"[^>],"view', data)
        if r and m:
            b = base64.b64encode(m.group(1).encode("utf-8")).decode("utf-8")
            url = "%s/0p/%s.m3u8?double_encode=1" % (r.group(1), b)
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserJWPLAYER(self, baseUrl):  # update 170126
        def jw_hidden(html, url):
            domain = urlparser.getDomain(url, False)[:-1]
            mediaid = url.rstrip(".html").split("/")[-1].split("-")[-1]
            forms = {}
            for form in re.finditer(r"<form[^>]*>(.*?)</form>", html, re.DOTALL | re.I):
                purl = re.search(r'action\s*=\s*[\'"]([^\'"]+)', form.group(0))
                for field in re.finditer(r'type=[\'"]?(hidden|submit)[\'"]?[^>]*>', form.group(1)):
                    name = re.search(r'name\s*=\s*[\'"]([^\'"]+)', field.group(0))
                    value = re.search(r'value\s*=\s*[\'"]([^\'"]*)', field.group(0))
                    if name and value:
                        name = name.group(1)
                        value = value.group(1)
                        if name == "file_code" and value == "":
                            value = mediaid
                        forms[name] = value
                if purl:
                    purl = purl.group(1)
                    if purl.startswith("/"):
                        purl = domain + purl
                    if purl and forms:
                        GetIPTVSleep().Sleep(6)
                        sts, data = self.cm.getPage(purl, urlParams, forms)
                        if sts:
                            return data
            return ""

        printDBG("parserJWPLAYER baseUrl[%s]" % baseUrl)
        urltab = []
        COOKIE_FILE = GetCookieDir("%s.cookie" % urlparser.getDomain(baseUrl))
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", urlparser.getDomain(baseUrl, False))
        urlParams = {"header": HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": COOKIE_FILE}
        if "mxdrop" in baseUrl or "mixdro" in baseUrl or "mixdrp" in baseUrl or "m1xdrop" in baseUrl:
            baseUrl = baseUrl.replace(".co/", ".ag/").replace(".club/", ".ag/")
            baseUrl = "/".join(baseUrl.split("/")[:5]).replace("/f/", "/e/") if "/f/" in baseUrl else baseUrl
        if "hglink.to" in baseUrl:
            baseUrl = baseUrl.replace("hglink.to", "dumbalag.com")
        if "cybervynx.com" in baseUrl:
            baseUrl = baseUrl.replace("cybervynx.com", "guxhag.com")
        if "streamwish.to" in baseUrl:
            baseUrl = baseUrl.replace("streamwish.to", "hglamioz.com")
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        if "p,a,c,k,e" not in data and "mp4" not in data and "m3u8" not in data:
            src = re.search(r'(?:data-embed|iframe\s+src)="([^"]+)"', data)
            if src:
                sts, data = self.cm.getPage(src.group(1), urlParams)
                if not sts:
                    return []
            elif "<form" in data:
                data = jw_hidden(data, baseUrl)
        if "function(p,a,c,k,e" in data:
            data = get_packed_data(data)
            if not data:
                return []
        host = urlparser.getDomain(baseUrl, False)
        url = re.search(r"""["']((?:https?:)?//[^'^"]+?\.(?:mp4|m3u8|mkv)(?:\?[^"^']+?)?)["']""", data)
        if not url:
            url = re.search(r"""file":"([^"]+)""", data)
        subTracks = []
        sub = re.findall(r"""{\s*file:\s*["']([^"']+)["'],\s*label:\s*["']([^"']+)["'],\s*kind:\s*["'](?:captions|subtitles)["']""", data)
        if not sub:
            sub = re.findall(r"""file_path":"([^"]+)","language":"([^"]+)""", data)
        if sub:
            for src, label in sub:
                src = src.replace(r"\/", "/")
                subTracks.append({"title": "", "url": "https:" + src if src.startswith("//") else src, "lang": label})
        if url:
            url = url.group(1)
            url = "https:" + url if url.startswith("//") else url
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            if ".m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
            elif ".mpd" in url:
                urltab.extend(getMPDLinksWithMeta(url))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserOKRU(self, baseUrl):  # Fix 061225
        printDBG("parserOKRU baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        urltab = []
        match = re.search(r'data-options="([^"]+)', data)
        if match:
            match = match.group(1).replace("&quot;", '"').replace("&amp;", "&")
            js = json_loads(match).get("flashvars", {}).get("metadata")
            js = json_loads(js)
            url = js.get("hlsManifestUrl") or js.get("ondemandHls") or js.get("hlsMasterPlaylistUrl")
            if url:
                url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        return urltab

    def parserVIDSRC(self, baseUrl):  # add 171225
        printDBG("parserVIDSRC baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        urltab = []
        baseUrl = baseUrl.replace("vidsrc.to", "vidsrc.xyz").replace("vidsrc.pm", "vidsrc.xyz")
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        url = re.search(r"""src=['"]([^"]+)['"] f""", data)
        if not url:
            return []
        url = url.group(1)
        url = "https:" + url if url.startswith("//") else url
        host = urlparser.getDomain(url, False)
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return []
        HTTP_HEADER["Referer"] = url
        url = re.search(r""" src: ['"]([^'"]+)""", data)
        if not url:
            return []
        url = host[:-1] + url.group(1)
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return []
        match = re.findall(r'id="([^"]+)" style="display:none;">([^<]+)', data)
        if match:
            a, b = match[0]
            d = crsdiv(b, a)
            if d:
                url = d.split(" ")[0].replace("{v1}", "thrumbleandjaxon.com")
                url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                if ".m3u8" in url:
                    urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        return urltab

    def parserGUPLOAD(self, baseUrl):
        printDBG("parserGUPLOAD baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        urltab = []
        match = re.search(r"""decodePayload.*?['\"]([A-Za-z0-9+/=]+)['\"]""", data)
        if match:
            data = base64.b64decode(match.group(1)).decode()
            url = json_loads(data.split("|", 1)[1]).get("videoUrl")
            if url:
                url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        return urltab

    def parserVIDSONIC(self, baseUrl):
        def decode_string(_0x3):
            _0x4 = _0x3.replace("|", "")
            _0x5 = ""
            for i in range(0, len(_0x4), 2):
                _0x5 += chr(int(_0x4[i: i + 2], 16))
            return _0x5[::-1]

        printDBG("parserVIDSONIC baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        urltab = []
        match = re.search(r"""const\s+_0x1\s*=\s*'([^']+)';""", data)
        if match:
            url = decode_string(match.group(1))
            if url:
                url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserVIDCLOUD(self, baseUrl):  # add 280126
        printDBG("parserVIDCLOUD baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        url = baseUrl.split("?")[0].rsplit("/", 1)
        sts, data = self.cm.getPage("%s/getSources?id=%s" % (url[0], url[1]), {"header": HTTP_HEADER})
        if not sts:
            return []
        urltab = []
        subTracks = []
        js = json_loads(data)
        if not js.get("encrypted"):
            for s in js.get("tracks"):
                if s.get("file") and s.get("label"):
                    subTracks.append({"title": "", "url": s.get("file"), "lang": s.get("label")})
            for x in js.get("sources"):
                url = urlparser.decorateUrl(x.get("file"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
                urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserCOVERAPI(self, baseUrl):  # Add Partly work 250226
        def fix_b64_padding(s):
            return s + "=" * (-len(s) % 4)

        printDBG("parserCOVERAPI baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Accept-Language"] = "el,en-US;q=0.9,en;q=0.8"
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        news_id = re.search(r"""news_id:\s*'(\d+)'""", data)
        if news_id:
            postdata = {"mod": "players", "news_id": news_id.group(1)}
            HTTP_HEADER["Referer"] = baseUrl
            sts, data = self.cm.getPage("%sengine/ajax/controller.php" % host, {"header": HTTP_HEADER}, postdata)
            if not sts:
                return []
            js = json_loads(data).get("html5", "")
            data = re.search(r'file:"([^"]+)', js)
            if data:
                data = str(data.group(1))
                t = []
                if data.startswith("#2"):
                    encoded = data[2:]
                    encoded = encoded.split("=")
                    for a in encoded:
                        if a:
                            t.append(a.split("//")[0])
                    t = str("".join(t))
                    if t:
                        url = base64.b64decode(fix_b64_padding(t)).decode("latin1")
                        return urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            return []

    def parserMEGAFILES(self, baseUrl):  # Add Partly work 250226
        printDBG("parserMEGAFILES baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        urltab = []
        subTracks = []
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        var = re.findall(r'var\s+(\w+)\s*=\s*"([^"]*)"', data)
        if var:
            ids = dict(var)
            mid = ids.get("movieId")
            user_id = "zh&72ciO39tgH5" + "_" + ids.get("userId")
            vrf = generate_vrf(mid, user_id)
            url = "%sapi/%s/servers?id=%s&type=%s&v=%s&vrf=%s&imdbId=%s" % (host, mid, mid, ids.get("movieType"), ids.get("v"), vrf, ids.get("imdbId", "null"))
            var = re.findall(r"var\s+(\w+)\s*=\s*(\d+);", data)
            if var:
                tv = dict(var)
                url += "&season=%s&episode=%s" % (tv.get("season"), tv.get("episode"))
            sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return []

            js = json_loads(data).get("data")
            url = "%sapi/source/%s" % (host, js[0].get("hash"))
            sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return []
            js = json_loads(data).get("data")
            # if isinstance(js.get("subtitles"), list):
            #     subTracks = [{"title": "", "url": sub.get("file"), "lang": sub.get("label")} for sub in js.get("subtitles", []) if sub.get("file") and sub.get("label")]
            url = urlparser.decorateUrl(js.get("source"), {"User-Agent": HTTP_HEADER["User-Agent"], "Accept": "*/*", "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            urltab.extend(getDirectM3U8Playlist(url))
        return urltab
