# -*- coding: utf-8 -*-
""" crypto.common
    Common utility routines for crypto modules

    Copyright (c) 2002 by Paul A. Lambert
    Read LICENSE.txt for license information.
"""
import sys #required to catch PY2/PY3 and properly manage ord

def getOrdForVal(val):
    try:
        return ord(val) #usually py2 and py3 for strings
    except Exception:
        return val #py3 for binaries

def xorS(a, b):
    """ XOR two strings """
    assert len(a) == len(b)
    x = []
    for i in range(len(a)):
            x.append(chr(getOrdForVal(a[i]) ^ getOrdForVal(b[i])))
    return ''.join(x)


def xor(a, b):
    """ XOR two strings """
    x = []
    for i in range(min(len(a), len(b))):
        x.append(chr(getOrdForVal(a[i]) ^ getOrdForVal(b[i])))
    return ''.join(x)
