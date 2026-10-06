# -*- coding: utf-8 -*-
from ast import literal_eval
import base64
from binascii import hexlify, unhexlify
import codecs
from hashlib import md5, sha256
from random import choice as random_choice, randint, uniform
import re
import string
import struct
import time
import zlib
from os import urandom
from Components.config import config
from Screens.MessageBox import MessageBox
from Plugins.Extensions.IPTVPlayer.components.asynccall import MainSessionWrapper
from Plugins.Extensions.IPTVPlayer.components.captcha_helper import CaptchaHelper
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import GetIPTVSleep, SetIPTVPlayerLastHostError, TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.iptvdm.iptvdh import DMHelper
from Plugins.Extensions.IPTVPlayer.libs import ph, pyaes
from Plugins.Extensions.IPTVPlayer.libs.aesgcm import python_aesgcm
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps
from Plugins.Extensions.IPTVPlayer.libs.ecdsa import NIST256p as ECDSA_NIST256p, SigningKey as ECDSA_SigningKey
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import captchaParser, decorateUrl, getDirectM3U8Playlist, getMPDLinksWithMeta, requireDownloaderForDisguisedHls, unicode_escape, unpackJSPlayerParams, VIDUPME_decryptPlayerParams, safeEvalExpression
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import parse_qs, urljoin, urlparse
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, GetCookieDir, GetDefaultLang, GetJSScriptFile, GetPluginDir, b64urlEncode, printDBG, printExc, rm
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


def cryptoJSAesDecrypt(encrypted, passphrase):
    # CryptoJS.AES.decrypt(<JSON {ct, iv, s}>, passphrase): OpenSSL EVP_BytesToKey (MD5) -> AES-256-CBC, PKCS#7;
    # the plain text, None when the passphrase does not fit
    try:
        # only the 32 key bytes are derived - the IV comes with the data
        salt, password, key, prev = unhexlify(encrypted["s"]), ensure_binary(passphrase), b"", b""
        while len(key) < 32:
            prev = md5(prev + password + salt).digest()
            key += prev
        decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key[:32], unhexlify(encrypted["iv"])))
        plain = decrypter.feed(base64.b64decode(encrypted["ct"]))
        return ensure_str(plain + decrypter.feed())
    except Exception:
        return None


class urlparser:
    def __init__(self):
        self.cm = common()
        self.pp = pageParser()
        self.hostMap = {
            "0gomovies.beer": self.pp.parserHQQ,  # add 061026
            "19turanosephantasia.com": self.pp.parserVOESX,  # add 061026
            "1azayf9w.xyz": self.pp.parserBYSE,
            "1fichier.com": self.pp.parser1FICHIERCOM,
            "1vid.xyz": self.pp.parserJWPLAYER,
            "20demidistance9elongations.com": self.pp.parserVOESX,  # add 061026
            "222i8x.lol": self.pp.parserBYSE,
            "26efp.com": self.pp.parserJWPLAYER,
            "30sensualizeexpression.com": self.pp.parserVOESX,  # add 061026
            "321naturelikefurfuroid.com": self.pp.parserVOESX,  # add 061026
            "35volitantplimsoles5.com": self.pp.parserVOESX,  # add 061026
            "360.yandex.ru": self.pp.parserYANDEXDISK,
            "449unceremoniousnasoseptal.com": self.pp.parserVOESX,  # add 061026
            "4yftwvrdz7.sbs": self.pp.parserJWPLAYER,
            "6sfkrspw4u.sbs": self.pp.parserJWPLAYER,  # add 061026
            "71stream.one": self.pp.parserR2EMBED,  # add 031026
            "732eg54de642sa.sbs": self.pp.parserJWPLAYER,  # add 061026
            "745mingiestblissfully.com": self.pp.parserVOESX,  # add 061026
            "81u6xl9d.xyz": self.pp.parserBYSE,
            "8mhlloqo.fun": self.pp.parserBYSE,
            "96ar.com": self.pp.parserBYSE,
            # a
            "abkrzkr.sbs": self.pp.parserJWPLAYER,  # add 061026
            "abkrzkz.sbs": self.pp.parserJWPLAYER,  # add 061026
            "abstream.to": self.pp.parserJWPLAYER,  # add 041026
            "abysscdn.com": self.pp.parserABYSS,
            "abyssplayer.com": self.pp.parserABYSS,
            "adblocktape.wiki": self.pp.parserSTREAMTAPE,
            "adrianmissionminute.com": self.pp.parserVOESX,  # add 061026
            "advertape.net": self.pp.parserSTREAMTAPE,  # add 061026
            "advtpe.com": self.pp.parserSTREAMTAPE,  # add 061026
            "agbsb.com": self.pp.parserSTREAMUP,
            "aiavh.com": self.pp.parserJWPLAYER,
            "ajmidyad.sbs": self.pp.parserJWPLAYER,  # add 061026
            "ajmidyadfihayh.sbs": self.pp.parserJWPLAYER,  # add 061026
            "alhayabambi.sbs": self.pp.parserJWPLAYER,  # add 061026
            "aliez.me": self.pp.parserJWPLAYER,
            "alions.pro": self.pp.parserJWPLAYER,  # add 061026
            "all3do.com": self.pp.parserDOOD,
            "alleneconomicmatter.com": self.pp.parserVOESX,  # add 061026
            "anafast.cyou": self.pp.parserJWPLAYER,
            "anafast.online": self.pp.parserJWPLAYER,  # add 061026
            "anafast.org": self.pp.parserJWPLAYER,  # add 061026
            "anafasts.com": self.pp.parserJWPLAYER,  # add 061026
            "anaplayer.online": self.pp.parserALBAPLAYER,  # add 031026 (w.anaplayer.online/albaplayer/<slug>/)
            "anime4low.sbs": self.pp.parserJWPLAYER,
            "anime7u.com": self.pp.parserJWPLAYER,  # add 061026
            "animeshqip.uns.bio": self.pp.parserSBS,  # add 061026
            "ankrzkz.sbs": self.pp.parserJWPLAYER,  # add 061026
            "ankrznm.sbs": self.pp.parserJWPLAYER,  # add 061026
            "ano.cx": self.pp.parserSTREAMUP,  # add 061026
            "anonmp4.art": self.pp.parserANONMP4,  # add 061026
            "anonmp4.help": self.pp.parserANONMP4,
            "antecoxalbobbing1010.com": self.pp.parserVOESX,  # add 061026
            "antiadtape.com": self.pp.parserSTREAMTAPE,
            "apinchcaseation.com": self.pp.parserVOESX,  # add 061026
            "arabveturk.com": self.pp.parserJWPLAYER,
            "archive.org": self.pp.parserARCHIVEORG,
            "ashortl.ink": self.pp.parserVIDMOLYME,
            "asianembed.cam": self.pp.parserSBS,  # add 061026
            "asjp1j93c1.sbs": self.pp.parserJWPLAYER,  # add 061026
            "asnwish.com": self.pp.parserJWPLAYER,
            "atabkhha.sbs": self.pp.parserJWPLAYER,  # add 061026
            "atabknha.sbs": self.pp.parserJWPLAYER,  # add 061026
            "atabknhk.sbs": self.pp.parserJWPLAYER,  # add 061026
            "atabknhs.sbs": self.pp.parserJWPLAYER,  # add 061026
            "audaciousdefaulthouse.com": self.pp.parserVOESX,  # add 061026
            "availedsmallest.com": self.pp.parserVOESX,  # add 061026
            "awish.pro": self.pp.parserJWPLAYER,
            "azipcdn.com": self.pp.parserJWPLAYER,  # add 061026
            # b
            "bbc.co.uk": self.pp.parserBBC,
            "bestwish.lol": self.pp.parserJWPLAYER,
            "bf0skv.org": self.pp.parserBYSE,
            "bgwp.cc": self.pp.parserJWPLAYER,
            "bigclatterhomesguideservice.com": self.pp.parserVOESX,  # add 061026
            "bigshare.io": self.pp.parserJWPLAYER,
            "bigwarp.art": self.pp.parserJWPLAYER,
            "bigwarp.cc": self.pp.parserJWPLAYER,
            "bigwarp.io": self.pp.parserJWPLAYER,
            "bigwarp.pro": self.pp.parserJWPLAYER,
            "bigwings.io": self.pp.parserJWPLAYER,
            "bingezove.com": self.pp.parserJWPLAYER,
            "boonlessbestselling244.com": self.pp.parserVOESX,  # add 061026
            "boosteradx.online": self.pp.parserBYSE,
            "bradleyviewdoctor.com": self.pp.parserVOESX,  # add 061026
            "brightmindwave.com": self.pp.parserHQQ,  # add 061026
            "brittneystandardwestern.com": self.pp.parserVOESX,  # add 061026
            "brucevotewithin.com": self.pp.parserVOESX,  # add 061026
            "btg549.filmoviplex.com": self.pp.parserABYSS,
            "bullstream.xyz": self.pp.parserSTREAMEMBED,  # add 061026
            "byse.sx": self.pp.parserBYSE,
            "bysebuho.com": self.pp.parserBYSE,
            "bysedikamoum.com": self.pp.parserBYSE,
            "bysefujedu.com": self.pp.parserBYSE,
            "bysejikuar.com": self.pp.parserBYSE,
            "bysekoze.com": self.pp.parserBYSE,
            "byselapuix.com": self.pp.parserBYSE,
            "byseqekaho.com": self.pp.parserBYSE,
            "byseraguci.com": self.pp.parserBYSE,
            "bysesayeveum.com": self.pp.parserBYSE,
            "bysesukior.com": self.pp.parserBYSE,
            "bysetayico.com": self.pp.parserBYSE,
            "bysevepoin.com": self.pp.parserBYSE,
            "bysewihe.com": self.pp.parserBYSE,
            "bysezejataos.com": self.pp.parserBYSE,
            "bysezoxexe.com": self.pp.parserBYSE,
            # c
            "c1z39.com": self.pp.parserBYSE,
            "callistanise.com": self.pp.parserJWPLAYER,
            "caseyimpactstation.com": self.pp.parserVOESX,  # add 061026
            "casthq.to": self.pp.parserJWPLAYER,  # add 061026
            "cavanhabg.com": self.pp.parserJWPLAYER,
            "cd189tryo7.sbs": self.pp.parserJWPLAYER,  # add 061026
            "cda.pl": self.pp.parserCDA,
            "cdn1.site": self.pp.parserJWPLAYER,
            "cdnplus.sbs": self.pp.parserJWPLAYER,  # add 031026
            "cdnplus.space": self.pp.parserJWPLAYER,
            "cdnwish.com": self.pp.parserJWPLAYER,
            "charlestoughrace.com": self.pp.parserVOESX,  # add 061026
            "christopheruntilpoint.com": self.pp.parserVOESX,  # add 061026
            "chromotypic.com": self.pp.parserVOESX,  # add 061026
            "chuckle-tube.com": self.pp.parserVOESX,
            "cilootv.store": self.pp.parserJWPLAYER,  # add 061026
            "cimanow.upns.online": self.pp.parserSBS,  # add 061026
            "cindyeyefinal.com": self.pp.parserVOESX,  # add 061026
            "cinegrab.com": self.pp.parserBYSE,
            "cinemathek.online": self.pp.parserJWPLAYER,  # add 061026
            "cloud.mail.ru": self.pp.parserCOUDMAILRU,
            "cloudorchestranova.com": self.pp.parserVIDSRC,
            "coflix.upn.one": self.pp.parserSBS,
            "coolciima.online": self.pp.parserJWPLAYER,  # add 061026
            "counterclockwisejacky.com": self.pp.parserVOESX,  # add 061026
            "coverapi.store": self.pp.parserCOVERAPI,
            "crownmakermacaronicism.com": self.pp.parserVOESX,  # add 061026
            "crystaltreatmenteast.com": self.pp.parserVOESX,  # add 061026
            "csst.online": self.pp.parserSST,
            "cyamidpulverulence530.com": self.pp.parserVOESX,  # add 061026
            "cybervynx.com": self.pp.parserJWPLAYER,
            # d
            "d0000d.com": self.pp.parserDOOD,
            "d000d.com": self.pp.parserDOOD,
            "d00ds.site": self.pp.parserJWPLAYER,  # add 061026
            "d0o0d.com": self.pp.parserDOOD,
            "d-s.io": self.pp.parserDOOD,
            "dailymotion.com": self.pp.parserDAILYMOTION,
            "darkibox.com": self.pp.parserJWPLAYER,
            "dancima.shop": self.pp.parserJWPLAYER,
            "davioad.com": self.pp.parserJWPLAYER,
            "devideosrc.co": self.pp.parserMEINECLOUD,
            "dhcplay.com": self.pp.parserJWPLAYER,
            "dhtpre.com": self.pp.parserJWPLAYER,
            "dianaavoidthey.com": self.pp.parserVOESX,  # add 061026
            "diananatureforeign.com": self.pp.parserVOESX,  # add 061026
            "dingtezuni.com": self.pp.parserJWPLAYER,
            "dinisglows.com": self.pp.parserJWPLAYER,  # add 061026
            "dintezuvio.com": self.pp.parserJWPLAYER,
            "disk.yandex.com": self.pp.parserYANDEXDISK,
            "disk.yandex.ru": self.pp.parserYANDEXDISK,
            "disneycdn.net": self.pp.parserSBS,  # add 061026
            "dlions.pro": self.pp.parserJWPLAYER,  # add 061026
            "do0od.com": self.pp.parserDOOD,
            "do7go.com": self.pp.parserDOOD,
            "donaldlineelse.com": self.pp.parserVOESX,  # add 061026
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
            "doodporn.xyz": self.pp.parserJWPLAYER,  # add 061026
            "doods.pro": self.pp.parserDOOD,
            "doods.to": self.pp.parserVEEV,
            "doodcdn.io": self.pp.parserDOOD,
            "doodstream.co": self.pp.parserDOOD,
            "doodstream.com": self.pp.parserDOOD,
            "dooodster.com": self.pp.parserDOOD,
            "dooood.com": self.pp.parserDOOD,
            "doplay.store": self.pp.parserHQQ,
            "doply.net": self.pp.parserDOOD,
            "dpstream.fyi": self.pp.parserJWPLAYER,
            "dr0pstream.com": self.pp.parserJWPLAYER,
            "drakkar.st": self.pp.parserDRAKKAR,
            "dropload.co": self.pp.parserJWPLAYER,
            "dropload.io": self.pp.parserJWPLAYER,
            "dropload.pro": self.pp.parserJWPLAYER,
            "dropload.tv": self.pp.parserJWPLAYER,
            "ds2play.com": self.pp.parserDOOD,
            "ds2video.com": self.pp.parserDOOD,
            "dsvplay.com": self.pp.parserDOOD,
            "dumbalag.com": self.pp.parserJWPLAYER,
            "dwish.pro": self.pp.parserJWPLAYER,  # add 061026
            "dzo.vidplayer.live": self.pp.parserSBS,  # add 061026
            # e
            "e4xb5c2xnz.sbs": self.pp.parserJWPLAYER,  # add 061026
            "earnvids.xyz": self.pp.parserJWPLAYER,  # add 031026
            "eb8gfmjn71.sbs": self.pp.parserJWPLAYER,
            "ebd.cda.pl": self.pp.parserCDA,
            "edbrdl7pab.sbs": self.pp.parserJWPLAYER,
            "edwardarriveoften.com": self.pp.parserVOESX,  # add 061026
            "eghjrutf.sbs": self.pp.parserJWPLAYER,  # add 061026
            "eghzrutw.sbs": self.pp.parserJWPLAYER,  # add 061026
            "egsyxurh.sbs": self.pp.parserJWPLAYER,  # add 061026
            "egsyxutd.sbs": self.pp.parserJWPLAYER,  # add 061026
            "egtpgrvh.sbs": self.pp.parserJWPLAYER,
            "ellenpoliticalfollow.com": self.pp.parserVOESX,  # add 061026
            "embedplay.upns.ink": self.pp.parserSBS,  # add 061026
            "embedplayabyss.top": self.pp.parserABYSS,
            "embedplayapiupn.upns.xyz": self.pp.parserSBS,  # add 061026
            "embedplaybyse.top": self.pp.parserBYSE,
            "embedwish.com": self.pp.parserJWPLAYER,
            "emturbovid.com": self.pp.parserJWPLAYER,
            "en.embedz.net": self.pp.parserJWPLAYER,
            "erikcoldperson.com": self.pp.parserVOESX,  # add 061026
            "eugenemakedraw.com": self.pp.parserVOESX,  # add 061026
            # f
            "f16px.com": self.pp.parserBYSE,
            "f51rm.com": self.pp.parserBYSE,
            "fastream.to": self.pp.parserJWPLAYER,
            "fastvid.cam": self.pp.parserJWPLAYER,  # add 041026
            "fdewsdc.sbs": self.pp.parserJWPLAYER,
            "figeterpiazine.com": self.pp.parserVOESX,  # add 061026
            "file-upload.com": self.pp.parserJWPLAYER,  # add 061026
            "file-upload.in": self.pp.parserJWPLAYER,  # add 061026
            "filecloud.io": self.pp.parserFILECLOUDIO,
            "filedecrypt.link": self.pp.parserSBS,  # add 061026
            "filefactory.com": self.pp.parserFILEFACTORYCOM,
            "filelions.co": self.pp.parserJWPLAYER,  # add 061026
            "filelions.com": self.pp.parserJWPLAYER,  # add 061026
            "filelions.live": self.pp.parserJWPLAYER,
            "filelions.online": self.pp.parserJWPLAYER,
            "filelions.site": self.pp.parserJWPLAYER,
            "filelions.to": self.pp.parserJWPLAYER,
            "filelions.xyz": self.pp.parserJWPLAYER,  # add 061026
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
            "filma365.strp2p.site": self.pp.parserSBS,
            "filmi9.upns.xyz": self.pp.parserSBS,  # add 061026
            "firestream.site": self.pp.parserFIRESTREAM,  # add 061026
            "firestream.to": self.pp.parserFIRESTREAM,
            "fittingcentermondaysunday.com": self.pp.parserVOESX,  # add 061026
            "fiuosba.com": self.pp.parserSTREAMUP,  # add 041026 - strmup mirror (mlblive)
            "flaswish.com": self.pp.parserJWPLAYER,
            "flimmer.rpmvip.com": self.pp.parserSBS,  # add 061026
            "flyf.lat": self.pp.parserFLYFILE,
            "flyfile.app": self.pp.parserFLYFILE,
            "forafile.com": self.pp.parserJWPLAYER,
            "fraudclatterflyingcar.com": self.pp.parserVOESX,  # add 061026
            "freedisc.pl": self.pp.parserFREEDISC,
            "fsdcmo.sbs": self.pp.parserJWPLAYER,
            "fsst.online": self.pp.parserSST,
            "furher.in": self.pp.parserBYSE,
            "fviplions.com": self.pp.parserJWPLAYER,  # add 061026
            # g
            "gamoneinterrupted.com": self.pp.parserVOESX,  # add 061026
            "garylargeavailable.com": self.pp.parserVOESX,  # add 061026
            "gbsagbo.com": self.pp.parserSTREAMUP,
            "generatesnitrosate.com": self.pp.parserVOESX,  # add 061026
            "gettapeads.com": self.pp.parserSTREAMTAPE,  # add 061026
            "ghbrisk.com": self.pp.parserJWPLAYER,
            "goodstream.one": self.pp.parserJWPLAYER,
            "goodstream.uno": self.pp.parserJWPLAYER,
            "goodstream.vip": self.pp.parserSTREAMCASH,
            "goofy-banana.com": self.pp.parserVOESX,
            "google.com": self.pp.parserGOOGLE,
            "govid.live": self.pp.parserGOVID,  # add 031026
            "govid.site": self.pp.parserJWPLAYER,
            "graceaddresscommunity.com": self.pp.parserVOESX,  # add 061026
            "gradehgplus.com": self.pp.parserJWPLAYER,  # add 061026
            "greaseball6eventual20.com": self.pp.parserVOESX,  # add 061026
            "gscdn.cam": self.pp.parserJWPLAYER,
            "gsfomqu.sbs": self.pp.parserJWPLAYER,  # add 061026
            "gsfqzmqu.sbs": self.pp.parserJWPLAYER,
            "guidon40hyporadius9.com": self.pp.parserVOESX,  # add 061026
            "gupload.site": self.pp.parserGUPLOAD,  # add 061026
            "gupload.xyz": self.pp.parserGUPLOAD,
            "guxhag.com": self.pp.parserJWPLAYER,  # add 061026
            # h
            "hailindihg.com": self.pp.parserJWPLAYER,  # add 061026
            "haxloppd.com": self.pp.parserJWPLAYER,
            "hayaatieadhab.sbs": self.pp.parserJWPLAYER,  # add 061026
            "hd1.hdup20.com": self.pp.parserJWPLAYER,
            "hdbestvd.online": self.pp.parserJWPLAYER,
            "hdup400.com": self.pp.parserJWPLAYER,  # add 031026 (s1.hdup400.com via the parent domain)
            "heatherdiscussionwhen.com": self.pp.parserVOESX,  # add 061026
            "hexload.com": self.pp.parserHEXLOAD,
            "hexupload.net": self.pp.parserHEXLOAD,
            "hgbazooka.com": self.pp.parserJWPLAYER,  # add 061026
            "hgcloud.to": self.pp.parserJWPLAYER,
            "hglink.to": self.pp.parserJWPLAYER,
            "hgplaycdn.com": self.pp.parserJWPLAYER,
            "hlsflast.com": self.pp.parserJWPLAYER,
            "hlsplayer.org": self.pp.parserJWPLAYER,
            "hlswish.com": self.pp.parserJWPLAYER,
            "housecardsummerbutton.com": self.pp.parserVOESX,  # add 061026
            "hqq.ac": self.pp.parserHQQ,
            "hqq.to": self.pp.parserHQQ,
            "hqq.tv": self.pp.parserHQQ,
            "hydraxcdn.biz": self.pp.parserABYSS,
            # i
            "ianrequireadult.com": self.pp.parserVOESX,  # add 061026
            "incvideo1.online": self.pp.parserSST,  # add 061026
            "iplayerhls.com": self.pp.parserJWPLAYER,
            "isbfga.online": self.pp.parserSTREAMUP,  # add 061026
            "isbfga.space": self.pp.parserSTREAMUP,  # add 061026
            "isbfga.store": self.pp.parserSTREAMUP,  # add 061026
            # j
            "jamesbornmain.com": self.pp.parserVOESX,  # add 061026
            "jamessoundcost.com": self.pp.parserVOESX,  # add 061026
            "jamiesamewalk.com": self.pp.parserVOESX,  # add 061026
            "jasminetesttry.com": self.pp.parserVOESX,  # add 061026
            "javggvideo.xyz": self.pp.parserJWPLAYER,  # add 061026
            "javlion.xyz": self.pp.parserJWPLAYER,  # add 061026
            "javplaya.com": self.pp.parserJWPLAYER,  # add 061026
            "javsw.me": self.pp.parserJWPLAYER,
            "jayservicestuff.com": self.pp.parserVOESX,  # add 061026
            "jeanprofessorcentral.com": self.pp.parserVOESX,  # add 061026
            "jefferycontrolmodel.com": self.pp.parserVOESX,  # add 061026
            "jennifercertaindevelopment.com": self.pp.parserVOESX,  # add 061026
            "jennifereconomicgive.com": self.pp.parserVOESX,  # add 061026
            "jeremyparticipantanything.com": self.pp.parserVOESX,  # add 061026
            "jessicachoosemake.com": self.pp.parserVOESX,  # add 061026
            "jessicayeahcatch.com": self.pp.parserVOESX,  # add 061026
            "jilliandescribecompany.com": self.pp.parserVOESX,  # add 061026
            "jodwish.com": self.pp.parserJWPLAYER,
            "johnalwayssame.com": self.pp.parserVOESX,  # add 061026
            "johnbeyondnation.com": self.pp.parserVOESX,  # add 061026
            "johnfullwonder.com": self.pp.parserVOESX,  # add 061026
            "jonathansociallike.com": self.pp.parserVOESX,  # add 061026
            "josephseveralconcern.com": self.pp.parserVOESX,  # add 061026
            "juliewomanwish.com": self.pp.parserVOESX,  # add 061026
            "justupload.io": self.pp.parserJWPLAYER,
            # k
            "katherineschoolphone.com": self.pp.parserVOESX,  # add 061026
            "kathleenmemberhistory.com": self.pp.parserVOESX,  # add 061026
            "katomen.online": self.pp.parserJWPLAYER,  # add 061026
            "katomen.store": self.pp.parserJWPLAYER,  # add 061026
            "kellywhatcould.com": self.pp.parserVOESX,  # add 061026
            "kennethofficialitem.com": self.pp.parserVOESX,  # add 061026
            "kerapoxy.cc": self.pp.parserBYSE,
            "khadhnayad.sbs": self.pp.parserJWPLAYER,  # add 061026
            "kharabnahs.sbs": self.pp.parserJWPLAYER,  # add 061026
            "kinoger.be": self.pp.parserJWPLAYER,
            "kinoger.embed4me.vip": self.pp.parserSBS,
            "kinoger.seekplays.pro": self.pp.parserSBS,
            "kinoger.p2pplay.pro": self.pp.parserSBS,
            "kinoger.pw": self.pp.parserSTREAMUP,
            "kinoger.re": self.pp.parserSBS,
            "kinoger.ru": self.pp.parserVOESX,
            "klcams.com": self.pp.parserBYSE,  # add 061026
            "kory.4meplayer.pro": self.pp.parserSBS,  # add 061026
            "kravaxxa.com": self.pp.parserJWPLAYER,
            "kristiesoundsimply.com": self.pp.parserVOESX,  # add 061026
            # l
            "l1afav.net": self.pp.parserBYSE,
            "lancewhosedifficult.com": self.pp.parserVOESX,  # add 061026
            "launchreliantcleaverriver.com": self.pp.parserVOESX,  # add 061026
            "lauradaydo.com": self.pp.parserVOESX,  # add 061026
            "lisatrialidea.com": self.pp.parserVOESX,  # add 061026
            "lolololo.store": self.pp.parserSBS,  # add 031026 (Streamp2p "#id" player, not the earnvids lolololu.website)
            "lolololu.website": self.pp.parserJWPLAYER,
            "lookmovie2.skin": self.pp.parserJWPLAYER,  # add 061026
            "loriwithinfamily.com": self.pp.parserVOESX,  # add 061026
            "lukecomparetwo.com": self.pp.parserVOESX,  # add 061026
            "lukesitturn.com": self.pp.parserVOESX,  # add 061026
            "lulu.st": self.pp.parserJWPLAYER,
            "lulust.com": self.pp.parserJWPLAYER,
            "lulustream.com": self.pp.parserJWPLAYER,
            "luluvid.com": self.pp.parserJWPLAYER,
            "luluvdo.com": self.pp.parserJWPLAYER,
            "luluvdoo.com": self.pp.parserJWPLAYER,
            "luluvido.com": self.pp.parserJWPLAYER,  # add 061026
            "lumiawatch.top": self.pp.parserJWPLAYER,  # add 061026
            # m
            "m1xdrop.bz": self.pp.parserMIXDROP,  # add 041026
            "m1xdrop.click": self.pp.parserMIXDROP,
            "m1xdrop.com": self.pp.parserMIXDROP,
            "m1xdrop.net": self.pp.parserMIXDROP,
            "ma2d.store": self.pp.parserJWPLAYER,  # add 061026
            "mariatheserepublican.com": self.pp.parserVOESX,  # add 061026
            "marissasharecareer.com": self.pp.parserVOESX,  # add 061026
            "matriculant401merited.com": self.pp.parserVOESX,  # add 061026
            "matthewhotelscience.com": self.pp.parserVOESX,  # add 061026
            "maxfinishseveral.com": self.pp.parserVOESX,  # add 061026
            "md3b0j6hj.com": self.pp.parserMIXDROP,
            "mdbekjwqa.pw": self.pp.parserMIXDROP,
            "mdfx9dc8n.net": self.pp.parserMIXDROP,
            "mdy48tn97.com": self.pp.parserMIXDROP,
            "mdzsmutpcvykb.net": self.pp.parserMIXDROP,
            "mediafire.com": self.pp.parserMEDIAFIRECOM,
            "megamax.cam": self.pp.parserMEGAMAX,  # add 031026
            "megamax.me": self.pp.parserMEGAMAX,  # add 031026
            "megatuktuk.store": self.pp.parserMEGAMAX,  # add 031026
            "meinecloud.click": self.pp.parserMEINECLOUD,
            "metagnathtuggers.com": self.pp.parserVOESX,  # add 061026
            "mfw09.org": self.pp.parserBYSE,
            "michaelapplysome.com": self.pp.parserVOESX,  # add 061026
            "miiiixdrop.net": self.pp.parserMIXDROP,
            "miiixdrop.net": self.pp.parserMIXDROP,
            "miixdrop.net": self.pp.parserMIXDROP,
            "mikaylaarealike.com": self.pp.parserVOESX,  # add 061026
            "minochinos.com": self.pp.parserJWPLAYER,
            "mivalyo.com": self.pp.parserJWPLAYER,
            "mixdrp.click": self.pp.parserMIXDROP,
            "mixdrp.co": self.pp.parserMIXDROP,
            "mixdrp.to": self.pp.parserMIXDROP,
            "mixdroop.bz": self.pp.parserMIXDROP,
            "mixdroop.co": self.pp.parserMIXDROP,
            "mixdrop21.net": self.pp.parserMIXDROP,
            "mixdrop23.net": self.pp.parserMIXDROP,
            "mixdrop.ag": self.pp.parserMIXDROP,
            "mixdrop.bz": self.pp.parserMIXDROP,
            "mixdrop.ch": self.pp.parserMIXDROP,
            "mixdrop.club": self.pp.parserMIXDROP,
            "mixdrop.co": self.pp.parserMIXDROP,
            "mixdrop.gl": self.pp.parserMIXDROP,
            "mixdrop.is": self.pp.parserMIXDROP,
            "mixdrop.ms": self.pp.parserMIXDROP,
            "mixdrop.my": self.pp.parserMIXDROP,
            "mixdrop.nu": self.pp.parserMIXDROP,
            "mixdrop.ps": self.pp.parserMIXDROP,
            "mixdrop.sb": self.pp.parserMIXDROP,
            "mixdrop.si": self.pp.parserMIXDROP,
            "mixdrop.sn": self.pp.parserMIXDROP,
            "mixdrop.sx": self.pp.parserMIXDROP,
            "mixdrop.to": self.pp.parserMIXDROP,
            "mixdrop.top": self.pp.parserMIXDROP,
            "mixdrop.vc": self.pp.parserMIXDROP,
            "mixdropjmk.pw": self.pp.parserMIXDROP,
            "mlions.pro": self.pp.parserJWPLAYER,  # add 061026
            "moflix-stream.click": self.pp.parserJWPLAYER,
            "moflix-stream.fans": self.pp.parserJWPLAYER,
            "moflix-stream.link": self.pp.parserBYSE,
            "moflix.rpmplay.xyz": self.pp.parserSBS,
            "moflix.upns.xyz": self.pp.parserSBS,
            "mohahhda.site": self.pp.parserJWPLAYER,  # add 061026
            "moonmov.pro": self.pp.parserBYSE,
            "morencius.com": self.pp.parserJWPLAYER,
            "motvy55.store": self.pp.parserJWPLAYER,  # add 061026
            "movearnpre.com": self.pp.parserJWPLAYER,
            "moviesapi.club": self.pp.parserVIDSRC,
            "moviesapi.to": self.pp.parserVIDSRC,
            "mp4player.site": self.pp.parserSTREAMEMBED,
            "mp4plus.cyou": self.pp.parserJWPLAYER,
            "mp4plus.org": self.pp.parserJWPLAYER,
            "mp4upload.com": self.pp.parserJWPLAYER,
            "mwish.pro": self.pp.parserJWPLAYER,  # add 061026
            "mxdrop.sx": self.pp.parserMIXDROP,
            "mxdrop.to": self.pp.parserMIXDROP,
            "mxdrop.top": self.pp.parserMIXDROP,
            "mysportzfy.com": self.pp.parserJWPLAYER,
            "myvidplay.com": self.pp.parserDOOD,
            # n
            "nathanfromsubject.com": self.pp.parserVOESX,  # add 061026
            "ncdn22.xyz": self.pp.parserHQQ,  # add 061026
            "nectareousoverelate.com": self.pp.parserVOESX,  # add 061026
            "netu.ac": self.pp.parserHQQ,
            "netu.filmoviplex.com": self.pp.parserHQQ,
            "netu.to": self.pp.parserHQQ,
            "netu.tv": self.pp.parserHQQ,
            "nonesnanking.com": self.pp.parserVOESX,  # add 061026
            "nova.upn.one": self.pp.parserSBS,
            # o
            "obeywish.com": self.pp.parserJWPLAYER,
            "odnoklassniki.ru": self.pp.parserOKRU,
            "odysee.com": self.pp.parserJWPLAYER,
            "odysseusa.cc": self.pp.parserSTREAMUP,
            "ogladaj.me": self.pp.parserVOESX,  # add 041026
            "ok.ru": self.pp.parserOKRU,
            "okhd.site": self.pp.parserJWPLAYER,  # add 031026 (mp4./mp5.okhd.site via the parent domain)
            "ougbas.xyz": self.pp.parserSTREAMUP,  # add 061026
            "oyohd.one": self.pp.parserHQQ,  # add 061026
            # p
            "pamelachangemission.com": self.pp.parserVOESX,  # add 061026
            "paulkitchendark.com": self.pp.parserVOESX,  # add 061026
            "peachify.top": self.pp.parserPEACHIFY,
            "peytonepre.com": self.pp.parserJWPLAYER,
            "playembed.online": self.pp.parserJWPLAYER,  # add 061026
            "player.sorozatok.me": self.pp.parserHQQ,  # add 061026
            "player.upn.one": self.pp.parserSBS,
            "playerwish.com": self.pp.parserJWPLAYER,
            "playmate.to": self.pp.parserPLAYMATE,
            "playmogo.com": self.pp.parserDOOD,
            "polsatsport.pl": self.pp.parserJWPLAYER,
            "poophq.com": self.pp.parserVEEV,
            "pqham.com": self.pp.parserJWPLAYER,
            # r
            "rapid-cloud.co": self.pp.parserVIDCLOUD,
            "realfinanceblogcenter.com": self.pp.parserVOESX,  # add 061026
            "rebeccaneverbase.com": self.pp.parserVOESX,  # add 061026
            "reputationsheriffkennethsand.com": self.pp.parserVOESX,  # add 061026
            "richardsignfish.com": self.pp.parserVOESX,  # add 061026
            "roberteachfinal.com": self.pp.parserVOESX,  # add 061026
            "robertordercharacter.com": self.pp.parserVOESX,  # add 061026
            "robertplacespace.com": self.pp.parserVOESX,  # add 061026
            "rubystm.com": self.pp.parserJWPLAYER,
            "rubystream.xyz": self.pp.parserJWPLAYER,  # add 061026
            "rubyvid.com": self.pp.parserJWPLAYER,  # add 061026
            "rubyvidhub.com": self.pp.parserJWPLAYER,
            "rty1.film77.xyz": self.pp.parserJWPLAYER,
            "ryderjet.com": self.pp.parserJWPLAYER,
            # s
            "s3taku.pro": self.pp.parserJWPLAYER,
            "sandratableother.com": self.pp.parserVOESX,  # add 061026
            "sandrataxeight.com": self.pp.parserVOESX,  # add 061026
            "savefiles.com": self.pp.parserJWPLAYER,
            "sb1254w9megshle.org": self.pp.parserBYSE,
            "scatch176duplicities.com": self.pp.parserVOESX,  # add 061026
            "scloud.online": self.pp.parserSTREAMTAPE,
            "securecdn.shop": self.pp.parserSBS,  # add 061026
            "secvideo1.online": self.pp.parserSST,  # add 061026
            "seekplayer.vip": self.pp.parserSBS,
            "sendvid.com": self.pp.parserJWPLAYER,
            "sethniceletter.com": self.pp.parserVOESX,  # add 061026
            "sfastwish.com": self.pp.parserJWPLAYER,
            "shannonpersonalcost.com": self.pp.parserVOESX,  # add 061026
            "share4max.com": self.pp.parserMEGAMAX,  # add 031026
            "sharevideo.pl": self.pp.parserSHAREVIDEO,
            "shavetape.cash": self.pp.parserSTREAMTAPE,
            "shiid4u.upn.one": self.pp.parserSBS,
            "short.icu": self.pp.parserABYSS,
            "simpulumlamerop.com": self.pp.parserVOESX,  # add 061026
            "smdfs40r.skin": self.pp.parserBYSE,
            "smoki.cc": self.pp.parserVOESX,  # add 061026
            "smoothpre.com": self.pp.parserJWPLAYER,
            "soundcloud.com": self.pp.parserSOUNDCLOUDCOM,
            "sportsonline.si": self.pp.parserJWPLAYER,
            "sportsonline.to": self.pp.parserJWPLAYER,
            "srbe84.vidplayer.live": self.pp.parserSBS,  # add 061026
            "sruby.xyz": self.pp.parserJWPLAYER,  # add 061026
            "ss.hd-vk.com": self.pp.parserJWPLAYER,
            "stape.fun": self.pp.parserSTREAMTAPE,
            "stbhg.click": self.pp.parserJWPLAYER,  # add 061026
            "stbnetu.xyz": self.pp.parserHQQ,
            "stbturbo.xyz": self.pp.parserJWPLAYER,  # add 061026
            "stevenfamilyedge.com": self.pp.parserVOESX,  # add 061026
            "stevenimaginelittle.com": self.pp.parserVOESX,  # add 061026
            "stmix.io": self.pp.parserSTREAMUP,
            "stmruby.com": self.pp.parserJWPLAYER,  # add 061026
            "strawberriesporail.com": self.pp.parserVOESX,  # add 061026
            "strcloud.club": self.pp.parserSTREAMTAPE,
            "strcloud.link": self.pp.parserSTREAMTAPE,
            "streamable.com": self.pp.parserSTREAMABLE,
            "streamadblocker.xyz": self.pp.parserSTREAMTAPE,
            "streamadblockplus.com": self.pp.parserSTREAMTAPE,
            "streamcash.to": self.pp.parserSTREAMCASH,
            "streamhihi.com": self.pp.parserJWPLAYER,
            "streamhls.to": self.pp.parserJWPLAYER,
            "streamlyplayer.online": self.pp.parserBYSE,
            "streamlyplayero.online": self.pp.parserBYSE,
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
            "streamtapeadblock.art": self.pp.parserSTREAMTAPE,  # add 061026
            "streamtapeadblockuser.xyz": self.pp.parserSTREAMTAPE,  # add 061026
            "streamup.cc": self.pp.parserSTREAMUP,  # add 061026
            "streamup.ws": self.pp.parserSTREAMUP,
            "streamvid.su": self.pp.parserJWPLAYER,
            "streamwish.com": self.pp.parserJWPLAYER,  # add 061026
            "streamwish.fun": self.pp.parserJWPLAYER,
            "streamwish.site": self.pp.parserJWPLAYER,  # add 061026
            "streamwish.to": self.pp.parserJWPLAYER,
            "strmup.cc": self.pp.parserSTREAMUP,
            "strmup.to": self.pp.parserSTREAMUP,
            "strmwis.xyz": self.pp.parserJWPLAYER,  # add 061026
            "strp2p.site": self.pp.parserSBS,
            "strtape.cloud": self.pp.parserSTREAMTAPE,
            "strtape.site": self.pp.parserSTREAMTAPE,  # add 061026
            "strtapeadblock.me": self.pp.parserSTREAMTAPE,  # add 061026
            "strtpe.link": self.pp.parserSTREAMTAPE,
            "strwish.com": self.pp.parserJWPLAYER,  # add 061026
            "strwish.xyz": self.pp.parserJWPLAYER,  # add 061026
            "sufbgao.space": self.pp.parserSTREAMUP,  # add 061026
            "sufbgao.xyz": self.pp.parserSTREAMUP,  # add 061026
            "supervideo.cc": self.pp.parserJWPLAYER,
            "supervideo.tv": self.pp.parserJWPLAYER,
            "swdyu.com": self.pp.parserJWPLAYER,
            "swhoi.com": self.pp.parserJWPLAYER,
            "swiftplayers.com": self.pp.parserJWPLAYER,
            "swishsrv.com": self.pp.parserJWPLAYER,
            # t
            "t1.p2pplay.pro": self.pp.parserSBS,  # add 061026
            "tapeadsenjoyer.com": self.pp.parserSTREAMTAPE,
            "tapeadvertisement.com": self.pp.parserSTREAMTAPE,
            "tapeblocker.com": self.pp.parserSTREAMTAPE,
            "tapewithadblock.org": self.pp.parserSTREAMTAPE,
            "taylorplayer.com": self.pp.parserJWPLAYER,  # add 061026
            "techradar.ink": self.pp.parserJWPLAYER,  # add 061026
            "telyn610zoanthropy.com": self.pp.parserVOESX,  # add 061026
            "tenstream.net": self.pp.parserJWPLAYER,
            "teresapoliticallearn.com": self.pp.parserVOESX,  # add 061026
            "thebesthosterv.com": self.pp.parserSTREAMUP,  # add 061026
            "timberwoodanotia.com": self.pp.parserVOESX,  # add 061026
            "timmaybealready.com": self.pp.parserVOESX,  # add 061026
            "tinycat-voe-fashion.com": self.pp.parserVOESX,  # add 061026
            "toddpartneranimal.com": self.pp.parserVOESX,  # add 061026
            "toxitabellaeatrebates306.com": self.pp.parserVOESX,  # add 061026
            "tpead.net": self.pp.parserSTREAMTAPE,  # add 061026
            "tracylocalschool.com": self.pp.parserVOESX,  # add 061026
            "trgsfjll.sbs": self.pp.parserJWPLAYER,  # add 061026
            "tryzendm.com": self.pp.parserJWPLAYER,  # add 061026
            "tuborstb.co": self.pp.parserJWPLAYER,  # add 061026
            "tuktuk.rpmvid.com": self.pp.parserSBS,  # add 061026
            "tuktuk.upns.one": self.pp.parserSBS,
            "tuktukcimamulti.buzz": self.pp.parserJWPLAYER,  # add 061026
            "tuktukcinema.store": self.pp.parserJWPLAYER,  # add 061026
            "turbovidhls.com": self.pp.parserJWPLAYER,  # add 061026
            "turboviplay.com": self.pp.parserJWPLAYER,
            "tusfiles.com": self.pp.parserUSERSCLOUDCOM,
            "tusfiles.net": self.pp.parserUSERSCLOUDCOM,
            "tvp.pl": self.pp.parserTVP,
            # u
            "uasopt.com": self.pp.parserJWPLAYER,  # add 061026
            "ult4vid.one": self.pp.parserR2EMBED,  # add 031026
            "ultra.rpmvid.site": self.pp.parserSBS,  # add 061026
            "ultrastream.online": self.pp.parserSBS,
            "un-block-voe.net": self.pp.parserVOESX,  # add 061026
            "up4fun.top": self.pp.parserJWPLAYER,
            "up4stream.com": self.pp.parserJWPLAYER,
            "updown.cam": self.pp.parserJWPLAYER,  # add 061026
            "updown.icu": self.pp.parserJWPLAYER,
            "updown.sbs": self.pp.parserJWPLAYER,  # add 061026
            "upn.one": self.pp.parserSBS,  # add 031026 (lodynet.upn.one and other subdomains via the parent domain)
            "upns.live": self.pp.parserSBS,  # add 031026 (lodynet.upns.live)
            "uptodatefinishconferenceroom.com": self.pp.parserVOESX,  # add 061026
            "upzone.cc": self.pp.parserUPZONECC,
            "uqload.bz": self.pp.parserJWPLAYER,
            "uqload.co": self.pp.parserJWPLAYER,  # add 061026
            "uqload.com": self.pp.parserJWPLAYER,
            "uqload.cx": self.pp.parserJWPLAYER,
            "uqload.io": self.pp.parserJWPLAYER,
            "uqload.is": self.pp.parserJWPLAYER,  # add 031026
            "uqload.net": self.pp.parserJWPLAYER,
            "uqload.org": self.pp.parserJWPLAYER,  # add 061026
            "uqload.to": self.pp.parserJWPLAYER,  # add 061026
            "uqload.vc": self.pp.parserJWPLAYER,
            "uqload.ws": self.pp.parserJWPLAYER,
            "uqloads.xyz": self.pp.parserJWPLAYER,
            "userscloud.com": self.pp.parserUSERSCLOUDCOM,
            # v
            "v-o-e-unblock.com": self.pp.parserVOESX,  # add 061026
            "v.turkvearab.com": self.pp.parserJWPLAYER,
            "valeronevijao.com": self.pp.parserVOESX,  # add 061026
            "veev.pro": self.pp.parserVEEV,  # add 061026
            "veev.to": self.pp.parserVEEV,
            "vfaststream.com": self.pp.parserSTREAMUP,  # add 061026
            "vide0.net": self.pp.parserDOOD,
            "videoland.cfd": self.pp.parserSBS,  # add 061026
            "videoland.sbs": self.pp.parserJWPLAYER,  # add 061026
            "videoshar.uns.bio": self.pp.parserSBS,  # add 061026
            "viderea.online": self.pp.parserSTREAMUP,  # add 061026
            "vidhide.com": self.pp.parserJWPLAYER,  # add 061026
            "vidhide.fun": self.pp.parserJWPLAYER,  # add 061026
            "vidhidefast.com": self.pp.parserJWPLAYER,  # add 061026
            "vidhideplus.com": self.pp.parserJWPLAYER,
            "vidhidepre.com": self.pp.parserJWPLAYER,  # add 061026
            "vidhidepro.com": self.pp.parserJWPLAYER,  # add 061026
            "vidhidevip.com": self.pp.parserJWPLAYER,  # add 031026
            "vidmoly.cam": self.pp.parserHQQ,  # add 061026
            "vidmoviesb.xyz": self.pp.parserJWPLAYER,  # add 061026
            "vidnest.live": self.pp.parserJWPLAYER,  # add 061026
            "vidoba.org": self.pp.parserJWPLAYER,
            "vidply.com": self.pp.parserDOOD,
            "vidcore.io": self.pp.parserVIDCORE,
            "vidcore.net": self.pp.parserVIDCORE,
            "vidfast.pro": self.pp.parserVIDCORE,
            "vidfast.vc": self.pp.parserVIDCORE,
            "vidlink.pro": self.pp.parserVIDLINK,
            "videa.hu": self.pp.parserVIDEA,
            "videakid.hu": self.pp.parserVIDEA,
            "videasy.net": self.pp.parserVIDEASY,
            "videasy.to": self.pp.parserVIDEASY,
            "vidaraa.cc": self.pp.parserSTREAMUP,
            "vidarax.cc": self.pp.parserSTREAMUP,
            "vidavaca.net": self.pp.parserSTREAMUP,
            "vidroba.com": self.pp.parserJWPLAYER,  # add 061026
            "vidspeed.cc": self.pp.parserJWPLAYER,  # add 061026
            "vidspeed.org": self.pp.parserJWPLAYER,
            "vidspeeds.com": self.pp.parserJWPLAYER,  # add 061026
            "vidspeeds.org": self.pp.parserJWPLAYER,  # add 061026
            "vidvara.biz": self.pp.parserSTREAMUP,
            "vidara.so": self.pp.parserSTREAMUP,
            "vidara.to": self.pp.parserSTREAMUP,
            "vidavra.cc": self.pp.parserSTREAMUP,
            "vidmatrixa.com": self.pp.parserSTREAMUP,
            "vidora.stream": self.pp.parserJWPLAYER,
            "videzz.net": self.pp.parserJWPLAYER,
            "vidhidehub.com": self.pp.parserJWPLAYER,
            "vidload.co": self.pp.parserVIDLOADCO,
            "vidmoly.biz": self.pp.parserVIDMOLYME,
            "vidmoly.me": self.pp.parserVIDMOLYME,
            "vidmoly.net": self.pp.parserVIDMOLYME,
            "vidmoly.org": self.pp.parserVIDMOLYME,
            "vidmoly.to": self.pp.parserVIDMOLYME,
            "vidneo.cc": self.pp.parserVIDNEO,
            "vidnest.fun": self.pp.parserVIDNEST,
            "vidnest.io": self.pp.parserJWPLAYER,
            "vidoba.cyou": self.pp.parserJWPLAYER,
            "vidoza.co": self.pp.parserJWPLAYER,
            "vidoza.net": self.pp.parserJWPLAYER,
            "vidoza.org": self.pp.parserJWPLAYER,
            "vidrock.net": self.pp.parserVIDROCK,
            "vids.st": self.pp.parserVIDSST,
            "vidsonic.net": self.pp.parserVIDSONIC,
            "vidspeed.space": self.pp.parserJWPLAYER,
            "vidsrc.bz": self.pp.parserVIDSRC,
            "vidsrc.cc": self.pp.parserMEGAFILES,
            "vidsrc.do": self.pp.parserVIDSRC,
            "vidsrc.fyi": self.pp.parserVIDSRCMOV,
            "vidsrc.gd": self.pp.parserVIDSRC,
            "vidsrc.in": self.pp.parserVIDSRC,
            "vidsrc.io": self.pp.parserVIDSRC,
            "vidsrc.me": self.pp.parserVIDSRC,
            "vidsrc.mn": self.pp.parserVIDSRC,
            "vidsrc.mov": self.pp.parserVIDSRCMOV,
            "vidsrc.net": self.pp.parserVIDSRC,
            "vidsrc.pm": self.pp.parserVIDSRC,
            "vidsrc.sh": self.pp.parserVIDSRC,
            "vidsrc.to": self.pp.parserVIDSRC,
            "vidsrc.tw": self.pp.parserVIDSRC,
            "vidsrc.vc": self.pp.parserVIDSRC,
            "vidsrc.xyz": self.pp.parserVIDSRC,
            "vidsrc-embed.ru": self.pp.parserVIDSRC,
            "vidsrc-embed.su": self.pp.parserVIDSRC,
            "vidsrc-me.ru": self.pp.parserVIDSRC,
            "vidsrc-me.su": self.pp.parserVIDSRC,
            "vidsrcme.ru": self.pp.parserVIDSRC,
            "vidsrcme.su": self.pp.parserVIDSRC,
            "vidtube.cam": self.pp.parserJWPLAYER,
            "vidtube.one": self.pp.parserJWPLAYER,
            "vidtube.pro": self.pp.parserJWPLAYER,
            "vidup.to": self.pp.parserVIDCORE,
            "vidvara.fit": self.pp.parserSTREAMUP,  # add 061026
            "vidvara.lol": self.pp.parserSTREAMUP,  # add 061026
            "vidvara.online": self.pp.parserSTREAMUP,  # add 061026
            "vidvara.site": self.pp.parserSTREAMUP,  # add 061026
            "vidwara.art": self.pp.parserSTREAMUP,  # add 061026
            "vidwara.biz": self.pp.parserSTREAMUP,  # add 061026
            "vidwara.cc": self.pp.parserSTREAMUP,  # add 061026
            "vidwara.fit": self.pp.parserSTREAMUP,  # add 061026
            "vidwara.site": self.pp.parserSTREAMUP,  # add 061026
            "vidzy.cc": self.pp.parserJWPLAYER,  # add 061026
            "viewdara.com": self.pp.parserSTREAMUP,  # add 061026
            "vimeo.com": self.pp.parserVIMEO,
            "vixeo.io": self.pp.parserVIXEO,
            "vixsrc.to": self.pp.parserVIXSRC,
            "vk.ru": self.pp.parserVK,
            "voe-un-block.com": self.pp.parserVOESX,  # add 061026
            "voe-unblock.com": self.pp.parserVOESX,  # add 061026
            "voe-unblock.net": self.pp.parserVOESX,  # add 061026
            "voeun-block.net": self.pp.parserVOESX,  # add 061026
            "voeunbl0ck.com": self.pp.parserVOESX,  # add 061026
            "voeunblck.com": self.pp.parserVOESX,  # add 061026
            "voeunblk.com": self.pp.parserVOESX,  # add 061026
            "voeunblock.com": self.pp.parserVOESX,  # add 061026
            "volvovideo.top": self.pp.parserJWPLAYER,  # add 061026
            "vsonic.click": self.pp.parserVIDSONIC,  # add 061026
            "vsrc.su": self.pp.parserVIDSRC,
            "vsembed.ru": self.pp.parserVIDSRC,
            "vsembed.su": self.pp.parserVIDSRC,
            "vidzy.org": self.pp.parserJWPLAYER,
            "vinovo.si": self.pp.parserVINOVO,
            "vinovo.to": self.pp.parserVINOVO,
            "vk.com": self.pp.parserVK,
            "vkvideo.ru": self.pp.parserVK,
            "vkvd298.okcdn.ru": self.pp.parserVK,
            "voe.sx": self.pp.parserVOESX,
            "vrra.top": self.pp.parserVRRATOP,
            "vrrstream.ru": self.pp.parserVRRATOP,
            "vsports.pt": self.pp.parserJWPLAYER,
            "vtbe.net": self.pp.parserJWPLAYER,  # add 061026
            "vtbe.to": self.pp.parserJWPLAYER,
            "vtplay.net": self.pp.parserJWPLAYER,  # add 061026
            "vtube.network": self.pp.parserJWPLAYER,
            "vtube.to": self.pp.parserJWPLAYER,
            "vvide0.com": self.pp.parserDOOD,
            # w
            "w1tv.xyz": self.pp.parserSBS,  # add 061026
            "waaw.ac": self.pp.parserHQQ,
            "waaw.to": self.pp.parserHQQ,
            "waaw.tv": self.pp.parserHQQ,
            "walterprettytheir.com": self.pp.parserVOESX,  # add 061026
            "wasuytm.store": self.pp.parserSBS,
            "watch.brstream.cc": self.pp.parserSTREAMEMBED,  # add 061026
            "watch.ezplayer.me": self.pp.parserSBS,
            "watch.gxplayer.xyz": self.pp.parserSTREAMEMBED,
            "watch.streamcasthub.store": self.pp.parserSBS,  # add 061026
            "watchadsontape.com": self.pp.parserSTREAMTAPE,
            "wavehd.com": self.pp.parserJWPLAYER,
            "webcamera.mobi": self.pp.parserWEBCAMERAPL,
            "webcamera.pl": self.pp.parserWEBCAMERAPL,
            "wishembed.pro": self.pp.parserJWPLAYER,
            "wishfast.top": self.pp.parserJWPLAYER,  # add 061026
            "wishonly.site": self.pp.parserJWPLAYER,
            "wolfdyslectic.com": self.pp.parserVOESX,  # add 061026
            "wrzucaj.pl": self.pp.parserSST,
            # x
            "xcoic.com": self.pp.parserBYSE,
            # y
            "yadi.sk": self.pp.parserYANDEXDISK,
            "yadmalik.sbs": self.pp.parserJWPLAYER,  # add 061026
            "yodelswartlike.com": self.pp.parserVOESX,  # add 061026
            "younetu.com": self.pp.parserHQQ,
            "yourupload.com": self.pp.parserJWPLAYER,
            "youtu.be": self.pp.parserYOUTUBE,
            "youtube-nocookie.com": self.pp.parserYOUTUBE,
            "youtube.com": self.pp.parserYOUTUBE,
            "yucache.net": self.pp.parserJWPLAYER,  # add 061026
            # z
            "z1ekv717.fun": self.pp.parserBYSE
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
        if host == "facebook.com" and ("likebox.php" in url or "like.php" in url or "/groups/" in url):
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
                url = strwithmeta(urltab[idx]["url"])
                if not self.cm.isValidUrl(url):
                    continue
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


# add 061026: rotating-domain families, after ResolveURL (Gujal00) streamwish.py / filelions.py.
# StreamWish domains are often DMCA-blocked or gone, the same file id plays on the current mirrors;
# dhcplay / hglink / hgcloud links belong to a second mirror group
STREAMWISH_DOMAINS = frozenset((
    "streamwish.com", "streamwish.to", "ajmidyad.sbs", "khadhnayad.sbs", "yadmalik.sbs", "hayaatieadhab.sbs", "kharabnahs.sbs",
    "atabkhha.sbs", "atabknha.sbs", "atabknhk.sbs", "atabknhs.sbs", "abkrzkr.sbs", "abkrzkz.sbs", "wishembed.pro", "mwish.pro",
    "strmwis.xyz", "awish.pro", "dwish.pro", "vidmoviesb.xyz", "embedwish.com", "cilootv.store", "uqloads.xyz",
    "tuktukcinema.store", "doodporn.xyz", "ankrzkz.sbs", "volvovideo.top", "streamwish.site", "wishfast.top", "ankrznm.sbs",
    "sfastwish.com", "eghjrutf.sbs", "eghzrutw.sbs", "guxhag.com", "playembed.online", "egsyxurh.sbs", "egtpgrvh.sbs",
    "flaswish.com", "obeywish.com", "cdnwish.com", "javsw.me", "cinemathek.online", "trgsfjll.sbs", "fsdcmo.sbs",
    "hailindihg.com", "anime4low.sbs", "mohahhda.site", "ma2d.store", "dancima.shop", "swhoi.com", "gsfqzmqu.sbs",
    "jodwish.com", "swdyu.com", "strwish.com", "asnwish.com", "kravaxxa.com", "wishonly.site", "playerwish.com",
    "katomen.store", "hlswish.com", "streamwish.fun", "swishsrv.com", "iplayerhls.com", "hlsflast.com", "4yftwvrdz7.sbs",
    "ghbrisk.com", "hgbazooka.com", "eb8gfmjn71.sbs", "cybervynx.com", "edbrdl7pab.sbs", "stbhg.click", "dhcplay.com",
    "strwish.xyz", "gradehgplus.com", "tryzendm.com", "hglink.to", "dumbalag.com", "haxloppd.com", "davioad.com",
    "uasopt.com", "hgcloud.to",
))
STREAMWISH_MIRRORS = ("hglamioz.com", "hgplaycdn.com", "niramirus.com", "playnixes.com", "medixiru.com")
STREAMWISH_MIRRORS_HG = ("hanerix.com", "audinifer.com", "vibuxer.com")
STREAMWISH_HG_DOMAINS = frozenset(("dhcplay.com", "hglink.to", "hgcloud.to"))
# FileLions / VidHide domains that no longer serve the player; the files play on callistanise.com
FILELIONS_DEAD_DOMAINS = frozenset((
    "filelions.com", "filelions.to", "ajmidyadfihayh.sbs", "alhayabambi.sbs", "vidhideplus.com", "azipcdn.com", "mlions.pro",
    "alions.pro", "dlions.pro", "mivalyo.com", "vidhidefast.com", "filelions.live", "motvy55.store", "filelions.xyz",
    "lumiawatch.top", "filelions.online", "fviplions.com", "egsyxutd.sbs", "filelions.site", "filelions.co", "vidhidepre.com",
    "vidhidepro.com", "vidhidevip.com", "e4xb5c2xnz.sbs", "taylorplayer.com", "ryderjet.com", "techradar.ink", "anime7u.com",
    "coolciima.online", "gsfomqu.sbs", "bingezove.com", "katomen.online", "vidhide.fun", "6sfkrspw4u.sbs", "dingtezuni.com",
    "dinisglows.com", "dintezuvio.com",
))
FILELIONS_LIVE_HOST = "callistanise.com"


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

    def parserVRRATOP(self, baseUrl):
        printDBG("parserVRRATOP baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        handshake = self.cm.ph.getSearchGroups(data, r"""var HANDSHAKE = "([^"]+)";""")[0]
        if not handshake:
            handshake = self.cm.ph.getSearchGroups(data, r"""HANDSHAKE\s*=\s*["']([^"^']+?)["']""")[0]
        if not handshake:
            printDBG("parserVRRATOP: Handshake token not found")
            return []
        api_url = "https://vrra.top/api/manifest"
        HTTP_HEADER.update({"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest", "Referer": baseUrl})
        json_data = json_dumps({"h": handshake})
        sts, resp = self.cm.getPage(api_url, {"header": HTTP_HEADER, "raw_post_data": True}, json_data)
        if not sts:
            printDBG("parserVRRATOP: API request failed")
            return []
        try:
            resp_json = json_loads(resp)
            video_url = resp_json.get("url", "")
        except TypeError:
            printDBG("parserVRRATOP: Failed to parse JSON response")
            return []
        if video_url and self.cm.isValidUrl(video_url):
            host = "https://vrra.top/"
            url = urlparser.decorateUrl(video_url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "iptv_proto": "m3u8"})
            if ".m3u8" in video_url:
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
            else:
                urltab.append({"name": "vrra.top", "url": url})
        return urltab

    def parserFREEDISC(self, baseUrl):  # OK according to PL user?
        urltab = []
        COOKIE_FILE = GetCookieDir("FreeDiscPL.cookie")
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0 ", "Accept": "text/html", "Accept-Encoding": "gzip, deflate"}
        params = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True, "load_cookie": True}
        videoId = self.cm.ph.getSearchGroups(baseUrl, r"""\,f\-([0-9]+?)[^0-9]""")[0]
        if videoId == "":
            videoId = self.cm.ph.getSearchGroups(baseUrl, """/video/([0-9]+?)[^0-9]""")[0]
        rest = baseUrl.split("/")[-1].split(",")[-1]
        idx = rest.rfind("-")
        if idx != -1:
            rest = rest[:idx] + ".mp4"
            videoUrl = "https://stream.freedisc.pl/video/%s/%s" % (videoId, rest)
            try:
                params2 = dict(params)
                params2["max_data_size"] = 0
                params2["header"] = dict(HTTP_HEADER)
                params2["header"].update({"Referer": "https://freedisc.pl/static/player/v612/jwplayer.flash.swf"})
                sts, data = self.cm.getPage(videoUrl, params2)
                if self.cm.meta["status_code"] == 200:
                    cookieHeader = self.cm.getCookieHeader(COOKIE_FILE, [], False)
                    urltab.append({"name": "[prepared] freedisc.pl", "url": urlparser.decorateUrl(self.cm.meta["url"], {"Cookie": cookieHeader, "Referer": params2["header"]["Referer"], "User-Agent": params2["header"]["User-Agent"]})})
            except Exception:
                printExc()
        params.update({"load_cookie": False, "cookiefile": GetCookieDir("FreeDiscPL_2.cookie")})
        tmpUrls = []
        if "/embed/" not in baseUrl:
            sts, data = self.cm.getPage(baseUrl, params)
            if not sts:
                return urltab
            try:
                tmp = self.cm.ph.getDataBeetwenMarkers(data, '<script type="application/ld+json">', "</script>", False)[1]
                tmp = json_loads(tmp)
                tmp = tmp["embedUrl"].split("?file=")
                if tmp[1].startswith("https"):
                    urltab.append({"name": "freedisc.pl", "url": urlparser.decorateUrl(tmp[1], {"Referer": tmp[0], "User-Agent": HTTP_HEADER["User-Agent"]})})
                    tmpUrls.append(tmp[1])
            except Exception:
                printExc()
            videoUrl = self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=["'](http[^"^']+?/embed/[^"^']+?)["']""", 1, True)[0]
        else:
            videoUrl = baseUrl
        if videoUrl != "":
            params["load_cookie"] = True
            params["header"]["Referer"] = baseUrl
            sts, data = self.cm.getPage(videoUrl, params)
            if sts:
                videoUrl = self.cm.ph.getSearchGroups(data, """data-video-url=["'](http[^"^']+?)["']""", 1, True)[0]
                if videoUrl == "":
                    videoUrl = self.cm.ph.getSearchGroups(data, r"""player.swf\?file=(http[^"^']+?)["']""", 1, True)[0]
                if videoUrl.startswith("https") and videoUrl not in tmpUrls:
                    urltab.append({"name": "freedisc.pl", "url": urlparser.decorateUrl(videoUrl, {"Referer": "https://freedisc.pl/static/player/v612/jwplayer.flash.swf", "User-Agent": HTTP_HEADER["User-Agent"]})})
        return urltab

    def parserCDA(self, inUrl):
        printDBG("parserCDA inUrl[%r]" % inUrl)
        COOKIE_FILE = GetCookieDir("cdapl.cookie")
        self.cm.clearCookie(COOKIE_FILE, removeNames=["vToken"])
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (PlayStation 4 4.71) AppleWebKit/601.2 (KHTML, like Gecko)"}
        defaultParams = {"header": HTTP_HEADER, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": COOKIE_FILE}

        def getPage(url):
            sts, data = self.cm.getPage(url, defaultParams)
            if self.cm.meta.get("status_code") == 429:
                GetIPTVSleep().Sleep(61)
                sts, data = self.cm.getPage(url, defaultParams)
            return sts, data

        def _decorateUrl(inUrl, referer):
            cookies = []
            cj = self.cm.getCookie(COOKIE_FILE)
            for cookie in cj:
                if (cookie.name == "vToken" and cookie.path in inUrl) or cookie.name == "PHPSESSID":
                    cookies.append("%s=%s;" % (cookie.name, cookie.value))
            retUrl = strwithmeta(inUrl)
            retUrl.meta["User-Agent"] = HTTP_HEADER["User-Agent"]
            retUrl.meta["Referer"] = referer
            retUrl.meta["Cookie"] = " ".join(cookies)
            retUrl.meta["iptv_proto"] = "http"
            retUrl.meta["iptv_urlwithlimit"] = False
            retUrl.meta["iptv_livestream"] = False
            return retUrl

        def getVideoData(data):
            tmp = self.cm.ph.getDataBeetwenMarkers(data, "player_data='", "'", False)[1].strip()
            if tmp == "":
                tmp = self.cm.ph.getDataBeetwenMarkers(data, 'player_data="', '"', False)[1].strip()
            if tmp:
                try:
                    return json_loads(clean_html(tmp).replace("&quot;", '"')).get("video") or {}
                except Exception:
                    printExc()
            return {}

        def decodeFile(dat):
            # obfuscated progressive mp4 link (same decoding as ResolveURL / yt-dlp cda)
            if not dat or self.cm.isValidUrl(dat):
                return dat or ""
            for marker in ("_XDDD", "_CDA", "_ADC", "_CXD", "_QWE", "_Q5", "_IKSDE"):
                dat = dat.replace(marker, "")
            dat = "".join(chr(33 + (ord(c) + 14) % 94) if 32 < ord(c) < 127 else c for c in urllib_unquote(dat))
            dat = dat.replace(".cda.mp4", "").replace(".2cda.pl", ".cda.pl").replace(".3cda.pl", ".cda.pl")
            if "/upstream" in dat:
                return "https://" + dat.replace("/upstream", ".mp4/upstream")
            return "https://" + dat + ".mp4"

        if "/video/" not in inUrl and "ebd.cda.pl/" not in inUrl:
            # a cda page that is not a video page: look for the link to the video
            sts, data = getPage(inUrl)
            if sts:
                sts, match = self.cm.ph.getDataBeetwenMarkers(data, "Link do tego video:", "</a>", False)
                if sts:
                    match = self.cm.ph.getSearchGroups(match, 'href="([^"]+?)"')[0]
                else:
                    match = self.cm.ph.getSearchGroups(data, "link[ ]*?:[ ]*?'([^']+?/video/[^']+?)'")[0]
                if match.startswith("http"):
                    inUrl = match
        if "/video/" in inUrl:
            inUrl = "https://ebd.cda.pl/620x368/" + self.cm.ph.getSearchGroups(inUrl + "/", "/video/([^/]+?)/")[0]
        else:
            inUrl = inUrl.split("?", 1)[0].rstrip("/")
            if inUrl.endswith("/vfilm"):
                inUrl = inUrl[:-6]

        sts, data = getPage(inUrl)
        video = getVideoData(data) if sts else {}
        if not video:
            if sts and ("pakietu premium" in data or "premiumAccess(" in data):
                SetIPTVPlayerLastHostError(_("This video is Premium-only content."))
            elif self.cm.meta.get("status_code") == 404:
                SetIPTVPlayerLastHostError(_("The video has been removed."))
            return []

        videoUrls = []
        if video.get("file"):
            # legacy progressive mp4: one embed page per quality, each with its own obfuscated "file"
            qualities = video.get("qualities") or {}
            for name, code in list(qualities.items()) or [("", "")]:
                if name == "auto":
                    continue
                pageUrl = inUrl
                qVideo = video
                if name and code != video.get("quality"):
                    pageUrl = "%s/vfilm?wersja=%s&a=1&t=0" % (inUrl, name)
                    sts, qData = getPage(pageUrl)
                    qVideo = getVideoData(qData) if sts else {}
                url = decodeFile(qVideo.get("file", ""))
                if url.startswith("http") and url not in [item["url"] for item in videoUrls]:
                    videoUrls.append({"name": ("cda.pl %s" % name).strip(), "url": _decorateUrl(url, pageUrl)})
            videoUrls.sort(key=lambda item: int(self.cm.ph.getSearchGroups(item["name"], r"(\d+)p")[0] or 0), reverse=True)
        if not videoUrls and (video.get("manifest_drm_proxy") or video.get("manifest_drm_header")):
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
            return []
        hlsUrl = video.get("manifest_apple", "")
        if not videoUrls and hlsUrl:
            # cda now serves only DASH/HLS manifests ("file" is empty); the CDN wants the player User-Agent
            hlsUrl = urlparser.decorateUrl(hlsUrl, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": inUrl})
            for item in getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999):
                if item.get("width") and item.get("height"):
                    item["name"] = "cda.pl %dx%d" % (item["width"], item["height"])
                else:
                    item["name"] = "cda.pl " + item["name"]
                videoUrls.append(item)
        return videoUrls

    def parserDAILYMOTION(self, baseUrl):  # fix 180226
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
                    # e.g. DM005 "removed" (410) - the keys vary, raw_message is not always there
                    title = error.get("title") or error.get("raw_message") or error.get("message") or ""
                    printDBG("Error accessing metadata: %s " % title)
                    SetIPTVPlayerLastHostError(title or _("Content not available"))
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
                printExc()
        return urlsTab

    def parserVIMEO(self, baseUrl):  # add 031026 (ResolveURL vimeo.py: player config JSON)
        # vimeo.com/<id>[/<hash>], vimeo.com/channels|groups|showcase/.../<id>, player.vimeo.com/video/<id>[?h=<hash>]
        printDBG("parserVIMEO baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        match = re.search(r"/videos?/(\d{5,})(?:/([0-9a-f]{6,}))?(?:[/?#]|$)", baseUrl)
        if not match:
            match = re.search(r"vimeo\.com/(?:[^/?#]+/)*?(\d{5,})(?:/([0-9a-f]{6,}))?(?:[/?#]|$)", baseUrl)
        if not match:
            return []
        videoId = match.group(1)
        videoHash = match.group(2) or self.cm.ph.getSearchGroups(baseUrl, r"[?&]h=([0-9a-f]+)")[0]
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", "") or "https://vimeo.com/"
        query = ("?h=%s" % videoHash) if videoHash else ""
        playerUrl = "https://player.vimeo.com/video/%s%s" % (videoId, query)

        playerConfig = None
        sts, data = self.cm.getPage(playerUrl, {"header": HTTP_HEADER})
        if sts:
            start = data.find("window.playerConfig")
            start = data.find("{", start) if start > -1 else -1
            if start > -1:
                try:
                    from json import JSONDecoder
                    # raw_decode only finds where the object ends; json_loads parses it the plugin's way
                    # (utf-8 str on Python 2)
                    end = JSONDecoder().raw_decode(data, start)[1]
                    playerConfig = json_loads(data[start:end])
                except Exception:
                    printExc()
        if not isinstance(playerConfig, dict):
            sts, data = self.cm.getPage("https://player.vimeo.com/video/%s/config%s" % (videoId, query), {"header": HTTP_HEADER})
            try:
                playerConfig = json_loads(data) if sts else None
            except Exception:
                playerConfig = None
        if not isinstance(playerConfig, dict) or not isinstance(playerConfig.get("request"), dict):
            SetIPTVPlayerLastHostError(_("Vimeo: this video is private, removed or may only be played on the site that embeds it."))
            return []

        playerHeader = {"Referer": "https://player.vimeo.com/", "Origin": "https://player.vimeo.com", "User-Agent": HTTP_HEADER["User-Agent"]}
        subTracks = []
        for track in playerConfig["request"].get("text_tracks") or []:
            subUrl = track.get("url", "")
            if subUrl.startswith("/"):
                subUrl = "https://player.vimeo.com" + subUrl
            if self.cm.isValidUrl(subUrl):
                subTracks.append({"title": track.get("label") or track.get("lang", ""), "url": subUrl, "lang": track.get("lang", ""), "format": "vtt"})

        urlTab = []
        files = playerConfig["request"].get("files") or {}
        for item in sorted(files.get("progressive") or [], key=lambda x: int(x.get("height", 0) or 0), reverse=True):
            if item.get("url"):
                meta = dict(playerHeader)
                if subTracks:
                    meta["external_sub_tracks"] = subTracks
                urlTab.append({"name": "vimeo.com: %s mp4" % item.get("quality", ""), "url": urlparser.decorateUrl(item["url"], meta)})

        hls = files.get("hls") or {}
        cdns = hls.get("cdns") or {}
        cdnOrder = [hls.get("default_cdn")] + sorted([key for key in cdns if key != hls.get("default_cdn")])
        hlsUrl = ""
        drm = False
        for cdn in cdnOrder:
            for key in ("avc_url", "url"):
                url = (cdns.get(cdn) or {}).get(key, "")
                if not url:
                    continue
                if "/drm/" in url:
                    drm = True
                    continue
                hlsUrl = url
                break
            if hlsUrl:
                break
        if hlsUrl:
            meta = dict(playerHeader)
            meta["iptv_proto"] = "m3u8"
            if subTracks:
                meta["external_sub_tracks"] = subTracks
            urlTab.extend(getDirectM3U8Playlist(urlparser.decorateUrl(hlsUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
        if not urlTab and drm:
            SetIPTVPlayerLastHostError(_("Video with DRM protection."))
        return urlTab

    def parserVK(self, baseUrl):  # Partly work, Login not work
        printDBG("parserVK url[%s]" % baseUrl)
        COOKIE_FILE = GetCookieDir("vkcom.cookie")
        HTTP_HEADER = {"User-Agent": self.cm.getDefaultUserAgent("chrome")}
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
        # first call of this session: no remembered login yet (not an error)
        if not hasattr(self, "vkcom_login"):
            rm(COOKIE_FILE)
            self.vkcom_login = ""
            self.vkcom_pass = ""
        vkcom_login = self.vkcom_login
        vkcom_pass = self.vkcom_pass
        if '<div id="video_ext_msg">' in data or vkcom_login != login or vkcom_pass != password:
            rm(COOKIE_FILE)
            self.vkcom_login = login
            self.vkcom_pass = password
            if login.strip() == "" or password.strip() == "":
                # the embed's own reason first (e.g. "hidden by privacy settings") - a login only helps if it has access
                siteMsg = self.cm.ph.getDataBeetwenMarkers(data, '<div id="video_ext_msg">', "</div>", False)[1]
                siteMsg = clean_html(siteMsg).strip()
                msg = _("To watch videos from https://vk.com/ you need to login.\nPlease fill your login and password in the IPTVPlayer configuration.")
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, (siteMsg + "\n\n" + msg) if siteMsg else msg, type=MessageBox.TYPE_INFO, timeout=10)
                return False
            elif not _doLogin(login, password):
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, _('Login user "%s" to https://vk.com/ failed!\nPlease check your login data in the IPTVPlayer configuration.') % login, type=MessageBox.TYPE_INFO, timeout=10)
                return False
            else:
                sts, data = self.cm.getPage(baseUrl, params)
                if not sts:
                    return False
        movieUrls = []
        item = self.cm.ph.getSearchGroups(data, r"""['"]?cache([0-9]+?)['"]?[=:]['"]?(http[^"]+?\.mp4[^;^"^']*)[;"']""", 2)
        if item[1] != "":
            cacheItem = {"name": "vk.com: " + item[0] + "p (cache)", "url": item[1].replace("\\/", "/")}
        else:
            cacheItem = None
        tmpTab = re.findall(r"""['"]?url([0-9]+?)['"]?[=:]['"]?(http[^"]+?\.mp4[^;^"^']*)[;"']""", data)
        # current player params: "mp4_720":"https:\/\/vkvd...okcdn.ru\/?..." (no .mp4 in the url)
        tmpTab.extend(re.findall(r'''"mp4_([0-9]+)":"(https?:[^"]+)"''', data))
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
                movieUrls.append({"name": "vk.com: " + item[0] + "p", "url": item[1]})
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
        # the stream urls are bound to the browser family of the page request (srcAg=CHROME):
        # another User-Agent in the player gets "400 Bad Request"
        for item in movieUrls:
            item["url"] = strwithmeta(item["url"], {"User-Agent": HTTP_HEADER["User-Agent"]})
        if not movieUrls:
            hlsUrl = self.cm.ph.getSearchGroups(data, r'''"hls":"(https?:[^"]+)"''')[0].replace("\\/", "/")
            if hlsUrl:
                movieUrls = getDirectM3U8Playlist(strwithmeta(hlsUrl, {"User-Agent": HTTP_HEADER["User-Agent"]}), checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
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
                height = config.plugins.iptvplayer.ytDefaultformat.value
                dash = self.getYTParser().isDashAllowed()
                vp9 = self.getYTParser().isVP9Allowed()
            except Exception:
                printDBG("parserYOUTUBE default ytDefaultformat not available here")
                height = "360"
                dash = False
                vp9 = False
            tmpTab, dashTab = self.getYTParser().getDirectLinks(url, dash, dashSepareteList=True, allowVP9=vp9)
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
            sts, tmp = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return False
            data += tmp
            cUrl = self.cm.meta["url"]
        blob = ph.search(data, """['"]([a-zA-Z0-9=]{128,512})['"]""")[0]
        if not blob:
            # upzone.cc caps free-user transfer and then serves a stripped
            # "premium only" page with no player payload (Polish: "Transfer dla
            # darmowych uzytkownikow zostal wyczerpany ... PREMIUM").
            if "wyczerpany" in data or "PREMIUM" in data:
                SetIPTVPlayerLastHostError(_("upzone.cc: free transfer limit reached - PREMIUM account required."))
            return False
        js_params = [{"path": GetJSScriptFile("upzonecc.byte")}]
        js_params.append({"code": "print(cnc(atob('%s')));" % blob})
        ret = js_execute_ext(js_params)
        streamUrl = (ret.get("data", "") if ret else "").strip()
        if not streamUrl:
            return False
        url = self.cm.getFullUrl(streamUrl, cUrl)
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
        notice = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "notice"), ("</div", ">"), False)[1])
        # fix 041026: guest page = 'var ct = 60;' countdown, the POST is refused ("all free guest slots in use") before it ends
        countdown = int(self.cm.ph.getSearchGroups(data, r"""var\s+ct\s*=\s*([0-9]+)""")[0] or 0)
        data = self.cm.ph.getDataBeetwenNodes(data, ("<form", ">", "post"), ("</form", ">"), caseSensitive=False)[1]
        printDBG("++++")
        action = self.cm.ph.getSearchGroups(data, """action=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, "<input", ">", caseSensitive=False)
        all_post_data = {}
        for item in tmp:
            name = self.cm.ph.getSearchGroups(item, """name=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
            value = self.cm.ph.getSearchGroups(item, """value=['"]([^'^"]+?)['"]""", ignoreCase=True)[0]
            all_post_data[name] = value
        if "adzone" not in all_post_data and "dl_no_ssl" not in all_post_data:
            # no download form: file removed (404 page) or layout changed (fix 041026: the form has no adzone field any more)
            SetIPTVPlayerLastHostError(notice or error or _("Content not available"))
            return False
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
        post_data = {"dl_no_ssl": "on"}
        if "adzone" in all_post_data:
            post_data["adzone"] = all_post_data["adzone"]
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
            if countdown > 0:
                GetIPTVSleep().Sleep(min(countdown, 120) + 1)
            params["header"]["Referer"] = baseUrl
            sts, data = self.cm.getPage(action, params, post_data)
            if not sts:
                return False
            videoUrl = self.cm.ph.getSearchGroups(data, """<a[^>]+?href=['"](https?://[^'^"]+?)['"][^>]+?ok btn-general""")[0]
            if not videoUrl:
                # fix 041026: refusal reason in <div class="notice"> ("High demand: all free guest slots are currently in use.")
                notice = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "notice"), ("</div", ">"), False)[1])
                if notice:
                    SetIPTVPlayerLastHostError(notice)
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
        if "/error.php?errno=" in self.cm.meta.get("url", "") or self.cm.meta.get("status_code") == 404:
            # add 041026: removed file -> 302 to error.php?errno=320 ("Invalid or Deleted File")
            SetIPTVPlayerLastHostError(_("The video has been removed."))
            return False
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
        def voe_decode(ct, lut=None):
            txt = "".join(chr((ord(i) - 52) % 26 + 65) if 65 <= ord(i) <= 90 else chr((ord(i) - 84) % 26 + 97) if 97 <= ord(i) <= 122 else i for i in ct)
            if not lut:
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
        if not sts or not any(marker in data for marker in ("const currentUrl", "application/json", '";function', "hls")):
            # add 061026: VOE drops its rotation domains quickly (gone, or parked with a "Redirecting..." page);
            # the file id still plays via voe.sx
            fileId = ph.search(baseUrl, r"//[^/]+/(?:e/)?([0-9A-Za-z]+)")[0]
            if not fileId or "//voe.sx/" in baseUrl:
                return False
            printDBG("parserVOESX %s gone or no VOE page -> voe.sx" % urlparser.getDomain(baseUrl))
            sts, data = self.cm.getPage("https://voe.sx/e/%s" % fileId)
            if not sts:
                return False
        pageUrl = self.cm.meta.get("url", baseUrl)
        # fix 061026: the redirect page can lead to another redirect page (after ResolveURL voesx.py)
        for _hop in range(5):
            if "const currentUrl" not in data:
                break
            nextUrl = ph.search(data, r"""window.location.href\s*=\s*['"]([^"^']+?)['"]""")[0]
            if not nextUrl:
                break
            pageUrl = nextUrl
            sts, data = self.cm.getPage(pageUrl)
            if not sts:
                return False
        if "<title>404" in data:
            SetIPTVPlayerLastHostError(_("The video has been removed."))
            return []
        # add 061026: the junk strings of the decoder change with VOE's player script, which lists them
        # (['@$','^^',...]); the built-in list stays the fallback
        lut = None
        script = ph.search(data, r"""json">\["[^"]+"]</script>\s*<script\s*src="([^"]+)""")[0]
        if script:
            stsS, dataS = self.cm.getPage(urljoin(pageUrl, script))
            table = ph.search(dataS, r"""(\[(?:'\W{2}'[,\]]){1,9})""")[0] if stsS else ""
            if table:
                lut = [re.escape(x) for x in table[2:-2].split("','")]
                printDBG("parserVOESX junk table from the player script: %s" % table)
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
                payload = ensure_str(r.group(1))
                r = voe_decode(payload, lut)
                if not r and lut:
                    r = voe_decode(payload)
                if r:
                    subtitles = [{"title": "", "lang": x.get("label"), "url": urljoin(pageUrl, x.get("file"))} for x in r.get("captions", []) if x.get("kind") == "captions"]
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
                for _x in range(count):
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

    def parserDOOD(self, baseUrl):  # update 240926
        urlsTab = []
        sub_tracks = []
        printDBG("parserDOOD baseUrl [%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        urlParams = {"header": HTTP_HEADER}
        urls = ["all3do.com", "d0000d.com", "d000d.com", "d0o0d.com", "d-s.io", "do0od.com", "dooodster.com", "doodstream.com", "doply.net", "dooood.com", "do7go.com", "ds2play.com", "ds2video.com", "dood.cx", "dood.la", "dood.li", "dood.pm", "dood.re", "dood.sh", "dood.so", "dood.stream", "dood.to", "dood.watch", "dood.work", "dood.wf", "dood.ws", "dood.yt", "doods.pro", "doodcdn.io", "vide0.net", "vidply.com", "vvide0.com", "playmogo.com"]
        baseUrl = baseUrl.replace("/w/", "/e/")  # watch page -> embed page
        # fix 041026: the /d/ download page now says "Video not found" while /e/<same id> still plays (ds2play/playmogo)
        baseUrl = re.sub(r"(https?://[^/]+)/d/", r"\1/e/", baseUrl)
        # the embed domain redirects to the current mirror (vide0.net -> playmogo.com);
        # dead mirrors (d-s.io: no DNS) fall back to that mirror, then dsvplay.com
        # (some providers block dsvplay.com with a connection reset)
        candidates = [baseUrl]
        for url in urls:
            if url in baseUrl:
                candidates.extend(baseUrl.replace(url, mirror) for mirror in ("playmogo.com", "dsvplay.com") if mirror != url)
                break
        sts, data = False, ""
        for baseUrl in candidates:
            sts, data = self.cm.getPage(baseUrl, urlParams)
            if sts:
                baseUrl = self.cm.meta.get("url", "") or baseUrl
                break
        if not sts:
            return []
        if "<title>Video not found" in data:
            SetIPTVPlayerLastHostError(_("The video has been removed."))
            return []
        host = "https://%s" % urlparser.getDomain(baseUrl, True)
        if "/d/" in baseUrl:
            # /d/ links were rewritten to /e/ above - this only happens when the mirror redirects back to a /d/ page
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
            url = urlparser.decorateUrl(url, {"external_sub_tracks": sub_tracks, "User-Agent": urlParams["header"]["User-Agent"], "Referer": baseUrl, "iptv_format": "mp4"})
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
        if code == 404 and httpParams["header"]["Referer"] != baseUrl:
            # 041026: a domain-locked video answers 404 "not found" to any foreign Referer
            httpParams["header"]["Referer"] = baseUrl
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
            t = self.cm.ph.getSearchGroups(data, """innerHTML = ([^;]+?);""")[0]
            if not t:
                # no player token in the page - streamtape now serves a
                # bot/geo wall (HTTP 200 with an interstitial) instead of the
                # real embed; bail out cleanly instead of eval()-ing garbage.
                printDBG("parserSTREAMTAPE no innerHTML token - page blocked?")
                return urltabs
            t = t + ";"
            printDBG("parserSTREAMTAPE t[%s]" % t)
            t = t.replace(".substring(", "[", 1).replace(").substring(", ":][").replace(");", ":]") + "[1:]"
            try:
                # parsed, not executed - the expression comes from the page
                t = safeEvalExpression(t)
            except Exception:
                printExc()
                return urltabs
            if t.startswith("/"):
                t = "https:/" + t
            if self.cm.isValidUrl(t):
                cookieHeader = self.cm.getCookieHeader(COOKIE_FILE, [], False)
                params = {"Cookie": cookieHeader, "Referer": httpParams["header"]["Referer"], "User-Agent": httpParams["header"]["User-Agent"]}
                params["external_sub_tracks"] = subTracks
                params["iptv_format"] = "mp4"  # /get_video?id=... redirects to the mp4
                t = urlparser.decorateUrl(t, params)
                params = {"name": "link", "url": t}
                urltabs.append(params)
        return urltabs

    def parserSST(self, url):  # update 020926
        printDBG("parserSST baseUrl[%s]" % url)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER, "with_metadata": True})
        if not sts:
            return []
        host = urlparser.getDomain(getattr(data, "meta", {}).get("url", url), False)  # fsst.online -> incvideo1.online after redirect
        meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]}
        urltab = []
        srcList = re.findall(r'<source[^>]*src="([^"]+)"[^>]*label="([^"]+)"', data)
        if srcList:
            for surl, q in srcList:
                urltab.append({"name": q, "url": urlparser.decorateUrl(surl, dict(meta))})
            return urltab
        m = re.search(r'file\s*:\s*"([^"]+)"', data)
        if not m:
            return []
        fileUrl = m.group(1)
        if "[" in fileUrl:  # Playerjs multi-quality: [360p]url,[720p]url
            for quality, qurl in re.findall(r"\[(\d+p)\](https?://[^\s,\]]+)", fileUrl):
                urltab.append({"name": quality, "url": urlparser.decorateUrl(qurl, dict(meta))})
        elif self.cm.isValidUrl(fileUrl):
            q = self.cm.ph.getSearchGroups(data, r'default_quality\s*:\s*"([^"]+)')[0] or "MP4"
            urltab.append({"name": q, "url": urlparser.decorateUrl(fileUrl, dict(meta))})
        return urltab

    def parserSBS(self, baseUrl):  # update 031026
        printDBG("parserSBS baseUrl[%s]" % baseUrl)
        # strp2p / upn / rpmplay player family: <domain>/#<id> -> api/v1/video (hex, AES-128-CBC)
        # key/iv are still built in the player JS (kiemtienmua911ca / 1234567890oiuytr);
        # a deleted video answers 404 {"message": "Video not found or deleted"}
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        referer = baseUrl.meta.get("Referer", "")
        url = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER["Referer"] = url
        urlParams = {"header": HTTP_HEADER, "ignore_http_code_ranges": [(400, 599)]}
        apiUrl = baseUrl
        if "#" in baseUrl:
            videoId = baseUrl.split("#", 1)[1].split("&", 1)[0]
            host = referer.split("/")[2] if self.cm.isValidUrl(referer) else ""
            if host.startswith("www."):
                host = host[4:]
            apiUrl = "%sapi/v1/video?id=%s&w=1920&h=1080&r=%s" % (url, videoId, host)

        def _getVideo(addParams=""):
            sts, data = self.cm.getPage(apiUrl + addParams, urlParams)
            if not sts or not data:
                return None, _("Content not available")
            data = data.strip()
            if not re.match(r"^[0-9a-fA-F]+$", data):
                msg = ""
                try:
                    msg = json_loads(data).get("message", "")
                except Exception:
                    printDBG("parserSBS: no video data [%s]" % data[:100])  # HTML error page: no traceback
                return None, msg or _("Content not available")
            try:
                decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(b"kiemtienmua911ca", b"1234567890oiuytr"))
                data = decrypter.feed(unhexlify(data))
                data += decrypter.feed()
                return json_loads(data.decode("utf-8")), ""
            except Exception:
                printExc()
            return None, _("Content not available")

        data, msg = _getVideo()
        if data and not data.get("source"):
            # in-house streaming saturated -> the player retries with a capacity token
            delivery = data.get("delivery") or {}
            if delivery.get("capacityToken") and delivery.get("capacityTokenExpire"):
                GetIPTVSleep().Sleep(min(15, max(2, int(delivery.get("retryAfter") or 3))))
                data, msg = _getVideo("&capacityToken=%s&capacityTokenExpire=%s" % (urllib_quote(str(delivery["capacityToken"])), urllib_quote(str(delivery["capacityTokenExpire"]))))
        if not data:
            SetIPTVPlayerLastHostError(msg)
            return []

        subTracks = []
        subtitle = data.get("subtitle") or {}
        if isinstance(subtitle, dict):
            for lang, src in subtitle.items():
                if src.startswith("/"):
                    src = url[:-1] + src.split("#")[0]
                subTracks.append({"title": lang, "url": src, "lang": lang})

        urltab = []
        hls = data.get("source")
        if hls:
            # source (in-house, fMP4 HLS) needs Referer + Origin of the player domain, 403 without
            hls = urlparser.decorateUrl(hls, {"iptv_proto": "m3u8", "User-Agent": HTTP_HEADER["User-Agent"], "Referer": url, "Origin": url[:-1], "external_sub_tracks": subTracks})
            urltab.extend(getDirectM3U8Playlist(hls, checkContent=True, sortWithMaxBitrate=999999999))
        if not urltab and data.get("cfNative"):
            hls = urlparser.decorateUrl(data["cfNative"], {"iptv_proto": "m3u8", "User-Agent": HTTP_HEADER["User-Agent"], "Referer": url, "Origin": url[:-1], "external_sub_tracks": subTracks})
            urltab.extend(getDirectM3U8Playlist(hls, checkContent=True, sortWithMaxBitrate=999999999))
        return urltab

    def parserVINOVO(self, baseUrl):  # fix 15.06.25, update 031026
        printDBG("parserVINOVO baseUrl[%s]" % baseUrl)
        COOKIE_FILE = self.COOKIE_PATH + "vinovo.cookie"
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        params = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE}
        pageUrl = re.sub(r"/(?:d|v|f)/", "/e/", baseUrl.split("?")[0], count=1)
        sts, data = self.cm.getPage(pageUrl, params)
        if not sts:
            return []
        # vinovo.si redirects to vinovo.to - take the domain we really landed on
        finalUrl = self.cm.meta.get("url", "") or pageUrl
        if self.cm.isValidUrl(finalUrl):
            pageUrl = finalUrl
        token = re.search(r'name="token"\s*content="([^"]+)', data)
        videoBase = re.search(r'data-base="([^"]+)', data)
        fileCode = re.search(r'name="file_code"\s*content="([^"]+)', data) or re.search(r'file_code"\s*(?:content)?="([^"]+)', data)
        if not (token and videoBase and fileCode):
            printDBG("parserVINOVO: player data not found")
            return []
        rurl = urljoin(pageUrl, "/")
        apiUrl = "%sapi/file/url/%s" % (rurl, fileCode.group(1))
        apiHeader = dict(HTTP_HEADER)
        apiHeader.update({"Origin": rurl[:-1], "Referer": pageUrl, "X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/javascript, */*; q=0.01"})
        apiParams = {"header": apiHeader, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE}

        # reCAPTCHA v3 (invisible) token; the player itself posts an empty one when grecaptcha fails, so retry with ""
        recaptcha = ""
        try:
            recaptcha = girc(data, rurl) or ""
        except Exception:
            printExc()
        streamToken = ""
        for rc in ([recaptcha, ""] if recaptcha else [""]):
            sts, resp = self.cm.getPage(apiUrl, apiParams, {"token": token.group(1), "recaptcha": rc})
            if not sts:
                continue
            try:
                resp = json_loads(resp)
            except Exception:
                printExc()
                continue
            printDBG("parserVINOVO api status[%s]" % resp.get("status"))
            if resp.get("status") == "ok" and resp.get("token"):
                streamToken = resp["token"]
                break
        if not streamToken:
            return []
        vidUrl = "%s/stream/%s" % (videoBase.group(1).rstrip("/"), streamToken)
        meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": pageUrl, "Origin": rurl[:-1], "iptv_format": "mp4"}
        return [{"name": "vinovo MP4", "url": urlparser.decorateUrl(vidUrl, meta)}]

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
            urltab = getDirectM3U8Playlist(url, checkExt=False, variantCheck=False, checkContent=True, cookieParams={"header": headers, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True})
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
        pageParams = {"header": HTTP_HEADER, "collect_all_headers": True}

        def grabSlCookie(prev):
            m = re.search(r"\bsl=([^;\s]+)", self.cm.meta.get("set-cookie", ""))
            if m and m.group(1) != "deleted":
                return "sl=" + m.group(1)
            return prev

        videaXml = ""
        slCookie = ""
        for _retry in range(3):
            sts, data = self.cm.getPage(baseUrl, dict(pageParams))
            if not sts:
                return []
            slCookie = grabSlCookie(slCookie)
            url = baseUrl if "/player" in baseUrl else urljoin(baseUrl, re.search(r'<iframe.*?src="(/player\?[^"]+)"', data).group(1))
            sts, nonce = self.cm.getPage(url, dict(pageParams))
            if not sts:
                return []
            slCookie = grabSlCookie(slCookie)
            nonce = re.search(r'_xt\s*=\s*"([^"]+)"', nonce).group(1)
            l, s = nonce[:32], nonce[32:]
            result = "".join(s[i - (STATIC_SECRET.index(l[i]) - 31)] for i in range(32))
            query = parse_qs(urlparse(url).query)
            _s = random_seed(8)
            _t = result[:16]
            _param = "f=%s" % query["f"][0] if "f" in query else "v=%s" % query["v"][0]
            hurl = "https://%s/player/xml?platform=desktop&%s&_s=%s&_t=%s" % (urlparser.getDomain(baseUrl), _param, _s, _t)
            sts, videaXml = self.cm.getPage(hurl, dict(pageParams))
            if not sts:
                return []
            slCookie = grabSlCookie(slCookie)
            if not videaXml.startswith("<?xml"):
                key = result[16:] + _s + self.cm.meta.get("x-videa-xs", "")
                videaXml = rc4(videaXml, key)
            noembed = re.search(r'<error.*?"noembed".*?>\s*(.*?)\s*</error>', videaXml)
            if not noembed:
                break
            newUrl = noembed.group(1).strip().replace("&amp;", "&")
            if newUrl.startswith("//"):
                newUrl = "https:" + newUrl
            elif newUrl.startswith("/"):
                newUrl = urljoin(baseUrl, newUrl)
            if not newUrl.lower().startswith("http"):
                break
            printDBG("parserVIDEA noembed redirect -> [%s]" % newUrl)
            baseUrl = newUrl
        else:
            return []

        subTracks = []
        for block in re.findall(r"<subtitle\b[^>]*>", videaXml):
            src = self.cm.ph.getSearchGroups(block, r'src="([^"]+)"')[0].replace("&amp;", "&")
            lang = self.cm.ph.getSearchGroups(block, r'(?:title|lang|language)="([^"]+)"')[0]
            if not src:
                continue
            src = "https:" + src if src.startswith("//") else src
            subTracks.append({"title": lang, "url": src, "lang": lang or "und"})

        urltab = []
        for block in re.findall(r"<video_source\b[^>]*>[^<]*</video_source>", videaXml):
            label = self.cm.ph.getSearchGroups(block, r'name="([^"]+)"')[0]
            exp = self.cm.ph.getSearchGroups(block, r'exp="([^"]*)"')[0]
            url = self.cm.ph.getDataBeetwenMarkers(block, ">", "</video_source>", False)[1].replace("&amp;", "&")
            if not url:
                continue
            url = "https:" + url if url.startswith("//") else url
            if "md5=" not in url:
                hsh = re.search(r"<hash_value_%s>([^<]+)<" % re.escape(label), videaXml)
                if not hsh:
                    continue
                if not exp:
                    exp = self.cm.ph.getSearchGroups(url, r"expires=([0-9]+)")[0]
                url = "%s?md5=%s&expires=%s" % (url, hsh.group(1), exp)
            # the CDN paths carry no file extension (.../1.29.12.3456789.1)
            fmt = self.cm.ph.getSearchGroups(block, r'mimetype="video/([a-z0-9]+)"')[0] or "mp4"
            urltab.append({"name": label, "url": strwithmeta(url, {"iptv_format": fmt})})
        urltab.reverse()
        if not urltab:
            mhls = re.search(r"<master_playlist_url>([^<]+)", videaXml)
            if mhls:
                hlsUrl = mhls.group(1).strip().replace("&amp;", "&")
                hlsUrl = "https:" + hlsUrl if hlsUrl.startswith("//") else hlsUrl
                urltab.append({"name": "HLS", "url": strwithmeta(hlsUrl, {"iptv_proto": "m3u8"})})
        if not urltab:
            for block in re.findall(r"<audio_source\b[^>]*>[^<]*</audio_source>", videaXml):
                url = self.cm.ph.getDataBeetwenMarkers(block, ">", "</audio_source>", False)[1].replace("&amp;", "&")
                if not url:
                    continue
                url = "https:" + url if url.startswith("//") else url
                urltab.append({"name": "Audio", "url": url})
        try:
            autoQuality = config.plugins.iptvplayer.videa_quality.value
        except Exception:
            autoQuality = False
        if autoQuality and urltab:
            best_source = None
            best_quality = 0
            for source in urltab:
                match = re.search(r"(\d{3,4})\s*[pP]", source.get("name", ""))
                if match and int(match.group(1)) > best_quality:
                    best_quality = int(match.group(1))
                    best_source = source
            if best_source:
                printDBG("Videa: Auto quality selected [%s] - %sp" % (best_source.get("name", ""), best_quality))
                urltab = [best_source]
        extraMeta = {}
        if slCookie:
            extraMeta["Cookie"] = slCookie
        if subTracks:
            extraMeta["external_sub_tracks"] = subTracks
        if extraMeta:
            for item in urltab:
                item["url"] = strwithmeta(item["url"], extraMeta)
        return urltab

    def parserSTREAMUP(self, baseUrl):  # fix 300426
        printDBG("parserSTREAMUP baseUrl[%s]" % baseUrl)
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        filecode = self.cm.ph.getSearchGroups(baseUrl, r"https:\/\/[a-zA-Z0-9.]+\/(?:e\/|v\/)?([A-Za-z0-9]+)")
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl
        HTTP_HEADER["Origin"] = host[:-1]
        post = json_dumps({"filecode": filecode[0], "device": "web"})
        sts, data = self.cm.getPage(host + "api/stream", {"header": HTTP_HEADER, "raw_post_data": True}, post)
        if not sts:
            return []
        try:
            # a dead strmup mirror redirects /api/stream to a parked domain that
            # answers 200 with a few bytes of HTML - don't crash on that
            data = json_loads(data)
        except Exception:
            printDBG("parserSTREAMUP non-JSON response - host down/parked?")
            return []
        url = data.get("streaming_url")
        if isinstance(data.get("subtitles"), list):
            subTracks = [{"title": "", "url": sub.get("file_path"), "lang": sub.get("language")} for sub in data.get("subtitles", []) if sub.get("file_path") and sub.get("language")]
        if url:
            url = url.replace("\r", "").replace("\n", "")
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            if ".m3u8" in url:
                # 041026: vidara's CDN (*.97bf1.com) now serves the segments as seg_*.js
                urltab.extend(requireDownloaderForDisguisedHls(getDirectM3U8Playlist(url)))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserFIRESTREAM(self, baseUrl):  # add 020926 - firestream.to (filmpalast/kinoger "Firestream HD")
        printDBG("parserFIRESTREAM baseUrl[%s]" % baseUrl)
        urltab = []
        host = urlparser.getDomain(baseUrl, False)
        mid = self.cm.ph.getSearchGroups(baseUrl, r"/(?:e|v)/([0-9A-Za-z_-]+)")[0]
        if mid == "":
            return []
        HTTP_HEADER = self.cm.getDefaultHeader()
        embedUrl = "%se/%s" % (host, mid)
        HTTP_HEADER["Referer"] = embedUrl
        sts, data = self.cm.getPage(embedUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        blob = self.cm.ph.getSearchGroups(data, r'id="token-blob"[^>]*>([^<]+)')[0].strip()
        if blob == "":
            return []
        postHeader = dict(HTTP_HEADER)
        postHeader.update({"Referer": embedUrl, "Origin": host[:-1], "Content-Type": "application/json"})
        sts, data = self.cm.getPage("%sapi/videos/%s/resolve" % (host, mid), {"header": postHeader, "raw_post_data": True}, json_dumps({"blob": blob}))
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        for key, name in (("signedVideoUrl", "HD"), ("signedVideoSdUrl", "SD")):
            url = data.get(key)
            if not url:
                continue
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            if ".m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url))
            else:
                urltab.append({"name": name, "url": url})
        return urltab

    def parserPLAYMATE(self, baseUrl):  # add 020926 - playmate.to (filmpalast "Playmate HD")
        printDBG("parserPLAYMATE baseUrl[%s]" % baseUrl)
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        mid = self.cm.ph.getSearchGroups(baseUrl, r"/(?:watch|embed|e|v)/([0-9A-Za-z]+)")[0]
        if mid == "":
            return []
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER.update({"Referer": "%sembed/%s" % (host, mid), "Origin": host[:-1], "Content-Type": "application/json"})
        sts, data = self.cm.getPage("%sapi/s" % host, {"header": HTTP_HEADER, "raw_post_data": True}, json_dumps({"c": mid, "d": "web"}))
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        for sub in (data.get("kx") or []):
            surl = sub.get("sf") or sub.get("file") or ""
            if surl:
                subTracks.append({"title": "", "url": "https:" + surl if surl.startswith("//") else surl, "lang": sub.get("sl") or sub.get("label") or ""})
        url = data.get("sx")
        if not url:
            return []
        meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks}
        if ".m3u8" in url or "/hls/" in url or url.split("?")[0].endswith(".txt"):
            # playmate's HLS master/variant playlists use a .txt extension AND the
            # segments are disguised as .css/.js/.woff (anti-adblock). exteplayer3's
            # ffmpeg refuses that ("Invalid data found"); hlsdl handles it
            meta["iptv_proto"] = "m3u8"
            meta["iptv_buffering"] = "required"
            urltab.append({"name": "HLS", "url": urlparser.decorateUrl(url, meta)})
        else:
            urltab.append({"name": "MP4", "url": urlparser.decorateUrl(url, meta)})
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

    BYSE_ACCESS = {}  # parserBYSE: player domain -> (valid until, fingerprint, captcha token)

    def parserBYSE(self, baseUrl):  # fix 240826 - captcha/proof-of-work challenge support
        UA = "Mozilla/5.0 (Linux; Android 10; TX6s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"

        def fp(x, y, z):  # thx Gujal00
            v_id = hexlify(urandom(x)).decode()
            d_id = hexlify(urandom(x)).decode()
            ctime = int(time.time())
            t_data = {"viewer_id": v_id, "device_id": d_id, "confidence": round(uniform(y, z), 2), "iat": ctime, "exp": ctime + 600}
            t_bdata = b64urlEncode(json_dumps(t_data), strip=True)
            t_sig = b64urlEncode(sha256(t_bdata.encode()).digest(), strip=True)
            token = "{0}.{1}".format(t_bdata, t_sig)
            t_data.update({"token": token})
            t_data.pop("iat")
            t_data.pop("exp")
            return {"fingerprint": t_data}

        def ft(e):
            t = e.replace("-", "+").replace("_", "/")
            r = 0 if len(t) % 4 == 0 else 4 - len(t) % 4
            n = t + "=" * r
            return base64.b64decode(n)

        def xn(e, v):
            if v:
                v = int(v)
                if 0 < v <= len(e):
                    e = [e[v - 1], e[len(e) - v]]
            t = list(map(ft, e))
            return b"".join(t)

        def fh(v):
            return b64urlEncode(sha256(str(v).encode("ascii")).digest(), strip=True)

        def wn(challenge):
            sk = ECDSA_SigningKey.generate(curve=ECDSA_NIST256p, hashfunc=sha256)
            vk = sk.verifying_key.to_string()
            nonce = str(challenge.get("nonce") or "")
            signature = sk.sign(nonce.encode(), hashfunc=sha256)
            pub = {"crv": "P-256", "ext": True, "key_ops": ["verify"], "kty": "EC", "x": b64urlEncode(vk[:32], strip=True), "y": b64urlEncode(vk[32:], strip=True)}
            r = uniform(0, 1)
            return {
                "viewer_id": "", "device_id": "", "challenge_id": challenge.get("challenge_id", ""), "nonce": nonce,
                "signature": b64urlEncode(signature, strip=True), "public_key": pub,
                "client": {
                    "user_agent": UA, "architecture": "arm", "bitness": "32", "platform": "Android", "platform_version": "10.0.0",
                    "model": "TX6s", "ua_full_version": "137.0.7337.0",
                    "brand_full_versions": [{"brand": "Chromium", "version": "137.0.7337.0"}],
                    "pixel_ratio": 1, "screen_width": 1280, "screen_height": 720, "color_depth": 24,
                    "languages": ["en-US"], "timezone": "America/New_York", "hardware_concurrency": 4, "device_memory": 2,
                    "touch_points": 1, "webgl_vendor": "Google Inc. (ARM)", "webgl_renderer": "ANGLE (ARM, Mali-G31 MP2, OpenGL ES 3.2)",
                    "canvas_hash": fh(r), "audio_hash": fh(r + 1), "webgl_params_hash": fh(r + 2), "fonts_hash": fh(r + 3), "codecs_hash": fh(r + 4),
                    "media_devices": "ai1ao1vi4", "pointer_type": "coarse",
                    "extra": {"vendor": "Google Inc.", "appVersion": UA[len("Mozilla/"):]},
                },
                "storage": {}, "attributes": {"entropy": "high"},
            }

        # Proof of work of the player (assets/pow-*.js: gr/wr/Er): find a counter s so that the custom
        # 512-word ChaCha-style hash of "<pow_nonce>:<s>" starts with pow_difficulty zero bits. Pure Python
        # is ~100x slower than the browser, so the solver is written flat: the ChaCha quarter round (ye) is
        # inlined on local variables (no function calls or list writes per round), the constant
        # "<pow_nonce>:" prefix is absorbed only once, and gr() stops at the first non-zero output word.
        def powBytes(s):
            # like the player's yr(): one byte per char code (& 255); a list behaves the same on py2 and py3
            return [ord(ch) & 255 for ch in s]

        def grAbsorb(data, state=(1779033703, 3144134277, 1013904242, 2773480762)):
            M = 0xFFFFFFFF
            a, b, c, d = state
            for i in data:
                a = (a + i) & M
                a = ((a << 7) | (a >> 25)) & M
                a = (a + b) & M
                d ^= a
                d = ((d << 16) | (d >> 16)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 12) | (b >> 20)) & M
                a = (a + b) & M
                d ^= a
                d = ((d << 8) | (d >> 24)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 7) | (b >> 25)) & M
            return a, b, c, d

        def gr(state, tail):
            # number of leading zero bits of the player's gr() hash of (absorbed prefix + tail), same as
            # wr(gr()) in the player JS; the eight output words are only computed until one is non-zero
            M = 0xFFFFFFFF
            a, b, c, d = grAbsorb(tail, state)
            for _i in range(8):
                a = (a + b) & M
                d ^= a
                d = ((d << 16) | (d >> 16)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 12) | (b >> 20)) & M
                a = (a + b) & M
                d ^= a
                d = ((d << 8) | (d >> 24)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 7) | (b >> 25)) & M
            r = [0] * 512
            for i in range(512):
                a = (a + b) & M
                d ^= a
                d = ((d << 16) | (d >> 16)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 12) | (b >> 20)) & M
                a = (a + b) & M
                d ^= a
                d = ((d << 8) | (d >> 24)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 7) | (b >> 25)) & M
                r[i] = a ^ c
            for _i in range(2):
                for s in range(512):
                    x = r[s]
                    x = (x + r[x & 511]) & M
                    x = ((x << 13) | (x >> 19)) & M
                    x ^= (r[(s + 1) & 511] * 2654435761) & M
                    r[s] = x
                    a ^= x
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 16) | (d >> 16)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 12) | (b >> 20)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 8) | (d >> 24)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 7) | (b >> 25)) & M
            zeros = 0
            for i in range(0, 512, 64):
                a = (a + b) & M
                d ^= a
                d = ((d << 16) | (d >> 16)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 12) | (b >> 20)) & M
                a = (a + b) & M
                d ^= a
                d = ((d << 8) | (d >> 24)) & M
                c = (c + d) & M
                b ^= c
                b = ((b << 7) | (b >> 25)) & M
                s = a
                for x in r[i:i + 64]:
                    s = (s + x) & M
                    s = ((s << 5) | (s >> 27)) & M
                    s ^= (x * 2246822519) & M
                s ^= c
                if s:
                    return zeros + 32 - s.bit_length()
                zeros += 32
            return zeros

        def er(t, e, timeout):
            # returns (solution or None, hashes tried); the time limit is checked every 16 hashes
            # (a few seconds at most even on a slow ARM box)
            if e <= 0:
                return "0", 0
            state = grAbsorb(powBytes(t + ":"))
            start = time.time()
            s = 0
            while True:
                for _i in range(16):
                    if gr(state, powBytes(str(s))) >= e:
                        return str(s), s + 1
                    s += 1
                if time.time() - start > timeout:
                    return None, s

        def statusCode(data, sts):
            try:
                code = getattr(data, "meta", {}).get("status_code")
                if code:
                    return code
            except Exception:
                pass
            return 200 if sts else 0

        def tryJson(data):
            try:
                return json_loads(data)
            except Exception:
                return None

        def jsonPost():
            # params for the API POST endpoints (challenge/attest/captcha/
            # verify/playback). Send a real JSON Content-Type (pycurl otherwise
            # defaults to application/x-www-form-urlencoded) and disable the
            # automatic "Expect: 100-continue" handshake, matching the site's
            # own frontend and upstream ResolveURL (jdata=True).
            hdr = dict(HTTP_HEADER)
            hdr["Content-Type"] = "application/json"
            hdr["Expect"] = ""
            return {"header": hdr, "raw_post_data": True, "timeout": 40}

        # embedding site of a domain-locked video (e.g. serijebalkan.com): its Referer comes in the link meta
        parent = getattr(baseUrl, "meta", {}).get("Referer", "")
        baseUrl = baseUrl.replace("/d/", "/e/")
        printDBG("parserBYSE baseUrl[%s]" % baseUrl)
        urltab = []
        for redirectDomain in ["boosteradx.online", "byse.sx", "streamlyplayer.online"]:
            baseUrl = baseUrl.replace(redirectDomain, "streamlyplayero.online")
        ref = urlparser.getDomain(baseUrl, False)
        midMatch = re.search(r"/(?:e|d|download)/([0-9a-zA-Z]+)", baseUrl)
        if not midMatch:
            return []
        mid = midMatch.group(1)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["User-Agent"] = UA
        HTTP_HEADER["Referer"] = ref
        HTTP_HEADER["Origin"] = ref[:-1]

        embed = ""
        detailsUrl = "%sapi/videos/%s/details" % (ref, mid)
        # with_metadata=True is required for statusCode() below to see the
        # real HTTP status: getPageWithPyCurl() treats a 404 as sts=True by
        # default (ignore_http_code_ranges), and only attaches .meta when
        # asked to - without it, statusCode() always fell through to its
        # sts-based 200/0 guess and this 404 retry never actually fired,
        # even though the site returns a valid JSON body on 404s.
        sts, data = self.cm.getPage(detailsUrl, {"header": dict(HTTP_HEADER), "with_metadata": True})
        details = tryJson(data) if sts else None
        if details is None or statusCode(data, sts) == 404:
            embed = "embed/"
            detailsUrl = "%sapi/videos/%s/%sdetails" % (ref, mid, embed)
            hdr = dict(HTTP_HEADER)
            if parent:  # add 041026: domain-locked videos check Referer/Origin of the embedding site
                hdr["Referer"] = urlparser.getDomain(parent, False)
                hdr["Origin"] = hdr["Referer"][:-1]
            # 404 {"error": "video record missing: video not found"}, 403 {"error": "embedding from this domain is not allowed ..."}
            sts, data = self.cm.getPage(detailsUrl, {"header": hdr, "ignore_http_code_ranges": [(403, 404)]})
            if not sts:
                return []
            details = tryJson(data)
            if not isinstance(details, dict):
                return []
            if details.get("error") and not details.get("embed_frame_url"):
                printDBG("parserBYSE details error [%s]" % details["error"])
                SetIPTVPlayerLastHostError(_("The video has been removed.") if "not found" in details["error"] else _("Content not available"))
                return []

        embedUrl = details.get("embed_frame_url")
        if embedUrl:
            ref = urlparser.getDomain(embedUrl, False)
            HTTP_HEADER["X-Embed-Parent"] = baseUrl
            HTTP_HEADER["Referer"] = ref
            HTTP_HEADER["Origin"] = ref[:-1]
            if parent:  # the player sends the embedding site as embedParentHost / Referrer
                HTTP_HEADER["X-Embed-Origin"] = urlparser.getDomain(parent).replace("www.", "", 1)
                HTTP_HEADER["X-Embed-Referer"] = urlparser.getDomain(parent, False)

        settingsUrl = "%sapi/videos/%s/%ssettings" % (ref, mid, embed)
        sts, data = self.cm.getPage(settingsUrl, {"header": dict(HTTP_HEADER)})
        settings = tryJson(data) if sts else None
        if settings is None:
            settings = {}

        playbackUrl = "%sapi/videos/%s/%splayback" % (ref, mid, embed)
        if settings.get("captcha_required"):
            # a solved captcha stays valid for the player domain for a while (verify expires_in, 1800 s):
            # reuse it for the next video instead of solving the proof of work again (minutes on a slow box)
            sts = False
            access = self.BYSE_ACCESS.get(ref)
            if access and access[0] > time.time():
                HTTP_HEADER["X-Captcha-Token"] = access[2]
                sts, data = self.cm.getPage(playbackUrl, jsonPost(), json_dumps({"fingerprint": access[1]}))
                printDBG("parserBYSE reused captcha token: %s" % sts)
                if not sts or tryJson(data) is None:
                    sts = False
                    self.BYSE_ACCESS.pop(ref, None)
            if not sts:
                challengeUrl = "%sapi/videos/access/challenge" % ref
                sts, data = self.cm.getPage(challengeUrl, jsonPost(), "")
                challenge = tryJson(data) if sts else None
                if challenge is None:
                    return []

                attestUrl = "%sapi/videos/access/attest" % ref
                sts, data = self.cm.getPage(attestUrl, jsonPost(), json_dumps(wn(challenge)))
                attest = tryJson(data) if sts else None
                if attest is None:
                    return []
                fingerprint = {"token": attest.get("token"), "viewer_id": attest.get("viewer_id"), "device_id": attest.get("device_id"), "confidence": attest.get("confidence")}

                captchaUrl = "%sapi/videos/%s/%scaptcha" % (ref, mid, embed)
                sts, data = self.cm.getPage(captchaUrl, jsonPost(), json_dumps({"fingerprint": fingerprint}))
                captcha = tryJson(data) if sts else None
                if captcha is None:
                    return []
                # mobile fingerprints get difficulty 12 (~4096 hashes, ~1 min on an ARM box), desktop ones 16;
                # the pow_token is valid for expires_in (1800 s), so the box may take longer than the
                # browser's 20 s
                difficulty = int(captcha.get("pow_difficulty") or 0)
                timeLimit = min(180.0, max(20.0, float(captcha.get("expires_in") or 300) - 60.0))
                powStart = time.time()
                solution, hashes = er(captcha.get("pow_nonce") or "", difficulty, timeLimit)
                printDBG("parserBYSE proof of work difficulty %d: %s after %d hashes in %.1fs" % (difficulty, solution, hashes, time.time() - powStart))
                if solution is None:
                    SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                    return []

                verifyUrl = "%sapi/videos/%s/%scaptcha/verify" % (ref, mid, embed)
                verifyPost = {"pow_token": captcha.get("pow_token"), "solution": solution, "fingerprint": fingerprint}
                sts, data = self.cm.getPage(verifyUrl, jsonPost(), json_dumps(verifyPost))
                verify = tryJson(data) if sts else None
                if not verify or not verify.get("token"):
                    printDBG("parserBYSE captcha verify failed [%s]" % data)
                    SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                    return []
                HTTP_HEADER["X-Captcha-Token"] = verify["token"]
                lifetime = min(float(verify.get("expires_in") or 0), 1800.0) - 60.0
                if lifetime > 0:
                    self.BYSE_ACCESS[ref] = (time.time() + lifetime, fingerprint, verify["token"])

                sts, data = self.cm.getPage(playbackUrl, jsonPost(), json_dumps({"fingerprint": fingerprint}))
        else:
            sts, data = self.cm.getPage(playbackUrl, jsonPost(), json_dumps(fp(16, 0.83, 0.94)))
        if not sts:
            return []

        html = tryJson(data)
        if html is None:
            return []
        sources = html.get("sources")
        if not sources:
            pd = html.get("playback")
            if pd:
                iv = ft(pd.get("iv"))
                key = xn(pd.get("key_parts"), pd.get("version"))
                pl = ft(pd.get("payload"))
                cipher = python_aesgcm.new(key)
                ct = cipher.open(iv, pl)
                html = json_loads(ct.decode("latin-1"))
                sources = html.get("sources")
        if sources:
            for x in sources:
                url = urlparser.decorateUrl(x.get("url"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": ref, "Origin": ref[:-1]})
                if ".m3u8" in url:
                    urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
                else:
                    urltab.append({"name": x.get("label", ""), "url": url})
        return urltab

    def parserDRAKKAR(self, baseUrl):  # add 250826
        def xd(enc, key):
            r = []
            for i in range(len(enc)):
                if isinstance(enc[i], int):
                    r.append(chr(enc[i] ^ key[i % len(key)]))
                else:
                    r.append(format(int(enc[i], 16) ^ int(key[i % len(key)], 16), "x"))
            return "".join(r)

        def wc(seed, ch):
            return sha256((seed + ch).encode("utf-8")).hexdigest()[:16]

        def stdB64Decode(s):
            s = s + "=" * (-len(s) % 4)
            return base64.b64decode(s)

        def aesCbcDecrypt(cipherBytes, ivHex, key):
            try:
                decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, unhexlify(ivHex)))
                decrypted = decrypter.feed(cipherBytes)
                decrypted += decrypter.feed()
                return decrypted.decode()
            except Exception:
                return None

        printDBG("parserDRAKKAR baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, html = self.cm.getPage(baseUrl, {"header": dict(HTTP_HEADER)})
        if not sts:
            return []
        m = re.search(r"\(function\(\){\s*(var.+?)\s*var\s*_cr.+?_ept\s*=\s*'([^']+).+?_ws\s*=\s*'([^']+)", html, re.DOTALL)
        if not m:
            return []
        varsBlock, ept, ws = m.group(1), m.group(2), m.group(3)
        if "fromCharCode" in varsBlock:
            s = re.findall(r"=\s*(\[[^;]+)", varsBlock)
            if not s:
                return []
            if len(s) == 2:
                cr = xd(literal_eval(s[0]), literal_eval(s[1]))
            else:
                t = int(varsBlock[:-2].split("]")[-1])
                cr = "".join([chr(i + t) for i in literal_eval(s[0])])
        else:
            s = re.findall(r"=((?:atob\()?'[^']+)", varsBlock)
            if len(s) < 2:
                return []
            if "atob(" in s[0]:
                cr = stdB64Decode(s[0].split("'")[-1]).decode("latin-1") + stdB64Decode(s[1].split("'")[-1]).decode("latin-1")
            else:
                cr = s[0].split("'")[-1][::-1] + s[1].split("'")[-1][::-1]

        ts = int(time.time() * 1000)
        time.sleep(1.5)
        ref = urlparser.getDomain(baseUrl, False)
        postData = {
            "cr": cr,
            "pt": xd(ept, cr),
            "wc": wc(ws, cr),
            "_ts2": int(time.time() * 1000) - randint(100, 500),
            "bs": {"ts": ts, "sw": 1280, "sh": 720, "plt": "", "tz": 240, "lang": "en-US", "pl": "", "ct": 4, "dm": 24, "td": 0, "cv": 1, "wg": 1},
        }
        HTTP_HEADER["Referer"] = ref
        HTTP_HEADER["Origin"] = ref[:-1]
        streamUrl = baseUrl.split("?")[0].rstrip("/") + "/stream"
        sts, data = self.cm.getPage(streamUrl, {"header": HTTP_HEADER, "raw_post_data": True}, json_dumps(postData))
        if not sts:
            return []
        try:
            res = json_loads(data)
        except Exception:
            return []
        if not (res.get("s") and res.get("d") and res.get("x")):
            return []
        key = sha256((str(res.get("p1", "")) + str(res.get("p2", "")) + str(res.get("p3", "")) + str(res.get("p4", "")) + cr + str(res.get("x", ""))).encode()).digest()
        payload = aesCbcDecrypt(stdB64Decode(res.get("d", "")), res.get("v", ""), key)
        if not payload:
            return []
        try:
            pdata = json_loads(payload)
        except Exception:
            return []
        playerHtml = ""
        epd = pdata.get("encrypted_player_data")
        if epd and epd.get("ct"):
            simpleKey = unhexlify(str(epd.get("k1", "")) + str(epd.get("k2", "")) + str(epd.get("k3", "")) + str(epd.get("k4", "")))
            if len(simpleKey) in [16, 24, 32]:
                playerHtml = aesCbcDecrypt(stdB64Decode(epd.get("ct", "")), epd.get("iv", ""), simpleKey) or ""
        elif pdata.get("processed_template"):
            playerHtml = pdata.get("processed_template")
        if not playerHtml:
            return []
        videoSrc = re.search(r"videoSrc:\s*'([^']+)", playerHtml)
        if not videoSrc:
            return []
        urlMeta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": ref, "Origin": ref[:-1]}
        subTracks = []
        subBlock = re.search(r"subtitles:\s*(\[.+?\])\s*,", playerHtml, re.DOTALL)
        if subBlock:
            try:
                for sub in json_loads(subBlock.group(1)):
                    src = sub.get("src") or sub.get("file") or sub.get("url")
                    if src:
                        subTracks.append({"title": "", "url": src, "lang": sub.get("lang") or sub.get("label") or ""})
            except Exception:
                pass
        if subTracks:
            urlMeta["external_sub_tracks"] = subTracks
        url = urlparser.decorateUrl(videoSrc.group(1), urlMeta)
        urltab.append({"name": "Drakkar", "url": url})
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

    def parserMIXDROP(self, baseUrl):  # add 041026 - like ResolveURL mixdrop.py
        printDBG("parserMIXDROP baseUrl[%s]" % baseUrl)
        mediaId = re.search(r"/[fe]/(\w+)", baseUrl)
        if not mediaId:
            return []
        # ids are the same on every mixdrop domain; old ones are parked (.co, .vc, ...), mixdrop.ag redirects to the live one
        url = "https://mixdrop.ag/e/%s" % mediaId.group(1)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER.update({"Referer": "https://mixdrop.ag/", "Origin": "https://mixdrop.ag"})
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return []
        url = self.cm.meta.get("url", "") or url
        redirect = re.search(r"""location\s*=\s*["'](/[^'"]+)""", data)
        if redirect:
            url = urljoin(url, redirect.group(1))
            sts, data = self.cm.getPage(url, urlParams)
            if not sts:
                return []
        if "(p,a,c,k,e,d)" in data:
            data = get_packed_data(data) or data
        src = re.search(r'(?:vsr|wurl|surl)[^=]*=\s*"([^"]+)', data)
        if not src:
            if re.search(r"can(?:'|&#0?39;)t find the (?:video|file)", data):
                # download-only uploads (e.g. .ts recordings) and deleted files have no embed
                SetIPTVPlayerLastHostError(_("MixDrop: this file is not available as a video stream (deleted or download only)."))
            return []
        src = src.group(1)
        if src.startswith("//"):
            src = "https:" + src
        return [{"name": "MP4", "url": urlparser.decorateUrl(src, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": url})}]

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
        hostOnly = re.sub(r"^www\.", "", urlparse(baseUrl).netloc.lower())
        mirrorData = None
        if hostOnly in STREAMWISH_DOMAINS:
            # add 061026 (after ResolveURL streamwish.py): the file plays as /e/<id> on the current mirrors;
            # the first one with a player wins, the original link stays the last resort.
            # hglamioz answers 404 to /e/<id>/<file name> (hgcloud.to/e/upbzgcmz0a1o/Ali-kara.S01E03.mp4), so only the id is kept
            # the mirrors are equivalent and a removed file answers 200 without a player on all of them,
            # so only 3 are tried (2 of the own group, 1 of the other) to keep a dead link from taking 8 requests
            fileId = ph.search(baseUrl, r"//[^/]+/(?:e/|f/|d/|v/)?([0-9a-zA-Z]+)(?:[/?#.]|$)")[0]
            if hostOnly in STREAMWISH_HG_DOMAINS:
                mirrors = STREAMWISH_MIRRORS_HG[:2] + STREAMWISH_MIRRORS[:1]
            else:
                mirrors = STREAMWISH_MIRRORS[:2] + STREAMWISH_MIRRORS_HG[:1]
            for mirror in mirrors if fileId else ():
                mirrorUrl = "https://%s/e/%s" % (mirror, fileId)
                stsM, dataM = self.cm.getPage(mirrorUrl, urlParams)
                if stsM and "p,a,c,k,e" in dataM:
                    printDBG("parserJWPLAYER StreamWish %s -> %s" % (hostOnly, mirror))
                    baseUrl = strwithmeta(mirrorUrl, baseUrl.meta)
                    mirrorData = dataM
                    break
        elif hostOnly in FILELIONS_DEAD_DOMAINS:
            # add 061026 (after ResolveURL filelions.py): dead FileLions / VidHide domains, same path on the live host
            baseUrl = strwithmeta(baseUrl.replace(urlparse(baseUrl).netloc, FILELIONS_LIVE_HOST, 1), baseUrl.meta)
        if "savefiles.com/" in baseUrl or "streamhls.to/" in baseUrl:
            # add 041026: streamhls.to is savefiles too - its /e/ page is only a click-to-play form;
            # download links /d/<id>_n play as /<id> (only the quality suffix right after the id goes)
            baseUrl = baseUrl.replace("/v/", "/").replace("/e/", "/")
            baseUrl = re.sub(r"/d/([0-9a-zA-Z]+)(?:_n)?", r"/\1", baseUrl, count=1)
        if "savefiles.com/" in baseUrl or "streamhls.to/" in baseUrl or "abstream.to/" in baseUrl:
            # add 041026: these pages bind the stream token to the client IP and their CDNs (s*.savefiles.com,
            # *.streambucket.xyz) are IPv4 only - a page fetched over IPv6 gives a playlist that answers 403
            urlParams["ipv4_only"] = True
        if "1vid.xyz/" in baseUrl:
            # add 041026: same IP binding (i=<IPv6 /64> instead of i=<IPv4 /16>), *.1vid.online is IPv4 only -> 404
            urlParams["ipv4_only"] = True
        if "rubyvidhub.com" in baseUrl or "rubystm.com" in baseUrl or "streamruby" in baseUrl:
            HTTP_HEADER.pop("Referer", None)  # embed is refused ("restricted for this domain") whenever a Referer is sent
        if "dropload." in baseUrl:
            baseUrl = re.sub(r"dropload\.co/embed-([^./]+)\.html", r"dr0pstream.com/e/\1", baseUrl)
            baseUrl = baseUrl.replace("dropload.tv", "dr0pstream.com").replace("dropload.io", "dr0pstream.com")
        if "uqload." in baseUrl and "/e/" in baseUrl:
            # add 031026: uqload /e/<id> is only a click-to-play form (its POST answers with the site's demo clip)
            baseUrl = re.sub(r"(uqload\.[a-z]+)/e/([0-9a-zA-Z]+).*", r"\1/embed-\2.html", baseUrl)
        if mirrorData:
            sts, data = True, mirrorData  # StreamWish mirror page fetched above
        else:
            sts, data = self.cm.getPage(baseUrl, urlParams)
        if sts and "embed restricted for this domain" in data and HTTP_HEADER.pop("Referer", None):
            # 041026: domain-locked embed (luluvdo ...) - the embedding site is not on the allow list,
            # but a request without any Referer is accepted
            sts, data = self.cm.getPage(baseUrl, urlParams)
        if sts and ("embed restricted for this domain" in data or "Embeds disabled" in data):
            # XFileSharing embed-<code>.html locked for every Referer (vidtube): the file page carries the same player
            fileUrl = re.sub(r"/embed-([0-9a-zA-Z]+)[^/]*\.html.*", r"/\1.html", baseUrl)
            if fileUrl != baseUrl:
                sts, data = self.cm.getPage(fileUrl, urlParams)
        if sts and "/d/" in baseUrl and "p,a,c,k,e" not in data:
            # fix 041026: VidHide /d/<id> (vidhideplus -> callistanise) is a download page without the player,
            # /v/<id> carries it (/e/<id> answers 522)
            stsV, dataV = self.cm.getPage(baseUrl.replace("/d/", "/v/"), urlParams)
            if stsV and "p,a,c,k,e" in dataV:
                data = dataV
        if not sts:
            return []
        if "File is no longer available" in data:
            SetIPTVPlayerLastHostError(_("The video has been removed."))
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
            # fix 041026: StreamHG HLS and the same CDN family (*.acek-cdn.com, *.premilkyway.com, *.cdn-centaurus.com:
            # "/hls2/...&i=0.4&sp=500", also behind fastvid.cam, hlswish.com and vidhideplus.com): exteplayer3 fails on
            # it on the box ("Invalid data found when processing input" or no picture) while gstplayer and hlsdl play
            # it; the playlist and the TS segments are clean, ffmpeg 8.1 (schannel) on a PC plays it too
            if ".m3u8" in url and ("hglamioz.com" in host or ("/hls2/" in url and re.search(r"[?&]sp=500(?:&|$)", url))):
                url.meta["iptv_buffering"] = "required"
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
            if isinstance(js, str):
                js = json_loads(js) if js else {}
            if not isinstance(js, dict):
                js = {}
            url = js.get("hlsManifestUrl") or js.get("ondemandHls") or js.get("hlsMasterPlaylistUrl")
            if url:
                url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        elif "vp_video_stub_txt" in data:
            # player stub instead of the player: blocked (copyright), deleted or private video
            SetIPTVPlayerLastHostError(_("Content not available"))
        return urltab

    def parserVIDSRC(self, baseUrl):  # update 031026 - vsembed/vidsrc -> cloudorchestranova -> data.vidsrc.sh (ChaCha20 wasm)
        printDBG("parserVIDSRC baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer", "") if isinstance(baseUrl, strwithmeta) else ""
        baseUrl = str(baseUrl)
        if baseUrl.startswith("//"):
            baseUrl = "https:" + baseUrl

        def leb(b, p, signed=False):
            r = s = 0
            while True:
                x = b[p]
                p += 1
                r |= (x & 0x7F) << s
                s += 7
                if not x & 0x80:
                    break
            if signed and (x & 0x40):
                r -= 1 << s
            return r, p

        def wasmDecrypt(wasm, encB64):
            # vsdec wasm = ChaCha20(key = mem32[a_i] ^ mem32[b_i], nonce = enc[:12], counter from 0)
            wasm = bytearray(wasm)
            if wasm[:4] != bytearray(b"\x00asm"):
                return ""
            secs = {}
            p = 8
            while p < len(wasm):
                sid = wasm[p]
                sz, p = leb(wasm, p + 1)
                secs.setdefault(sid, []).append(wasm[p:p + sz])
                p += sz
            if 10 not in secs or 11 not in secs:
                return ""
            mem = bytearray(65536)
            data = secs[11][0]
            n, p = leb(data, 0)
            for _seg in range(n):
                flag, p = leb(data, p)
                if flag != 0 or data[p] != 0x41:
                    return ""
                off, p = leb(data, p + 1, True)
                sz, p = leb(data, p + 1)
                mem[off:off + sz] = data[p:p + sz]
                p += sz
            code = secs[10][0]
            n, p = leb(code, 0)
            body = bytearray()
            for _fn in range(n):
                sz, p = leb(code, p)
                if sz > len(body):
                    body = code[p:p + sz]  # the ChaCha block function is by far the largest body
                p += sz
            body = bytes(body)
            # i32.const A ; i32.load ; i32.const B ; i32.load ; i32.xor
            pairs = re.findall(b"\\x41([\\x00-\\x7f]|[\\x80-\\xff]+[\\x00-\\x7f])\\x28\\x02\\x00\\x41([\\x00-\\x7f]|[\\x80-\\xff]+[\\x00-\\x7f])\\x28\\x02\\x00\\x73", body)
            if len(pairs) < 8:
                return ""
            key = []
            for a, b in pairs[:8]:
                a = leb(bytearray(a), 0, True)[0]
                b = leb(bytearray(b), 0, True)[0]
                key.append(struct.unpack("<I", bytes(mem[a:a + 4]))[0] ^ struct.unpack("<I", bytes(mem[b:b + 4]))[0])
            rounds = body.count(b"\x77") // 16  # 4 quarter rounds x 4 i32.rotl per round
            if rounds not in (8, 12, 20):
                rounds = 20
            enc = bytearray(base64.b64decode(encB64))
            if len(enc) < 13:
                return ""
            nonce = list(struct.unpack("<3I", bytes(enc[:12])))
            enc = enc[12:]
            M = 0xFFFFFFFF

            def qr(x, a, b, c, d):
                x[a] = (x[a] + x[b]) & M
                v = x[d] ^ x[a]
                x[d] = ((v << 16) & M) | (v >> 16)
                x[c] = (x[c] + x[d]) & M
                v = x[b] ^ x[c]
                x[b] = ((v << 12) & M) | (v >> 20)
                x[a] = (x[a] + x[b]) & M
                v = x[d] ^ x[a]
                x[d] = ((v << 8) & M) | (v >> 24)
                x[c] = (x[c] + x[d]) & M
                v = x[b] ^ x[c]
                x[b] = ((v << 7) & M) | (v >> 25)

            out = bytearray()
            for ctr, i in enumerate(range(0, len(enc), 64)):
                st = [0x61707865, 0x3320646E, 0x79622D32, 0x6B206574] + key + [ctr] + nonce
                x = list(st)
                for _round in range(rounds // 2):
                    qr(x, 0, 4, 8, 12)
                    qr(x, 1, 5, 9, 13)
                    qr(x, 2, 6, 10, 14)
                    qr(x, 3, 7, 11, 15)
                    qr(x, 0, 5, 10, 15)
                    qr(x, 1, 6, 11, 12)
                    qr(x, 2, 7, 8, 13)
                    qr(x, 3, 4, 9, 14)
                ks = bytearray(struct.pack("<16I", *[(x[k] + st[k]) & M for k in range(16)]))
                blk = enc[i:i + 64]
                out.extend(bytearray([blk[k] ^ ks[k] for k in range(len(blk))]))
            return out.decode("utf-8", "ignore")

        def getJson(url, hdr):
            sts, data = self.cm.getPage(url, {"header": hdr})
            if not sts:
                return {}
            try:
                data = json_loads(data)
            except Exception:
                return {}
            return data if isinstance(data, dict) else {}

        # 1-4: embed page -> vs_src.php -> cloudorchestranova embed -> player page -> CONFIG.api
        api = ""
        url = baseUrl
        ref = referer
        for _hop in range(6):
            hdr = dict(HTTP_HEADER)
            if ref:
                hdr["Referer"] = ref
            sts, data = self.cm.getPage(url, {"header": hdr})
            if not sts:
                break
            url = self.cm.meta.get("url", url)
            m = re.search(r"window\.CONFIG\s*=\s*(\{.+?\});", data)
            if m:
                try:
                    cfg = json_loads(m.group(1))
                except Exception:
                    cfg = {}
                api = cfg.get("api", "")
                if not api and cfg.get("streamBase"):
                    api = "%s&season=%s&episode=%s&stream_urls" % (cfg["streamBase"], cfg.get("season") or 1, cfg.get("episode") or 1)
                break
            nextUrl = ""
            m = re.search(r"window\.CFG\s*=\s*(\{.+?\});", data)
            if m:
                try:
                    nextUrl = json_loads(m.group(1)).get("playerUrl", "")
                except Exception:
                    nextUrl = ""
            if not nextUrl:
                m = re.search(r"""data-api=['"]([^'"]+)""", data)
                if m:
                    jhdr = dict(HTTP_HEADER)
                    jhdr.update({"Referer": url, "Accept": "application/json"})
                    nextUrl = getJson(urljoin(url, m.group(1).replace("&amp;", "&")), jhdr).get("src", "")
            if not nextUrl:
                m = re.search(r"""<iframe[^>]+?src=['"]([^'"]+/embed/[^'"]+)""", data)
                if m:
                    nextUrl = m.group(1)
            if not nextUrl:
                break
            ref = url
            url = urljoin(url, nextUrl.replace("&amp;", "&"))
            printDBG("parserVIDSRC next[%s]" % url)

        if not api:
            # fallback: build the API URL from the id in the embed URL
            m = re.search(r"/(?:embed/)?(?:player/)?(movie|tv)?/?(tt\d+|\d+)(?:[/-](\d+)[/-](\d+))?", baseUrl.split("?")[0])
            q = re.search(r"[?&](imdb|tmdb)=([^&]+)", baseUrl)
            if q:
                mid = q.group(2)
                kind = "tv" if "/tv" in baseUrl else "movie"
                season = re.search(r"[?&]season=(\d+)", baseUrl)
                episode = re.search(r"[?&]episode=(\d+)", baseUrl)
                season = season.group(1) if season else ""
                episode = episode.group(1) if episode else ""
            elif m:
                mid = m.group(2)
                season, episode = m.group(3) or "", m.group(4) or ""
                kind = m.group(1) or ("tv" if season else "movie")
            else:
                return []
            api = "https://data.vidsrc.sh/api.php?type=%s&%s=%s" % (kind, "imdb" if mid.startswith("tt") else "tmdb", mid)
            if kind == "tv":
                api += "&season=%s&episode=%s" % (season or 1, episode or 1)
            api += "&stream_urls"
        printDBG("parserVIDSRC api[%s]" % api)

        # 5: stream data (+ decryption of the stream_urls envelope)
        jhdr = dict(HTTP_HEADER)
        jhdr.update({"Referer": "https://cloudorchestranova.com/", "Origin": "https://cloudorchestranova.com", "Accept": "application/json"})
        js = getJson(api, jhdr)
        jdata = js.get("data") or {}
        if not isinstance(jdata, dict):
            return []
        streams = jdata.get("stream_urls") or []
        if not isinstance(streams, list):
            vs = js.get("vs") or {}
            text = ""
            try:
                if vs.get("wasm_url"):
                    # binary body -> raw response object (getPage would utf-8 decode it)
                    whdr = {"User-Agent": HTTP_HEADER["User-Agent"], "Accept": "*/*", "Referer": "https://cloudorchestranova.com/", "Origin": "https://cloudorchestranova.com"}
                    sts, resp = self.cm.getPage(vs["wasm_url"], {"header": whdr, "return_data": False})
                    wasm = b""
                    if sts and resp is not None:
                        try:
                            wasm = resp.read()
                        finally:
                            resp.close()
                    if wasm[:2] == b"\x1f\x8b":
                        wasm = zlib.decompress(wasm, 16 + zlib.MAX_WBITS)
                elif vs.get("wasm"):
                    wasm = base64.b64decode(vs["wasm"])
                else:
                    wasm = b""
                if wasm:
                    text = wasmDecrypt(wasm, streams)
            except Exception:
                printExc()
            streams = [x.strip() for x in text.split("\n") if x.strip().startswith("http")]
        printDBG("parserVIDSRC streams %s" % streams)
        if not streams:
            return []

        subTracks = []
        for sub in (js.get("default_subs") or jdata.get("default_subs") or []):
            if isinstance(sub, dict) and sub.get("url"):
                lang = sub.get("code") or sub.get("lang") or sub.get("label") or "und"
                subTracks.append({"title": sub.get("label") or sub.get("lang") or lang, "url": sub["url"], "lang": lang[:3].lower(), "format": "vtt" if ".vtt" in sub["url"] else "srt"})

        # 6: playback token. <cdn>/generate.php -> JWT bound to the client IP (/64), valid 4 h, accepted by every CDN host
        #    of this network; generate.php is rate limited per host (429) -> cache it and try the other hosts.
        def tokenClaims(tk):
            # JWT payload: {"exp": ..., "ip_cidr": "<client IPv4>/24" or "<client IPv6>/64"}
            try:
                pl = tk.split(".")[1]
                claims = json_loads(base64.urlsafe_b64decode(pl + "=" * (-len(pl) % 4)))
                return claims if isinstance(claims, dict) else {}
            except Exception:
                return {}

        def tokenExp(tk):
            try:
                return int(tokenClaims(tk).get("exp", 0))
            except Exception:
                return 0

        origins = []
        for surl in streams:
            origin = re.match(r"(https?://[^/]+)", surl)
            if origin and origin.group(1) not in origins:
                origins.append(origin.group(1))

        # token + playlist check over IPv6 first: the players (exteplayer3 / ffmpeg) prefer IPv6 when the box has
        # it and the CDN checks the token's ip_cidr against the requesting address. Without IPv6 (or when it fails)
        # the request is repeated normally; no answer at all over IPv6 (no route / no AAAA) -> skip it from then on.
        # ipv6_only only acts on the pycurl / curl-impersonate paths, urllib ignores it (= the normal request).
        useIPv6 = [True]

        def getPage6(url, params, request):
            if useIPv6[0]:
                p = dict(params)
                p["ipv6_only"] = True
                sts, data = request(url, p)
                if sts:
                    return sts, data
                if request == self.cm.getPage and not self.cm.meta.get("status_code"):
                    useIPv6[0] = False  # getDirectM3U8Playlist uses its own cm - only judged on our requests
                printDBG("parserVIDSRC IPv6 request failed[%s] -> normal request" % url)
            return request(url, params)

        def getM3U8(url, params):
            links = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=99999999, cookieParams=params)
            return bool(links), links

        def getToken():
            for attempt in range(3):  # ~1 request / 20 s / host is allowed
                if attempt:
                    GetIPTVSleep().Sleep(6 * attempt)
                for origin in origins:
                    sts, data = getPage6(origin + "/generate.php", {"header": HTTP_HEADER}, self.cm.getPage)
                    data = data.strip() if sts else ""
                    if data[:1] in ("{", "["):
                        try:
                            tj = json_loads(data)
                            data = tj if not isinstance(tj, dict) else (tj.get("token") or tj.get("data") or tj.get("string") or tj.get("result") or "")
                        except Exception:
                            data = ""
                    if data and re.match(r"^[\w\-]+\.[\w\-]+\.[\w\-]+$", data):
                        self.__class__._vidsrcToken = (data, tokenExp(data) or time.time() + 3600)
                        return data
            return ""

        cached = getattr(self.__class__, "_vidsrcToken", None)
        tk = cached[0] if cached and cached[1] > time.time() + 600 else ""
        fromCache = bool(tk)
        urltab = []
        freshTokens = 0
        for _attempt in range(3):
            if not tk:
                tk = getToken()
                freshTokens += 1
            printDBG("parserVIDSRC token[%s] cached[%s] ip_cidr[%s]" % (tk[:16], fromCache, tokenClaims(tk).get("ip_cidr", "")))
            for surl in streams:
                if tk:
                    surl = surl.replace("__TOKEN__", tk) if "__TOKEN__" in surl else surl + ("&" if "?" in surl else "?") + "token=" + tk
                meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://cloudorchestranova.com/", "Origin": "https://cloudorchestranova.com"}
                if subTracks:
                    meta["external_sub_tracks"] = subTracks
                surl = urlparser.decorateUrl(surl, meta)
                if ".m3u8" in surl:
                    sts, links = getPage6(surl, {}, getM3U8)
                    if sts:
                        urltab.extend(links)
                        break  # the urls are mirrors of the same file; one working master is enough
                else:
                    urltab.append({"name": "vidsrc mp4", "url": surl})
            if urltab or not tk or freshTokens >= 2:
                break
            # token rejected ("ip ... not in range"): a cached one after an IP change, or one issued for the other IP
            # family - every request (token, playlists, segments) is checked against the client's IPv4 /24 or
            # IPv6 /64 and a dual-stack connection can pick either family -> fetch a fresh one (twice at most)
            self.__class__._vidsrcToken = None
            tk = ""
            fromCache = False
        return urltab

    def parserVIDSRCMOV(self, baseUrl):  # add 240826
        printDBG("parserVIDSRCMOV baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        inner = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', data)
        if not inner:
            return []
        innerUrl = inner.group(1)
        innerUrl = "https:" + innerUrl if innerUrl.startswith("//") else innerUrl
        return self.parserVIDSRC(innerUrl)

    def parserMEINECLOUD(self, baseUrl):  # add 270926
        # meinecloud.click / devideosrc.co ("DeVideoSRC") player page -> its hoster embeds (libs/meinecloud.py) -> each resolved
        printDBG("parserMEINECLOUD baseUrl[%s]" % baseUrl)
        from Plugins.Extensions.IPTVPlayer.libs.meinecloud import MeineCloud, MAIN_URL as MC_URL
        referer = strwithmeta(baseUrl).meta.get("Referer", MC_URL)
        mc = MeineCloud(self.cm, {"header": self.cm.getDefaultHeader(browser="chrome")}, referer)
        imdb = MeineCloud.imdbFromUrl(baseUrl)
        episode = re.search(r"/(?:serial|tv)/tt\d+/(\d+)/(\d+)", baseUrl)
        if episode:
            embeds = mc.episodeLinks(imdb, episode.group(1), episode.group(2))
        else:
            embeds = mc.movieLinks(imdb)
        up = urlparser()
        urltab = []
        for embed in embeds:
            if up.checkHostSupport(embed) != 1:
                continue
            hoster = up.getHostName(embed, True)
            for item in up.getVideoLinkExt(strwithmeta(embed, {"Referer": MC_URL})):
                item["name"] = "%s %s" % (hoster, item.get("name", ""))
                urltab.append(item)
        return urltab

    def parserMEGAMAX(self, baseUrl):  # add 031026
        # Megamax mirror page (megamax.me / share4max.com / megatuktuk.store, Laravel + Inertia.js): the page JSON
        # gives the Inertia version, a partial Inertia request for the "streams" prop gives the hoster mirrors per
        # quality -> each mirror resolved through urlparser, the mirror name goes into the link name.
        # "Leech" player pages (/e/<id>, component files/leech/video) send the stream list CryptoJS-AES encrypted;
        # the passphrase is a constant of the player chunk (read again from the page's scripts when it changed)
        printDBG("parserMEGAMAX baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        referer = baseUrl.meta.get("Referer", "")
        # download pages: /download/<id> -> mirror page /iframe/<id>, "leech" download /d/<id> -> player /e/<id>
        url = str(baseUrl).replace("/download/", "/iframe/").replace("/d/", "/e/")
        if url.startswith("//"):
            url = "https:" + url
        origin = urlparser.getDomain(url, False)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        urlParams = {"header": dict(HTTP_HEADER), "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": GetCookieDir("megamax.cookie")}
        sts, data = False, ""
        if referer:
            # a Referer outside the video's allow_domain list is answered with 403, none at all always passes
            urlParams["header"]["Referer"] = referer
            sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            urlParams["header"] = dict(HTTP_HEADER)
            sts, data = self.cm.getPage(url, urlParams)
        if not sts or not data:
            return []
        page = data.replace("&quot;", '"').replace("\\/", "/")
        version = self.cm.ph.getSearchGroups(page, r'"version"\s*:\s*"([^"]+)"')[0]
        component = self.cm.ph.getSearchGroups(page, r'"component"\s*:\s*"([^"]+)"')[0] or "files/mirror/video"
        header = dict(HTTP_HEADER)
        header.update({"Referer": url, "Accept": "text/html, application/xhtml+xml", "X-Requested-With": "XMLHttpRequest", "X-Inertia": "true",
                       "X-Inertia-Partial-Component": component, "X-Inertia-Partial-Data": "streams"})
        if version:
            header["X-Inertia-Version"] = version
        sts, data = self.cm.getPage(url, dict(urlParams, header=header))
        if not sts or not data:
            return []
        try:
            streams = json_loads(data).get("props", {}).get("streams") or {}
        except Exception:
            printExc()
            return []
        if not isinstance(streams, dict):
            return []
        if streams.get("status", "success") != "success":
            if component == "files/leech/video" and "/e/" in url:
                # the leech backend often answers "something went wrong" - the mirror page of the same id
                # lists the hosters the file was uploaded to
                links = self.parserMEGAMAX(strwithmeta(url.replace("/e/", "/iframe/"), baseUrl.meta))
                if links:
                    return links
            SetIPTVPlayerLastHostError(streams.get("msg", "") or _("Content not available"))
            return []
        if component == "files/leech/video":
            return self._megamaxLeechLinks(page, streams.get("data"), origin, urlParams)
        up = urlparser()
        urltab = []
        tried = 0
        start = time.time()

        def mirrorCost(mirror):
            # morencius.com (VidHide) answers every request only after ~20 s: try it after the other hosters
            return 1 if "morencius." in str(mirror.get("link") or "") else 0

        for quality in streams.get("data") or []:
            label = str(quality.get("label") or quality.get("resolution") or "").replace(" (source)", "").strip()
            found = 0
            for mirror in sorted(quality.get("mirrors") or [], key=mirrorCost):
                if found >= 3 or tried >= 12:
                    break  # every mirror costs requests: three working hosters per quality are plenty
                if urltab and time.time() - start > 10:
                    break  # links resolve one after another - do not keep the user waiting for more mirrors
                link = str(mirror.get("link") or "").strip()
                if link.startswith("//"):
                    link = "https:" + link
                if not self.cm.isValidUrl(link) or up.checkHostSupport(link) != 1 or up.getParser(link) == up.pp.parserMEGAMAX:
                    continue
                tried += 1
                driver = str(mirror.get("driver") or "").strip() or up.getHostName(link, True)
                links = up.getVideoLinkExt(strwithmeta(link, {"Referer": origin}))
                if links:
                    found += 1
                for item in links:
                    item["name"] = ("%s %s %s" % (label, driver, item.get("name", ""))).strip()
                    urltab.append(item)
        return urltab

    def _megamaxLeechLinks(self, page, encrypted, origin, urlParams):  # add 031026
        # "data": JSON string {ct, iv, s} -> {"file": <HLS master / MP4>, "type", "label"} (or a list of them)
        try:
            encrypted = json_loads(encrypted) if isinstance(encrypted, basestring) else encrypted
        except Exception:
            encrypted = None
        if not isinstance(encrypted, dict):
            return []
        plain = cryptoJSAesDecrypt(encrypted, "k7v2m4x9bqwpnj6t")
        if plain is None:
            # passphrase changed: CryptoJS.AES.decrypt(e, `<passphrase>`, ...) in one of the page's module scripts
            for script in re.findall(r'<script[^>]+type="module"[^>]+src="([^"]+)"', page)[:4]:
                sts, js = self.cm.getPage(urljoin(origin, script), dict(urlParams, header=self.cm.getDefaultHeader(browser="chrome")))
                passphrase = self.cm.ph.getSearchGroups(js, r"""AES\.decrypt\(\w+,\s*[`'"]([^`'"]+)[`'"]""")[0] if sts else ""
                if passphrase:
                    plain = cryptoJSAesDecrypt(encrypted, passphrase)
                    break
        if plain is None:
            SetIPTVPlayerLastHostError(_("Encrypted stream list - not supported"))
            return []
        try:
            sources = json_loads(plain)
        except Exception:
            printExc()
            return []
        urltab = []
        meta = {"User-Agent": self.cm.getDefaultHeader(browser="chrome")["User-Agent"], "Referer": origin, "Origin": origin.rstrip("/")}
        for source in sources if isinstance(sources, list) else [sources]:
            fileUrl = str((source or {}).get("file") or "")
            if not self.cm.isValidUrl(fileUrl):
                continue
            if "mpegurl" in str(source.get("type", "")).lower() or ".m3u8" in fileUrl:
                urltab.extend(getDirectM3U8Playlist(strwithmeta(fileUrl, meta), checkExt=False, checkContent=True, sortWithMaxBitrate=99999999))
            else:
                urltab.append({"name": str(source.get("label") or "mp4"), "url": strwithmeta(fileUrl, meta)})
        return urltab

    def parserR2EMBED(self, baseUrl):  # add 031026
        # 71stream.one (/embed/<id>, /download/<id>: Inertia page prop "url") and ult4vid.one (/embed/<id>,
        # /en/<id>/watch: <video data-link>): one signed MP4 on Cloudflare R2
        printDBG("parserR2EMBED baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        url = str(baseUrl).replace("/download/", "/embed/")
        if url.startswith("//"):
            url = "https:" + url
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", urlparser.getDomain(url, False))
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts or not data:
            return []
        videoUrl = self.cm.ph.getSearchGroups(data, r'&quot;url&quot;:&quot;(https?:[^&]+?(?:&amp;[^&]+?)*)&quot;')[0]
        if not videoUrl:
            videoUrl = self.cm.ph.getSearchGroups(data, r'data-link="([^"]+)"')[0]
        videoUrl = videoUrl.replace("\\/", "/").replace("&amp;", "&")
        if not self.cm.isValidUrl(videoUrl):
            return []
        meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": urlparser.getDomain(url, False)}
        return [{"name": urlparser.getDomain(url), "url": strwithmeta(videoUrl, meta)}]

    def parserGOVID(self, baseUrl):  # add 031026
        # govid.live: /play/<token> is a gate page with the player in an iframe (govid.live/e/<id>/ or a foreign
        # hoster: voe, uqload, vinovo, vidara ...); /e/<id>/ keeps the HLS url hex-encoded in a JS constant
        printDBG("parserGOVID baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        # /d/<id>/ is the Turnstile-gated download page of the same video -> its player page /e/<id>/
        baseUrl = strwithmeta(re.sub(r"(govid\.[a-z]+)/d/(\d+)", r"\1/e/\2", baseUrl), baseUrl.meta)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        if baseUrl.meta.get("Referer"):
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts or not data:
            return []
        if "/play/" in baseUrl:
            frame = ""
            for src in re.findall(r"""<iframe[^>]+src=["']([^"']+)["']""", data):
                src = "https:" + src if src.startswith("//") else src
                if self.cm.isValidUrl(src) and ("/e/" in src or "embed" in src):
                    frame = src
                    break
            if not frame:
                return []
            if "govid." not in urlparser.getDomain(frame):
                return urlparser().getVideoLinkExt(strwithmeta(frame, {"Referer": urlparser.getDomain(baseUrl, False)}))
            HTTP_HEADER["Referer"] = str(baseUrl)
            baseUrl = strwithmeta(frame, baseUrl.meta)
            sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
            if not sts or not data:
                return []
        url = ""
        for hexUrl in re.findall(r"""["']((?:[0-9a-fA-F]{2}){20,})["']""", data):
            try:
                txt = ensure_str(unhexlify(hexUrl))
            except Exception:
                continue
            if txt.startswith("http"):
                url = txt
                break
        if not url:
            url = self.cm.ph.getSearchGroups(data, r"""["']((?:https?:)?//[^"']+?\.(?:m3u8|mp4)(?:\?[^"']*)?)["']""")[0]
            url = "https:" + url if url.startswith("//") else url
        if not self.cm.isValidUrl(url):
            return []
        host = urlparser.getDomain(baseUrl, False)
        # playlist and segments answer 404 without the player's Referer
        url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
        if ".m3u8" not in url:
            return [{"name": "MP4", "url": url}]
        url.meta["iptv_proto"] = "m3u8"
        return getDirectM3U8Playlist(url, checkExt=False, sortWithMaxBitrate=99999999) or [{"name": "HLS", "url": url}]

    def parserALBAPLAYER(self, baseUrl):  # add 031026
        # AlbaPlayer server picker (w.anaplayer.online/albaplayer/<slug>/): every "?serv=N" tab carries one hoster
        # iframe (cdnplus, mp4plus, anafast, vidoba, vidspeed, ok.ru ...) -> the first working ones through urlparser
        printDBG("parserALBAPLAYER baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        if baseUrl.meta.get("Referer"):
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]
        pageUrl = str(baseUrl).split("?", 1)[0]
        sts, data = self.cm.getPage(pageUrl, {"header": HTTP_HEADER})
        if not sts or not data:
            return []
        tabs = []
        for tab, name in re.findall(r"""<a[^>]+href=["']([^"']*?\?serv=\d+)["'][^>]*>([^<]*)</a>""", data):
            tabs.append((urljoin(pageUrl, tab.replace("&amp;", "&")), name.strip()))
        if not tabs:
            tabs = [(pageUrl, "")]
        up = urlparser()
        urltab = []
        found = 0
        for tab, name in tabs:
            if found >= 3:
                break
            if tab != pageUrl:
                sts, data = self.cm.getPage(tab, {"header": HTTP_HEADER})
                if not sts or not data:
                    continue
            frame = self.cm.ph.getSearchGroups(data, r"""<iframe[^>]+src=["']([^"']+)["']""")[0].replace("&amp;", "&")
            frame = "https:" + frame if frame.startswith("//") else frame
            if not self.cm.isValidUrl(frame) or up.checkHostSupport(frame) != 1 or up.getParser(frame) == up.pp.parserALBAPLAYER:
                continue
            links = up.getVideoLinkExt(strwithmeta(frame, {"Referer": urlparser.getDomain(pageUrl, False)}))
            if links:
                found += 1
            for item in links:
                item["name"] = ("%s %s" % (name or up.getHostName(frame, True), item.get("name", ""))).strip()
                urltab.append(item)
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

    def parserSTREAMCASH(self, baseUrl):  # add 031026 - streamcash.to /watch/<id> (fenixsite), goodstream.vip/embed/<id> (bajeczki): same player
        printDBG("parserSTREAMCASH baseUrl[%s]" % baseUrl)
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = strwithmeta(baseUrl).meta.get("Referer", host)
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        # window.__PCr = base64 JSON {"src": ".../index.m3u8", "subs": [{"src", "srclang", "label", "default"}], ...}
        match = re.search(r"""window\.__PCr\s*=\s*['"]([A-Za-z0-9+/=]+)['"]""", data)
        if not match:
            return []
        try:
            cfg = match.group(1)
            cfg = json_loads(ensure_str(base64.b64decode(cfg + "=" * (-len(cfg) % 4))))
        except Exception:
            printExc()
            return []
        url = (cfg.get("src") or "") if isinstance(cfg, dict) else ""
        if not url:
            return []
        url = urljoin(host, url)
        # Serbian/Croatian/Bosnian first, then the default track (sometimes a mislabelled Serbian one)
        for sub in sorted(cfg.get("subs", []) or [], key=lambda s: 0 if s.get("srclang", "") in ("rs", "sr", "hr", "bs") else (1 if s.get("default") else 2)):
            src = sub.get("src", "")
            if not src:
                continue
            lang = sub.get("srclang", "") or "und"
            subTracks.append({"title": lang.upper() if lang != "und" else sub.get("label", ""), "url": urljoin(host, src), "lang": lang, "format": "vtt"})
        isHls = ".m3u8" in url
        url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
        if isHls:
            urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=99999999))
        else:
            urltab.append({"name": urlparser.getDomain(baseUrl), "url": url})
        return urltab

    def parserVIDSONIC(self, baseUrl):
        printDBG("parserVIDSONIC baseUrl[%s]" % baseUrl)
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        match = re.search(r"""const\s+_0x1\s*=\s*'([^']+)';""", data)
        if not match:
            return []
        clean = match.group(1).replace("|", "")
        url = "".join(chr(int(clean[i: i + 2], 16)) for i in range(0, len(clean), 2))
        sub = re.search(r'data-subtitles\s*=\s*(["\'])(?P<content>.*?)\1', data)
        if sub:
            raw_content = sub.group("content").replace("&quot;", '"')
            var = re.findall(r'"lang":"([^"]+)","path":"([^"]+)', raw_content)
            for label, src in var:
                subTracks.append({"title": "", "url": "https:" + src if src.startswith("//") else src, "lang": label})
        url = urlparser.decorateUrl(url[::-1], {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
        urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserVIXEO(self, baseUrl):  # add 020926 - vixeo.io (filmpalast "Vixeo HD"), a vidsonic.net front
        printDBG("parserVIXEO baseUrl[%s]" % baseUrl)
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        m = re.search(r'data-config=(["\'])([A-Za-z0-9+/=_-]+)\1', data)
        if not m:
            return []
        blob = m.group(2).replace("-", "+").replace("_", "/").rstrip("=")
        try:
            cfg = json_loads(base64.b64decode(blob + "=" * (-len(blob) % 4)).decode())
        except Exception:
            printExc()
            return []
        # cfg["source"] is "|"-separated hex; concatenated, hex-decoded and byte-reversed it yields the stream url
        src = str(cfg.get("source", "") or "").replace("|", "")
        if not src:
            return []
        url = "".join(chr(int(src[i:i + 2], 16)) for i in range(0, len(src), 2))[::-1]
        for sub in (cfg.get("subtitles") or []):
            surl = sub.get("url") or sub.get("src") or sub.get("file") or ""
            if surl:
                subTracks.append({"title": "", "url": "https:" + surl if surl.startswith("//") else surl, "lang": sub.get("label") or sub.get("lang") or ""})
        url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
        if ".m3u8" in url:
            urltab.extend(getDirectM3U8Playlist(url))
        else:
            urltab.append({"name": "MP4", "url": url})
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

    def parserCOVERAPI(self, baseUrl):  # update 270226
        printDBG("parserCOVERAPI baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Accept-Language"] = "el,en-US;q=0.9,en;q=0.8"
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        news_id = re.search(r"news_id':'(\d+)'", data)
        if news_id:
            mod = "players3" if "player3" in data else "players"
            postdata = {"mod": mod, "news_id": news_id.group(1)}
            HTTP_HEADER["Referer"] = baseUrl
            sts, data = self.cm.getPage("%sengine/ajax/controller.php" % host, {"header": HTTP_HEADER}, postdata)
            if not sts:
                return []
            js = json_loads(data)
            if js.get("file"):
                url = js.get("file").split(" or ")[0]
                if "playlist" in url:
                    sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
                    if not sts:
                        return []
                    js = json_loads(data)
                    if js.get("playlist"):
                        js = js.get("playlist")[0]
                        for p in js.get("playlist", []):
                            if p.get("comment", "").endswith(baseUrl.meta.get("Episode")):
                                url = p.get("file")
            return urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
        return []

    def parserMEGAFILES(self, baseUrl):  # update 270226
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
            if isinstance(js.get("subtitles"), list):
                subTracks = [{"title": "", "url": sub.get("file"), "lang": sub.get("label")} for sub in js.get("subtitles", []) if sub.get("file") and sub.get("label")]
            url = urlparser.decorateUrl(js.get("source"), {"User-Agent": HTTP_HEADER["User-Agent"], "Accept": "*/*", "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserVIXSRC(self, baseUrl):  # fix 300526
        printDBG("parserVIXSRC baseUrl[%s]" % baseUrl)
        urltab = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", host)
        sts, data = self.cm.getPage(baseUrl.replace(host, host + "api/"), {"header": HTTP_HEADER})
        if not sts:
            return []
        src = json_loads(data).get("src", "")
        if src.startswith("/"):
            src = host[:-1] + src
        HTTP_HEADER["Referer"] = host
        HTTP_HEADER["Upgrade-Insecure-Requests"] = "1"
        sts, data = self.cm.getPage(src, {"header": HTTP_HEADER})
        if not sts:
            return []
        tok = re.search(r"token':\s*'([^']+)", data)
        exp = re.search(r"expires':\s*'([^']+)", data)
        hurl = re.search(r"url:\s*'([^']+)", data)
        if not all([tok, exp, hurl]):
            return []
        url = "%s%s&token=%s&expires=%s&h=1" % (hurl.group(1), "&" if "?" in hurl.group(1) else "?", tok.group(1), exp.group(1))
        if "?lang=it" in baseUrl:
            url += "&lang=it"
        if url.startswith("/"):
            url = host + url
        url = strwithmeta(url, {"iptv_proto": "m3u8", "User-Agent": HTTP_HEADER["User-Agent"], "Referer": src, "Accept": "*/*"})
        urltab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=False, sortWithMaxBitrate=99999999))
        return urltab

    def parserFLYFILE(self, baseUrl):  # add 030626, update 031026 - flyf.lat is the same player, its API is on flyfile.app; fallback for files without master.m3u8
        printDBG("parserFLYFILE baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        mid = baseUrl.split("?")[0].rstrip("/").split("/")[-1]
        if "flyf.lat/" in baseUrl:
            baseUrl = strwithmeta("https://flyfile.app/embed/%s" % mid, baseUrl.meta)
        origin = urlparser.getDomain(baseUrl, False).rstrip("/")
        api = "https://api.%s/api/" % urlparser.getDomain(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER.update({"Referer": baseUrl, "Origin": origin, "Accept": "application/json, text/plain, */*",
                            "X-FlyFile-View": "embed", "x-flyfile-host": urlparser.getDomain(baseUrl),
                            "X-Embed-Referrer": baseUrl.meta.get("Referer", "")})

        assignHeader = dict(HTTP_HEADER)
        assignHeader["X-Adblock-Detected"] = "0"
        sts, data = self.cm.getPage(api + "streaming/assign/%s" % mid, {"header": assignHeader})
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        if not data.get("url") or not data.get("token"):
            return []
        hlsBase = "%s/hls/%s/" % (data["url"].rstrip("/"), data["token"])
        streamHeader = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": origin + "/", "Origin": origin}
        urltab = getDirectM3U8Playlist(urlparser.decorateUrl(hlsBase + "master.m3u8", streamHeader), checkContent=True, sortWithMaxBitrate=999999999)
        if urltab:
            return urltab

        # some files have no master.m3u8 on the node (404), but <quality>/index.m3u8 and audio_<lang>_<n>/index.m3u8 exist;
        # the file info lists the qualities and audio tracks
        info = {}
        sts, data = self.cm.getPage(api + "public/file/%s" % mid, {"header": HTTP_HEADER})
        if sts:
            try:
                info = json_loads(data)
            except Exception:
                printExc()
        asset = (info.get("videoAsset") if isinstance(info, dict) else None) or {}
        qualities = asset.get("qualities") or []
        if not isinstance(qualities, list):
            try:
                qualities = json_loads(qualities)
            except Exception:
                qualities = []
        audioUrl = ""
        for idx, track in enumerate(asset.get("audioTracks") or [{}]):
            url = "%saudio_%s_%d/index.m3u8" % (hlsBase, track.get("lang") or "und", idx)
            sts, data = self.cm.getPage(url, {"header": streamHeader})
            if sts and "#EXTINF" in data:
                audioUrl = url
                break
        for q in qualities:
            q = q.get("quality", "") if isinstance(q, dict) else str(q)
            if not q:
                continue
            videoUrl = urlparser.decorateUrl(hlsBase + q + "/index.m3u8", streamHeader)
            if audioUrl:
                meta = dict(videoUrl.meta)
                meta.update({"audio_url": urlparser.decorateUrl(audioUrl, streamHeader), "video_url": videoUrl, "ff_out_container": "mpegts"})
                urltab.append({"name": "FlyFile %s" % q, "url": urlparser.decorateUrl("merge://audio_url|video_url", meta)})
            else:
                urltab.append({"name": "FlyFile %s" % q, "url": videoUrl})
        return urltab

    def parserABYSS(self, baseUrl):  # add 031026 - Abyss/SoTrym player (abyssplayer.com, abysscdn.com, btg549.filmoviplex.com)
        printDBG("parserABYSS baseUrl[%s]" % baseUrl)
        import json  # stdlib on purpose: py2 e2ijson (utf8=True) would byte-encode the binary "media" string

        def ctr(data, seed):
            key = ensure_binary(md5(seed).hexdigest())
            counter = pyaes.Counter(initial_value=int(hexlify(key[:16]), 16))
            return pyaes.AESModeOfOperationCTR(key, counter=counter).encrypt(data)

        def numSeed(value):  # md5 input the player uses for numbers: every digit as its byte value
            return bytes(bytearray(int(c) if c.isdigit() else ord(c) & 0xFF for c in str(value)))

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader("chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", urljoin(baseUrl, "/"))
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        playerOrigin = urljoin(self.cm.meta.get("url", baseUrl), "/")
        m = re.search(r'''(?:const|var|let)\s+datas\s*=\s*["']([^"']+)["']''', data)
        if not m:
            printDBG("parserABYSS: no datas blob")
            return []
        try:
            # atob() gives one char per byte, JSON.parse then resolves the \uXXXX escapes inside "media"
            datas = json.loads(base64.b64decode(m.group(1)).decode("latin-1"))
        except Exception:
            printExc()
            return []
        slug, md5Id, userId = datas.get("slug"), datas.get("md5_id"), datas.get("user_id")
        media = datas.get("media")
        if not isinstance(media, dict):
            if not (media and slug and md5Id and userId):
                return []
            enc = bytes(bytearray(ord(c) & 0xFF for c in media))
            seed = "%s:%s:%s" % (userId, slug, md5Id)
            media = None
            for s in (ensure_binary(seed), numSeed(seed)):
                try:
                    media = json.loads(ctr(enc, s).decode("utf-8"))
                    break
                except Exception:
                    media = None
            if not isinstance(media, dict):
                printDBG("parserABYSS: media decrypt failed")
                return []

        cdnHeader = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": playerOrigin}
        subTracks = []
        for sub in ((datas.get("config") or {}).get("subtitles") or []):
            if isinstance(sub, dict) and sub.get("slug"):
                lang = urllib_unquote(sub.get("lang") or "")
                subTracks.append({"title": lang, "url": "https://cdn.iamcdn.net/subtitle/%s/%s.%s" % (md5Id, sub["slug"], sub.get("type") or "srt"), "lang": lang, "format": sub.get("type") or "srt"})
        if subTracks:
            cdnHeader["external_sub_tracks"] = subTracks

        urltab = []
        mp4 = media.get("mp4") or {}
        domains = [d for d in (mp4.get("domains") or []) if d]
        sources = [s for s in (mp4.get("sources") or []) if isinstance(s, dict) and s.get("status") is not False]
        sources.sort(key=lambda s: int(s.get("size") or 0), reverse=True)
        for src in sources:
            label = "%s" % (src.get("label") or src.get("res_id") or "mp4")
            if src.get("file"):  # older payloads carry a plain link
                urltab.append({"name": "abyss %s" % label, "url": urlparser.decorateUrl(src["file"].replace("\\/", "/"), cdnHeader)})
                continue
            size, resId, sub = src.get("size"), src.get("res_id"), src.get("sub") or ""
            if not (size and resId and domains):
                continue
            domain = ([d for d in domains if sub and sub in d] or [domains[int(size) % len(domains)]])[0]
            path = "/mp4/%s/%s/%s?v=%s" % (md5Id, resId, size, slug)
            token = base64.b64encode(ctr(ensure_binary(path), numSeed(size))).replace(b"=", b"")
            token = ensure_str(base64.b64encode(token).replace(b"=", b""))
            url = "%s/sora/%s/%s" % (domain if domain.startswith("http") else "https://" + domain, size, token)
            urltab.append({"name": "abyss %s" % label, "url": urlparser.decorateUrl(url, dict(cdnHeader, iptv_format="mp4"))})

        hls = media.get("hls") or {}
        for key in ("file", "url", "master", "src", "source"):
            if isinstance(hls.get(key), basestring) and hls[key]:
                urltab.extend(getDirectM3U8Playlist(urlparser.decorateUrl(hls[key].replace("\\/", "/"), cdnHeader), checkContent=True))
                break
        return urltab

    def parserHQQ(self, baseUrl):  # add 031026 - netu/hqq/waaw (netu.filmoviplex.com, hqq.to, waaw.to)
        printDBG("parserHQQ baseUrl[%s]" % baseUrl)

        def clickPoint(png):
            # centre of the opaque pixels of the 8-bit, non-interlaced PNG the player shows (palette+tRNS seen;
            # RGBA/GA/RGB/grey handled too)
            try:
                if png[:8] != b"\x89PNG\r\n\x1a\n":
                    return None
                pos, idat, trns, ihdr = 8, b"", b"", None
                while pos + 8 <= len(png):
                    ln, typ = struct.unpack(">I4s", png[pos:pos + 8])
                    chunk = png[pos + 8:pos + 8 + ln]
                    if typ == b"IHDR":
                        ihdr = struct.unpack(">IIBBBBB", chunk)
                    elif typ == b"tRNS":
                        trns = bytearray(chunk)
                    elif typ == b"IDAT":
                        idat += chunk
                    elif typ == b"IEND":
                        break
                    pos += 12 + ln
                w, h, depth, ctype, _compr, _filt, interlace = ihdr
                bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
                if depth != 8 or interlace or not bpp:
                    return None
                raw = bytearray(zlib.decompress(idat))
                stride = w * bpp
                prev = bytearray(stride)
                xs = ys = n = 0
                bg = None
                for y in range(h):
                    f = raw[y * (stride + 1)]
                    line = raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
                    for i in range(stride):
                        a = line[i - bpp] if i >= bpp else 0
                        if f == 1:
                            line[i] = (line[i] + a) & 0xFF
                        elif f == 2:
                            line[i] = (line[i] + prev[i]) & 0xFF
                        elif f == 3:
                            line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
                        elif f == 4:
                            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
                            p = a + b - c
                            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                            line[i] = (line[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 0xFF
                    prev = line
                    for x in range(w):
                        px = line[x * bpp:(x + 1) * bpp]
                        if ctype == 3:
                            ink = (trns[px[0]] if px[0] < len(trns) else 255) >= 30
                        elif ctype in (4, 6):
                            ink = px[-1] >= 30
                        else:  # no alpha: anything that differs from the top-left background pixel
                            if bg is None:
                                bg = px
                            ink = sum(abs(px[k] - bg[k]) for k in range(bpp)) > 40
                        if ink:
                            xs += x
                            ys += y
                            n += 1
                if not n:
                    return None
                return xs // n, ys // n
            except Exception:
                printExc()
                return None

        baseUrl = strwithmeta(baseUrl)
        m = re.search(r'''/(?:[efv]/|watch_video\.php\?v=|embed_player\.php\?vid=)([A-Za-z0-9=+/_-]+)''', baseUrl) or \
            re.search(r'''[?&](?:v|vid)=([^&#]+)''', baseUrl)
        if not m:
            return []
        origin = urljoin(baseUrl, "/")[:-1]
        embedUrl = "%s/e/%s" % (origin, m.group(1))
        HTTP_HEADER = self.cm.getDefaultHeader("chrome")
        if baseUrl.meta.get("Referer"):
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]
        COOKIE_FILE = GetCookieDir("hqq.cookie")
        params = {"header": HTTP_HEADER, "ipv4_only": True, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE}
        sts, data = self.cm.getPage(embedUrl, params)
        if not sts:
            return []
        videoId = self.cm.ph.getSearchGroups(data, r"""['"]videoid['"]\s*:\s*['"]([^'"]+)""")[0]
        videoKey = self.cm.ph.getSearchGroups(data, r"""['"]videokey['"]\s*:\s*['"]([^'"]+)""")[0]
        adbn = self.cm.ph.getSearchGroups(data, r"""adbn\s*=\s*['"]([^'"]*)""")[0]
        keyOrig = self.cm.ph.getSearchGroups(data, r"""videokeyorig\s*=\s*['"]([^'"]+)""")[0] or m.group(1)
        if not videoId or not videoKey:
            printDBG("parserHQQ: no videoid/videokey (removed video?)")
            return []
        subTracks = []
        for subUrl, subLabel in re.findall(r'''file2sub\(\s*["']([^"']+)["']\s*,\s*["'][^"']*["']\s*,\s*["']([^"']*)["']''', data):
            if subUrl.startswith("//"):
                subUrl = "https:" + subUrl
            subTracks.append({"title": subLabel, "url": subUrl, "lang": subLabel, "format": subUrl.rsplit(".", 1)[-1].lower() if "." in subUrl[-5:] else "srt"})

        ajaxParams = dict(params)
        ajaxParams["load_cookie"] = True
        ajaxParams["raw_post_data"] = True
        ajaxParams["header"] = dict(HTTP_HEADER)
        ajaxParams["header"].update({"Referer": embedUrl, "Origin": origin, "X-Requested-With": "XMLHttpRequest",
                                     "Content-Type": "application/json", "Accept": "application/json, text/javascript, */*; q=0.01"})
        link = ""
        for attempt in range(3):
            sts, data = self.cm.getPage(origin + "/player/get_player_image.php", ajaxParams,
                                        json_dumps({"videoid": videoId, "videokey": videoKey, "width": 400, "height": 400}))
            if not sts or "Video not found" in data:
                return []
            try:
                img = json_loads(data)
            except Exception:
                printExc()
                return []
            if img.get("try_again") == "1" or not img.get("image"):
                GetIPTVSleep().Sleep(min(10, int(img.get("isec") or 5)))
                continue
            point = clickPoint(base64.b64decode(re.sub(r"^data:image/[a-z]+;base64,", "", img["image"])))
            printDBG("parserHQQ: click point %s" % (point,))
            x, y = point or (200, 200)
            GetIPTVSleep().Sleep(3)  # faster "clicks" are answered with try_again=1
            post = {"htoken": "", "sh": "".join(random_choice("0123456789abcdef") for _i in range(40)), "ver": "4", "secure": "0",
                    "adb": adbn, "v": urllib_quote(keyOrig, safe=""), "token": "", "gt": "", "embed_from": "0", "wasmcheck": 1,
                    "adscore": "", "click_hash": urllib_quote(img.get("hash_image", ""), safe=""), "clickx": x, "clicky": y}
            sts, data = self.cm.getPage(origin + "/player/get_md5.php", ajaxParams, json_dumps(post))
            if not sts:
                return []
            try:
                ret = json_loads(data)
            except Exception:
                printExc()
                return []
            obf = (ret.get("obf_link") or "#")[1:]
            if ret.get("try_again") == "1" or not obf:
                printDBG("parserHQQ: get_md5 try_again (attempt %d)" % attempt)
                continue
            link = "".join(chr(int(obf[i:i + 3], 16)) for i in range(0, len(obf) - 2, 3))
            break
        if not link:
            SetIPTVPlayerLastHostError(_("netu/hqq: the player check failed, try again later."))
            return []
        url = ("https:" + link) if link.startswith("//") else link
        if ".m3u8" not in url:
            url += ".mp4.m3u8"
        meta = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": embedUrl, "Origin": origin}
        if subTracks:
            meta["external_sub_tracks"] = subTracks
        url = urlparser.decorateUrl(url, meta)
        # the CDN (*.cfglobalcdn.com) is unreachable from some networks: without a connect timeout the request
        # hangs for minutes (TCP retries) before failing
        urltab = getDirectM3U8Playlist(url, checkExt=False, cookieParams={"timeout": 15}, checkContent=True, sortWithMaxBitrate=999999999)
        if not urltab:
            sts, data = self.cm.getPage(url, {"header": dict((k, meta[k]) for k in ("User-Agent", "Referer", "Origin")), "timeout": 15})
            if not sts and not (getattr(data, "meta", None) or self.cm.meta or {}).get("status_code"):
                SetIPTVPlayerLastHostError(_('Failed to connect to server "%s".') % self.cm.getBaseUrl(url, True))
                return []
            urltab = [{"name": "netu/hqq", "url": urlparser.decorateUrl(url, {"iptv_proto": "m3u8"})}]
        return urltab

    def parserANONMP4(self, baseUrl):  # fix 050626
        printDBG("parserANONMP4 baseUrl[%s]" % baseUrl)
        urltab = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER['Referer'] = baseUrl  # FIX: Added
        HTTP_HEADER['Origin'] = host[:-1] if host.endswith('/') else host  # FIX: Added
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        url = re.search(r"fetch\('(https://cryoapi\.shadowapi\.skin/load/[^']+)'\)", data)  # FIX: Changed from SINGLE_API_URL
        if url:
            HTTP_HEADER.update({"Referer": host, "Origin": host[:-1]})
            sts, data = self.cm.getPage(url.group(1), {"header": HTTP_HEADER})
            if not sts:
                return []
            js = json_loads(data)
            if "tracks" in js:
                for x in js.get("tracks", []):
                    name = "[%s] " % x.get("track_name", "unk")
                    sts, data = self.cm.getPage(x.get("track_url"), {"header": HTTP_HEADER})
                    if not sts:
                        continue
                    js = json_loads(data)
                    url = urlparser.decorateUrl(js.get("hls"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                    for p in getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999):  # Add language
                        p["name"] = name + p.get("name", "")
                        urltab.append(p)
            else:
                url = urlparser.decorateUrl(js.get("hls"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
                urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
        return urltab

    def parserVIDROCK(self, baseUrl):  # add 030926 - vidrock.net (7reels "AdRock"); per-server AES-256-GCM blobs from a plain JSON API
        printDBG("parserVIDROCK baseUrl[%s]" % baseUrl)
        m = re.search(r"vidrock\.net/(?:api/)?(movie/\d+|tv/\d+/\d+/\d+)", baseUrl)
        if not m:
            return []
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = "https://vidrock.net/"
        sts, data = self.cm.getPage("https://vidrock.net/api/" + m.group(1), {"header": HTTP_HEADER})
        if not sts:
            return []
        try:
            servers = json_loads(data)
        except Exception:
            printExc()
            return []
        cipher = python_aesgcm.new(unhexlify("7f3e9c2a8b5d1f4e6a9c3b7d2e5f8a1c4b6d9e2f5a8c1b4d7e9f2a5c8b1d4e7f"))
        urltab = []
        for name, info in servers.items():
            enc = (info or {}).get("url")
            if not enc:
                continue
            try:
                blob = base64.b64decode(enc.replace("-", "+").replace("_", "/") + "=" * (-len(enc) % 4))
                plain = cipher.open(blob[:12], blob[12:])
            except Exception:
                printExc()
                continue
            if not plain:
                continue
            if isinstance(plain, (bytes, bytearray)):
                url = plain.decode("utf-8", "ignore").strip()
            else:
                url = str(plain).strip()
            if not url.startswith("http"):
                continue
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://vidrock.net/", "Origin": "https://vidrock.net"})
            if ".m3u8" in url:
                for item in getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999):
                    item["name"] = "%s %s" % (name, item.get("name", ""))
                    urltab.append(item)
            else:
                urltab.append({"name": name, "url": url})
        return urltab

    def parserVIDNEO(self, baseUrl):  # fix 060726
        printDBG("parserVIDNEO baseUrl[%s]" % baseUrl)
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER['Referer'] = baseUrl
        HTTP_HEADER['Origin'] = host[:-1] if host.endswith('/') else host

        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []

        urltab = []
        r = re.search(r'({\\"src.+})]}]', data)
        if r:
            try:
                json_str = r.group(1).replace('\\', '')
                jd = json_loads(json_str)
                src = jd.get('src')

                if src:
                    if src.startswith('/'):
                        src = "https://%s%s" % (urlparser.getDomain(baseUrl), src)

                    url = urlparser.decorateUrl(src, {
                        "User-Agent": HTTP_HEADER["User-Agent"],
                        "Referer": baseUrl,
                        "Origin": host[:-1] if host.endswith('/') else host
                    })

                    if '.m3u8' in url.lower():
                        urltab.extend(getDirectM3U8Playlist(url))
                    else:
                        urltab.append({'name': 'VidNeo Direct', 'url': url, 'need_resolve': 0})
            except Exception:
                printExc()
                return []

        return urltab

    def parserVIDNEST(self, baseUrl):  # add 250826
        def vidnestB64Decode(s):
            alphabet = "RB0fpH8ZEyVLkv7c2i6MAJ5u3IKFDxlS1NTsnGaqmXYdUrtzjwObCgQP94hoeW+/="
            rev = {c: i for i, c in enumerate(alphabet)}
            s = s + "=" * ((-len(s)) % 4)
            out = bytearray()
            for i in range(0, len(s), 4):
                chunk = s[i:i + 4]
                c0 = rev.get(chunk[0], 64)
                c1 = rev.get(chunk[1], 64)
                c2 = 64 if chunk[2] == "=" else rev.get(chunk[2], 64)
                c3 = 64 if chunk[3] == "=" else rev.get(chunk[3], 64)
                out.append(((c0 << 2) | (c1 >> 4)) & 0xFF)
                if c2 != 64:
                    out.append((((c1 & 0x0F) << 4) | (c2 >> 2)) & 0xFF)
                if c3 != 64:
                    out.append((((c2 & 0x03) << 6) | c3) & 0xFF)
            return bytes(out).decode("utf-8", "replace")

        def extractLinks(server, root):
            links = []
            try:
                if server == "moviebox":
                    for item in root.get("url", []) or []:
                        if item.get("link"):
                            links.append((item["link"], item.get("resolution", "")))
                elif server in ("allmovies", "delta"):
                    for item in root.get("streams", []) or []:
                        if item.get("url"):
                            links.append((item["url"], item.get("language", "")))
                elif server == "hollymoviehd":
                    for item in root.get("sources", []) or []:
                        if item.get("file"):
                            links.append((item["file"], item.get("label", "")))
                elif server in ("purstream", "klikxxi"):
                    for item in root.get("sources", []) or []:
                        if item.get("url"):
                            links.append((item["url"], item.get("quality", item.get("name", ""))))
                elif server == "vidlink":
                    playlist = root.get("data", {}).get("stream", {}).get("playlist")
                    if playlist:
                        links.append((playlist, ""))
                elif server == "onehd":
                    if root.get("url"):
                        links.append((root["url"], ""))
            except Exception:
                printExc()
            return links

        printDBG("parserVIDNEST baseUrl[%s]" % baseUrl)
        urltab = []
        m = re.search(r"/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?", baseUrl)
        if not m:
            return []
        mediaType, tmdbId, season, episode = m.group(1), m.group(2), m.group(3), m.group(4)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = "https://vidnest.fun/"
        HTTP_HEADER["Origin"] = "https://vidnest.fun"
        servers = ["moviebox", "allmovies", "catflix", "purstream", "hollymoviehd", "lamda", "flixhq", "vidlink", "onehd", "klikxxi"]
        for server in servers:
            if mediaType == "tv" and season and episode:
                apiUrl = "https://new.vidnest.fun/%s/tv/%s/%s/%s" % (server, tmdbId, season, episode)
            else:
                apiUrl = "https://new.vidnest.fun/%s/movie/%s" % (server, tmdbId)
            if server == "onehd":
                apiUrl += "?server=upcloud"
            sts, data = self.cm.getPage(apiUrl, {"header": dict(HTTP_HEADER), "timeout": 10})
            if not sts:
                continue
            try:
                resp = json_loads(data)
                payload = resp.get("data")
                if not payload:
                    continue
                if resp.get("encrypted"):
                    payload = vidnestB64Decode(payload)
                root = json_loads(payload)
            except Exception:
                continue
            for url, label in extractLinks(server, root):
                if url.startswith("//"):
                    url = "https:" + url
                decoUrl = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://vidnest.fun/"})
                name = "VidNest %s" % server.capitalize()
                if label:
                    name += " %s" % label
                if ".m3u8" in url.lower():
                    for item in getDirectM3U8Playlist(decoUrl, sortWithMaxBitrate=99999999):
                        item["name"] = ("%s %s" % (name, item.get("name", ""))).strip()
                        urltab.append(item)
                else:
                    urltab.append({"name": name, "url": decoUrl})
        return urltab

    def _externalResolveAllowed(self, who):
        # parserVIDEASY/VIDCORE/VIDLINK/PEACHIFY need the third-party enc-dec.app
        # service to decrypt their links; it is opt-in (off by default) and the
        # settings screen makes the user confirm twice - see iptvconfigmenu.
        try:
            from Plugins.Extensions.IPTVPlayer.components.iptvconfigmenu import IsExternalResolveAllowed
            if not IsExternalResolveAllowed():
                printDBG("%s: external link-decryption (enc-dec.app) disabled in config" % who)
                return False
        except Exception:
            printExc()
        return True

    def parserPEACHIFY(self, baseUrl):  # add 250826
        printDBG("parserPEACHIFY baseUrl[%s]" % baseUrl)
        if not self._externalResolveAllowed("parserPEACHIFY"):
            return []
        urltab = []
        m = re.search(r"/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?", baseUrl)
        if not m:
            return []
        mediaType, tmdbId, season, episode = m.group(1), m.group(2), m.group(3), m.group(4)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = "https://peachify.top/"
        HTTP_HEADER["Origin"] = "https://peachify.top"
        apiBase = "https://x.eat-peach.sbs"
        servers = ["moviebox", "air", "holly", "hr", "multi"]
        for server in servers:
            if mediaType == "tv" and season and episode:
                apiUrl = "%s/%s/tv/%s/%s/%s" % (apiBase, server, tmdbId, season, episode)
            else:
                apiUrl = "%s/%s/movie/%s" % (apiBase, server, tmdbId)
            sts, data = self.cm.getPage(apiUrl, {"header": dict(HTTP_HEADER), "timeout": 10})
            if not sts:
                continue
            try:
                payload = json_loads(data).get("data")
                if not payload:
                    continue
                sts2, decData = self.cm.getPage(
                    "https://enc-dec.app/api/dec-peachify",
                    {"header": {"Content-Type": "application/json"}, "raw_post_data": True, "timeout": 10},
                    json_dumps({"text": payload}),
                )
                if not sts2:
                    continue
                decResp = json_loads(decData)
                if decResp.get("status") != 200:
                    continue
                sources = decResp.get("result", {}).get("sources", [])
            except Exception:
                continue
            for src in sources or []:
                url = src.get("url")
                if not url:
                    continue
                name = "Peachify %s" % server.capitalize()
                if src.get("dub"):
                    name += " %s" % src["dub"]
                if src.get("quality"):
                    name += " %sp" % src["quality"]
                decoUrl = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://peachify.top/", "Origin": "https://peachify.top"})
                if ".m3u8" in url.lower():
                    for item in getDirectM3U8Playlist(decoUrl, sortWithMaxBitrate=99999999):
                        item["name"] = ("%s %s" % (name, item.get("name", ""))).strip()
                        urltab.append(item)
                else:
                    urltab.append({"name": name, "url": decoUrl})
        return urltab

    def parserVIDEASY(self, baseUrl):  # updated 040926 - site moved its backend from api.videasy.net to api.speedracelight.com and now requires a /seed step plus a (double URL-encoded) title for sources-with-title
        printDBG("parserVIDEASY baseUrl[%s]" % baseUrl)
        if not self._externalResolveAllowed("parserVIDEASY"):
            return []
        urltab = []
        m = re.search(r"/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?", baseUrl)
        if not m:
            return []
        mediaType, tmdbId, season, episode = m.group(1), m.group(2), m.group(3), m.group(4)

        # title/year travel as plain query params on the candidate URL itself
        # (decorateParamsFromUrl only whitelists header-ish keys into .meta, so
        # we read them back out of the raw url text here instead).
        titleMatch = re.search(r"[?&]title=([^&]+)", baseUrl)
        yearMatch = re.search(r"[?&]year=([^&]+)", baseUrl)
        title = urllib_unquote(titleMatch.group(1)) if titleMatch else ""
        year = urllib_unquote(yearMatch.group(1)) if yearMatch else ""
        encTitle = urllib_quote(urllib_quote(title, safe=""), safe="")

        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = "https://player.videasy.to/"
        HTTP_HEADER["Origin"] = "https://player.videasy.to"

        sts0, seedData = self.cm.getPage("https://api.speedracelight.com/seed?mediaId=%s" % tmdbId, {"header": dict(HTTP_HEADER), "timeout": 10})
        if not sts0:
            return []
        try:
            seed = json_loads(seedData).get("seed")
        except Exception:
            seed = None
        if not seed:
            return []

        # server list per smy778/EncDecEndpoints samples/videasy.py
        # ("vsrc" / "meine" endpoints 404 on the live API, left out)
        servers = ["cdn", "hdmovie", "m4uhd", "lamovie", "superflix"]
        for name in servers:
            apiUrl = ("https://api.speedracelight.com/%s/sources-with-title"
                      "?title=%s&mediaType=%s&year=%s&tmdbId=%s&imdbId=&episodeId=%s&seasonId=%s&enc=2&seed=%s"
                      % (name, encTitle, mediaType, year, tmdbId, episode or "1", season or "1", seed))
            sts, data = self.cm.getPage(apiUrl, {"header": dict(HTTP_HEADER), "timeout": 10})
            if not sts:
                continue
            blob = data.strip()
            if not blob or len(blob) < 10:
                continue
            sts2, decData = self.cm.getPage(
                "https://enc-dec.app/api/dec-videasy",
                {"header": {"Content-Type": "application/json"}, "raw_post_data": True, "timeout": 10},
                json_dumps({"text": blob, "id": tmdbId, "seed": seed}),
            )
            if not sts2:
                continue
            try:
                decResp = json_loads(decData)
                if decResp.get("status") != 200:
                    continue
                result = decResp.get("result", {})
            except Exception:
                continue

            sources = result.get("sources") if isinstance(result, dict) else None
            found = []
            if sources:
                for src in sources:
                    u = src.get("url")
                    if u:
                        found.append((u, src.get("quality")))
            else:
                # schema-agnostic fallback: walk the whole result for any
                # http(s) link ending up as a playable stream
                stack = [result]
                while stack:
                    node = stack.pop()
                    if isinstance(node, dict):
                        stack.extend(node.values())
                    elif isinstance(node, list):
                        stack.extend(node)
                    elif isinstance(node, basestring) and node.startswith("http") and (".m3u8" in node or ".mp4" in node):
                        found.append((node, None))

            for url, quality in found:
                itemName = "Videasy %s" % name.capitalize()
                decoUrl = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://player.videasy.to/", "Origin": "https://player.videasy.to", "iptv_use_ffmpeg": True})
                qm = re.search(r"(\d{3,4})p", url)
                if quality or qm:
                    # this link already names its own single quality (either the
                    # API told us, or it's baked into the URL, e.g. .../s1080p-.../
                    # ...m3u8) - no need to probe the playlist to discover it.
                    itemName += " %s" % (quality or ("%sp" % qm.group(1)))
                    urltab.append({"name": itemName, "url": decoUrl})
                elif ".m3u8" in url.lower():
                    # genuine multi-variant master playlist - let the helper
                    # discover the actual qualities inside it.
                    for item in getDirectM3U8Playlist(decoUrl, sortWithMaxBitrate=99999999):
                        item["name"] = ("%s %s" % (itemName, item.get("name", ""))).strip()
                        urltab.append(item)
                else:
                    urltab.append({"name": itemName, "url": decoUrl})
            if urltab:
                return urltab
        return urltab

    def parserVIDLINK(self, baseUrl):  # add 060926 - vidlink.pro; enc-dec.app encrypts the tmdb id, /api/b returns the sources json directly (no 2nd decrypt)
        printDBG("parserVIDLINK baseUrl[%s]" % baseUrl)
        if not self._externalResolveAllowed("parserVIDLINK"):
            return []
        urltab = []
        m = re.search(r"/(movie|tv)/(\d+)(?:/(\d+)/(\d+))?", baseUrl)
        if not m:
            return []
        mediaType, tmdbId, season, episode = m.group(1), m.group(2), m.group(3), m.group(4)
        api = "https://enc-dec.app/api"
        HTTP_HEADER = self.cm.getDefaultHeader()
        sts, data = self.cm.getPage("%s/enc-vidlink?%s" % (api, urllib_urlencode({"text": tmdbId})), {"header": {"User-Agent": HTTP_HEADER["User-Agent"]}})
        if not sts:
            return []
        try:
            enc = json_loads(data).get("result")
        except Exception:
            printExc()
            return []
        if not enc:
            return []
        if mediaType == "tv":
            apiUrl = "https://vidlink.pro/api/b/tv/%s/%s/%s" % (enc, season or "1", episode or "1")
        else:
            apiUrl = "https://vidlink.pro/api/b/movie/%s" % enc
        provHdr = {"User-Agent": HTTP_HEADER["User-Agent"], "Origin": "https://vidlink.pro", "Referer": "https://vidlink.pro/"}
        sts, data = self.cm.getPage(apiUrl, {"header": provHdr})
        if not sts:
            return []
        try:
            res = json_loads(data)
        except Exception:
            printExc()
            return []
        if not isinstance(res, dict):
            return []
        subTracks = []
        try:
            for c in (((res.get("stream") or {}) if isinstance(res.get("stream"), dict) else {}).get("captions") or res.get("captions") or []):
                cu = c.get("url") or c.get("file")
                if cu:
                    subTracks.append({"title": c.get("label", ""), "url": cu, "lang": c.get("language", c.get("label", ""))})
        except Exception:
            printExc()
        found = []
        stack = [res]
        seen = set()
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, basestring) and node.startswith("http") and node not in seen and (".m3u8" in node or ".mp4" in node):
                seen.add(node)
                found.append(node)
        for url in found:
            deco = {"User-Agent": provHdr["User-Agent"], "Referer": "https://vidlink.pro/", "Origin": "https://vidlink.pro", "iptv_use_ffmpeg": True}
            if subTracks:
                deco["external_sub_tracks"] = subTracks
            decoUrl = urlparser.decorateUrl(url, deco)
            if ".m3u8" in url.lower():
                for item in getDirectM3U8Playlist(decoUrl, sortWithMaxBitrate=99999999):
                    item["name"] = ("Vidlink %s" % item.get("name", "")).strip()
                    urltab.append(item)
            else:
                urltab.append({"name": "Vidlink", "url": decoUrl})
        return urltab

    def parserVIDCORE(self, baseUrl):  # add 030926 / upd 060926 - vidcore.net/.io + vidup.to + vidfast.pro/.vc (shared codebase); page token -> enc-dec.app enc/dec chain
        printDBG("parserVIDCORE baseUrl[%s]" % baseUrl)
        if not self._externalResolveAllowed("parserVIDCORE"):
            return []
        urltab = []
        m = re.search(r"/(movie|tv)/([A-Za-z0-9]+)(?:/(\d+)/(\d+))?", baseUrl)
        if not m:
            return []
        mediaType, mid, season, episode = m.group(1), m.group(2), m.group(3), m.group(4)
        lowUrl = baseUrl.lower()
        if "vidfast" in lowUrl:
            host = "vidfast.vc" if "vidfast.vc" in lowUrl else "vidfast.pro"
            name = "vidfast"
        elif "vidup" in lowUrl:
            host, name = "vidup.to", "vidup"
        else:
            host, name = "vidcore.io", "vidcore"
        ref = "https://%s/" % host
        api = "https://enc-dec.app/api"
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = ref
        if mediaType == "tv" and season and episode:
            pageUrl = "%stv/%s/%s/%s/" % (ref, mid, season, episode)
        else:
            pageUrl = "%smovie/%s/" % (ref, mid)
        sts, data = self.cm.getPage(pageUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        # the page carries the real request token as \"en\":\"...\"; a Firebase
        # service-worker registration on the same page also has a \"token\":\"APA91...\"
        # - prefer "en", and never hand a Firebase FCM token to the API
        token = None
        for pat in (r'\\"en\\":\\"([^\\"]+)', r'\\"token\\":\\"([^\\"]+)'):
            for cand in re.findall(pat, data):
                if cand.startswith("APA91") or len(cand) > 400:
                    continue
                token = cand
                break
            if token:
                break
        if not token:
            return []
        sts, data = self.cm.getPage("%s/enc-%s?%s" % (api, name, urllib_urlencode({"text": token})), {"header": {"User-Agent": HTTP_HEADER["User-Agent"]}})
        if not sts:
            return []
        try:
            parts = json_loads(data)["result"]
            serversUrl, streamBase, csrf = parts["servers"], parts["stream"], parts["token"]
        except Exception:
            printExc()
            return []
        provHdr = {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": ref, "X-Requested-With": "XMLHttpRequest", "X-CSRF-Token": csrf}
        sts, serversEnc = self.cm.getPage(serversUrl, {"header": provHdr, "raw_post_data": True}, "")
        if not sts:
            return []
        sts, data = self.cm.getPage("%s/dec-%s" % (api, name), {"header": {"Content-Type": "application/json"}, "raw_post_data": True}, json_dumps({"text": serversEnc}))
        if not sts:
            return []
        try:
            serverList = json_loads(data).get("result") or []
        except Exception:
            printExc()
            return []
        for srv in serverList[:5]:
            srvData = srv.get("data")
            if not srvData:
                continue
            sts, streamEnc = self.cm.getPage("%s/%s" % (streamBase, srvData), {"header": provHdr, "raw_post_data": True}, "")
            if not sts:
                continue
            sts, data = self.cm.getPage("%s/dec-%s" % (api, name), {"header": {"Content-Type": "application/json"}, "raw_post_data": True}, json_dumps({"text": streamEnc}))
            if not sts:
                continue
            try:
                res = json_loads(data)
                if res.get("status") != 200:
                    continue
                streamUrl = res.get("result", {}).get("url")
            except Exception:
                continue
            if not streamUrl:
                continue
            label = ("%s %s" % (name.capitalize(), srv.get("name", ""))).strip()
            decoUrl = urlparser.decorateUrl(streamUrl, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": ref, "Origin": ref[:-1], "iptv_use_ffmpeg": True})
            if ".m3u8" in streamUrl:
                for item in getDirectM3U8Playlist(decoUrl, sortWithMaxBitrate=99999999):
                    item["name"] = ("%s %s" % (label, item.get("name", ""))).strip()
                    urltab.append(item)
            else:
                urltab.append({"name": label, "url": decoUrl})
        # the "Euro" server has repeatedly been observed serving short ad clips
        # instead of the real movie/episode - push it to the back so it isn't
        # the first thing the user tries, without dropping it as a fallback.
        urltab.sort(key=lambda item: 1 if "euro" in item.get("name", "").lower() else 0)
        return urltab

    def parserVIDSST(self, baseUrl):  # add 050926 - vids.st (premiumsmart.eu "VidsST" mirror), bespoke ArtPlayer host
        printDBG("parserVIDSST baseUrl[%s]" % baseUrl)
        urltab = []
        host = urlparser.getDomain(baseUrl, False)
        HTTP_HEADER = self.cm.getDefaultHeader()
        HTTP_HEADER["Referer"] = baseUrl
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return []
        # the /e/<id> embed page carries the master playlist url in a plain JS const
        m = re.search(r'''const\s+url\s*=\s*["'](https?:[^"']+\.m3u8[^"']*)["']''', data)
        if not m:
            m = re.search(r'''["'](https?:(?:\\?/){2}[^"']+?/master\.m3u8[^"']*)["']''', data)
        # add 041026: some files are a plain MP4 (const url = "https:\/\/vids.st\/storage\/uploads\/...mp4")
        isMp4 = False
        if not m:
            m = re.search(r'''const\s+url\s*=\s*["'](https?:[^"']+\.mp4[^"']*)["']''', data)
            isMp4 = bool(m)
        if not m:
            return []
        url = m.group(1).replace("\\/", "/")
        subTracks = []
        sm = re.search(r'"subtitleUrl"\s*:\s*"([^"]+)"', data)
        if sm and sm.group(1):
            lm = re.search(r'"subtitleLabel"\s*:\s*"([^"]*)"', data)
            label = lm.group(1) if lm else ""
            subTracks.append({"title": label, "url": sm.group(1).replace("\\/", "/"), "lang": label})
        url = urlparser.decorateUrl(url, {
            "User-Agent": HTTP_HEADER["User-Agent"],
            "Referer": baseUrl,
            "Origin": host[:-1] if host.endswith("/") else host,
            "external_sub_tracks": subTracks,
        })
        if not isMp4:
            urltab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True))
        if not urltab:
            urltab.append({"name": "vids.st", "url": url, "need_resolve": 0})
        return urltab

    def parserYANDEXDISK(self, baseUrl):  # add 031026 - yadi.sk / disk.yandex.* / disk.360.yandex.ru public links, official public API
        printDBG("parserYANDEXDISK baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        api = "https://cloud-api.yandex.net/v1/disk/public/resources"
        publicKey = urllib_quote(baseUrl.split("?")[0].split("#")[0], safe="")
        sts, data = self.cm.getPage("%s?public_key=%s&limit=200" % (api, publicKey), {"header": HTTP_HEADER})
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        # a shared file, or a shared folder: then every video file in it
        files = [("", data)] if data.get("type") == "file" else \
            [(item.get("path", ""), item) for item in (data.get("_embedded") or {}).get("items", []) if item.get("type") == "file"]
        urltab = []
        for path, item in files:
            if not (item.get("mime_type") or "").startswith(("video/", "audio/")):
                continue
            url = "%s/download?public_key=%s" % (api, publicKey)
            if path:
                url += "&path=" + urllib_quote(path, safe="")
            sts, link = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                continue
            try:
                href = json_loads(link).get("href", "")
            except Exception:
                printExc()
                continue
            if href:
                urltab.append({"name": "Yandex Disk %s" % item.get("name", ""), "url": urlparser.decorateUrl(href, {"User-Agent": HTTP_HEADER["User-Agent"]})})
        return urltab

    def parserSTREAMABLE(self, baseUrl):  # add 031026 - streamable.com, public video API (the page's videoObject json is gone)
        printDBG("parserSTREAMABLE baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        videoId = ph.search(baseUrl, r"streamable\.com/(?:[eos]/)?([A-Za-z0-9]+)")[0]
        if not videoId:
            return []
        sts, data = self.cm.getPage("https://api.streamable.com/videos/%s" % videoId, {"header": HTTP_HEADER})
        if not sts:
            return []
        try:
            data = json_loads(data)
        except Exception:
            printExc()
            return []
        urltab = []
        for key, stream in (data.get("files") or {}).items():
            url = (stream or {}).get("url") or ""
            # the API sometimes answers "https:https://..." or a scheme-less "//..."
            url = re.sub(r"^(?:https?:)+(?=//)", "", url)
            if url.startswith("//"):
                url = "https:" + url
            if url.startswith("http"):
                height = stream.get("height") or 0
                urltab.append((height, {"name": "%sp %s" % (height, key) if height else key, "url": urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"]})}))
        urltab.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in urltab]
