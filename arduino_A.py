#!/usr/bin/env python3
from optparse import OptionParser

from daemon import SimpleFactory, SimpleProtocol, catch
from min_daemon import MINProtocol


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes.
    
    @catch
    def processMessage(self, string):
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        Sstring = (string.strip('\n')).split(';')
        for sstring in Sstring:
            sstring = sstring.lower()
            while True:
                # managment commands
                if sstring == 'get_status':
                    self.message(
                        'status hw_connected={hw_connected}'.format(**self.object))
                    break
                if not obj['hw_connected']:
                    break
                queue_frame = obj['hw'].protocol.queue_frame
                if sstring == 'testcomm':
                    payload = bytes("hello world {}".format(time()), encoding='ascii')
                    queue_frame(1, payload)
                    break
                break
   
class ArduinoMINProtocol(MINProtocol):
    @catch
    def __init__(self, devname, obj, debug=False):
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source"
        self.status_commands = []  # commands send when device not busy to keep tabs on the state
        super().__init__(devname=devname, obj=obj, refresh=1, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=400, debug=debug)
        
    @catch
    def connectionMade(self):
        self.commands = []
        super().connectionMade()
        self.object['hw_connected'] = 1

    @catch
    def connectionLost(self, reason):
        super().connectionLost(reason)
        self.object['hw_connected'] = 0
        self.commands = []

    @catch
    def processBinary(self, bstring):
        # Process the device reply
        self._bs = bstring
        if self._debug:
            print("hw bb > %s" % self._bs)
        
    @catch
    def update(self):
        if self._debug:
            print ('updater')


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-d', '--device', help='the device to connect to.',  action='store', dest='devname', type='str', default='/dev/ttyUSB0')
    parser.add_option('-p', '--port', help='Daemon port', action='store', dest='port', type='int', default=7030)
    parser.add_option('-n', '--name', help='Daemon name', action='store', dest='name', default='arduino1')
    parser.add_option("-D", '--debug', help='Debug mode', action="store_true", dest="debug")

    (options, args) = parser.parse_args()

    # Object holding actual state and work logic.
    # May be anything that will be passed by reference - list, dict, object etc
    obj = {'hw_connected': 0,}
    
    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    obj['daemon'] = daemon

    proto = ArduinoMINProtocol(devname=options.devname, obj=obj, debug=options.debug)

    if options.debug:
        daemon._protocol._debug = True

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
