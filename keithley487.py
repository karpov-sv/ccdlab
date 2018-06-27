#!/usr/bin/env python

from daemon import SimpleFactory, SimpleProtocol, catch
import datetime
from command import Command

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
            daemon.log('Resetting Keithley 487')
            self.sendCommand('L0X')
            self.sendCommand('K0X') #enable EOI and holdoff
        elif cmd.name in ['idn']:
            self.sendCommand('U2X', keep=True)
        elif cmd.name in ['get_voltage']:
            self.sendCommand('U8X', keep=True)
        elif string and cmd.name.split(',')[0] == ['set_voltage']:
            # the format is set_voltage,val1,val2,val3
            # val1 -> voltage in V; val2 -> range, 0 is 50V, 1 is 500V; val3 -> curr. limit, 0 is 20 uA, 1 is 2 mA          
            volt_pars=cmd.name.split(',')
            if len(volt_pars)!=4:
                raise ValueError('KEITHLEY487: unable to parse voltage command')
                return
            if volt_pars[2]=='0': vlim=50
            elif volt_pars[2]=='1': vlim=500
            else: 
                raise ValueError('KEITHLEY487: unable to parse voltage range')
                return
            if abs(float(volt_pars[1]))>vlim:
                raise ValueError('KEITHLEY487: requested voltage out of range')
                return
            if volt_pars[3] not in ['0','1']:
                raise ValueError('KEITHLEY487: unable to parse current limit')
                return
            self.sendCommand('V'+volt_pars[1]+','+volt_pars[2]+','+volt_pars[3], keep=False)
       
    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory
        hw.messageAll(string, type='hw', keep=keep, source=self.name)

class KeithleyProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes
    _refresh = 1

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = [] # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.name = 'hw'
        self.type = 'hw'
        self.lastAutoRead=datetime.datetime.utcnow()
        
    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)
        self.object['hw_connected'] = 0 # We will set this flag when we receive any reply from the device
        SimpleProtocol.message(self, 'set_addr %d' % self.object['addr'])
        SimpleProtocol.message(self, '?$K0XU0X') #enable EOI and holdoff
       
    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        daemon = obj['daemon']

        if self._debug:
            print 'KEITHLEY487 >> %s' % string

        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
        
        # Process the device reply
        if len(self.commands):
            if self.commands[0]['cmd'] == 'XL0XK0B1' and self.commands[0]['source']=='itself':
                obj['value'] = float(string[4:-1])
                obj['units'] = 'mA'
                obj['timestamp'] = (datetime.datetime(2018, 1, 1)-datetime.datetime.utcnow()).total_seconds()
            if self.commands[0]['cmd']=='U8X':
                daemon.messageAll(string,self.commands[0]['source'])
            self.commands.pop(0)

    @catch
    def update(self):
        if (datetime.datetime.utcnow() - obj['hw_last_reply_time']).total_seconds() > 10:
            # We did not get any reply from device during last 10 seconds, probably it is disconnected?
            self.object['hw_connected'] = 0
             # TODO: should we clear the command queue here?
             
        #first check if device is hw_connected
        if self.object['hw_connected'] == 0:
            #if not connected do not send any commands
            return
                
        elif (datetime.datetime.utcnow()-self.lastAutoRead).total_seconds()>2. and len(self.commands)==0:
            # Request the hardware state from the device
            self.message('XL0XK0B1', keep=True, source='itself')
            self.lastAutoRead=datetime.datetime.utcnow()


    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        cmd = Command(string)
        if keep:
            self.commands.append({'cmd':cmd.name,'source':source,'timeStamp':datetime.datetime.utcnow(),'keep':keep})
            SimpleProtocol.message(self, '?$%s' % cmd.name)
        else:
            SimpleProtocol.message(self, cmd.name)

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=15)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7022)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley487')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'addr':options.addr, 'value':0, 'units':'', 'timestamp':0, 'range':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(KeithleyProtocol, obj)

    if options.debug:
        daemon._protocol._debug=True
        hw._protocol._debug=True

    daemon.name = options.name

    obj['daemon'] = daemon
    obj['hw'] = hw

    obj['hw_last_reply_time'] = datetime.datetime(1970, 1, 1) # Arbitrarily old time moment

    # Incoming connections
    daemon.listen(options.port)
    # Outgoing connection
    hw.connect(options.hw_host, options.hw_port)

    daemon._reactor.run()
