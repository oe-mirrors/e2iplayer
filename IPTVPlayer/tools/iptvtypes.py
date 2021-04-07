# -*- coding: utf-8 -*-
#

def enum(**enums):
    return type('Enum', (), enums)

# Posible args and values for strwithmeta used for url:

# If meta data exists the at least "iptv_proto" MUST by added to them
#   "iptv_proto":           "m3u8" | "f4m" | "mpd" | "rtmp" | "https" | "http" | "rtsp" | "merge"
#   "iptv_format":          "mp4" | "ts" | "flv" | "wmv" 
#   "iptv_urlwithlimit":    True | False
#   "iptv_livestream":      True | False
#   "iptv_bitrate":         number
#   "iptv_chank_url":       "http... link"
#   "iptv_audio_url"        "http... link"
#   "iptv_m3u8_custom_base_link" "http... link"
#   "iptv_m3u8_skip_seg"    0, 2, 3 - defaul 0 (sip first num of seg from first list)
#   "iptv_m3u8_live_start_index" segment index to start live streams at (negative values are from the end)
#   "iptv_m3u8_key_uri_replace_old" allow to replace part of AES key uri - old
#   "iptv_m3u8_key_uri_replace_new" allow to replace part of AES key uri - new
#   "iptv_proxy_gateway"    "http... link"
#   "iptv_refresh_cmd"      "refresh cmd line needed for some streams to keep playing"
#   "iptv_wget_continue"    True | False - default False 
#   "iptv_wget_timeout"     in second, default 30s when iptv_wget_continue == True
#   "iptv_wget_waitretry"   in second, default 1s when iptv_wget_continue == True
#   "iptv_audio_rep_idx"    audio representation index in mpd
#   "iptv_video_rep_idx"    video representation index in mpd

# Force buffering settings, generally this field should 
# be used only to materials that we know that they do 
# not work without buffering, or vice versa
#   "iptv_buffering":       "required" | "forbidden" 

#   "Host": http header field
#   "User-Agent": http header field
#   "Referer": http header field
#   "Cookie": http header field
#   "Accept": http header field
#   "Range": http header field
#   "Orgin": http header field
#   "Origin": http header field
#   "X-Forwarded-For": http header field
class strwithmeta(str):
    def __new__(cls, value, meta={}):
        obj = str.__new__(cls, value)
        obj.meta = {}
        if isinstance(value, strwithmeta):
            obj.meta = dict(value.meta)
        else:
            obj.meta = {}
        obj.meta.update(meta)
        return obj
