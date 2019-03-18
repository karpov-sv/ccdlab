#!/usr/bin/env python

from twisted.internet import stdio
from twisted.protocols.basic import LineReceiver
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.internet.endpoints import TCP4ServerEndpoint
from txsockjs.factory import SockJSResource

from twistedauth import wrap_with_auth as Auth

import os, sys, posixpath, datetime
import re
import urlparse
import json
import numpy as np

from collections import OrderedDict

from StringIO import StringIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib.ticker import ScalarFormatter, LogLocator, LinearLocator, MaxNLocator, NullLocator

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch
from db import DB

def kwargsToString(kwargs, prefix=''):
    return " ".join([prefix + _ + '=' + kwargs[_] for _ in kwargs])

class MonitorProtocol(SimpleProtocol):
    _debug = False

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.name = None
        self.status = {}

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.message('id name=monitor') # Send our identity to the peer
        self.message('get_id') # Request peer identity

    @catch
    def connectionLost(self, reason):
        if self.object['clients'].has_key(self.name):
            self.log("%s disconnected" % self.name, type='info')
            # print "Disconnected:", self.name

        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        if self._debug:
            print "%s:%d > %s" % (self._peer.host, self._peer.port, string)

        cmd = Command(string)

        if cmd.name == 'id':
            self.name = cmd.get('name', None)
            self.type = cmd.get('type', None)

            if self.object['clients'].has_key(self.name):
                self.log("%s connected" % self.name, type='info')
                # print "Connected:", self.name

        elif cmd.name == 'status':
            # We keep var=value pairs from the status to report it to clients
            self.status = cmd.kwargs

            # We have to keep the history of values for some variables for plots
            if self.object['values'].has_key(self.name):
                for name in self.object['values'][self.name]:
                    if name == 'time':
                        value = datetime.datetime.utcnow()
                    else:
                        value = self.status.get(name, None)
                        # Now we should try to convert the value to numerical form, if possible
                        try:
                            value = float(value)
                        except:
                            pass

                    self.object['values'][self.name][name].append(value)
                    # Keep the maximal length of data arrays limited
                    # TODO: make it configurable, probably for every plot
                    if len(self.object['values'][self.name][name]) > 1000:
                        self.object['values'][self.name][name] = self.object['values'][self.name][name][100:]

            # Broadcast new values to all CCDs, if the client itself is not CCD
            if self.type != 'ccd':
                self.factory.messageAll("set_keywords " + " ".join([self.name+'.'+_+'=\"'+self.status[_]+'\"' for _ in self.status.keys()]), type="ccd")

            # Store the values to database, if necessary
            if self.object.has_key('db') and self.object['db'] is not None:
                if (datetime.datetime.utcnow() - self.object['db_status_timestamp']).total_seconds() > self.object['db_status_interval']:
                    # FIXME: should we also store the status if no peer is reporting at all?
                    # print "Storing the state to DB"

                    time = datetime.datetime.utcnow()
                    status = self.factory.getStatus(as_dict=True)
                    self.object['db'].query('INSERT INTO monitor_status (time, status) VALUES (%s,%s)', (time, status))

                    self.object['db_status_timestamp'] = datetime.datetime.utcnow()
                    pass

        elif cmd.name == 'get_status':
            if cmd.kwargs.get('format', 'plain') == 'json':
                self.message('status_json ' + json.dumps(self.factory.getStatus(as_dict=True)))
            else:
                self.message(self.factory.getStatus())

        elif cmd.name == 'send' and cmd.chunks[1]:
            c = self.factory.findConnection(name=cmd.chunks[1])
            if c:
                c.message(" ".join(cmd.chunks[2:]))

        elif cmd.name in ['debug', 'info', 'message', 'error', 'warning', 'success']:
            msg = " ".join(cmd.chunks[1:])
            self.log(msg, source=self.name, type=cmd.name)

        elif cmd.name == 'reset_plots':
            self.factory.reset_plots()

    def log(self, msg, time=None, source=None, type='message'):
        if source is None:
            source = self.name

        self.factory.log(msg, time=time, source=source, type=type)

    def update(self):
        if self.name or self.type:
            self.message('get_status')

class WSProtocol(SimpleProtocol):
    def message(self, string):
        """Sending outgoing message with no newline"""
        self.transport.write(string)

class MonitorFactory(SimpleFactory):
    @catch
    def getStatus(self, as_dict=False):
        if as_dict:
            status = {'nconnected':len(self.connections), 'db_status_interval':self.object['db_status_interval']}
        else:
            status = 'status nconnected=%d db_status_interval=%g' % (len(self.connections), self.object['db_status_interval'])

        # Monitor only specified connections
        for name in self.object['clients']:
            c = self.findConnection(name=name)
            if c:
                if as_dict:
                    status[c.name] = c.status
                else:
                    status += ' ' + c.name + '=1 ' + kwargsToString(c.status, prefix=c.name + '.')
            else:
                if as_dict:
                    status[name] = {}
                else:
                    status += ' ' + name + '=0'

        # Monitor all connections instead
        # for c in self.connections:
        #     if c.name:
        #         status += ' ' + c.name + '=1 ' + kwargsToString(c.status, prefix=c.name + '_')

        return status

    @catch
    def log(self, msg, time=None, source=None, type='message'):
        """Log the message to both console, web-interface and database, if connected"""
        if time is None:
            time = datetime.datetime.utcnow()

        if source is None:
            source = 'monitor'

        print "%s: %s > %s > %s" % (time, source, type, msg)

        # DB
        if self.object.has_key('db') and self.object['db'] is not None:
            self.object['db'].log(msg, time=time, source=source, type=type)

        # WebSockets
        if self.object.has_key('ws'):
            self.object['ws'].messageAll(json.dumps({'msg':msg, 'time':str(time), 'source':source, 'type':type}))

    @catch
    def reset_plots(self):
        values = self.object['values']

        for client in values.keys():
            for param in values[client].keys():
                values[client][param] = []

        self.log('Resetting plots', source='monitor', type='info')
        pass

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
            self.message("Number of connections: %d" % len(self.factory.connections))
            for c in self.factory.connections:
                self.message("  %s:%s name:%s type:%s\n" % (c._peer.host, c._peer.port, c.name, c.type))

            if self.object.has_key('ws'):
                self.message("Number of WS connections: %d" % len(self.object['ws'].connections))
                for c in self.object['ws'].connections:
                    self.message("  %s:%s name:%s type:%s\n" % (c._peer.host, c._peer.port, c.name, c.type))

        elif cmd.name == 'clients' or not cmd.name:
            self.message("Number of registered clients: %d" % len(self.object['clients']))
            for name,c in self.object['clients'].items():
                conn = self.factory.findConnection(name=c['name'])
                self.message("  %s:%s name:%s connected:%s" % (c['host'], c['port'], c['name'], conn!=None))
            self.message()

        elif cmd.name == 'send' and cmd.chunks[1]:
            c = self.factory.findConnection(name=cmd.chunks[1])
            if c:
                c.message(" ".join(cmd.chunks[2:]))

        elif cmd.name == 'get_status':
            self.message(self.factory.getStatus())

        elif cmd.name in ['debug', 'info', 'message', 'error', 'warning']:
            msg = " ".join(cmd.chunks[1:])
            time = datetime.datetime.utcnow()
            self.factory.log(msg, time=time, source='web', type=cmd.name)

        elif cmd.name == 'reset_plots':
            self.factory.reset_plots()

        self.transport.write(b'### ')

def serve_json(request, **kwargs):
    request.responseHeaders.setRawHeaders("Content-Type", ['application/json'])
    return json.dumps(kwargs)

def make_plot(file, obj, client_name, plot_name, size=800):
    plot = obj['clients'][client_name]['plots'][plot_name]
    values = obj['values'][client_name]

    has_data = False

    fig = Figure(facecolor='white', dpi=72, figsize=(plot['width']/72, plot['height']/72), tight_layout=True)
    ax = fig.add_subplot(111)

    for _ in plot['values'][1:]:
        # Check whether we have at least one data point to plot
        if np.any(np.array(values[_]) != None):
            has_data = True
            ax.plot(values[plot['values'][0]], values[_], '-', label=_)

    if plot['values'][0] == 'time' and len(values[plot['values'][0]]) > 1 and has_data:
        ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        fig.autofmt_xdate()

    if plot['xlabel']:
        ax.set_xlabel(plot['xlabel'])
    else:
        ax.set_xlabel(plot['values'][0])

    if plot['ylabel']:
        ax.set_ylabel(plot['ylabel'])
    elif len(plot['values']) == 1:
        ax.set_ylabel(plot['values'][1])

    if has_data:
        if plot['xscale'] != 'linear':
            ax.set_xscale(plot['xscale'], nonposx='clip')

        if plot['yscale'] != 'linear':
            ax.set_yscale(plot['yscale'], nonposy='clip')

            if plot['yscale'] == 'log':
                # Try to fix the ticks if the data span is too small
                axis = ax.get_yaxis()
                if np.ptp(np.log10(axis.get_data_interval())) < 1:
                    axis.set_major_locator(MaxNLocator())
                    axis.set_minor_locator(NullLocator())

        if len(plot['values']) > 4:
            ax.legend(frameon=True, loc=2, framealpha=0.99)
        elif len(plot['values']) > 2:
            ax.legend(frameon=False)

    if plot['name']:
        ax.set_title(plot['name'])
    ax.margins(0.01, 0.1)

    # FIXME: make it configurable
    ax.grid(True)

    # Return the image
    canvas = FigureCanvas(fig)
    canvas.print_png(file, bbox_inches='tight')

class WebMonitor(Resource):
    isLeaf = True

    def __init__(self, factory=None, object=None):
        self.factory = factory
        self.object = object

    @catch
    def render_GET(self, request):
        q = urlparse.urlparse(request.uri)
        args = urlparse.parse_qs(q.query)
        qs = q.path.split('/')

        if q.path == '/monitor/status':
            return serve_json(request,
                              clients = self.object['clients'],
                              status = self.factory.getStatus(as_dict=True))
        # /monitor/plots/{client}/{name}
        elif qs[1] == 'monitor' and qs[2] == 'plot' and len(qs) > 4:
            s = StringIO()
            make_plot(s, self.object, qs[3], qs[4])
            request.responseHeaders.setRawHeaders("Content-Type", ['image/png'])
            request.responseHeaders.setRawHeaders("Content-Length", [s.len])
            request.responseHeaders.setRawHeaders("Cache-Control", ['no-store, no-cache, must-revalidate, max-age=0'])
            return s.getvalue()
        elif q.path == '/monitor/command' and args.has_key('string'):
            cmd = Command(args['string'][0])

            # TODO: re-use the command processing code from TCP server part
            if cmd.name == 'exit':
                self.factory._reactor.stop()

            elif cmd.name == 'send' and cmd.chunks[1]:
                c = self.factory.findConnection(name=cmd.chunks[1])
                if c:
                    c.message(" ".join(cmd.chunks[2:]))

            elif (cmd.name == 'broadcast' or cmd.name == 'send_all'):
                self.factory.messageAll(" ".join(cmd.chunks[1:]))

            elif (cmd.name == 'set'):
                if cmd.has_key('interval'):
                    self.object['db_status_interval'] = float(cmd.get('interval'))
                    self.factory.log('DB status interval set to %g' % self.object['db_status_interval'], type='info')

            elif cmd.name in ['debug', 'info', 'message', 'error', 'warning']:
                msg = " ".join(cmd.chunks[1:])
                time = datetime.datetime.utcnow()
                self.factory.log(msg, time=time, source='web', type=cmd.name)

            elif cmd.name == 'reset_plots':
                self.factory.reset_plots()

            return serve_json(request)

        else:
            return q.path;

def loadINI(filename, obj):
    # We use ConfigObj library, docs: http://configobj.readthedocs.io/en/latest/index.html
    from configobj import ConfigObj,Section # apt-get install python-configobj
    from validate import Validator

    # Schema to validate and transform the values from config file
    schema = ConfigObj(StringIO('''
    port = integer(min=0,max=65535,default=%d)
    http_port = integer(min=0,max=65535,default=%d)
    name = string(default=%s)
    db_host = string(default=%s)
    db_status_interval = float(min=0, max=3600, default=%g)

    [__many__]
    enabled = boolean(default=True)
    port = integer(min=0,max=65535,default=0)
    host = string(default=localhost)
    description = string(default=None)
    template = string(default=default.html)

    [[plots]]
    [[[__many__]]]
    name = string(default=None)
    values = list(default=,)
    xlabel = string(default=None)
    ylabel = string(default=None)
    width = integer(min=0,max=2048,default=800)
    height = integer(min=0,max=2048,default=300)
    xscale = string(default=linear)
    yscale = string(default=linear)
    ''' % (obj['port'], obj['http_port'], obj['name'], obj['db_host'], obj['db_status_interval'])), list_values=False)

    confname = '%s.ini' % posixpath.splitext(__file__)[0]
    conf = ConfigObj(confname, configspec=schema)
    if len(conf):
        result = conf.validate(Validator())
        if result != True:
            print "Config file failed validation: %s" % confname
            print result

            raise RuntimeError

        for sname in conf:
            section = conf[sname]

            # Skip leafs and branches with enabled=False
            if type(section) != Section or not section['enabled']:
                continue

            client = section.dict()
            client['name'] = sname

            obj['values'][sname] = {}

            if section.has_key('plots'):
                values = []

                # Parse parameters of plots
                for plot in section['plots']:
                    client['plots'][plot] = section['plots'][plot]

                    values += section['plots'][plot]['values']

                obj['values'][sname] = {_:[] for _ in set(values)} # Unique values

            obj['clients'][sname] = client

        for key in ['port', 'http_port', 'name', 'db_host', 'db_status_interval']:
            obj[key] = conf.get(key)

    # print obj
    # sys.exit(1)

    return True

if __name__ == '__main__':
    from optparse import OptionParser

    # Object holding actual state and work logic.
    obj = {'clients':OrderedDict(), 'values':{}, 'port':7100, 'http_port':8888, 'db_host':None, 'db_status_interval':60.0, 'name':'monitor', 'db':None}

    # First read client config from INI file
    loadINI('%s.ini' % posixpath.splitext(__file__)[0], obj)

    # Now parse command-line arguments using values read from config as defaults
    # so that they may be changed at startup time
    parser = OptionParser(usage="usage: %prog [options] name1=host1:port1 name2=host2:port2 ...")
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=obj['port'])
    parser.add_option('-H', '--http-port', help='HTTP server port', action='store', dest='http_port', type='int', default=obj['http_port'])
    parser.add_option('-D', '--db-host', help='Database server host', action='store', dest='db_host', type='string', default=obj['db_host'])
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', type='string', default=obj['name'])
    parser.add_option('-d', '--debug', help='Debug output', action='store_true', dest='debug', default=False)
    parser.add_option('-s', '--server', help='Act as a TCP and HTTP server', action='store_true', dest='server', default=False)
    parser.add_option('-i', '--interval', help='DB logging status inteval', dest='interval', type='float', default=obj['db_status_interval'])

    (options,args) = parser.parse_args()

    obj['db_status_interval'] = options.interval

    # Next parse command line positional args as name=host:port tokens
    for arg in args:
        m = re.match('(([a-zA-Z0-9-_]+)=)?(.*):(\d+)', arg)
        if m:
            name,host,port = m.group(2,3,4)

            if obj['clients'].has_key(name):
                obj['clients'][name]['host'] = host
                obj['clients'][name]['port'] = int(port)
            else:
                obj['clients'][name] = {'host':host, 'port':int(port), 'name':name, 'description':name, 'template':'default.html', 'plots':None}

    # Now we have everything to construct and run the daemon
    daemon = MonitorFactory(MonitorProtocol, obj, name=options.name)

    for name,c in obj['clients'].items():
        daemon.connect(c['host'], c['port'])

    # Simple stdio interface
    stdio.StandardIO(CmdlineProtocol(factory=daemon, object=obj), reactor=daemon._reactor)

    # Web interface
    if options.debug:
        from twisted.python import log
        log.startLogging(sys.stdout)

    if options.server:
        # Listen for incoming TCP connections
        print "Listening for incoming TCP connections on port %d" % options.port
        daemon.listen(options.port)

        # Serve files from web
        root = File("web")
        root.putChild("", File('web/main.html'))
        root.putChild("monitor", WebMonitor(factory=daemon, object=obj))
        #site = Site(root)
        site = Site(Auth(root, {'ccd':'ccd'}))

        # WebSockets
        ws = SimpleFactory(WSProtocol, obj)
        obj['ws'] = ws
        root.putChild("ws", SockJSResource(ws))

        # Database connection
        obj['db'] = DB(dbhost=options.db_host)
        obj['db_status_timestamp'] = datetime.datetime.utcfromtimestamp(0)

        print "Listening for incoming HTTP connections on port %d" % options.http_port
        TCP4ServerEndpoint(daemon._reactor, options.http_port).listen(site)

    daemon._reactor.run()
