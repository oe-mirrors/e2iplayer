# macro to load functions from correct modules depending on the python version
# build to simplify loading modules in e2iplayer scripts
# just change:
#   from urlib import
# to:
#   from Plugins.Extensions.IPTVPlayer.p2p3.UrlLib import 
#


from urllib.request import addinfourl     as urllib_addinfourl,           BaseHandler         as urllib2_BaseHandler, \
                            build_opener   as urllib2_build_opener,        HTTPCookieProcessor as urllib2_HTTPCookieProcessor, \
                            HTTPHandler    as urllib2_HTTPHandler,         HTTPRedirectHandler as urllib2_HTTPRedirectHandler, \
                            HTTPSHandler   as urllib2_HTTPSHandler,        ProxyHandler        as urllib2_ProxyHandler, \
                            Request        as urllib2_Request,             urlopen             as urllib2_urlopen, \
                            urlopen        as urllib_urlopen,              urlretrieve         as urllib_urlretrieve, \
                            install_opener as urllib2_install_opener

from urllib.parse import quote            as urllib_quote,                quote_plus          as urllib_quote_plus, \
                            unquote          as urllib_unquote,              unquote_plus        as urllib_unquote_plus, \
                            urlencode           as urllib_urlencode

from urllib.error import HTTPError        as urllib2_HTTPError,           URLError            as urllib2_URLError
