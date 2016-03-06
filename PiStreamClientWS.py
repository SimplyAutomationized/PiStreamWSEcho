import time,timeit
from autobahn.twisted.websocket import WebSocketClientProtocol,WebSocketClientFactory,connectWS
from twisted.internet import threads
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.internet import reactor, ssl

from gmpy import mpz
try:
    import ujson as json
except ImportError:
    import json


calc_uy = 1
u,y = -1,-1
q,r,t,j = mpz(1), mpz(180), mpz(60), 2
startTime = -1


def pi_calc():
    global calcs,y,u,q,r,t,j,calc_uy,startTime
    digitstring = ''
    dpm = 0
    strPi = ''
    loop = 1
    elapsed=0
    elapsedStart = time.time()
    while loop:
        digitCalcTime = time.time()
        u, y = mpz(3*(3*j+1)*(3*j+2)), mpz((q*(27*j-12)+5*r)/(5*t))
        strPi = str(y)
        digitstring += strPi
        q, r, t, j = mpz((20*j**2-10*j)*q), mpz(10*u*(q*(5*j-2)+r-y*t)), mpz(t*u), j+1
        # dpm = digits per minute
        now = time.time()
        elapsed = now - elapsedStart
        if elapsed >= 1:
            break
        elif (j-2) % 1000 == 0:
            break
    dps = (1.0/elapsed)*len(digitstring)
    info = {"digit": digitstring, "digits": j-2, "dpm": round(dps*60),"dps":round(dps,2)}
    if (j-2) % 1000 != 0:
        info['mark'] = {(j-2) : startTime-time.time()}
    return info


class PiWebSocketProtocol(WebSocketClientProtocol):
    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))
        self.factory.resetDelay()
        self.factory.sendMessage = self.sendMessage

    def onOpen(self):
        self.factory.start_calculating()
        pass

    def onMessage(self, payload, isBinary):
        pass

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))



class PiWebSocketFactory(WebSocketClientFactory, ReconnectingClientFactory):
    protocol = PiWebSocketProtocol
    running_calc = 0

    def clientConnectionFailed(self, connector, reason):
        print("Client connection failed .. retrying ..")
        self.retry(connector)

    def clientConnectionLost(self, connector, reason):
        print("Client connection lost .. retrying ..")
        self.retry(connector)

    def sendMessage(self,data):
        pass

    def start_calculating(self):
        global startTime
        print 'starting calcs'
        if not self.running_calc:
                self.sendMessage(json.dumps({"startTime": time.time()}))
                startTime = time.time()
                d = threads.deferToThread(pi_calc)
                d.addCallback(self.getDigit)
                self.running_calc = 1

    def getDigit(self, pidigits):
        self.sendMessage(json.dumps(pidigits))
        d = threads.deferToThread(pi_calc)
        d.addCallback(self.getDigit)

if __name__=="__main__":
    import sys
     if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        log.startLogging(sys.stdout)
        debug = True
    else:
        debug = False
    log.startLogging(sys.stdout)
    headers = {"PiClient":"Pi3"}
    contextFactory = ssl.ClientContextFactory()
    factory = PiWebSocketFactory(u"wss://pi.raspi-ninja.com:9000/ws_pi?pi",headers=headers, debug=debug)
    connectWS(factory,contextFactory)
    reactor.run()