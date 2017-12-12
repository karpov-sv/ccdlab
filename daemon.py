#!/usr/bin/env python

from twisted.internet.protocol import Protocol, Factory, ServerFactory
from twisted.application.internet import ClientService
from twisted.application.service import Service
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
from twisted.protocols.basic import LineReceiver
from twisted.internet.task import LoopingCall

import os, sys
import re
import shlex

class SimpleProtocol(Protocol):
    _debug = False

    """Class corresponding to a single connection, either incoming or outgoing"""
    def __init__(self, refresh=1):
        self._buffer = ''
        self._is_binary = False
        self._binary_length = 0
        self._peer = None
        self._refresh = refresh

    def connectionMade(self):
        """Method called when connection is established"""
        self._peer = self.transport.getPeer()
        print "Connected to %s:%d" % (self._peer.host, self._peer.port)

        LoopingCall(self.update).start(self._refresh)

    def connectionLost(self, reason):
        """Method called when connection is finished"""
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
                token, self._buffer = re.split('\0|\n', self._buffer, 1)
                self.processMessage(token)

    def switchToBinary(self, length=0):
        """
        Switches the connection to binary mode to receive _length_ bytes.
        Will call processBinary() callback when completed
        """
        self._is_binary = True
        self._binary_length = length

    def processMessage(self, string):
        """Process single message"""
        if self._debug:
            print "%s:%d > %s" % (self._peer.host, self._peer.port, string)

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
    def __init__(self, protocol, object=None, reactor=None):
        self._object = object
        self._protocol = protocol
        self._reactor = reactor

        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor

    def buildProtocol(self, addr):
        p = self._protocol()
        p._factory = self
        p.object = self._object

        return p

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

class Command:
    """Parse a text command into command name and arguments, both positional and keyword"""
    def __init__(self, string):
        self.name = None
        self.args = []
        self.kwargs = {}

        self.parse(string)

    def name(self):
            return self.name

    def get(self, key, value=None):
            return self.kwargs.get(key, value)

    def parse(self, string):
        chunks = shlex.split(string)

        for i,chunk in enumerate(chunks):
            if '=' not in chunk:
                if i == 0:
                    self.name = chunk
                else:
                    self.args.append(chunk)
            else:
                pos = chunk.find('=')
                self.kwargs[chunk[:pos]] = chunk[pos+1:]
