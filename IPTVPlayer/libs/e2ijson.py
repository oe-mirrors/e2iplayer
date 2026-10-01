# -*- coding: utf-8 -*-
#
# Thin wrapper around the stdlib json module. The extra loads() keyword
# arguments are kept for call-site compatibility; they are no-ops now that
# the optional e2icjson C accelerator has been dropped.

import json


def loads(inputString, noneReplacement=None, baseTypesAsString=False, utf8=True):
    return json.loads(inputString)


# Non-raising variant for call sites that treat bad data as "no data".
# loads() keeps raising on purpose: most hosts use the exception to spot
# HTML/Cloudflare pages and empty bodies.
def loads_safe(inputString, default=None):
    try:
        return json.loads(inputString)
    except (ValueError, TypeError):
        return default


def dumps(inputString, *args, **kwargs):
    return json.dumps(inputString, *args, **kwargs)
