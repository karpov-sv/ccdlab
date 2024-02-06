"""
this is revritten code from: 
github.com/min-protocol/min
Implementation of T-MIN for Python. Designed to run on a host PC (the target board has a C version).

Author: Ken Tindell
"""
from serial import Serial
from time import time
from logging import getLogger, ERROR, DEBUG
from binascii import crc32
from pyudev import Context, Monitor, MonitorObserver
from struct import pack

from twisted.internet.task import LoopingCall

min_logger = getLogger('min')


def now_ms():
    now = int(time() * 1000.0)
    return now


def int32_to_bytes(value: int) -> bytes:
    return pack('>I', value)


def bytes_to_hexstr(b: bytes) -> str:
    return "".join("{:02x}".format(byte) for byte in b)


class MINFrame:
    def __init__(self, min_id: int, payload: bytes, seq: int, transport: bool, source="", ack_or_reset=False):
        if ack_or_reset:
            self.min_id = min_id
        else:
            self.min_id = min_id & 0x3f
        self.payload = payload
        self.seq = seq
        self.is_transport = transport
        self.last_sent_time = None  # type: int
        self.source = source


class MINProtocol():
    """ 
    Class for outgoing connection to a Arduino (or other device) using the MIN protocol
    https://github.com/min-protocol/min
    """
    ACK = 0xff
    RESET = 0xfe

    HEADER_BYTE = 0xaa
    STUFF_BYTE = 0x55
    EOF_BYTE = 0x55

    SEARCHING_FOR_SOF = 0
    RECEIVING_ID_CONTROL = 1
    RECEIVING_LENGTH = 2
    RECEIVING_SEQ = 3
    RECEIVING_PAYLOAD = 4
    RECEIVING_CHECKSUM_3 = 5
    RECEIVING_CHECKSUM_2 = 6
    RECEIVING_CHECKSUM_1 = 7
    RECEIVING_CHECKSUM_0 = 8
    RECEIVING_EOF = 9

    def __init__(self, obj, devname, refresh=0, baudrate=115200, bytesize=8, parity='N', stopbits=2, timeout=400, debug=False, window_size=8, rx_window_size=16, transport_fifo_size=100, ack_retransmit_timeout_ms=25, frame_retransmit_timeout_ms=50):
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

        self.transport_fifo_size = transport_fifo_size
        self.ack_retransmit_timeout_ms = ack_retransmit_timeout_ms
        self.max_window_size = window_size
        self.frame_retransmit_timeout_ms = frame_retransmit_timeout_ms
        self.rx_window_size = rx_window_size

        # State of transport FIFO
        self._transport_fifo = None
        self._last_sent_ack_time_ms = None

        # State for receiving a MIN frame
        self._rx_frame_buf = bytearray()
        self._rx_header_bytes_seen = 0
        self._rx_frame_state = self.SEARCHING_FOR_SOF
        self._rx_frame_checksum = 0
        self._rx_frame_id_control = 0
        self._rx_frame_seq = 0
        self._rx_frame_length = 0
        self._rx_control = 0
        self._stashed_rx_dict = {}

        self._rn = 0  # Sequence number expected to be received next
        self._sn_min = 0  # Sequence number of first frame currently in the sending window
        self._sn_max = 0  # Next sequence number to use for sending a frame
        self.source = {}  # sequence <--> sommand source linking

        self._nack_outstanding = None

        self._transport_fifo_reset()

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
        self.object['hw'] = Serial(port=self._devname, baudrate=self.baudrate, bytesize=self.bytesize,
                                   parity=self.parity, stopbits=self.stopbits, timeout=self.timeout)

    def ConnectionMCallBack(self, dd):
        if self._devname in dd.get('DEVLINKS'):
            if dd.action == 'add':
                self.Connect()
                self.connectionMade()
            if dd.action == 'remove':
                self.connectionLost()

    def connectionMade(self):
        self.transport_reset()
        min_logger.debug('Connected to ' + self._devname)

    def connectionLost(self):
        min_logger.debug('Disconnected from ' + self._devname)

    def update(self):
        pass

    def _transport_fifo_pop(self):
        assert len(self._transport_fifo) > 0
        if self._transport_fifo[0].source:
            self.source[self._transport_fifo[0].seq] = self._transport_fifo[0].source
        del self._transport_fifo[0]

    def _transport_fifo_send(self, frame: MINFrame):
        on_wire_bytes = self._on_wire_bytes(frame=frame)
        min_logger.debug("Sending Frame, bytes={}".format(on_wire_bytes))
        frame.last_sent_time = now_ms()
        self.object['hw'].write(on_wire_bytes)

    def _send_ack(self):
        # For a regular ACK we request no additional retransmits
        ack_frame = MINFrame(min_id=self.ACK, seq=self._rn, payload=bytes([self._rn]), transport=True, ack_or_reset=True)
        on_wire_bytes = self._on_wire_bytes(frame=ack_frame)
        self._last_sent_ack_time_ms = now_ms()
        #min_logger.debug("Sending ACK, seq={}, bytes={}".format(ack_frame.seq, on_wire_bytes))
        self.object['hw'].write(on_wire_bytes)

    def _send_nack(self, to: int):
        # For a NACK we send an ACK but also request some frame retransmits
        nack_frame = MINFrame(min_id=self.ACK, seq=self._rn, payload=bytes([to]), transport=True, ack_or_reset=True)
        on_wire_bytes = self._on_wire_bytes(frame=nack_frame)
        min_logger.debug("Sending NACK, seq={}, to={}".format(nack_frame.seq, to))
        self.object['hw'].write(on_wire_bytes)

    def _send_reset(self):
        min_logger.debug("Sending RESET")
        reset_frame = MINFrame(min_id=self.RESET, seq=0, payload=bytes(), transport=True, ack_or_reset=True)
        on_wire_bytes = self._on_wire_bytes(frame=reset_frame)
        self.object['hw'].write(on_wire_bytes)

    def _transport_fifo_reset(self):
        self.source = {}
        self._transport_fifo = []
        self._last_sent_ack_time_ms = now_ms()
        self._sn_min = 0
        self._sn_max = 0

    def _rx_reset(self):
        self._stashed_rx_dict = {}

    def transport_reset(self):
        """
        Sends a RESET to the other side to say that we are going away and clears out the FIFO and receive queues
        :return: 
        """
        self._send_reset()
        self._send_reset()
        self._transport_fifo_reset()
        self._rx_reset()

    def queue_frame(self, min_id: int, payload: bytes, source: str):
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
            min_logger.debug("Queueing min_id={}".format(min_id))
            frame = MINFrame(min_id=min_id, payload=payload, seq=self._sn_max, source=source, transport=True)
            self._transport_fifo.append(frame)
        else:
            raise MINConnectionError("No space in transport FIFO queue")

    def _min_frame_received(self, min_id_control: int, min_payload: bytes, min_seq: int):
        """
        Handle a received MIN frame. Because this runs on a host with plenty of CPU time and memory we stash out-of-order frames
        and send negative acknowledgements (NACKs) to ask for missing ones. This greatly improves the performance in the presence
        of line noise: a dropped frame will be specifically requested to be resent and then the stashed frames appended in the
        right order.

        Note that the automatic retransmit of frames must be tuned carefully so that a window + a NACK received + retransmission
        of missing frames + ACK for the complete set is faster than the retransmission timeout otherwise there is unnecessary
        retransmission of frames which wastes bandwidth.

        The embedded version of this code does not implement NACKs: generally the MCU will not have enough memory to stash out-of-order
        frames for later reassembly.
        """
        min_logger.debug("MIN frame received @{}: min_id_control=0x{:02x}, min_seq={}".format(time(), min_id_control, min_seq))
        if min_id_control & 0x80:
            if min_id_control == self.ACK:
                min_logger.debug("Received ACK")
                # The ACK number indicates the serial number of the next packet wanted, so any previous packets can be marked off
                number_acked = (min_seq - self._sn_min) & 0xff
                number_in_window = (self._sn_max - self._sn_min) & 0xff
                # Need to guard against old ACKs from an old session still turning up.
                # Number acked will be 1 if there are no frames in the window
                if number_acked <= number_in_window:
                    min_logger.debug("Number ACKed = {}".format(number_acked))
                    self._sn_min = min_seq
                    assert len(self._transport_fifo) >= number_in_window
                    assert number_in_window <= self.max_window_size
                    new_number_in_window = (self._sn_max - self._sn_min) & 0xff
                    if new_number_in_window + number_acked != number_in_window:
                        raise AssertionError
                    for i in range(number_acked):
                        self._transport_fifo_pop()
                else:
                    if number_in_window > 0:
                        min_logger.warning("Spurious ACK: self._sn_min={}, self._sn_max={}, min_seq={}, payload[0]={}".format(
                            self._sn_min, self._sn_max, min_seq, min_payload[0]))
            elif min_id_control == self.RESET:
                min_logger.debug("RESET received".format(min_seq))
                self._transport_fifo_reset()
                self._rx_reset()
            elif len(self.source):
                # MIN frame received
                orig_seq=int(min_payload.decode('ascii').split(':')[0])
                min_frame = MINFrame(min_id=min_id_control, payload=min_payload, seq=min_seq, source=self.source[orig_seq], transport=True)
                del self.source[orig_seq]
                min_logger.debug("orig seq {}, sources left {}".format(orig_seq,len(self.source)))
                if min_seq == self._rn:
                    min_logger.debug("MIN application frame received @{} (min_id={} seq={})".format(time(), min_id_control & 0x3f, min_seq))
                    self.processFrame(min_frame)
                    # We want this frame. Now see if there are stashed frames it joins up with and 'receive' those
                    self._rn = (self._rn + 1) & 0xff
                    while self._rn in self._stashed_rx_dict:
                        stashed_frame = self._stashed_rx_dict[self._rn]  # type: MINFrame
                        min_logger.debug("MIN application stashed frame recovered @{} (self._rn={} min_id={} seq={})".format(time(),
                                                                                                                             self._rn, stashed_frame.min_id, stashed_frame.seq))
                        del self._stashed_rx_dict[self._rn]
                        self.processFrame(stashed_frame)
                        self._rn = (self._rn + 1) & 0xff
                        if self._rn == self._nack_outstanding:
                            self._nack_outstanding = None  # The missing frames we asked for have joined up with the main sequence
                    # If there are stashed frames left then it means that the stashed ones have missing frames in the sequence
                    if self._nack_outstanding is None and len(self._stashed_rx_dict) > 0:
                        # We can send a NACK to ask for those too, starting with the earliest sequence number
                        earliest_seq = sorted(self._stashed_rx_dict.keys())[0]
                        # Check it's within the window size from us
                        if (earliest_seq - self._rn) & 0xff < self.rx_window_size:
                            self._nack_outstanding = earliest_seq
                            self._send_nack(earliest_seq)
                        else:
                            # Something has gone wrong here: stale stuff is hanging around, give up and reset
                            min_logger.error("Stale frames in the stashed area; resetting")
                            self._nack_outstanding = None
                            self._stashed_rx_dict = {}
                            self._send_ack()
                    else:
                        self._send_ack()
                    min_logger.debug("Sending ACK for min ID={} with self._rn={}".format(min_id_control & 0x3f, self._rn))
                else:
                    # If the frames come within the window size in the future sequence range then we accept them and assume some were missing
                    # (They may also be duplicates, in which case we store them over the top of the old ones)
                    if (min_seq - self._rn) & 0xff < self.rx_window_size:
                        # We want to only NACK a range of frames once, not each time otherwise we will overload with retransmissions
                        if self._nack_outstanding is None:
                            # If we are missing specific frames then send a NACK to specifically request them
                            min_logger.debug("Sending NACK for min ID={} with seq={} to={}".format(min_id_control & 0x3f, self._rn, min_seq))
                            self._send_nack(min_seq)
                            self._nack_outstanding = min_seq
                        else:
                            min_logger.debug("(Outstanding NACK)")
                        # Hang on to this frame because we will join it up later with the missing ones that are re-sent
                        self._stashed_rx_dict[min_seq] = min_frame
                        min_logger.debug("MIN application frame stashed @{} (min_id={}, seq={})".format(time(), min_id_control & 0x3f, min_seq))
                    else:
                        min_logger.warning("Frame stale? Discarding @{} (min_id={}, seq={})".format(time(), min_id_control & 0x3f, min_seq))
                        if min_seq in self._stashed_rx_dict and min_payload != self._stashed_rx_dict[min_seq].payload:
                            min_logger.error("Inconsistency between frame contents")
                        # Out of range (may be an old retransmit duplicate that we don't want) - throw it away
        else:
            min_frame = MINFrame(min_id=min_id_control, payload=min_payload, seq=0, transport=False)
            self.processFrame(min_frame)

    def _rx_bytes(self, data: bytes):
        """
        Called by handler to pass over a sequence of bytes
        :param data:
        """
        min_logger.debug("Received bytes: {}".format(bytes_to_hexstr(data)))
        for byte in data:
            if self._rx_header_bytes_seen == 2:
                self._rx_header_bytes_seen = 0
                if byte == self.HEADER_BYTE:
                    self._rx_frame_state = self.RECEIVING_ID_CONTROL
                    continue
                if byte == self.STUFF_BYTE:
                    # Discard this byte; carry on receiving the next character
                    continue
                # By here something must have gone wrong, give up on this frame and look for new header
                self._rx_frame_state = self.SEARCHING_FOR_SOF
                continue
            if byte == self.HEADER_BYTE:
                self._rx_header_bytes_seen += 1
            else:
                self._rx_header_bytes_seen = 0
            if self._rx_frame_state == self.SEARCHING_FOR_SOF:
                pass
            elif self._rx_frame_state == self.RECEIVING_ID_CONTROL:
                self._rx_frame_id_control = byte
                if self._rx_frame_id_control & 0x80:
                    self._rx_frame_state = self.RECEIVING_SEQ
                else:
                    self._rx_frame_state = self.RECEIVING_LENGTH
            elif self._rx_frame_state == self.RECEIVING_SEQ:
                self._rx_frame_seq = byte
                self._rx_frame_state = self.RECEIVING_LENGTH
            elif self._rx_frame_state == self.RECEIVING_LENGTH:
                self._rx_frame_length = byte
                self._rx_control = byte
                self._rx_frame_buf = bytearray()
                if self._rx_frame_length > 0:
                    self._rx_frame_state = self.RECEIVING_PAYLOAD
                else:
                    self._rx_frame_state = self.RECEIVING_CHECKSUM_3
            elif self._rx_frame_state == self.RECEIVING_PAYLOAD:
                self._rx_frame_buf.append(byte)
                self._rx_frame_length -= 1
                if self._rx_frame_length == 0:
                    self._rx_frame_state = self.RECEIVING_CHECKSUM_3
            elif self._rx_frame_state == self.RECEIVING_CHECKSUM_3:
                self._rx_frame_checksum = byte << 24
                self._rx_frame_state = self.RECEIVING_CHECKSUM_2
            elif self._rx_frame_state == self.RECEIVING_CHECKSUM_2:
                self._rx_frame_checksum |= byte << 16
                self._rx_frame_state = self.RECEIVING_CHECKSUM_1
            elif self._rx_frame_state == self.RECEIVING_CHECKSUM_1:
                self._rx_frame_checksum |= byte << 8
                self._rx_frame_state = self.RECEIVING_CHECKSUM_0
            elif self._rx_frame_state == self.RECEIVING_CHECKSUM_0:
                self._rx_frame_checksum |= byte
                if self._rx_frame_id_control & 0x80:
                    computed_checksum = crc32(bytearray([self._rx_frame_id_control, self._rx_frame_seq, self._rx_control]) + self._rx_frame_buf, 0)
                else:
                    computed_checksum = crc32(bytearray([self._rx_frame_id_control, self._rx_control]) + self._rx_frame_buf, 0)

                if self._rx_frame_checksum != computed_checksum:
                    min_logger.warning("CRC mismatch (0x{:08x} vs 0x{:08x}), frame dropped".format(self._rx_frame_checksum, computed_checksum))
                    # Frame fails checksum, is dropped
                    self._rx_frame_state = self.SEARCHING_FOR_SOF
                else:
                    # Checksum passes, wait for EOF
                    self._rx_frame_state = self.RECEIVING_EOF
            elif self._rx_frame_state == self.RECEIVING_EOF:
                if byte == self.EOF_BYTE:
                    # Frame received OK, pass up frame for handling")
                    self._min_frame_received(min_id_control=self._rx_frame_id_control,
                                             min_payload=bytes(self._rx_frame_buf), min_seq=self._rx_frame_seq)
                else:
                    min_logger.warning("No EOF received, dropping frame")
                # Look for next frame
                self._rx_frame_state = self.SEARCHING_FOR_SOF
            else:
                min_logger.error("Unexpected state, state machine reset")
                # Should never get here but in case we do just reset
                self._rx_frame_state = self.SEARCHING_FOR_SOF

    def _on_wire_bytes(self, frame: MINFrame) -> bytes:
        """ Get the on-wire byte sequence for the frame, including stuff bytes after every 0xaa 0xaa pair """
        if frame.is_transport:
            prolog = bytes([frame.min_id | 0x80, frame.seq, len(frame.payload)]) + frame.payload
        else:
            prolog = bytes([frame.min_id, len(frame.payload)]) + frame.payload
        raw = prolog + int32_to_bytes(crc32(prolog, 0))
        stuffed = bytearray([self.HEADER_BYTE, self.HEADER_BYTE, self.HEADER_BYTE])
        count = 0
        for i in raw:
            stuffed.append(i)
            if i == self.HEADER_BYTE:
                count += 1
                if count == 2:
                    stuffed.append(self.STUFF_BYTE)
                    count = 0
            else:
                count = 0
        stuffed.append(self.EOF_BYTE)
        return bytes(stuffed)

    def _find_oldest_frame(self):
        if len(self._transport_fifo) == 0:
            raise AssertionError
        window_size = (self._sn_max - self._sn_min) & 0xff
        oldest_frame = self._transport_fifo[0]  # type: MINFrame
        longest_elapsed_time = (now_ms() - oldest_frame.last_sent_time)
        for i in range(window_size):
            elapsed = now_ms() - self._transport_fifo[i].last_sent_time
            if elapsed >= longest_elapsed_time:
                oldest_frame = self._transport_fifo[i]
                longest_elapsed_time = elapsed
        return oldest_frame

    def poll(self):
        """
        Polls the serial line, runs through MIN, sends ACKs, handles retransmits where ACK has gone missing.
        add frames array of accepted MIN frames
        """
        data = self.object['hw'].read_all()
        if data:
            self._rx_bytes(data=data)
        window_size = (self._sn_max - self._sn_min) & 0xff
        if window_size < self.max_window_size and len(self._transport_fifo) > window_size:
            # Frames still to send
            frame = self._transport_fifo[window_size]
            frame.seq = self._sn_max
            frame.last_sent_time = now_ms()
            min_logger.debug("Sending new frame id={} seq={} len={} payload={}".format(
                frame.min_id, frame.seq, len(frame.payload), bytes_to_hexstr(frame.payload)))
            self._transport_fifo_send(frame=frame)
            self._sn_max = (self._sn_max + 1) & 0xff
        else:
            # Maybe retransmits
            if window_size > 0:
                oldest_frame = self._find_oldest_frame()
                if now_ms() - oldest_frame.last_sent_time > self.frame_retransmit_timeout_ms:
                    min_logger.debug("Resending old frame id={} seq={}".format(oldest_frame.min_id, oldest_frame.seq))
                    self._transport_fifo_send(frame=oldest_frame)
        # Periodically transmit ACK
        if now_ms() - self._last_sent_ack_time_ms > self.ack_retransmit_timeout_ms:
            #min_logger.debug("Periodic send of ACK")
            self._send_ack()

        if (self._sn_max - self._sn_max) & 0xff > window_size:
            raise AssertionError
