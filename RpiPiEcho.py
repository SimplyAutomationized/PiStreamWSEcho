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
        if(header.has_key('pi')):
            self.factory.registerPiServer(self)
        else:
            self.factory.register(self)

    def onMessage(self, payload, isBinary):


        if(self in self.factory.piClient):
            data = DataObj(json.loads(payload))
            #print data.__dict__
            ws_url=self.http_request_uri
            if data.digit:
                self.factory.digitAnalyzer[ws_url]
            if data.dpm:
                self.factory.digitAnalyzer[ws_url].addDPM(data.dpm)
            if data.mark:
                self.factory.digitAnalyzer[ws_url].history.append(data.mark.__dict__)
            self.factory.broadcast(payload, ws_url)

        #else: #possibly create a chat


    def onClose(self, wasClean, code, reason):
        self.factory.unregister(self)

class BroadcastServerFactory(WebSocketServerFactory):
    def __init__(self, url, debug=True, debugCodePaths=True):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.clients = {'/ws_pi?dec': [], '/ws_pi?bbp': []}
        self.piClient = []

    def registerPiServer(self,PiClient):
        ws_page = PiClient.http_request_uri
        self.piClient.append(PiClient)

    def register(self, client):
        ws_page = client.http_request_uri
        if self.clients.has_key(ws_page):
            if client not in self.clients[ws_page]:
                self.clients[ws_page].append(client)
                self.clientChange(ws_page)

    def unregister(self, client):
        ws_page = client.http_request_uri
        if(client in self.clients[ws_page]):
            self.clients[ws_page].remove(client)
            self.clientChange(ws_page)

        if(client in self.piClient):
            self.piClient.remove(client)

    def clientChange(self,ws_page):
        self.broadcast(json.dumps({"connectedClients": len(self.clients[ws_page])}),ws_page)

    def broadcast(self, msg,ws_page):
        prepared_msg = self.prepareMessage(base64.b64encode(msg),isBinary=True)
        print msg
        for c in self.clients[ws_page]:
            c.sendPreparedMessage(prepared_msg)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        log.startLogging(sys.stdout)
        debug = True
    else:
        debug = False
    contextFactory = ssl.DefaultOpenSSLContextFactory('/etc/letsencrypt/live/pi.raspi-ninja.com/privkey.pem',
                                                      '/etc/letsencrypt/live/pi.raspi-ninja.com/cert.pem')
    factory = BroadcastServerFactory(u"wss://pi.raspi-ninja.com:9000/ws_pi")
    factory.protocol = PiServerProtocol
    #resource = WebSocketResource(factory)
    listenWS(factory,contextFactory)
    print 'starting...'
    reactor.run()
