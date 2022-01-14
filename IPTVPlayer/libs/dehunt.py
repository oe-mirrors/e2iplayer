# -*- coding: UTF-8 -*-
try:
    xrange
except Exception:
    xrange = range


def _0xe35c(d, e, f):# {
    g = list("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/")
    h = g[0:e]
    i = g[0:f]
    listad = list(d)[::-1]

    def redux(listad):
        j = 0
        for c in xrange(len(listad)):
            b = listad[c]
            if b in h:
                j += h.index(b) * (e**c)
        return j
    j = redux(listad)
    k = ''
    while j > 0:
        k = i[int(j % f)] + k
        j = (j - (int(j % f))) / f

    return int(k) if k else 0


def dehunt(h, u, n, t, e, r):# {
    r = ""
    i = 0

    while i < len(h):
        s = ''

        while h[i] != n[e]:
            try:
                ooo = chr(h[i])
            except:
                ooo = h[i]
            s += ooo#chr(h[i]);
            i += 1
        for j in xrange(len(n)):
            try:
                bbb = chr(n[j])
            except:
                bbb = n[j]
            s = s.replace(bbb, str(j))
        r += chr(_0xe35c(s, e, 10) - t)
        i += 1
    return r
