
from collections import namedtuple
import urllib.parse

from . import parser


class M3U8(object):
    '''
    Represents a single M3U8 playlist. Should be instantiated with
    the content as string.

    Parameters:

     `content`
       the m3u8 content as string

     `base_uri`
      directory uri the playlist comes from (with a trailing slash, see
      `inits`). Relative segment / playlist / rendition uris are resolved
      against it by `absolute_uri`.

    Attributes:

     `key`
       it's a `Key` object, the EXT-X-KEY from m3u8. Or None

     `segments`
       list of `Segment`s of a media playlist

     `is_variant`
        True if this M3U8 is a master playlist with links to other M3U8s
        with different bitrates; `playlists` is then the list of them.

     `is_endlist`
        True if the EXT-X-ENDLIST tag is present (VOD, not live).

      `target_duration`, `media_sequence`, `version`, `allow_cache`
        the values of the simple EXT-X-* tags (or None)

    Only reading is supported - the playlist is never written back.
    '''

    simple_attributes = (
        # obj attribute      # parser attribute
        ('is_variant', 'is_variant'),
        ('is_endlist', 'is_endlist'),
        ('target_duration', 'targetduration'),
        ('media_sequence', 'media_sequence'),
        ('version', 'version'),
        ('allow_cache', 'allow_cache'),
        )

    def __init__(self, content=None, base_uri=None, uri=None):
        if content is not None:
            self.data = parser.parse(content, uri)
        else:
            self.data = {}
        self.base_uri = base_uri
        self._initialize_attributes()

    def _initialize_attributes(self):
        self.key = Key(base_uri=self.base_uri, **self.data['key']) if 'key' in self.data else None
        self.segments = [Segment(base_uri=self.base_uri, **params)
                         for params in self.data.get('segments', [])]

        for attr, param in self.simple_attributes:
            setattr(self, attr, self.data.get(param))

        self.playlists = [Playlist(base_uri=self.base_uri, **playlist)
                          for playlist in self.data.get('playlists', [])]


class BasePathMixin(object):

    @property
    def absolute_uri(self):
        if self.uri is None:
            return None
        if parser.is_url(self.uri):
            uri = self.uri
        else:
            if self.base_uri is None:
                raise ValueError('There can not be `absolute_uri` with no `base_uri` set')
            # Plain RFC 3986 join. `base_uri` is expected to carry a trailing
            # slash (see `M3U8` / `inits`), so a relative playlist/segment path
            # resolves against the playlist directory. Unlike the old
            # os.path.normpath() approach this keeps query strings intact even
            # when a signed token contains slashes (e.g. `?hdnts=...~acl=/*~`).
            uri = urllib.parse.urljoin(self.base_uri, self.uri)

        # BBC web-proxy passthrough (config.plugins.iptvplayer.bbc_use_web_proxy):
        # if the playlist was fetched through the proxy, keep its children on it.
        proxyUri = 'englandproxy.co.uk'
        if self.base_uri and proxyUri in self.base_uri and proxyUri not in uri:
            try:
                uri = 'http://www.englandproxy.co.uk/' + uri[uri.find('://') + 3:]
            except Exception:
                pass
        return uri


class Segment(BasePathMixin):
    '''
    A video segment from a M3U8 playlist

    `uri`
      a string with the segment uri

    `title`
      title attribute from EXTINF parameter

    `duration`
      duration attribute from EXTINF paramter

    `program_date_time`
      program date from EXT-X-PROGRAM-DATE-TIME paramter
    '''

    def __init__(self, uri, base_uri, duration=None, title=None, program_date_time=None):
        self.uri = uri
        self.program_date_time = program_date_time
        self.duration = duration
        self.title = title
        self.base_uri = base_uri


class Key(BasePathMixin):
    '''
    Key used to encrypt the segments in a m3u8 playlist (EXT-X-KEY)

    `method`
      is a string. ex.: "AES-128"

    `uri`
      is a string. ex:: "https://priv.example.com/key.php?r=52"

    `iv`
      initialization vector. a string representing a hexadecimal number. ex.: 0X12A
    '''

    def __init__(self, method=None, uri=None, base_uri=None, iv=None, **kwargs):
        self.method = method
        self.uri = uri
        self.iv = iv
        self.base_uri = base_uri
        # KEYFORMAT / KEYFORMATVERSIONS and other modern EXT-X-KEY attributes
        # are kept but not acted on - swallowing them here keeps a media
        # playlist with e.g. Widevine/FairPlay keys from aborting the parse.
        self.extra_params = kwargs


class AudioStream(BasePathMixin):
    '''
    An alternate AUDIO rendition (EXT-X-MEDIA:TYPE=AUDIO). `uri` is None for a
    rendition that is muxed into the variant stream itself.
    '''

    def __init__(self, uri, name, language, base_uri, channels=None, characteristics=None, default=None, forced=None):

        self.uri = uri
        self.base_uri = base_uri
        self.language = language
        self.name = name
        self.channels = channels
        self.characteristics = characteristics
        self.default = (default == 'YES')
        self.forced = (forced == 'YES')


class SubtitleStream(BasePathMixin):
    '''
    An alternate SUBTITLES rendition referenced from a variant playlist
    (EXT-X-MEDIA:TYPE=SUBTITLES). `uri` points to the WebVTT media playlist.
    '''

    def __init__(self, uri, name, language, base_uri, forced=None, default=None, characteristics=None):

        self.uri = uri
        self.base_uri = base_uri
        self.language = language
        self.name = name
        self.characteristics = characteristics
        self.forced = (forced == 'YES')
        self.default = (default == 'YES')


def _audio_streams(base_uri, streams):
    return [AudioStream(base_uri=base_uri, uri=s.get('uri'), name=s.get('name'), language=s.get('language'),
                        channels=s.get('channels'), characteristics=s.get('characteristics'),
                        default=s.get('default'), forced=s.get('forced'))
            for s in (streams or [])]


class Playlist(BasePathMixin):
    '''
    Playlist object representing a link to a variant M3U8 with a specific bitrate.
    Each `stream_info` attribute has: `program_id`, `bandwidth`, `resolution` and `codecs`
    `resolution` is a tuple (h, v) of integers

    `alt_audio_streams`: the AUDIO renditions of its group that have their own uri
    `muxed_audio_streams`: the AUDIO renditions of its group without uri, i.e. the
    audio already contained in this variant (normally one, the original language)

    More info: http://tools.ietf.org/html/draft-pantos-http-live-streaming-07#section-3.3.10
    '''

    def __init__(self, uri, stream_info, alt_audio_streams=None, subtitle_streams=None, base_uri=None, muxed_audio_streams=None):

        self.uri = uri
        self.base_uri = base_uri

        resolution = stream_info.get('resolution')
        if resolution is not None:
            try:
                values = str(resolution).replace('"', '').split('x')
                resolution_pair = (int(values[0]), int(values[1]))
            except Exception:
                resolution_pair = None
        else:
            resolution_pair = None

        self.stream_info = StreamInfo(bandwidth=stream_info.get('bandwidth'),
                                      average_bandwidth=stream_info.get('average_bandwidth'),
                                      program_id=stream_info.get('program_id'),
                                      resolution=resolution_pair,
                                      codecs=stream_info.get('codecs'),
                                      frame_rate=stream_info.get('frame_rate'),
                                      video_range=stream_info.get('video_range'),
                                      audio=stream_info.get('audio'),
                                      subtitles=stream_info.get('subtitles'),
                                      supplemental_codecs=stream_info.get('supplemental_codecs'),
                                      pathway_id=stream_info.get('pathway_id'))
        self.alt_audio_streams = _audio_streams(self.base_uri, alt_audio_streams)
        self.muxed_audio_streams = _audio_streams(self.base_uri, muxed_audio_streams)
        self.subtitle_streams = [SubtitleStream(base_uri=self.base_uri, uri=s.get('uri'), name=s.get('name'), language=s.get('language'),
                                                forced=s.get('forced'), default=s.get('default'), characteristics=s.get('characteristics'))
                                    for s in (subtitle_streams or [])]


StreamInfo = namedtuple('StreamInfo', ['bandwidth', 'average_bandwidth', 'program_id',
                                       'resolution', 'codecs', 'frame_rate', 'video_range',
                                       'audio', 'subtitles', 'supplemental_codecs', 'pathway_id'])
