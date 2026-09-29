# -*- coding: utf-8 -*-
#
# Thin wrapper around the stdlib json module. The extra loads() keyword
# arguments are kept for call-site compatibility; they are no-ops now that
# the optional e2icjson C accelerator has been dropped.

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import byteify, printExc
import json


def loads(inputString, noneReplacement=None, baseTypesAsString=False, utf8=True):
    try:
        outDict = json.loads(inputString)
    except json.JSONDecodeError:
        printExc()
        outDict = {}

    if utf8 or noneReplacement is not None or baseTypesAsString != False:
        return byteify(outDict, noneReplacement, baseTypesAsString)
    else:
        return outDict


def dumps(inputString, *args, **kwargs):
    return json.dumps(inputString, *args, **kwargs)
