#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol
from command import Command

def dictToString(kwargs, prefix=''):
    return " ".join([prefix + _ + '=' + kwargs[_] for _ in kwargs])

class DaemonProtocol(SimpleProtocol):
    _debug = True # Display all traffic for debug purposes

    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        if cmd.name == 'get_status':
            self.message('status hw_connected=%s %s' % (self.object['hw_connected'], dictToString(obj['status'])))
        else:
            if obj['hw_connected']:
                # Pass all other commands directly to hardware
                hw.messageAll(string, name='hw', type='hw')

class ArchonProtocol(SimpleProtocol):
    _debug = True # Display all traffic for debug purposes

    def connectionMade(self):
        self.object['hw_connected'] = 1
        self.name = 'hw'
        self.type = 'hw'

        self.command_id = 0

        SimpleProtocol.connectionMade(self)

    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    def processMessage(self, string):
        # Process the device reply
        if string[0] != '<':
            print "Wrong reply from controller: %s" % string
            return

        id = int(string[1:3], 16)
        cmd = Command(string[3:])

        self.object['status'] = cmd.kwargs

    def message(self, string):
        SimpleProtocol.message(self, '>%02x%s' % (self.command_id, string))
        self.command_id = (self.command_id + 1) % 0x100

    def update(self):
        # Request the hardware state from the device
        self.message('STATUS')

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=4242)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7001)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='archon')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'status':{}}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(ArchonProtocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
