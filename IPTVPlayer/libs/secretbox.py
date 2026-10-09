# -*- coding: utf-8 -*-
# Added: 09.10.2026 - pure-python NaCl / libsodium crypto_secretbox (XSalsa20-Poly1305), py2.7 + py3
#   used by urlparser.parserVIDLINK to build the vidlink.pro request token on the box (the site's
#   fu.wasm calls crypto_secretbox_easy). Plain integer arithmetic, only meant for tiny payloads
#   (ids, tokens), not for bulk data.
import struct

_MASK = 0xffffffff
_SIGMA = struct.unpack("<4I", b"expand 32-byte k")


def _rotl(v, c):
    return ((v << c) & _MASK) | (v >> (32 - c))


def _salsa_rounds(x):
    for _ in range(10):
        # column round
        x[4] ^= _rotl((x[0] + x[12]) & _MASK, 7)
        x[8] ^= _rotl((x[4] + x[0]) & _MASK, 9)
        x[12] ^= _rotl((x[8] + x[4]) & _MASK, 13)
        x[0] ^= _rotl((x[12] + x[8]) & _MASK, 18)
        x[9] ^= _rotl((x[5] + x[1]) & _MASK, 7)
        x[13] ^= _rotl((x[9] + x[5]) & _MASK, 9)
        x[1] ^= _rotl((x[13] + x[9]) & _MASK, 13)
        x[5] ^= _rotl((x[1] + x[13]) & _MASK, 18)
        x[14] ^= _rotl((x[10] + x[6]) & _MASK, 7)
        x[2] ^= _rotl((x[14] + x[10]) & _MASK, 9)
        x[6] ^= _rotl((x[2] + x[14]) & _MASK, 13)
        x[10] ^= _rotl((x[6] + x[2]) & _MASK, 18)
        x[3] ^= _rotl((x[15] + x[11]) & _MASK, 7)
        x[7] ^= _rotl((x[3] + x[15]) & _MASK, 9)
        x[11] ^= _rotl((x[7] + x[3]) & _MASK, 13)
        x[15] ^= _rotl((x[11] + x[7]) & _MASK, 18)
        # row round
        x[1] ^= _rotl((x[0] + x[3]) & _MASK, 7)
        x[2] ^= _rotl((x[1] + x[0]) & _MASK, 9)
        x[3] ^= _rotl((x[2] + x[1]) & _MASK, 13)
        x[0] ^= _rotl((x[3] + x[2]) & _MASK, 18)
        x[6] ^= _rotl((x[5] + x[4]) & _MASK, 7)
        x[7] ^= _rotl((x[6] + x[5]) & _MASK, 9)
        x[4] ^= _rotl((x[7] + x[6]) & _MASK, 13)
        x[5] ^= _rotl((x[4] + x[7]) & _MASK, 18)
        x[11] ^= _rotl((x[10] + x[9]) & _MASK, 7)
        x[8] ^= _rotl((x[11] + x[10]) & _MASK, 9)
        x[9] ^= _rotl((x[8] + x[11]) & _MASK, 13)
        x[10] ^= _rotl((x[9] + x[8]) & _MASK, 18)
        x[12] ^= _rotl((x[15] + x[14]) & _MASK, 7)
        x[13] ^= _rotl((x[12] + x[15]) & _MASK, 9)
        x[14] ^= _rotl((x[13] + x[12]) & _MASK, 13)
        x[15] ^= _rotl((x[14] + x[13]) & _MASK, 18)
    return x


def _setup(key, n16):
    k = struct.unpack("<8I", key)
    n = struct.unpack("<4I", n16)
    return [_SIGMA[0], k[0], k[1], k[2], k[3], _SIGMA[1], n[0], n[1],
            n[2], n[3], _SIGMA[2], k[4], k[5], k[6], k[7], _SIGMA[3]]


def _hsalsa20(key, n16):
    x = _salsa_rounds(_setup(key, n16))
    return struct.pack("<8I", x[0], x[5], x[10], x[15], x[6], x[7], x[8], x[9])


def _salsa20_stream(key, n8, length):
    out = []
    for ctr in range((length + 63) // 64):
        inp = _setup(key, n8 + struct.pack("<Q", ctr))
        x = _salsa_rounds(list(inp))
        out.append(struct.pack("<16I", *[(x[i] + inp[i]) & _MASK for i in range(16)]))
    return b"".join(out)[:length]


def _le(b):
    v = 0
    for c in reversed(bytearray(b)):
        v = (v << 8) | c
    return v


def _tole(v, n):
    return bytes(bytearray((v >> (8 * i)) & 0xff for i in range(n)))


def _poly1305(key, msg):
    r = _le(key[:16]) & 0x0ffffffc0ffffffc0ffffffc0fffffff
    s = _le(key[16:32])
    p = (1 << 130) - 5
    acc = 0
    for i in range(0, len(msg), 16):
        acc = ((acc + _le(msg[i:i + 16] + b"\x01")) * r) % p
    return _tole((acc + s) & ((1 << 128) - 1), 16)


def _xor(a, b):
    return bytes(bytearray(x ^ y for x, y in zip(bytearray(a), bytearray(b))))


def secretbox(msg, nonce, key):
    """crypto_secretbox_easy: returns MAC(16) + ciphertext; nonce 24 bytes, key 32 bytes"""
    subkey = _hsalsa20(key, nonce[:16])
    stream = _salsa20_stream(subkey, nonce[16:24], 32 + len(msg))
    ct = _xor(msg, stream[32:])
    return _poly1305(stream[:32], ct) + ct


def secretbox_open(box, nonce, key):
    """crypto_secretbox_open_easy: box = MAC(16) + ciphertext; raises ValueError on a bad MAC"""
    subkey = _hsalsa20(key, nonce[:16])
    mac, ct = box[:16], box[16:]
    stream = _salsa20_stream(subkey, nonce[16:24], 32 + len(ct))
    if _poly1305(stream[:32], ct) != mac:
        raise ValueError("secretbox: bad MAC")
    return _xor(ct, stream[32:])
