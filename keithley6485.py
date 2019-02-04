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
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return
        obj = self.object  # Object holding the state
        daemon = self.factory
        hw = obj['hw']  # HW factory

        string = string.strip()
        STRING = string.upper()

        while True:
            if string == 'get_status':
                self.message('status hw_connected=%s value=%g units=%s timestamp=%g' %
                             (self.object['hw_connected'], self.object['value'], self.object['units'], self.object['timestamp']))
                break
            if string == 'reset':
                daemon.log('Resetting Keithley 6485')
                self.sendCommand('*RST')
                daemon.log('Device reset')
                break
            if string == 'idn':
                self.sendCommand('*idn?', keep=True)
                break

            regex = re.compile(r'\:?(SYST|SYSTE|SYSTEM)\:(ZCH|ZCHE|ZCHEC|ZCHECK)\:(STAT|STATE)\?')
            if re.match(regex, STRING) or string == 'get_zcheck_state':
                hw.messageAll(':SYST:ZCH:STAT?\n', type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'(\:?(SYST|SYSTE|SYSTEM)\:(ZCH|ZCHE|ZCHEC|ZCHECK)\:(STAT|STATE)|SET_ZCHECK_STATE) (?P<state>(ON|OFF))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll(':SYST:ZCH:STAT ' + match.group('state') + '\n', type='hw', keep=False, source=self.name)
                daemon.log('Zero-check state set to ' + match.group('state'))
                break

            regex = re.compile(r'(\:?(CURR|CURRE|CURREN|CURRENT):(RANG|RANGE)|SET_CURRENT_RANGE) (?P<val>(0\.\d+?$|2E\-\d?$))')
            match = re.match(regex, STRING)
            if match:
                allowed_values = [2E-2, 2E-3, 2E-4, 2E-5, 2E-6, 2E-7, 2E-8, 2E-9]
                if float(match.group('val')) not in allowed_values:
                    daemon.log('WARNING wrong range value ' + match.group('val'))
                    break
                else:
                    hw.messageAll(':CURR:RANG ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                    daemon.log('Range set to ' + match.group('val'))
                    break

#            regex = re.compiler(r'(\:?(SYST|SYST|SYSTEM)\:(ZCOR|ZCORR|ZCORRE|ZCORREC|ZCORRECT)\:(STAT|STATE)|SET_ZCOR_STATE) (?P<state>(ON|OFF))')
#            match = re.match(regex, STRING)
#            if match:
#                hw.messageAll(':SYST:ZCOR:STAT' + match.group('state') + '\n', type='hw', keep=False, source=self.name)
#                daemon.log('Zero-correct state set to' + match.group('state'))
#                break


#            regex = re.compile(r'do_zero_check (?P<val>(0\.\d+?$|2E\-\d?$)))')
#            match = re.match(regex, string)
#            if match :
#                if  match.group('val') = '0' :
#                    val = '2E-2'
#                else :
#                    val = match.group('val')
#                if float(match.group('val')) not in allowed_values:
#                    daemon.log('WARNING wrong range value ' + match.group('val'))
#                    break
#                else :
#                      hw.messageAll(':SYST:ZCH ON\n', type='hw', keep=True, source=self.name)
#                      hw.messageAll(':CURR:RANG ' + val + '\n', type='hw', keep=False, source=self.name)
#                      hw.messageAll(':INIT')
#                      hw.messageAll(':SYST:ZCOR:ACQ'\n, type='hw', keep=True, source=self.name)
#                      hw.messageAll(':SYST:ZCH OFF\n', type='hw', keep=True, source=self.name)
#	               hw.messageAll(':SYSR:ZCOR ON'\n', type='hw', keep=True, source=self.name))
#                      break

            if cmd.name in ['get_curr_range']:
                self.sendCommand('CURR:RANGE?', keep=True)
                break
            if cmd.name in ['zero_check_on']:
                self.sendCommand('SYST:ZCH ON')
                break
            if cmd.name in ['trigger']:
                self.sendCommand('INIT')
                break
            if cmd.name in ['zero_check_aquire']:
                self.sendCommand('SYST:ZCOR:ACQ')
                break
            if cmd.name in ['zero_check_do']:
                self.sendCommand('SYST:ZCOR ON')
                break
            if cmd.name in ['set_curr_range_auto']:
                self.sendCommand('CURR:RANG:AUTO ON')
                break

            if cmd.name[-1] == '?':
                print 'unrecog query cmd', cmd.name
                self.sendCommand(cmd.name, keep=True)
            else:
                self.sendCommand(cmd.name, keep=False)
            break

    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object  # Object holding the state
        hw = obj['hw']  # HW factory
        hw.messageAll(string, type='hw', keep=keep, source=self.name)


class KeithleyProtocol(SimpleProtocol):
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
        self.object['hw_connected'] = 0  # We will set this flag when we receive any reply from the device
        SimpleProtocol.message(self, 'set_addr %d' % self.object['addr'])
        SimpleProtocol.message(self, '*rst')
        SimpleProtocol.message(self, '?$*opc?')
        self.commands = [{'cmd': '*opc?', 'source': 'itself', 'timeStamp': datetime.datetime.utcnow(), 'keep': 'keep'}]

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        obj = self.object  # Object holding the state
        daemon = obj['daemon']

        if self._debug:
            print 'KEITHLEY6485 >> %s' % string
            print 'commands Q:', self.commands
        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1

        # Process the device reply
        while len(self.commands):
            # We have some sent commands in the queue - let's check what was the oldest one
            if self.commands[0]['cmd'] == '*opc?' and self.commands[0]['source'] == 'itself':
                # not used at the moment
                break
            if self.commands[0]['cmd'] == '*idn?' and self.commands[0]['source'] == 'itself':
                # Example of how to broadcast some message to be printed on screen and stored to database
                daemon.log(string)
                break
            if self.commands[0]['cmd'] == 'fetch?' and self.commands[0]['source'] == 'itself':
                s = string.split(',')
                obj['value'] = float(s[0][:-1])
                obj['units'] = s[0][-1]
                obj['timestamp'] = float(s[1])
                break
            if self.commands[0]['cmd'] == 'fetch?' and not self.commands[0]['source'] == 'itself':
                daemon.messageAll(string, self.commands[0]['source'])
                break
            if self.commands[0]['cmd'] == 'CURR:RANGE?':
                daemon.messageAll(string, self.commands[0]['source'])
                break
            if self.commands[0]['cmd'] == 'CURR:RANGE?':
                daemon.messageAll(string, self.commands[0]['source'])
                break
            daemon.messageAll(string, self.commands[0]['source'])
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
            SimpleProtocol.message(self, '?$%s' % string)
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
            self.message('init', keep=False, source='itself')
            self.message('fetch?', keep=True, source='itself')
            self.lastAutoRead = datetime.datetime.utcnow()


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=14)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7021)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley6485')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0, 'addr': options.addr, 'value': 0, 'units': '', 'timestamp': 0, range: 0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(KeithleyProtocol, obj)

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
