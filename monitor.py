#!/usr/bin/env python

from twisted.internet import stdio
from twisted.protocols.basic import LineReceiver
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet.endpoints import TCP4ServerEndpoint

import os, sys, posixpath
import re
import urlparse
import json
import ConfigParser

from daemon import SimpleFactory, SimpleProtocol
from command import Command

### Example code with server daemon and outgoing connection to hardware

def kwargsToString(kwargs, prefix=''):
    return " ".join([prefix + _ + '=' + kwargs[_] for _ in kwargs])

def catch(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            import traceback
            traceback.print_exc()

    return wrapper

class MonitorProtocol(SimpleProtocol):
    _debug = False

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.name = None
        self.status = {}

    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.message('get_id')

    @catch
    def processMessage(self, string):
        if self._debug:
            print "%s:%d > %s" % (self._peer.host, self._peer.port, string)

        cmd = Command(string)

        if cmd.name == 'id':
            self.name = cmd.get('name', None)
            self.type = cmd.get('type', None)

        elif cmd.name == 'status':
            # We keep var=value pairs from the status to report it to clients
            self.status = cmd.kwargs

        elif cmd.name == 'get_status':
            self.message(self.factory.getStatus())

    def update(self):
        self.factory.messageAll('get_status')

class MonitorFactory(SimpleFactory):
    @catch
    def getStatus(self, as_dict=False):
        if as_dict:
            status = {'nconnected':len(self.connections)}
        else:
            status = 'status nconnected=%d' % len(self.connections)

        # Monitor only specified connections
        for name in [_['name'] for _ in self.object['clients'] if _['name']]:
            c = self.findConnection(name=name)
            if c:
                if as_dict:
                    status[c.name] = c.status
                else:
                    status += ' ' + c.name + '=1 ' + kwargsToString(c.status, prefix=c.name + '_')
            else:
                if as_dict:
                    status[name] = 0
                else:
                    status += ' ' + name + '=0'

        # Monitor all connections instead
        # for c in self.connections:
        #     if c.name:
        #         status += ' ' + c.name + '=1 ' + kwargsToString(c.status, prefix=c.name + '_')

        return status

class CmdlineProtocol(LineReceiver):
    delimiter = os.linesep.encode('ascii')

    def __init__(self, factory=None, object=None):
        self.factory = factory
        self.object = object

    def connectionMade(self):
        self.transport.write(b'### ')

    def message(self, string=''):
        self.transport.write(string)
        self.transport.write('\n')

    @catch
    def lineReceived(self, line):
        cmd = Command(line)

        if cmd.name == 'exit':
            self.factory._reactor.stop()

        elif cmd.name == 'connections':
            print "Number of connections:", len(self.factory.connections)
            for c in self.factory.connections:
                self.message("  %s:%s name:%s type:%s\n" % (c._peer.host, c._peer.port, c.name, c.type))

        elif cmd.name == 'clients':
            print "Number of registered clients:", len(self.object['clients'])
            for c in self.object['clients']:
                conn = self.factory.findConnection(name=c['name'])
                self.message("  %s:%s name:%s connected:%s" % (c['host'], c['port'], c['name'], conn!=None))
            self.message()

        elif cmd.name == 'send' and cmd.chunks[1]:
            c = self.factory.findConnection(name=cmd.chunks[1])
            if c:
                c.message(" ".join(cmd.chunks[2:]))

        elif cmd.name == 'get_status':
            self.message(self.factory.getStatus())

        self.transport.write(b'### ')

def serve_json(request, **kwargs):
    request.responseHeaders.setRawHeaders("Content-Type", ['application/json'])
    return json.dumps(kwargs)

class WebMonitor(Resource):
    isLeaf = True

    def __init__(self, factory=None, object=None):
        self.factory = factory
        self.object = object

    def render_GET(self, request):
        q = urlparse.urlparse(request.uri)
        args = urlparse.parse_qs(q.query)

        if q.path == '/monitor/status':
            return serve_json(request,
                              clients = self.object['clients'],
                              status = self.factory.getStatus(as_dict=True))
        elif q.path == '/monitor/command':
            cmd = Command(args['string'][0])

            if cmd.name == 'exit':
                self.factory._reactor.stop()

            elif cmd.name == 'send' and cmd.chunks[1]:
                c = self.factory.findConnection(name=cmd.chunks[1])
                if c:
                    c.message(" ".join(cmd.chunks[2:]))

            elif (cmd.name == 'broadcast' or cmd.name == 'send_all'):
                self.factory.messageAll(" ".join(cmd.chunks[1:]))

            return serve_json(request)

if __name__ == '__main__':
    from optparse import OptionParser
    from ConfigParser import SafeConfigParser
    
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7100)

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    obj = {'clients':[]}

    # First read client config from INI file
    parser = SafeConfigParser({'enabled':'True', 'description':None})
    parser.read('%s.ini' % posixpath.splitext(__file__)[0])

    for section in parser.sections():
        if not parser.getboolean(section, 'enabled'):
            continue
        
        if parser.has_option(section, 'host') and parser.has_option(section, 'port'):
            client = {'name':section,
                      'host':parser.get(section, 'host'),
                      'port':parser.getint(section, 'port'),
                      'description':parser.get(section, 'description')}

            # if parser.has_option(section, 'description'):
            #     client['description'] = parser.get(section, 'description')

        obj['clients'].append(client)

    # Next parse command line positional args as name=host:port tokens
    for arg in args:
        m = re.match('(([a-zA-Z0-9-_]+)=)?(.*):(\d+)', arg)
        if m:
            name,host,port = m.group(2,3,4)
            print name,host,port

            client = [_ for _ in obj['clients'] if _['name'] == name]

            if client:
                client[0]['host'] = host
                client[0]['port'] = int(port)
            else:
                obj['clients'].append({'host':host, 'port':int(port), 'name':name, 'description':None})

    daemon = MonitorFactory(MonitorProtocol, obj)
    daemon.listen(options.port)

    obj['daemon'] = daemon

    for c in obj['clients']:
        daemon.connect(c['host'], c['port'])

    # Simple stdio interface
    stdio.StandardIO(CmdlineProtocol(factory=daemon, object=obj), reactor=daemon._reactor)

    # Web interface

    # Serve files from web
    root = File("web")
    root.putChild("", File('web/webmonitor.html'))
    root.putChild("monitor", WebMonitor(factory=daemon, object=obj))
    site = Site(root)

    print "Listening for incoming HTTP connections on port %d" % 8888
    TCP4ServerEndpoint(daemon._reactor, 8888).listen(site)

    daemon._reactor.run()
