# macro to load functions from correct modules depending on the python version
# build to simplify loading modules in e2iplayer scripts
# just change:
#   from urlparse import
# to:
#   from Plugins.Extensions.IPTVPlayer.p2p3.UrlParse import
#

from Plugins.Extensions.IPTVPlayer.p2p3.pVer import isPY2

if isPY2():
    from urlparse import urljoin, urlparse, urlunparse, urlsplit, urlunsplit, parse_qs, parse_qsl
else:
    from urllib.parse import urljoin, urlparse, urlunparse, urlsplit, urlunsplit, parse_qs, parse_qsl
