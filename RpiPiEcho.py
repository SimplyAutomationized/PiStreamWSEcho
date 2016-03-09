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
class Stats(object):
    pass

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
            if data.startTime:
                self.stats.startTime = data.startTime
            if data.digit:
                for num in data.digit:
                    if self.stats.digitcounts.has_key(num):
                        self.stats.digitcounts[num] += 1
                    else:
                        self.stats.digitcounts[num] = 1
            newpayload = {
                            "Device": self.device,
                            "digits": data.digit,
                            # "runtime": data.time - self.stats.startTime,
                            "dpm": data.dpm
                        }
            if data.mark:
                self.stats.digits_history.append(data.mark.__dict__)
                if data.dpm:
                    self.stats.dpm_history.append({data.time: data.dps})
                newpayload['mark'] = {
                    data.time: data.dps,
                    "digitmark": data.mark.digitmark,
                    "time": data.mark.time
                }
            self.factory.broadcast(newpayload)
        else:
            try:
                data = DataObj(json.loads(payload))
                if data.showpi:
                    self.showpi = data.showpi
            except Exception as e:
                pass

    def onClose(self, wasClean, code, reason):
        self.factory.unregister(self)

class BroadcastServerFactory(WebSocketServerFactory):
    def __init__(self, url, debug=True, debugCodePaths=True):
        WebSocketServerFactory.__init__(self, url, debug=debug, debugCodePaths=debugCodePaths)
        self.clients = []
        self.piClients = []

    def registerPiServer(self,PiClient):
        PiClient.stats = Stats()
        # self.stats.startTime = 0
        PiClient.stats.digits_history=[]
        PiClient.stats.digitcounts = {}
        PiClient.stats.digit_count=0
        PiClient.stats.dpm_history=[]
        PiClient.device = PiClient.http_headers['piclient']
        self.piClients.append(PiClient)
        print 'welcome :',PiClient.http_headers['piclient']

    def register(self, client):
        if client not in self.clients:
            client.showpi = None
            self.clients.append(client)
            for piclient in self.piClients:
                newclientdata={"piclient": piclient.device}
                self.sendMessage(newclientdata)
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
        #print msg
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
    factory = BroadcastServerFactory(u"wss://pi.raspi-ninja.com:9000/ws_pi",debug=debug)
    factory.protocol = PiServerProtocol
    listenWS(factory,contextFactory)
    print 'starting...'
    reactor.run()
