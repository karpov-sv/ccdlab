#!/usr/bin/env python3
import datetime
import re
import numpy as np 

from daemon import SimpleFactory, SimpleProtocol, catch

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
                self.message('status hw_connected=%s out_load=%g volt_offs=%g, volt_unit=%s' %
                             (self.object['hw_connected'],self.object['out_load'],self.object['volt_offs'],self.object['volt_unit']))
                break
            if STRING == '*IDN?':
                self.sendCommand('*IDN?', keep=True)
                break
            
            regex = re.compile(r'\:?(OUTP|OUTPUT)\:(LOAD)\?')
            if re.match(regex, STRING) or string == 'get_out_load':
                hw.messageAll(':OUTP:LOAD?\n', type='hw', keep=True, source=self.name)
                break
            regex = re.compile(r'(\:?(OUTP|OUTPUT)\:(LOAD) (?P<val>(50|INF|MIN|MAX)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll(':OUTP:LOAD ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                daemon.log('Output load set to ' + match.group('val'))
                break

            regex = re.compile(r'\:?(VOLT|VOLTAGE)\:(OFFS|OFFSET)\?')
            if re.match(regex, STRING) or string == 'get_volt_offs':
                hw.messageAll(':VOLT:OFFS?\n', type='hw', keep=True, source=self.name)
                break
            regex = re.compile(r'(\:?(VOLT|VOLTAGE)\:(OFFS|OFFSET) (?P<val>(MIN|MAX|0\.\d+?$|2e\-\d?$|2E\-\d?$)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll(':VOLT:OFFS ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                daemon.log('Voltage Offset set to' + match.group('val'))
                break

            regex = re.compile(r'\:?(VOLT|VOLTAGE)\:(UNIT)\?')
            if re.match(regex, STRING) or string == 'get_volt_unit':
                hw.messageAll(':VOLT:UNIT?\n', type='hw', keep=True, source=self.name)
                break
            regex = re.compile(r'(\:?(VOLT|VOLTAGE)\:(UNIT) (?P<val>(VPP|VRMS|DBM|DEF)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll(':VOLT:UNIT ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                daemon.log('Voltage Unit set to ' + match.group('val'))
                break
            
            regex = re.compile(r'\:?(FUNC|FUNCTION)\:(USER)\?')
            if re.match(regex, STRING) or string == 'get_func_user':
                hw.messageAll(':FUNC:USER?\n', type='hw', keep=True, source=self.name)
                break
            regex = re.compile(r'(\:?(FUNC|FUNCTION)\:(USER) (?P<val>(SINC|NEG_RAMP|EXP_RISE|EXP_FALL|CARDIAC)))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll(':FUNC:USER ' + match.group('val') + '\n', type='hw', keep=False, source=self.name)
                daemon.log('Function user set to ' + match.group('val'))
                break

            regex = re.compile(r'\:?(APPL|APPLY)\?')
            if re.match(regex, STRING) or string == 'get_apply':
                hw.messageAll(':APPL?\n', type='hw', keep=True, source=self.name)
                break
            
            
            regex = re.compile(r'(\:?(APPL|APPLY)\:(?P<val0>(USER|SIN|SQU|TRI|RAMP|NOIS|DC)) (?P<val1>(DEF|[1-9]\d*(\.\d+)?)|0(\.\d+)),(?P<val2>(DEF|[1-9]\d*(\.\d+)?)|0(\.\d+))((?P<val3>((,[1-9]\d*(\.\d+)?)|0(\.\d+))?)))')
            match = re.match(regex, STRING)
            if match:
                msgstr = 'APPL:' + match.group('val0') + ' '+ match.group('val1') + ','+ match.group('val2') + match.group('val3')
                print ('msgstr',msgstr)
                hw.messageAll(msgstr + '\n', type='hw', keep=False, source=self.name)
                daemon.log(msgstr)
                break

            if string[-1] == '?':
                print ('unrecog query cmd', string)
                hw.messageAll(string, type='hw', keep=True, source=self.name)
            else:
                hw.messageAll(string, type='hw', keep=False, source=self.name)
            break

    
    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object  # Object holding the state
        hw = obj['hw']  # HW factory
        hw.messageAll(string, type='hw', keep=keep, source=self.name)

class HP33120AProtocol(SimpleProtocol):
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
        SimpleProtocol.message(self, '?$SYST:ERR?')
        self.commands = [{'cmd': 'SYST:ERR?', 'source': 'itself', 'timeStamp': datetime.datetime.utcnow(), 'keep': 'keep'}]
        SimpleProtocol.message(self, '*RST')
        SimpleProtocol.message(self, 'OUTP:LOAD 50')
        self.object['out_load'] = 50
        SimpleProtocol.message(self, 'VOLT:OFFS 0')
        self.object['volt_offs'] = 0
        SimpleProtocol.message(self, 'VOLT:UNIT VPP')
        self.object['volt_unit'] = 'VPP'
        
        SimpleProtocol.message(self, '?$*OPC?')
        self.commands = [{'cmd': '*OPC?', 'source': 'itself', 'timeStamp': datetime.datetime.utcnow(), 'keep': 'keep'}]

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        self.object['out_load'] = np.nan
        self.object['volt_unit'] = 'none'
        SimpleProtocol.connectionLost(self, reason)
        
    @catch
    def processMessage(self, string):
        obj = self.object  # Object holding the state
        daemon = obj['daemon']

        if self._debug:
            print ('HP33120A >> %s' % string)
            print ('commands Q:', self.commands)
        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1

        # Process the device reply
        while len(self.commands):
            # We have some sent commands in the queue - let's check what was the oldest one
            if self.commands[0]['cmd'] == '*OPC?' and self.commands[0]['source'] == 'itself':
                # not used at the moment
                break
            if self.commands[0]['cmd'] == '*IDN?' and self.commands[0]['source'] == 'itself':
                # Example of how to broadcast some message to be printed on screen and stored to database
                daemon.log(string)
                break
            if not self.commands[0]['source'] == 'itself':
                # in case the origin of the query was not itself, forward the answer to the origin
                daemon.messageAll(string, self.commands[0]['source'])
            if self.commands[0]['cmd'] == ':OUTP:LOAD?':
                obj['out_load'] = float(string)
                break
            if self.commands[0]['cmd'] == ':VOLT:OFFS?':
                obj['volt_offs'] = float(string)
                break
            if self.commands[0]['cmd'] == ':VOLT:UNIT?':
                obj['volt_unit'] = string
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
            SimpleProtocol.message(self, '?$%s' % string)
        else:
            SimpleProtocol.message(self, string)
            
    @catch
    def update(self):
        if self._debug:      
            print ('update')
        
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
            self.message('SYST:ERR?', keep=True, source='itself')
            self.message('OUTPut:LOAD?', keep=True, source='itself')
            self.message('VOLT:OFFS?', keep=True, source='itself')
            self.message('VOLT:UNIT?', keep=True, source='itself')
            self.lastAutoRead = datetime.datetime.utcnow()

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=15)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7032)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='HP33120A')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {
        'hw_connected': 0,
        'addr': options.addr,
        'out_load':np.nan,
        'volt_offs':np.nan,
        'volt_unit':'none',
        }
    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(HP33120AProtocol, obj)

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
