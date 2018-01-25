#!/usr/bin/env python

import os, sys, datetime

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
            self.message('status hw_connected=%s value=%g units=%s timestamp=%g' % (self.object['hw_connected'], self.object['value'], self.object['units'], self.object['timestamp']))
        elif cmd.name in ['reset']:
            daemon.log('Resetting Keithley 6487')
            self.sendCommand('*RST')
        elif cmd.name in ['idn']:
            self.sendCommand('*idn?', keep=True)
        elif string and string[0] == '*':
            # For debug purposes only
            self.sendCommand(string)

    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        hw.messageAll(string, type='hw', keep=keep)

class KeithleyProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = [] # Queue of command sent to the device which will provide replies
        self.name = 'hw'
        self.type = 'hw'

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.object['hw_connected'] = 0 # We will set this flag when we receive any reply from the device
        self.message('set_addr %d' % self.object['addr'])

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        daemon = obj['daemon']

        print 'KEITHLEY >> %s' % string

        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1

        # Process the device reply
        if len(self.commands):
            # We have some sent commands in the queue - let's check what was the oldest one
            if self.commands[0] == '*idn?':
                # Example of how to broadcast some message to be printed on screen and stored to database
                daemon.log(string)
            elif self.commands[0] == 'read?':
                #print "new reading:", string
                s = string.split(',')
                obj['value'] = float(s[0][:-1])
                obj['units'] = s[0][-1]
                obj['timestamp'] = float(s[1])

            # Remove oldest command from queue
            self.commands.pop(0)
        pass

    @catch
    def message(self, string, keep=False):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        SimpleProtocol.message(self, '%s' % (string))
        print 'KEITHLEY << %s' % string

        if keep:
            cmd = Command(string)
            self.commands.append(cmd.name)

    @catch
    def update(self):
        if (datetime.datetime.utcnow() - obj['hw_last_reply_time']).total_seconds() > 10:
            # We did not get any reply from device during last 10 seconds, probably it is disconnected?
            obj['hw_connected'] = 0

            # TODO: should we clear the command queue here?

        # Request the hardware state from the device
        self.message('read?', keep=True)

        pass

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=14)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7021)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley6487')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'addr':options.addr, 'value':0, 'units':'', 'timestamp':0, range:0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(KeithleyProtocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    obj['hw_last_reply_time'] = datetime.datetime(1970, 1, 1) # Arbitrarily old time moment

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
