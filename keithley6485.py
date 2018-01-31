#!/usr/bin/env python

import os, sys, datetime

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch

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
            daemon.log('Resetting Keithley 6485')
            self.sendCommand('*RST')
        elif cmd.name in ['idn']:
            self.sendCommand('*idn?', keep=True)
        elif string and string[0] == '*':
            # For debug purposes only
            self.sendCommand(string)
        elif cmd.name in ['get_curr']:
            self.sendCommand('CURR:RANGE?', keep=True)

    @catch
    def sendCommand(self, string, keep=False):
        obj = self.object # Object holding the state
        hw = obj['hw'] # HW factory
        hw.messageAll(string, type='hw', keep=keep, source=self.name)

class KeithleyProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes
    _refresh = 0.1

    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = [] # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.name = 'hw'
        self.type = 'hw'
        self.waitForMessage=False
        self.lastAutoRead=datetime.datetime.utcnow()

    @catch
    def connectionMade(self):
        SimpleProtocol.connectionMade(self)
        self.object['hw_connected'] = 0 # We will set this flag when we receive any reply from the device
        SimpleProtocol.message(self, 'set_addr %d' % self.object['addr'])
        SimpleProtocol.message(self, '*opc?')
       
    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)

    @catch
    def processMessage(self, string):
        SimpleProtocol.processMessage(self, string)
        obj = self.object # Object holding the state
        daemon = obj['daemon']

        print 'KEITHLEY6485 >> %s' % string

        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
                
        # Process the device reply
        if len(self.commands):
            # We have some sent commands in the queue - let's check what was the oldest one
            if self.commands[0]['cmd'] == '*opc?' and self.commands[0]['source']=='itself':
                if string=='1':
                    # devide is ready
                    self.commands[0]['keep']=False
                    return
                else:
                    return
            if self.commands[0]['cmd'] == '*idn?' and self.commands[0]['source']=='itself':
                # Example of how to broadcast some message to be printed on screen and stored to database
                daemon.log(string)
            elif self.commands[0]['cmd'] == 'read?' and self.commands[0]['source']=='itself':
                s = string.split(',')
                obj['value'] = float(s[0][:-1])
                obj['units'] = s[0][-1]
                obj['timestamp'] = float(s[1])
            elif self.commands[0]['cmd'] == 'read?' and not self.commands[0]['source']=='itself':
                daemon.messageAll(string,self.commands[0]['source'])
            elif self.commands[0]['cmd'] == 'CURR:RANGE?':
                daemon.messageAll(string,self.commands[0]['source'])
            else:
                daemon.log('WARNING responce to unidentified command: '+self.commands[0]['cmd']+' from connection '+self.commands[0]['source'])
            self.commands[0]['keep']=False

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, append the command name to
        internal queue so that we may properly recognize the reply
        """
        #SimpleProtocol.message(self, '%s' % (string))
        cmd = Command(string)
        self.commands.append({'cmd':cmd.name,'source':source,'timeStamp':datetime.datetime.utcnow(),'keep':keep})

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

        if self._debug: print len(self.commands),' commands in the Q:\n',self.commands, "waitForMessage= ",self.waitForMessage
        
        if len(self.commands):
            if self.commands[0]['cmd']=='*opc?' and self.commands[0]['source']=='itself' and not self.waitForMessage:
                if self._debug: print 'last command was auto *opc? call, sorting out the result'
                if self.commands[0]['keep']:
                    #check opc status, because last opc status indicated divice is busy send it again, no need to change the Q
                    if self._debug: print '*opc? waiting'
                    SimpleProtocol.message(self, '%s' % ('*opc?'))
                elif not self.commands[0]['keep']:
                    # opc status is 1, the device is ready, send next command
                    self.commands.pop(0) #remove the opc from queue
                    if self._debug: print '*opc? indicates device ready, sending command ',self.commands[0]['cmd']
                    SimpleProtocol.message(self, '%s' % (self.commands[0]['cmd'])) #send the actual command
                    if not self.commands[0]['keep']:
                        self.commands.pop(0)
                    else:
                        self.waitForMessage=True   
            else:
                if not self.waitForMessage:
                    #before sending a new command, send opc query
                    if self._debug: print '*opc? before next command'
                    self.commands.insert(0,{'cmd':'*opc?','source':'itself','timeStamp':datetime.datetime.utcnow(),'keep':True})
                    SimpleProtocol.message(self, '%s' % ('*opc?'))
                elif not self.commands[0]['keep']:
                    #the last command is not periodic *opc? check, it was actual command expecting answer and the answer arrived
                    if self._debug: print 'it was actual command expecting answer and the answer arrived'
                    self.commands.pop(0) #remove the actual command from the Q
                    self.waitForMessage=False
        elif (datetime.datetime.utcnow()-self.lastAutoRead).total_seconds()>2.:
            # Request the hardware state from the device
            self.message('*rst', keep=False, source='itself')
            self.message('read?', keep=True, source='itself')
            self.lastAutoRead=datetime.datetime.utcnow()

if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='GPIB multiplexor host to connect', action='store', dest='hw_host', default='localhost')
    parser.add_option('-P', '--hw-port', help='GPIB multiplexor port to connect', action='store', dest='hw_port', type='int', default=7020)
    parser.add_option('-a', '--addr', help='GPIB bus address of the device', action='store', dest='addr', default=14)
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7021)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='keithley6485')

    (options,args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected':0, 'addr':options.addr, 'value':0, 'units':'', 'timestamp':0, range:0}

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
