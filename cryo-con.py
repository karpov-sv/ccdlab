#!/usr/bin/env python

import os, sys
import numpy as np

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch

class DaemonProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes
    _simulator = False

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory

        if cmd.name == 'get_status':
            if self._simulator:
                self.message('status hw_connected=1 status=0 temperatureA=%g  temperatureB=%g temperatureC=%g temperatureD=%g simulator=1' 
                             % (np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0)))
            else:
                self.message('status hw_connected=%s status=%s temperatureA=%g temperatureB=%g temperatureC=%g temperatureD=%g' 
                             % (self.object['hw_connected'], self.object['status'], 
                                self.object['temperatureA'], self.object['temperatureB'], self.object['temperatureC'], self.object['temperatureD']))
        else:
            if obj['hw_connected']:
                # Pass all other commands directly to hardware
                hw.messageAll(string, name='hw', type='hw')
                
class HWProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self.name = 'hw'
        self.type = 'hw'
        SimpleProtocol.connectionMade(self)
        # make sure the units are Celsius
        self.message('input a,b,c,d:units c')


    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        # Process the device reply
        if self._debug:
            print "hw > %s" % string

        if len(string):
            # values for channel a;b;c;d (....... means dot connected)
            sstring = string.split(';')
            status = ''
            channel = ['temperatureA','temperatureB','temperatureC','temperatureD']
            for s in range(len(sstring)):
                try:
                    sstring[s] = float(sstring[s])
                    status = status+'1'
                    self.object[channel[s]] = sstring[s]
                except ValueError:
                    status = status+'0'
                    self.object[channel[s]] = np.nan
            self.object['status'] = status


    @catch
    def message(self, string):
        """Sending outgoing message"""
        if self._debug:
            print ">> serial >>", string
        self.transport.write(string)
        self.transport.write("\n")


    @catch
    def update(self):
        # Request the hardware state from the device
        self.message('input? a,b,c,d')

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='192.168.1.5')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=5000)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7024)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='cryo-con')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")
    parser.add_option("-S", '--simulator', help='Simulator mode', action="store_true", dest="simulator")

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'status':-1, 'temperatureA':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(HWProtocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    if options.debug:
        daemon._protocol._debug = True
        hw._protocol._debug = True

    if options.simulator:
        daemon._protocol._simulator = True

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
