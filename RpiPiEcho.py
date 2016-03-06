import json,sys,base64
import os

from twisted.internet import reactor, ssl
from twisted.python import log
from twisted.python.modules import getModule
from twisted.web.server import Site
from twisted.web.static import File
from autobahn.twisted.websocket import WebSocketServerFactory, WebSocketServerProtocol
from autobahn.twisted.resource import WebSocketResource

from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory,listenWS


class DataObj(object):
    def __init__(self, d={}):
        for a, b in d.items():
            if isinstance(b, (list, tuple)):
               setattr(self, a, [DataObj(x) if isinstance(x, dict) else x for x in b])
            else:
               setattr(self, a, DataObj(b) if isinstance(b, dict) else b)
        pass

    def __getattr__(self, item):
        try:
            return super(DataObj, self).__getattribute__(item)
        except AttributeError:
            setattr(self,item,None)
            return super(DataObj, self).__getattribute__(item)


class DigitAnalyzer:
    def __init__(self):
        self.digits={}
        self.history = []
        self.dpms = []

    def appendDigits(self,digits):
        for digit in digits:
            if self.digits.has_key(digit):
                self.digits[digit]=+1
            else:
                self.digits[digit]=1

    def addDPM(self,dpm):
        self.dpms.append(dpm)
        if(len(self.dpms)>100):
            self.dpms.pop(0)

class PiServerProtocol(WebSocketServerProtocol):

    def onOpen(self):
        header = self.http_headers
        if(header.has_key('piclient')):
            self.factory.registerPiServer(self)
        else:
            print 'non pi client', self.peer
            self.factory.register(self)

    def onConnect(self, request):
        pass

    def onMessage(self, payload, isBinary):
        if(self in self.factory.piClients):
            data = DataObj(json.loads(payload))
            #print data.__dict__
            ws_url = self.http_request_uri
            if data.digit:
                for num in data.digit:
                    if self.digitcounts.has_key(num):
                        self.digitcounts[num] += 1
                    else:
                        self.digitcounts[num] = 1
            if data.dpm:
                self.dpm_history.append(data.dpm)
            if data.mark:
                self.digits_history.append(data.mark)
            self.factory.broadcast(payload)
        #else: #possibly create a chat

    def onClose(self, wasClean, code, reason):
        self.factory.unregister(self)

class BroadcastServerFactory(WebSocketServerFactory):
    def __init__(self, url, debug=True, debugCodePaths=True):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.clients = []
        self.digitAnalyzer = DigitAnalyzer()
        self.piClients = []

    def registerPiServer(self,PiClient):
        PiClient.digits_history=[]
        PiClient.digitcounts={}
        PiClient.digit_count=0
        PiClient.dpm_history=[]
        self.piClients.append(PiClient)
        print 'welcome :',PiClient.http_headers['piclient']

    def register(self, client):
        if client not in self.clients:
            self.clients.append(client)
            self.clientChange()

    def unregister(self, client):
        if client in self.clients:
            self.clients.remove(client)
            self.clientChange()

        if(client in self.piClients):
            self.piClients.remove(client)

    def clientChange(self):
        self.broadcast(json.dumps({"connectedClients": len(self.clients)}))

    def broadcast(self, msg):
        prepared_msg = self.prepareMessage(base64.b64encode(msg),isBinary=True)
        print msg
        for c in self.clients:
            c.sendPreparedMessage(prepared_msg)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        log.startLogging(sys.stdout)
        debug = True
    else:
        debug = False
    contextFactory = ssl.DefaultOpenSSLContextFactory('/etc/letsencrypt/live/pi.raspi-ninja.com/privkey.pem',
                                                      '/etc/letsencrypt/live/pi.raspi-ninja.com/cert.pem')
    factory = BroadcastServerFactory(u"wss://pi.raspi-ninja.com:9000/ws_pi",debug=True)
    factory.protocol = PiServerProtocol
    listenWS(factory,contextFactory)
    print 'starting...'
    reactor.run()
