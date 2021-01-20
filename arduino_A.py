#!/usr/bin/env python3
from optparse import OptionParser
from logging import DEBUG, StreamHandler

from daemon import SimpleFactory, SimpleProtocol, catch
from daemon_min import MINProtocol, MINFrame, min_logger


class DaemonProtocol(SimpleProtocol):

    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        Sstring = (string.strip('\n')).split(';')
        for sstring in Sstring:
            sstring = sstring.lower()
            payload = None
            while True:
                # managment commands
                if sstring == 'get_status':
                    self.message(
                        'status hw_connected={hw_connected} temp01={temp01} humd01={humd01} temp02={temp02} humd02={humd02}'.format(**self.object))
                    break
                if not obj['hw_connected']:
                    break
                queue_frame = obj['hwprotocol'].queue_frame
                if sstring == 'reset':
                    obj['hwprotocol'].transport_reset()
                    break
                if sstring == 'testcomm':
                    from time import time
                    payload = bytes("hello world {}".format(time()), encoding='ascii')
                    break
                if sstring in ['get_temp01', 'get_humd01','get_temp02','get_humd02']:
                    payload = bytes(sstring, encoding='ascii')
                    break
                break
            if payload:
                queue_frame(1, payload, source=self.name)


class Arduino_A_Protocol(MINProtocol):
    status_commands = ['get_temp01','get_humd01','get_temp02','get_humd02']

    @catch
    def __init__(self, devname, obj, debug=False):
        super().__init__(devname=devname, obj=obj, refresh=1, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=400, debug=debug)
        min_log_handler = StreamHandler()
        min_logger.addHandler(min_log_handler)
        if debug:
            min_logger.setLevel(level=DEBUG)

    @catch
    def connectionMade(self):
        super().connectionMade()
        self.object['hw_connected'] = 1

    @catch
    def connectionLost(self):
        super().connectionLost()
        self.object['hw_connected'] = 0
        self.object['temp01'] = 'nan'
        self.object['humd01'] = 'nan'
        self.object['temp02'] = 'nan'
        self.object['humd02'] = 'nan'

    @catch
    def processFrame(self, frame: MINFrame):
        # Process the device reply
        min_logger.debug("Received MIN frame, min_id={}, payload={}, seq={}, source={}, tr={}".format(
            frame.min_id, frame.payload, frame.seq, frame.source, frame.is_transport))
        plString = frame.payload.decode('ascii')
        r_str = ''
        while True:
            if plString.startswith('temp01='):
                r_str = plString
                self.object['temp01'] = plString.split('=')[1]
                break
            if plString.startswith('humd01='):
                r_str = plString
                self.object['humd01'] = plString.split('=')[1]
                break
            if plString.startswith('temp02='):
                r_str = plString
                self.object['temp02'] = plString.split('=')[1]
                break
            if plString.startswith('humd02='):
                r_str = plString
                self.object['humd02'] = plString.split('=')[1]
                break
            break
        if frame.source == 'itself':
            return
        if r_str == '':
            daemon.messageAll(plString, frame.source)
        else:
            daemon.messageAll(r_str, frame.source)

    @catch
    def update(self):
        if self.object['hw_connected'] == 0:
            return
        min_logger.debug('updater')
        if (len(self._transport_fifo)==0):
            for ccmd in self.status_commands:
                payload = bytes(ccmd, encoding='ascii')
                self.queue_frame(1, payload, source='itself')
        self.poll()


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-d', '--device', help='the device to connect to.',  action='store', dest='devname', type='str', default='/dev/arduino_A')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7030)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='arduino_A')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0, 'temp01': 'nan', 'humd01': 'nan', 'temp02': 'nan', 'humd02': 'nan'}

    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    obj['daemon'] = daemon

    obj['hwprotocol'] = Arduino_A_Protocol(devname=options.devname, obj=obj, debug=options.debug)

    if options.debug:
        daemon._protocol._debug = True

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()