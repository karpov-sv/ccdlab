#!/usr/bin/env python

import os
import sys
import datetime
import re

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return
        obj = self.object
        daemon = self.factory
        hw = obj['hw']
        string = string.strip()
        STRING = string.upper()
        while True:
            if string == 'get_status':
                self.message('status hw_connected=%s Current=%g Voltage=%g CurrentActual=%g VoltageActual=%g' %
                             (self.object['hw_connected'], self.object['Current'], self.object['Voltage'], self.object['CurrentActual'], self.object['VoltageActual']))
                break
            if string == 'reset':
                self.sendCommand('*RST', keep=True)
                break
            if string == 'idn':
                self.sendCommand('*IDN?', keep=True)
                break
            if string == 'config':
                self.sendCommand('CONFIG?', keep=True)
                break
            if string == 'get_voltage':
                self.sendCommand('V1?', keep=True)
                break
            if string == 'get_readback_voltage':
                self.sendCommand('V1O?', keep=True)
                break
            if string == 'get_readback_current':
                self.sendCommand('I1O?', keep=True)
                break
            if string == 'get_voltage_limit':
                self.sendCommand('OVP1?', keep=True)
                break
            if string == 'get_current_limit':
                self.sendCommand('I1?', keep=True)
                break
            if string == 'step_size_voltage':
                self.sendCommand('DELTAV1?', keep=True)
                break
            if string == 'get_current_trip':
                self.sendCommand('OCP1?', keep=True)
                break
            else:
                self.sendCommand(cmd.name, keep=False)

            regex = re.compile(r'(\:?(V1|SET_VOLTAGE) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('V1 ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                break

            regex = re.compile(r'(\:?(I1|SET_CURRENT_LIMIT) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('I1 ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                break

            regex = re.compile(r'(\:?(OVP1|SET_VOLTAGE_LIMIT) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('OVP1 ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                break

            regex = re.compile(r'(\:?(DELTAV1|SET_STEP_SIZE_VOLTAGE) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('DELTAV1 ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                break

            regex = re.compile(r'(\:?(INCV1|INCREMENT_VOLTAGE) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('INCV1 ' + '\n', type='hw', keep=False, source=self.name)
                break

            regex = re.compile(r'(\:?(DECV1|DECREMENT_VOLTAGE) (?P<val>(\d+\.\d+?$|\d+?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('DECV1 ' + '\n', type='hw', keep=False, source=self.name)
                break
            break

    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object  # Object holding the state
        hw = obj['hw']  # HW factory
        hw.messageAll(string, type='hw', keep=keep, source=self.name)


class plh120_Protocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _refresh = 0.1

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.name = 'hw'
        self.type = 'hw'
        self.lastAutoRead = datetime.datetime.utcnow()

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)
        self.commands = []
        # We will set this flag when we receive any reply from the device
        self.object['hw_connected'] = 1
        SimpleProtocol.message(self, '*RST')
        SimpleProtocol.message(self, '*IDN?')

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        obj = self.object  # Object holding the state
        daemon = obj['daemon']
        if self._debug:
            print 'PLH120-P >> %s' % string
            #print 'commands Q:', self.commands
        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
        # Process the device reply
        while len(self.commands):
            # We have some sent commands in the queue - let's check what was the oldest one
            if self.commands[0]['cmd'] == '*RST' and self.commands[0]['source'] == 'itself':
                # not used at the moment
                pass
                break
            if self.commands[0]['cmd'] == '*IDN?' and self.commands[0]['source'] == 'itself':
                # Example of how to broadcast some message to be printed on screen and stored to database
                # daemon.log(string)
                pass
                break
            if self.commands[0]['cmd'] == 'I1?' and self.commands[0]['source'] == 'itself':
                obj['Current'] = float(string[3:-1])
                break
            if self.commands[0]['cmd'] == 'V1?' and self.commands[0]['source'] == 'itself':
                obj['Voltage'] = float(string[3:-1])
                break
            if self.commands[0]['cmd'] == 'OVP1?' and self.commands[0]['source'] == 'itself':
                obj['OVP1'] = float(string[3:-1])
                break
            if self.commands[0]['cmd'] == 'DELTAV1?' and self.commands[0]['source'] == 'itself':
                obj['DELTAV1'] = float(string[7:-1])
                break
            if self.commands[0]['cmd'] == 'V1O?' and self.commands[0]['source'] == 'itself':
                obj['V1O'] = float(string[0:-2])
                break
            if self.commands[0]['cmd'] == 'I1O?' and self.commands[0]['source'] == 'itself':
                obj['I1O'] = float(string[0:-2])
                break
            if not self.commands[0]['source'] == 'itself':
                # in case the origin of the query was not itself, forward the answer to the origin
                daemon.messageAll(string, self.commands[0]['source'])
                break
            break
        else:
            return
        self.commands.pop(0)

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        if keep:
            self.commands.append({'cmd': string,
                                  'source': source,
                                  'timeStamp': datetime.datetime.utcnow(),
                                  'keep': keep})
            SimpleProtocol.message(self, '%s' % string)
        else:
            SimpleProtocol.message(self, string)

    @catch
    def update(self):
        if (datetime.datetime.utcnow() - obj['hw_last_reply_time']).total_seconds() > 10:
            # We did not get any reply from device during last 10 seconds, probably it is disconnected?
            self.object['hw_connected'] = 0
            # TODO: should we clear the command queue here?
        # first check if device is hw_connected
        if self.object['hw_connected'] == 0:
            # if not connected do not send any commands
            return
        elif (datetime.datetime.utcnow() - self.lastAutoRead).total_seconds() > 2. and len(self.commands) == 0:
            # Request the hardware state from the device
            self.message('I1?', keep=True, source='itself')
            self.message('V1?', keep=True, source='itself')
            self.message('I1O?', keep=True, source='itself')
            self.message('V1O?', keep=True, source='itself')
            self.message('CONFIG?', keep=True, source='itself')
            self.message('*IDN?', keep=True, source='itself')
            self.lastAutoRead = datetime.datetime.utcnow()


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='192.168.1.6')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=9221)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7026)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='plh120-p')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")
    (options, args) = parser.parse_args()
    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0,
           'Current': 0,
           'Voltage': 0,
           'CurrentActual': 0,
           'VoltageActual': 0}
    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(plh120_Protocol, obj)
    if options.debug:
        daemon._protocol._debug = True
        hw._protocol._debug = True
    daemon.name = options.name
    obj['daemon'] = daemon
    obj['hw'] = hw
    obj['hw_last_reply_time'] = datetime.datetime(1970, 1, 1)  # Arbitrarily old time moment
    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)
    daemon._reactor.run()
