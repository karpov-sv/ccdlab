#!/usr/bin/env python

from twisted.internet.protocol import Protocol, Factory, ServerFactory
from twisted.application.internet import ClientService
from twisted.application.service import Service
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
from twisted.protocols.basic import LineReceiver
from twisted.internet.task import LoopingCall

import os, sys
import re
import socket

from command import Command

def catch(func):
    '''Decorator to catch errors inside functions and print tracebacks'''
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            import traceback
            traceback.print_exc()

    return wrapper

class SimpleProtocol(Protocol):
    """Class corresponding to a single connection, either incoming or outgoing"""
    _debug = False

    # Some sensible TCP keepalive settings. This way the connection will close after 13 seconds of network failure
    _tcp_keepidle = 10 # Interval to wait before sending first keepalive packet
    _tcp_keepintvl = 1 # Interval between packets
    _tcp_keepcnt = 3 # Number of retries

    def __init__(self, refresh=1):
        self._buffer = ''
        self._is_binary = False
        self._binary_length = 0
        self._peer = None
        self._refresh = refresh

        # Name and type of the connection peer
        self.name = ''
        self.type = ''

        # These will be set in Factory::buildProtocol
        self.factory = None
        self.object = None

    def setName(self, name, type=None):
        """Set the name (and type) used to identify the connection"""
        self.name = name
        self.type = type

    def connectionMade(self):
        """Method called when connection is established"""
        self._peer = self.transport.getPeer()
        self.factory.connections.append(self)

        print "Connected to %s:%d" % (self._peer.host, self._peer.port)

        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)

        # Set up TCP keepalive for the connection
        self.transport.getHandle().setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if sys.platform == 'darwin':
            # OSX specific code
            TCP_KEEPALIVE = 0x10
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, self._tcp_keepidle)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self._tcp_keepintvl)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._tcp_keepcnt)
        elif sys.platform.startswith('linux'):
            # Linux specific code
            TCP_KEEPIDLE = 0x4
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, TCP_KEEPIDLE, self._tcp_keepidle)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self._tcp_keepintvl)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._tcp_keepcnt)

    def connectionLost(self, reason):
        """Method called when connection is finished"""
        self.factory.connections.remove(self)

        self._updateTimer.stop()

        print "Disconnected from %s:%d" % (self._peer.host, self._peer.port)

    def message(self, string):
        """Sending outgoing message"""
        if self._debug:
            print ">>", self._peer.host, self._peer.port, '>>', string
        self.transport.write(string)
        self.transport.write("\n")

    def dataReceived(self, data):
        """Parse incoming data and split it into messages"""
        self._buffer = self._buffer + data

        while len(self._buffer):
            if self._is_binary:
                if len(self._buffer) >= self._binary_length:
                    bdata = self._buffer[:self._binary_length]
                    self._buffer = self._buffer[self._binary_length:]

                    self.processBinary(bdata)
                    self._is_binary = False
                else:
                    break
            else:
                try:
                    token, self._buffer = re.split('\0|\n', self._buffer, 1)
                    self.processMessage(token)
                except ValueError:
                    break

    def switchToBinary(self, length=0):
        """
        Switches the connection to binary mode to receive _length_ bytes.
        Will call processBinary() callback when completed
        """
        self._is_binary = True
        self._binary_length = length
        if self._debug:
            print "%s:%d = binary mode waiting for %d bytes" % (self._peer.host, self._peer.port, string, length)

    def processMessage(self, string):
        """Process single message"""
        if self._debug:
            print "%s:%d > %s" % (self._peer.host, self._peer.port, string)

        cmd = Command(string)

        # Some generic commands every connection should understand
        if cmd.name == 'get_id':
            # Identification of the daemon
            self.message('id name=%s type=%s' % (self.factory.name, self.factory.type))
        elif cmd.name == 'id':
            # Set peer identification
            self.name = cmd.get('name', '')
            self.type = cmd.get('type', '')
        elif cmd.name == 'exit':
            # Stops the daemon
            self.factory._reactor.stop()

        return cmd

    def processBinary(self, data):
        """Process binary data when completely read out"""
        if self._debug:
            print "%s:%d binary > %d bytes" % (self._peer.host, self._peer.port, len(data))

    def update(self):
        pass

class SimpleFactory(Factory):
    """
    Class that manages all connections, both incoming and outgoing.
    Every connection receives the object passed to class constructor
    so it may be accessed from connection protocol
    """
    def __init__(self, protocol, object=None, reactor=None, name=None, type=None):
        self._protocol = protocol
        self._reactor = reactor

        self.connections = [] # List of all currently active connections
        self.object = object # User-supplied object what should be accessible by all connections and daemon itself

        # Name and type of the daemon
        self.name = ''
        self.type = ''

        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor

    def buildProtocol(self, addr):
        p = self._protocol()

        p.factory = self
        p.object = self.object

        return p

    def findConnection(self, name=None, type=None):
        """Find the first connection with given name and type among the active connections"""
        for c in self.connections:
            isMatched = True

            if name and c.name != name:
                isMatched = False

            if type and c.type != type:
                isMatched = False

            if isMatched:
                return c

        return None

    def messageAll(self, string, name=None, type=None):
        """Send the message to all (or with a given name/type only) active connections"""
        for c in self.connections:
            if name and c.name != name:
                continue
            if type and c.type != type:
                continue
            c.message(string)

    def listen(self, port=0):
        """Listen for incoming connections on a given port"""
        print "Listening for incoming connections on port %d" % port
        TCP4ServerEndpoint(self._reactor, port).listen(self)

    def connect(self, host, port, reconnect=True):
        """Initiate outgoing connection, either persistent or no"""
        print "Initiating connection to %s:%d" % (host, port)
        ep = TCP4ClientEndpoint(self._reactor, host, port)
        if reconnect:
            service = ClientService(ep, self, retryPolicy=lambda x: 1)
            service.startService()
        else:
            ep.connect(self)
