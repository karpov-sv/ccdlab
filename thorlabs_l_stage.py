#!/usr/bin/env python3
from optparse import OptionParser
from collections import namedtuple
import struct as st
#from threading import Thread

from daemon import SimpleFactory, SimpleProtocol, FTDIProtocol, catch
import time


"""
Simple class to make construction and decoding of message bytes easier.

Most of this class was taken from github.com/freespace/pyAPT

Based on APT Communication Protocol Rev. 7 (Thorlabs)

"""
_Message = namedtuple('_Message',  ['messageID', 'param1', 'param2', 'dest', 'src', 'data'])

class Message(_Message):

    @classmethod
    def unpack(cls, databytes, header_only=False):
        """
        pack() produces a string of bytes from a Message, pack() produces a Message from a string of bytes

        If header_only is True, then we will only attempt to decode the header, ignoring any bytes that follow, if any. This allows you get determine what the message is without having to read it in its entirety.

        Note that dest is returned AS IS, which means its MSB will be set if the message is more than just a header.
        """

        Header = namedtuple('Header', ['messageID', 'param1', 'param2', 'dest', 'src'])
        hd = Header._make(st.unpack('<HBBBB', databytes[:6]))

        # if MSB of dest is set, then there is additional data to follow
        if hd.dest & 0x80:
            datalen = hd.param1 | (hd.param2 << 8)
            if header_only:
                data = None
            else:
                data = st.unpack('<%dB' % (datalen), databytes[6:])
            # we need param1 and param2 to be set since we need to know how long the data is when we decode only a header
            return Message(hd.messageID,  dest=hd.dest,  src=hd.src,  param1=hd.param1,  param2=hd.param2,  data=data)
        else:
            return Message(hd.messageID, param1=hd.param1, param2=hd.param2, dest=hd.dest, src=hd.src,  data=data)

    def __new__(cls, messageID, dest=0x50, src=0x01, param1=0, param2=0, data=None):
        assert(type(messageID) == int)
        if data:
            assert(param1 == 0 and param2 == 0)
            assert(type(data) in [list, tuple, str, bytes])
            if type(data) == str:
                data = [ord(c) for c in data]
            elif type(data) == bytes:
                data = list(data)
            return super(Message, cls).__new__(Message, messageID, None, None, dest, src, data)
        else:
            assert(type(param1) == int)
            assert(type(param2) == int)
            return super(Message, cls).__new__(Message, messageID, param1, param2, dest, src, None)

    def pack(self, verbose=False):
        """
        Returns a byte array representing this message packed in little endian
        """
        if self.data:
            """
            <: little endian
            H: 2 bytes for message ID
            H: 2 bytes for data length
            B: unsigned char for dest
            B: unsigned char for src
            %dB: %d bytes of data
            """
            datalen = len(self.data)
            if type(self.data) == str:
                datalist = list(self.data)
            else:
                datalist = self.data

            ret = st.pack('<HHBB%dB' % (datalen), self.messageID, datalen, self.dest | 0x80, self.src, *datalist)
        else:
            """
            <: little endian
            H: 2 bytes for message ID
            B: unsigned char for param1
            B: unsigned char for param2
            B: unsigned char for dest
            B: unsigned char for src
            """
            ret = st.pack('<HBBBB', self.messageID, self.param1, self.param2, self.dest, self.src)
        if verbose:
            print(bytes(self), '=', [hex(ord(x)) for x in ret])
        return ret

    def __eq__(self, other):
        """
        We don't compare the underlying namedtuple because we consider data of
        [1,2,3,4,5] and (1,2,3,4,5) to be the same, while python doesn't.
        """
        return self.pack() == other.pack()

    @property
    def datastring(self):
        if type(self.data) == bytes:
            return self.data
        else:
            return self.data.encode()

    @property
    def datalength(self):
        if self.hasdata:
            if self.data:
                return len(self.data)
            else:
                return self.param1 | (self.param2 << 8)
        else:
            return -1

    @property
    def hasdata(self):
        return self.dest & 0x80

    MGMSG_HEADER_SIZE = 6

    # Generic Commands
    MGMSG_MOD_IDENTIFY = 0x0223
    #MGMSG_HW_RESPONSE = 0x0080

    MGMSG_HW_REQ_INFO = 0x0005
    MGMSG_HW_GET_INFO = 0x0006

    #MGMSG_MOT_ACK_DCSTATUSUPDATE = 0x0492

    # Motor Commands
    #MGMSG_MOT_SET_PZSTAGEPARAMDEFAULTS = 0x0686

    #MGMSG_MOT_MOVE_HOME = 0x0443
    #MGMSG_MOT_MOVE_HOMED = 0x0444
    #MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
    #MGMSG_MOT_MOVE_COMPLETED = 0x0464

    MGMSG_MOT_SET_HOMEPARAMS = 0x0440
    MGMSG_MOT_REQ_HOMEPARAMS = 0x0441
    MGMSG_MOT_GET_HOMEPARAMS = 0x0442

    MGMSG_MOT_REQ_POSCOUNTER = 0x0411
    MGMSG_MOT_GET_POSCOUNTER = 0x0412

    #MGMSG_MOT_REQ_DCSTATUSUPDATE = 0x0490
    #MGMSG_MOT_GET_DCSTATUSUPDATE = 0x0491

    MGMSG_MOT_SET_VELPARAMS = 0x413
    MGMSG_MOT_REQ_VELPARAMS = 0x414
    MGMSG_MOT_GET_VELPARAMS = 0x415

    #MGMSG_MOT_SUSPEND_ENDOFMOVEMSGS = 0x046B
    #MGMSG_MOT_RESUME_ENDOFMOVEMSGS = 0x046C

    #MGMSG_MOT_MOVE_STOP = 0x0465
    #MGMSG_MOT_MOVE_STOPPED = 0x0466


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes.
    
    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        Sstring = (string.strip('\n')).split(';')
        for sstring in Sstring:
            sstring = sstring.strip(' ').lower()

            while True:
                if sstring == 'flash_led':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOD_IDENTIFY),
                                               'source': self.name, 'get_c': 0})
                    break
                if sstring == 'get_info':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_HW_REQ_INFO),
                                               'source': self.name, 'get_c': Message.MGMSG_HW_GET_INFO})
                    break
                if sstring.startswith('get_home_pars'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_HOMEPARAMS),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_HOMEPARAMS,
                                               'unit': 'mm' if sstring == 'get_home_pars_mm' else 'counts'})
                    break
                if sstring.startswith('get_pos'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_POSCOUNTER),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_POSCOUNTER,
                                               'unit': 'mm' if sstring == 'get_pos_mm' else 'counts'})
                    break
                if sstring.startswith('get_vel_pars'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_VELPARAMS),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_VELPARAMS,
                                               'unit': 'mm' if sstring == 'get_vel_pars_mm' else 'counts'})
                    break
                if sstring.startswith('set_vel_pars'):
                    # sould look like: set_vel_pars(_mm),vel:value,acc:value
                    # the pars order does not matter
                    ss=sstring.split(',')
                    assert len(ss)==3, 'command '+ sstring + ' is not valid'
                    vals={}
                    for input_ex in ss[1:]:
                        try:
                            input_ex = input_ex.split(':')
                            vals[input_ex[0]]=float(input_ex[1])
                        except:
                            print ('command '+ sstring + ' is not valid')
                            return
                    
                    if sstring.startswith('set_vel_pars_mm'):
                        vals['acc']*=obj['hw']._acceleration_scale
                        vals['vel']*=obj['hw']._velocity_scale
                    if vals['acc']>obj['hw']._max_acceleration:
                        daemon.log('requested acc of {} [counts*s^-2] is above the limit of {} [counts*s^-2], using the limit value'.format(vals['acc'],obj['hw']._max_acceleration),'warning')
                        vals['acc']=obj['hw']._max_acceleration
                    if vals['vel']>obj['hw']._max_velocity:
                        daemon.log('requested vel of {} [counts*s^-1] is above the limit of {} [counts*s^-1], using the limit value'.format(vals['vel'],obj['hw']._max_acceleration),'warning')
                        vals['vel']=obj['hw']._max_acceleration
                     
                    params = st.pack('<HIII',1,0,int(vals['acc']),int(vals['vel']) )
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_SET_VELPARAMS, data=params),
                                               'source': self.name, 'get_c': 0})
                    break
                #if sstring == 'get_pos':
                break


class ThorlabsLSProtocol(FTDIProtocol):
    _debug = False  # Display all traffic for debug purposes
    
    #the following can in principle be 3 different values
    _position_scale = 25600 # 1mm * position_scale = number of microsteps
    _velocity_scale = 25600 # 1mm/s * velocity_scale = microsteps/s
    _acceleration_scale = 25600 # 1mm * s^-2 = microsteps * s^-2
    
    # conservative limits
    # velocity is in counts
    # acceleration is in counts * s^-2
    _max_velocity = 5.0*_velocity_scale
    _max_acceleration = 5.0*_acceleration_scale
    
    # The linear range for this stage is 50mm
    _linear_range = (0,50*_position_scale)



    @catch
    def __init__(self, serial_num, obj):
        FTDIProtocol.__init__(self, serial_num, obj)
        self.name = 'hw'
        self.type = 'hw'
        self._refresh = 1
        self.commands = []

    @catch
    def ConnectionLost(self):
        super().ConnectionLost()
        self.object['hw_connected'] = 0

    @catch
    def ConnectionMade(self):
        super().ConnectionMade()
        self.object['hw_connected'] = 1
        self.commands = []

    @catch
    def ProcessMessage(self, msg):
        if self._debug:
            print('hw bb >', msg)
            print('last command which expects reply was:', '0x{:04x}'.format(-self.commands[0]['get_c']), '('+str(-self.commands[0]['get_c'])+')')
        r_str = None
        while True:
            if self.commands[0]['get_c'] == -Message.MGMSG_HW_GET_INFO:
                umsg = st.unpack('<I8sH4s48s12sHHH', msg.datastring)
                r_str = 'serial_number:'+str(umsg[0])
                r_str += ',model:'+umsg[1].strip(b'\x00').decode('ascii')
                r_str += ',hw_type:'+str(umsg[2])
                r_str += ',firmware_version:'+str(int.from_bytes(umsg[3], 'little'))
                r_str += ',notes:'+umsg[4].strip(b'\x00').decode('ascii')
                r_str += ',hw_version:'+str(umsg[6])
                r_str += ',modificiation_state:'+str(umsg[7])
                r_str += ',n_channels:'+str(umsg[8])
                break
            if self.commands[0]['get_c'] == -Message.MGMSG_MOT_GET_HOMEPARAMS:
                umsg = st.unpack('<HHHII', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                r_str += ',home_direction:'+str(umsg[1])
                r_str += ',Limit_switch:'+str(umsg[2])
                if self.commands[0]['unit'] == 'counts':
                    r_str += ',home_velocity[counts/s]:'+str(umsg[3])
                    r_str += ',offset_distance[counts]:'+str(umsg[4])
                else:
                    r_str += ',home_velocity[mm/s]:'+str(umsg[3]/self._velocity_scale)
                    r_str += ',offset_distance[mm]:'+str(umsg[4]/self._position_scale)                    
                break
            if self.commands[0]['get_c'] == -Message.MGMSG_MOT_GET_POSCOUNTER:
                umsg = st.unpack('<HI', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                if self.commands[0]['unit'] == 'counts':
                    r_str += ',position[counts]:'+str(umsg[1])
                else:
                    r_str += ',position[mm]:'+str(umsg[1]/self._position_scale)
                break
            if self.commands[0]['get_c'] == -Message.MGMSG_MOT_GET_VELPARAMS:
                umsg = st.unpack('<HIII', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                if self.commands[0]['unit'] == 'counts':
                    r_str += ',accel[counts/s^2]:'+str(umsg[2])
                    r_str += ',vel[counts/s]:'+str(umsg[3])
                else:
                    r_str += ',accel[mm/s^2]:'+str(umsg[2]/self._acceleration_scale)
                    r_str += ',vel[mm/s]:'+str(umsg[3]/self._velocity_scale)
                print('iii', umsg)
                break
            break
        if type(r_str) == str:
            daemon.messageAll(r_str, self.commands[0]['source'])
        elif type(r_str) == bytes:
            daemon.messageAll(r_str, self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def read(self):
        data = bytes()
        while len(data) < Message.MGMSG_HEADER_SIZE:
            diff = Message.MGMSG_HEADER_SIZE - len(data)
            data += self.device.read(diff)
            time.sleep(0.001)
        msg = Message.unpack(data, header_only=True)
        if msg.hasdata:
            data = self.device.read(msg.datalength)
            msglist = list(msg)
            msglist[-1] = data
            self.ProcessMessage(Message._make(msglist))
        else:
            self.ProcessMessage(msg)

    @catch
    def update(self):
        if self.object['hw_connected']:
            if len(self.commands) and self.commands[0]['get_c'] >= 0:
                if self._debug:
                    print('sending command',self.commands[0])
                self.send_message(self.commands[0]['msg'].pack())
                get_c = self.commands[0]['get_c']
                source = obj['hw'].commands[0]['source']
                if get_c:
                    # this command does expect a response, replace the req command with a get one
                    self.commands[0]['get_c']=-self.commands[0]['get_c']
                    self.read()
                else:
                    self.commands.pop(0)



if __name__ == '__main__':
    parser = OptionParser(usage='usage: %prog [options] arg')
    parser.add_option('-s', '--serial-num',
                      help='Serial number of the device to connect to. To ensure the USB device is accesible udev rule, something like: ATTRS{idVendor}=="0403", ATTRS{idProduct}=="faf0" , MODE="0666", GROUP="plugdev"', action='store', dest='serial_num', type='str', default='40824267')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7028)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='thorlabs_l_stage')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0, }

    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    obj['daemon'] = daemon

    hw = ThorlabsLSProtocol(options.serial_num, obj)
    obj['hw'] = hw

    if options.debug:
        daemon._protocol._debug = True
        hw._debug = True

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
