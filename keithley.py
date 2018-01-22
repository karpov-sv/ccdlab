#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch

class DaemonProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        daemon = self.factory
        hw = obj['hw'] # HW factory

        if cmd.name == 'get_status':
            self.message('status hw_connected=%s' % (self.object['hw_connected']))
        elif cmd.name in ['start', 'poweron']:
            daemon.log('Powering on')
            self.sendCommand('POWERON')

    @catch
    def sendCommand(self, string):
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        hw.messageAll(string, type='hw')

class KeithleyProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    _tcp_keepidle = 1 # Faster detection of peer disconnection

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.command_id = 0
        self.name = 'hw'
        self.type = 'hw'

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.object['hw_connected'] = 1
        # self.message('SYSTEM') # Request some initial info on the device

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        SimpleProtocol.processMessage(self, string)
        daemon = self.object['daemon']

        print 'KEITHLEY >> %s' % string

        # Process the device reply
        pass

    @catch
    def message(self, string):
        SimpleProtocol.message(self, '%s' % (string))
        print 'KEITHLEY << %s' % string

    @catch
    def update(self):
        # Request the hardware state from the device
        # self.message('STATUS')
        pass

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=4242)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7002)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(KeithleyProtocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
