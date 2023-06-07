#!/usr/bin/env python3

import datetime
import numpy as np
import re

from daemon import SimpleFactory, SimpleProtocol, catch


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return
        obj = self.object
        hw = obj['hw']
        string = string.strip()
        STRING = string.upper()
        while True:
            if string == 'get_status':
                self.message('status hw_connected=%s VSet1=%g VSet2=%g VSet3=%g VSet4=%g '
                             'V1=%g V2=%g V3=%g V4=%g '
                             'ILim1=%g ILim2=%g ILim3=%g ILim4=%g '
                             'I1=%g I2=%g I3=%g I4=%g '
                             'VOut1=%i VOut2=%i VOut3=%i VOut4=%i '
                             'OVP1=%g OVP2=%g OVP3=%g OVP4=%g '
                             'OCP1=%s OCP2=%s OCP3=%s OCP4=%s' %
                             (self.object['hw_connected'],
                              self.object['V1'], self.object['V2'], self.object['V3'], self.object['V4'],
                              self.object['V1O'], self.object['V2O'], self.object['V3O'], self.object['V4O'],
                              self.object['I1'], self.object['I2'], self.object['I3'], self.object['I4'],
                              self.object['I1O'], self.object['I2O'], self.object['I3O'], self.object['I4O'],
                              self.object['VOut1'], self.object['VOut2'], self.object['VOut3'], self.object['VOut4'],
                              self.object['OVP1'], self.object['OVP2'], self.object['OVP3'], self.object['OVP4'],
                              self.object['OCP1'], self.object['OCP2'], self.object['OCP3'], self.object['OCP4'],))
                break
            if string == 'reset_q':
                hw.messageAll('reset_q', type='hw', keep=False, source=self.name)
                break

            regex0 = re.compile(r'\:?ENGAGE(?P<val>([1-4])\b)')
            regex1 = re.compile(r'\:?OP(?P<val>([1-4])).1')
            match = re.match(regex0, STRING)
            if not match:
                match = re.match(regex1, STRING)
            if match:
                hw.messageAll('OP' + match.group('val') + ' 1\n', type='hw', keep=False, source=self.name)
                obj['VOut'+match.group('val')] = 1
                break

            regex0 = re.compile(r'\:?DISENGAGE(?P<val>([1-4])\b)')
            regex1 = re.compile(r'\:?OP(?P<val>([1-4])).0')
            match = re.match(regex0, STRING)
            if not match:
                match = re.match(regex1, STRING)
            if match:
                hw.messageAll('OP' + match.group('val') + ' 0\n', type='hw', keep=False, source=self.name)
                obj['VOut'+match.group('val')] = 0
                break

            if STRING[-1] == '?':
                hw.messageAll(string, type='hw', keep=True, source=self.name)
            else:
                hw.messageAll(string, type='hw', keep=False, source=self.name)
            break


class mx100qp_Protocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _refresh = 0.01

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.status_commands = ['I1?', 'V1?', 'I1O?', 'V1O?', 'OP1?',
                                'I2?', 'V2?', 'I2O?', 'V2O?', 'OP2?',
                                'I3?', 'V3?', 'I3O?', 'V3O?', 'OP3?',
                                'I4?', 'V4?', 'I4O?', 'V4O?', 'OP4?',
                                'OVP1?', 'OVP2?', 'OVP3?', 'OVP4?',
                                'OCP1?', 'OCP2?', 'OCP3?', 'OCP4?',
                                'CONFIG?', ]
        #self.status_commands = []
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

    @catch
    def connectionLost(self, reason):
        self.commands = []
        SimpleProtocol.connectionLost(self, reason)
        resetObjStatus(self.object)

    @catch
    def processMessage(self, string):
        obj = self.object  # Object holding the state
        if self._debug:
            print('MX100QP >> %s' % string)
        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
        # Process the device reply
        while len(self.commands):
            ccmd = self.commands[0]['cmd'].decode()
            # We have some sent commands in the queue - let's check what was the oldest one
            br = False
            for ch in ['1', '2', '3', '4']:
                if ccmd == 'I'+ch+'?':
                    obj['I'+ch] = float(string[3:-1])
                    br = True
                    break
                if ccmd == 'V'+ch+'?':
                    obj['V'+ch] = float(string[3:-1])
                    br = True
                    break
                if ccmd == 'V'+ch+'O?':
                    obj['V'+ch+'O'] = float(string[0:-2])
                    br = True
                    break
                if ccmd == 'I'+ch+'O?':
                    obj['I'+ch+'O'] = float(string[0:-2])
                    br = True
                    break
                if ccmd == 'OP'+ch+'?':
                    obj['VOut'+ch] = int(string[0])
                    br = True
                    break
                if ccmd == 'OVP'+ch+'?':
                    obj['OVP'+ch] = float(string[:-1].split()[1])
                    br = True
                    break
                if ccmd == 'OCP'+ch+'?':
                    obj['OCP'+ch] = float(string[:-1].split()[1])
                    br = True
                    break
            if br:
                break

            # some more commands
            break
        else:
            return
        if not self.commands[0]['source'] == 'itself':
            # in case the origin of the query was not itself, forward the answer to the origin
            obj['daemon'].messageAll(string, self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def update(self):
        if self._debug:
            print('--------self.commands--------------')
            for cc in self.commands:
                print(cc)
            print('----------------------')
        # first check if device is hw_connected
        if self.object['hw_connected'] == 0:
            # if not connected do not send any commands
            return

        if len(self.commands) and not self.commands[0]['sent']:
            SimpleProtocol.message(self, self.commands[0]['cmd'])
            if not self.commands[0]['keep']:
                self.commands.pop(0)
            else:
                self.commands[0]['sent'] = True
        elif not len(self.commands):
            for k in self.status_commands:
                self.commands.append({'cmd': k.encode('ascii'), 'source': 'itself', 'keep': True, 'sent': False})

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, expect reply
        """
        if string == b'reset_q':
            self.commands = []
            return

        if string in [b'EER?', b'QER?']:
            self.commands.insert(0, {'cmd': string, 'source': source, 'keep': keep, 'sent': False})
            return

        n = 0
        for cc in self.commands:
            if not cc['sent']:
                break
            n += 1
        if self._debug:
            print('cmd', string, 'from', source, 'will be inserted at', n)
        self.commands.insert(n, {'cmd': string, 'source': source, 'keep': keep, 'sent': False})


def resetObjStatus(obj):
    obj['hw_connected'] = 0
    obj['I1'] = np.nan
    obj['V1'] = np.nan
    obj['I1O'] = np.nan
    obj['V1O'] = np.nan
    obj['VOut1'] = 0
    obj['I2'] = np.nan
    obj['V2'] = np.nan
    obj['I2O'] = np.nan
    obj['V2O'] = np.nan
    obj['VOut2'] = 0
    obj['I3'] = np.nan
    obj['V3'] = np.nan
    obj['I3O'] = np.nan
    obj['V3O'] = np.nan
    obj['VOut3'] = 0
    obj['I4'] = np.nan
    obj['V4'] = np.nan
    obj['I4O'] = np.nan
    obj['V4O'] = np.nan
    obj['VOut4'] = 0
    obj['OVP1'] = np.nan
    obj['OVP2'] = np.nan
    obj['OVP3'] = np.nan
    obj['OVP4'] = np.nan
    obj['OCP1'] = np.nan
    obj['OCP2'] = np.nan
    obj['OCP3'] = np.nan
    obj['OCP4'] = np.nan


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='192.168.1.14')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=9221)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7034)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='mx100qp')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")
    (options, args) = parser.parse_args()
    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {}
    resetObjStatus(obj)

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(mx100qp_Protocol, obj)
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
