# -*- encoding: utf-8 -*-
import socket
import hashlib
import hmac
import time
import urllib
import urllib2
import base64
import sys
import traceback
from BaseHTTPServer import BaseHTTPRequestHandler
try:    import json
except Exception: import simplejson as json
from binascii import hexlify
import threading

import signal
import os
def signal_handler(sig, frame):
    os.kill(os.getpid(), signal.SIGTERM)
signal.signal(signal.SIGINT, signal_handler)

LAST_HTTP_ERROR_CODE =  -1
LAST_HTTP_ERROR_DATA =  ''

def updateStatus(type, data, code=None):
    obj = {'type':type, 'data':data, 'code':code}
    sys.stderr.write('\n%s\n' % json.dumps(obj).encode('utf-8'))

DEBUGE = False 

def printDBG(strDat):
    if DEBUGE:
        print("%s" % strDat)

def printExc(msg=''):
    printDBG("===============================================")
    printDBG("                   EXCEPTION                   ")
    printDBG("===============================================")
    msg = msg + ': \n%s' % traceback.format_exc()
    printDBG(msg)
    printDBG("===============================================")

def getPage(url, headers={}, post_data=None):
    printDBG('url [%s]' % url)
    customOpeners = []
    
    try:
        ctx = ssl._create_unverified_context()
        customOpeners.append(urllib2.HTTPSHandler(context=ctx))
    except Exception:
        pass
    
    sts = 0
    data = ''
    try:
        req = urllib2.Request(url)
        for key in headers:
            req.add_header(key, headers[key])
        
        printDBG("++++HEADERS START++++")
        printDBG(req.headers)
        printDBG("++++HEADERS END++++")
        
        opener = urllib2.build_opener( *customOpeners )
        response = opener.open(req)
        data = response.read()
        sts = response.getcode()
    except urllib2.HTTPError, e:
        global LAST_HTTP_ERROR_CODE
        global LAST_HTTP_ERROR_DATA
        LAST_HTTP_ERROR_CODE = e.code
        LAST_HTTP_ERROR_DATA = e.fp.read()
        sts = LAST_HTTP_ERROR_CODE
        data = LAST_HTTP_ERROR_DATA
        printExc()
    except Exception:
        printExc()
    return sts, data 

def _fromhex(hex):
    if sys.version_info < (2,7,0):
        return hex.decode('hex')
    else:
        return bytearray.fromhex(hex)

class MYJDException(BaseException):
    pass

class Jddevice:
    def __init__(self, jd, device_dict):
        self.name = device_dict["name"]
        self.device_id = device_dict["id"]
        self.device_type = device_dict["type"]
        self.myjd = jd
    
    def action(self, path, params=(), http_action="POST"):
        action_url = self.__action_url()
        response = self.myjd.request_api(path, http_action, params, action_url)
        if response is None:
            return False
        return response['data']

    def __action_url(self):
        return "/t_"+self.myjd.get_session_token()+"_"+self.device_id

def decrypt(secret_token, data):
    iv = secret_token[:len(secret_token)//2]
    key = secret_token[len(secret_token)//2:]
    
    cipher = AES_CBC(key=key, keySize=16)
    decrypted_data = cipher.decrypt(base64.b64decode(data), iv).strip()
    
    return decrypted_data

def encrypt(secret_token, data):
    data = data.encode('utf-8')
    iv = secret_token[:len(secret_token)//2]
    key = secret_token[len(secret_token)//2:]
    
    cipher = AES_CBC(key=key, keySize=16)
    encrypted_data = base64.b64encode(cipher.encrypt(data, iv)) 
    
    return encrypted_data

class Myjdapi:
    def __init__(self):
        self._request_id = int(time.time()*1000)
        self._api_url = "http://api.jdownloader.org"
        self._app_key = "http://git.io/vmcsk"
        self._api_version = 1
        self._devices = None
        self._login_secret = None
        self._device_secret = None
        self._session_token = None
        self._regain_token = None
        self._server_encryption_token = None
        self._device_encryption_token = None
        self._connected = False
        
    def get_device_secret(self):
        return self._device_secret

    def get_session_token(self):
        return self._session_token

    def get_server_encryption_token(self):
        return self._server_encryption_token
        
    def get_device_encryption_token(self):
        return self._device_encryption_token

    def is_connected(self):
        return self._connected

    def set_app_key(self, app_key):
        self._app_key = app_key

    def __secret_create(self, email, password, domain):
        secret_hash = hashlib.sha256()
        secret_hash.update(email.lower().encode('utf-8') + password.encode('utf-8') + \
                    domain.lower().encode('utf-8'))
        return secret_hash.digest()

    def _update_encryption_tokens(self):
        if self._server_encryption_token is None:
            old_token = self._login_secret
        else:
            old_token = self._server_encryption_token
        new_token = hashlib.sha256()
        new_token.update(old_token + _fromhex(self._session_token))
        self._server_encryption_token = new_token.digest()
        new_token = hashlib.sha256()
        new_token.update(self._device_secret + _fromhex(self._session_token))
        self._device_encryption_token = new_token.digest()

    def _signature_create(self,key,data):
        signature = hmac.new(key, data.encode('utf-8'), hashlib.sha256)
        return signature.hexdigest()
    
    def _decrypt(self, secret_token, data):
        return decrypt(secret_token, data)

    def _encrypt(self, secret_token, data):
        return encrypt(secret_token, data)

    def update_request_id(self):
        self._request_id = int(time.time())

    def connect(self, email, password):
        self._login_secret = self.__secret_create(email, password, "server")
        self._device_secret = self.__secret_create(email, password, "device")
        response = self.request_api("/my/connect", "GET",[("email", email), ("appkey", self._app_key)])
        self._connected = True
        self.update_request_id()
        self._session_token = response["sessiontoken"]
        self._regain_token = response["regaintoken"]
        self._update_encryption_tokens()

    def reconnect(self):
        response = self.request_api("/my/reconnect", "GET",[("sessiontoken", self._session_token), ("regaintoken", self._regain_token)])
        self.update_request_id()
        self._session_token = response["sessiontoken"]
        self._regain_token = response["regaintoken"]
        self._update_encryption_tokens()

    def disconnect(self):
        response = self.request_api("/my/disconnect", "GET", [("sessiontoken", self._session_token)])
        self.update_request_id()
        self._login_secret = None
        self._device_secret = None
        self._session_token = None
        self._regain_token = None
        self._server_encryption_token = None
        self._device_encryption_token = None
        self._devices = None
        self._connected = False

    def update_devices(self):
        response = self.request_api("/my/listdevices", "GET",[("sessiontoken",self._session_token)])
        self.update_request_id()
        self._devices = response["list"]

    def request_api(self, path, http_method="GET",params=None, action=None):
        data = None
        if not self.is_connected() and path != "/my/connect":
            raise(MYJDException("No connection established\n"))
        if http_method == "GET":
            query = [path + "?"]
            for param in params:
                if param[0] != "encryptedLoginSecret":
                    query += ["%s=%s" % (param[0], urllib.quote(param[1]))]
                else:
                    query += ["&%s=%s" % (param[0], param[1])]
            query += ["rid="+str(self._request_id)]
            if self._server_encryption_token is None:
                query += ["signature=" + \
                          str(self._signature_create(self._login_secret, query[0]+"&".join(query[1:])))]
            else:
                query += ["signature=" + \
                          str(self._signature_create(self._server_encryption_token, query[0]+"&".join(query[1:])))]
            query = query[0]+"&".join(query[1:])
            encrypted_response_status_code, encrypted_response_text = getPage(self._api_url+query)
        else:
            params_request=[]
            for param in params:
                if not isinstance(param,list):
                    # params_request+=[str(param).replace("'",'\"').replace("True","true").replace("False","false").replace('None',"null")]
                    params_request+=[json.dumps(param)]
                else:
                    params_request+=[param]
            params_request = {"apiVer": self._api_version, "url" : path, "params":params_request, "rid":self._request_id}
            data = json.dumps(params_request).replace('"null"',"null").replace("'null'","null")
            encrypted_data = self._encrypt(self._device_encryption_token,data)
            if action is not None:
                request_url=self._api_url+action+path
            else:
                request_url=self._api_url+path
            encrypted_response_status_code, encrypted_response_text = getPage(request_url, headers={"Content-Type": "application/aesjson-jd; charset=utf-8"}, data=encrypted_data)
        if encrypted_response_status_code != 200:
            error_msg=json.loads(encrypted_response_text)
            msg="\n\tSOURCE: "+error_msg["src"]+"\n\tTYPE: "+ \
                                error_msg["type"]+"\n------\nREQUEST_URL: "+ \
                                self._api_url+path
            if http_method == "GET":
                msg+=query
            msg+="\n"
            if data is not None:
                msg+="DATA:\n"+data
            raise(MYJDException(msg))
        if action is None:
            if not self._server_encryption_token:
                response = self._decrypt(self._login_secret, encrypted_response_text)
            else:
                response = self._decrypt(self._server_encryption_token, encrypted_response_text)
        else:
            if params is not None:
                response = self._decrypt(self._device_encryption_token, encrypted_response_text)
            else:
                return {"data" : response}
        jsondata = json.loads(response.decode('utf-8'))
        if jsondata['rid'] != self._request_id:
            self.update_request_id()
            return None
        self.update_request_id()
        return jsondata

class MyjdRequestHandler(BaseHTTPRequestHandler):
    server_version = 'IPTVPlayer HttpServer' #'AppWork GmbH HttpServer'
    
    def log_message(self, format, *args):
        printDBG(format%args)
    
    def parse_request(self):
        idx = -1
        for i in range(len(self.raw_requestline)):
            if self.raw_requestline[i:i+4] == 'POST':
                idx = i
                break
            elif self.raw_requestline[i:i+3] == 'GET':
                idx = i
                break
        if idx > 0:
            self.raw_requestline =  self.raw_requestline[idx:]
        if idx == -1:
            printDBG("Wrong request %s..." % self.raw_requestline[:256])
            #sys.exit(-1)
            #raise Exception("Wrong request %s..." % self.raw_requestline[:256])
        return BaseHTTPRequestHandler.parse_request(self)
    
    def _set_headers(self, returnCode=200, addHeaders=[]):
        self.send_response(returnCode)
        self.send_header('Connection', 'close')
        self.send_header('Cache-Control', 'no-store, no-cache')
        self.send_header('Content-type', 'application/json')
        for header in addHeaders:
            self.send_header(header[0], header[1])
        self.end_headers()

    def do_GET(self):
        self._set_headers(404)

    def do_HEAD(self):
        self._set_headers(501)

    def do_POST(self):
        jd = self.server
        return_data = ''
        returnCode = 200
        
        printDBG("In post method \n" + str(self.path))
        self.data_string = self.rfile.read(int(self.headers['Content-Length']))
        
        session_token = self.path.split('/t_', 1)[-1].split('_', 1)[0]
        new_token = hashlib.sha256()
        new_token.update(jd.get_device_secret() + _fromhex(session_token))
        encryption_token = new_token.digest()
        
        printDBG("SESSION TOKEN: %s" % session_token)
        data = decrypt(encryption_token, self.data_string)

        printDBG("ENCRYPTED_DATA [%s]: %s" % (len(self.data_string), self.data_string))
        printDBG("DECRYPTED_DATA [%s]: %s" % (len(data), data))
        
        data = json.loads(data)
        
        if data['url'] == '/device/getDirectConnectionInfos':
            updateStatus('status', "Client connected")
            return_data = { "infos" : [ ], "rebindProtectionDetected" : False, "mode" : "NONE"}
        elif data['url'] == '/update/isUpdateAvailable':
            return_data = False
        elif data['url'] == '/config/get':
            if data['params'][-1] == '"DirectConnectMode"':
                return_data = "NONE"
            elif data['params'][-1] == '"manuallocalport"':
                return_data = 3129
            else:
                returnCode = 404
                #sys.exit(-1)
        elif data['url'] == '/captcha/list':
            if jd.captcha_result == None:
                return_data = [{'hoster': 'iptvplayer.gitlab.io', 'created': jd.captcha_data['id'], 'explain': None, 'id': jd.captcha_data['id'], 'captchaCategory': 'recaptchav2', 'link': 1535005786381L, 'timeout': 600000, 'type': 'RecaptchaV2Challenge', 'remaining': 593028}]
            else:
                return_data = []
        elif data['url'] == '/events/subscribe':
            return_data = {"subscriptionid" : jd.subscription_id, "subscribed" : True, "subscriptions" : None,  "exclusions" : None,  "maxPolltimeout" : 25000, "maxKeepalive" : 120000}
            jd.captcha_notified = False
        elif data['url'] == '/events/setsubscription':
            #'^downloads', '^extraction', '^linkcrawler', '^dialogs', '^downloadwatchdog'
            return_data = {'maxKeepalive': 120000, 'subscribed': True, 'subscriptions': ['^captchas'], 'maxPolltimeout': 25000, 'subscriptionid': data['params'][0], 'exclusions': ['REFRESH_CONTENT']}
            jd.captcha_notified = False
        elif data['url'] == '/linkcrawler/isCrawling':
            return_data = False
        elif data['url'] == '/dialogs/list':
            return_data = []
        elif data['url'] == '/downloadsV2/getStopMarkedLink':
            return_data = None
        elif data['url'] == '/polling/poll':
            return_data = [{'eventName': 'jdState', 'eventData': {'data': 'IDLE'}}, {'eventName': 'aggregatedNumbers', 'eventData': {'data': {'crawledPackageCount': 0, 'downloadSpeed': 0, 'crawledStatusUnknown': 0, 'crawledStatusOnline': 0, 'crawledLinksCount': 0, 'packageCount': 0, 'linksCount': 0, 'connections': 0, 'running': 0, 'eta': 0, 'crawledStatusOffline': 0, 'totalBytes': 0, 'totalCrawledBytes': 0, 'loadedBytes': 0}}}]
        elif data['url'] == '/events/listen':
            return_data = ''
            #if jd.captcha_result == None and jd.captcha_notified == False:
            if jd.captcha_result == None:
                return_data = [{'eventid': 'NEW', 'eventData': jd.captcha_data['id'], 'publisher': 'captchas'}]
                jd.captcha_notified = True
            #elif jd.captcha_result !=  None:
            else:
                return_data = [{"eventid" : "DONE", "eventData" : jd.captcha_data['id'], "publisher" : "captchas"}]
                jd.captcha_finished = True

        elif data['url'] == '/captcha/getCaptchaJob':
            if jd.captcha_result == None:
                return_data = {'hoster': 'iptvplayer.gitlab.io', 'created': jd.captcha_data['id'], 'explain': None, 'id': jd.captcha_data['id'], 'captchaCategory': 'recaptchav2', 'link': 1535005786381L, 'timeout': 600000, 'type': 'RecaptchaV2Challenge', 'remaining': 593028}
            else:
                return_data = None
        elif data['url'] == '/captcha/get':
            if jd.captcha_result == None:
                updateStatus('status', "Waiting for captcha solving")
                return_data = jd.captcha_data
            else:
                return_data = None
        elif data['url'] == '/accountsV2/getPremiumHosterUrl':
            return_data = None
        elif data['url'] == '/captcha/solve':
            updateStatus('status', "Captcha solved")
            return_data = True
            jd.captcha_result = json.loads(data['params'][1]).encode('utf-8')
            updateStatus('captcha_result', jd.captcha_result)
        elif data['url'] == '/captcha/skip':
            updateStatus('status', "Captcha skipped")
            return_data = True
            jd.captcha_result = 'SKIPPED'
        elif data['url'] == '/downloadevents/setStatusEventInterval':
            return_data = True
        elif data['url'] == '/linkgrabberv2/queryPackages':
            return_data = []
        elif data['url'] == '/accountsV2/listAccounts':
            return_data = []
        elif data['url'] == '/downloadcontroller/getCurrentState':
            return_data = '"IDLE"'
        elif data['url'] == '/linkgrabberv2/queryLinks':
            return_data = []
        elif data['url'] == '/downloadsV2/getStopMark':
            return_data = -1
        elif data['url'] == '/captcha/keepAlive':
            return_data = 600000
        elif data['url'] == '/contentV2/getFavIcon':
            return_data = None
        else:
            returnCode = 404
            #sys.exit(-1)

        self._set_headers(returnCode)
        return_data = '''{"data" : %s, "rid" : %s}''' % (json.dumps(return_data), data['rid'])

        printDBG('RETURN DATA: %s' % return_data)
        self.wfile.write(encrypt(encryption_token, return_data))
        return

##################################
def PoolConnection(*args, **kwargs):
    parameters = kwargs['params']
    printDBG("START THREAD")
    while not parameters.captcha_finished:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('api.jdownloader.org', 80))
            s.send("DEVICE%s" % parameters.session_token)
            
            tmp = MyjdRequestHandler(s, (None, None), parameters)
            s.close()
        except Exception:
            printExc()

class Params:
    def get_device_secret(self):
        return self.device_secret
    pass

if __name__ == "__main__":
    if len(sys.argv) != 7:
        sys.stderr.write('Wrong parameters\n')
        sys.exit(1)
        
    libsPath   = sys.argv[1]
    sys.path.insert(1, libsPath)
    from crypto.cipher.aes_cbc import AES_CBC
        
    APP_KEY = "JD_api_39100"
    LOGIN = sys.argv[2]
    PASSWORD = sys.argv[3]
    JDNAME = "IPTVPlayer@" + sys.argv[4]
    CAPTCHA_DATA = json.loads(base64.b64decode(sys.argv[5]))
    CAPTCHA_DATA['id'] = int(time.time()*1000)

    hash = hashlib.sha256()
    hash.update(LOGIN + JDNAME)
    DEVICEID = hexlify(hash.digest()[:16])
    SUBSCRIPTION_ID = int(time.time()*1000)
    DEBUGE = int(sys.argv[6])
    returnCode = 0
    
    parameters = Params()
    parameters.captcha_finished = False
    parameters.captcha_result = None
    parameters.captcha_notified = False
    parameters.captcha_data = CAPTCHA_DATA
    parameters.subscription_id = SUBSCRIPTION_ID
    
    
    try:
        jd = None

        updateStatus('status', "Connecting to server")

        jd = Myjdapi()
        jd.set_app_key(APP_KEY)
        jd.connect(LOGIN, PASSWORD)

        response = jd.request_api("/my/binddevice", "GET", [("sessiontoken", jd.get_session_token()), ("deviceID", DEVICEID), ("type", "jd"), ("name", JDNAME)])
        printDBG(response)
        jd.update_request_id()

        response = jd.request_api("/my/captchas/isEnabled", "GET",[("sessiontoken", jd.get_session_token())])
        printDBG(response)
        jd.update_request_id()

        response = jd.request_api("/notify/list", "GET",[("sessiontoken", jd.get_session_token())])
        printDBG(response)
        jd.update_request_id()
        parameters.device_secret = jd.get_device_secret()
        parameters.session_token = jd.get_session_token()
        
        updateStatus('status', "Waiting for client connection")
        if True:
            threads = [None, None, None] #None, None, None
            for i in range(len(threads)):
                threads[i] = threading.Thread(target = PoolConnection, name = 'PoolConnection %d' % i, kwargs = {'params':parameters})
                threads[i].daemon = True 
                threads[i].start()
        
        while not parameters.captcha_finished:
            # send keep alive to server
            time.sleep(2)
            response = jd.request_api("/my/keepalive", "GET",[("sessiontoken", jd.get_session_token())])
            printDBG(response)
            printDBG(response['rid'])
            jd.update_request_id()

        updateStatus('captcha_result', parameters.captcha_result)
        
        try:
            if jd:
                jd.disconnect()
        except Exception:
            pass
    except MYJDException as e:
        updateStatus('error', str(e), LAST_HTTP_ERROR_CODE)
        printExc()
        returnCode = -1
    except KeyboardInterrupt as e:
        raise e
    except Exception:
        updateStatus('error', '', LAST_HTTP_ERROR_CODE)
        printExc()
        returnCode = -1

    sys.exit(returnCode)
