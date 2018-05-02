#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol
from twisted.internet.serialport import SerialPort
from twisted.internet.task import LoopingCall
from command import Command

### Example code with server daemon and outgoing connection to hardware

class DaemonProtocol(SimpleProtocol):
    # _debug = True # Display all traffic for debug purposes

    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        if cmd.name == 'get_status':
            self.message('status hw_connected=%s status=%d pressure=%g' % (self.object['hw_connected'], self.object['status'], self.object['pressure']))
        else:
            if obj['hw_connected']:
                # Pass all other commands directly to hardware
                hw.protocol.message(string)

class HWProtocol(SimpleProtocol):
    # _debug = True # Display all traffic for debug purposes

    def connectionMade(self):
        self.object['hw_connected'] = 1
        # SimpleProtocol.connectionMade(self)
        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)

    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        self.object['status'] = -1
        self.object['pressure'] = 0
        # SimpleProtocol.connectionLost(self, reason)
        self._updateTimer.stop()

    def processMessage(self, string):
        # Process the device reply
        if self._debug:
            print "hw > %s" % string

        if len(string) and string[0] >= '0' and string[0] <= '6' and 'E' in string:
            # b,sx.xxxxEsxx
            self.object['status'] = int(string[0])
            self.object['pressure'] = float(string[2:])

    def message(self, string):
        """Sending outgoing message"""
        if self._debug:
            print ">> serial >>", string
        self.transport.write(string)
        self.transport.write("\r\n")

    def update(self):
        # Request the hardware state from the device
        self.message('COM') # Start periodic reporting of status
        pass

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', default='/dev/ttyUSB0')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7023)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='pfeiffer')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'status':-1, 'pressure':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)

    proto = HWProtocol()
    proto.object = obj
    hw = SerialPort(proto, options.hw_port, daemon._reactor, baudrate=9600)
    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
