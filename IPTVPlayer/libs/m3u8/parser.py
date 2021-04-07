'''
M3U8 parser.

'''
import re
from collections import namedtuple

ext_x_targetduration = '#EXT-X-TARGETDURATION'
ext_x_media_sequence = '#EXT-X-MEDIA-SEQUENCE'
ext_x_key = '#EXT-X-KEY'
ext_x_stream_inf = '#EXT-X-STREAM-INF'
ext_x_version = '#EXT-X-VERSION'
ext_x_allow_cache = '#EXT-X-ALLOW-CACHE'
ext_x_endlist = '#EXT-X-ENDLIST'
extinf = '#EXTINF'
ext_x_program_date_time = '#EXT-X-PROGRAM-DATE-TIME'
ext_x_media = '#EXT-X-MEDIA'

'''
http://tools.ietf.org/html/draft-pantos-http-live-streaming-08#section-3.2
http://stackoverflow.com/questions/2785755/how-to-split-but-ignore-separators-in-quoted-strings-in-python
'''
ATTRIBUTELISTPATTERN = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')


def parse(content):
    '''
    Given a M3U8 playlist content returns a dictionary with all data found
    '''
    data = {
        'is_variant': False,
        'is_endlist': False,
        'playlists': [],
        'segments': [],
        'alt_media': {},
        }

    state = {
        'expect_segment': False,
        'expect_playlist': False,
        }

    for line in string_to_lines(content):
        line = line.strip()

        if line.startswith(ext_x_targetduration):
            _parse_simple_parameter(line, data, float)
        elif line.startswith(ext_x_media_sequence):
            _parse_simple_parameter(line, data, int)
        elif line.startswith(ext_x_version):
            _parse_simple_parameter(line, data)
        elif line.startswith(ext_x_allow_cache):
            _parse_simple_parameter(line, data)
        elif line.startswith(ext_x_media):
            _parse_alternate_media(line, data)
        elif line.startswith(ext_x_key):
            _parse_key(line, data)

        elif line.startswith(extinf):
            _parse_extinf(line, data, state)
            state['expect_segment'] = True

        elif line.startswith(ext_x_program_date_time):
            if state['expect_segment']:
                _parse_simple_parameter(line, state)

        elif line.startswith(ext_x_stream_inf):
            state['expect_playlist'] = True
            _parse_stream_inf(line, data, state)

        elif line.startswith(ext_x_endlist):
            data['is_endlist'] = True

        elif state['expect_segment']:
            _parse_ts_chunk(line, data, state)
            state['expect_segment'] = False

        elif state['expect_playlist']:
            _parse_variant_playlist(line, data, state)
            state['expect_playlist'] = False

    try:
        for playlist in data['playlists']:
            if 'audio' in playlist['stream_info']:
                if playlist['stream_info']['audio'] in data['alt_media']:
                    playlist['alt_audio_streams'] = data['alt_media'][playlist['stream_info']['audio']]
    except Exception:
        pass

    return data


def _parse_key(line, data):
    params = ATTRIBUTELISTPATTERN.split(line.replace(ext_x_key + ':', ''))[1::2]
    data['key'] = {}
    for param in params:
        name, value = param.split('=', 1)
        data['key'][normalize_attribute(name)] = remove_quotes(value)


def _parse_extinf(line, data, state):
    val = line.replace(extinf + ':', '').split(',')
    if len(val) > 1:
        title = val[1]
    else:
        title = ""

    state['segment'] = {'duration': float(val[0]), 'title': remove_quotes(title)}


def _parse_ts_chunk(line, data, state):
    segment = state.pop('segment')
    segment['uri'] = line
    data['segments'].append(segment)


def _parse_stream_inf(line, data, state):
    params = ATTRIBUTELISTPATTERN.split(line.replace(ext_x_stream_inf + ':', ''))[1::2]

    stream_info = {}
    for param in params:
        name, value = param.split('=', 1)
        stream_info[normalize_attribute(name)] = value

    if 'codecs' in stream_info:
        stream_info['codecs'] = remove_quotes(stream_info['codecs'])

    if 'audio' in stream_info:
        stream_info['audio'] = remove_quotes(stream_info['audio'])

    data['is_variant'] = True
    state['stream_info'] = stream_info


def _parse_alternate_media(line, data):
    params = ATTRIBUTELISTPATTERN.split(line.replace(ext_x_media + ':', ''))[1::2]

    normalize_params = {}
    for param in params:
        name, value = param.split('=', 1)
        normalize_params[normalize_attribute(name)] = remove_quotes(value)

    # skip alternative audio if it does not have URI to media playlist attrib
    if normalize_params.get('type', '').upper() == 'AUDIO' and not normalize_params.get('uri', None):
        return

    group = remove_quotes(normalize_params.pop('group_id', None))
    if group:
        if group not in data['alt_media']:
            data['alt_media'][group] = []
        if normalize_params.get('default') == "YES":
            data['alt_media'][group].insert(0, normalize_params)
        else:
            data['alt_media'][group].append(normalize_params)


def _parse_variant_playlist(line, data, state):
    stream_info = state.pop('stream_info')
    playlist = {'uri': line,
                'stream_info': stream_info,
                'alt_audio_streams': []}
    data['playlists'].append(playlist)


def _parse_simple_parameter(line, data, cast_to=str):
    param, value = line.split(':', 1)
    param = normalize_attribute(param.replace('#EXT-X-', ''))
    value = normalize_attribute(value)
    data[param] = cast_to(value)


def string_to_lines(string):
    return string.strip().replace('\r\n', '\n').split('\n')


def remove_quotes(string):
    '''
    Remove quotes from string.

    Ex.:
      "foo" -> foo
      'foo' -> foo
      'foo  -> 'foo

    '''
    quotes = ('"', "'")
    if string and string[0] in quotes and string[-1] in quotes:
        return string[1:-1]
    return string


def normalize_attribute(attribute):
    return attribute.replace('-', '_').lower().strip()


def is_url(uri):
    return re.match(r'https?://', uri) is not None
