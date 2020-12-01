#!/usr/bin/env python3
from optparse import OptionParser
from collections import namedtuple
import struct as st
#from threading import Thread

from daemon import SimpleFactory, SimpleProtocol, FTDIProtocol, catch
from time import sleep


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
            return Message(hd.messageID, param1=hd.param1, param2=hd.param2, dest=hd.dest, src=hd.src)

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

    MGMSG_MOD_SET_CHANENABLESTATE = 0x0210
    MGMSG_MOD_REQ_CHANENABLESTATE = 0x0211
    MGMSG_MOD_GET_CHANENABLESTATE = 0x0212

    #MGMSG_HW_RESPONSE = 0x0080

    MGMSG_HW_REQ_INFO = 0x0005
    MGMSG_HW_GET_INFO = 0x0006

    MGMSG_MOT_ACK_DCSTATUSUPDATE = 0x0492

    # Motor Commands

    MGMSG_MOT_MOVE_HOME = 0x0443
    #MGMSG_MOT_MOVE_HOMED = 0x0444
    MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
    #MGMSG_MOT_MOVE_COMPLETED = 0x0464

    MGMSG_MOT_SET_HOMEPARAMS = 0x0440
    MGMSG_MOT_REQ_HOMEPARAMS = 0x0441
    MGMSG_MOT_GET_HOMEPARAMS = 0x0442

    MGMSG_MOT_SET_LIMSWITCHPARAMS = 0x0423
    MGMSG_MOT_REQ_LIMSWITCHPARAMS = 0x0424
    MGMSG_MOT_GET_LIMSWITCHPARAMS = 0x0425

    MGMSG_MOT_REQ_POSCOUNTER = 0x0411
    MGMSG_MOT_GET_POSCOUNTER = 0x0412

    MGMSG_MOT_GET_STATUSUPDATE = 0x0481
    MGMSG_MOT_REQ_STATUSUPDATE = 0x0480

    MGMSG_MOT_SET_VELPARAMS = 0x413
    MGMSG_MOT_REQ_VELPARAMS = 0x414
    MGMSG_MOT_GET_VELPARAMS = 0x415

    #MGMSG_MOT_SUSPEND_ENDOFMOVEMSGS = 0x046B
    #MGMSG_MOT_RESUME_ENDOFMOVEMSGS = 0x046C

    MGMSG_MOT_MOVE_STOP = 0x0465
    MGMSG_MOT_MOVE_STOPPED = 0x0466


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
                if sstring == 'get_status':
                    self.message(
                        'status hw_connected={hw_connected} position={position} hw_limit={hw_limit} moving={moving} jogg={jogg} home={home} tracking={tracking} settled={settled} motion_limit_err={motion_limit_err} curr_limit_err={curr_limit_err} channel_enabled={channel_enabled}'.format(**self.object))
                    break
                if sstring == 'flash_led':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOD_IDENTIFY),
                                               'source': self.name, 'get_c': 0})
                    break
                if sstring == 'get_info':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_HW_REQ_INFO),
                                               'source': self.name, 'get_c': Message.MGMSG_HW_GET_INFO})
                    break
                if sstring.startswith('get_hw_status'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_STATUSUPDATE),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_STATUSUPDATE,
                                               'unit': 'mm' if sstring == 'get_pos_mm' else 'counts'})
                    break
                if sstring == 'get_enable_state':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOD_REQ_CHANENABLESTATE, param1=1),
                                               'source': self.name, 'get_c': Message.MGMSG_MOD_GET_CHANENABLESTATE})
                    break
                if sstring.startswith('set_enable_state'):
                    ss = sstring.split(':')
                    assert len(ss) == 2, 'command ' + sstring + ' is not valid'
                    if ss[1] not in ['0', '1']:
                        print('command ' + sstring + ' is not valid')
                        return
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOD_SET_CHANENABLESTATE, param1=1, param2=int(ss[1])),
                                               'source': self.name, 'get_c': 0})
                    break
                if sstring.startswith('get_home_pars'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_HOMEPARAMS, param1=1),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_HOMEPARAMS,
                                               'unit': 'mm' if sstring == 'get_home_pars_mm' else 'counts'})
                    break
                if sstring.startswith('set_home_pars'):
                    ss = sstring.split(',')
                    assert len(ss) == 5, 'command ' + sstring + ' is not valid '+str(len(ss))
                    vals = {}
                    for input_ex in ss[1:]:
                        try:
                            input_ex = input_ex.split(':')
                            if input_ex[0] == 'dir' and input_ex[1] in ['1', '2']:
                                vals[input_ex[0]] = int(input_ex[1])
                            elif input_ex[0] == 'lim' and input_ex[1] in ['1', '4']:
                                vals[input_ex[0]] = int(input_ex[1])
                            elif input_ex[0] == 'v':
                                vals[input_ex[0]] = float(input_ex[1])
                                if sstring.startswith('set_home_pars_mm'):
                                    vals[input_ex[0]] *= obj['hw']._velocity_scale
                            elif input_ex[0] == 'offset':
                                vals[input_ex[0]] = float(input_ex[1])
                                if sstring.startswith('set_home_pars_mm'):
                                    vals[input_ex[0]] *= obj['hw']._position_scale
                        except:
                            print('command ' + sstring + ' is not valid')
                            return

                    if {'dir', 'lim', 'v', 'offset'} != vals.keys():
                        print('command ' + sstring + ' is not valid')

                    params = st.pack('<HHHII', 1, int(vals['dir']), int(vals['lim']), int(vals['v']), int(vals['offset']))
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_SET_HOMEPARAMS, data=params),
                                               'source': self.name, 'get_c': 0})
                if sstring.startswith('get_lim_pars'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_LIMSWITCHPARAMS, param1=1),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_LIMSWITCHPARAMS,
                                               'unit': 'mm' if sstring == 'get_lim_pars_mm' else 'counts'})
                    break
                if sstring.startswith('set_lim_pars'):
                    ss = sstring.split(',')
                    assert len(ss) == 5, 'command ' + sstring + ' is not valid '+str(len(ss))
                    vals = {}
                    for input_ex in ss[1:]:
                        try:
                            input_ex = input_ex.split(':')
                            if input_ex[0] in ['CW_hw_lim', 'CCW_hw_lim'] and input_ex[1] in ['1', '2', '3']:
                                vals[input_ex[0]] = int(input_ex[1])
                            if input_ex[0] in ['CW_sw_lim', 'CCW_sw_lim']:
                                vals[input_ex[0]] = int(input_ex[1])
                                if (sstring == 'get_lim_pars_mm'):
                                    vals[input_ex[0]] *= obj['hw']._position_scale
                            if input_ex[0] == 'sw_lim_mode' and input_ex[1] in ['1', '2', '3']:
                                vals[input_ex[0]] = int(input_ex[1])
                        except:
                            print('command ' + sstring + ' is not valid')
                            return

                    if {'CW_hw_lim', 'CCW_hw_lim', 'CW_sw_lim', 'CCW_sw_lim', 'sw_lim_mode'} != vals.keys():
                        print('command ' + sstring + ' is not valid')
                        return
                    params = st.pack('<HHHIIH', 1, int(vals['CW_hw_lim']), int(vals['CCW_hw_lim']), int(
                        vals['CW_sw_lim']), int(vals['CCW_sw_lim']), int(vals['sw_lim_mode']))
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_SET_LIMSWITCHPARAMS, data=params),
                                               'source': self.name, 'get_c': 0,
                                               'unit': 'mm' if sstring == 'get_lim_pars_mm' else 'counts'})
                    break

                if sstring.startswith('get_pos'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_POSCOUNTER, param1=1),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_POSCOUNTER,
                                               'unit': 'mm' if sstring == 'get_pos_mm' else 'counts'})
                    break
                if sstring.startswith('get_v_pars'):
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_REQ_VELPARAMS, param1=1),
                                               'source': self.name, 'get_c': Message.MGMSG_MOT_GET_VELPARAMS,
                                               'unit': 'mm' if sstring == 'get_v_pars_mm' else 'counts'})
                    break
                if sstring.startswith('set_v_pars'):
                    # sould look like: set_v_pars(_mm),v:value,a:value
                    # the pars order does not matter
                    ss = sstring.split(',')
                    assert len(ss) == 3, 'command ' + sstring + ' is not valid'
                    vals = {}
                    for input_ex in ss[1:]:
                        try:
                            input_ex = input_ex.split(':')
                            vals[input_ex[0]] = float(input_ex[1])
                        except:
                            print('command ' + sstring + ' is not valid')
                            return
                    if {'v', 'a'} != vals.keys():
                        print('command ' + sstring + ' is not valid')
                        return
                    if sstring.startswith('set_v_pars_mm'):
                        vals['a'] *= obj['hw']._acceleration_scale
                        vals['v'] *= obj['hw']._velocity_scale
                    if vals['a'] > obj['hw']._max_acceleration:
                        daemon.log(
                            'requested acc of {} [counts*s^-2] is above the limit of {} [counts*s^-2], using the limit value'.format(vals['a'], obj['hw']._max_acceleration), 'warning')
                        vals['a'] = obj['hw']._max_acceleration
                    if vals['v'] > obj['hw']._max_velocity:
                        daemon.log(
                            'requested v of {} [counts*s^-1] is above the limit of {} [counts*s^-1], using the limit value'.format(vals['v'], obj['hw']._max_acceleration), 'warning')
                        vals['v'] = obj['hw']._max_velocity

                    params = st.pack('<HIII', 1, 0, int(vals['a']), int(vals['v']))
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_SET_VELPARAMS, data=params),
                                               'source': self.name, 'get_c': 0})
                    break

                if sstring == 'home':
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_MOVE_HOME, param1=1),
                                               'source': self.name, 'get_c': 0})
                    break

                if sstring.startswith('move_abs'):
                    # sould look like: move_abs(_mm):value
                    ss = sstring.split(':')
                    assert len(ss) == 2, 'command ' + sstring + ' is not valid'
                    apos = 0
                    try:
                        apos = float(ss[1])
                    except:
                        print('command ' + sstring + ' is not valid')
                        return
                    if sstring.startswith('move_abs_mm'):
                        apos *= obj['hw']._position_scale
                    if apos < obj['hw']._linear_range[0]:
                        daemon.log('requested abs position of {} [counts] is below the limit of {} [counts], using the limit value'.format(
                            apos, obj['hw']._linear_range[0]), 'warning')
                        apos = obj['hw']._linear_range[0]
                    if apos > obj['hw']._linear_range[1]:
                        daemon.log('requested abs position of {} [counts] is above the limit of {} [counts], using the limit value'.format(
                            apos, obj['hw']._linear_range[1]), 'warning')
                        apos = obj['hw']._linear_range[1]
                    params = st.pack('<Hi', 1, int(apos))
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_MOVE_ABSOLUTE, data=params),
                                               'source': self.name, 'get_c': 0})
                    break
                if sstring.startswith('stop'):
                    ss = sstring.split(':')
                    assert len(ss) == 2, 'command ' + sstring + ' is not valid'
                    if ss[1] == 'now':
                        p2 = 0x01
                    elif ss[1] == 'slow':
                        p2 = 0x02
                    else:
                        print('command ' + sstring + ' is not valid')
                        break
                    obj['hw'].commands.append({'msg': Message(Message.MGMSG_MOT_MOVE_STOP, param1=1, param2=p2),
                                               'source': self.name, 'get_c': 0})
                    break
                break


class ThorlabsLSProtocol(FTDIProtocol):
    _debug = False  # Display all traffic for debug purposes

    # the following can in principle be 3 different values
    _position_scale = 25600  # 1mm * position_scale = number of microsteps
    _velocity_scale = 25600  # 1mm/s * velocity_scale = microsteps/s
    _acceleration_scale = 25600  # 1mm * s^-2 = microsteps * s^-2

    # conservative limits
    # velocity is in counts
    # acceleration is in counts * s^-2
    # From the manual:
    # Maximum Velocity	50 mm/s
    # Maximum Acceleration	50 mm/s2
    _max_velocity = 5.0*_velocity_scale
    _max_acceleration = 5.0*_acceleration_scale

    # The linear range for this stage is 50mm
    _linear_range = (0, 50*_position_scale)

    _buffer = bytes()
    _read_msg = None

    @catch
    def __init__(self, serial_num, obj, debug=False):
        # commands send when device not busy to keep tabs on the state
        self.status_commands = [{'msg': Message(Message.MGMSG_MOT_REQ_STATUSUPDATE), 'source': 'itself',
                                 'get_c': -Message.MGMSG_MOT_GET_STATUSUPDATE, 'unit': 'mm'}]
        self._debug = debug
        FTDIProtocol.__init__(self, serial_num, obj)
        self.name = 'hw'
        self.type = 'hw'
        self._refresh = 1

    @catch
    def ConnectionLost(self):
        super().ConnectionLost()
        self.object['hw_connected'] = 0
        self.object['position'] = '-'
        self.object['hw_limit'] = '--.--'
        self.object['moving'] = '-'
        self.object['jogg'] = '-'
        self.object['home'] = '-'
        self.object['tracking'] = '-',
        self.object['settled'] = '-'
        self.object['motion_limit_err'] = '-'
        self.object['curr_limit_err'] = '-'
        self.object['channel_enabled'] = '-'

    @catch
    def ConnectionMade(self):
        self._buffer = bytes()
        self._read_msg = None

        self.commands = []
        # init some parameters
        params = st.pack('<HHHIIH', 1, 3, 3, 50*self._position_scale, 0, 1)
        self.commands.append({'msg': Message(Message.MGMSG_MOT_SET_LIMSWITCHPARAMS, data=params), 'source': 'itself', 'get_c': 0})
        params = st.pack('<HHHII', 1, 2, 1, 2*self._velocity_scale, int(0.1*self._position_scale))
        self.commands.append({'msg': Message(Message.MGMSG_MOT_SET_HOMEPARAMS, data=params), 'source': 'itself', 'get_c': 0})
        super().ConnectionMade()
        self.object['hw_connected'] = 1

    @catch
    def DecodeStatusBits(self, status_bits):
        _hw_lim_fw = 0x1
        _hw_lim_re = 0x2
        _mov_fw = 0x10
        _mov_re = 0x20
        _jog_fw = 0x40
        _jog_re = 0x80
        _homing = 0x200
        _homed = 0x400
        _tracking = 0x1000
        _settled = 0x2000
        _mot_err = 0x4000
        _curr_err = 0x1000000
        _ch_en = 0x80000000

        self.object['hw_limit'] = ('fw' if status_bits & _hw_lim_fw else 'OK') + self.object['hw_limit'][2:]
        self.object['hw_limit'] = self.object['hw_limit'][:3]+('re' if status_bits & _hw_lim_re else 'OK')
        self.object['moving'] = 'fw' if status_bits & _mov_fw else 're' if status_bits & _mov_re else 'x'
        self.object['jogg'] = 'fw' if status_bits & _jog_fw else 're' if status_bits & _jog_re else 'x'
        self.object['home'] = 'homing' if status_bits & _homing else 'homed' if status_bits & _homed else 'no'
        self.object['tracking'] = 'yes' if status_bits & _tracking else 'no'
        self.object['settled'] = 'yes' if status_bits & _settled else 'no'
        self.object['motion_limit_err'] = 'err' if status_bits & _mot_err else 'ok'
        self.object['curr_limit_err'] = 'err' if status_bits & _curr_err else 'ok'
        self.object['channel_enabled'] = 'yes' if status_bits & _ch_en else 'no'

    @catch
    def ProcessMessage(self, msg):
        if self._debug:
            print('hw bb >', msg)

        r_str = None
        while True:
            if self._debug and len(self.commands):
                print('last command which expects reply was:', '0x{:04x}'.format(-self.commands[0]['get_c']), '('+str(-self.commands[0]['get_c'])+')')

            source = None
            unit = 'mm'
            if len(self.commands) and -self.commands[0]['get_c'] == msg.messageID:
                source = self.commands[0]['source']
                unit = self.commands[0]['unit'] if 'unit' in self.commands[0].keys() else None
                if self._debug:
                    print('pop command', self.commands[0])
                self.commands.pop(0)

            if msg.messageID == Message.MGMSG_HW_GET_INFO:
                print('msg.messageID', msg.messageID, Message.MGMSG_HW_GET_INFO)
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
            if msg.messageID == Message.MGMSG_MOT_GET_STATUSUPDATE:
                umsg = st.unpack('<HiII', msg.datastring[:14])
                self.DecodeStatusBits(umsg[3])
                r_str = 'channel_id:'+str(umsg[0])
                self.object['position'] = str(umsg[1]/self._position_scale)
                if unit == 'counts':
                    r_str += ',position[counts]:'+str(umsg[1])
                else:
                    r_str += ',position[mm]:'+str(umsg[1]/self._position_scale)
                r_str += ',encounter:'+str(umsg[2])
                r_str += ',status_bits:{:032b}'.format(umsg[3])
                break
            if msg.messageID == Message.MGMSG_MOD_GET_CHANENABLESTATE:
                r_str = 'channel_id:'+str(msg.param1)
                r_str += ',enable_state:'+str(msg.param2)+'command does not seem to work'
                break
            if msg.messageID == Message.MGMSG_MOT_GET_HOMEPARAMS:
                umsg = st.unpack('<HHHii', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                r_str += ',home_direction:'+str(umsg[1])
                r_str += ',Limit_switch:'+str(umsg[2])
                if unit == 'counts':
                    r_str += ',home_velocity[counts/s]:'+str(umsg[3])
                    r_str += ',offset_distance[counts]:'+str(umsg[4])
                else:
                    r_str += ',home_velocity[mm/s]:'+str(umsg[3]/self._velocity_scale)
                    r_str += ',offset_distance[mm]:'+str(umsg[4]/self._position_scale)
                break
            if msg.messageID == Message.MGMSG_MOT_GET_LIMSWITCHPARAMS:
                umsg = st.unpack('<HHHIIH', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                r_str += ',CW_hw_lim:0x{:02x}'.format(umsg[1])
                r_str += ',CCW_hw_lim:0x{:02x}'.format(umsg[2])
                if unit == 'counts':
                    r_str += ',CW_sw_lim[counts]:'+str(umsg[3])
                    r_str += ',CCW_sw_lim[counts]:'+str(umsg[4])
                else:
                    r_str += ',CW_sw_lim[mm]:'+str(umsg[3]/self._position_scale)
                    r_str += ',CCW_sw_lim[mm]:'+str(umsg[4]/self._position_scale)
                r_str += ',sw_lim_mode:0x{:02x}'.format(umsg[5])
                break
            if msg.messageID == Message.MGMSG_MOT_GET_POSCOUNTER:
                umsg = st.unpack('<Hi', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                if unit == 'counts':
                    r_str += ',position[counts]:'+str(umsg[1])
                else:
                    r_str += ',position[mm]:'+str(umsg[1]/self._position_scale)
                break
            if msg.messageID == Message.MGMSG_MOT_GET_VELPARAMS:
                umsg = st.unpack('<Hiii', msg.datastring)
                r_str = 'channel_id:'+str(umsg[0])
                if unit == 'counts':
                    r_str += ',a[counts/s^2]:'+str(umsg[2])
                    r_str += ',v[counts/s]:'+str(umsg[3])
                else:
                    r_str += ',a[mm/s^2]:'+str(umsg[2]/self._acceleration_scale)
                    r_str += ',v[mm/s]:'+str(umsg[3]/self._velocity_scale)
                break
            if msg.messageID == Message.MGMSG_MOT_MOVE_STOPPED:
                umsg = st.unpack('<HihHI', msg.datastring)
                self.DecodeStatusBits(umsg[4])
                r_str = 'channel_id:'+str(umsg[0])
                r_str += ',pos[counts]:'+str(umsg[1])
                r_str += ',v[counts/s]:'+str(umsg[2])
                r_str += ',status_bits:{:032b}'.format(umsg[4])
                break
            break

        if type(r_str) == str and source:
            daemon.messageAll(r_str, source)
        elif type(r_str) == bytes and source:
            daemon.messageAll(r_str, source)
        else:
            print('unrequested responce:', '0x{:04x}'.format(msg.messageID), msg, r_str)

    @catch
    def read(self):
        if not self._read_msg and len(self._buffer) < Message.MGMSG_HEADER_SIZE:
            self._buffer += self.device.read(Message.MGMSG_HEADER_SIZE-len(self._buffer))
            # expecting header, if not complete header read some more

        if not self._read_msg and len(self._buffer) >= Message.MGMSG_HEADER_SIZE:
            # expecting header, which just arrived
            self._read_msg = Message.unpack(self._buffer[:Message.MGMSG_HEADER_SIZE], header_only=True)
            self._buffer = self._buffer[Message.MGMSG_HEADER_SIZE:]
            if not self._read_msg.hasdata:
                # the message has no additional data, send it further and reset self._read_msg
                self.ProcessMessage(self._read_msg)
                self._read_msg = None
                return

        if self._read_msg and len(self._buffer) < self._read_msg.datalength:
            self._buffer += self.device.read(self._read_msg.datalength-len(self._buffer))
            # header has been received and processed and now if not (at least) the required amount of data arrived read some more

        if self._read_msg and len(self._buffer) >= self._read_msg.datalength:
            # header has been received and processed and now (at least) the required amount of data arrived, send it further and reset self._read_msg
            msglist = list(self._read_msg)
            msglist[-1] = self._buffer[:self._read_msg.datalength]
            self.ProcessMessage(Message._make(msglist))
            self._buffer = self._buffer[self._read_msg.datalength:]
            self._read_msg = None

    @catch
    def update(self):
        if self._debug:
            print("----------------------- command queue ----------------------------")
            for k in self.commands:
                print('0x{:04x}'.format(k['msg'].messageID), k)
            print("===================== command queue end ==========================")

        if self.object['hw_connected']:
            if len(self.commands) and self.commands[0]['get_c'] >= 0:
                if self._debug:
                    print('sending command', self.commands[0])
                self.send_message(self.commands[0]['msg'].pack())
                if self.commands[0]['get_c']:
                    # this command does expect a response, replace the req command with a get one
                    self.commands[0]['get_c'] = -self.commands[0]['get_c']
                else:
                    self.commands.pop(0)
            else:
                for cc in self.status_commands:
                    if cc['get_c']:
                        self.commands.append(cc)
                    self.send_message(cc['msg'].pack())


if __name__ == '__main__':
    parser = OptionParser(usage='usage: %prog [options] arg')
    parser.add_option('-s', '--serial-num',
                      help='Serial number of the device to connect to. To ensure the USB device is accesible udev rule, something like: ATTRS{idVendor}=="0403", ATTRS{idProduct}=="faf0" , MODE="0666", GROUP="plugdev"', action='store', dest='serial_num', type='str', default='40824267')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7028)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='thorlabs_l_stage1')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0,
           'position': '-',
           'hw_limit': '--.--',
           'moving': '-',
           'jogg': '-',
           'home': '-',
           'tracking': '-',
           'settled': '-',
           'motion_limit_err': '-',
           'curr_limit_err': '-',
           'channel_enabled': '-',
           }

    daemon = SimpleFactory(DaemonProtocol, obj)
    if options.debug:
        daemon._protocol._debug = True
    daemon.name = options.name
    obj['daemon'] = daemon

    hw = ThorlabsLSProtocol(options.serial_num, obj, debug=options.debug)
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
