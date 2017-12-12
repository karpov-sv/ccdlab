#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol, Command

### Example code with server daemon and outgoing connection to hardware

class DaemonProtocol(SimpleProtocol):
    _debug = True

    def processMessage(self, string):
        if self._debug:
            print "%s:%d > %s" % (self._peer.host, self._peer.port, string)

        cmd = Command(string)

        if cmd.name == 'get_status':
            self.message('status hw_connected=%s' % self.object['hw_connected'])

class HWProtocol(SimpleProtocol):
    def connectionMade(self):
        self.object['hw_connected'] = 1
        SimpleProtocol.connectionMade(self)

    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    def processMessage(self, string):
        # Process the device reply
        print "hw > %s" % string

    def update(self):
        # Request the hardware state from the device
        self.message('status?')

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=8099)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=12345)

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(HWProtocol, obj)

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
