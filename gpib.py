#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch

class DaemonProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.addr = -1

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        daemon = self.factory
        hw = obj['hw'] # HW factory

        if cmd.name == 'get_status':
            self.message('status hw_connected=%s current_addr=%d' % (obj['hw_connected'], obj['current_addr']))
        elif cmd.name == 'set_addr':
            self.addr = int(cmd.args[0]) if len(cmd.args) else -1
        elif cmd.name == 'send':
            # TODO: escape all necessary characters in the string
            self.sendCommand(" ".join(cmd.chunks[1:]))
        elif self.addr >= 0:
            # FIXME: we should somehow prevent the commands already processed in superclass from arriving here
            self.sendCommand(string)

    @catch
    def sendCommand(self, string):
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        if hw.object['current_addr'] != self.addr:
            # Switching GPIB address to the one of current connection
            hw.object['current_addr'] = self.addr
            hw.messageAll('++addr %d' % self.addr)

        hw.messageAll(string, type='hw')

class GPIBProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes
    _tcp_keepidle = 10 # Faster detection of peer disconnection

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.command_id = 0
        self.commands = []
        self.name = 'hw'
        self.type = 'hw'

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.object['hw_connected'] = 1
        self.object['current_addr'] = -1 # We are resetting it to be sure that we have proper address later

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        SimpleProtocol.processMessage(self, string)
        daemon = self.object['daemon']

        # Process the device reply
        if len(self.commands) and self.commands[0] in ['++addr']:
            # We are silently ignoring the results from these commands
            self.commands.pop(0) # Remove the command from queue
        else:
            for conn in daemon.connections:
                if conn.addr == self.object['current_addr'] and self.object['current_addr'] >= 0:
                    # Send the device reply to the client connection with given address
                    conn.message(string)

        pass

    @catch
    def message(self, string, keep=False):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        SimpleProtocol.message(self, '%s' % (string))

        if keep:
            cmd = Command(string)
            self.commands.append(cmd.name)

    @catch
    def update(self):
        # FIXME: Our GPIB controller does not support TCP keepalive, so let's
        # just send some harmless message just to keep the connection up.
        self.message('++addr', keep=True)
        pass

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='10.0.0.2')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=1234)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7020)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='gpib')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'current_addr':-1}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(GPIBProtocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
