#!/usr/bin/env python3
import datetime
import re
import numpy as np
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
                self.message('status hw_connected=%s CH1_Stat=%s CH2_Stat=%s '
                             'CH1_Func=%s CH2_Func=%s '
                             'CH1_Freq=%g CH2_Freq=%g '
                             'CH1_Unit=%s CH2_Unit=%s '
                             'CH1_Ampl=%g CH2_Ampl=%g '
                             'CH1_Offs=%g CH2_Offs=%g '
                             'CH1_RSym=%g CH2_RSym=%g' %
                             (obj['hw_connected'],
                              obj['CH1_Stat'], obj['CH2_Stat'],
                              obj['CH1_Func'], obj['CH2_Func'],
                              obj['CH1_Freq'], obj['CH2_Freq'],
                              obj['CH1_Unit'], obj['CH2_Unit'],
                              obj['CH1_Ampl'], obj['CH2_Ampl'],
                              obj['CH1_Offs'], obj['CH2_Offs'],
                              obj['CH1_RSym'], obj['CH2_RSym'],))
                break
            if string == 'reset_q':
                hw.messageAll('reset_q', type='hw', keep=False, source=self.name)
                break

            # will change commands which are also status comands to a standart from, so that they are recognized for status updates
            regex = re.compile(r'\:?SYST(|EM):ERR(|OR)\?')
            m = re.match(regex, STRING)
            if m:
                hw.messageAll('SYST:ERR?', type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?OUTP(|UT)(?P<chan>(1|2))\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'OUTP'+m.group('chan')+'?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):FUNC(|TION)\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':FUNC?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):FREQ(|UENCY)\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':FREQ?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):VOLT(|AGE):UNIT\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':VOLT:UNIT?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):VOLT(|AGE):AMPL(|ITUDE)\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':VOLT:AMPL?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):VOLT(|AGE):OFFS(|ET)\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':VOLT:OFFS?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'\:?SOUR(|CE)(?P<chan>(1|2)):FUNC(|TION):RAMP:SYMM(|ETRY)\?')
            m = re.match(regex, STRING)
            if m:
                STRING = 'SOUR'+m.group('chan')+':FUNC:RAMP:SYMM?'
                hw.messageAll(STRING, type='hw', keep=True, source=self.name)
                break

            if STRING[-1] == '?':
                hw.messageAll(string, type='hw', keep=True, source=self.name)
            else:
                hw.messageAll(string, type='hw', keep=False, source=self.name)
            break


class afg31k_Protocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _refresh = 0.01

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.status_commands = ['OUTP1?', 'OUTP2?',
                                'SOUR1:FUNC?', 'SOUR2:FUNC?',
                                'SOUR1:FREQ?', 'SOUR2:FREQ?',
                                'SOUR1:VOLT:AMPL?', 'SOUR2:VOLT:AMPL?',
                                'SOUR1:VOLT:UNIT?', 'SOUR2:VOLT:UNIT?',
                                'SOUR1:VOLT:OFFS?', 'SOUR2:VOLT:OFFS?',
                                'SOUR1:FUNC:RAMP:SYMM?', 'SOUR2:FUNC:RAMP:SYMM?', ]
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

    @catch
    def connectionLost(self, reason):
        self.commands = []
        SimpleProtocol.connectionLost(self, reason)
        resetObjStatus(self.object)

    @catch
    def processMessage(self, string):
        obj = self.object  # Object holding the state
        if self._debug:
            print('AFG31K >> %s' % string)
        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
        # Process the device reply
        while len(self.commands):
            ccmd = self.commands[0]['cmd'].decode()
            # We have some sent commands in the queue - let's check what was the oldest one
            br = False
            for ch in ['1', '2']:
                if ccmd == 'OUTP'+ch+'?':
                    obj['CH'+ch+'_Stat'] = 'OFF' if string[0] == '0' else 'ON'
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':FUNC?':
                    obj['CH'+ch+'_Func'] = string
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':FREQ?':
                    obj['CH'+ch+'_Freq'] = float(string)
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':VOLT:UNIT?':
                    obj['CH'+ch+'_Unit'] = string
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':VOLT:AMPL?':
                    obj['CH'+ch+'_Ampl'] = float(string)
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':VOLT:OFFS?':
                    obj['CH'+ch+'_Offs'] = float(string)
                    br = True
                    break
                if ccmd == 'SOUR'+ch+':FUNC:RAMP:SYMM?':
                    obj['CH'+ch+'_RSym'] = float(string)
                    br = True
                    break

            if br:
                break

            # some more commans
            break
        else:
            return
        if not self.commands[0]['source'] == 'itself':
            # in case the origin of the query was not itself, forward the answer to the origin
            obj['daemon'].messageAll(string, self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def update(self):
        if self._debug and len(self.commands):
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

        if string == b'SYST:ERR?':
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
    obj['CH1_Stat'] = '-'
    obj['CH2_Stat'] = '-'
    obj['CH1_Func'] = '-'
    obj['CH2_Func'] = '-'
    obj['CH1_Freq'] = np.nan
    obj['CH2_Freq'] = np.nan
    obj['CH1_Unit'] = '-'
    obj['CH2_Unit'] = '-'
    obj['CH1_Ampl'] = np.nan
    obj['CH2_Ampl'] = np.nan
    obj['CH1_Offs'] = np.nan
    obj['CH2_Offs'] = np.nan
    obj['CH1_RSym'] = np.nan
    obj['CH2_RSym'] = np.nan


if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='192.168.1.15')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=5025)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7035)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='afg31k')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")
    (options, args) = parser.parse_args()
    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {}
    resetObjStatus(obj)

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(afg31k_Protocol, obj)
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
