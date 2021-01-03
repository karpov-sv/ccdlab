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
                queue_frame = obj['hwprotocol'].queue_frame
                if sstring == 'testcomm':
                    from time import time
                    payload = bytes("hello world {}".format(time()), encoding='ascii')
                    queue_frame(1, payload)
                    break
                break
   
class Arduino_A_Protocol(MINProtocol):
    @catch
    def __init__(self, devname, obj, debug=False):
        super().__init__(devname=devname, obj=obj, refresh=1, baudrate=115200, bytesize=8, parity='N', stopbits=1, timeout=400, debug=debug)
        
    @catch
    def connectionMade(self):
        self.object['hw_connected'] = 1

    @catch
    def connectionLost(self):
        self.object['hw_connected'] = 0

    @catch
    def processBinary(self, bstring):
        # Process the device reply
        self._bs = bstring
        if self._debug:
            print("hw bb > %s" % self._bs)
        
    @catch
    def update(self):
        if self.object['hw_connected']==0:
            return
        if self._debug:
            print ('updater')


if __name__ == '__main__':
    parser = OptionParser(usage="usage: %prog [options] arg")
    parser.add_option('-d', '--device', help='the device to connect to.',  action='store', dest='devname', type='str', default='/dev/arduino')
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

    obj['hwprotocol'] = Arduino_A_Protocol(devname=options.devname, obj=obj, debug=options.debug)
    
    if options.debug:
        daemon._protocol._debug = True

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
