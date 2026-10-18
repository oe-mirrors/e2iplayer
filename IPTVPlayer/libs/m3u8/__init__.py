
import urllib.parse

from .model import M3U8, Playlist
from .parser import parse

__all__ = 'M3U8', 'Playlist', 'inits', 'parse'


def _dir_base_uri(uri):
    '''
    Directory the playlist lives in, with a trailing slash, so relative
    child URIs resolve with a plain urljoin(). Query string is dropped.
    '''
    return urllib.parse.urljoin(uri, '.')


def inits(content, uri):
    '''
    Given a string with a m3u8 content and uri from which
    this content was downloaded returns a M3U8 object.
    (The playlist itself is always fetched by the caller through pCommon.)
    '''
    base_uri = _dir_base_uri(uri) if uri else None
    return M3U8(content, base_uri=base_uri, uri=uri)
