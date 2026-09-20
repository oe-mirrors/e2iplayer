# -*- coding: utf-8 -*-
from __future__ import absolute_import

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.p2p3.manipulateStrings import ensure_binary
###################################################

###################################################
# FOREIGN import
###################################################
import struct
import zlib
###################################################

# Byte mode, error correction L, mask 0, one data block. The smallest of these
# versions that holds the text is used: (size, data codewords, ECC codewords,
# alignment pattern centres) - v3 holds 53 bytes, v4 78, v5 106.
_VERSIONS = (
    (29, 55, 15, (6, 22)),
    (33, 80, 20, (6, 26)),
    (37, 108, 26, (6, 30)),
)
_MAX_BYTES = _VERSIONS[-1][1] - 2
_MASK = 0


def _gf_mul(x, y):
    z = 0
    while y:
        if y & 1:
            z ^= x
        y >>= 1
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    return z


def _rs_generator(degree):
    gen = [1]
    root = 1
    for _ in range(degree):
        out = [0] * (len(gen) + 1)
        for i, coef in enumerate(gen):
            out[i] ^= coef
            out[i + 1] ^= _gf_mul(coef, root)
        gen = out
        root = _gf_mul(root, 2)
    return gen


def _rs_remainder(data, degree):
    gen = _rs_generator(degree)
    rem = [0] * degree
    for value in data:
        factor = value ^ rem[0]
        rem = rem[1:] + [0]
        for i in range(degree):
            rem[i] ^= _gf_mul(gen[i + 1], factor)
    return rem


def _append_bits(bits, value, length):
    for i in range(length - 1, -1, -1):
        bits.append((value >> i) & 1)


def _pick_version(raw):
    for version in _VERSIONS:
        if len(raw) <= version[1] - 2:  # 4 bit mode + 8 bit length = 12 bits of header
            return version
    raise ValueError("text too long for a QR code (max %d bytes, got %d)" % (_MAX_BYTES, len(raw)))


def _codewords(raw, dataCodewords, eccCodewords):
    bits = []
    _append_bits(bits, 0x4, 4)  # byte mode
    _append_bits(bits, len(raw), 8)
    for value in bytearray(raw):
        _append_bits(bits, value, 8)
    capacity = dataCodewords * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    while len(bits) % 8:
        bits.append(0)
    data = []
    for pos in range(0, len(bits), 8):
        value = 0
        for bit in bits[pos:pos + 8]:
            value = (value << 1) | bit
        data.append(value)
    pads = (0xEC, 0x11)
    n = 0
    while len(data) < dataCodewords:
        data.append(pads[n & 1])
        n += 1
    return data + _rs_remainder(data, eccCodewords)


def _bch_digit(value):
    digit = 0
    while value:
        digit += 1
        value >>= 1
    return digit


def _format_bits():
    # Error correction L is encoded as 01; mask 0.
    g15 = (1 << 10) | (1 << 8) | (1 << 5) | (1 << 4) | (1 << 2) | (1 << 1) | 1
    g15_mask = (1 << 14) | (1 << 12) | (1 << 10) | (1 << 4) | (1 << 1)
    data = (1 << 3) | _MASK
    value = data << 10
    while _bch_digit(value) - _bch_digit(g15) >= 0:
        value ^= g15 << (_bch_digit(value) - _bch_digit(g15))
    return ((data << 10) | value) ^ g15_mask


_FORMAT_BITS = _format_bits()  # ECC level and mask are both fixed, so this never changes


def _matrix(text):
    raw = ensure_binary(text)
    size, dataCodewords, eccCodewords, centres = _pick_version(raw)
    modules = [[None] * size for _ in range(size)]

    def finder(row, col):
        for rr in range(-1, 8):
            y = row + rr
            if y <= -1 or y >= size:
                continue
            for cc in range(-1, 8):
                x = col + cc
                if x <= -1 or x >= size:
                    continue
                dark = ((0 <= rr <= 6 and cc in (0, 6)) or
                        (0 <= cc <= 6 and rr in (0, 6)) or
                        (2 <= rr <= 4 and 2 <= cc <= 4))
                modules[y][x] = dark

    finder(0, 0)
    finder(size - 7, 0)
    finder(0, size - 7)

    # Overlapping finder positions skip.
    for row in centres:
        for col in centres:
            if modules[row][col] is not None:
                continue
            for rr in range(-2, 3):
                for cc in range(-2, 3):
                    modules[row + rr][col + cc] = (
                        rr in (-2, 2) or cc in (-2, 2) or (rr == 0 and cc == 0)
                    )

    for row in range(8, size - 8):
        if modules[row][6] is None:
            modules[row][6] = (row % 2 == 0)
    for col in range(8, size - 8):
        if modules[6][col] is None:
            modules[6][col] = (col % 2 == 0)

    bits = _FORMAT_BITS
    for i in range(15):
        dark = ((bits >> i) & 1) == 1
        if i < 6:
            modules[i][8] = dark
        elif i < 8:
            modules[i + 1][8] = dark
        else:
            modules[size - 15 + i][8] = dark
    for i in range(15):
        dark = ((bits >> i) & 1) == 1
        if i < 8:
            modules[8][size - i - 1] = dark
        elif i < 9:
            modules[8][15 - i] = dark
        else:
            modules[8][14 - i] = dark
    modules[size - 8][8] = True

    data = _codewords(raw, dataCodewords, eccCodewords)
    inc = -1
    row = size - 1
    bit_index = 7
    byte_index = 0
    for original_col in range(size - 1, 0, -2):
        col = original_col
        if col <= 6:
            col -= 1
        while True:
            for current_col in (col, col - 1):
                if modules[row][current_col] is None:
                    dark = False
                    if byte_index < len(data):
                        dark = ((data[byte_index] >> bit_index) & 1) == 1
                    if (row + current_col) % 2 == 0:  # mask 0
                        dark = not dark
                    modules[row][current_col] = dark
                    bit_index -= 1
                    if bit_index == -1:
                        byte_index += 1
                        bit_index = 7
            row += inc
            if row < 0 or row >= size:
                row -= inc
                inc = -inc
                break
    return modules


def _png_chunk(name, payload):
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)


def make_qr_png(text, path, scale=9, border=4):
    matrix = _matrix(text)
    size = len(matrix)
    width = (size + border * 2) * scale
    rows = []
    for y in range(-border, size + border):
        line = bytearray()
        for x in range(-border, size + border):
            dark = 0 <= y < size and 0 <= x < size and bool(matrix[y][x])
            value = 0 if dark else 255
            line.extend([value] * scale)
        raw = bytes(line)
        for _ in range(scale):
            rows.append(b"\x00" + raw)  # grayscale, filter 0
    payload = b"".join(rows)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, width, 8, 0, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(payload, 9))
    png += _png_chunk(b"IEND", b"")

    with open(path, "wb") as handle:
        handle.write(png)
    return path
