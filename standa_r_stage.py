#!/usr/bin/env python3
from optparse import OptionParser
import re
from libscrc import modbus

from twisted.internet.serialport import SerialPort
from twisted.internet.task import LoopingCall

from daemon import SimpleFactory, SimpleProtocol, catch

class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    @catch
    def mbytes(self,cmd, pars, reserved_bytes=0):
        bss = cmd.encode('ascii')+b''.join([int(p[1]).to_bytes( p[0], 'little', signed=True ) for p in pars])
        if reserved_bytes:
            bss += reserved_bytes*b'\xcc'
        bss +=modbus(bss[4:]).to_bytes( 2, 'little' )
        return bss
        
    @catch
    def parsePars(self,cmd,pars_o,ss,rbs):
        if len(pars_o) != len(ss):
            return None
        is_labeled=False
        if all(':' in sss for sss in ss):
            is_labeled=True
        elif not all(':' not in sss for sss in ss):
            return None
        pars=[]
        for n in range(len(pars_o)):
            pars+=[[pars_o[n][0],ss[n]]]
            if is_labeled:
                pars[-1][1]=[i for i in ss if pars_o[n][1] in i][0].split(':')[1]
        mstr = self.mbytes(cmd,pars,rbs)
        if mstr:
            obj['hw'].protocol.Imessage(mstr, nb=4, source=self.name)
        return True
    
    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        Imessage=obj['hw'].protocol.Imessage
        Sstring = (string.strip('\n')).split(';')
        for sstring in Sstring:
            sstring = sstring.lower()
            while True:
                # managment commands
                if sstring == 'get_status':
                    self.message('status hw_connected=%s position=%s uposition=%s encposition=%s' % (self.object['hw_connected'], self.object['position'], self.object['uposition'], self.object['encposition']))
                    break
                if sstring == 'timeout':
                    self.factory.log('command timeout - removing command from list and flushing buffer')
                    hw._buffer = b''  # empty buffer after timeout
                    hw.commands.pop(0)
                    break
                if string == 'sync':
                    # sync after failed comand
                    Imessage(bytearray(64), nb=64, source=self.name)
                    break

                # general query command (xxxx comands from manual)(for specifically implemented comands see below)
                ss = sstring.split('<')
                if len(ss) == 2 and len(ss[1])==4:
                    Imessage(ss[1], nb=int(ss[0]), source=self.name)
                    break
                elif len(ss) > 2 or (len(ss)==2 and len(ss[1])!=4):
                    daemon.log('unable to parse command, format sould be "nb<xxxx" insted of: '+sstring,'error')
                    break
                

                # human readable version for the most useful comands
                if sstring == 'get_device_info':
                    # get some device info (model, etc.)
                    Imessage('gsti', nb=70, source=self.name)
                    break
                if sstring == 'get_move_pars':
                    # get movement parameters
                    Imessage('gmov', nb=30, source=self.name)
                    break
                if sstring == 'get_position':
                    # get movement parameters
                    Imessage('gpos', nb=26, source=self.name)
                    break
                if sstring.startswith('set_move_pars'):
                    # set movement parameters, examples:
                    # set_move_pars speed:2000 uspeed:0 accel:2000 decel:5000 anti_play_speed:2000 uanti_play_speed:0                    
                    # set_move_pars 2000 0 2000 5000 2000 0  
                    pars_o=[[4 ,'speed'],[1 ,'uspeed'],[2 ,'accel'],[2 ,'decel'],[4 ,'anti_play_speed'],[1 ,'uanti_play_speed']]
                    if self.parsePars('smov',pars_o,sstring.split(' ')[1:],10) is not None:
                        break
                if sstring.startswith('move_in_direction'):
                    # set movement parameters
                    pars_o=[[4 ,'dpos'],[2 ,'udpos']]
                    if self.parsePars('movr',pars_o,sstring.split(' ')[1:],6) is not None:
                        break
                if sstring.startswith('move'):
                    # set movement parameters
                    pars_o=[[4 ,'pos'],[2 ,'upos']]
                    if self.parsePars('move',pars_o,sstring.split(' ')[1:],6) is not None:
                        break
                if sstring == 'set_zero':
                    # set current position as zero
                    Imessage('zero', nb=4, source=self.name)
                    break
                # general set command (xxxx comands from manual) (for specifically implemented comands see below)
                # command example: smov 4:2000 1:0 2:2000 2:5000 4:2000 1:0 10:r
                # for these commands one needs to specity the number of bytes given value occupies:
                # nbytes1:value1 nbytes2:value2 nreserved:r
                # 
                ss = sstring.split(' ')
                if all(':' in sss for sss in ss[1:]) and all(nnn.split(':')[0].isdigit() for nnn in ss[1:]):
                    cmd=ss[0]
                    ss=ss[1:]
                    rbs=0
                    if len(ss)>1 and ss[-1].split(':')[1] =='r':
                        rbs=int(ss[-1].split(':')[0])
                        ss=ss[:-1]
                    pars=[sss.split(':') for sss in ss]
                    pars = list(map(lambda x:[int(x[0]),x[1]], pars))
                    mstr = self.mbytes(cmd,pars,rbs)
                    if mstr:
                        Imessage(mstr, nb=4, source=self.name)
                    break
                print('command', sstring, 'not implemented!')
                break

class StandaRSProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _bs = b''

    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source"
        self.status_commands = [['gpos',26]]  # commands send when device not busy to keep tabs on the state
        self._comand_end_character = b''


    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0
        self.object['position'] = float('nan')
        self.object['uposition'] = float('nan')
        self.object['encposition'] = float('nan')
        
    @catch
    def processMessage(self, string):
        # Process the device reply
        if self._debug:
            print("hw cc > %s" % string)
        self.commands.pop(0)

    @catch
    def iscom(self,com):
        if self.commands[0]['cmd'] == com and self._bs[:4].decode('ascii') == com:
            self._bs=self._bs[4:]
            return True
        return False
        
    @catch
    def sintb(self,nb):
        ss=self._bs[:nb]
        self._bs=self._bs[nb:]
        return str(int.from_bytes(ss, "little"))
    
    @catch
    def strb(self,nb):
        ss=self._bs[:nb]
        self._bs=self._bs[nb:]
        return (ss.strip(b'\x00')).decode('ascii')

    @catch
    def processBinary(self, bstring):
        # Process the device reply
        self._bs=bstring
        if self._debug:
            print("hw bb > %s" % self._bs)
        if len(self.commands):
            if self._debug:
                print("last command which expects reply was:", self.commands[0]['cmd'])
                print("received reply:", self._bs)
            if (b'errc' or b'errd' or b'errv') in self._bs:
                print('command', self.commands[0]['cmd'], 'produced error', self._bs)
                self._buffer = b''  # empty buffer after error
            
            r_str=None
            while True:
                if self.commands[0]['status'] == 'sent_status':
                    if self.iscom('gpos'):
                        self.object['position'] = int(self.sintb(4))
                        self.object['uposition'] = int(self.sintb(2))
                        self.object['encposition'] = int(self.sintb(8))
                    break
                # check buffer empty and checksum
                if self._buffer != b'':
                    print('warning buffer not empty after expected number of bytes')
                    self._buffer = b''  # empty buffer
                if len(self._bs) > 4 and self.commands[0]['status'] == 'sent' and modbus(self._bs[4:]) != 0:
                    r_str = 'checksum failed'
                    self._buffer = b''
                    break
                if self.commands[0]['status']=='sync':
                    # sync after failed comand
                    r_str = 'sync'
                    if len(self.commands)>1 and self.commands[1]['status']=='sent':
                        #remove failed command
                        self.commands.pop(0)
                    break
                r_str = b''
                if self.iscom('gsti'):
                    r_str = self.strb(16)+' '
                    r_str += self.strb(24)
                    break
                if self.iscom('gmov'):
                    r_str  = 'speed:'+self.sintb(4)+' '
                    r_str += 'uspeed:'+self.sintb(1)+' '
                    r_str += 'accel:'+self.sintb(2)+' '
                    r_str += 'decel:'+self.sintb(2)+' '
                    r_str += 'anti_play_speed:'+self.sintb(4)+' '
                    r_str += 'uanti_play_speed:'+self.sintb(1)
                    break
                if self.iscom('gpos'):
                    pos=self.sintb(4)
                    self.object['position'] = int(pos)
                    r_str = 'pos:'+pos+' '
                    r_str += 'upos:'+self.sintb(2)+' '
                    r_str += 'encpos:'+self.sintb(8)+' '
                    break
                # not recognized command, just pass the output
                r_str = self._bs
                break
            if type(r_str) == str:
                daemon.messageAll(r_str, self.commands[0]['source'])
            elif r_str != b'':
                daemon.messageAll(r_str, self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def Imessage(self, string, nb, source='itself'):
        """Sending outgoing message"""
        if self._debug:
            print(">> serial >>", string, 'expecting', nb, 'bytes')

        """
        Send the message to the controller. If keep=True, expect reply (for this device it seems all comands expect reply
        """
        if string[0] == 0:
            # sync after failed comand, the sync is put at the front of the queue
            self.commands = [{'cmd': string, 'nb': nb, 'source': source, 'status': 'sync'}]+self.commands
        else:
            self.commands.append({'cmd': string, 'nb': nb, 'source': source, 'status': 'new'})

    @catch
    def update(self):
        # Request the hardware state from the device
        if self._debug:
            print ("----------------------- command queue ----------------------------")
            for k in self.commands:
                print (self.commands[0]['cmd'],self.commands[0]['nb'],self.commands[0]['source'],self.commands[0]['status'])
            print ("===================== command queue end ==========================")
            
        if len(self.commands):
            if self.commands[0]['status'].startswith('sent'):
                return
            if self.commands[0]['status'] ==  'new':
                self.commands[0]['status'] = 'sent'
            elif self.commands[0]['status'] ==  'status':
                self.commands[0]['status'] = 'sent_status'
            self.switchToBinary(length=max(4, self.commands[0]['nb']))
            self.message(self.commands[0]['cmd'])
        else:
            for k in self.status_commands:
                self.commands.append({'cmd': k[0], 'nb': k[1], 'source': 'itself', 'status': 'status'})


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-d', '--hw-device',
                      help='Device to connect to. To ensure the USB device is the same after unplug/plug set up an udev rule, something like: ACTION=="add", ATTRS{idVendor}=="1cbe", ATTRS{idProduct}=="0007", ATTRS{serial}=="00004186", SYMLINK+="standa_rs"', action='store', dest='hw_dev', default='/dev/standa_rs')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7027)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='standa_r_stage')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0, 'position': float('nan'), 'uposition': float('nan'), 'encposition': float('nan')}

    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    

    proto = StandaRSProtocol()
    proto.object = obj
    hw = SerialPort(proto, options.hw_dev, daemon._reactor, baudrate=115200, bytesize=8,
                    parity='N', stopbits=2, timeout=400)  # parameters from manual

    hw.protocol._ttydev = options.hw_dev

    if options.debug:
        daemon._protocol._debug = True
        hw.protocol._debug = True

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
