# -*- coding: utf-8 -*-
import base64
from binascii import unhexlify
import codecs
from copy import deepcopy
from hashlib import sha256
from random import choice as random_choice, randrange
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
from Plugins.Extensions.IPTVPlayer.libs import aadecode, ph, pyaes
from Plugins.Extensions.IPTVPlayer.libs.crypto.cipher.aes_cbc import AES_CBC
from Plugins.Extensions.IPTVPlayer.libs.dehunt import dehunt
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
from Plugins.Extensions.IPTVPlayer.libs.jsunpack import get_packed_data
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common, CParsingHelper
from Plugins.Extensions.IPTVPlayer.libs.recaptcha_v2 import UnCaptchaReCaptcha
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import captchaParser, decorateUrl, getDirectM3U8Playlist, getMPDLinksWithMeta, TEAMCASTPL_decryptPlayerParams, unicode_escape, unpackJSPlayerParams, VIDUPME_decryptPlayerParams
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.mtv import GametrailersIE
from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.utils import clean_html, unescapeHTML
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary, ensure_str
from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2
from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import urllib_quote, urllib_quote_plus, urllib_unquote, urllib_urlencode
from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import parse_qs, urljoin, urlparse
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import CSelOneLink, formatBytes, GetCookieDir, GetDefaultLang, GetJSScriptFile, GetPluginDir, GetPyScriptCmd, GetTmpDir, MergeDicts, printDBG, printExc, rm
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta

if not isPY2():
    basestring = str
    xrange = range


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


def tear_decode(data_file, data_seed):
    def replacer(match):
        chars = {"0": "5", "1": "6", "2": "7", "5": "0", "6": "1", "7": "2"}
        return chars[match.group(0)]

    def str2bytes(a16):
        return [ord(i) for i in a16]

    def bytes2str(a10):
        return "".join(chr(255 & b) for b in a10)

    def digest_pad(a36):
        a41 = []
        a39 = 0
        a40 = len(a36)
        a43 = 15 - (a40 % 16)
        a41.append(a43)
        while a39 < a40:
            a41.append(a36[a39])
            a39 += 1
        a45 = a43
        while a45 > 0:
            a41.append(0)
            a45 -= 1
        return a41

    def blocks2bytes(a29):
        a34 = []
        a33 = 0
        a32 = len(a29)
        while a33 < a32:
            a34 += [255 & rshift(int(a29[a33]), 24)]
            a34 += [255 & rshift(int(a29[a33]), 16)]
            a34 += [255 & rshift(int(a29[a33]), 8)]
            a34 += [255 & a29[a33]]
            a33 += 1
        return a34

    def bytes2blocks(a22):
        a27 = []
        a28 = 0
        a26 = 0
        a25 = len(a22)
        while True:
            a27.append(((255 & a22[a26]) << 24) & 0xFFFFFFFF)
            a26 += 1
            if a26 >= a25:
                break
            a27[a28] |= (255 & a22[a26]) << 16 & 0xFFFFFFFF
            a26 += 1
            if a26 >= a25:
                break
            a27[a28] |= (255 & a22[a26]) << 8 & 0xFFFFFFFF
            a26 += 1
            if a26 >= a25:
                break
            a27[a28] |= 255 & a22[a26]
            a26 += 1
            if a26 >= a25:
                break
            a28 += 1
        return a27

    def xor_blocks(a76, a77):
        return [a76[0] ^ a77[0], a76[1] ^ a77[1]]

    def unpad(a46):
        a49 = 0
        a52 = []
        a53 = 7 & a46[a49]
        a49 += 1
        a51 = len(a46) - a53
        while a49 < a51:
            a52 += [a46[a49]]
            a49 += 1
        return a52

    def rshift(a, b):
        return (a % 0x100000000) >> b

    def tea_code(a79, a80):
        a85 = a79[0]
        a83 = a79[1]
        a87 = 0

        for a86 in range(32):
            a85 += int((((int(a83) << 4) ^ rshift(int(a83), 5)) + a83) ^ (a87 + a80[(a87 & 3)]))
            a85 = int(a85 | 0)
            a87 = int(a87) - int(1640531527)
            a83 += int((((int(a85) << 4) ^ rshift(int(a85), 5)) + a85) ^ (a87 + a80[(rshift(a87, 11) & 3)]))
            a83 = int(a83 | 0)
        return [a85, a83]

    def binarydigest(a55):
        a63 = [1633837924, 1650680933, 1667523942, 1684366951]
        a62 = [1633837924, 1650680933]
        a61 = a62
        a66 = [0, 0]
        a68 = [0, 0]
        a59 = bytes2blocks(digest_pad(str2bytes(a55)))
        a65 = 0
        a67 = len(a59)
        while a65 < a67:
            a66[0] = a59[a65]
            a65 += 1
            a66[1] = a59[a65]
            a65 += 1
            a68[0] = a59[a65]
            a65 += 1
            a68[1] = a59[a65]
            a65 += 1
            a62 = tea_code(xor_blocks(a66, a62), a63)
            a61 = tea_code(xor_blocks(a68, a61), a63)
            a64 = a62[0]
            a62[0] = a62[1]
            a62[1] = a61[0]
            a61[0] = a61[1]
            a61[1] = a64

        return [a62[0], a62[1], a61[0], a61[1]]

    def ascii2bytes(a99):
        a2b = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9, "K": 10, "L": 11, "M": 12, "N": 13, "O": 14, "P": 15, "Q": 16, "R": 17, "S": 18, "T": 19, "U": 20, "V": 21, "W": 22, "X": 23, "Y": 24, "Z": 25, "a": 26, "b": 27, "c": 28, "d": 29, "e": 30, "f": 31, "g": 32, "h": 33, "i": 34, "j": 35, "k": 36, "l": 37, "m": 38, "n": 39, "o": 40, "p": 41, "q": 42, "r": 43, "s": 44, "t": 45, "u": 46, "v": 47, "w": 48, "x": 49, "y": 50, "z": 51, "0": 52, "1": 53, "2": 54, "3": 55, "4": 56, "5": 57, "6": 58, "7": 59, "8": 60, "9": 61, "-": 62, "_": 63}
        a6 = -1
        a7 = len(a99)
        a9 = 0
        a8 = []

        while True:
            while True:
                a6 += 1
                if a6 >= a7:
                    return a8
                if a99[a6] in a2b.keys():
                    break
            a8.insert(a9, int(int(a2b[a99[a6]]) << 2))
            while True:
                a6 += 1
                if a6 >= a7:
                    return a8
                if a99[a6] in a2b.keys():
                    break
            a3 = a2b[a99[a6]]
            a8[a9] |= rshift(int(a3), 4)
            a9 += 1
            a3 = 15 & a3
            if (a3 == 0) and (a6 == (a7 - 1)):
                return a8
            a8.insert(a9, int(a3) << 4)
            while True:
                a6 += 1
                if a6 >= a7:
                    return a8
                if a99[a6] in a2b.keys():
                    break
            a3 = a2b[a99[a6]]
            a8[a9] |= rshift(int(a3), 2)
            a9 += 1
            a3 = 3 & a3
            if (a3 == 0) and (a6 == (a7 - 1)):
                return a8
            a8.insert(a9, int(a3) << 6)
            while True:
                a6 += 1
                if a6 >= a7:
                    return a8
                if a99[a6] in a2b.keys():
                    break
            a8[a9] |= a2b[a99[a6]]
            a9 += 1

        return a8

    def ascii2binary(a0):
        return bytes2blocks(ascii2bytes(a0))

    def tea_decode(a90, a91):
        a95 = a90[0]
        a96 = a90[1]
        a97 = int(-957401312)
        for a98 in range(32):
            a96 = int(a96) - ((((int(a95) << 4) ^ rshift(int(a95), 5)) + a95) ^ (a97 + a91[(rshift(int(a97), 11) & 3)]))
            a96 = int(a96 | 0)
            a97 = int(a97) + 1640531527
            a97 = int(a97 | 0)
            a95 = int(a95) - int((((int(a96) << 4) ^ rshift(int(a96), 5)) + a96) ^ (a97 + a91[(a97 & 3)]))
            a95 = int(a95 | 0)
        return [a95, a96]

    data_seed = re.sub("[012567]", replacer, data_seed)
    new_data_seed = binarydigest(data_seed)
    new_data_file = ascii2binary(data_file)
    a69 = 0
    a70 = len(new_data_file)
    a71 = [1633837924, 1650680933]
    a73 = [0, 0]
    a74 = []
    while a69 < a70:
        a73[0] = new_data_file[a69]
        a69 += 1
        a73[1] = new_data_file[a69]
        a69 += 1
        a72 = xor_blocks(a71, tea_decode(a73, new_data_seed))
        a74 += a72
        a71[0] = a73[0]
        a71[1] = a73[1]
    return re.sub("[012567]", replacer, bytes2str(unpad(blocks2bytes(a74))))


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
    else:
        return cipher.decrypt(data, iv)


class urlparser:
    def __init__(self):
        self.cm = common()
        self.pp = pageParser()
        self.hostMap = {
            "1fichier.com": self.pp.parser1FICHIERCOM,
            "222i8x.lol": self.pp.parserFILEMOON,
            "26efp.com": self.pp.parserJWPLAYER,
            "4yftwvrdz7.sbs": self.pp.parserJWPLAYER,
            "732eg54de642sa.sbs": self.pp.parserJWPLAYER,
            "96ar.com": self.pp.parserFILEMOON,
            # a
            "adblocktape.wiki": self.pp.parserSTREAMTAPE,
            "aiavh.com": self.pp.parserJWPLAYER,
            "aliez.me": self.pp.parserJWPLAYER,
            "all3do.com": self.pp.parserDOOD,
            "allocine.fr": self.pp.parserALLOCINEFR,
            "anime4low.sbs": self.pp.parserJWPLAYER,
            "ankrzkz.sbs": self.pp.parserJWPLAYER,
            "ankrznm.sbs": self.pp.parserJWPLAYER,
            "antiadtape.com": self.pp.parserSTREAMTAPE,
            "aparat.com": self.pp.parserAPARATCOM,
            "archive.org": self.pp.parserARCHIVEORG,
            "ashortl.ink": self.pp.parserVIDMOLYME,
            "asnwish.com": self.pp.parserJWPLAYER,
            "awish.pro": self.pp.parserJWPLAYER,
            # b
            "bbc.co.uk": self.pp.parserBBC,
            "bestwish.lol": self.pp.parserJWPLAYER,
            "bf0skv.org": self.pp.parserFILEMOON,
            "bgwp.cc": self.pp.parserJWPLAYER,
            "bigwarp.art": self.pp.parserJWPLAYER,
            "bigwarp.cc": self.pp.parserJWPLAYER,
            "bigwarp.io": self.pp.parserJWPLAYER,
            "bigwarp.pro": self.pp.parserJWPLAYER,
            "bitporno.com": self.pp.parserBITPORNOCOM,
            "browncrossing.net": self.pp.parserONLYSTREAMTV,
            "bullstream.xyz": self.pp.parserSTREAMEMBED,
            # c
            "c1z39.com": self.pp.parserFILEMOON,
            "casacinema.cc": self.pp.parserCASACINEMACC,
            "cda.pl": self.pp.parserCDA,
            "cdn1.site": self.pp.parserJWPLAYER,
            "cdn4.1vid1shar.space": self.pp.parserJWPLAYER,
            "cdnwish.com": self.pp.parserJWPLAYER,
            "chuckle-tube.com": self.pp.parserVOESX,
            "cloud.mail.ru": self.pp.parserCOUDMAILRU,
            "cloudcartel.net": self.pp.parserCLOUDCARTELNET,
            "cloudstream.us": self.pp.parserCLOUDSTREAMUS,
            "cloudvideo.tv": self.pp.parserCLOUDVIDEOTV,
            "coolrea.link": self.pp.parserSPORTSONLINETO,
            "csst.online": self.pp.parserSST,
            "cybervynx.com": self.pp.parserJWPLAYER,
            # d
            "d0000d.com": self.pp.parserDOOD,
            "d000d.com": self.pp.parserDOOD,
            "d0o0d.com": self.pp.parserDOOD,
            "d-s.io": self.pp.parserDOOD,
            "daddylive.club": self.pp.parserDADDYLIVE,
            "daddylive.me": self.pp.parserDADDYLIVE,
            "dailymotion.com": self.pp.parserDAILYMOTION,
            "dailyuploads.net": self.pp.parserUPLOAD2,
            "dancima.shop": self.pp.parserJWPLAYER,
            "dartstreams.de.cool": self.pp.parserONLYSTREAMTV,
            "davioad.com": self.pp.parserJWPLAYER,
            "dhcplay.com": self.pp.parserJWPLAYER,
            "dhtpre.com": self.pp.parserJWPLAYER,
            "dingtezuni.com": self.pp.parserJWPLAYER,
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
            "dropload.tv": self.pp.parserJWPLAYER,
            "ds2play.com": self.pp.parserDOOD,
            "ds2video.com": self.pp.parserDOOD,
            "dsvplay.com": self.pp.parserDOOD,
            "dumbalag.com": self.pp.parserJWPLAYER,
            "dwish.pro": self.pp.parserJWPLAYER,
            # e
            "easyvideo.me": self.pp.parserEASYVIDEOME,
            "eb8gfmjn71.sbs": self.pp.parserJWPLAYER,
            "ebd.cda.pl": self.pp.parserCDA,
            "edbrdl7pab.sbs": self.pp.parserJWPLAYER,
            "edwardarriveoften.com": self.pp.parserMATCHATONLINE,
            "egtpgrvh.sbs": self.pp.parserJWPLAYER,
            "embedv.net": self.pp.parserVIDGUARDTO,
            "embedwish.com": self.pp.parserJWPLAYER,
            "emturbovid.com": self.pp.parserJWPLAYER,
            "en.embedz.net": self.pp.parserJWPLAYER,
            # f
            "f16px.com": self.pp.parserf16px,
            "f51rm.com": self.pp.parserFILEMOON,
            "facebook.com": self.pp.parserFACEBOOK,
            "fastshare.cz": self.pp.parserFASTSHARECZ,
            "fdewsdc.sbs": self.pp.parserJWPLAYER,
            "fembed.com": self.pp.parserXSTREAMCDNCOM,
            "filecloud.io": self.pp.parserFILECLOUDIO,
            "filefactory.com": self.pp.parserFILEFACTORYCOM,
            "filelions.live": self.pp.parserONLYSTREAMTV,
            "filelions.online": self.pp.parserONLYSTREAMTV,
            "filelions.site": self.pp.parserONLYSTREAMTV,
            "filelions.to": self.pp.parserONLYSTREAMTV,
            "filemoon.art": self.pp.parserFILEMOON,
            "filemoon.eu": self.pp.parserFILEMOON,
            "filemoon.in": self.pp.parserFILEMOON,
            "filemoon.link": self.pp.parserFILEMOON,
            "filemoon.nl": self.pp.parserFILEMOON,
            "filemoon.sx": self.pp.parserFILEMOON,
            "filemoon.to": self.pp.parserFILEMOON,
            "filemoon.wf": self.pp.parserFILEMOON,
            "fileone.tv": self.pp.parserFILEONETV,
            "filez.tv": self.pp.parserFILEZTV,
            "firedrive.com": self.pp.parserFIREDRIVE,
            "flaswish.com": self.pp.parserJWPLAYER,
            "flix555.com": self.pp.parserFLIX555COM,
            "forafile.com": self.pp.parserJWPLAYER,
            "foothubhd.live": self.pp.parserSHOWSPORTXYZ,
            "forstreams.com": self.pp.parserVIUCLIPS,
            "fsdcmo.sbs": self.pp.parserJWPLAYER,
            "fslinks.org": self.pp.parserVIDGUARDTO,
            "fsst.online": self.pp.parserSST,
            "fviplions.com": self.pp.parserONLYSTREAMTV,
            # g
            "gametrailers.com": self.pp.parserGAMETRAILERS,
            "gamovideo.com": self.pp.parserGAMOVIDEOCOM,
            "ghbrisk.com": self.pp.parserJWPLAYER,
            "gloria.tv": self.pp.parserGLORIATV,
            "goodstream.one": self.pp.parserJWPLAYER,
            "goodstream.uno": self.pp.parserJWPLAYER,
            "goofy-banana.com": self.pp.parserVOESX,
            "google.com": self.pp.parserGOOGLE,
            "govid.me": self.pp.parserGOVIDME,
            "gradehgplus.com": self.pp.parserJWPLAYER,
            "gsfqzmqu.sbs": self.pp.parserJWPLAYER,
            "guccihide.com": self.pp.parserONLYSTREAMTV,
            "guerrillaforfight.com": self.pp.parserONLYSTREAMTV,
            # h
            "harpy.tv": self.pp.parserHARPYTV,
            "haxhits.com": self.pp.parserHAXHITSCOM,
            "haxloppd.com": self.pp.parserJWPLAYER,
            "hdbestvd.online": self.pp.parserJWPLAYER,
            "hdfilmstreaming.com": self.pp.parserHDFILMSTREAMING,
            "hexload.com": self.pp.parserHEXLOAD,
            "hexupload.net": self.pp.parserHEXLOAD,
            "hglink.to": self.pp.parserJWPLAYER,
            "hgplaycdn.com": self.pp.parserJWPLAYER,
            "hlsflast.com": self.pp.parserJWPLAYER,
            "hlsplayer.org": self.pp.parserHLSPLAYER,
            "hlswish.com": self.pp.parserJWPLAYER,
            "hydrax.net": self.pp.parserHYDRAXNET,
            # i
            "interia.tv": self.pp.parserINTERIATV,
            "iplayerhls.com": self.pp.parserJWPLAYER,
            # j
            "javsw.me": self.pp.parserJWPLAYER,
            "jodwish.com": self.pp.parserJWPLAYER,
            "johntryopen.com": self.pp.parserMATCHATONLINE,
            "junkyvideo.com": self.pp.parserJUNKYVIDEO,
            "justupload.io": self.pp.parserJUSTUPLOAD,
            # k
            "kabab.lima-city.de": self.pp.parserKABABLIMA,
            "kinoger.be": self.pp.parserJWPLAYER,
            "kinoger.p2pplay.pro": self.pp.parserSBS,
            "kinoger.pw": self.pp.parserVIDGUARDTO,
            "kinoger.re": self.pp.parserSBS,
            "kinoger.ru": self.pp.parserVOESX,
            "krakenfiles.com": self.pp.parserKRAKENFILESCOM,
            "kravaxxa.com": self.pp.parserJWPLAYER,
            # l
            "l1afav.net": self.pp.parserFILEMOON,
            "listeamed.net": self.pp.parserVIDGUARDTO,
            "live-stream.tv": self.pp.parserLIVESTRAMTV,
            "liveonlinetv247.info": self.pp.parserLIVEONLINETV247,
            "liveonlinetv247.net": self.pp.parserLIVEONLINE247,
            "liveonscore.to": self.pp.parserLIVEONSCORETV,
            "louishide.com": self.pp.parserONLYSTREAMTV,
            "lulu.st": self.pp.parserJWPLAYER,
            "lulustream.com": self.pp.parserJWPLAYER,
            "luluvid.com": self.pp.parserJWPLAYER,
            "luluvdo.com": self.pp.parserJWPLAYER,
            "luluvdoo.com": self.pp.parserJWPLAYER,
            "lylxan.com": self.pp.parserONLYSTREAMTV,
            # m
            "matchat.online": self.pp.parserMATCHATONLINE,
            "mcloud.to": self.pp.parserMYCLOUDTO,
            "md3b0j6hj.com": self.pp.parserJWPLAYER,
            "mdbekjwqa.pw": self.pp.parserJWPLAYER,
            "mdfx9dc8n.net": self.pp.parserJWPLAYER,
            "mdy48tn97.com": self.pp.parserJWPLAYER,
            "mdzsmutpcvykb.net": self.pp.parserJWPLAYER,
            "mediafire.com": self.pp.parserMEDIAFIRECOM,
            "mediasetplay.mediaset.it": self.pp.parserMEDIASET,
            "miplayer.net": self.pp.parserMIPLAYERNET,
            "mivalyo.com": self.pp.parserJWPLAYER,
            "mixdrp.co": self.pp.parserJWPLAYER,
            "mixdrp.to": self.pp.parserJWPLAYER,
            "mixdroop.co": self.pp.parserJWPLAYER,
            "mixdrop21.net": self.pp.parserJWPLAYER,
            "mixdrop23.net": self.pp.parserJWPLAYER,
            "mixdrop.ag": self.pp.parserJWPLAYER,
            "mixdrop.bz": self.pp.parserJWPLAYER,
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
            "mixdropjmk.pw": self.pp.parserJWPLAYER,
            "moflix-stream.click": self.pp.parserJWPLAYER,
            "moflix-stream.day": self.pp.parserVIDGUARDTO,
            "moflix-stream.fans": self.pp.parserJWPLAYER,
            "moflix.rpmplay.xyz": self.pp.parserSBS,
            "moflix.upns.xyz": self.pp.parserSBS,
            "movearnpre.com": self.pp.parserJWPLAYER,
            "movreel.com": self.pp.parserMOVRELLCOM,
            "mp4player.site": self.pp.parserSTREAMEMBED,
            "mp4upload.com": self.pp.parserONLYSTREAMTV,
            "mwish.pro": self.pp.parserJWPLAYER,
            "mxdrop.to": self.pp.parserJWPLAYER,
            "mycloud.to": self.pp.parserMYCLOUDTO,
            "mysportzfy.com": self.pp.parserJWPLAYER,
            # n
            "nadaje.com": self.pp.parserNADAJECOM,
            "nba-streams.online": self.pp.parserSHOWSPORTXYZ,
            "nflinsider.net": self.pp.parserVIDEOHOUSE,
            "ninjastream.to": self.pp.parserNINJASTREAMTO,
            "nonlimit.pl": self.pp.parserIITV,
            "nova.upn.one": self.pp.parserSBS,
            "novamov.com": self.pp.parserNOVAMOV,
            "nowvideo.ch": self.pp.parserNOWVIDEOCH,
            "nxload.com": self.pp.parserNXLOADCOM,
            # o
            "obeywish.com": self.pp.parserJWPLAYER,
            "odysee.com": self.pp.parserODYSEECOM,
            "ok.ru": self.pp.parserOKRU,
            "onet.pl": self.pp.parserONETTV,
            "onet.tv": self.pp.parserONETTV,
            "ovva.tv": self.pp.parserOVVATV,
            # p
            "partners.nettvplus.com": self.pp.parserNETTVPLUSCOM,
            "peytonepre.com": self.pp.parserONLYSTREAMTV,
            "planetfastidious.net": self.pp.parserONLYSTREAMTV,
            "playbb.me": self.pp.parserEASYVIDEOME,
            "player.upn.one": self.pp.parserSBS,
            "playerwish.com": self.pp.parserONLYSTREAMTV,
            "playpanda.net": self.pp.parserPLAYPANDANET,
            "playtube.ws": self.pp.parserONLYSTREAMTV,
            "polsatsport.pl": self.pp.parserPOLSATSPORTPL,
            "poophq.com": self.pp.parserVEEV,
            "posiedze.pl": self.pp.parserPOSIEDZEPL,
            "powvideo.cc": self.pp.parserPOWVIDEONET,
            "powvideo.net": self.pp.parserPOWVIDEONET,
            "pqham.com": self.pp.parserJWPLAYER,
            "primevideos.net": self.pp.parserPRIMEVIDEOS,
            "promptfile.com": self.pp.parserPROMPTFILE,
            "publicvideohost.org": self.pp.parserPUBLICVIDEOHOST,
            "putlive.in": self.pp.parserPUTLIVEIN,
            "putlocker.com": self.pp.parserFIREDRIVE,
            "pxstream.tv": self.pp.parserPXSTREAMTV,
            # q
            "qfer.net": self.pp.parserQFER,
            # r
            "room905.com": self.pp.parserONLYSTREAMTV,
            "rubystm.com": self.pp.parserJWPLAYER,
            "rumble.com": self.pp.parserRUMBLECOM,
            "ryderjet.com": self.pp.parserONLYSTREAMTV,
            # s
            "s3taku.pro": self.pp.parserJWPLAYER,
            "savefiles.com": self.pp.parserJWPLAYER,
            "scloud.online": self.pp.parserSTREAMTAPE,
            "seraphinapl.com": self.pp.parserJWPLAYER,
            "sendvid.com": self.pp.parserSENDVIDCOM,
            "sfastwish.com": self.pp.parserJWPLAYER,
            "shared.sx": self.pp.parserSHAREDSX,
            "sharerepo.com": self.pp.parserSHAREREPOCOM,
            "sharevideo.pl": self.pp.parserSHAREVIDEO,
            "shavetape.cash": self.pp.parserSTREAMTAPE,
            "shiid4u.upn.one": self.pp.parserSBS,
            "showsport.xyz": self.pp.parserSHOWSPORTXYZ,
            "slmaxed.com": self.pp.parserSTREAMLARE,
            "sltube.org": self.pp.parserSTREAMLARE,
            "slwatch.cog": self.pp.parserSTREAMLARE,
            "smoothpre.com": self.pp.parserJWPLAYER,
            "sonline.pro": self.pp.parserXSTREAMCDNCOM,
            "sostart.org": self.pp.parserSOSTARTORG,
            "soundcloud.com": self.pp.parserSOUNDCLOUDCOM,
            "sportsonline.si": self.pp.parserSPORTSONLINETO,
            "sportsonline.to": self.pp.parserSPORTSONLINETO,
            "sportstream365.com": self.pp.parserSPORTSTREAM365,
            "sprocked.com": self.pp.parserSPROCKED,
            "spruto.tv": self.pp.parserSPRUTOTV,
            "stape.fun": self.pp.parserSTREAMTAPE,
            "stbhg.click": self.pp.parserJWPLAYER,
            "strcloud.club": self.pp.parserSTREAMTAPE,
            "strcloud.link": self.pp.parserSTREAMTAPE,
            "stream.moe": self.pp.parserSTREAMMOE,
            "streamable.com": self.pp.parserSTREAMABLECOM,
            "streamadblocker.xyz": self.pp.parserSTREAMTAPE,
            "streamadblockplus.com": self.pp.parserSTREAMTAPE,
            "streamatus.tk": self.pp.parserVIUCLIPS,
            "streambolt.tv": self.pp.parserJWPLAYER,
            "streamhide.to": self.pp.parserONLYSTREAMTV,
            "streamhihi.com": self.pp.parserJWPLAYER,
            "streamhls.to": self.pp.parserJWPLAYER,
            "streamhub.gg": self.pp.parserONLYSTREAMTV,
            "streamhub.link": self.pp.parserONLYSTREAMTV,
            "streamhub.to": self.pp.parserONLYSTREAMTV,
            "streamja.com": self.pp.parserSTREAMJACOM,
            "streamlare.com": self.pp.parserSTREAMLARE,
            "streamnoads.com": self.pp.parserSTREAMTAPE,
            "streamo.tv": self.pp.parserIITV,
            "streamruby.com": self.pp.parserJWPLAYER,
            "streamsilk.com": self.pp.parserSTREAMSILKCOM,
            "streamta.pe": self.pp.parserSTREAMTAPE,
            "streamta.site": self.pp.parserSTREAMTAPE,
            "streamtape.cc": self.pp.parserSTREAMTAPE,
            "streamtape.com": self.pp.parserSTREAMTAPE,
            "streamtape.net": self.pp.parserSTREAMTAPE,
            "streamtape.site": self.pp.parserSTREAMTAPE,
            "streamtape.to": self.pp.parserSTREAMTAPE,
            "streamtape.xyz": self.pp.parserSTREAMTAPE,
            "streamtp3.com": self.pp.parserONLYSTREAMTV,
            "streamtp4.com": self.pp.parserONLYSTREAMTV,
            "streamup.ws": self.pp.parserSTREAMUP,
            "streamvid.net": self.pp.parserONLYSTREAMTV,
            "streamvid.su": self.pp.parserJWPLAYER,
            "streamwire.net": self.pp.parserONLYSTREAMTV,
            "streamwish.fun": self.pp.parserJWPLAYER,
            "streamwish.to": self.pp.parserJWPLAYER,
            "strmup.cc": self.pp.parserSTREAMUP,
            "strmup.to": self.pp.parserSTREAMUP,
            "strtape.cloud": self.pp.parserSTREAMTAPE,
            "strtpe.link": self.pp.parserSTREAMTAPE,
            "strwish.com": self.pp.parserONLYSTREAMTV,
            "superfilm.pl": self.pp.parserSUPERFILMPL,
            "supervideo.cc": self.pp.parserJWPLAYER,
            "supervideo.tv": self.pp.parserJWPLAYER,
            "svetacdn.in": self.pp.parserSVETACDNIN,
            "swdyu.com": self.pp.parserJWPLAYER,
            "swhoi.com": self.pp.parserJWPLAYER,
            "swiftplayers.com": self.pp.parserJWPLAYER,
            "swishsrv.com": self.pp.parserJWPLAYER,
            # t
            "tapeadsenjoyer.com": self.pp.parserSTREAMTAPE,
            "tapeadvertisement.com": self.pp.parserSTREAMTAPE,
            "tapeblocker.com": self.pp.parserSTREAMTAPE,
            "tapewithadblock.org": self.pp.parserSTREAMTAPE,
            "telerium.tv": self.pp.parserTELERIUMTV,
            "thevideobee.to": self.pp.parserTHEVIDEOBEETO,
            "tiny.cc": self.pp.parserTINYCC,
            "toclipit.com": self.pp.parserVIUCLIPS,
            "trgsfjll.sbs": self.pp.parserJWPLAYER,
            "tunein.com": self.pp.parserTUNEINCOM,
            "tunestream.net": self.pp.parserONLYSTREAMTV,
            "turboviplay.com": self.pp.parserJWPLAYER,
            "tusfiles.com": self.pp.parserUSERSCLOUDCOM,
            "tusfiles.net": self.pp.parserUSERSCLOUDCOM,
            "tvp.pl": self.pp.parserTVP,
            "twitch.tv": self.pp.parserTWITCHTV,
            # u
            "uefa.com": self.pp.parserUEFACOM,
            "ufckhabib.com": self.pp.parserSPORTSONLINETO,
            "ultimatedown.com": self.pp.parserULTIMATEDOWN,
            "ultrastream.online": self.pp.parserSBS,
            "unbiasedsenseevent.com": self.pp.parserONLYSTREAMTV,
            "up4stream.com": self.pp.parserJWPLAYER,
            "upclips.online": self.pp.parserVIUCLIPS,
            "updown.icu": self.pp.parserJWPLAYER,
            "upload.mn": self.pp.parserUPLOAD2,
            "uploaduj.net": self.pp.parserUPLOADUJNET,
            "ups2up.fun": self.pp.parserJWPLAYER,
            "upstream.to": self.pp.parserONLYSTREAMTV,
            "upvideo.cc": self.pp.parserONLYSTREAMTV,
            "upzone.cc": self.pp.parserUPZONECC,
            "uqload.cx": self.pp.parserJWPLAYER,
            "uqload.io": self.pp.parserJWPLAYER,
            "uqload.ws": self.pp.parserJWPLAYER,
            "uqloads.xyz": self.pp.parserJWPLAYER,
            "userload.co": self.pp.parserUSERLOADCO,
            "userscloud.com": self.pp.parserUSERSCLOUDCOM,
            "ustreamix.com": self.pp.parserUSTREAMIXCOM,
            # v
            "v6embed.xyz": self.pp.parserVIDGUARDTO,
            "vbn2.vdbtm.shop": self.pp.parserJWPLAYER,
            "vcstream.to": self.pp.parserVCSTREAMTO,
            "veehd.com": self.pp.parserVEEHDCOM,
            "veev.to": self.pp.parserVEEV,
            "vembed.net": self.pp.parserVIDGUARDTO,
            "veoh.com": self.pp.parserVEOHCOM,
            "veuclips.com": self.pp.parserVEUCLIPS,
            "veuclipstoday.tk": self.pp.parserVIUCLIPS,
            "vevo.com": self.pp.parserVEVO,
            "vgembed.com": self.pp.parserVIDGUARDTO,
            "vgfplay.com": self.pp.parserVIDGUARDTO,
            "vid-guard.com": self.pp.parserVIDGUARDTO,
            "vidbom.com": self.pp.parserVIDBOMCOM,
            "vidcloud.co": self.pp.parserVIDCLOUDCO,
            "vidcloud.icu": self.pp.parserVIDCLOUDICU,
            "vidcloud9.com": self.pp.parserVIDCLOUD9,
            "vide0.net": self.pp.parserDOOD,
            "vidply.com": self.pp.parserDOOD,
            "videa.hu": self.pp.parserVIDEA,
            "videakid.hu": self.pp.parserVIDEA,
            "video.tt": self.pp.parserVIDEOTT,
            "videohouse.me": self.pp.parserVIDEOHOUSE,
            "videostreamlet.net": self.pp.parserVIDEOSTREAMLETNET,
            "videowood.tv": self.pp.parserVIDEOWOODTV,
            "videzz.net": self.pp.parserVIDOZANET,
            "vidfile.net": self.pp.parserVIDFILENET,
            "vidflare.com": self.pp.parserVIDFLARECOM,
            "vidguard.to": self.pp.parserVIDGUARDTO,
            "vidhidefast.com": self.pp.parserJWPLAYER,
            "vidhidefun.com": self.pp.parserJWPLAYER,
            "vidhidehub.com": self.pp.parserJWPLAYER,
            "vidhidepro.com": self.pp.parserJWPLAYER,
            "vidia.tv": self.pp.parserONLYSTREAMTV,
            "vidload.co": self.pp.parserVIDLOADCO,
            "vidload.net": self.pp.parserVIDLOADNET,
            "vidmoly.me": self.pp.parserVIDMOLYME,
            "vidmoly.net": self.pp.parserVIDMOLYME,
            "vidmoly.to": self.pp.parserVIDMOLYME,
            "vidoo.tv": self.pp.parserONLYSTREAMTV,
            "vidoza.co": self.pp.parserVIDOZANET,
            "vidoza.net": self.pp.parserVIDOZANET,
            "vidoza.org": self.pp.parserVIDOZANET,
            "vidshare.space": self.pp.parserJWPLAYER,
            "vidshare.tv": self.pp.parserVIDSHARETV,
            "vidsrc.in": self.pp.parserVIDSRC,
            "vidsrc.net": self.pp.parserVIDSRC,
            "vidsrc.pm": self.pp.parserVIDSRC,
            "vidsrc.to": self.pp.parserVIDSRC,
            "vidsrc.xyz": self.pp.parserVIDSRC,
            "vidstodo.me": self.pp.parserVIDSTODOME,
            "vidstreamup.com": self.pp.parserVIUCLIPS,
            "vidtodo.com": self.pp.parserVIDSTODOME,
            "viduplayer.com": self.pp.parserVIDUPLAYERCOM,
            "vidzer.net": self.pp.parserVIDZER,
            "vidzy.org": self.pp.parserJWPLAYER,
            "vimeo.com": self.pp.parseVIMEOCOM,
            "vinovo.si": self.pp.parserVINOVO,
            "vinovo.to": self.pp.parserVINOVO,
            "viuclips.net": self.pp.parserVIUCLIPS,
            "vivo.sx": self.pp.parserVIVOSX,
            "vk.com": self.pp.parserVK,
            "vkprime.com": self.pp.parserONLYSTREAMTV,
            "vkvideo.ru": self.pp.parserVK,
            "voe.sx": self.pp.parserVOESX,
            "voodc.com": self.pp.parserVOODCCOM,
            "vsports.pt": self.pp.parserVSPORTSPT,
            "vtbe.to": self.pp.parserJWPLAYER,
            "vtube.network": self.pp.parserJWPLAYER,
            "vtube.to": self.pp.parserJWPLAYER,
            "vup.to": self.pp.parserONLYSTREAMTV,
            "vvide0.com": self.pp.parserDOOD,
            # w
            "wasuytm.store": self.pp.parserSBS,
            "watch.ezplayer.me": self.pp.parserSBS,
            "watch.gxplayer.xyz": self.pp.parserSTREAMEMBED,
            "watchadsontape.com": self.pp.parserSTREAMTAPE,
            "wavehd.com": self.pp.parserJWPLAYER,
            "weakstreams.com": self.pp.parserLIVEONSCORETV,
            "webcamera.mobi": self.pp.parserWEBCAMERAPL,
            "webcamera.pl": self.pp.parserWEBCAMERAPL,
            "wikisport.best": self.pp.parserWIKISPORTCLICK,
            "wikisport.click": self.pp.parserWIKISPORTCLICK,
            "wikisport.se": self.pp.parserWIKISPORTCLICK,
            "wishembed.pro": self.pp.parserJWPLAYER,
            "wishfast.top": self.pp.parserONLYSTREAMTV,
            "wishonly.site": self.pp.parserJWPLAYER,
            # x
            "xage.pl": self.pp.parserXAGEPL,
            "xcoic.com": self.pp.parserFILEMOON,
            "xcv2.goveed1.space": self.pp.parserJWPLAYER,
            "xstreamcdn.com": self.pp.parserXSTREAMCDNCOM,
            "xvideoshare.live": self.pp.parserONLYSTREAMTV,
            # y
            "yocast.tv": self.pp.parserYOCASTTV,
            "yodbox.com": self.pp.parserONLYSTREAMTV,
            "youdbox.com": self.pp.parserONLYSTREAMTV,
            "youtu.be": self.pp.parserYOUTUBE,
            "youtube-nocookie.com": self.pp.parserYOUTUBE,
            "youtube.com": self.pp.parserYOUTUBE,
            # z
            "zerocast.tv": self.pp.parserZEROCASTTV,
            "z1ekv717.fun": self.pp.parserJWPLAYER,
            "zstream.to": self.pp.parserZSTREAMTO,
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
        if 2 == len(tmp):
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
                if 1 == self.checkHostSupport(url):
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
                if 0 < len(ret):
                    host = self.getHostName(url)
                    urltab.append({"name": host, "url": ret})
            elif isinstance(ret, list) or isinstance(ret, tuple):
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

            if isinstance(nUrl, list) or isinstance(nUrl, tuple):
                if True is acceptsList:
                    return nUrl
                else:
                    if len(nUrl) > 0:
                        return nUrl[0]["url"]
                    else:
                        return False
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
        self.moonwalkParser = None
        self.vevoIE = None
        self.bbcIE = None
        self.sportStream365ServIP = None

        # config
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

    def getVevoIE(self):
        if self.vevoIE is None:
            try:
                from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.vevo import VevoIE

                self.vevoIE = VevoIE()
            except Exception:
                self.vevoIE = None
                printExc()
        return self.vevoIE

    def getBBCIE(self):
        if self.bbcIE is None:
            try:
                from Plugins.Extensions.IPTVPlayer.libs.youtube_dl.extractor.bbc import BBCCoUkIE

                self.bbcIE = BBCCoUkIE()
            except Exception:
                self.bbcIE = None
                printExc()
        return self.bbcIE

    def _getSources(self, data):
        printDBG(">>>>>>>>>> _getSources")
        urltab = []
        tmp = self.cm.ph.getDataBeetwenMarkers(data, "sources", "]")[1]
        if tmp != "":
            tmp = tmp.replace("\\", "")
            tmp = tmp.split("}")
            urlAttrName = "file"
            sp = ":"
        else:
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">", withMarkers=True)
            urlAttrName = "src"
            sp = "="
        printDBG(tmp)
        for item in tmp:
            url = self.cm.ph.getSearchGroups(item, r"""['"]?{0}['"]?\s*{1}\s*['"](https?://[^"^']+)['"]""".format(urlAttrName, sp))[0]
            if not self.cm.isValidUrl(url):
                continue
            name = self.cm.ph.getSearchGroups(item, r"""['"]?label['"]?\s*""" + sp + r"""\s*['"]?([^"^'^\,^\{]+)['"\,\{]""")[0]

            printDBG("---------------------------")
            printDBG("url:  " + url)
            printDBG("name: " + name)
            printDBG("+++++++++++++++++++++++++++")
            printDBG(item)

            if "flv" in item:
                if name == "":
                    name = "[FLV]"
                urltab.insert(0, {"name": name, "url": url})
            elif "mp4" in item:
                if name == "":
                    name = "[MP4]"
                urltab.append({"name": name, "url": url})

        return urltab

    def _findLinks(self, data, serverName="", linkMarker=r"""['"]?file['"]?[ ]*:[ ]*['"](http[^"^']+)['"][,}]""", m1="sources", m2="]", contain="", meta={}):
        urltab = []

        def _isSmil(data):
            return data.split("?")[0].endswith(".smil")

        def _getSmilUrl(url):
            if _isSmil(url):
                SWF_URL = ""
                # get stream link
                sts, data = self.cm.getPage(url)
                if sts:
                    base = self.cm.ph.getSearchGroups(data, 'base="([^"]+?)"')[0]
                    src = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
                    # if ':' in src:
                    #    src = src.split(':')[1]
                    if base.startswith("rtmp"):
                        return base + "/" + src + " swfUrl=%s pageUrl=%s" % (SWF_URL, url)
            return ""

        subTracks = []
        subData = self.cm.ph.getDataBeetwenReMarkers(data, re.compile(r"""['"]?tracks['"]?\s*?:"""), re.compile("]"), False)[1].split("}")
        for item in subData:
            kind = self.cm.ph.getSearchGroups(item, r"""['"]?kind['"]?\s*?:\s*?['"]([^"^']+?)['"]""")[0].lower()
            if kind != "captions":
                continue
            src = self.cm.ph.getSearchGroups(item, r"""['"]?file['"]?\s*?:\s*?['"](https?://[^"^']+?)['"]""")[0]
            if src == "":
                continue
            label = self.cm.ph.getSearchGroups(item, r"""label['"]?\s*?:\s*?['"]([^"^']+?)['"]""")[0]
            format = src.split("?", 1)[0].split(".")[-1].lower()
            if format not in ["srt", "vtt"]:
                continue
            if "empty" in src.lower():
                continue
            subTracks.append({"title": label, "url": src, "lang": "unk", "format": "srt"})

        srcData = self.cm.ph.getDataBeetwenMarkers(data, m1, m2, False)[1].split("},")
        for item in srcData:
            item += "},"
            if contain != "" and contain not in item:
                continue
            link = self.cm.ph.getSearchGroups(item, linkMarker)[0].replace(r"\/", "/")
            if "%3A%2F%2F" in link and "://" not in link:
                link = urllib_unquote(link)
            link = strwithmeta(link, meta)
            label = self.cm.ph.getSearchGroups(item, r"""['"]?label['"]?[ ]*:[ ]*['"]([^"^']+)['"]""")[0]
            if _isSmil(link):
                link = _getSmilUrl(link)
            if "://" in link:
                proto = "mp4"
                if link.startswith("rtmp"):
                    proto = "rtmp"
                if link.split("?")[0].endswith("m3u8"):
                    tmp = getDirectM3U8Playlist(link)
                    urltab.extend(tmp)
                else:
                    urltab.append({"name": "%s %s" % (proto + " " + serverName, label), "url": link})
                printDBG("_findLinks A")

        if 0 == len(urltab):
            printDBG("_findLinks B")
            link = self.cm.ph.getSearchGroups(data, linkMarker)[0].replace(r"\/", "/")
            link = strwithmeta(link, meta)
            if _isSmil(link):
                link = _getSmilUrl(link)
            if "://" in link:
                proto = "mp4"
                if link.startswith("rtmp"):
                    proto = "rtmp"
                urltab.append({"name": proto + " " + serverName, "url": link})

        if len(subTracks):
            for idx in range(len(urltab)):
                urltab[idx]["url"] = urlparser.decorateUrl(urltab[idx]["url"], {"external_sub_tracks": subTracks})

        return urltab

    def _parserUNIVERSAL_A(self, baseUrl, embedUrl, _findLinks, _preProcessing=None, httpHeader={}, params={}):
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0"}
        if "Referer" in strwithmeta(baseUrl).meta:
            HTTP_HEADER["Referer"] = strwithmeta(baseUrl).meta["Referer"]
        HTTP_HEADER.update(httpHeader)

        if "embed" not in baseUrl and "{0}" in embedUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{12})[/.-]")[0]
            url = embedUrl.format(video_id)
        else:
            url = baseUrl

        params = dict(params)
        params.update({"header": HTTP_HEADER})
        post_data = None

        if params.get("cfused", False):
            sts, data = self.getPageCF(url, params, post_data)
        else:
            sts, data = self.cm.getPage(url, params, post_data)
        if not sts:
            return False

        # printDBG(data)
        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        # data = re.sub("/\*[\s\S]*?\*/", "", data)

        errMarkers = ["File was deleted", "File Removed", "File Deleted.", "File Not Found"]
        for errMarker in errMarkers:
            if errMarker in data:
                SetIPTVPlayerLastHostError(errMarker)

        if _preProcessing is not None:
            data = _preProcessing(data)
        printDBG("Data: " + data)

        # get JS player script code from confirmation page
        vplayerData = ""
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "eval(" in item and "vplayer" in item:
                vplayerData = item

        if vplayerData != "":
            jscode = base64.b64decode("""ZnVuY3Rpb24gc3R1Yigpe31mdW5jdGlvbiBqd3BsYXllcigpe3JldHVybntzZXR1cDpmdW5jdGlvbigpe3ByaW50KEpTT04uc3RyaW5naWZ5KGFyZ3VtZW50c1swXSkpfSxvblRpbWU6c3R1YixvblBsYXk6c3R1YixvbkNvbXBsZXRlOnN0dWIsb25SZWFkeTpzdHViLGFkZEJ1dHRvbjpzdHVifX12YXIgZG9jdW1lbnQ9e30sd2luZG93PXRoaXM7""")
            jscode += vplayerData
            vplayerData = ""
            tmp = []
            ret = js_execute(jscode)
            if ret["sts"] and 0 == ret["code"] or "sources" in ret.get("data", ""):
                vplayerData = ret["data"].strip()

        if vplayerData != "":
            data += vplayerData
        else:
            mrk1 = ">eval("
            mrk2 = 'eval("'
            if mrk1 in data:
                m1 = mrk1
            elif mrk2 in data:
                m1 = mrk2
            else:
                m1 = "eval("
            tmpDataTab = self.cm.ph.getAllItemsBeetwenMarkers(data, m1, "</script>", False)
            for tmpData in tmpDataTab:
                data2 = tmpData
                tmpData = None
                # unpack and decode params from JS player script code
                tmpData = unpackJSPlayerParams(data2, VIDUPME_decryptPlayerParams)
                if tmpData == "":
                    tmpData = unpackJSPlayerParams(data2, VIDUPME_decryptPlayerParams, 0)

                if None is not tmpData:
                    data = data + tmpData

        printDBG("-*-*-*-*-*-*-*-*-*-*-*-*-*-\nData: %s\n-*-*-*-*-*-*-*-*-*-*-*-*-*-\n" % data)
        return _findLinks(data)

    def _parserUNIVERSAL_B(self, url, userAgent="Mozilla/5.0"):
        printDBG("_parserUNIVERSAL_B url[%s]" % url)

        domain = urlparser.getDomain(url)

        if self.cm.getPage(url, {"max_data_size": 0})[0]:
            url = self.cm.meta["url"]

        post_data = None

        if "/embed" not in url:
            sts, data = self.cm.getPage(url, {"header": {"User-Agent": userAgent}})
            if not sts:
                return False
            try:
                tmp = self.cm.ph.getDataBeetwenMarkers(data, '<form method="post" action="">', "</form>", False, False)[1]
                if tmp == "":
                    tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<form[^>]+?method="post"[^>]*?>', re.IGNORECASE), re.compile("</form>", re.IGNORECASE), False)[1]
                post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', tmp))
            except Exception:
                printExc()
            try:
                tmp = dict(re.findall(r'<button[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', tmp))
                post_data.update(tmp)
            except Exception:
                printExc()
        urltab = []
        params = {"header": {"User-Agent": userAgent, "Content-Type": "application/x-www-form-urlencoded", "Referer": url}}
        try:
            sts, data = self.cm.getPage(url, params, post_data)
            # printDBG(data)

            sts, tmp = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")
            if sts:
                tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<source", ">")
                printDBG(tmp)
                for item in tmp:
                    if "video/mp4" not in item and "video/x-flv" not in item:
                        continue
                    tType = self.cm.ph.getSearchGroups(item, """type=['"]([^'^"]+?)['"]""")[0].replace("video/", "")
                    tUrl = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?)['"]""")[0]
                    printDBG(tUrl)
                    if self.cm.isValidUrl(tUrl):
                        urltab.append({"name": "[%s] %s" % (tType, domain), "url": strwithmeta(tUrl, {"User-Agent": userAgent})})
                if len(urltab):
                    return urltab

            tmp = self.cm.ph.getDataBeetwenMarkers(data, "player.ready", "}")[1]
            url = self.cm.ph.getSearchGroups(tmp, r"""src['"\s]*?:\s['"]([^'^"]+?)['"]""")[0]
            if url.startswith("/"):
                url = domain + url[1:]
            if self.cm.isValidUrl(url) and url.split("?")[0].endswith(".mpd"):
                url = strwithmeta(url, {"User-Agent": params["header"]["User-Agent"]})
                urltab.extend(getMPDLinksWithMeta(url, False))

            filekey = re.search('flashvars.filekey="([^"]+?)";', data)
            if None is filekey:
                filekey = re.search("flashvars.filekey=([^;]+?);", data)
                filekey = re.search('var {0}="([^"]+?)";'.format(filekey.group(1)), data)
            filekey = filekey.group(1)
            file = re.search('flashvars.file="([^"]+?)";', data).group(1)
            domain = re.search('flashvars.domain="(http[^"]+?)"', data).group(1)

            url = domain + "/api/player.api.php?cid2=undefined&cid3=undefined&cid=undefined&user=undefined&pass=undefined&numOfErrors=0"
            url = url + "&key=" + urllib_quote_plus(filekey) + "&file=" + urllib_quote_plus(file)
            sts, data = self.cm.getPage(url)
            videoUrl = re.search("url=([^&]+?)&", data).group(1)

            errUrl = domain + "/api/player.api.php?errorCode=404&cid=1&file=%s&cid2=undefined&cid3=undefined&key=%s&numOfErrors=1&user=undefined&errorUrl=%s&pass=undefined" % (urllib_quote_plus(file), urllib_quote_plus(filekey), urllib_quote_plus(videoUrl))
            sts, data = self.cm.getPage(errUrl)
            errUrl = re.search("url=([^&]+?)&", data).group(1)
            if "" != errUrl:
                url = errUrl
            if "" != url:
                urltab.append({"name": "base", "url": strwithmeta(url, {"User-Agent": userAgent})})
        except Exception:
            printExc()
        return urltab

    def __parseJWPLAYER_A(self, baseUrl, serverName="", customLinksFinder=None, folowIframe=False, sleep_time=None):
        printDBG("pageParser.__parseJWPLAYER_A serverName[%s], baseUrl[%r]" % (serverName, baseUrl))

        linkList = []
        tries = 3
        while tries > 0:
            tries -= 1
            HTTP_HEADER = dict(self.HTTP_HEADER)
            HTTP_HEADER["Referer"] = baseUrl
            sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})

            if sts:
                HTTP_HEADER = dict(self.HTTP_HEADER)
                HTTP_HEADER["Referer"] = baseUrl
                url = self.cm.ph.getSearchGroups(data, 'iframe[ ]+src="(https?://[^"]*?embed[^"]+?)"')[0]
                if "" != url and (serverName in url or folowIframe):
                    sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
                else:
                    url = baseUrl

            if sts and "" != data:
                try:
                    sts, data2 = self.cm.ph.getDataBeetwenMarkers(data, 'method="POST"', "</Form>", False, False)
                    if sts:
                        post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data2))
                        try:
                            tmp = dict(re.findall(r'<button[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
                            post_data.update(tmp)
                        except Exception:
                            printExc()
                        if tries == 0:
                            try:
                                sleep_time = self.cm.ph.getSearchGroups(data2, ">([0-9]+?)</span> seconds<")[0]
                                if "" != sleep_time:
                                    GetIPTVSleep().Sleep(int(sleep_time))
                            except Exception:
                                if sleep_time is not None:
                                    GetIPTVSleep().Sleep(sleep_time)
                                printExc()
                        HTTP_HEADER["Referer"] = url
                        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER}, post_data)
                        if sts:
                            tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, ">eval(", "</script>")
                            for tmpItem in tmp:
                                try:
                                    tmpItem = unpackJSPlayerParams(tmpItem, VIDUPME_decryptPlayerParams)
                                    data = tmpItem + data
                                except Exception:
                                    printExc()
                    if None is not customLinksFinder:
                        linkList = customLinksFinder(data)
                    if 0 == len(linkList):
                        linkList = self._findLinks(data, serverName)
                except Exception:
                    printExc()
            if len(linkList) > 0:
                break
        return linkList

    def parserFIREDRIVE(self, url):
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        COOKIEFILE = self.COOKIE_PATH + "firedrive.cookie"
        url = url.replace("putlocker", "firedrive").replace("file", "embed")
        HTTP_HEADER["Referer"] = url

        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIEFILE})
        if not sts:
            return False
        if "Continue to " not in data:
            return False
        data = re.search('name="confirm" value="([^"]+?)"', data)
        if not data:
            return False
        data = {"confirm": data.group(1)}
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIEFILE}, data)
        if not sts:
            return False
        sts, link_data = CParsingHelper.getDataBeetwenMarkers(data, "function getVideoUrl(){", "return", False)
        if sts:
            match = re.search(r"post\('(http[^']+?)'", link_data)
        else:
            match = re.search("file: '(http[^']+?)'", data)
        if not match:
            match = re.search(r"file: loadURL\('(http[^']+?)'", data)

        if not match:
            return False
        url = match.group(1)
        printDBG("parserFIREDRIVE url[%s]" % url)
        return url

    def parserSPROCKED(self, url):
        url = url.replace("embed", "show")
        sts, link = self.cm.getPage(url)
        match = re.search("""url: ['"](.+?)['"],.*\nprovider""", link)
        if match:
            return match.group(1)
        else:
            return False

    def parserCDA(self, inUrl):
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
                if 429 == self.cm.meta["status_code"]:
                    GetIPTVSleep().Sleep(int(61))
                    sts, data = self.cm.getPage(url, defaultParams, post_data)
            return sts, data

        def _decorateUrl(inUrl, host, referer):
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
            inUrl = "http://ebd.cda.pl/620x368/" + vid

        # extract qualities
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

        if 0 == len(tmpUrls):
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
            if ret["sts"] and 0 == ret["code"]:
                return ret["data"].strip("\n")
            else:
                return ""

        for urlItem in tmpUrls:
            if urlItem["url"].startswith("/"):
                inUrl = "http://www.cda.pl/" + urlItem["url"]
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
            if 0 < len(data) and data[0].startswith("http"):
                __appendVideoUrl({"name": urlItem["name"] + " flv", "url": _decorateUrl(data[0], "cda.pl", urlItem["url"])})
            if 1 < len(data) and data[1].startswith("http"):
                __appendVideoUrl({"name": urlItem["name"] + " mp4", "url": _decorateUrl(data[1], "cda.pl", urlItem["url"])})
            if 0 == len(data):
                data = self.cm.ph.getDataBeetwenReMarkers(tmpData, re.compile(r"video:[\s]*{"), re.compile("}"), False)[1]
                data = self.cm.ph.getSearchGroups(data, r"'(http[^']+?(?:\.mp4|\.flv)[^']*?)'")[0]
                if "" != data:
                    type = " flv "
                    if ".mp4" in data:
                        type = " mp4 "
                    __appendVideoUrl({"name": urlItem["name"] + type, "url": _decorateUrl(data, "cda.pl", urlItem["url"])})

        self.jscode["data"] = ""
        return videoUrls[::-1]

    def parserNOVAMOV(self, url):
        return self._parserUNIVERSAL_B(url)

    def parserDAILYMOTION(self, baseUrl):  # Partly fix 18.10
        printDBG("parserDAILYMOTION %s" % baseUrl)
        COOKIE_FILE = self.COOKIE_PATH + "dailymotion.cookie"
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36"}
        httpParams = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": False, "load_cookie": False, "cookiefile": COOKIE_FILE}
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
                            tmpTab = getDirectM3U8Playlist(media_url, False, checkContent=True, sortWithMaxBitrate=99999999, cookieParams={"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True})
                            cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
                            for tmp in tmpTab:
                                hlsUrl = self.cm.ph.getSearchGroups(tmp["url"], r"""(https?://[^'^"]+?\.m3u8[^'^"]*?)#?""")[0]
                                redirectUrl = strwithmeta(hlsUrl, {"iptv_proto": "m3u8", "Cookie": cookieHeader, "User-Agent": HTTP_HEADER["User-Agent"]})
                                urlsTab.append({"name": "dailymotion.com: %sp hls" % (tmp.get("heigth", "0")), "url": redirectUrl, "quality": tmp.get("heigth", "0")})
                        else:
                            urlsTab.append({"name": quality, "url": media_url})
            except:
                printExc
        return urlsTab

    def parserVK(self, baseUrl):  # Partly work
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
            printDBG(data)
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
        if baseUrl.startswith("http://"):
            baseUrl = "https" + baseUrl[4:]
        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False
        login = config.plugins.iptvplayer.vkcom_login.value
        password = config.plugins.iptvplayer.vkcom_password.value
        try:
            vkcom_login = self.vkcom_login
            vkcom_pass = self.vkcom_pass
        except:
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
                sessionEx.waitForFinishOpen(MessageBox, _("To watch videos from http://vk.com/ you need to login.\nPlease fill your login and password in the IPTVPlayer configuration."), type=MessageBox.TYPE_INFO, timeout=10)
                return False
            elif not _doLogin(login, password):
                sessionEx = MainSessionWrapper()
                sessionEx.waitForFinishOpen(MessageBox, _('Login user "%s" to http://vk.com/ failed!\nPlease check your login data in the IPTVPlayer configuration.' % login), type=MessageBox.TYPE_INFO, timeout=10)
                return False
            else:
                sts, data = self.cm.getPage(baseUrl, params)
                if not sts:
                    return False
        movieUrls = []
        item = self.cm.ph.getSearchGroups(data, r"""['"]?cache([0-9]+?)['"]?[=:]['"]?(http[^"]+?\.mp4[^;^"^']*)[;"']""", 2)
        if "" != item[1]:
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
            if DEFAULT_FORMAT == movieUrls[idx]["name"]:
                defaultItem = movieUrls[idx]
                del movieUrls[idx]
                break
        movieUrls = movieUrls[::-1]
        if None is not defaultItem:
            movieUrls.insert(0, defaultItem)
        if None is not cacheItem:
            movieUrls.insert(0, cacheItem)
        return movieUrls

    def parserIITV(self, url):
        if "streamo" in url:
            match = re.compile("url: '(.+?)',").findall(self.cm.getPage(url)[1])

        if "nonlimit" in url:
            match = re.compile('url: "(.+?)",     provider:').findall(self.cm.getPage(url + ".html?i&e&m=iitv")[1])

        if len(match) > 0:
            linkVideo = match[0]
            printDBG("linkVideo " + linkVideo)
            return linkVideo
        else:
            SetIPTVPlayerLastHostError("Przepraszamy\nObecnie zbyt dużo osób ogląda film za pomocą\ndarmowego playera premium.\nSproboj ponownie za jakis czas")
        return False

    def parserQFER(self, url):
        match = re.compile('"PSST",url: "(.+?)"').findall(self.cm.getPage(url)[1])
        if len(match) > 0:
            linkVideo = match[0]
            printDBG("linkVideo " + linkVideo)
            return linkVideo
        else:
            return False

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
            # tmpTab = CSelOneLink(tmpTab, __getLinkQuality, int(height)).getSortedLinks()
            # dashTab = CSelOneLink(dashTab, __getLinkQuality, int(height)).getSortedLinks()

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

    def parserVIDBOMCOM(self, baseUrl):
        printDBG("parserVIDBOMCOM baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"with_metadata": True, "header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        cUrl = self.cm.getBaseUrl(data.meta["url"])
        domain = urlparser.getDomain(cUrl)

        jscode = [self.jscode["jwplayer"]]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "eval(" in item and "setup" in item:
                jscode.append(item)
        urltab = []
        try:
            jscode = "\n".join(jscode)
            ret = js_execute(jscode)
            tmp = json_loads(ret["data"])
            for item in tmp["sources"]:
                url = item["file"]
                type = item.get("type", "")
                if type == "":
                    type = url.split(".")[-1].split("?", 1)[0]
                type = type.lower()
                label = item["label"]
                if "mp4" not in type:
                    continue
                if url == "":
                    continue
                url = urlparser.decorateUrl(self.cm.getFullUrl(url, cUrl), {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
                urltab.append({"name": "{0} {1}".format(domain, label), "url": url})
        except Exception:
            printExc()
        if len(urltab) == 0:
            items = self.cm.ph.getDataBeetwenReMarkers(data, re.compile(r"""sources\s*[=:]\s*\["""), re.compile(r"""\]"""), False)[1].split("},")
            printDBG(items)
            domain = urlparser.getDomain(baseUrl)
            for item in items:
                item = item.replace(r"\/", "/")
                url = self.cm.ph.getSearchGroups(item, r"""(?:src|file)['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                if not url.lower().split("?", 1)[0].endswith(".mp4") or not self.cm.isValidUrl(url):
                    continue
                type = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                res = self.cm.ph.getSearchGroups(item, r"""res['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                if res == "":
                    res = self.cm.ph.getSearchGroups(item, r"""label['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                lang = self.cm.ph.getSearchGroups(item, r"""lang['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                url = urlparser.decorateUrl(self.cm.getFullUrl(url, cUrl), {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
                urltab.append({"name": domain + " {0} {1}".format(lang, res), "url": url})
        return urltab

    def parserINTERIATV(self, baseUrl):
        printDBG("parserINTERIATV baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"with_metadata": True, "header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        cUrl = self.cm.getBaseUrl(data.meta["url"])
        domain = urlparser.getDomain(cUrl)

        urltab = []
        embededLink = self.cm.ph.getSearchGroups(data, r"""['"]data\-url['"]\s*?\,\s*?['"]([^'^"]+?)['"]""")[0]
        if embededLink.startswith("//"):
            embededLink = "http:" + embededLink
        if self.cm.isValidUrl(embededLink):
            urlParams["header"]["Referer"] = baseUrl
            sts, tmp = self.cm.getPage(embededLink, urlParams)
            printDBG(tmp)
            if sts:
                embededLink = self.cm.ph.getSearchGroups(tmp, r"""['"]?src['"]?\s*?:\s*?['"]([^'^"]+?\.mp4(?:\?[^'^"]+?)?)['"]""")[0]
                if embededLink.startswith("//"):
                    embededLink = "http:" + embededLink
                if self.cm.isValidUrl(embededLink):
                    urltab.append({"name": "{0} {1}".format(domain, "external"), "url": embededLink})

        jscode = ["var window=this,document={};function jQuery(){return document}document.ready=function(n){n()};var element=function(n){this._name=n,this.setAttribute=function(){},this.attachTo=function(){}};document.getElementById=function(n){return new element(n)};var Inpl={Video:{}};Inpl.Video.createInstance=function(n){print(JSON.stringify(n))};"]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "Video.createInstance" in item:
                jscode.append(item)

        jscode = "\n".join(jscode)
        ret = js_execute(jscode)
        try:
            data = json_loads(ret["data"])["tracks"]
            for tmp in data:
                printDBG(tmp)
                for key in ["hi", "lo"]:
                    if not isinstance(tmp["src"][key], list):
                        tmp["src"][key] = [tmp["src"][key]]
                    for item in tmp["src"][key]:
                        if "mp4" not in item["type"].lower():
                            continue
                        if item["src"] == "":
                            continue
                        url = urlparser.decorateUrl(self.cm.getFullUrl(item["src"], cUrl), {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
                        urltab.append({"name": "{0} {1}".format(domain, key), "url": url})
        except Exception:
            printExc()
        return urltab

    def parserPOWVIDEONET(self, videoUrl):
        printDBG("parserPOWVIDEONET baseUrl[%r]" % videoUrl)
        HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36", "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
        sts, data = self.cm.getPage(videoUrl, {"header": HEADER})
        if not sts:
            return False

        baseUrl = urlparser.getDomain(self.cm.meta["url"], False)
        vidId = self.cm.ph.getSearchGroups(videoUrl, r"""[^-]*?\-([^-^.]+?)[-.]""")[0]
        if not vidId:
            vidId = videoUrl.rsplit("/")[-1].split(".", 1)[0]
        printDBG("parserPOWVIDEONET VID ID: %s" % vidId)
        referer = baseUrl + ("preview-%s-1920x882.html" % vidId)
        videoUrl = baseUrl + ("iframe-%s-1920x882.html" % vidId)
        HEADER["Referer"] = referer

        sts, data = self.cm.getPage(videoUrl, {"header": HEADER})
        if not sts:
            return False

        jscode = []
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "eval(" in item:
                jscode.append(item)
            elif "S?S" in item:
                jscode.append(self.cm.ph.getSearchGroups(item, "(var\\s_[^\n]+?)\n")[0])

        jwplayer = self.cm.ph.getSearchGroups(data, r"""<script[^>]+?src=['"]([^'^"]+?jwplayer\.js[^'^"]*?)['"]""")[0]
        if jwplayer != "" and not self.cm.isValidUrl(jwplayer):
            if jwplayer.startswith("//"):
                jwplayer = "https:" + jwplayer
            elif jwplayer.startswith("/"):
                jwplayer = baseUrl + jwplayer[1:]
            else:
                jwplayer = baseUrl + jwplayer

        sts, data = self.cm.getPage(jwplayer, {"header": HEADER})
        if not sts:
            return False

        hlsTab = []
        urltab = []
        jscode.insert(0, "location={};jQuery.cookie = function(){};function ga(){};document.getElementsByTagName = function(){return [document]}; document.createElement = function(){return document};document.parentNode = {insertBefore: function(){return document}};")
        jscode.insert(0, data[data.find("var S="):])
        jscode.insert(0, base64.b64decode("""aXB0dl9zb3VyY2VzPVtdO3ZhciBkb2N1bWVudD17fTt3aW5kb3c9dGhpcyx3aW5kb3cuYXRvYj1mdW5jdGlvbih0KXt0Lmxlbmd0aCU0PT09MyYmKHQrPSI9IiksdC5sZW5ndGglND09PTImJih0Kz0iPT0iKSx0PUR1a3RhcGUuZGVjKCJiYXNlNjQiLHQpLGRlY1RleHQ9IiI7Zm9yKHZhciBlPTA7ZTx0LmJ5dGVMZW5ndGg7ZSsrKWRlY1RleHQrPVN0cmluZy5mcm9tQ2hhckNvZGUodFtlXSk7cmV0dXJuIGRlY1RleHR9LGpRdWVyeT17fSxqUXVlcnkubWFwPUFycmF5LnByb3RvdHlwZS5tYXAsalF1ZXJ5Lm1hcD1mdW5jdGlvbigpe3JldHVybiBhcmd1bWVudHNbMF0ubWFwKGFyZ3VtZW50c1sxXSksaXB0dl9zb3VyY2VzLnB1c2goYXJndW1lbnRzWzBdKSxhcmd1bWVudHNbMF19LCQ9alF1ZXJ5LGlwdHZvYmo9e30saXB0dm9iai5zZXR1cD1mdW5jdGlvbigpe3JldHVybiBpcHR2b2JqfSxpcHR2b2JqLm9uPWZ1bmN0aW9uKCl7cmV0dXJuIGlwdHZvYmp9LGp3cGxheWVyPWZ1bmN0aW9uKCl7cmV0dXJuIGlwdHZvYmp9Ow=="""))
        jscode.append("print(JSON.stringify(iptv_sources[iptv_sources.length-1]));")
        ret = js_execute("\n".join(jscode))
        if ret["sts"] and 0 == ret["code"]:
            data = json_loads(ret["data"])
            for item in data:
                if "src" in item:
                    url = item["src"]
                else:
                    url = item["file"]
                url = strwithmeta(url, {"Referer": HEADER["Referer"], "User-Agent": HEADER["User-Agent"]})
                test = url.lower()
                if test.split("?", 1)[0].endswith(".mp4"):
                    urltab.append({"name": "mp4", "url": url})
                elif test.split("?", 1)[0].endswith(".m3u8"):
                    hlsTab.extend(getDirectM3U8Playlist(url, checkContent=True))
        urltab.extend(hlsTab)
        return urltab

    def parserMYCLOUDTO(self, baseUrl):
        printDBG("parserMYCLOUDTO baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        header = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36", "Referer": baseUrl.meta.get("Referer", baseUrl), "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}

        sts, data = self.cm.getPage(baseUrl, {"header": header})
        if not sts:
            return False

        data = data.replace("\\/", "/")

        url = self.cm.ph.getSearchGroups(data, r"""['"]((?:https?:)?//[^"^']+\.m3u8[^'^"]*?)['"]""")[0]
        if url.startswith("//"):
            url = "http:" + url

        url = strwithmeta(url, {"User-Agent": header["User-Agent"], "Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
        tab = getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)
        printDBG("parserMYCLOUDTO tab[%s]" % tab)
        return tab

    def parserVIDOZANET(self, baseUrl):
        printDBG("parserVIDOZANET baseUrl[%r]" % baseUrl)
        referer = strwithmeta(baseUrl).meta.get("Referer", "")
        baseUrl = strwithmeta(baseUrl, {"Referer": referer})
        domain = urlparser.getDomain(baseUrl)

        def _findLinks(data):
            tmp = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")[1]
            tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<source", ">", False)
            urltab = []
            for item in tmp:
                if "video/mp4" not in item and "video/x-flv" not in item:
                    continue
                tType = self.cm.ph.getSearchGroups(item, """type=['"]([^'^"]+?)['"]""")[0].replace("video/", "")
                tUrl = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?)['"]""")[0]
                printDBG(tUrl)
                if self.cm.isValidUrl(tUrl):
                    urltab.append({"name": "[%s] %s" % (tType, domain), "url": strwithmeta(tUrl)})
            return urltab

        return self._parserUNIVERSAL_A(baseUrl, "https://vidoza.net/embed-{0}.html", _findLinks)

    def parserSPRUTOTV(self, baseUrl):
        printDBG("parserSPRUTOTV baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        return self._findLinks(data, serverName="spruto.tv", linkMarker=r"""['"]?file['"]?[ ]*:[ ]*['"](http[^"^']+)['"][,}]""", m1="Uppod(", m2=")", contain=".mp4")

    def parserOVVATV(self, baseUrl):
        printDBG("parserOVVATV baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        data = self.cm.ph.getDataBeetwenMarkers(data, "ovva(", ")", False)[1].strip()[1:-1]
        data = json_loads(base64.b64decode(data))
        url = data["url"]

        sts, data = self.cm.getPage(url)
        if not sts:
            return False
        data = data.strip()
        if data.startswith("302="):
            url = data[4:]

        return getDirectM3U8Playlist(url, checkContent=True)[::-1]

    def parserSTREAMMOE(self, baseUrl):
        printDBG("parserSTREAMMOE baseUrl[%r]" % baseUrl)

        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        url = baseUrl
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False

        data = re.sub(r"""atob\(["']([^"^']+?)['"]\)""", lambda m: base64.b64decode(m.group(1)), data)
        printDBG(data)
        tab = self._findLinks(data, "stream.moe", linkMarker=r"""['"]?url['"]?[ ]*:[ ]*['"](http[^"^']+(?:\.mp4|\.flv)[^"^']*)['"][,}]""", m1="clip:")
        if len(tab) == 0:
            data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">", False, False)
            for item in data:
                if "video/mp4" in item:
                    url = self.cm.ph.getSearchGroups(item, """src=['"]([^"^']+?)['"]""")[0]
                    tab.append({"name": "stream.moe", "url": url})
            return tab

    def parserCOUDMAILRU(self, baseUrl):
        printDBG("parserCOUDMAILRU baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        weblink = self.cm.ph.getSearchGroups(data, r'"weblink"\s*:\s*"([^"]+?)"')[0]
        videoUrl = self.cm.ph.getSearchGroups(data, r'"weblink_video"\s*:[^\]]*?"url"\s*:\s*"(https?://[^"]+?)"')[0]
        videoUrl += "0p/%s.m3u8?double_encode=1" % (base64.b64encode(weblink))
        videoUrl = strwithmeta(videoUrl, {"User-Agent": HTTP_HEADER["User-Agent"]})
        return getDirectM3U8Playlist(videoUrl, checkContent=True)

    def parserVIDZER(self, baseUrl):
        printDBG("parserVIDZER baseUrl[%s]" % baseUrl)

        baseUrl = baseUrl.split("?")[0]

        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        defaultParams = {"header": HTTP_HEADER, "cookiefile": GetCookieDir("vidzernet.cookie"), "use_cookie": True, "save_cookie": True, "load_cookie": True}

        def getPage(url, params={}, post_data=None):
            sts, data = False, None
            sts, data = self.cm.getPage(url, defaultParams, post_data)
            if sts:
                imgUrl = self.cm.ph.getSearchGroups(data, '"([^"]+?captcha-master[^"]+?)"')[0]
                if imgUrl.startswith("/"):
                    imgUrl = "http://www.vidzer.net" + imgUrl
                if imgUrl.startswith("http://") or imgUrl.startswith("https://"):
                    sessionEx = MainSessionWrapper()
                    header = dict(HTTP_HEADER)
                    header["Accept"] = "image/png,image/*;q=0.8,*/*;q=0.5"
                    params = dict(defaultParams)
                    params.update({"maintype": "image", "subtypes": ["jpeg", "png"], "check_first_bytes": [b"\xFF\xD8", b"\xFF\xD9", b"\x89\x50\x4E\x47"], "header": header})
                    filePath = GetTmpDir(".iptvplayer_captcha.jpg")
                    # Accept=image/png,image/*;q=0.8,*/*;q=0.5
                    ret = self.cm.saveWebFile(filePath, imgUrl.replace("&amp;", "&"), params)
                    if not ret.get("sts"):
                        SetIPTVPlayerLastHostError(_('Fail to get "%s".') % imgUrl)
                        return False

                    from Plugins.Extensions.IPTVPlayer.components.iptvmultipleinputbox import IPTVMultipleInputBox

                    params = deepcopy(IPTVMultipleInputBox.DEF_PARAMS)
                    params["accep_label"] = _("Send")
                    params["title"] = _("Answer")
                    params["list"] = []
                    item = deepcopy(IPTVMultipleInputBox.DEF_INPUT_PARAMS)
                    item["label_size"] = (160, 75)
                    item["input_size"] = (300, 25)
                    item["icon_path"] = filePath
                    item["title"] = clean_html(CParsingHelper.getDataBeetwenMarkers(data, "<h1", "</h1>")[1]).strip()
                    item["input"]["text"] = ""
                    params["list"].append(item)

                    ret = 0
                    retArg = sessionEx.waitForFinishOpen(IPTVMultipleInputBox, params)
                    printDBG(retArg)
                    if retArg and len(retArg) and retArg[0]:
                        printDBG(retArg[0])
                        sts, data = self.cm.getPage(url, defaultParams, {"captcha": retArg[0][0]})
                        return sts, data
                    else:
                        SetIPTVPlayerLastHostError(_("Wrong answer."))
                    return False, None
            return sts, data

        sts, data = getPage(baseUrl)
        if not sts:
            return False
        url = self.cm.ph.getSearchGroups(data, '<iframe src="(http[^"]+?)"')[0]
        if url != "":
            sts, data = getPage(url)
            if not sts:
                return False
        data = CParsingHelper.getDataBeetwenMarkers(data, '<div id="playerVidzer">', "</a>", False)[1]
        match = re.search('href="(http[^"]+?)"', data)
        if match:
            url = urllib_unquote(match.group(1))
            return url

        r = re.search('value="(.+?)" name="fuck_you"', data)
        r2 = re.search('name="confirm" type="submit" value="(.+?)"', data)
        r3 = re.search('<a href="/file/([^"]+?)" target', data)
        if r:
            printDBG("r_1[%s]" % r.group(1))
            printDBG("r_2[%s]" % r2.group(1))
            data = "http://www.vidzer.net/e/" + r3.group(1) + "?w=631&h=425"
            postdata = {"confirm": r2.group(1), "fuck_you": r.group(1)}
            sts, data = getPage(data, {}, postdata)
            match = re.search("url: '([^']+?)'", data)
            if match:
                url = match.group(1)  # + '|Referer=http://www.vidzer.net/media/flowplayer/flowplayer.commercial-3.2.18.swf'
                return url
            else:
                return False
        else:
            return False

    def parserNOWVIDEOCH(self, url):
        printDBG("parserNOWVIDEOCH url[%s]" % url)
        return self._parserUNIVERSAL_B(url)

    def parserFILEONETV(self, baseUrl):
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

    def parserUSERSCLOUDCOM(self, baseUrl):
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
        # printDBG(data)
        # get direct link to file from params
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

    def parserVIDEOTT(self, url):
        printDBG("parserVIDEOTT url[%r]" % url)
        """
        based on https://github.com/rg3/youtube-dl/blob/master/youtube_dl/extractor/videott.py
        example video: http://www.video.tt/video/HRKwm3EhI
        """
        linkList = []
        try:
            mobj = re.match(r"http://(?:www\.)?video\.tt/(?:video/|watch_video\.php\?v=|embed/)(?P<id>[\da-zA-Z]{9})", url)
            video_id = mobj.group("id")
        except Exception:
            printExc()
            return linkList
        url = "http://www.video.tt/player_control/settings.php?v=%s" % video_id
        sts, data = self.cm.getPage(url)
        if sts:
            try:
                data = json_loads(data)["settings"]
                linkList = [
                    {
                        "url": base64.b64decode(res["u"]),
                        "name": res["l"],
                    }
                    for res in data["res"]
                    if res["u"]
                ]
            except Exception:
                printExc()
        return linkList

    def parserSTREAMABLECOM(self, baseUrl):
        printDBG("parserSTREAMABLECOM baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        videoUrl = self.cm.ph.getSearchGroups(data, """<source[^>]+?src=['"]([^'^"]+?)['"][^>]+?video/mp4""")[0]
        if videoUrl == "":
            tmp = re.compile(r"""sourceTag\.src\s*?=\s*?['"]([^'^"]+?)['"]""").findall(data)
            for item in tmp:
                if "mobile" not in item:
                    videoUrl = item
                    break
            if videoUrl == "" and len(tmp):
                videoUrl = tmp[-1]
        if videoUrl == "":
            videoUrl = self.cm.ph.getSearchGroups(data, """<video[^>]+?src=['"]([^'^"]+?)['"]""")[0]
            if videoUrl.split("?", 1)[0].split(".")[-1].lower() != "mp4":
                videoUrl = ""

        if videoUrl.startswith("//"):
            videoUrl = "https:" + videoUrl
        if self.cm.isValidUrl(videoUrl):
            return videoUrl.replace("&amp;", "&")
        msg = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "content"), ("</div", ">"))[1])
        SetIPTVPlayerLastHostError(msg)
        printDBG("++++++++++++++++++++++++++++++++++++++++++++++++++++++ " + msg)
        return False

    def parserMATCHATONLINE(self, baseUrl):
        printDBG("parserMATCHATONLINE baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        subTracksData = self.cm.ph.getAllItemsBeetwenMarkers(data, "<track ", ">", False, False)
        subTracks = []
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

        hlsUrl = self.cm.ph.getSearchGroups(data, r"""['"]?hls['"]?\s*?:\s*?['"]([^'^"]+?)['"]""")[0]
        if hlsUrl.startswith("//"):
            hlsUrl = "http:" + hlsUrl
        if self.cm.isValidUrl(hlsUrl):
            params = {"iptv_proto": "m3u8", "Referer": baseUrl, "Origin": urlparser.getDomain(baseUrl, False)}
            params["external_sub_tracks"] = subTracks
            hlsUrl = urlparser.decorateUrl(hlsUrl, params)
            return getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
        return False

    def parserPLAYPANDANET(self, baseUrl):
        printDBG("parserPLAYPANDANET baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl.replace("&amp;", "&"))
        if not sts:
            return False
        videoUrl = self.cm.ph.getSearchGroups(data, r"""_url\s*=\s*['"]([^'^"]+?)['"]""")[0]
        if videoUrl.startswith("//"):
            videoUrl = "http:" + videoUrl
        videoUrl = urllib_unquote(videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserAPARATCOM(self, baseUrl):
        printDBG("parserAPARATCOM baseUrl[%r]" % baseUrl)
        httpParams = {"header": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36", "Accept": "*/*", "Accept-Encoding": "gzip", "Referer": baseUrl.meta.get("Referer", baseUrl)}}

        urlsTab = []

        if "/videohash/" not in baseUrl and "/showvideo/" not in baseUrl:
            sts, data = self.cm.getPage(baseUrl, httpParams)
            if not sts:
                return False

            cUrl = self.cm.meta["url"]
            baseUrl = self.cm.getFullUrl(ph.search(data, """['"]([^'^"]+?/videohash/[^'^"]+?)['"]""")[0], cUrl)
            if not baseUrl:
                baseUrl = self.cm.getFullUrl(ph.search(data, """['"]([^'^"]+?/showvideo/[^'^"]+?)['"]""")[0], cUrl)

        sts, data = self.cm.getPage(baseUrl, httpParams)

        if sts:
            # printDBG("-----------------------")
            # printDBG(data)
            # printDBG("-----------------------")

            srcJson = re.findall(r"sources\s?:\s?\[(.*?)\]", data, re.S)
            if not srcJson:
                srcJson = re.findall('multiSRC"?\\s?:\\s?\\[\\[(.*?)\\]\\]', data, re.S)
                if srcJson:
                    sources = re.findall('(\\{"src":.*?\\})', srcJson[0])
                    if sources:
                        srcJson = [",".join(sources)]

            if srcJson:
                srcJson = srcJson[0]
                sources = json_loads("[" + srcJson + "]")
                printDBG(str(sources))

                for s in sources:
                    u = s.get("src", "")
                    if self.cm.isValidUrl(u):
                        u = urlparser.decorateUrl(u, {"Referer": baseUrl})
                        label = s.get("label", "")
                        srcType = s.get("type", "")
                    if "m3u" in u or "hls" in srcType or "x-mpeg" in srcType:
                        params = getDirectM3U8Playlist(u, checkExt=True, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999)
                        printDBG(str(params))
                        urlsTab.extend(params)
                    else:
                        params = {"name": label, "url": u}
                        printDBG(str(params))
                        urlsTab.append(params)

        return urlsTab

    def parserSTREAMJACOM(self, baseUrl):
        printDBG("parserSTREAMJACOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        domain = self.cm.getBaseUrl(cUrl, True)
        SetIPTVPlayerLastHostError(ph.clean_html(ph.find(data, ("<div", "</div>", "video has"))[1]))
        urltab = []
        data = ph.find(data, ("<video", ">"), "</video>", flags=ph.I)[1]
        data = ph.findall(data, "<source", ">", flags=ph.I)
        for item in data:
            type = ph.getattr(item, "type", flags=ph.I).lower()
            if "video/" not in type:
                continue
            url = ph.getattr(item, "src", flags=ph.I)
            if not url:
                continue
            urltab.append({"name": "[%s] %s" % (type, domain), "url": strwithmeta(url, {"User-Agent": HTTP_HEADER["User-Agent"]})})

        return urltab

    def parserUEFACOM(self, baseUrl):
        printDBG("parserUEFACOM baseUrl[%r]" % baseUrl)
        vid = ph.search(baseUrl, "vid=([0-9]+)")[0]
        if len(vid) % 2 > 0:
            vid = "0" + vid
        vidPart = []
        for idx in range(0, len(vid), 2):
            vidPart.append("n%s=%s" % (len(vidPart) + 1, vid[idx:idx + 2]))
        url = "https://www.uefa.com/library/common/video/%s/feed.js" % ("/").join(vidPart)
        urlParams = {"header": self.cm.getDefaultHeader(browser="chrome")}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        token = ph.clean_html(ph.find(data, ("<div", ">", "token"), "</div>", flags=0)[1])
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        streamUrl = ph.search(data, r"""["']([^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", flags=0)[0] + "?hdnea=" + token
        streamUrl = strwithmeta(self.cm.getFullUrl(streamUrl, cUrl), {"Referer": cUrl, "User-Agent": urlParams["header"]["User-Agent"]})
        return getDirectM3U8Playlist(streamUrl, checkContent=True, sortWithMaxBitrate=999999999)

    def parserVIDUPLAYERCOM(self, baseUrl):
        printDBG("parserVIDUPLAYERCOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        jscode = [self.jscode["jwplayer"]]
        jscode.append("LevelSelector={};var element=function(n){print(JSON.stringify(n)),this.on=function(){}},Clappr={};Clappr.Player=element,Clappr.Events={PLAYER_READY:1,PLAYER_TIMEUPDATE:1,PLAYER_PLAY:1,PLAYER_ENDED:1};")
        tmp = ph.findall(data, ("<script", ">"), "</script>", flags=0)
        for item in tmp:
            if "eval(" in item:
                jscode.append(item)

        urltab = []
        ret = js_execute(("\n").join(jscode))
        data = json_loads(ret["data"].strip())
        for item in data["sources"]:
            url = item.get("file", "")
            label = item.get("label", "")
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
            elif "mp4" in url:
                urltab.append({"name": "res: " + label, "url": url})
        return urltab

    def parserHYDRAXNET(self, baseUrl):
        printDBG("parserHYDRAXNET baseUrl[%r]" % baseUrl)
        player = json_loads(baseUrl.meta["player_data"])
        for k in ("width", "height", "autostart"):
            player.pop(k, None)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        videoUrl = "https://multi.hydrax.net/vip"
        sts, data = self.cm.getPage(videoUrl, {"header": HTTP_HEADER}, player)
        if not sts:
            return False
        videoUrl += "?" + urllib_urlencode(player)
        pyCmd = GetPyScriptCmd("hydrax") + ' "%s" "%s" "%s" "%s" "%s" "%s" "%s" "%s" ' % (0, videoUrl, "quality", "0xb1d43309ca93c802b7ed16csf7e8d4f1b", baseUrl, GetJSScriptFile("hydrax.byte"), HTTP_HEADER["User-Agent"], "/usr/bin/duk")
        urlsTab = []
        map = [("sd", "480x360"), ("mhd", "640x480"), ("hd", "1280x720"), ("fullhd", "1920x1080")]
        data = json_loads(data)
        for item in map:
            if item[0] not in data:
                continue
            meta = {"iptv_proto": "em3u8"}
            meta["iptv_refresh_cmd"] = pyCmd.replace('"quality"', '"%s"' % item[0])
            url = urlparser.decorateUrl("ext://url/" + videoUrl, meta)
            urlsTab.append({"name": "%s, %s" % item, "url": url})

        return urlsTab

    def parserUPZONECC(self, baseUrl):
        printDBG("parserUPZONECC baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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
        printDBG(data)
        js_params = [{"path": GetJSScriptFile("upzonecc.byte")}]
        js_params.append({"code": "print(cnc(atob('%s')));" % data})
        ret = js_execute_ext(js_params)
        url = self.cm.getFullUrl(ret["data"].strip(), cUrl)
        return strwithmeta(url, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})

    def parserXSTREAMCDNCOM(self, baseUrl):
        printDBG("parserXSTREAMCDNCOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        COOKIE_FILE = GetCookieDir("xstreamcdn.com.cookie")
        rm(COOKIE_FILE)
        urlParams = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        urlParams["header"].update({"Referer": cUrl, "Accept": "*/*", "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"})
        url = self.cm.getFullUrl("/api/source/%s" % cUrl.rsplit("/", 1)[(-1)], cUrl)
        sts, data = self.cm.getPage(url, urlParams, {"r": "", "d": self.cm.getBaseUrl(cUrl, True)})
        if not sts:
            return False
        data = json_loads(data)
        urltab = []
        for item in data["data"]:
            url = item.get("file", "")
            type = item.get("type", "")
            label = item.get("label", "")
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
            elif "mp4" in type:
                urltab.append({"name": type + " res: " + label, "url": url})
        return urltab

    def parserVEUCLIPS(self, baseUrl):
        printDBG("parserVEUCLIPS baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        COOKIE_FILE = GetCookieDir("veuclips.com.cookie")
        rm(COOKIE_FILE)
        urlParams = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE}
        aObj = re.compile("""<a[^>]+?href=(['"])([^>]*?/player/[^>]*?)(?:\1)""", re.I)
        url = baseUrl
        tries = 0
        while tries < 3:
            tries += 1
            sts, data = self.cm.getPage(url, urlParams)
            if not sts:
                return False
            cUrl = self.cm.meta["url"]
            if "/embed/" in cUrl:
                break
            urlParams["header"].update({"Referer": cUrl})
            url = ph.search(data, ph.IFRAME)[1]
            if not url:
                url = ph.search(data, aObj)[1]
            url = self.cm.getFullUrl(url.replace("&amp;", "&"), cUrl)

        urltab = []
        data = re.compile(r"""["']((?:https?:)?//[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", re.I).findall(data)
        meta = {"Referer": cUrl, "Origin": self.cm.getBaseUrl(cUrl)[:-1], "User-Agent": HTTP_HEADER["User-Agent"]}
        uniqueUrls = set()
        for hlsUrl in data:
            if hlsUrl in uniqueUrls:
                continue
            uniqueUrls.add(hlsUrl)
            hlsUrl = strwithmeta(self.cm.getFullUrl(hlsUrl.replace("&amp;", "&"), cUrl), meta)
            urltab.extend(getDirectM3U8Playlist(hlsUrl, checkContent=True, sortWithMaxBitrate=999999999))

        return urltab

    def parserPROMPTFILE(self, baseUrl):
        printDBG("parserPROMPTFILE baseUrl[%s]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if sts:
            HTTP_HEADER = dict(self.HTTP_HEADER)
            HTTP_HEADER["Referer"] = baseUrl
            if "Continue to File" in data:
                sts, data = self.cm.ph.getDataBeetwenMarkers(data, '<form method="post" action="">', "</form>", False, False)
                post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
                params = {"header": HTTP_HEADER, "cookiefile": GetCookieDir("promptfile.cookie"), "use_cookie": True, "save_cookie": True, "load_cookie": False}
                sts, data = self.cm.getPage(baseUrl, params, post_data)
                if not sts:
                    return False
            data = self.cm.ph.getSearchGroups(data, """url: ["'](http[^"']+?)["'],""")[0]
            if "" != data:
                return data
        return False

    def parserVIDEOWOODTV(self, baseUrl):
        printDBG("parserVIDEOWOODTV baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        if "embed" not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{4})/")[0]
            url = "http://videowood.tv/embed/{0}".format(video_id)
        else:
            url = baseUrl

        params = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return False
        while True:
            vidUrl = self.cm.ph.getSearchGroups(data, r"""["']*file["']*:[ ]*["'](http[^"']+?(?:\.mp4|\.flv)[^"']*?)["']""")[0]
            if "" != vidUrl:
                return vidUrl.replace("\\/", "/")

            sts, data = self.cm.ph.getDataBeetwenMarkers(data, "eval(", "</script>")
            if sts:
                # unpack and decode params from JS player script code
                data = unpackJSPlayerParams(data, TEAMCASTPL_decryptPlayerParams)
                # data = self.cm.ph.getDataBeetwenMarkers(data, 'config=', ';',
                printDBG(data)
                continue
            break
        return False

    def parserMOVRELLCOM(self, baseUrl):
        printDBG("parserMOVRELLCOM baseUrl[%s]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if sts:
            HTTP_HEADER = dict(self.HTTP_HEADER)
            HTTP_HEADER["Referer"] = baseUrl
            if "Watch as Free User" in data:
                sts, data = self.cm.ph.getDataBeetwenMarkers(data, "<form", "</form>", False, False)
                post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', data))
                params = {"header": HTTP_HEADER}
                sts, data = self.cm.getPage(baseUrl, params, post_data)
                if not sts:
                    return False
            # get JS player script code from confirmation page
            sts, tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="player_code"', "</div>", True)
            sts, tmp = self.cm.ph.getDataBeetwenMarkers(tmp, ">eval(", "</script>")
            if sts:
                # unpack and decode params from JS player script code
                data = unpackJSPlayerParams(tmp, VIDUPME_decryptPlayerParams)
                printDBG(data)
                # get direct link to file from params
                src = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
                if src.startswith("http"):
                    return src
        return False

    def parserVIDFILENET(self, baseUrl):
        printDBG("parserVIDFILENET baseUrl[%s]" % baseUrl)
        vidTab = []
        # COOKIE_FILE = GetCookieDir('vidfilenet.cookie')
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        params = {"header": HTTP_HEADER}  # , 'cookiefile':COOKIE_FILE, 'use_cookie': True, 'save_cookie':True}
        rm(HTTP_HEADER)

        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False

        # cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">", False, False)
        for item in data:
            if "video/mp4" in item or ".mp4" in item:
                res = self.cm.ph.getSearchGroups(item, """res=['"]([^"^']+?)['"]""")[0]
                url = self.cm.ph.getSearchGroups(item, """src=['"]([^"^']+?)['"]""")[0]
                if url.startswith("//"):
                    url = "http:" + url
                if not self.cm.isValidUrl(url):
                    continue
                vidTab.append({"name": "vidfile.net " + res, "url": strwithmeta(url, {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})})  # 'Cookie':cookieHeader,
        vidTab.reverse()
        return vidTab

    def parserVIVOSX(self, baseUrl):
        printDBG("parserVIVOSX baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Accept": "text/html", "Accept-Encoding": "gzip, deflate"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        data = self.cm.ph.getDataBeetwenMarkers(data, "InitializeStream", ";", False)[1]
        data = self.cm.ph.getSearchGroups(data, """['"]([^'^"]+?)['"]""")[0]
        data = json_loads(base64.b64decode(data))
        urltab = []
        for idx in range(len(data)):
            if not self.cm.isValidUrl(data[idx]):
                continue
            urltab.append({"name": _("Source %s") % (idx + 1), "url": strwithmeta(data[idx], {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})})
        return urltab

    def parserZSTREAMTO(self, baseUrl):
        printDBG("parserZSTREAMTO baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Accept": "text/html", "Accept-Encoding": "gzip, deflate"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        return self._findLinks(data, "zstream")

    def parserTHEVIDEOBEETO(self, baseUrl):
        printDBG("parserTHEVIDEOBEETO baseUrl[%r]" % baseUrl)

        if "embed-" not in baseUrl:
            url = "https://thevideobee.to/embed-%s.html" % baseUrl.split("/")[-1].replace(".html", "")
        else:
            url = baseUrl

        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False

        videoUrl = self.cm.ph.getSearchGroups(data, 'type="video[^>]*?src="([^"]+?)"')[0]
        if not self.cm.isValidUrl(videoUrl):
            videoUrl = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"[^>]*?type="video')[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parser1FICHIERCOM(self, baseUrl):
        printDBG("parser1FICHIERCOM baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {
            "User-Agent": "Mozilla/%s%s" % (pageParser.FICHIER_DOWNLOAD_NUM, pageParser.FICHIER_DOWNLOAD_NUM),  # 'Wget/1.%s.%s (linux-gnu)'
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
            printDBG(data)
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
        printDBG(data)
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

            printDBG(data)
            videoUrl = self.cm.ph.getSearchGroups(data, """<a[^>]+?href=['"](https?://[^'^"]+?)['"][^>]+?ok btn-general""")[0]

        error = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "bloc"), ("</div", ">"), False)[1])
        if error != "":
            SetIPTVPlayerLastHostError(error)

        printDBG(">>> videoUrl[%s]" % videoUrl)
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserFILECLOUDIO(self, baseUrl):
        printDBG("parserFILECLOUDIO baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        referer = baseUrl.meta.get("Referer", baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserGOOGLE(self, baseUrl):
        printDBG("parserGOOGLE baseUrl[%s]" % baseUrl)

        urltab = []
        _VALID_URL = r"https?://(?:(?:docs|drive)\.google\.com/(?:uc\?.*?id=|file/d/)|video\.google\.com/get_player\?.*?docid=)(?P<id>[a-zA-Z0-9_-]{28,})"
        mobj = re.match(_VALID_URL, baseUrl)
        try:
            video_id = mobj.group("id")
            linkUrl = "http://docs.google.com/file/d/" + video_id
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

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserARCHIVEORG(self, linkUrl):
        printDBG("parserARCHIVEORG linkUrl[%s]" % linkUrl)
        urltab = []
        sts, data = self.cm.getPage(linkUrl)
        if sts:
            data = self.cm.ph.getSearchGroups(data, r'"sources":\[([^]]+?)]')[0]
            data = "[%s]" % data
            try:
                data = json_loads(data)
                for item in data:
                    if "mp4" == item["type"]:
                        urltab.append({"name": "archive.org: " + item["label"], "url": "https://archive.org" + item["file"]})
            except Exception:
                printExc()
        return urltab

    def parserWEBCAMERAPL(self, baseUrl):
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

    def parserJUNKYVIDEO(self, baseUrl):
        printDBG("parserJUNKYVIDEO baseUrl[%s]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, r"""['"]?file['"]?[ ]*:[ ]*['"]([^"^']+)['"],""")[0]
        if url.startswith("http"):
            return [{"name": "junkyvideo.com", "url": url}]
        return []

    def parserNETTVPLUSCOM(self, baseUrl):
        printDBG("parserNETTVPLUSCOM baseUrl[%s]" % baseUrl)
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER["User-Agent"] = "Mozilla/5.0 (Linux; U; Android 4.1.1; en-us; androVM for VirtualBox ('Tablet' version with phone caps) Build/JRO03S) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"
        HTTP_HEADER["Referer"] = baseUrl
        if baseUrl.endswith("/source.js"):
            url = baseUrl
        else:
            url = baseUrl[: baseUrl.rfind("/")] + "/source.js"
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return []
        url = self.cm.ph.getSearchGroups(data, """["'](http[^'^"]+?m3u8[^'^"]*?)["']""")[0]
        if "" != url:
            return getDirectM3U8Playlist(url, False)
        return []

    def parserFACEBOOK(self, baseUrl):
        printDBG("parserFACEBOOK baseUrl[%s]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return []

        printDBG(data)

        urlsTab = []
        for item in ["hd_src_no_ratelimit", "hd_src", "sd_src_no_ratelimit", "sd_src"]:
            url = self.cm.ph.getSearchGroups(data, r'''"?%s"?\s*?:\s*?"(http[^"]+?\.mp4[^"]*?)"''' % item)[0]
            url = url.replace("\\/", "/")
            if self.cm.isValidUrl(url):
                urlsTab.append({"name": "facebook %s" % item, "url": url})

        return urlsTab

    def parserXAGEPL(self, baseUrl):
        printDBG("parserXAGEPL baseUrl[%s]" % baseUrl)

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        url = self.cm.ph.getSearchGroups(data, 'src="([^"]+?)"')[0]
        return urlparser().getVideoLinkExt(url)

    def parserKABABLIMA(self, baseUrl):
        printDBG("parserKABABLIMA baseUrl[%s]" % baseUrl)
        baseUrl = urlparser.decorateParamsFromUrl(baseUrl)
        Referer = baseUrl.meta.get("Referer", "")
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER["Referer"] = Referer
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        data = re.sub(r"/\*[\s\S]*?\*/", "", data)

        printDBG(data)
        hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        if hlsUrl != "":
            return getDirectM3U8Playlist(hlsUrl, checkContent=True)
        return False

    def parserUSTREAMIXCOM(self, baseUrl):
        printDBG("parserUSTREAMIXCOM baseUrl[%s]" % baseUrl)
        baseUrl = urlparser.decorateParamsFromUrl(baseUrl)
        Referer = baseUrl.meta.get("Referer", "")
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER["Referer"] = Referer
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        val = int(self.cm.ph.getSearchGroups(data, r" \- (\d+)")[0])

        data = self.cm.ph.getDataBeetwenMarkers(data, "= [", "]")[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '"', '"')
        text = ""
        numObj = re.compile(r"(\d+)")
        for value in data:
            value = base64.b64decode(value)
            text += chr(int(numObj.search(value).group(1)) - val)

        statsUrl = self.cm.ph.getSearchGroups(text, r"""src=["'](https?://[^'^"]*?stats\.php[^'^"]*?)["']""", ignoreCase=True)[0]
        HTTP_HEADER["Referer"] = baseUrl
        sts, data = self.cm.getPage(statsUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        token = self.cm.ph.getAllItemsBeetwenMarkers(data, '"', '"', False)[-1]

        printDBG("token||||||||||||||||| " + token)

        hlsUrl = self.cm.ph.getSearchGroups(text, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        printDBG("hlsUrl||||||||||||||||| " + hlsUrl)
        if hlsUrl != "":
            if hlsUrl.endswith("="):
                hlsUrl += token
            hlsUrl = strwithmeta(hlsUrl, {"Referer": baseUrl})
            return getDirectM3U8Playlist(hlsUrl, checkContent=True)
        return False

    def parserPXSTREAMTV(self, baseUrl):
        printDBG("parserPXSTREAMTV baseUrl[%s]" % baseUrl)
        baseUrl = urlparser.decorateParamsFromUrl(baseUrl)
        Referer = baseUrl.meta.get("Referer", "")
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER["Referer"] = Referer
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        data = re.sub(r"/\*[\s\S]*?\*/", "", data)

        printDBG(data)

        def _getParam(name):
            return self.cm.ph.getSearchGroups(data, """%s:[^'^"]*?['"]([^'^"]+?)['"]""" % name)[0]

        swfUrl = "http://pxstream.tv/player510.swf"
        url = _getParam("streamer")
        file = _getParam("file")
        if file == "":
            hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
            if self.cm.isValidUrl(hlsUrl):
                tmp = getDirectM3U8Playlist(hlsUrl, checkContent=True)
                if len(tmp):
                    return tmp
        if file.split("?")[0].endswith(".m3u8"):
            return getDirectM3U8Playlist(file)
        elif "" != file and "" != url:
            url += " playpath=%s swfUrl=%s pageUrl=%s live=1 " % (file, swfUrl, baseUrl)
            printDBG(url)
            return url
        return False

    def parserVEEHDCOM(self, baseUrl):
        printDBG("parserVEEHDCOM baseUrl[%s]" % baseUrl)
        COOKIE_FILE = GetCookieDir("veehdcom.cookie")
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (X11; Linux i686) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.120 Chrome/37.0.2062.120 Safari/537.36", "Referer": baseUrl}
        params = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True}

        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False
        data = self.cm.ph.getDataBeetwenMarkers(data, "playeriframe", ";", False)[1]
        url = self.cm.ph.getSearchGroups(data, """src[ ]*?:[ ]*?['"]([^"^']+?)['"]""")[0]
        if not url.startswith("http"):
            if not url.startswith("/"):
                url = "/" + url
            url = "http://veehd.com" + url
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return False
        vidUrl = self.cm.ph.getSearchGroups(data, """type=['"]video[^"^']*?["'][^>]+?src=["']([^'^"]+?)['"]""")[0]
        if vidUrl.startswith("http"):
            return vidUrl
        return False

    def parserSHAREREPOCOM(self, baseUrl):
        printDBG("parserSHAREREPOCOM baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        tab = []
        tmp = self._findLinks(data, m1="setup", m2="</script>")
        for item in tmp:
            item["url"] = urlparser.decorateUrl(item["url"], {"Referer": baseUrl, "User-Agent": "Mozilla/5.0"})
            tab.append(item)
        return tab

    def parserEASYVIDEOME(self, baseUrl):
        printDBG("parserEASYVIDEOME baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        subTracks = []
        videoUrls = []

        tmp = self.cm.ph.getDataBeetwenMarkers(data, '<div id="flowplayer">', "</script>", False)[1]
        videoUrls = self._findLinks(tmp, serverName="playlist", linkMarker=r"""['"]?url['"]?[ ]*:[ ]*['"](http[^"^']+)['"][,}]""", m1="playlist", m2="]")
        try:
            tmp = self.cm.ph.getDataBeetwenMarkers(data, '"storage":', "]", False)[1]
            printDBG("|||" + tmp)
            tmp = json_loads(tmp + "]")
            for item in tmp:
                videoUrls.append({"name": str(item["quality"]), "url": item["link"]})
                if self.cm.isValidUrl(item.get("sub", "")):
                    url = item["sub"]
                    type = url.split(".")[-1]
                    subTracks.append({"title": _("default"), "url": url, "lang": "unk", "format": type})
        except Exception:
            printExc()

        video_url = self.cm.ph.getSearchGroups(data, '_url = "(http[^"]+?)"')[0]
        if "" != video_url:
            video_url = urllib_unquote(video_url)
            videoUrls.insert(0, {"name": "main", "url": video_url})

        if len(subTracks):
            for idx in range(len(videoUrls)):
                videoUrls[idx]["url"] = strwithmeta(videoUrls[idx]["url"], {"external_sub_tracks": subTracks})

        return videoUrls

    def parseVIMEOCOM(self, baseUrl):
        printDBG("parseVIMEOCOM baseUrl[%s]" % baseUrl)

        if "player" not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([0-9]+?)[/.]")[0]
            if video_id != "":
                url = "https://player.vimeo.com/video/" + video_id
            else:
                sts, data = self.cm.getPage(baseUrl)
                if not sts:
                    return False
                url = self.cm.ph.getSearchGroups(data, r"""['"]embedUrl['"]\s*?:\s*?['"]([^'^"]+?)['"]""")[0]
        else:
            url = baseUrl

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        if "Referer" in baseUrl.meta:
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]

        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False

        urltab = []

        tmp = self.cm.ph.getDataBeetwenMarkers(data, "progressive", "]", False)[1]
        tmp = tmp.split("}")
        printDBG(tmp)
        for item in tmp:
            if "video/mp4" not in item:
                continue
            quality = self.cm.ph.getSearchGroups(item, """quality['"]?:['"]([^"^']+?)['"]""")[0]
            url = self.cm.ph.getSearchGroups(item, """url['"]?:['"]([^"^']+?)['"]""")[0]
            if url.startswith("http"):
                urltab.append({"name": "vimeo.com {0}".format(quality), "url": url})

        hlsUrl = self.cm.ph.getSearchGroups(data, r'"hls"[^}]+?"url"\:"([^"]+?)"')[0]
        tab = getDirectM3U8Playlist(hlsUrl)
        urltab.extend(tab)

        return urltab

    def parserTINYCC(self, baseUrl):
        printDBG("parserTINYCC baseUrl[%s]" % baseUrl)
        self.cm.getPage(baseUrl, {"max_data_size": 0})
        redirectUrl = self.cm.meta["url"]
        if baseUrl != redirectUrl:
            return urlparser().getVideoLinkExt(redirectUrl)
        return False

    def parserONETTV(self, baseUrl):
        printDBG("parserONETTV baseUrl[%r]" % baseUrl)

        videoUrls = []
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return videoUrls
        ckmId = self.cm.ph.getSearchGroups(data, 'data-params-mvp="([^"]+?)"')[0]
        if "" == ckmId:
            ckmId = self.cm.ph.getSearchGroups(data, 'id="mvp:([^"]+?)"')[0]
        if "" == ckmId:
            return videoUrls

        tm = str(int(time.time() * 1000))
        jQ = str(randrange(562674473039806, 962674473039806))
        authKey = "FDF9406DE81BE0B573142F380CFA6043"
        hostName = urlparser().getHostName(baseUrl)
        contentUrl = "http://qi.ckm.onetapi.pl/?callback=jQuery183040" + jQ + "_" + tm + "&body%5Bid%5D=" + authKey + "&body%5Bjsonrpc%5D=2.0&body%5Bmethod%5D=get_asset_detail&body%5Bparams%5D%5BID_Publikacji%5D=" + ckmId + "&body%5Bparams%5D%5BService%5D={0}&content-type=application%2Fjsonp&x-onet-app=player.front.onetapi.pl&_=".format(hostName) + tm
        sts, data = self.cm.getPage(contentUrl)
        if sts:
            try:
                printDBG(data)
                data = json_loads(data[data.find("(") + 1:-2])
                data = data["result"]["0"]["formats"]["wideo"]
                for type in data:
                    for vidItem in data[type]:
                        if None is not vidItem.get("drm_key", None):
                            continue
                        vidUrl = vidItem.get("url", "")
                        if "" == vidUrl:
                            continue
                        if "hls" == type:
                            tmpTab = getDirectM3U8Playlist(vidUrl)
                            for tmp in tmpTab:
                                videoUrls.append({"name": "ONET type:%s :%s" % (type, tmp.get("bitrate", "0")), "url": tmp["url"]})
                        elif None is not vidItem.get("video_bitrate", None):
                            videoUrls.append({"name": "ONET type:%s :%s" % (type, vidItem.get("video_bitrate", "0")), "url": vidUrl})
                        elif None is not vidItem.get("audio_bitrate", None):
                            videoUrls.append({"name": "ONET type:%s :%s" % (type, vidItem.get("audio_bitrate", "0")), "url": vidUrl})
            except Exception:
                printExc()
        return videoUrls

    def parserPUTLIVEIN(self, baseUrl):
        printDBG("parserPUTLIVEIN baseUrl[%r]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl.meta.get("Referer", baseUrl)}
        file = self.cm.ph.getSearchGroups(baseUrl, "file=([0-9]+?)[^0-9]")[0]
        if "" == file:
            file = self.cm.ph.getSearchGroups(baseUrl + "/", "/e/([^/]+?)/")[0]

        linkUrl = "http://www.putlive.in/e/{0}".format(file)
        sts, data = self.cm.getPage(linkUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        # printDBG("=======================================================")
        # printDBG(data)
        # printDBG("=======================================================")
        token = self.cm.ph.getSearchGroups(data, "'key' : '([^']+?)'")[0]
        if token != "":
            token = " token=%s " % token
        sts, data = CParsingHelper.getDataBeetwenMarkers(data, 'unescape("', '")', False)
        if not sts:
            return False
        data = urllib_unquote(data)
        # printDBG(data)

        def _getParam(name):
            return self.cm.ph.getSearchGroups(data, "%s=([^&]+?)&" % name)[0]

        swfUrl = "http://putlive.in/player59.swf"
        streamer = _getParam("streamer")
        file = _getParam("file")
        provider = _getParam("provider")
        rtmpUrl = provider + streamer[streamer.find(":"):]
        if "" != file and "" != rtmpUrl:
            rtmpUrl += " playpath=%s swfUrl=%s %s pageUrl=%s live=1 " % (file, swfUrl, token, linkUrl)
            printDBG(rtmpUrl)
            return rtmpUrl
        return False

    def parserVIDEOHOUSE(self, baseUrl):
        printDBG("parserVIDEOHOUSE baseUrl[%r]" % baseUrl)
        HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader("firefox"), {"Referer": baseUrl})
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        up = urlparser()
        tmp = ph.IFRAME.findall(data)
        tmp.extend(ph.A.findall(data))
        for item in tmp:
            url = self.cm.getFullUrl(item[1], cUrl)
            if 1 == up.checkHostSupport(url):
                urls = up.getVideoLink(url)
                if urls:
                    return urls
        return False

    def parserJUSTUPLOAD(self, baseUrl):
        printDBG("parserJUSTUPLOAD baseUrl[%r]" % baseUrl)
        HTTP_HEADER = MergeDicts(self.cm.getDefaultHeader("firefox"), {"Referer": baseUrl})
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        # printDBG("parserJUSTUPLOAD data: [%s]" % data )
        videoUrl = ph.search(data, r"""<source\s*?src=['"]([^'^"]+?)['"]""")[0]
        if videoUrl.startswith("//"):
            videoUrl = "http:" + videoUrl
        return videoUrl

    def parserGAMETRAILERS(self, baseUrl):
        printDBG("parserGAMETRAILERS baseUrl[%r]" % baseUrl)
        list = GametrailersIE()._real_extract(baseUrl)[0]["formats"]

        for idx in range(len(list)):
            width = int(list[idx].get("width", 0))
            height = int(list[idx].get("height", 0))
            bitrate = int(list[idx].get("bitrate", 0))
            if 0 != width or 0 != height:
                name = "%sx%s" % (width, height)
            elif 0 != bitrate:
                name = "bitrate %s" % (bitrate)
            else:
                name = "%s." % (idx + 1)
            list[idx]["name"] = name
        return list

    def parserVEVO(self, baseUrl):
        printDBG("parserVEVO baseUrl[%r]" % baseUrl)
        videoUrls = self.getVevoIE()._real_extract(baseUrl)["formats"]

        for idx in range(len(videoUrls)):
            width = int(videoUrls[idx].get("width", 0))
            height = int(videoUrls[idx].get("height", 0))
            bitrate = int(videoUrls[idx].get("bitrate", 0)) / 8
            name = ""
            if 0 != bitrate:
                name = "bitrate %s" % (formatBytes(bitrate, 0).replace(".0", "") + "/s")
            if 0 != width or 0 != height:
                name += " %sx%s" % (width, height)
            if "" == name:
                name = "%s." % (idx + 1)
            videoUrls[idx]["name"] = name
        if 0 < len(videoUrls):
            max_bitrate = int(config.plugins.iptvplayer.vevo_default_quality.value)

            def __getLinkQuality(itemLink):
                return int(itemLink["bitrate"])

            videoUrls = CSelOneLink(videoUrls, __getLinkQuality, max_bitrate).getSortedLinks()
            if config.plugins.iptvplayer.vevo_use_default_quality.value:
                videoUrls = [videoUrls[0]]
        return videoUrls

    def parserBBC(self, baseUrl):
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

        printDBG(">>>>>>>>>>>%s<<<<<<<<<<<<<<" % data["formats"])
        for vidItem in data["formats"]:
            if "url" in vidItem:
                url = self.getBBCIE().getFullUrl(vidItem["url"].replace("&amp;", "&"))
                if vidItem.get("ext", "") == "hls" and 0 == len(hlsLinks):
                    hlsLinks.extend(getDirectM3U8Playlist(url, False, checkContent=True))
                elif vidItem.get("ext", "") == "mpd" and 0 == len(mpdLinks):
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

        if len(subtitlesTab):
            for idx in range(len(videoUrls)):
                videoUrls[idx]["url"] = strwithmeta(videoUrls[idx]["url"], {"external_sub_tracks": subtitlesTab})

        return videoUrls

    def parserSHAREDSX(self, baseUrl):
        printDBG("parserSHAREDSX baseUrl[%r]" % baseUrl)
        # based on https://github.com/rg3/youtube-dl/blob/master/youtube_dl/extractor/shared.py
        sts, data = self.cm.getPage(baseUrl)

        if ">File does not exist<" in data:
            SetIPTVPlayerLastHostError("Video %s does not exist" % baseUrl)
            return False

        data = self.cm.ph.getDataBeetwenMarkers(data, "<form", "</form>", False)[1]
        data = re.compile('name="([^"]+?)"[^>]*?value="([^"]+?)"').findall(data)
        post_data = dict(data)
        sts, data = self.cm.getPage(baseUrl, {"header": self.HTTP_HEADER}, post_data)
        if not sts:
            return False

        videoUrl = self.cm.ph.getSearchGroups(data, 'data-url="([^"]+)"')[0]
        if videoUrl.startswith("http"):
            return videoUrl
        return False

    def parserPOSIEDZEPL(self, baseUrl):
        printDBG("parserPOSIEDZEPL baseUrl[%r]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}
        if "/e." not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{10})[/.?]")[0]
            url = "http://e.posiedze.pl/" + video_id
        else:
            url = baseUrl
        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False

        videoUrl = self.cm.ph.getSearchGroups(data, """["']*file["']*[ ]*?:[ ]*?["']([^"^']+?)['"]""")[0]
        if videoUrl.startswith("http"):
            return urlparser.decorateUrl(videoUrl)
        return False

    def parserMIPLAYERNET(self, baseUrl):
        printDBG("parserMIPLAYERNET baseUrl[%r]" % baseUrl)
        Referer = strwithmeta(baseUrl).meta.get("Referer", baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": Referer}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        url2 = self.cm.ph.getSearchGroups(data, """<iframe[^>]*?src=["'](http://miplayer.net[^"^']+?)["']""", 1, True)[0]
        if url2 != "":
            sts, data = self.cm.getPage(url2, {"header": HTTP_HEADER})
            if not sts:
                return False

        curl = self.cm.ph.getSearchGroups(data, """curl[ ]*?=[ ]*?["']([^"^']+?)["']""", 1, True)[0]
        curl = base64.b64decode(curl)
        if curl.split("?")[0].endswith(".m3u8"):
            return getDirectM3U8Playlist(curl, checkExt=False)
        elif curl.startswith("rtmp"):
            swfUrl = "http://p.jwpcdn.com/6/12/jwplayer.flash.swf"
            curl += " swfUrl=%s pageUrl=%s token=OOG17t.x#K9Vh#| " % (swfUrl, url2)
            # curl += ' token=OOG17t.x#K9Vh#| '
            return curl
        return False

    def parserYOCASTTV(self, baseUrl):
        printDBG("parserYOCASTTV baseUrl[%r]" % baseUrl)
        Referer = strwithmeta(baseUrl).meta.get("Referer", baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": Referer}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        swfUrl = self.cm.ph.getSearchGroups(data, """["'](http[^'^"]+?swf)['"]""")[0]
        url = self.cm.ph.getSearchGroups(data, """streamer[^'^"]*?['"](rtmp[^'^"]+?)['"]""")[0]
        file = self.cm.ph.getSearchGroups(data, """file[^'^"]*?['"]([^'^"]+?)['"]""")[0].replace(".flv", "")
        if "" != file and "" != url:
            url += " playpath=%s swfVfy=%s pageUrl=%s " % (file, swfUrl, baseUrl)
            printDBG(url)
            return url
        return False

    def parserSOSTARTORG(self, baseUrl):
        printDBG("parserSOSTARTORG baseUrl[%r]" % baseUrl)
        Referer = strwithmeta(baseUrl).meta.get("Referer", baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": Referer}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        swfUrl = "http://sostart.org/jw/jwplayer.flash.swf"
        url = ""
        file = self.cm.ph.getSearchGroups(data, """file[^'^"]*?['"]([^'^"]+?)['"]""")[0]
        url += file
        if "" != file and "" != url:
            url += " swfVfy=%s pageUrl=%s " % (swfUrl, baseUrl)
            printDBG(url)
            return url
        return False

    def parserLIVEONLINETV247(self, baseUrl):
        printDBG("parserLIVEONLINETV247 baseUrl[%r]" % baseUrl)
        urltab = []
        baseUrl = urlparser.decorateParamsFromUrl(baseUrl)
        Referer = baseUrl.meta.get("Referer", "")
        HTTP_HEADER = dict(self.HTTP_HEADER)
        HTTP_HEADER["Referer"] = Referer

        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        data = re.sub(r"/\*[\s\S]*?\*/", "", data)

        tmp = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">")
        printDBG(tmp)
        for item in tmp:
            if "application/x-mpegurl" not in item.lower():
                continue
            hlsUrl = self.cm.ph.getSearchGroups(item, """src=["'](https?://[^'^"]+?)["']""")[0]
            if not self.cm.isValidUrl(hlsUrl):
                continue
            urltab.extend(getDirectM3U8Playlist(hlsUrl))
        return urltab

    def parserLIVEONLINE247(self, baseUrl):
        printDBG("parserLIVEONLINE247 baseUrl[%r]" % baseUrl)
        Referer = strwithmeta(baseUrl).meta.get("Referer", baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": Referer}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        swfUrl = self.cm.ph.getSearchGroups(data, """["'](http[^'^"]+?swf)['"]""")[0]
        if swfUrl == "":
            swfUrl = "http://p.jwpcdn.com/6/12/jwplayer.flash.swf"
        url = self.cm.ph.getSearchGroups(data, """file[^'^"]*?['"]([^'^"]+?)['"]""")[0]
        if url.startswith("rtmp"):
            url += " swfVfy=%s pageUrl=%s " % (swfUrl, baseUrl)
            printDBG(url)
            return url
        else:
            data = self.cm.ph.getDataBeetwenMarkers(data, "source:", "}", False)[1]
            url = self.cm.ph.getSearchGroups(data, """hls[^'^"]*?['"]([^'^"]+?)['"]""")[0]
            return getDirectM3U8Playlist(url)
        return False

    def parserHDFILMSTREAMING(self, baseUrl):
        printDBG("parserHDFILMSTREAMING baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        sub_tracks = []
        subData = self.cm.ph.getDataBeetwenMarkers(data, "tracks:", "]", False)[1].split("}")
        for item in subData:
            if '"captions"' in item:
                label = self.cm.ph.getSearchGroups(item, 'label:[ ]*?"([^"]+?)"')[0]
                src = self.cm.ph.getSearchGroups(item, 'file:[ ]*?"([^"]+?)"')[0]
                if not src.startswith("http"):
                    continue
                sub_tracks.append({"title": label, "url": src, "lang": "unk", "format": "srt"})

        urltab = self._findLinks(data, serverName="hdfilmstreaming.com")
        for idx in range(len(urltab)):
            urltab[idx]["url"] = urlparser.decorateUrl(urltab[idx]["url"], {"external_sub_tracks": sub_tracks})

        return urltab

    def parserSUPERFILMPL(self, baseUrl):
        printDBG("parserSUPERFILMPL baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        data = self.cm.ph.getDataBeetwenMarkers(data, "<video ", "</video>", False)[1]
        linkUrl = self.cm.ph.getSearchGroups(data, '<source[^>]+?src="(http[^"]+?)"')[0]
        return linkUrl

    def parserSENDVIDCOM(self, baseUrl):
        printDBG("parserSENDVIDCOM baseUrl[%r]" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False
        data = self.cm.ph.getDataBeetwenMarkers(data, "<video ", "</video>", False)[1]
        linkUrl = self.cm.ph.getSearchGroups(data, '<source[^>]+?src="([^"]+?)"')[0]
        if linkUrl.startswith("//"):
            linkUrl = "http:" + linkUrl
        return linkUrl

    def parserTWITCHTV(self, baseUrl):
        printDBG("parserTWITCHTV baseUrl[%r]" % baseUrl)
        if "channel" in baseUrl:
            data = baseUrl + "&"
        else:
            sts, data = self.cm.getPage(baseUrl)
        channel = self.cm.ph.getSearchGroups(data, """channel=([^&^'^"]+?)[&'"]""")[0]
        MAIN_URLS = "https://api.twitch.tv/"
        CHANNEL_TOKEN_URL = MAIN_URLS + "api/channels/%s/access_token?need_https=false&oauth_token&platform=web&player_backend=mediaplayer&player_type=site"
        LIVE_URL = "http://usher.justin.tv/api/channel/hls/%s.m3u8?token=%s&sig=%s&allow_source=true"
        if "" != channel:
            url = CHANNEL_TOKEN_URL % channel
            sts, data = self.cm.getPage(url, {"header": MergeDicts(self.cm.getDefaultHeader(browser="chrome"), {"Accept": "application/vnd.twitchtv.v5+json", "Client-ID": "jzkbprff40iqj646a697cyrvl0zt2m6"})})
            urltab = []
            if sts:
                try:
                    data = json_loads(data)
                    url = LIVE_URL % (channel, urllib_quote(data["token"]), data["sig"])
                    data = getDirectM3U8Playlist(url, checkExt=False)
                    for item in data:
                        item["url"] = urlparser.decorateUrl(item["url"], {"iptv_proto": "m3u8", "iptv_livestream": True})
                        urltab.append(item)
                except Exception:
                    printExc()
            return urltab
        return False

    def parserOKRU(self, baseUrl):
        printDBG("parserOKRU baseUrl[%r]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": baseUrl, "Cookie": "_flashVersion=18", "X-Requested-With": "XMLHttpRequest"}

        metadataUrl = ""
        if "videoPlayerMetadata" not in baseUrl:
            sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
            if not sts:
                return False
            error = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "vp_video_stub_txt"), ("</div", ">"), False)[1])
            if error == "":
                error = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<", ">", "page-not-found"), ("</", ">"), False)[1])
            if error != "":
                SetIPTVPlayerLastHostError(error)

            tmpTab = re.compile("""data-options=['"]([^'^"]+?)['"]""").findall(data)
            for tmp in tmpTab:
                tmp = clean_html(tmp)
                tmp = json_loads(tmp)
                printDBG("====")
                printDBG(tmp)
                printDBG("====")

                tmp = tmp["flashvars"]
                if "metadata" in tmp:
                    data = json_loads(tmp["metadata"])
                    metadataUrl = ""
                    break
                else:
                    metadataUrl = urllib_unquote(tmp["metadataUrl"])
        else:
            metadataUrl = baseUrl

        if metadataUrl != "":
            url = metadataUrl
            sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return False
            data = json_loads(data)

        urlsTab = []
        for item in data["videos"]:
            url = item["url"]  # .replace('&ct=4&', '&ct=0&') #+ '&bytes'#=0-7078'
            url = strwithmeta(url, {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            urlsTab.append({"name": item["name"], "url": url})
        urlsTab = urlsTab[::-1]

        if 1:  # 0 == len(urlsTab):
            url = urlparser.decorateUrl(data["hlsManifestUrl"], {"iptv_proto": "m3u8", "Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            urltab = getDirectM3U8Playlist(url, checkExt=False, checkContent=True)

            for idx in range(len(urltab)):
                meta = dict(urltab[idx]["url"].meta)
                meta["iptv_proto"] = "m3u8"
                url = urltab[idx]["url"]
                if url.endswith("/"):
                    urltab[idx]["url"] = strwithmeta(url + "playlist.m3u8", meta)

            try:
                tmpurltab = sorted(urltab, key=lambda item: -1 * int(item.get("bitrate", 0)))
                tmpurltab.extend(urlsTab)
                urlsTab = tmpurltab
            except Exception:
                printExc()
        return urlsTab

    def parserALLOCINEFR(self, baseUrl):
        printDBG("parserALLOCINEFR baseUrl[%r]" % baseUrl)
        # based on https://github.com/rg3/youtube-dl/blob/master/youtube_dl/extractor/allocine.py
        _VALID_URL = r"https?://(?:www\.)?allocine\.fr/_?(?P<typ>article|video|film|video|film)/(iblogvision.aspx\?cmedia=|fichearticle_gen_carticle=|player_gen_cmedia=|fichefilm_gen_cfilm=|video-)(?P<id>[0-9]+)(?:\.html)?"
        mobj = re.match(_VALID_URL, baseUrl)
        typ = mobj.group("typ")

        sts, webpage = self.cm.getPage(baseUrl)
        if not sts:
            return False

        if "film" == typ:
            video_id = self.cm.ph.getSearchGroups(webpage, r'href="/video/player_gen_cmedia=([0-9]+).+"')[0]
        else:
            player = self.cm.ph.getSearchGroups(webpage, r"data-player=\'([^\']+)\'>")[0]
            if player != "":
                player_data = json_loads(player)
                video_id = player_data["refMedia"]
            else:
                model = self.cm.ph.getSearchGroups(webpage, r'data-model="([^"]+)"')[0]
                model_data = json_loads(unescapeHTML(model.decode()))
                if "videos" in model_data:
                    try:
                        urlsTab = []
                        for item in model_data["videos"]:
                            for key in item["sources"]:
                                url = item["sources"][key]
                                if url.startswith("//"):
                                    url = "http:" + url
                                if self.cm.isValidUrl(url):
                                    urlsTab.append({"name": key, "url": url})
                        if len(urlsTab):
                            return urlsTab
                    except Exception:
                        printExc()

                video_id = model_data["id"]

        sts, data = self.cm.getPage("http://www.allocine.fr/ws/AcVisiondataV5.ashx?media=%s" % video_id)
        if not sts:
            return False

        data = json_loads(data)
        quality = ["hd", "md", "ld"]
        urlsTab = []
        for item in quality:
            url = data["video"].get(item + "Path", "")
            if not url.startswith("http"):
                continue
            urlsTab.append({"name": item, "url": url})
        return urlsTab

    def parserLIVESTRAMTV(self, baseUrl):
        printDBG("parserLIVESTRAMTV baseUrl[%r]" % baseUrl)
        url = "http://www.live-stream.tv/"
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Referer": baseUrl}

        COOKIEFILE = self.COOKIE_PATH + "live-stream.tv.cookie"
        params = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIEFILE}

        def reloadEpgNow(upBaseUrl):
            tm = str(int(time.time() * 1000))
            upUrl = upBaseUrl + "&_=" + tm + "&callback=?"
            std, data = self.cm.getPage(upUrl, params)
            return

        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return

        mediaId = self.cm.ph.getSearchGroups(data, r"""reloadEpgNow\(\s*['"]([^'^"]+?)['"]""", 1, True)[0]

        url = self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=["'](http[^"^']+?)["']""", 1, True)[0]
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return

        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<script", "</script>")
        tmp = ""
        for item in data:
            if "eval(" in item:
                tmp += "\n %s" % self.cm.ph.getDataBeetwenReMarkers(item, re.compile("<script[^>]*?>"), re.compile("</script>"), False)[1].strip()

        jscode = base64.b64decode("""dmFyIGlwdHZfc3JjZXM9W10sZG9jdW1lbnQ9e30sd2luZG93PXRoaXMsTGV2ZWxTZWxlY3Rvcj0iIixDbGFwcHI9e307Q2xhcHByLlBsYXllcj1mdW5jdGlvbihyKXt0cnl7aXB0dl9zcmNlcy5wdXNoKHIuc291cmNlKX1jYXRjaChlKXt9fTt2YXIgJD1mdW5jdGlvbigpe3JldHVybntyZWFkeTpmdW5jdGlvbihyKXtyKCl9fX07""")
        jscode += tmp + "\nprint(JSON.stringify(iptv_srces));"
        tmp = []
        ret = js_execute(jscode)
        if ret["sts"] and 0 == ret["code"]:
            tmp = ret["data"].strip()
            tmp = json_loads(tmp)

        refreshUrl = "http://www.live-stream.tv/php/ajax.php?f=epgNow&cid=" + mediaId
        reloadEpgNow(refreshUrl)

        tmp = set(tmp)
        printDBG(tmp)
        for vidUrl in tmp:
            vidUrl = strwithmeta(vidUrl, {"iptv_proto": "em3u8", "Referer": url, "iptv_livestream": True, "User-Agent": HTTP_HEADER["User-Agent"]})  # 'iptv_m3u8_skip_seg':2, 'Referer':'http://static.live-stream.tv/player/player.swf'
            tab = getDirectM3U8Playlist(vidUrl, checkContent=True)
            for it in tab:
                it["url"].meta["iptv_refresh_cmd"] = GetPyScriptCmd("livestreamtv") + ' "%s" "%s" "%s" "%s" ' % (it["url"], refreshUrl, baseUrl, HTTP_HEADER["User-Agent"])
            tab.reverse()
            return tab
        return False

    def parserZEROCASTTV(self, baseUrl):
        printDBG("parserZEROCASTTV baseUrl[%r]" % baseUrl)
        if "embed.php" in baseUrl:
            url = baseUrl
        elif "chan.php?" in baseUrl:
            sts, data = self.cm.getPage(baseUrl)
            if not sts:
                return False
            data = self.cm.ph.getDataBeetwenMarkers(data, "<body ", "</body>", False)[1]
            url = self.cm.ph.getSearchGroups(data, r"""src=['"](http[^"^']+)['"]""")[0]

        if "embed.php" not in url:
            sts, data = self.cm.getPage(url)
            if not sts:
                return False
            url = self.cm.ph.getSearchGroups(data, r"""var [^=]+?=[^'^"]*?['"](http[^'^"]+?)['"];""")[0]

        if url == "":
            return False
        sts, data = self.cm.getPage(url)
        if not sts:
            return False

        channelData = self.cm.ph.getSearchGroups(data, r"""unescape\(['"]([^'^"]+?)['"]\)""")[0]
        channelData = urllib_unquote(channelData)

        if channelData == "":
            data = self.cm.ph.getSearchGroups(data, "<h1[^>]*?>([^<]+?)<")[0]
            SetIPTVPlayerLastHostError(data)

        if channelData.startswith("rtmp"):
            channelData += " live=1 "
            return channelData
        return False

    def parserVEOHCOM(self, baseUrl):
        printDBG("parserVEOHCOM url[%s]\n" % baseUrl)

        mediaId = self.cm.ph.getSearchGroups(baseUrl, """permalinkId=([^&]+?)[&$]""")[0]
        if mediaId == "":
            mediaId = self.cm.ph.getSearchGroups(baseUrl, """/watch/([^/]+?)[/$]""")[0]

        # url = 'http://www.veoh.com/api/findByPermalink?permalink=%s' % id

        url = "http://www.veoh.com/iphone/views/watch.php?id=%s&__async=true&__source=waBrowse" % mediaId
        sts, data = self.cm.getPage(url)
        if not sts:
            return False

        printDBG(data)

        data = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")[1]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source", ">", False)
        for item in data:
            url = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?)['"]""")[0]
            if self.cm.isValidUrl(url):
                return url

        url = "http://www.veoh.com/rest/video/%s/details" % mediaId
        sts, data = self.cm.getPage(url)
        if not sts:
            return False

        printDBG(data)

        url = self.cm.ph.getSearchGroups(data, """fullPreviewHashPath=['"]([^'^"]+?)['"]""")[0]
        if self.cm.isValidUrl(url):
            return url
        return False

    def parserCASACINEMACC(self, baseUrl):
        printDBG("parserCASACINEMACC url[%s]\n" % baseUrl)

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        tmp = self.cm.ph.getDataBeetwenMarkers(data, "eval(", "</script>")[1]
        tmp = unpackJSPlayerParams(tmp, TEAMCASTPL_decryptPlayerParams, type=0)
        data += tmp

        printDBG(data)

        urltab = self._findLinks(data, "casacinema.cc")
        return urltab

    def parserULTIMATEDOWN(self, baseUrl):
        printDBG("parserCASACINEMACC url[%s]\n" % baseUrl)
        if "embed.php" not in baseUrl:
            videoId = self.cm.ph.getSearchGroups(baseUrl, r"ultimatedown\.com/([a-zA-z0-9]+?)/")[0]
            baseUrl = "https://ultimatedown.com/plugins/mediaplayer/site/_embed.php?u=%s&w=640h=320" % videoId

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        urltab = self._getSources(data)
        if len(urltab):
            return urltab
        return self._findLinks(data, contain="mp4")

    def parserFILEZTV(self, baseUrl):
        printDBG("parserFILEZTV url[%s]\n" % baseUrl)

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        data = self.cm.ph.getDataBeetwenMarkers(data, ".setup(", ")", False)[1].strip()
        printDBG(data)
        videoUrl = self.cm.ph.getSearchGroups(data, r"""['"]?file['"]?\s*:\s*['"](http[^'^"]+?)['"]""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserTUNEINCOM(self, baseUrl):
        printDBG("parserTUNEINCOM url[%s]\n" % baseUrl)
        streamsTab = []

        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Referer": baseUrl}

        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        tmp = self.cm.ph.getDataBeetwenMarkers(data, "TuneIn.payload =", "});", False)[1].strip()
        tmp = json_loads(tmp)

        partnerId = self.cm.ph.getSearchGroups(data, r"""partnerServiceId\s*=\s*['"]([^'^"]+?)['"]""")[0]
        if partnerId == "":
            partnerId = self.cm.ph.getSearchGroups(data, r"""embedPartnerKey\s*=\s*['"]([^'^"]+?)['"]""")[0]

        stationId = tmp["EmbedPlayer"]["guideItem"]["Id"]
        itemToken = tmp["EmbedPlayer"]["guideItem"]["Token"]
        tuneType = tmp["EmbedPlayer"]["guideItem"]["Type"]

        url = "http://tunein.com/tuner/tune/?tuneType=%s&preventNextTune=true&waitForAds=false&audioPrerollEnabled=false&partnerId=%s&stationId=%s&itemToken=%s" % (tuneType, partnerId, stationId, itemToken)

        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False
        data = json_loads(data)
        printDBG(data)
        printDBG("---")
        url = data["StreamUrl"]
        if url.startswith("//"):
            url = "http:" + url

        sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
        if not sts:
            return False
        data = json_loads(data)
        printDBG(data)
        printDBG("---")

        for item in data["Streams"]:
            url = item["Url"]
            if item.get("Type") == "Live":
                url = urlparser.decorateUrl(url, {"User-Agent": "VLC", "iptv_livestream": True})
            if self.cm.isValidUrl(url):
                streamsTab.append({"name": "Type: %s, MediaType: %s, Bandwidth: %s" % (item["Type"], item["MediaType"], item["Bandwidth"]), "url": url})

        return streamsTab

    def parserVSPORTSPT(self, baseUrl):
        printDBG("parserVSPORTSPT baseUrl[%s]\n" % baseUrl)
        urlsTab = []
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return []

        # example "//vsports.videos.sapo.pt/qS105THDPkJB9nzFNA5h/mov/"
        if "vsports.videos.sapo.pt" in data:
            videoUrl = re.findall(r"(vsports\.videos\.sapo\.pt/[\w]+/mov/)", data)
            if videoUrl:
                videoUrl = "http://" + videoUrl[0] + "?videosrc=true"
                sts, link = self.cm.getPage(videoUrl)
                if sts:
                    printDBG(" '%s' ---> '%s' " % (videoUrl, link))
                    urlsTab.append({"name": "link", "url": link})
                    return urlsTab

        tmp = self.cm.ph.getDataBeetwenReMarkers(data, re.compile(r"""['"]?sources['"]?\s*:\s*\["""), re.compile(r"\]"), False)[1]
        tmp = tmp.split("}")
        for item in tmp:
            videoUrl = self.cm.ph.getSearchGroups(item, r"""['"]?src['"]?\s*:.*?['"]([^'^"]*?//[^'^"]+?)['"]""")[0]
            type = self.cm.ph.getSearchGroups(item, r"""['"]?type['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
            if videoUrl.startswith("//"):
                videoUrl = "http:" + videoUrl
            if self.cm.isValidUrl(videoUrl):
                urlsTab.append({"name": type, "url": videoUrl})

        data = self.cm.ph.getDataBeetwenMarkers(data, ".setup(", ");", False)[1].strip()
        printDBG(data)
        videoUrl = self.cm.ph.getSearchGroups(data, r"""['"]?file['"]?\s*:\s*['"]((?:https?:)?//[^"^']+\.mp4)['"]""")[0]
        if videoUrl.startswith("//"):
            videoUrl = "http:" + videoUrl
        if self.cm.isValidUrl(videoUrl):
            urlsTab.append({"name": "direct", "url": videoUrl})

        return urlsTab

    def parserPUBLICVIDEOHOST(self, baseUrl):
        printDBG("parserPUBLICVIDEOHOST baseUrl[%s]\n" % baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return []

        data = self.cm.ph.getDataBeetwenMarkers(data, "playlist:", "]", False)[1].strip()
        printDBG(data)
        videoUrl = self.cm.ph.getSearchGroups(data, r"""['"]?file['"]?\s*:\s*['"]((?:https?:)?//[^"^']+(?:\.mp4|\.flv))['"]""")[0]
        if videoUrl.startswith("//"):
            videoUrl = "http:" + videoUrl
        if self.cm.isValidUrl(videoUrl):
            return videoUrl
        return False

    def parserUPLOAD2(self, baseUrl):
        printDBG("parserUPLOAD2 baseUrl[%s]" % baseUrl)
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0", "Accept": "text/html", "Accept-Encoding": "gzip, deflate"}

        self.cm.getPage(baseUrl, {"max_data_size": 0})
        baseUrl = self.cm.meta["url"]

        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False

        for marker in ["File Not Found", "The file you were looking for could not be found, sorry for any inconvenience."]:
            if marker in data:
                SetIPTVPlayerLastHostError(_(marker))

        tries = 5
        while tries > 0:
            tries -= 1
            sts, tmp = self.cm.ph.getDataBeetwenMarkers(data, 'method="POST"', "</form>", caseSensitive=False)
            if not sts:
                break

            post_data = dict(re.findall(r'<input[^>]*name="([^"]*)"[^>]*value="([^"]*)"[^>]*>', tmp))
            for key in post_data:
                post_data[key] = clean_html(post_data[key])
            HTTP_HEADER["Referer"] = baseUrl

            try:
                sleep_time = self.cm.ph.getDataBeetwenReMarkers(data, re.compile('<span[^>]+?id="countdown'), re.compile("</span>"))[1]
                sleep_time = self.cm.ph.getSearchGroups(sleep_time, r">\s*([0-9]+?)\s*<")[0]
                if "" != sleep_time:
                    GetIPTVSleep().Sleep(int(sleep_time))
            except Exception:
                pass

            sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER}, post_data)
            if not sts:
                return False

        data = re.sub(r"<!--[\s\S]*?-->", "", data)
        data = re.sub(r"/\*[\s\S]*?\*/", "", data)

        videoData = self.cm.ph.rgetDataBeetwenMarkers2(data, ">download<", "<a ", caseSensitive=False)[1]
        printDBG("videoData[%s]" % videoData)
        videoUrl = self.cm.ph.getSearchGroups(videoData, 'href="([^"]+?)"')[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl

        videoUrl = self.cm.ph.getSearchGroups(data, """<[^>]+?class="downloadbtn"[^>]+?['"](https?://[^'^"]+?)['"]""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl

        tmp = self.cm.ph.getDataBeetwenMarkers(data, 'class="downloadbtn"', "</a>", caseSensitive=False)[1]
        videoUrl = self.cm.ph.getSearchGroups(tmp, """['"](https?://[^'^"]+?)['"]""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl

        tmp = self.cm.ph.getDataBeetwenMarkers(data, "direct link", "</a>", caseSensitive=False)[1]
        videoUrl = self.cm.ph.getSearchGroups(tmp, """['"](https?://[^'^"]+?)['"]""")[0]
        if self.cm.isValidUrl(videoUrl):
            return videoUrl

        return False

    def parserPOLSATSPORTPL(self, baseUrl):
        printDBG("parserPOLSATSPORTPL baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        domain = urlparser.getDomain(baseUrl)
        sts, data = self.cm.getPage(baseUrl)
        sts, tmp = self.cm.ph.getDataBeetwenMarkers(data, "<video", "</video>")
        if not sts:
            return False
        tmp = self.cm.ph.getAllItemsBeetwenMarkers(tmp, "<source", ">")
        urltab = []
        for item in tmp:
            if "video/mp4" not in item and "video/x-flv" not in item:
                continue
            tType = self.cm.ph.getSearchGroups(item, """type=['"]([^'^"]+?)['"]""")[0].replace("video/", "")
            tUrl = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?)['"]""")[0]
            printDBG(tUrl)
            if self.cm.isValidUrl(tUrl):
                urltab.append({"name": "[%s] %s" % (tType, domain), "url": strwithmeta(tUrl)})
        return urltab

    def parserGAMOVIDEOCOM(self, baseUrl):
        printDBG("parserGAMOVIDEOCOM baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        referer = baseUrl.meta.get("Referer", "")

        domain = urlparser.getDomain(baseUrl)
        HEADER = self.cm.getDefaultHeader(browser="chrome")
        HEADER["Referer"] = referer

        sts, data = self.cm.getPage(baseUrl, {"header": HEADER})
        if not sts:
            return False

        if "embed" not in self.cm.meta["url"].lower():
            HEADER["Referer"] = self.cm.meta["url"]
            url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=['"]([^"^']+?embed[^"^']+?)['"]""", 1, True)[0], self.cm.meta["url"])
            sts, data = self.cm.getPage(url, {"header": HEADER})
            if not sts:
                return False

        jscode = [self.jscode["jwplayer"]]
        jscode.append("var element=function(n){print(JSON.stringify(n)),this.on=function(){}},Clappr={};Clappr.Player=element,Clappr.Events={PLAYER_READY:1,PLAYER_TIMEUPDATE:1,PLAYER_PLAY:1,PLAYER_ENDED:1};")
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "eval(" in item and "jwplayer" in item:
                jscode.append(item)

        ret = js_execute("\n".join(jscode))
        if ret["sts"]:
            data += ret["data"]

        urltab = []
        items = self.cm.ph.getAllItemsBeetwenMarkers(data, "<source ", ">", False, False)
        if 0 == len(items):
            items = self.cm.ph.getDataBeetwenReMarkers(data, re.compile(r"""[\s'"]sources[\s'"]*[=:]\s*\["""), re.compile(r"""\]"""), False)[1].split("},")
        printDBG(items)
        for item in items:
            item = item.replace(r"\/", "/")
            url = self.cm.ph.getSearchGroups(item, r"""(?:src|file)['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
            if not url.lower().split("?", 1)[0].endswith(".mp4") or not self.cm.isValidUrl(url):
                continue
            res = self.cm.ph.getSearchGroups(item, r"""res['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
            lang = self.cm.ph.getSearchGroups(item, r"""lang['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
            url = strwithmeta(url, {"Referer": baseUrl})
            urltab.append({"name": domain + " {0} {1}".format(lang, res), "url": url})
        return urltab

    def parserMEDIAFIRECOM(self, baseUrl):
        printDBG("parserMEDIAFIRECOM baseUrl[%s]" % baseUrl)
        HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0", "Accept": "*/*", "Accept-Encoding": "gzip, deflate"}
        sts, data = self.cm.getPage(baseUrl, {"header": HEADER})
        if not sts:
            return False

        data = self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", '"download_link"'), ("</div", ">"))[1]
        data = self.cm.ph.getDataBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)[1]

        jscode = """window=this;document={};document.write=function(){print(arguments[0]);}"""
        ret = js_execute(jscode + "\n" + data)
        if ret["sts"] and 0 == ret["code"]:
            videoUrl = self.cm.ph.getSearchGroups(ret["data"], """href=['"]([^"^']+?)['"]""")[0]
            if self.cm.isValidUrl(videoUrl):
                return videoUrl
        return False

    def parserNADAJECOM(self, baseUrl):
        printDBG("parserNADAJECOM baseUrl[%s]" % baseUrl, params={})
        baseUrl = strwithmeta(baseUrl)
        referer = baseUrl.meta.get("Referer", baseUrl)
        origin = self.cm.getBaseUrl(referer)[:-1]
        USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0"
        HEADER = {"User-Agent": USER_AGENT, "Accept": "*/*", "Content-Type": "application/json", "Accept-Encoding": "gzip, deflate", "Referer": referer, "Origin": origin}
        COOKIE_FILE = GetCookieDir("nadaje.com.cookie")
        params = {"header": HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE}
        rm(COOKIE_FILE)
        videoId = self.cm.ph.getSearchGroups(baseUrl + "/", """/video/([0-9]+?)/""")[0]

        sts, data = self.cm.getPage("https://nadaje.com/api/1.0/services/video/%s/" % videoId, {"header": HEADER})
        if not sts:
            return False

        urltab = []
        data = json_loads(data)["transmission-info"]["data"]["streams"][0]["urls"]
        for key in ["hls", "rtmp", "hds"]:
            if key not in data:
                continue
            url = data[key]
            url = urlparser.decorateUrl(url, {"iptv_livestream": True, "Referer": referer, "User-Agent": USER_AGENT, "Origin": origin})
            if key == "hls":
                urltab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True))
        return urltab

        sts, data = self.cm.getPage(url, params)
        if not sts:
            return []

    def parserVIDSHARETV(self, baseUrl):
        printDBG("parserVIDSHARETV baseUrl[%s]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0",
            "Referer": baseUrl.meta.get("Referer", ""),
        }
        COOKIE_FILE = GetCookieDir("vidshare.tv.cookie")
        rm(COOKIE_FILE)
        params = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": True, "cookiefile": COOKIE_FILE}

        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return

        printDBG(data)

        data = self.cm.ph.getDataBeetwenMarkers(data, ".setup(", ");", False)[1]
        jscode = "var iptv_srces = %s; \nprint(JSON.stringify(iptv_srces));" % data
        ret = js_execute(jscode)
        if ret["sts"] and 0 == ret["code"]:
            data = ret["data"].strip()
            data = json_loads(data)

        cookieHeader = self.cm.getCookieHeader(COOKIE_FILE)
        dashTab = []
        hlsTab = []
        mp4Tab = []
        for item in data["sources"]:
            url = item["file"]
            type = item.get("type", url.split("?", 1)[0].split(".")[-1]).lower()
            label = item.get("label", type)

            if url.startswith("//"):
                url = "http:" + url
            if not self.cm.isValidUrl(url):
                continue

            url = strwithmeta(url, {"Cookie": cookieHeader, "Referer": HTTP_HEADER["Referer"], "User-Agent": HTTP_HEADER["User-Agent"]})
            if "dash" in type:
                dashTab.extend(getMPDLinksWithMeta(url, False, sortWithMaxBandwidth=999999999))
            elif "hls" in type or "m3u8" in type:
                hlsTab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
            elif "mp4" in type or "mpegurl" in type:
                try:
                    sortKey = int(self.cm.ph.getSearchGroups(label, """([0-9]+)""")[0])
                except Exception:
                    sortKey = -1
                mp4Tab.append({"name": "[%s] %s" % (type, label), "url": url, "sort_key": sortKey})

        urltab = []
        mp4Tab.sort(key=lambda item: item["sort_key"], reverse=True)
        urltab.extend(mp4Tab)
        urltab.extend(hlsTab)
        urltab.extend(dashTab)
        return urltab

    def parserVCSTREAMTO(self, baseUrl):
        printDBG("parserVCSTREAMTO baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)

        urlParams = {"with_metadata": True, "header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = data.meta["url"]

        playerUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, """['"]([^'^"]*?/player[^'^"]*?)['"]""")[0], self.cm.getBaseUrl(cUrl))
        urlParams["header"]["Referer"] = cUrl

        sts, data = self.cm.getPage(playerUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        domain = self.cm.getBaseUrl(cUrl, True)

        urltab = []
        data = json_loads(data)["html"]
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "sources", "]", False)
        printDBG(data)
        for sourceData in data:
            sourceData = self.cm.ph.getAllItemsBeetwenMarkers(sourceData, "{", "}")
            for item in sourceData:
                marker = item.lower()
                if " type=" in marker and ("video/mp4" not in marker and "video/x-flv" not in marker and "x-mpeg" not in marker):
                    continue
                item = item.replace("\\/", "/")
                url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, r"""(?:src|file)['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0], self.cm.getBaseUrl(cUrl))
                type = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                label = self.cm.ph.getSearchGroups(item, r"""label['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                printDBG(url)
                if type == "":
                    type = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
                if url == "":
                    continue
                url = strwithmeta(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": cUrl})
                if "x-mpeg" in marker or type == "m3u8":
                    urltab.extend(getDirectM3U8Playlist(url, checkContent=True))
                else:
                    urltab.append({"name": "[%s] %s %s" % (type, domain, label), "url": url})
        return urltab

    def parserVIDCLOUDICU(self, baseUrl):
        printDBG("parserVIDCLOUDICU baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)

        urlParams = {"with_metadata": True, "header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = data.meta["url"]

        urlsTab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "sources", "]", False)
        printDBG(data)
        for sourceData in data:
            sourceData = self.cm.ph.getAllItemsBeetwenMarkers(sourceData, "{", "}")
            for item in sourceData:
                type = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]type['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0].lower()
                if "mp4" not in type:
                    continue
                url = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]src['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
                if url == "":
                    url = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]file['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
                name = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]label['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
                if name == "":
                    name = urlparser.getDomain(url) + " " + name
                url = strwithmeta(url.replace("\\/", "/"), {"Referer": cUrl})
                urlsTab.append({"name": name, "url": url})
        return urlsTab

    def parserUPLOADUJNET(self, baseUrl):
        printDBG("parserUPLOADUJNET baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)

        urlParams = {"with_metadata": True, "header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = data.meta["url"]

        url = self.cm.getFullUrl("/api/preview/request/", self.cm.getBaseUrl(cUrl))
        HTTP_HEADER["Referer"] = cUrl

        hash = "".join([random_choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789") for i in range(20)])
        sts, data = self.cm.getPage(url, urlParams, {"hash": hash, "url": cUrl})
        if not sts:
            return False

        printDBG(data)
        data = json_loads(data)
        if self.cm.isValidUrl(data["clientUrl"]):
            return strwithmeta(data["clientUrl"], {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
        return False

    def parserVIDLOADCO(self, baseUrl):
        printDBG("parserVIDLOADCO baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)

        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        domain = self.cm.getBaseUrl(cUrl, True)

        urltab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "sources", "]", False)
        printDBG(data)
        for sourceData in data:
            sourceData = self.cm.ph.getAllItemsBeetwenMarkers(sourceData, "{", "}")
            for item in sourceData:
                marker = item.lower()
                if "video/mp4" not in marker and "video/x-flv" not in marker and "x-mpeg" not in marker:
                    continue
                item = item.replace("\\/", "/")
                url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(item, r"""(?:src|file)['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0], self.cm.getBaseUrl(cUrl))
                type = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                label = self.cm.ph.getSearchGroups(item, r"""type['"]?\s*[=:]\s*['"]([^"^']+?)['"]""")[0]
                printDBG(url)
                if url == "":
                    continue
                url = strwithmeta(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": cUrl})
                if "x-mpeg" in marker:
                    urltab.extend(getDirectM3U8Playlist(url, checkContent=True))
                else:
                    urltab.append({"name": "[%s] %s %s" % (type, domain, label), "url": url})

        return urltab

    def parserSOUNDCLOUDCOM(self, baseUrl):
        printDBG("parserCLOUDSTREAMUS baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        cUrl = baseUrl
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserCLOUDSTREAMUS(self, baseUrl):
        printDBG("parserCLOUDSTREAMUS baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)

        jscode = ["eval=function(t){return function(){print(arguments[0]);try{return t.apply(this,arguments)}catch(t){}}}(eval);"]
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        data = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in data:
            if "eval(" in item:
                jscode.append(item)
        ret = js_execute("\n".join(jscode))
        if ret["sts"] and 0 == ret["code"]:
            data = ret["data"]

        urlsTab = []
        googleDriveFiles = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, "sources:", "],", False)
        for sourceData in data:
            sourceData = self.cm.ph.getAllItemsBeetwenMarkers(sourceData, "{", "}")
            for item in sourceData:
                type = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]type['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0].lower()
                if type != "mp4":
                    continue
                url = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]file['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
                if "googleapis.com/drive" in url and "/files/" in url:
                    fileId = url.split("/files/", 1)[-1].split("?", 1)[0]
                    if fileId != "":
                        if fileId in googleDriveFiles:
                            continue
                        googleDriveFiles.append(fileId)
                        continue
                name = self.cm.ph.getSearchGroups(item, r"""['"\{\,\s]label['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0]
                if name == "":
                    name = urlparser.getDomain(url)
                urlsTab.append({"name": name, "url": url})
        printDBG(googleDriveFiles)
        for fileId in googleDriveFiles:
            tmp = urlparser().getVideoLinkExt("https://drive.google.com/file/d/%s/view" % fileId)
            if len(tmp):
                tmp.extend(urlsTab)
                urlsTab = tmp
        return urlsTab

    def parserSPORTSTREAM365(self, baseUrl):
        printDBG("parserSPORTSTREAM365 baseUrl[%r]" % baseUrl)
        if self.sportStream365ServIP is None:
            retry = False
        else:
            retry = True

        COOKIE_FILE = GetCookieDir("sportstream365.com.cookie")
        lang = self.cm.getCookieItem(COOKIE_FILE, "lng")

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="iphone_3_0")
        if "Referer" in baseUrl.meta:
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]

        defaultParams = {"header": HTTP_HEADER, "cookiefile": COOKIE_FILE, "use_cookie": True, "save_cookie": True}
        if "cookie_items" in baseUrl.meta:
            defaultParams["cookie_items"] = baseUrl.meta["cookie_items"]

        sts, data = self.cm.getPage(baseUrl, defaultParams)
        if not sts:
            return

        vi = self.cm.ph.getSearchGroups(baseUrl, r"""data\-vi=['"]([0-9]+)['"]""")[0]

        cUrl = self.cm.meta["url"]
        if "Referer" not in HTTP_HEADER:
            HTTP_HEADER["Referer"] = cUrl
        mainUrl = self.cm.getBaseUrl(cUrl)
        if None is self.sportStream365ServIP:
            url = self.cm.getFullUrl("/cinema", mainUrl)
            sts, data = self.cm.getPage(url, MergeDicts(defaultParams, {"raw_post_data": True}), post_data="")
            if not sts:
                return False
            vServIP = data.strip()
            printDBG('vServIP: "%s"' % vServIP)
            if len(vServIP):
                self.sportStream365ServIP = vServIP
            else:
                return

        if vi == "":
            game = self.cm.ph.getSearchGroups(baseUrl, """game=([0-9]+)""")[0]
            if game == "":
                printDBG("Unknown game id!")
                return False

            url = self.cm.getFullUrl("/LiveFeed/GetGame?id=%s&partner=24" % game, mainUrl)
            if lang != "":
                url += "&lng=" + lang
            sts, data = self.cm.getPage(url, defaultParams)
            if not sts:
                return False

            data = json_loads(data)
            printDBG(data)
            vi = data["Value"]["VI"]

        url = "//" + self.sportStream365ServIP + "/hls-live/xmlive/_definst_/" + vi + "/" + vi + ".m3u8?whence=1001"
        url = strwithmeta(self.cm.getFullUrl(url, mainUrl), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": cUrl})
        urltab = getDirectM3U8Playlist(url, checkContent=True)
        if 0 == len(urltab) and retry:
            self.sportStream365ServIP = None
            return self.parserSPORTSTREAM365(baseUrl)

        return urltab

    def parserNXLOADCOM(self, baseUrl):
        printDBG("parserNXLOADCOM baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        if "Referer" in baseUrl.meta:
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]
        params = {"header": HTTP_HEADER}

        if "embed" not in baseUrl:
            sts, data = self.cm.getPage(baseUrl, params)
            if not sts:
                return False
            videoId = self.cm.ph.getSearchGroups(baseUrl + "/", r"[/\-\.]([A-Za-z0-9]{12})[/\-\.]")[0]
            url = self.cm.getBaseUrl(self.cm.meta["url"]) + "embed-{0}.html".format(videoId)
        else:
            url = baseUrl

        sts, data = self.cm.getPage(url, params)
        if not sts:
            return False

        tmp = self.cm.ph.getSearchGroups(data, r"""externalTracks['":\s]*?\[([^\]]+?)\]""")[0]
        printDBG(tmp)
        tmp = re.compile(r"""\{([^\}]+?)\}""", re.I).findall(tmp)
        subTracks = []
        for item in tmp:
            lang = self.cm.ph.getSearchGroups(item, r"""['"]?lang['"]?\s*?:\s*?['"]([^"^']+?)['"]""")[0].lower()
            src = self.cm.ph.getSearchGroups(item, r"""['"]?src['"]?\s*?:\s*?['"](https?://[^"^']+?)['"]""")[0]
            label = self.cm.ph.getSearchGroups(item, r"""label['"]?\s*?:\s*?['"]([^"^']+?)['"]""")[0]
            format = src.split("?", 1)[0].split(".")[-1].lower()
            if format not in ["srt", "vtt"]:
                continue
            if "empty" in src.lower():
                continue
            subTracks.append({"title": label, "url": src, "lang": lang.lower()[:3], "format": "srt"})

        urltab = []
        tmp = self.cm.ph.getSearchGroups(data, r"""sources['":\s]*?\[([^\]]+?)\]""")[0]
        printDBG(tmp)
        tmp = re.compile(r"""['"]([^'^"]+?\.(?:m3u8|mp4|flv)(?:\?[^'^"]*?)?)['"]""", re.I).findall(tmp)
        for url in tmp:
            type = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
            url = self.cm.getFullUrl(url, self.cm.getBaseUrl(self.cm.meta["url"]))
            if type in ["mp4", "flv"]:
                urltab.append({"name": "mp4", "url": url})
            elif type == "m3u8":
                urltab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))

        if len(subTracks):
            for idx in range(len(urltab)):
                urltab[idx]["url"] = urlparser.decorateUrl(urltab[idx]["url"], {"external_sub_tracks": subTracks})

        return urltab

    def parserCLOUDCARTELNET(self, baseUrl):
        printDBG("parserCLOUDCARTELNET baseUrl[%s]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader()
        if "Referer" in baseUrl.meta:
            HTTP_HEADER["Referer"] = baseUrl.meta["Referer"]
        params = {"header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, params)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        domain = self.cm.getBaseUrl(cUrl)
        videoId = self.cm.ph.getSearchGroups(baseUrl + "/", """(?:/video/|/link/)([^/]+?)/""")[0]
        apiUrl = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, """<video[^>]+?poster=['"]([^'^"]+?)['"]""")[0], domain)
        apiDomain = self.cm.getBaseUrl(apiUrl)

        url = self.cm.getFullUrl("/download/link/" + videoId, apiDomain)
        sts, data = self.cm.getPage(url, params)
        if not sts:
            return False

        data = json_loads(data)
        if "mp4" in data["content_type"]:
            return self.cm.getFullUrl(data["url"], apiDomain)

        return False

    def parserHAXHITSCOM(self, baseUrl):
        printDBG("parserHAXHITSCOM baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"with_metadata": True, "header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        cUrl = self.cm.getBaseUrl(data.meta["url"])
        domain = urlparser.getDomain(cUrl)

        jscode = [self.jscode["jwplayer"]]
        tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in tmp:
            if "eval(" in item and "setup" in item:
                jscode.append(item)
        urltab = []
        jscode = "\n".join(jscode)
        ret = js_execute(jscode)
        data = json_loads(ret["data"])
        for item in data["sources"]:
            url = item["file"]
            type = item.get("type", "")
            if type == "":
                type = url.split(".")[-1].split("?", 1)[0]
            type = type.lower()
            label = item["label"]
            if "mp4" not in type:
                continue
            if url == "":
                continue
            url = urlparser.decorateUrl(self.cm.getFullUrl(url, cUrl), {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            urltab.append({"name": "{0} {1}".format(domain, label), "url": url})
        return urltab

    def parserKRAKENFILESCOM(self, baseUrl):
        printDBG("parserKRAKENFILESCOM baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        domain = urlparser.getDomain(cUrl)

        urltab = []
        data = re.compile(r"""['"]([^'^"]+?/uploads/[^'^"]+?\.(?:m4a|mp3)(?:\?[^'^"]*?)?)['"]""").findall(data)
        for url in data:
            url = strwithmeta(self.cm.getFullUrl(url, self.cm.meta["url"]), {"Referer": baseUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            urltab.append({"name": "%s %s" % (domain, len(urltab) + 1), "url": url})

        return urltab

    def parserFILEFACTORYCOM(self, baseUrl):
        printDBG("parserFILEFACTORYCOM baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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
            else:
                printDBG(data)
                msg = clean_html(self.cm.ph.getDataBeetwenNodes(data, ("<div", ">", "box-message"), ("</div", ">"), False)[1])
                SetIPTVPlayerLastHostError(msg)

        return False

    def parserTELERIUMTV(self, baseUrl):
        printDBG("parserTELERIUMTV baseUrl[%r]" % baseUrl)

        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")

        HTTP_HEADER["User-Agent"] = "Mozilla / 5.0 (SMART-TV; Linux; Tizen 2.4.0) AppleWebkit / 538.1 (KHTML, podobnie jak Gecko) SamsungBrowser / 1.1 TV Safari / 538.1"
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        js_params = [{"code": 'var e2i_obj={resp:"", agent:"%s", ref:"%s"};' % (HTTP_HEADER["User-Agent"], HTTP_HEADER["Referer"])}]
        js_params.append({"path": GetJSScriptFile("telerium1.byte")})
        js_params.append({"hash": str(time.time()), "name": "telerium2", "code": ""})

        HTTP_HEADER["Referer"] = cUrl

        data = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
        for item in data:
            if "eval(" in item:
                js_params[2]["code"] = item

        ret = js_execute_ext(js_params)
        data = json_loads(ret["data"])

        url = self.cm.getFullUrl(data["url"], cUrl)

        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return False

        data = json_loads(data)
        printDBG(">>>: " + data)
        js_params[0]["code"] = js_params[0]["code"].replace('resp:""', 'resp:"%s"' % data)

        ret = js_execute_ext(js_params)
        data = json_loads(ret["data"])

        url = self.cm.getFullUrl(data["source"], cUrl)

        if url.split("?", 1)[0].lower().endswith(".m3u8"):
            url = strwithmeta(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": HTTP_HEADER["Referer"], "Origin": self.cm.getBaseUrl(HTTP_HEADER["Referer"])[:-1], "Accept": "*/*"})
            return getDirectM3U8Playlist(url, checkExt=False, checkContent=True)

        return False

    def parserVIDSTODOME(self, baseUrl):
        printDBG("parserVIDSTODOME baseUrl[%r]" % baseUrl)
        # example video: https://vidstodo.me/embed-6g0hf5ne3eb2.html

        """
        def _findLinks(data):
            urltab = []
            data = self.cm.ph.getDataBeetwenMarkers(data, 'sources:', ']', False)[1]
            data = re.compile('"(http[^"]+?)"').findall(data)
            for link in data:
                if link.split('?')[0].endswith('m3u8'):
                    urltab.extend(getDirectM3U8Playlist(link, checkContent=True))
                elif link.split('?')[0].endswith('mp4'):
                    urltab.append({'name':'mp4', 'url': link})
                return urltab
        return self.parserONLYSTREAMTV(baseUrl, 'https://vidtodo.com/embed-{0}.html', _findLinks)
        """

        baseUrl = strwithmeta(baseUrl)
        if "embed" not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{12})[/.]")[0]
            printDBG("parserVIDSTODOME video_id[%s]" % video_id)
            baseUrl = "https://vidtodo.com/embed-{0}.html".format(video_id)

        return self.parserONLYSTREAMTV(strwithmeta(baseUrl, {"Referer": baseUrl}))

    def parserCLOUDVIDEOTV(self, baseUrl):
        printDBG("parserCLOUDVIDEOTV baseUrl[%r]" % baseUrl)
        # example video: https://cloudvideo.tv/embed-1d3w4w97woun.html
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        HTTP_HEADER["Referer"] = baseUrl.meta.get("Referer", baseUrl)
        urlParams = {"header": HTTP_HEADER}

        if "embed" not in baseUrl:
            videoID = self.cm.ph.getSearchGroups(baseUrl + "/", "[^A-Za-z0-9]([A-Za-z0-9]{12})[^A-Za-z0-9]")[0]
            printDBG("parserCLOUDVIDEOTV videoID[%s]" % videoID)
            baseUrl = "{0}embed-{1}.html".format(urlparser.getDomain(baseUrl, False), videoID)

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        retTab = []
        tmp = ph.find(data, "<video", "</video>", flags=ph.IGNORECASE)[1]
        tmp = ph.findall(tmp, "<source", ">", flags=ph.IGNORECASE)
        for item in tmp:
            url = ph.getattr(item, "src")
            type = ph.getattr(item, "type")
            if "video" not in type and "x-mpeg" not in type:
                continue
            if url:
                url = self.cm.getFullUrl(url, cUrl)
                if "video" in type:
                    retTab.append({"name": "[%s]" % type, "url": url})
                elif "x-mpeg" in type:
                    retTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
        return retTab

    def parserMEDIASET(self, baseUrl):
        printDBG("parserMEDIASET baseUrl[%r]" % baseUrl)
        guid = ph.search(baseUrl, r"""https?://(?:(?:www|static3)\.)?mediasetplay\.mediaset\.it/(?:(?:video|on-demand)/(?:[^/]+/)+[^/]+_|player/index\.html\?.*?\bprogramGuid=)([0-9A-Z]{16})""")[0]
        if not guid:
            return

        tp_path = "PR1GhC/media/guid/2702976343/" + guid

        uniqueUrls = set()
        retTab = []
        for asset_type in ("SD", "HD"):
            for f in "MPEG4":  # , 'MPEG-DASH', 'M3U', 'ISM'):
                url = "http://link.theplatform.%s/s/%s?mbr=true&formats=%s&assetTypes=%s" % ("eu", tp_path, f, asset_type)
                sts, data = self.cm.getPage(url, post_data={"format": "SMIL"})
                if not sts:
                    continue
                if "GeoLocationBlocked" in data:
                    SetIPTVPlayerLastHostError(ph.getattr(data, "abstract"))
                printDBG("++++++++++++++++++++++++++++++++++")
                printDBG(data)
                tmp = ph.findall(data, "<video", ">")
                for item in tmp:
                    url = ph.getattr(item, "src")
                    if not self.cm.isValidUrl(url):
                        continue
                    if url not in uniqueUrls:
                        uniqueUrls.add(url)
                        retTab.append({"name": "%s - %s" % (f, asset_type), "url": url})
        return retTab

    def parserBITPORNOCOM(self, baseUrl):
        printDBG("parserBITPORNOCOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        uniqueUrls = set()
        videoUrls = []

        def _addLinks(data):
            data = ph.find(data, ("<video", ">"), "</video>", flags=ph.I)[1]
            data = ph.findall(data, "<source", ">", flags=ph.I)
            for item in data:
                url = ph.getattr(item, "src")
                res = ph.getattr(item, "data-res")
                if not res:
                    name = ph.getattr(item, "title")
                else:
                    name = res
                type = ph.getattr(item, "type").lower()
                if "mp4" in type:
                    videoUrls.append({"name": name, "url": url, "res": res})
                else:
                    if "x-mpeg" in type:
                        videoUrls.extend(getDirectM3U8Playlist(url, checkContent=True))
                uniqueUrls.add(name)

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        _addLinks(data)
        links = re.compile("""<a[^>]+?href=(['"])([^>]*?&q=([0-9]+?)p[^>]*?)(?:\1)""", re.I).findall(data)
        for item in links:
            if item[2] in uniqueUrls:
                continue
            uniqueUrls.add(item[2])
            sts, data = self.cm.getPage(self.cm.getFullUrl(item[1], cUrl), urlParams)
            if sts:
                _addLinks(data)

        try:
            videoUrls = sorted(videoUrls, key=lambda item: int(item.get("res", 0)))
        except Exception:
            pass

        return videoUrls[::-1]

    def parserGLORIATV(self, baseUrl):
        printDBG("parserGLORIATV baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        retTab = []
        data = ph.find(data, ("<video", ">"), "</video>", flags=0)[1]
        data = ph.findall(data, "<source", ">", flags=0)
        for item in data:
            url = self.cm.getFullUrl(ph.getattr(item, "src").replace("&amp;", "&"), cUrl)
            type = ph.clean_html(ph.getattr(item, "type").lower())
            if "video" not in type and "x-mpeg" not in type:
                continue
            url = strwithmeta(url, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
            if "video" in type:
                width = ph.getattr(item, "width")
                height = ph.getattr(item, "height")
                bitrate = ph.getattr(item, "bitrate")
                retTab.append({"name": "[%s] %sx%s %s" % (type, width, height, bitrate), "url": url})
            elif "x-mpeg" in type:
                retTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))

        return retTab

    def parserPRIMEVIDEOS(self, baseUrl):
        printDBG("parserPRIMEVIDEOS baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        reHLS = re.compile(r"""['"]([^'^"]*?://[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]""")
        url = ph.search(data, reHLS)[0]
        if not url:
            tmp = self.cm.getFullUrl(ph.search(data, ph.IFRAME)[1], cUrl)
            urlParams["header"]["Referer"] = cUrl
            sts, data = self.cm.getPage(tmp, urlParams)
            if not sts:
                return False
            cUrl = self.cm.meta["url"]
            reHLS = re.compile(r"""['"]([^'^"]*?://[^'^"]+?\.m3u8(?:\?[^'^"]+?)?)['"]""")
            url = ph.search(data, reHLS)[0]
            if not url:
                return
        url = strwithmeta(self.cm.getFullUrl(url, cUrl), {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
        return getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999)

    def parserVIDFLARECOM(self, baseUrl):
        printDBG("parserVIDFLARECOM baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        baseUrl = self.cm.getFullUrl(ph.search(data, ph.IFRAME)[1], cUrl)
        return urlparser().getVideoLinkExt(strwithmeta(baseUrl, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]}))

    def parserVIDCLOUDCO(self, baseUrl):
        printDBG("parserVIDCLOUDCO baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        COOKIE_FILE = GetCookieDir("vidcloud.co.cookie")
        urlParams = {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        token = ph.getattr(ph.find(data, ("<meta", ">", "-token"), flags=ph.I | ph.START_E)[1], "content", flags=ph.I)
        urlParams["header"].update({"X-CSRF-TOKEN": token, "Referer": cUrl, "X-Requested-With": "XMLHttpRequest"})
        data = ph.find(data, ("function loadPlayer(", "{"), "}", flags=0)[1]
        url = self.cm.getFullUrl(ph.search(data, r"""url['"]?\s*:\s*['"]([^'^"]+?)['"]""")[0], cUrl)
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        data = json_loads(data)
        printDBG(data["html"])
        return self._findLinks(data["html"], self.cm.getBaseUrl(baseUrl, True))

    def parserGOVIDME(self, baseUrl):
        printDBG("parserGOVIDME baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        return self._findSourceLinks(data, cUrl, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})

    def parserHARPYTV(self, baseUrl):
        printDBG("parserHARPYTV baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        return self._findSourceLinks(data, cUrl, {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})

    def parserFLIX555COM(self, baseUrl):
        printDBG("parserFLIX555COM baseUrl[%r]" % baseUrl)
        return self._parserUNIVERSAL_A(baseUrl, "https://flix555.com/embed-{0}-800x600.html", self._findLinks)

    def parserVIDEOSTREAMLETNET(self, baseUrl):
        printDBG("parserVIDEOSTREAMLETNET baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]
        streamUrl = ph.search(data, r"""["']([^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", flags=0)[0]
        streamUrl = strwithmeta(self.cm.getFullUrl(streamUrl, cUrl), {"Referer": cUrl, "User-Agent": HTTP_HEADER["User-Agent"]})
        return getDirectM3U8Playlist(streamUrl, checkContent=True, sortWithMaxBitrate=999999999)

    def parserVIUCLIPS(self, baseUrl):
        printDBG("parserVIUCLIPS baseUrl[%s]" % baseUrl)
        """
        example video:
        http://oms.viuclips.net/player/PopUpIframe/JwB2kRDt7Y?iframe=popup&u=
        http://oms.veuclips.com/player/PopUpIframe/HGXPBPodVx?iframe=popup&u=
        https://footy11.viuclips.net/player/html/D7o5OVWU9C?popup=yes&autoplay=1
        http://player.veuclips.com/embed/JwB2kRDt7Y
        """
        if "parserVIUCLIPS" in baseUrl:
            baseUrl = ph.search(baseUrl, r"""https?://.*parserVIUCLIPS\[([^"]+?)\]""")[0]
            printDBG("force parserVIUCLIPS baseUrl[%s]" % baseUrl)

        if "embed" not in baseUrl:
            video_id = ph.search(baseUrl, r"""https?://.*/player/.*/([a-zA-Z0-9]{13})\?""")[0]
            printDBG("parserVIUCLIPS video_id[%s]" % video_id)
            baseUrl = "{0}embed/{1}".format(urlparser.getDomain(baseUrl, False), video_id)

        sts, data = self.cm.getPage(baseUrl)
        if not sts:
            return False

        if "This video has been removed" in data:
            SetIPTVPlayerLastHostError("This video has been removed")
            return False

        vidTab = []
        hlsUrl = self.cm.ph.getSearchGroups(data, r"""["']([^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        tmpUrl = urlparser.getDomain(hlsUrl)
        hlsUrl = hlsUrl.replace(tmpUrl + "//", tmpUrl + "/")
        if hlsUrl != "":
            if hlsUrl.startswith("//"):
                hlsUrl = "https:" + hlsUrl
            hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            vidTab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
        return vidTab

    def parserONLYSTREAMTV(self, baseUrl):
        printDBG("parserONLYSTREAMTV baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        if "eval(function(p,a,c,k,e,d)" in data:
            printDBG("Host resolveUrl packed")
            scripts = re.findall(r"(eval\s?\(function\(p,a,c,k,e,d.*?)</script>", data, re.S)
            data = ""
            for packed in scripts:
                data2 = packed
                printDBG("Host pack: [%s]" % data2)
                try:
                    data += unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                    printDBG("OK unpack: [%s]" % data)
                except Exception:
                    pass

        urltab = self._findLinks(data, meta={"Referer": baseUrl})
        if 0 == len(urltab):
            url = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.mp4(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
            if url != "":
                url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
                urltab.append({"name": "mp4", "url": url})
            hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
            if hlsUrl != "":
                hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
                urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        return urltab

    def parserVIDLOADNET(self, baseUrl):
        printDBG("parserVIDLOADNET baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}

        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        url = ""
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '<input type="hidden"', ">")
        for item in data:
            data = self.cm.ph.getSearchGroups(item, r"""\svalue=['"]([^'^"]+?)['"]""")[0]
            if "==" in data:
                myreason = data[:-2]
            if "=" not in data:
                url = data
        if url == "":
            return False

        url = "https://www.vidload.net/streamurl/{0}/".format(url)
        post_data = {"myreason": myreason, "saveme": "undefined"}
        sts, data = self.cm.getPage(url, urlParams, post_data)
        if not sts:
            return False

        sts, data = self.cm.getPage(self.cm.getFullUrl(data, cUrl), urlParams)
        if not sts:
            return False

        urltab = []
        url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, """<source[^>]+?src=['"]([^'^"]+?)['"][^>]+?video/mp4""")[0], cUrl)
        if url != "" and "m3u8" not in url:
            url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.append({"name": "mp4", "url": url})
        hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        if hlsUrl != "":
            hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
        return urltab

    def parserVIDCLOUD9(self, baseUrl):
        printDBG("parserVIDCLOUD9 baseUrl[%r]" % baseUrl)
        baseUrl = strwithmeta(baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="firefox")
        urlParams = {"header": HTTP_HEADER}
        urlParams["header"].update({"Referer": urlparser.getDomain(baseUrl, False), "X-Requested-With": "XMLHttpRequest"})
        _url = self.cm.ph.getSearchGroups(baseUrl, r"""https?://.+?/(.+?)\.php.+?""", ignoreCase=True)[0]
        sts, data = self.cm.getPage(baseUrl.replace(_url, "ajax"), urlParams)
        if not sts:
            return False
        data = json_loads(data)
        urltab = []
        for item in data["source"]:
            url = item.get("file", "")
            url = strwithmeta(url, {"Referer": baseUrl})
            label = item.get("label", "")
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
            elif "mp4" in url:
                urltab.append({"name": "res: " + label, "url": url})
        for item in data["source_bk"]:
            url = item.get("file", "")
            url = strwithmeta(url, {"Referer": baseUrl})
            label = item.get("label", "")
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))
            elif "mp4" in url:
                urltab.append({"name": "res: " + label, "url": url})
        return urltab

    def parserNINJASTREAMTO(self, baseUrl):
        printDBG("parserNINJASTREAMTO baseUrl [%s]" % baseUrl)

        COOKIE_FILE = GetCookieDir("ninjastream.cookie")
        httpParams = {"header": {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36", "Accept": "*/*", "Accept-Encoding": "gzip", "Referer": baseUrl.meta.get("Referer", baseUrl)}, "use_cookie": True, "load_cookie": True, "save_cookie": True, "cookiefile": COOKIE_FILE}

        urlsTab = []

        sts, data = self.cm.getPage(baseUrl, httpParams)
        if sts:
            r = self.cm.ph.getSearchGroups(data, r'v-bind:[n|s]*stream="([^"]+?)"')[0].replace("&quot;", '"')
            if not r:
                r = self.cm.ph.getSearchGroups(data, r'v-bind:[n|s]*file="([^"]+?)"')[0].replace("&quot;", '"')
            printDBG("parserNINJASTREAMTO r [%s]" % r)
            httpParams["header"]["X-Requested-With"] = "XMLHttpRequest"
            httpParams["header"]["x-csrf-token"] = self.cm.ph.getSearchGroups(data, """<[^>]+?csrf-token[^>]+?content=['"]([^'^"]+?)['"]""")[0]
            httpParams["header"]["x-xsrf-token"] = self.cm.getCookieItem(COOKIE_FILE, "XSRF-TOKEN")
            if r:
                data = json_loads(r)
                sts, data = self.cm.getPage("https://ninjastream.to/api/video/get", httpParams, {"id": data.get("hashid")})
                if sts:
                    data = json_loads(data)
                    url = data["result"]["playlist"]
                    urlsTab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))

        return urlsTab

    def parserUSERLOADCO(self, baseUrl):
        printDBG("parserUSERLOADCO baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        subTracksData = self.cm.ph.getAllItemsBeetwenMarkers(data, "<track ", ">", False, False)
        subTracks = []
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

        urltab = []

        if "eval(function(p,a,c,k,e,d)" in data:
            printDBG("Host resolveUrl packed")
            packed = re.compile(r">eval\(function\(p,a,c,k,e,d\)(.+?)</script>", re.DOTALL).findall(data)
            if packed:
                data2 = packed[-1]
            else:
                return ""
            printDBG("Host pack: [%s]" % data2)
            try:
                data = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                printDBG("OK unpack: [%s]" % data)
            except Exception:
                pass

            morocco = self.cm.ph.getSearchGroups(data, """['"](AO.+?Aa)['"]""")[0]
            if morocco == "":
                morocco = self.cm.ph.getSearchGroups(data, """['"]([0-9a-zA-Z]{31})['"]""")[0]
            tmp = re.findall("""['"]([0-9a-z]{32})['"]""", data)
            for item in tmp:
                post_data = {"morocco": morocco, "mycountry": item}
                sts, data = self.cm.getPage("https://userload.co/api/request/", urlParams, post_data)
                if not sts:
                    return False
                if "http" in data:
                    break
            data = data.splitlines()[0]

            params = {"Referer": baseUrl, "Origin": urlparser.getDomain(baseUrl, False)}
            params["external_sub_tracks"] = subTracks
            url = urlparser.decorateUrl(data, params)
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
            else:
                urltab.append({"name": "mp4", "url": url})

        return urltab

    def parserFASTSHARECZ(self, baseUrl):
        printDBG("parserFASTSHARECZ baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        url = self.cm.getFullUrl(self.cm.ph.getSearchGroups(data, r"""action=(\/free\/[^>]+?)>""")[0], baseUrl)
        urlParams["max_data_size"] = 0
        urlParams["no_redirection"] = True
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return False

        urltab = []
        url = self.cm.meta.get("location", "")
        if self.cm.isValidUrl(url):
            url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.append({"name": "mp4", "url": url})

        return urltab

    def parserRUMBLECOM(self, baseUrl):
        printDBG("parserRUMBLECOM baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False

        urltab = []
        data = self.cm.ph.getAllItemsBeetwenMarkers(data, '"url":', "}", withMarkers=True)
        for item in data:
            printDBG("parserRUMBLECOM item[%s]" % item)
            url = self.cm.ph.getSearchGroups(item, """['"]url['"]:['"]([^"^']+?)['"]""")[0].replace(r"\/", "/")
            if "mp4" not in url:
                continue
            name = self.cm.ph.getSearchGroups(item, r"""['"]w['"]:(\d+)""")[0] + "x" + self.cm.ph.getSearchGroups(item, r"""['"]h['"]:(\d+)""")[0]
            urltab.append({"name": name, "url": url})

        return urltab

    def parserSHOWSPORTXYZ(self, baseUrl):
        printDBG("parserSHOWSPORTXYZ baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        urltab = []
        url = self.cm.ph.getSearchGroups(data, r"""\swindow.atob\(['"]([^"^']+?)['"]""")[0]
        if url != "":
            url = urllib_unquote(base64.b64decode(url).replace("playoutengine.sinclairstoryline", "playoutengine-v2.sinclairstoryline"))
            url = strwithmeta(url, {"Referer": baseUrl})
            urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))

        return urltab

    def parserDADDYLIVE(self, baseUrl):
        printDBG("parserDADDYLIVE baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        cUrl = self.cm.meta["url"]

        data = self.cm.ph.getDataBeetwenNodes(data, ("<iframe", ">", "src"), ("</iframe", ">"))[1]
        url = self.cm.ph.getSearchGroups(data, """src=['"]([^"^']+?)['"]""")[0]
        HTTP_HEADER["Referer"] = cUrl
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return []
        printDBG("parserDADDYLIVE data[%s]" % data)
        urltab = []
        data = self.cm.ph.getDataBeetwenMarkers(data, "Clappr.Player", ("</script", ">"), False)[1]
        url = self.cm.ph.getSearchGroups(data, r"""source:\s?['"]([^"^']+?)['"]""")[0]
        url = strwithmeta(url, {"Origin": urlparser.getDomain(baseUrl, False), "Referer": cUrl})
        if url != "":
            urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))

        return urltab

    def parserLIVEONSCORETV(self, baseUrl):
        printDBG("parserLIVEONSCORETV baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        cUrl = self.cm.meta["url"]

        data = self.cm.ph.getDataBeetwenMarkers(data, "var player", ("</script", ">"), False)[1]
        url = self.cm.ph.getSearchGroups(data, r"""url:\s*['"]([^"^']+?)['"]""")[0]
        UrlID = self.cm.ph.getSearchGroups(data, r"""var\svidgstream\s?=\s?['"]([^"^']+?)['"]""")[0]
        url = url + "?idgstream=" + urllib_quote(UrlID)
        HTTP_HEADER["Referer"] = cUrl
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(url, urlParams)
        if not sts:
            return []
        data = data.replace(r"\/", "/")

        urltab = []
        url = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.mp4(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        if url != "":
            url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.append({"name": "mp4", "url": url})
        hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
        if hlsUrl != "":
            hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        return urltab

    def parserSPORTSONLINETO(self, baseUrl):
        printDBG("parserSPORTSONLINETO baseUrl[%r]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        _url = self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=['"](http[^"^']+?)['"]""", 1, True)[0]
        HTTP_HEADER["Referer"] = cUrl
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(_url, urlParams)
        if not sts:
            return False

        urltab = []
        if "eval(function(p,a,c,k,e,d)" in data:
            printDBG("Host resolveUrl packed")
            scripts = re.findall(r"(eval\s?\(function\(p,a,c,k,e,d.*?)</script>", data, re.S)
            for packed in scripts:
                data2 = packed
                printDBG("Host pack: [%s]" % data2)
                try:
                    data = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                    printDBG("OK unpack: [%s]" % data)
                except Exception:
                    pass

                url = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.mp4(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
                if url != "":
                    url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": _url})
                    urltab.append({"name": "mp4", "url": url})
                hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]
                if hlsUrl != "":
                    hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": _url})
                    urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
        return urltab

    def parserHLSPLAYER(self, baseUrl):
        printDBG("parserHLSPLAYER baseUrl[%r]" % baseUrl)

        url = baseUrl.split("url=")[-1]
        url = urllib_unquote(url)

        urltab = []
        url = strwithmeta(url, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
        urltab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        return urltab

    def parserSTREAMLARE(self, baseUrl):
        printDBG("parserSTREAMLARE baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        urlParams = {"header": HTTP_HEADER}

        media_id = self.cm.ph.getSearchGroups(baseUrl + "/", "(?:e|v)[/-]([A-Za-z0-9]+)[^A-Za-z0-9]")[0]
        api_surl = "https://{0}/api/video/stream/get".format(urlparser.getDomain(baseUrl))
        post_data = {"id": media_id}
        sts, data = self.cm.getPage(api_surl, urlParams, post_data)
        if not sts:
            return False

        data = data.replace("\\/", "/")
        data = data.split("type")
        for item in data:
            videoUrl = self.cm.ph.getSearchGroups(item, r"""file['"]:\s?['"]([^"^']+?)['"]""")[0]
            videoUrl = strwithmeta(videoUrl, {"Referer": baseUrl})
            name = self.cm.ph.getSearchGroups(item, r"""label['"]:\s?['"]([^"^']+?)['"]""")[0]
            if videoUrl:
                params = {"name": name, "url": videoUrl}
                urltab.append(params)

        return urltab

    def parserFILEMOON(self, baseUrl):
        printDBG("parserFILEMOON baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        if "file_code" not in data:
            url = self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=['"]([^"^']+?)['"]""", 1, True)[0]
            if url != "":
                sts, data = self.cm.getPage(url, urlParams)
                if not sts:
                    return []

        if "eval(function(p,a,c,k,e,d)" in data:
            printDBG("Host resolveUrl packed")
            scripts = re.findall(r"(eval\s?\(function\(p,a,c,k,e,d.*?)</script>", data, re.S)
            for packed in scripts:
                data2 = packed
                printDBG("Host pack: [%s]" % data2)
                try:
                    data = unpackJSPlayerParams(data2, TEAMCASTPL_decryptPlayerParams, 0, True, True)
                    printDBG("OK unpack: [%s]" % data)
                except Exception:
                    pass

        r = re.search(r"""b:\s*'([^']+)',\s*file_code:\s*'([^']+)',\s*hash:\s*'([^']+)""", data)
        if r:
            url = "https://{0}/dl".format(urlparser.getDomain(baseUrl))
            post_data = {"b": r.group(1), "file_code": r.group(2), "hash": r.group(3)}
            sts, data = self.cm.getPage(url, urlParams, post_data)
            if not sts:
                return []
            data = data.replace(self.cm.ph.getDataBeetwenMarkers(data, 'tracks":[', "]", False)[1], "")
            vfile = self.cm.ph.getSearchGroups(data, r"""file['"]:\s?['"]([^"^']+?)['"]""")[0]
            seed = self.cm.ph.getSearchGroups(data, r"""seed['"]:\s?['"]([^"^']+?)['"]""")[0]
            hlsUrl = tear_decode(vfile, seed)
        else:
            hlsUrl = self.cm.ph.getSearchGroups(data, r"""["'](https?://[^'^"]+?\.m3u8(?:\?[^"^']+?)?)["']""", ignoreCase=True)[0]

        if hlsUrl != "":
            hlsUrl = strwithmeta(hlsUrl, {"Origin": "https://" + urlparser.getDomain(baseUrl), "Referer": baseUrl})
            urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

        return urltab

    def parserODYSEECOM(self, baseUrl):
        printDBG("parserODYSEECOM baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        urltab = []
        url = self.cm.ph.getSearchGroups(data, r"""contentUrl['"]:\s?['"]([^"^']+?)['"]""")[0]
        url = strwithmeta(url, {"Origin": urlparser.getDomain(baseUrl, False), "Referer": baseUrl})
        if url != "":
            urltab.append({"name": "mp4", "url": url})

        return urltab

    def parserSVETACDNIN(self, baseUrl):
        printDBG("parserSVETACDNIN baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        cUrl = self.cm.meta["url"]

        data = self.cm.ph.getSearchGroups(data, """id="files" value=['"]([^"^']+?)['"]""")[0]
        data = re.findall(r"\[(\d*p)\]([^,^\s]*)[,\s]", data)
        urltab = []
        for item in data:
            url = item[1].replace(r"\/", "/")
            if url.startswith("//"):
                url = "http:" + url
            url = strwithmeta(url, {"Origin": urlparser.getDomain(baseUrl, False), "Referer": cUrl})
            if url != "":
                urltab.append({"name": item[0], "url": url})

        return urltab

    def parserVIDMOLYME(self, baseUrl):
        printDBG("parserVIDMOLYME baseUrl[%r]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")

        baseUrl = strwithmeta(baseUrl)
        if "embed" not in baseUrl:
            video_id = self.cm.ph.getSearchGroups(baseUrl + "/", "/([A-Za-z0-9]{12})[/.]")[0]
            printDBG("parserVIDMOLYME video_id[%s]" % video_id)
            baseUrl = urlparser.getDomain(baseUrl, False) + "/embed-{0}.html".format(video_id)
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER})
        if not sts:
            return False
        cUrl = self.cm.meta["url"]

        if "<title>Please wait</title>" in data:
            sts, data = self.cm.getPage(baseUrl.replace(".me/", ".to/"), {"header": HTTP_HEADER})

        urltab = []
        url = self.cm.ph.getSearchGroups(data, """sources[^'^"]*?['"]([^'^"]+?)['"]""")[0]
        if url == "":
            url = self.cm.ph.getSearchGroups(data, """<iframe[^>]*?src=["'](http[^"^']+?)["']""", 1, True)[0]
            sts, data = self.cm.getPage(url, {"header": HTTP_HEADER})
            if not sts:
                return False
            cUrl = self.cm.meta["url"]
            url = self.cm.ph.getSearchGroups(data, """sources[^'^"]*?['"]([^'^"]+?)['"]""")[0]
        url = strwithmeta(url, {"Origin": urlparser.getDomain(cUrl, False), "Referer": cUrl})
        if url != "":
            urltab.extend(getDirectM3U8Playlist(url, checkContent=True, sortWithMaxBitrate=999999999))

        return urltab

    def parserWIKISPORTCLICK(self, baseUrl):
        printDBG("parserWIKISPORTCLICK baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        tmpUrl = self.cm.ph.getSearchGroups(data, """<iframe[^>]+?src=['"]([^"^']+?)['"]""", 1, True)[0]
        HTTP_HEADER["Referer"] = baseUrl
        urlParams = {"header": HTTP_HEADER}
        if tmpUrl == "":
            tmp = self.cm.ph.getAllItemsBeetwenNodes(data, ("<script", ">"), ("</script", ">"), False)
            tmp = "\n".join(tmp)
            scriptUrl = self.cm.ph.getSearchGroups(data, r"""<script[^>]+?src=['"]([^'^"]+?wiki\.js[^'^"]*?)['"]""")[0]
            if scriptUrl.startswith("//"):
                scriptUrl = "https:" + scriptUrl
            sts, data = self.cm.getPage(scriptUrl, urlParams)
            if not sts:
                return []
            if data != "" and tmp != "":
                jscode = base64.b64decode("""dmFyIG5hdmlnYXRvcj17dXNlckFnZW50OiJkZXNrdG9wIn07d2luZG93PXRoaXM7ZG9jdW1lbnQ9e307ZG9jdW1lbnQud3JpdGU9ZnVuY3Rpb24oKXtwcmludChhcmd1bWVudHNbMF0pO307YXRvYj1mdW5jdGlvbihlKXtlLmxlbmd0aCU0PT0zJiYoZSs9Ij0iKSxlLmxlbmd0aCU0PT0yJiYoZSs9Ij09IiksZT1EdWt0YXBlLmRlYygiYmFzZTY0IixlKSxkZWNUZXh0PSIiO2Zvcih2YXIgdD0wO3Q8ZS5ieXRlTGVuZ3RoO3QrKylkZWNUZXh0Kz1TdHJpbmcuZnJvbUNoYXJDb2RlKGVbdF0pO3JldHVybiBkZWNUZXh0fTs=""")
                jscode += tmp
                jscode += data
                ret = js_execute(jscode)
                if ret["sts"] and 0 == ret["code"]:
                    tmp = ret["data"].strip()
            tmpUrl = self.cm.ph.getSearchGroups(tmp, """<iframe[^>]+?src=['"]([^"^']+?)['"]""", 1, True)[0]
            sts, data = self.cm.getPage(tmpUrl, urlParams)
            if not sts:
                return []
            data = eval(re.findall(r"return\((\[.+?\])", data)[0])
            data = "".join(data).replace(r"\/", "/")
        else:
            sts, data = self.cm.getPage(tmpUrl, urlParams)
            if not sts:
                return []
            data = self.cm.ph.getSearchGroups(data, """source[^'^"]*?['"]([^'^"]+?)['"]""")[0]

        urltab = []
        if "m3u8" in data:
            if ":////" in data:
                data = data.replace(":////", "://")
            hlsUrl = strwithmeta(data, {"Origin": urlparser.getDomain(tmpUrl, False), "Referer": tmpUrl})
            urltab.extend(getDirectM3U8Playlist(hlsUrl, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
        return urltab

    def parserVIDGUARDTO(self, baseUrl):
        printDBG("parserVIDGUARDTO baseUrl[%s]" % baseUrl)

        def sig_decode(url):
            sig = url.split("sig=")[1].split("&")[0]
            t = ""
            for v in unhexlify(sig):
                t += chr((v if isinstance(v, int) else ord(v)) ^ 2)
            t = list(base64.b64decode(t + "==")[:-5][::-1])
            for i in range(0, len(t) - 1, 2):
                t[i + 1], t[i] = t[i], t[i + 1]
            t = "".join(chr((i if isinstance(i, int) else ord(i))) for i in t)
            url = url.replace(sig, "".join(t)[:-5])
            return url

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        baseUrl = baseUrl.replace("/v/", "/e/")
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        cUrl = self.cm.meta["url"]

        urltab = []
        r = re.search(r'eval\("window\.ADBLOCKER\s*=\s*false;\\n(.+?);"\);</script', data)
        if r:
            r = r.group(1).replace("\\u002b", "+")
            r = r.replace("\\u0027", "'")
            r = r.replace("\\u0022", '"')
            r = r.replace("\\/", "/")
            r = r.replace("\\\\", "\\")
            r = r.replace('\\"', '"')
            aa_decoded = aadecode.decode(r, alt=True)
            stream_url = json_loads(aa_decoded[11:]).get("stream")
            if stream_url:
                if isinstance(stream_url, list):
                    sources = [(x.get("Label"), x.get("URL")) for x in stream_url]
                    for item in sources:
                        url = item[1]
                        if not url.startswith("https://"):
                            url = re.sub(":/*", "://", url)
                        url = strwithmeta(sig_decode(url), {"Origin": urlparser.getDomain(baseUrl, False), "Referer": cUrl})
                        urltab.append({"name": item[0], "url": url})
                else:
                    url = strwithmeta(sig_decode(stream_url), {"Origin": urlparser.getDomain(baseUrl, False), "Referer": cUrl})
                    urltab.append({"name": "mp4", "url": url})

        return urltab

    def parserVOODCCOM(self, baseUrl):
        printDBG("parserVOODCCOM baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        urltab = []
        script = "https:" + re.findall(r'" src="(.+?)"', data)[0]
        split = script.split("/")
        embed_url = "https://voodc.com/player/d/%s/%s" % (split[-1], split[-2])
        sts, data = self.cm.getPage(embed_url, urlParams)
        if not sts:
            return []
        m3u8 = re.findall(r'"file": \'(.+?)\'', data)[0]
        if "m3u8" in data:
            urltab.extend(getDirectM3U8Playlist(m3u8, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))

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
                hlsUrl = "http:" + hlsUrl
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

    def parserSTREAMSILKCOM(self, baseUrl):
        printDBG("parserSTREAMSILKCOM baseUrl[%s]" % baseUrl)

        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer")
        if referer:
            HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []

        if "function(h,u,n,t,e,r)" in data:
            ff = re.findall(r'function\(h,u,n,t,e,r\).*?}\((".+?)\)\)', data, re.DOTALL)[0]
            ff = ff.replace('"', "")
            h, u, n, t, e, r = ff.split(",")
            data = dehunt(h, int(u), n, int(t), int(e), int(r))

        # printDBG("parserSTREAMSILKCOM data[%s]" % data)
        urltab = []
        url = self.cm.ph.getSearchGroups(data, r"""urlPlay\s*=\s*"\s*([^"^\s]+)""")[0]
        url = strwithmeta(url, {"Origin": urlparser.getDomain(baseUrl, False), "Referer": baseUrl})
        if url != "":
            if "m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url, checkExt=False, variantCheck=True, checkContent=True, sortWithMaxBitrate=99999999))
            else:
                urltab.append({"name": "mp4", "url": url})

        return urltab

    def parserVEEV(self, baseUrl):  # check 150625
        printDBG("parserVEEV baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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
        items = re.findall(r"""[\.\s'](?:fc|_vvto\[[^\]]*)(?:['\]]*)?\s*[:=]\s*['"]([^'"]+)""", data)
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
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserSBS(self, baseUrl):  # update 150825
        printDBG("parserSBS baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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
        urltab = []
        if hls:
            hls = urlparser.decorateUrl(hls, {"iptv_proto": "m3u8", "User-Agent": HTTP_HEADER["User-Agent"], "Referer": "https://%s/" % url, "Origin": "https://%s" % url})
            urltab.extend(getDirectM3U8Playlist(hls))
        return urltab

    def parserVINOVO(self, baseUrl):  # fix 15.06.25
        printDBG("parserVINOVO baseUrl[%s]" % baseUrl)
        COOKIE_FILE = self.COOKIE_PATH + "vinovo.cookie"
        HTTP_HEADER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"}
        sts, data = self.cm.getPage(baseUrl, {"header": HTTP_HEADER, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE})
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
        headers = self.cm.getDefaultHeader(browser="chrome")
        host = urlparser.getDomain(baseUrl, False)
        COOKIE_FILE = self.COOKIE_PATH + "streamembed.cookie"
        sts, data = self.cm.getPage(baseUrl, {"header": headers, "use_cookie": True, "save_cookie": True, "load_cookie": False, "cookiefile": COOKIE_FILE})
        if not sts:
            return []
        data = re.search(r"var\s*video\s*=\s*(.*?);\s", data)
        if data:
            headers.update({"Referer": baseUrl})
            data = json_loads(data.group(1))
            url = "{}m3u8/{}/{}/master.txt?s=1&id={}&cache=1".format(host, data.get("uid"), data.get("md5"), data.get("id"))
            headers["Referer"] = baseUrl
            headers["Accept"] = "*/*"
            url = urlparser.decorateUrl(url, {"header": headers, "use_cookie": True, "save_cookie": False, "load_cookie": True, "cookiefile": COOKIE_FILE})
            urltab.extend(getDirectM3U8Playlist(url))
        return urltab

    def parserJWPLAYER(self, baseUrl):  # update 230825
        printDBG("parserJWPLAYER baseUrl[%s]" % baseUrl)
        urltab = []
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        referer = baseUrl.meta.get("Referer", baseUrl)
        HTTP_HEADER["Referer"] = referer
        urlParams = {"header": HTTP_HEADER}
        if "mxdrop" in baseUrl or "mixdro" in baseUrl or "mixdrp" in baseUrl:
            baseUrl = baseUrl.replace(".co/", ".my/").replace(".club/", ".my/")
            baseUrl = "/".join(baseUrl.split("/")[:5]).replace("/f/", "/e/") if "/f/" in baseUrl else baseUrl
        if "hglink.to" in baseUrl:
            baseUrl = baseUrl.replace("hglink.to", "davioad.com")
        if "savefiles.com/e/" in baseUrl:
            baseUrl = baseUrl.replace("/e", "")
        if "savefiles.com/v/" in baseUrl:
            baseUrl = baseUrl.replace("/v", "")
        sts, data = self.cm.getPage(baseUrl, urlParams)
        if not sts:
            return []
        if "p,a,c,k,e" not in data and "mp4" not in data and "m3u8" not in data:
            src = re.search(r'(?:data-embed|iframe\s+src)="([^"]+)"', data)
            if src:
                sts, data = self.cm.getPage(src.group(1), urlParams)
                if not sts:
                    return []
        if "function(p,a,c,k,e" in data:
            printDBG("Host JSunpack")
            data = get_packed_data(data)
            if not data:
                return []
        host = urlparser.getDomain(baseUrl, False)
        url = re.search(r"""["']((?:https?:)?//[^'^"]+?\.(?:mp4|m3u8)(?:\?[^"^']+?)?)["']""", data)
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
                urltab.extend(getDirectM3U8Playlist(url))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserHEXLOAD(self, baseUrl):  # add 160625
        printDBG("parserHEXLOAD baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserSTREAMUP(self, baseUrl):  # update 070925
        printDBG("parserSTREAMUP baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        urltab = []
        subTracks = []
        host = urlparser.getDomain(baseUrl, False)
        sts, data = self.cm.getPage("%sajax/stream?filecode=%s" % (host, urlparse(baseUrl).path.strip("/")), HTTP_HEADER)
        if not sts:
            return []
        data = json_loads(data)
        url = data.get("streaming_url")
        subTracks = [{"title": "", "url": sub.get("file_path"), "lang": sub.get("language")} for sub in data.get("subtitles", []) if sub.get("file_path") and sub.get("language")]
        if url:
            url = urlparser.decorateUrl(url, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1], "external_sub_tracks": subTracks})
            if ".m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserVIDSRC(self, baseUrl):  # add 140925
        printDBG("parserVIDSRC baseUrl[%s]" % baseUrl)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        urltab = []
        baseUrl = baseUrl.replace("vidsrc.to", "vidsrc.xyz").replace("vidsrc.pm", "vidsrc.xyz")
        sts, data = self.cm.getPage(baseUrl, HTTP_HEADER)
        if not sts:
            return []
        url = re.search(r"""src=['"]([^"]+)['"] f""", data)
        if url:
            url = url.group(1)
            url = "https:" + url if url.startswith("//") else url
            host = urlparser.getDomain(url, False)
            sts, data = self.cm.getPage(url, HTTP_HEADER)
            if not sts:
                return []
        url = re.search(r""" src: ['"]([^'"]+)""", data)
        sts, data = self.cm.getPage(host + url.group(1), HTTP_HEADER)
        if not sts:
            return []
        url = re.search(r"""["']((?:https?:)?//[^'^"]+?\.(?:mp4|m3u8)(?:\?[^"^']+?)?)["']""", data)
        if url:
            url = urlparser.decorateUrl(url.group(1), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": host, "Origin": host[:-1]})
            if ".m3u8" in url:
                urltab.extend(getDirectM3U8Playlist(url))
            else:
                urltab.append({"name": "MP4", "url": url})
        return urltab

    def parserSHAREVIDEO(self, url):  # add 160925
        printDBG("parserSHAREVIDEO baseUrl[%s]" % url)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
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

    def parserf16px(self, url):  # add 121125 Partial support
        printDBG("parserf16px baseUrl[%s]" % url)
        HTTP_HEADER = self.cm.getDefaultHeader(browser="chrome")
        host = urlparser.getDomain(url, False)
        sts, data = self.cm.getPage(url.replace("/e/", "/api/videos/") + "/embed/playback", HTTP_HEADER)
        if not sts:
            return []
        urltab = []
        url = re.search('url":"([^"]+)', data)
        if url:
            url = host + url.group(1)
            urltab.append({"name": url, "url": url})
        return urltab
