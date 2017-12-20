#!/usr/bin/env python

import os, sys

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch

def dictToString(kwargs, prefix=''):
    return " ".join([prefix + _ + '=' + kwargs[_] for _ in kwargs])

class DaemonProtocol(SimpleProtocol):
    _debug = True # Display all traffic for debug purposes

    @catch
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

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.command_id = 0
        self.name = 'hw'
        self.type = 'hw'
        self.commands = {}

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)

        self.object['hw_connected'] = 1
        self.object['status'] = {}

        self.message('SYSTEM')

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        self.object['status'] = {}
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        # Process the device reply
        if string[0] != '<':
            print "Wrong reply from controller: %s" % string
            return

        id = int(string[1:3], 16)
        cmd = Command(string[3:])

        # Process and transform specific fields to be more understandable
        for key in cmd.kwargs:
            newkey = key.replace('/', '_')
            if newkey != key:
                # Rename the argument key
                cmd.kwargs[newkey] = cmd.kwargs.pop(key)

        if self.commands.get(id, '') == 'SYSTEM':
            cmd.kwargs['BACKPLANE_TYPE'] = {'0':'None', '1':'X12', '2':'X16'}.get(cmd.kwargs['BACKPLANE_TYPE'], 'unknown')
            self.object['Nmods'] = 12 if cmd.kwargs['BACKPLANE_TYPE'] == 'X12' else 16

            for _ in xrange(1, self.object['Nmods']+1):
                cmd.kwargs['MOD%d_TYPE' % _] = {'0':'None',
                                                '1':'Driver',
                                                '2':'AD',
                                                '3':'LVBias',
                                                '4':'HVBias',
                                                '5':'Heater',
                                                '6':'Atlas',
                                                '7':'HS',
                                                '8':'HVXBias',
                                                '9':'LVXBias',
                                                '10':'LVDS',
                                                '11':'HeaterX',
                                                '12':'XVBias',
                                                '13':'ADF'}.get(cmd.kwargs['MOD%d_TYPE' % _], 'unknown')

        elif self.commands.get(id, '') == 'STATUS':
            cmd.kwargs['POWER'] = {'0':'Unknown', '1':'NotConfigured', '2':'Off', '3':'Intermediate', '4':'On', '5':'Standby'}.get(cmd.kwargs['POWER'], 'unknown')

        self.commands.pop(id, '')

        self.object['status'].update(cmd.kwargs)

    @catch
    def message(self, string):
        SimpleProtocol.message(self, '>%02x%s' % (self.command_id, string))
        self.commands[self.command_id] = string
        self.command_id = (self.command_id + 1) % 0x100

    @catch
    def update(self):
        # Request the hardware state from the device
        self.message('STATUS')
        self.message('FRAME')

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
