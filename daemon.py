from __future__ import absolute_import, division, print_function, unicode_literals

from twisted.internet.protocol import Protocol, Factory, ServerFactory
from twisted.application.internet import ClientService
from twisted.application.service import Service
from twisted.internet.endpoints import TCP4ServerEndpoint, TCP4ClientEndpoint, connectProtocol
from twisted.protocols.basic import LineReceiver
from twisted.internet.task import LoopingCall
from twisted.internet.serialport import SerialPort

import pylibftdi
from pyudev import Context, Monitor, MonitorObserver

import os
import sys
import re
import socket
import time

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


class FTDIProtocol(Protocol):
    """ Class for outgoing connection to a FTDI device """
    _debug = False
    _refresh = 1.0
    pylibftdi.USB_PID_LIST.append(0xFAF0)

    def __init__(self, serial_num, obj, refresh=0, baudrate=115200):
        # Name and type of the connection peer
        self.name = ''
        self.type = ''

        self.object = obj
        self.baudrate = baudrate
        self.serial_num = serial_num
        self.devpath = ''

        if refresh > 0:
            self._refresh = refresh

        self.device = pylibftdi.Device(mode='b', device_id=self.serial_num, lazy_open=True)
        self.device._baudrate = self.baudrate
        
        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)
        self._readTimer = LoopingCall(self.read)
        self._readTimer.start(self._refresh/10)
        
        # the following will start a small daemon to monitor the connection and call ConnectionMade and ConnectionLost
        # pyftdi doesn't seem to support this so this pyudev daemon is necessary

        context = Context()
        # find out whether device is already connected and if that is the case open ftdi connection
        for device in context.list_devices(subsystem='usb'):
            if device.get('ID_SERIAL_SHORT') == self.serial_num:
                for ch in device.children:
                    if 'tty' not in ch.get('DEVPATH'):
                        self.devpath = ch.get('DEVPATH')
                        self.ConnectionMade()

        cm = Monitor.from_netlink(context)
        cm.filter_by(subsystem='usb')
        observer = MonitorObserver(cm, callback=self.ConnectionMCallBack, name='monitor-observer')
        observer.start()

    def ConnectionMCallBack(self, dd):
        if self.devpath == '':
            if dd.get('ID_SERIAL_SHORT') == self.serial_num:
                for ch in dd.children:
                    if 'tty' not in ch.get('DEVPATH'):
                        self.devpath = ch.get('DEVPATH')
                        self.ConnectionMade()
        elif dd.get('DEVPATH') == self.devpath:
            if dd.action == 'remove':
                self.ConnectionLost()
            if dd.action == 'add' and self.device.closed:
                self.ConnectionMade()

    def ConnectionMade(self):
        self.device.open()
        self.device.baudrate = self.baudrate
        self.device.ftdi_fn.ftdi_set_line_property(8, 1, 0)  # number of bits, number of stop bits, no parity

        time.sleep(50.0/1000)
        self.device.flush(pylibftdi.FLUSH_BOTH)
        time.sleep(50.0/1000)

        # this is pulled from ftdi.h
        SIO_RTS_CTS_HS = (0x1 << 8)
        self.device.ftdi_fn.ftdi_setflowctrl(SIO_RTS_CTS_HS)
        self.device.ftdi_fn.ftdi_setrts(1)

        print('Connected to', self.devpath)

    def ConnectionLost(self):
        self.device.close()
        print('Disconnected from', self.devpath)

    def send_message(self, packed_msg):
        if self._debug:
            print(">>", self.devpath, '>>', packed_msg, '(',packed_msg.hex(':'),')')
        self.device.write(packed_msg)

    def ProcessMessage(self, msg):
        pass

    def update(self):
        print ('dummy updater')
        pass

    def read(self):
        print ('dummy read')
        pass


class SerialUSBProtocol(Protocol):
    """ Class for outgoing connection to a USB serial device """
    _comand_end_character = b''
    _buffer = b''
    _devname = None
    _refresh = 1.0
    _binary_length = None

    def __init__(self, serial_num, obj, refresh=0, baudrate=115200, bytesize=8, parity='N', stopbits=2, timeout=400, debug=False):
        # Name and type of the connection peer
        self.name = ''
        self.type = ''

        self.serial_num = serial_num
        self.object = obj
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout

        self._debug = debug

        if refresh > 0:
            self._refresh = refresh

        self._updateTimer = LoopingCall(self.update)

        context = Context()
        for device in context.list_devices(subsystem='tty'):
            if device.get('ID_SERIAL_SHORT') == self.serial_num:
                self._devname = device['DEVNAME']
                self.Connect()

        cm = Monitor.from_netlink(context)
        cm.filter_by(subsystem='tty')
        observer = MonitorObserver(cm, callback=self.ConnectionMCallBack, name='monitor-observer')
        observer.start()

    def Connect(self):
        self.object['hw'] = SerialPort(self, self._devname, self.object['daemon']._reactor,
                                       baudrate=self.baudrate, bytesize=self.bytesize, parity=self.parity, stopbits=self.stopbits, timeout=self.timeout)

    def ConnectionMCallBack(self, dd):
        if self._devname == '':
            if dd.get('ID_SERIAL_SHORT') == self.serial_num:
                self._devname = device['DEVNAME']
                self.Connect()
        elif dd.get('DEVNAME') == self._devname:
            if dd.action == 'add':
                self.Connect()

    def connectionMade(self):
        print('Connected to', self._devname, 'serial number', self.serial_num)
        self._updateTimer.start(self._refresh)

    def connectionLost(self, reason):
        print('Disconnected from', self._devname, 'serial number', self.serial_num, reason)
        self._updateTimer.stop(self._refresh)

    def update(self):
        pass

    def dataReceived(self, data):
        """Parse incoming data and split it into messages"""
        # NOTE: user is responsible for not switching between binary ans string modes while in the process of receiving data
        self._buffer = self._buffer + data
        while len(self._buffer):
            if len(self._buffer) >= self._binary_length:
                bdata = self._buffer[:self._binary_length]
                self._buffer = self._buffer[self._binary_length:]
                self.processBinary(bdata)

    def message(self, string):
        """Sending outgoing message"""
        if type(string) == str:
            string = string.encode('ascii')+self._comand_end_character
        else:
            string = string+self._comand_end_character

        if self._debug:
            print(">>", self._devname, '>>', string)

        self.transport.write(string)


class SimpleProtocol(Protocol):
    """Class corresponding to a single connection, either incoming or outgoing"""
    _debug = False

    # Some sensible TCP keepalive settings. This way the connection will close after 13 seconds of network failure
    _tcp_keepidle = 10  # Interval to wait before sending first keepalive packet
    _tcp_keepintvl = 1  # Interval between packets
    _tcp_keepcnt = 3  # Number of retries
    _tcp_user_timeout = 10000  # Number of milliseconds to wait before closing the connection on retransmission
    _refresh = 1.0
    _comand_end_character = b'\n'

    def __init__(self, refresh=0):
        self._buffer = b''
        self._is_binary = False
        self._binary_length = 0
        self._peer = None

        if refresh > 0:
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

        print("Connected to %s:%d" % (self._peer.host, self._peer.port))

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
            TCP_USER_TIMEOUT = 0x12

            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, TCP_KEEPIDLE, self._tcp_keepidle)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, self._tcp_keepintvl)
            self.transport.getHandle().setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._tcp_keepcnt)
            # FIXME: works since 2.6.37 only
            self.transport.getHandle().setsockopt(socket.SOL_TCP, TCP_USER_TIMEOUT, self._tcp_user_timeout)

    def connectionLost(self, reason):
        """Method called when connection is finished"""
        self.factory.connections.remove(self)

        self._updateTimer.stop()

        print("Disconnected from %s:%d" % (self._peer.host, self._peer.port))

    def message(self, string):
        """Sending outgoing message"""
        if type(string) == str:
            string = string.encode('ascii')+self._comand_end_character
        else:
            string = string+self._comand_end_character

        if self._debug:
            print(">>", self._peer.host, self._peer.port, '>>', string)

        self.transport.write(string)

    def dataReceived(self, data):
        """Parse incoming data and split it into messages"""
        # NOTE: user is responsible for not switching between binary ans string modes while in the process of receiving data
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
                    token, self._buffer = re.split(b'\0|\n', self._buffer, 1)
                    self.processMessage(token.decode('ascii'))
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
            print("%s:%d = binary mode waiting for %d bytes" % (self._peer.host, self._peer.port, length))

    def processMessage(self, string):
        """Process single message"""
        if self._debug:
            print("%s:%d > %s" % (self._peer.host, self._peer.port, string))

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
        else:
            return cmd

        return None

    def processBinary(self, data):
        """Process binary data when completely read out"""
        if self._debug:
            print("%s:%d binary > %d bytes" % (self._peer.host, self._peer.port, len(data)))

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

        self.connections = []  # List of all currently active connections
        self.object = object  # User-supplied object what should be accessible by all connections and daemon itself

        # Name and type of the daemon
        self.name = ''
        self.type = ''

        # number of connections made since the deamon start
        self._nconnections = 0

        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor

    def buildProtocol(self, addr):
        p = self._protocol()

        p.factory = self
        if p.name == '':
            # Assign some default name to the connection
            p.name = 'anonymous%03d' % self._nconnections
            self._nconnections += 1

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

    def messageAll(self, string, name=None, type=None, **kwargs):
        """Send the message to all (or with a given name/type only) active connections"""
        for c in self.connections:
            if name and c.name != name:
                continue
            if type and c.type != type:
                continue
            c.message(string, **kwargs)

    def listen(self, port=0):
        """Listen for incoming connections on a given port"""
        print("Listening for incoming connections on port %d" % port)
        TCP4ServerEndpoint(self._reactor, port).listen(self)

    def connect(self, host, port, reconnect=True):
        """Initiate outgoing connection, either persistent or no"""
        print("Initiating connection to %s:%d" % (host, port))
        ep = TCP4ClientEndpoint(self._reactor, host, port)
        if reconnect:
            service = ClientService(ep, self, retryPolicy=lambda x: 1)
            service.startService()
        else:
            ep.connect(self)

    def log(self, message, type='info'):
        """Generic interface for sending system-level log messages, to be stored to DB and shown in GUI"""
        # TODO: should we send it to specific names/types only?
        self.messageAll(type + ' ' + message, name='monitor')
