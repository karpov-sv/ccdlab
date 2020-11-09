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
    def mbytes(self,ss,nbs):
        ss=ss.split(' ')
        if len(ss)-1 != len(nbs):
            print ('wrong input')
            return False
        bss = ss[0].encode('ascii')+b''.join([int(i).to_bytes( n, 'little', signed=True ) if n>0 else -n*b'\xcc' for [i,n] in zip(ss[1:],nbs)])
        bss +=modbus(bss[4:]).to_bytes( 2, 'little' )
        return bss
        
    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        obj = self.object  # Object holding the state
        hw = obj['hw'].protocol  # HW factory
        Sstring = (string.strip()).split(';')
        for sstring in Sstring:
            sstring = sstring.lower()
            while True:
                if sstring == 'get_status':
                    self.message('status hw_connected=%s' % (self.object['hw_connected'],))
                    break
                if sstring == 'timeout':
                    self.factory.log('command timeout - removing command from list and flushing buffer')
                    hw._buffer = b''  # empty buffer after timeout
                    hw.commands.pop(0)
                    break
                ss = sstring.split('_')
                if len(ss) == 2:
                    nb = int(ss[0])
                    sstring = ss[1]
                    if ':' in sstring:
                        # this emans command has input parameters, specified like this value1:nbytes1 value2:nbytes2
                        # for the reserved bytes any_num:-10, whete the 110 means 10 reserved bytes
                        # command example: 30_smov 2000:4 0:1 2000:2 5000:2 2000:4 0:1 -1:-10
                        vals=sstring[:4]+' '+' '.join(re.split(':| ',sstring)[1::2])
                        nbs=list(map(int, re.split(':| ',sstring)[2::2] ))
                        mstr = self.mbytes(vals,nbs)
                        if mstr:
                            hw.message(mstr, nb=4, source=self.name)
                    else:
                        hw.message(sstring, nb=nb, source=self.name)
                    break
                if string == 'sync':
                    # sync after failed comand
                    hw.message(bytearray(64), nb=64, source=self.name)
                    break
                if sstring == 'gsti':
                    # get some device info (model, etc.)
                    hw.message(sstring, nb=70, source=self.name)
                    break
                if sstring == 'gmov':
                    # get movement parameters
                    hw.message(sstring, nb=30, source=self.name)
                    break
                if sstring == 'gpos':
                    # get movement parameters
                    hw.message(sstring, nb=26, source=self.name)
                    break
                if sstring.startswith('smov'):
                    # set movement parameters
                    mstr = self.mbytes(sstring,[4,1,2,2,4,1,-10])
                    if mstr:
                        hw.message(mstr, nb=4, source=self.name)
                    break
                if sstring.startswith('move'):
                    # set movement parameters
                    mstr = self.mbytes(sstring,[4,2,-6])
                    if mstr:
                        hw.message(mstr, nb=4, source=self.name)
                    break
                if sstring.startswith('movr'):
                    # set movement parameters
                    mstr = self.mbytes(sstring,[4,2,-6])
                    if mstr:
                        hw.message(mstr, nb=4, source=self.name)
                    break
                if sstring == 'zero':
                    # set current position as zero
                    hw.message(sstring, nb=4, source=self.name)
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
        self.status_commands = []  # commands send when device not busy to keep tabs on the state
        SimpleProtocol._comand_end_character = ''
        print (SimpleProtocol._comand_end_character)


    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1
        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)

    @catch
    def connectionLost(self, reason):
        self.object['hw_connected'] = 0

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
            while True:
                if self.commands[0]['cmd'] in self.status_commands:
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
                    r_str = self.sintb(4)+' '
                    r_str += self.sintb(1)+' '
                    r_str += self.sintb(2)+' '
                    r_str += self.sintb(2)+' '
                    r_str += self.sintb(4)+' '
                    r_str += self.sintb(1)+' '
                    r_str += self.sintb(1)                                    
                    break
                if self.iscom('gpos'):
                    r_str = self.sintb(4)+' '
                    r_str += self.sintb(2)+' '
                    r_str += self.sintb(8)+' '
                    break
                if self.iscom('zero'):
                    break
                # not recognized command, just pass the output
                r_str = self._bs
                break
            if type(r_str) == str:
                daemon.messageAll(r_str+'\n', self.commands[0]['source'])
            elif r_str != b'':
                daemon.messageAll(r_str+b'\n', self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def message(self, string, nb, source='itself'):
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
        if len(self.commands):
            if self.commands[0]['status'] ==  'new':
                SimpleProtocol.switchToBinary(self, length=max(4, self.commands[0]['nb']))
                SimpleProtocol.message(self, self.commands[0]['cmd'])
                self.commands[0]['status'] = 'sent'
            elif self.commands[0]['status'] ==  'sync':
                SimpleProtocol.switchToBinary(self, length=max(4, self.commands[0]['nb']))
                SimpleProtocol.message(self, self.commands[0]['cmd'])
                
        # else:
            # for k in self.status_commands:
            # self.commands.append(
            # {'cmd': k, 'source': 'itself', 'keep': True})
            #SimpleProtocol.message(self, self.commands[0]['cmd'])


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
    obj = {
        'hw_connected': 0,
    }

    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    

    proto = StandaRSProtocol()
    proto.object = obj
    hw = SerialPort(proto, options.hw_dev, daemon._reactor, baudrate=115200, bytesize=8,
                    parity='N', stopbits=2, timeout=400)  # parameters from manual

    hw.protocol._ttydev = options.hw_dev
    hw.protocol._comand_end_character = ''  # the device expects just 4 bytes, then it acts

    if options.debug:
        daemon._protocol._debug = True
        hw.protocol._debug = True

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
