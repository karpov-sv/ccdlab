#!/usr/bin/env python

import os
import sys
import re
import numpy as np

from daemon import SimpleFactory, SimpleProtocol
from command import Command
from daemon import catch


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _simulator = False

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        obj = self.object  # Object holding the state
        hw = obj['hw']  # HW factory
        STRING = string.upper()
        while True:
            if cmd.name == 'get_status':
                self.message('status hw_connected=%s status=%s temperatureA=%g temperatureB=%g temperatureC=%g temperatureD=%g control=%s\
                            htr_status1=%s range1=%s ctrl_type1=%s pwr_set1=%g pwr_actual1=%g load1=%g source1=%s set_point1=%g ramp1=%s rate1=%g \
                            htr_status2=%s range2=%s ctrl_type2=%s pwr_set2=%g pwr_actual2=%g load2=%g source2=%s set_point2=%g ramp2=%s rate2=%g \
                            htr_status3=%s range3=%s ctrl_type3=%s pwr_set3=%s pwr_actual3=%s load3=%s source3=%s set_point3=%g ramp3=%s rate3=%g \
                            htr_status4=%s range4=%s ctrl_type4=%s pwr_set4=%s pwr_actual4=%s load4=%s source4=%s set_point4=%g ramp4=%s rate4=%g'
                             % (self.object['hw_connected'], self.object['status'],
                                self.object['temperatureA'], self.object['temperatureB'], self.object['temperatureC'], self.object['temperatureD'], self.object['control'],
                                self.object['htr_status1'], self.object['range1'], self.object['ctrl_type1'], self.object[
                                    'pwr_set1'], self.object['pwr_actual1'], self.object['load1'],
                                self.object['source1'], self.object['set_point1'], self.object['ramp1'], self.object['rate1'],
                                self.object['htr_status2'], self.object['range2'], self.object['ctrl_type2'], self.object[
                                    'pwr_set2'], self.object['pwr_actual2'], self.object['load2'],
                                self.object['source2'], self.object['set_point2'], self.object['ramp2'], self.object['rate2'],
                                self.object['htr_status3'], self.object['range3'], self.object['ctrl_type3'], self.object[
                                    'pwr_set3'], self.object['pwr_actual3'], self.object['load3'],
                                self.object['source3'], self.object['set_point3'], self.object['ramp3'], self.object['rate3'],
                                self.object['htr_status4'], self.object['range4'], self.object['ctrl_type4'], self.object[
                                    'pwr_set4'], self.object['pwr_actual4'], self.object['load4'],
                                self.object['source4'], self.object['set_point4'], self.object['ramp4'], self.object['rate4'],))
                break
            regex = re.compile(r'(CONT|CONTR|CONTRO|CONTROL)\?')
            if re.match(regex, STRING):
                hw.messageAll(string, type='hw', keep=True, source=self.name)
                break
            if STRING == 'STOP':
                hw.messageAll(string, type='hw', keep=False, source=self.name)
                break
            regex = re.compile(r'(CONT|CONTR|CONTRO|CONTROL)')
            if re.match(regex, STRING):
                hw.messageAll(string, type='hw', keep=False, source=self.name)
                break
            if STRING == '*OPC?':
                hw.messageAll(string, type='hw', keep=True, source=self.name)
                break
            while STRING[:4] == 'LOOP':
                regex = re.compile(r'LOOP [1-4]:(SOUR|SOURC|SOURCE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(SOUR|SOURC|SOURCE) [A-D]')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(RANG|RANGE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP 1:(RANG|RANGE) (HI|MID|LOW)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP 2:(RANG|RANGE) (HI|LOW)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [3-4]:(RANG|RANGE) (5V|10V)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:([PID]GA|[PID]GAI|[PID]GAIN)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:([PID]GA|[PID]GAI|[PID]GAIN) (\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1]) < 0 or float(STRING.split()[-1]) > 1000:
                        daemon.log('WARNING value out of range: ' +
                                   string+' from connection '+self.name)
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(SETP|SETPT)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(SETP|SETPT) -?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(TYP|TYPE)\?$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-2]:(TYP|TYPE) (OFF|PID|MAN|TABLE|RAMPP)$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [3-4]:(TYP|TYPE) (OFF|PID|MAN|TABLE|RAMPP|SCALE)$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(MAXP|MAXPW|MAXPWR)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(MAXP|MAXPW|MAXPWR) (\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1]) < 0 or float(STRING.split()[-1]) > 100:
                        daemon.log('WARNING value out of range: ' +
                                   string+' from connection '+self.name)
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(PMAN|PMANU|PMANUA|PMANUAL)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(PMAN|PMANU|PMANUA|PMANUAL) ?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1]) < 0 or float(STRING.split()[-1]) > 100:
                        daemon.log('WARNING value out of range: ' +
                                   string+' from connection '+self.name)
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:RAMP\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(RAT|RATE) ?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1]) < 0 or float(STRING.split()[-1]) > 100:
                        daemon.log('WARNING value out of range: ' +
                                   string+' from connection '+self.name)
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(r'LOOP [1-4]:(RAT|RATE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(STAR|START|EXIT|SAVE)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(MOD|MODE)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(MOD|MODE) (P--|PI-|PID)')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(DELT|DELTA|DELTAP)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(DELT|DELTA|DELTAP) ?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    if float(STRING.split()[-1]) < 0 or float(STRING.split()[-1]) > 100:
                        daemon.log('WARNING value out of range: ' +
                                   string+' from connection '+self.name)
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(TIM|TIME|TIMEO|TIMEOU|TIMEOUT)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(TIM|TIME|TIMEO|TIMEOU|TIMEOUT) ?(\d+?)?\.?(\d+?$)?$')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=False, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):([PID]GA|[PID]GAI|[PID]GAIN)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue
                regex = re.compile(
                    r'LOOP [1-4]:(AUT|AUTO|AUTOT|AUTOTU|AUTOTUN|AUTOTUNE):(STAT|STATU|STATUS)\?')
                if re.match(regex, STRING):
                    hw.messageAll(string, type='hw',
                                  keep=True, source=self.name)
                    STRING = ""
                    continue

                daemon.log('WARNING unidentified command: ' +
                           string+' from connection '+self.name)
                STRING = ""
            else:
                break
            if obj['hw_connected']:
                # Pass all other commands directly to hardware
                hw.messageAll(string, name='hw', type='hw')
            break


class CryoConProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    _tcp_keepidle = 1  # Faster detection of peer disconnection
    _tcp_user_timeout = 3000  # Faster detection of peer disconnection

    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source"
        self.name = 'hw'
        self.type = 'hw'
        self.status_commands = ["input? a,b,c,d;:cont?",
                                ":loop 1:err?;rang?;type?;load?;outp?;htrr?;sour?;setp?;ramp?;rate?;",
                                ":loop 2:err?;rang?;type?;load?;outp?;htrr?;sour?;setp?;ramp?;rate?;",
                                ":loop 3:err?;rang?;type?;load?;outp?;htrr?;sour?;setp?;ramp?;rate?;",
                                ":loop 4:err?;rang?;type?;load?;outp?;htrr?;sour?;setp?;ramp?;rate?;"]

    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self.name = 'hw'
        self.type = 'hw'
        SimpleProtocol.connectionMade(self)
        # make sure the units are Celsius
        self.message('input a,b,c,d:units c;:loop 1:load 50;:loop 2:load 0;')

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

        obj = self.object  # Object holding the state
        daemon = obj['daemon']

        obj['hw_connected'] = 1

        pwrfactor = {'HI': 1., 'MID': 0.1, 'LOW': 0.01}

        if len(self.commands) and string != "\r":
            if self._debug:
                print "last command which expects reply was:", self.commands[0]['cmd']
                print "received reply:", string
            if self.commands[0]['cmd'] in self.status_commands:
                if len(string):
                    # reply to parse looks like this:
                    # 20.806670;20.800480;20.896670;20.853670;--Htr OK--;HI ;MAN  ;50;0.000000;   0%;--Htr OK--;LOW;MAN  ;50;0.000000;   0%
                    # values for channel a;b;c;d (....... means not connected)
                    sstring = string.split(';')
                    if self.commands[0]['cmd'] == self.status_commands[0]:
                        status = ''
                        channel = ['temperatureA', 'temperatureB',
                                   'temperatureC', 'temperatureD']
                        # temperatures
                        for s in range(4):
                            try:
                                sstring[s] = float(sstring[s])
                                status = status + '1'
                                self.object[channel[s]] = sstring[s]
                            except ValueError:
                                status = status + '0'
                                self.object[channel[s]] = np.nan
                        self.object['control'] = sstring[4]
                        self.object['status'] = status
                    else:
                        nn = self.status_commands.index(
                            self.commands[0]['cmd'])
                        self.object['htr_status' +
                                    str(nn)] = sstring[0].replace(' ', '-')
                        self.object['range' +
                                    str(nn)] = sstring[1].replace(' ', '')
                        self.object['ctrl_type' +
                                    str(nn)] = sstring[2].replace(' ', '')
                        if nn == 1:
                            self.object['load'+str(nn)] = float(sstring[3])
                            self.object['pwr_set'+str(nn)] = float(
                                sstring[4])*pwrfactor[self.object['range'+str(nn)]]*self.object['load'+str(nn)]/100.
                            self.object['pwr_actual'+str(nn)] = float(sstring[5].replace(
                                '%', ''))*pwrfactor[self.object['range'+str(nn)]]*self.object['load'+str(nn)]/100.
                        elif nn == 2:
                            self.object['load'+str(nn)] = 0.
                            self.object['pwr_set'+str(nn)] = float(
                                sstring[4])*pwrfactor[self.object['range'+str(nn)]]*self.object['load'+str(nn)]/100.
                            self.object['pwr_actual'+str(nn)] = float(sstring[5].replace(
                                '%', ''))*pwrfactor[self.object['range'+str(nn)]]*self.object['load'+str(nn)]/100.
                        else:
                            self.object['load'+str(nn)] = sstring[3]
                            self.object['pwr_set'+str(nn)] = sstring[4]+'%'
                            self.object['pwr_actual' +
                                        str(nn)] = sstring[5].replace(' ', '')
                        self.object['source'+str(nn)] = sstring[6]
                        self.object['set_point' +
                                    str(nn)] = float(sstring[7][:-2])
                        self.object['ramp'+str(nn)] = sstring[8]
                        self.object['rate'+str(nn)] = float(sstring[9])

            else:
                # not recognized command, just pass the output
                daemon.messageAll(string, self.commands[0]['source'])
            self.commands.pop(0)

    @catch
    def update(self):
        # Request the hardware state from the device
        if len(self.commands):
            SimpleProtocol.message(self, self.commands[0]['cmd'])
            if not self.commands[0]['keep']:
                self.commands.pop(0)
        else:
            for k in self.status_commands:
                self.commands.append(
                    {'cmd': k, 'source': 'itself', 'keep': True})
                SimpleProtocol.message(self, self.commands[0]['cmd'])

    @catch
    def message(self, string, keep=False, source='itself'):
        """
        Send the message to the controller. If keep=True, expect reply
        """
        self.commands.append({'cmd': string, 'source': source, 'keep': keep})


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-H', '--hw-host', help='Hardware host to connect',
                      action='store', dest='hw_host', default='192.168.1.5')
    parser.add_option('-P', '--hw-port', help='Hardware port to connect',
                      action='store', dest='hw_port', type='int', default=5000)
    parser.add_option('-p', '--port', help='Daemon port',
                      action='store', dest='port', type='int', default=7024)
    parser.add_option('-n', '--name', help='Daemon name',
                      action='store', dest='name', default='cryo-con')
    parser.add_option("-D", '--debug', help='Debug mode',
                      action="store_true", dest="debug")
    parser.add_option("-S", '--simulator', help='Simulator mode',
                      action="store_true", dest="simulator")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0,
           'status': '----', 'temperatureA': 0, 'temperatureB': 0, 'temperatureC': 0, 'temperatureD': 0, 'control':'-',
           'htr_status1': '-', 'range1': '-', 'ctrl_type1': '-', 'pwr_set1': 0, 'pwr_actual1': 0, 'load1': 0, 'source1': '-', 'set_point1': np.nan, 'ramp1': '-', 'rate1': np.nan,
           'htr_status2': '-', 'range2': '-', 'ctrl_type2': '-', 'pwr_set2': 0, 'pwr_actual2': 0, 'load2': 0, 'source2': '-', 'set_point2': np.nan, 'ramp2': '-', 'rate2': np.nan,
           'htr_status3': '-', 'range3': '-', 'ctrl_type3': '-', 'pwr_set3': 0, 'pwr_actual3': 0, 'load3': 0, 'source3': '-', 'set_point3': np.nan, 'ramp3': '-', 'rate3': np.nan,
           'htr_status4': '-', 'range4': '-', 'ctrl_type4': '-', 'pwr_set4': 0, 'pwr_actual4': 0, 'load4': 0, 'source4': '-', 'set_point4': np.nan, 'ramp4': '-', 'rate4': np.nan}

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
