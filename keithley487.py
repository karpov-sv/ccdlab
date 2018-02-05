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

        print 'KEITHLEY487 >> %s' % string

        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
        
        # Process the device reply
        if len(self.commands):
            if self.commands[0]['cmd'] == '?$XL0XK0B1' and self.commands[0]['source']=='itself':
                obj['value'] = float(string[4:-1])
                obj['units'] = 'mA'
                obj['timestamp'] = (datetime.datetime(2018, 1, 1)-datetime.datetime.utcnow()).total_seconds()
                self.commands[0]['keep']=False


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

        if self._debug: print len(self.commands),' commands in the Q:\n',self.commands
        if len(self.commands):
            SimpleProtocol.message(self, '%s' % (self.commands[0]['cmd'])) #send the actual command
            if not self.commands[0]['keep']:
                self.commands.pop(0)
                
        elif (datetime.datetime.utcnow()-self.lastAutoRead).total_seconds()>2.:
            # Request the hardware state from the device
            self.message('?$XL0XK0B1', keep=True, source='itself')
            self.lastAutoRead=datetime.datetime.utcnow()
            
    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        cmd = Command(string)
        self.commands.append({'cmd':cmd.name,'source':source,'timeStamp':datetime.datetime.utcnow(),'keep':keep})

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=15)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7022)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley487')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'addr':options.addr, 'value':0, 'units':'', 'timestamp':0, 'range':0}

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
