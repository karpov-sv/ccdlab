from serial import Serial
from twisted.internet.task import LoopingCall
from pyudev import Context, Monitor, MonitorObserver

class MINFrame:
    def __init__(self, min_id: int, payload: bytes, seq: int, transport: bool, ack_or_reset=False):
        if ack_or_reset:
            self.min_id = min_id
        else:
            self.min_id = min_id & 0x3f
        self.payload = payload
        self.seq = seq
        self.is_transport = transport
        self.last_sent_time = None  # type: int

class MINProtocol():
    """ 
    Class for outgoing connection to a Arduino (or other device) using the MIN protocol
    https://github.com/min-protocol/min
    """
    _debug = False

    def __init__(self, obj, devname, refresh=0, baudrate=115200, bytesize=8, parity='N', stopbits=2, timeout=400, debug=False):
        # Name and type of the connection peer
        self.name = ''
        self.type = ''

        self._devname = devname
        self.object = obj
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout

        self._debug = debug
        
        self.transport_fifo_size = 100
        self._transport_fifo = []
        
        self._sn_min = 0  # Sequence number of first frame currently in the sending window
        self._sn_max = 0  # Next sequence number to use for sending a frame

        if refresh > 0:
            self._refresh = refresh

        self._updateTimer = LoopingCall(self.update)
        self._updateTimer.start(self._refresh)

        context = Context()
        for device in context.list_devices(subsystem='tty'):
            if 'DEVLINKS' in device.keys() and self._devname in device.get('DEVLINKS'):
                self.Connect()
                self.connectionMade()

        cm = Monitor.from_netlink(context)
        cm.filter_by(subsystem='tty')
        observer = MonitorObserver(cm, callback=self.ConnectionMCallBack, name='monitor-observer')
        observer.start()
        
    def Connect(self):
        self.object['hw'] = Serial(port=self._devname,baudrate=self.baudrate, bytesize=self.bytesize,parity=self.parity, stopbits=self.stopbits, timeout=self.timeout)
        
    def ConnectionMCallBack(self, dd):
        if self._devname in dd.get('DEVLINKS'):
            if dd.action == 'add':
                self.Connect()
                self.connectionMade()
            if dd.action == 'remove':
                self.connectionLost()
 
    def connectionMade(self):
        self._transport_fifo_reset()
        print('Connected to', self._devname)

    def connectionLost(self):
        print('Disconnected from', self._devname)
        
    def _transport_fifo_reset(self):
        self._transport_fifo = []
        #self._last_received_anything_ms = self._now_ms()
        #self._last_sent_ack_time_ms = self._now_ms()
        #self._last_sent_frame_ms = 0
        #self._last_received_frame_ms = 0
        self._sn_min = 0
        self._sn_max = 0

    def queue_frame(self, min_id: int, payload: bytes):
        print('q frame')
        """
        Queues a MIN frame for transmission through the transport protocol. Will be retransmitted until it is
        delivered or the connection has timed out.

        :param min_id: ID of MIN frame (0 .. 63)
        :param payload: up to 255 bytes of payload
        :return:
        """
        if len(payload) not in range(256):
            raise ValueError("MIN payload too large")
        if min_id not in range(64):
            raise ValueError("MIN ID out of range")
        # Frame put into the transport FIFO
        if len(self._transport_fifo) < self.transport_fifo_size:
            if self._debug:
                print("Queueing min_id={}".format(min_id))
            frame = MINFrame(min_id=min_id, payload=payload, seq=self._sn_max, transport=True)
            self._transport_fifo.append(frame)
        else:
            self._dropped_frames += 1
            raise MINConnectionError("No space in transport FIFO queue")


    def update(self):
        pass

