# coding=utf-8

import re
from Plugins.Extensions.IPTVPlayer.libs.pCommon import common

cm = common('', False)


def get_token(site_key, co, sa, loc):

    httpParams = {
            'header': {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip',
                'Referer': loc
            }
    }

    url1 = 'https://www.google.com/recaptcha/api.js'
    sts, data = cm.getPage(url1, httpParams)
    if not sts:
        return
    regex = r"releases\/(.*?)\/"
    v = re.findall(regex, data, re.MULTILINE)[0]
    cb = '123456789'

    url2 = "https://www.google.com/recaptcha/api2/anchor?ar=1&k=" + site_key + "&co=" + co + "&hl=ro&v=" + v + "&size=invisible&cb=" + cb

    sts, data = cm.getPage(url2, httpParams)
    if not sts:
        return

    data = data.replace('\x22', '')

    c = ''
    try:
        regex = r"recaptcha-token.*?=(.*?)>"
        c = re.findall(regex, data, re.MULTILINE)[0]
    except:
        print('error getting recaptcha-token')
        return

    url3 = "https://www.google.com/recaptcha/api2/reload?k=" + site_key

    post_data = {'v': v,
       'reason': 'q',
       'k': site_key,
       'c': c,
       'sa': sa,
       'co': co
    }

    httpParams = {
            'header': {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip',
                'Referer': url2
            }
    }

    sts, data = cm.getPage(url3, httpParams, post_data)
    if not sts:
        return
    regex = r"resp\",\"(.*?)\""
    token = re.findall(regex, data, re.MULTILINE)[0]
    return token
