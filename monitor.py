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
    from configobj import ConfigObj,Section # apt-get install python-configobj
    from validate import Validator
    from StringIO import StringIO
    
    # Object holding actual state and work logic.
    obj = {'clients':[], 'port':7100, 'name':'monitor'}

    # First read client config from INI file
    # We use ConfigObj library from http://www.voidspace.org.uk/python/configobj.html

    # Schema to validate and transform the values from config file
    schema = ConfigObj(StringIO('''
    port = integer(min=0,max=65535,default=%d)
    name = string(default=%s)
    [__many__]
    enabled = boolean(default=True)
    port = integer(min=0,max=65535,default=0)
    host = string(default="localhost")
    description = string(default=None)
    ''' % (obj['port'], obj['name'])), list_values=False)

    confname = '%s.ini' % posixpath.splitext(__file__)[0]
    conf = ConfigObj(confname, configspec=schema)
    if len(conf):
        result = conf.validate(Validator())
        if result != True:
            print "Config file failed validation: %s" % confname
            print result
            sys.exit(1)

        for section in conf:
            # Skip leafs and branches with enabled=False
            if type(conf[section]) != Section or not conf[section]['enabled']:
                continue

            client = {'name':section,
                      'host':conf[section]['host'],
                      'port':conf[section]['port'],
                      'description':conf[section]['description']}

            obj['clients'].append(client)

        obj['port'] = conf.get('port')
        obj['name'] = conf.get('name')

    # Now parse command-line arguments using values read from config as defaults
    # so that they may be changed at startup time
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=obj['port'])
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', type='string', default=obj['name'])
    
    (options,args) = parser.parse_args()

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

    # Now we have everything to construct an run the daemon
    daemon = MonitorFactory(MonitorProtocol, obj, name=options.name)
    daemon.listen(options.port)

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
