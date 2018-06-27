#!/usr/bin/env python

import os, sys, datetime, re
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
        STRING=string.upper()
        while True:
            if cmd.name == 'get_status':
                if self._simulator:
                    self.message('status hw_connected=1 status=0 temperatureA=%g  temperatureB=%g temperatureC=%g temperatureD=%g simulator=1'
                                % (np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0),np.random.uniform(1.0, 10.0)))
                else:
                    self.message('status hw_connected=%s status=%s temperatureA=%g temperatureB=%g temperatureC=%g temperatureD=%g \
                                htr_status1=%s range1=%s ctrl_type1=%s pwr_set1=%g pwr_actual1=%g load1=%g \
                                htr_status2=%s range2=%s ctrl_type2=%s pwr_set2=%g pwr_actual2=%g load2=%g'
                                % (self.object['hw_connected'], self.object['status'],
                                    self.object['temperatureA'], self.object['temperatureB'], self.object['temperatureC'], self.object['temperatureD'],
                                    self.object['htr_status1'], self.object['range1'], self.object['ctrl_type1'], self.object['pwr_set1'], self.object['pwr_actual1'],self.object['load1'],
                                    self.object['htr_status2'], self.object['range2'], self.object['ctrl_type2'], self.object['pwr_set2'], self.object['pwr_actual2'],self.object['load1']))
                break
            regex=re.compile(r'(CONT|CONTR|CONTRO|CONTROL)\?')
            if re.match(regex, STRING):
                hw.messageAll(string, type='hw', keep=True, source=self.name)
                break            
            if STRING == 'STOP':
                hw.messageAll(string, type='hw', keep=False, source=self.name)
                break
            regex=re.compile(r'(CONT|CONTR|CONTRO|CONTROL)')
            if re.match(regex, STRING):
                hw.messageAll(string, type='hw', keep=False, source=self.name)
                break            
            if STRING == '*OPC?':
                hw.messageAll(string, type='hw', keep=True, source=self.name)
                break
            while STRING[:4] == 'LOOP':
                regex = re.compile(r'LOOP [1-4]:(SOUR|SOURC|SOURCE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=True, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-4]:(SOUR|SOURC|SOURCE) [A-D]')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-4]:(RANG|RANGE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=True, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP 1:(RANG|RANGE) (HI|MID|LOW)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP 2:(RANG|RANGE) (HI|LOW)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [3-4]:(RANG|RANGE) (5V|10V)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-4]:([PID]GA|[PID]GAI|[PID]GAIN)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=True, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-4]:([PID]GA|[PID]GAI|[PID]GAIN) (\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1])<0 or float(STRING.split()[-1])>1000:
                        daemon.log('WARNING value out of range: '+string+' from connection '+self.name)
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-4]:(SET|SETP|SETPT)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=True, source=self.name)
                    STRING=""
                    continue

                regex=re.compile(r'LOOP [1-4]:(SET|SETP|SETPT) -?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    #if float(STRING.split()[-1])<0 or float(STRING.split()[-1])>1000:
                        #daemon.log('WARNING value out of range: '+string+' from connection '+self.name)
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue

                regex=re.compile(r'LOOP [1-4]:(TYP|TYPE)\?$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=True, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [1-2]:(TYP|TYPE) (OFF|PID|MAN|TABLE|RAMPP)$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                regex=re.compile(r'LOOP [3-4]:(TYP|TYPE) (OFF|PID|MAN|TABLE|RAMPP|SCALE)$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw', keep=False, source=self.name)
                    STRING=""
                    continue
                daemon.log('WARNING unidentified command: '+string+' from connection '+self.name)
                STRING=""
            else:
                break
            if obj['hw_connected']:
                # Pass all other commands directly to hardware
                hw.messageAll(string, name='hw', type='hw')
            break

class CryoConProtocol(SimpleProtocol):
    _debug = False # Display all traffic for debug purposes

    _tcp_keepidle = 1 # Faster detection of peer disconnection
    _tcp_user_timeout = 3000 # Faster detection of peer disconnection
    
    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = [] # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source","timeStamp"
        self.name = 'hw'
        self.type = 'hw'
        
    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self.name = 'hw'
        self.type = 'hw'
        SimpleProtocol.connectionMade(self)
        # make sure the units are Celsius
        self.message('input a,b,c,d:units c;:loop 1:load 50')

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        SimpleProtocol.connectionLost(self, reason)
        self.object['status'] = '----'

    @catch
    def processMessage(self, string):
        # Process the device reply
        if self._debug:
            print "hw cc > %s" % string
            
        obj = self.object # Object holding the state
        daemon = obj['daemon']

        # Update the last reply timestamp
        obj['hw_last_reply_time'] = datetime.datetime.utcnow()
        obj['hw_connected'] = 1
    
        pwrfactor = {'HI':1.,'MID':0.1,'LOW':0.01}
        
        if len(self.commands) and string!="\r":
            if self._debug:
                print "last command which expects reply was:", self.commands[0]['cmd']
                print "received reply:", string
            if self.commands[0]['cmd'] == "input? a,b,c,d;:loop 1:err?;rang?;type?;load?;outp?;htrr?;:loop 2:err?;rang?;type?;load?;outp?;htrr?;":                
                if len(string):
                    # reply to parse looks like this:
                    # 20.806670;20.800480;20.896670;20.853670;--Htr OK--;HI ;MAN  ;50;0.000000;   0%;0.000A; 0.00V;--Htr OK--;LOW;MAN  ;50;0.000000;   0%;0.000A; 0.00V
                    # values for channel a;b;c;d (....... means dot connected)
                    sstring = string.split(';')
                    status = ''
                    channel = ['temperatureA', 'temperatureB', 'temperatureC', 'temperatureD']

                    # temperatures
                    for s in range(4):
                        try:
                            sstring[s] = float(sstring[s])
                            status = status + '1'
                            self.object[channel[s]] = sstring[s]
                        except ValueError:
                            status = status + '0'
                            self.object[channel[s]] = np.nan
                    self.object['status'] = status
                    # heater loop 1
                    self.object['htr_status1'] = sstring[4].replace(' ','-')
                    self.object['range1'] = sstring[5].replace(' ','')
                    self.object['ctrl_type1'] = sstring[6].replace(' ','')
                    self.object['load1'] = float(sstring[7])
                    self.object['pwr_set1'] = float(sstring[8])*pwrfactor[self.object['range1']]*self.object['load1']/100.
                    self.object['pwr_actual1'] = float(sstring[9].replace('%',''))*pwrfactor[self.object['range1']]*self.object['load1']/100.
                    self.object['htr_status2'] = sstring[10].replace(' ','-')
                    self.object['range2'] = sstring[11].replace(' ','')
                    self.object['ctrl_type1'] = sstring[12].replace(' ','')
                    self.object['load2'] = float(sstring[13])
                    self.object['pwr_set2'] = float(sstring[14])*pwrfactor[self.object['range2']]*self.object['load2']*0.5/100.
                    self.object['pwr_actual2'] = float(sstring[15].replace('%',''))*pwrfactor[self.object['range2']]*self.object['load2']*0.5/100.
                self.commands.pop(0)
            else:
                # not recognized command, just pass the output
                daemon.messageAll(string,self.commands[0]['source'])
                self.commands.pop(0)
            
    @catch
    def update(self):
        # Request the hardware state from the device
        if len(self.commands):
            SimpleProtocol.message(self, self.commands[0]['cmd'])
            if not self.commands[0]['keep']:
                self.commands.pop(0) 
        else:
            self.commands.append({'cmd':'input? a,b,c,d;:loop 1:err?;rang?;type?;load?;outp?;htrr?;:loop 2:err?;rang?;type?;load?;outp?;htrr?;', 'source':'itself','timeStamp':datetime.datetime.utcnow(),'keep':True})
            SimpleProtocol.message(self, self.commands[0]['cmd'])

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, expect reply
        """
        print "msg", string, keep, source
        self.commands.append({'cmd':string,'source':source,'timeStamp':datetime.datetime.utcnow(),'keep':keep})

        
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
    obj = {'hw_connected':0, 
           'status':'----', 'temperatureA':0, 'temperatureB':0, 'temperatureC':0, 'temperatureD':0,
           'htr_status1':'-','range1':'-','ctrl_type1':'-','pwr_set1':0,'pwr_actual1':0,'load1':0,'current1':0,
           'htr_status2':'-','range2':'-','ctrl_type2':'-','pwr_set2':0,'pwr_actual2':0,'load2':0,'current2':0}

    # Factories for daemon and hardware connections
    # We need two different factories as the protocols are different
    daemon = SimpleFactory(DaemonProtocol, obj)
    hw = SimpleFactory(CryoConProtocol, obj)

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
