#!/usr/bin/env python3
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
        hw = obj['hw']  # HW factory
        string=string.strip()
        STRING = string.upper()
        while True:
            if cmd.name == 'get_status':
                self.message('status hw_connected=%s V1=%g V2=%g V3=%g I1=%g I2=%g I3=%g O1=%i O2=%i O3=%i' % (self.object['hw_connected'],
                                                                                                               self.object['V1'], self.object['V2'], self.object['V3'],
                                                                                                               self.object['I1'], self.object['I2'], self.object['I3'],
                                                                                                               self.object['O1'], self.object['O2'], self.object['O3'], ))
                break
            
            regex = re.compile(r'(APP|APPLY):(VOLT|VOLTAGE)\?')
            if re.match(regex, STRING):
                hw.messageAll(':APP:VOLT?', type='hw', keep=True, source=self.name)
                break
            
            regex = re.compile(r'(APP|APPLY):(CURR|CURRENT)\?')
            if re.match(regex, STRING):
                hw.messageAll(':APP:CURR?', type='hw', keep=True, source=self.name)
                break

            regex = re.compile(r'(CHAN|CHANNEL):(OUTP|OUTPUT):(ALL)\?')
            if re.match(regex, STRING):
                hw.messageAll('CHAN:OUTP:ALL?', type='hw', keep=True, source=self.name)
                break
            
            regex = re.compile(r'(INST|INSTRUMENT):(NSEL|NSELECT)\?')
            if re.match(regex, STRING):
                hw.messageAll('INST:NSEL?', type='hw', keep=True, source=self.name)
                break
            
            regex = re.compile(r'(INST|INSTRUMENT):(NSEL|NSELECT) (?P<val>(1|2|3))')
            match = re.match(regex, STRING)
            if match:
                hw.messageAll('INST:NSEL ' + match.group('val'), type='hw', keep=False, source=self.name)
                break
            
            
            if STRING[-1] == '?':
                hw.messageAll(string, type='hw', keep=True, source=self.name)
            else:
                hw.messageAll(string, type='hw', keep=False, source=self.name)
            break
    
class Owon_odp6033Protocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    _tcp_keepidle = 1  # Faster detection of peer disconnection
    _tcp_user_timeout = 3000  # Faster detection of peer disconnection
    
    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","keep", and "sent"
        self.name = 'hw'
        self.type = 'hw'
        self.status_commands = [':APP:VOLT?',':APP:CURR?','CHAN:OUTP:ALL?']
        
    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self.name = 'hw'
        self.type = 'hw'
        SimpleProtocol.connectionMade(self)

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        self.object['V1'] = np.nan
        self.object['V2'] = np.nan
        self.object['V3'] = np.nan
        self.object['I1'] = np.nan
        self.object['I2'] = np.nan
        self.object['I3'] = np.nan
        self.object['O1'] = -1
        self.object['O2'] = -1
        self.object['O3'] = -1
        SimpleProtocol.connectionLost(self, reason)
        
    @catch
    def processMessage(self, string):
        # Process the device reply
        if self._debug:
            print ('hw cc > %s' % string)

        obj = self.object  # Object holding the state
        daemon = obj['daemon']
        
        while len(self.commands) and string != "\r":
            if self._debug:
                print ('last command which expects reply was:', self.commands[0]['cmd'])
                print ('received reply:', string)
            if not self.commands[0]['source'] == 'itself':
                # in case the origin of the query was not itself, forward the answer to the origin
                daemon.messageAll(string, self.commands[0]['source'])
                
            if self.commands[0]['cmd'] == ':APP:VOLT?':
                VV = string.split(',')
                self.object['V1'] = float(VV[0])
                self.object['V2'] = float(VV[1])
                self.object['V3'] = float(VV[2])
                break
            if self.commands[0]['cmd'] == ':APP:CURR?':
                II = string.split(',')
                self.object['I1'] = float(II[0])
                self.object['I2'] = float(II[1])
                self.object['I3'] = float(II[2])
                break
            if self.commands[0]['cmd'] == 'CHAN:OUTP:ALL?':
                OO = string.split(',')
                self.object['O1'] = int(OO[0])
                self.object['O2'] = int(OO[1])
                self.object['O3'] = int(OO[2])
                break
            break
        else:
            return
        self.commands.pop(0)


    @catch
    def update(self):
        print ('--------self.commands--------------')
        for cc in self.commands:
            print (cc)
        print ('----------------------')
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
                self.commands.append({'cmd': k, 'source': 'itself', 'keep': True, 'sent':False})
                

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, expect reply
        """
        n = 0
        for cc in self.commands:
            if not cc['sent']:
                break
            n += 1
        self.commands.insert(n, {'cmd': string, 'source': source, 'keep': keep, 'sent':False})
                
        
if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect', action='store', dest='hw_host', default='192.168.1.198')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect', action='store', dest='hw_port', type='int', default=3000)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7033)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='Owon_odp6033')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0,'V1':np.nan,'V2':np.nan,'V3':np.nan,'I1':np.nan,'I2':np.nan,'I3':np.nan,'O1':-1,'O2':-1,'O3':-1}

    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(Owon_odp6033Protocol, obj)

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    if options.debug:
        daemon._protocol._debug = True
        hw._protocol._debug = True

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
