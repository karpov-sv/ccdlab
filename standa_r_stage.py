#!/usr/bin/env python3
from optparse import OptionParser
from twisted.internet.serialport import SerialPort
from twisted.internet.task import LoopingCall

from daemon import SimpleFactory, SimpleProtocol, catch


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        obj = self.object  # Object holding the state
        hw = obj['hw'].protocol  # HW factory
        Sstring = string.strip()
        string = string.lower()
        while True:
            if string == 'get_status':
                self.message('status hw_connected=%s' % (self.object['hw_connected'],))
                break

            if string == 'gsti':
                hw.message(string, nb=70, source=self.name)
                break

            print('command', string, 'not implemented!')
            break


class StandaRSProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes

    @catch
    def __init__(self):
        SimpleProtocol.__init__(self)
        self.commands = []  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source"
        self.status_commands = []  # commands send when device not busy to keep tabs on the state

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
    def processBinary(self, string):
        # Process the device reply
        if self._debug:
            print("hw cc > %s" % string)
        if len(self.commands):
            if self._debug:
                print("last command which expects reply was:", self.commands[0]['cmd'])
                print("received reply:", string)
            while True:
                if self.commands[0]['cmd'] in self.status_commands:
                    break

                r_str = b''
                if self.commands[0]['cmd'] == 'gsti':
                    r_str += string[4:20].strip(b'\x00')+b' '
                    r_str += string[20:44].strip(b'\x00')
                break
                # not recognized command, just pass the output
            daemon.messageAll(r_str.decode('ascii'), self.commands[0]['source'])
        self.commands.pop(0)

    @catch
    def message(self, string, nb, source='itself'):
        """Sending outgoing message"""
        if self._debug:
            print(">> serial >>", string, 'expecting', nb, 'bytes')

        """
        Send the message to the controller. If keep=True, expect reply (for this device it seems all comands expect reply
        """
        self.commands.append({'cmd': string, 'nb': nb, 'source': source})

    @catch
    def update(self):
        print('update')
        # Request the hardware state from the device
        if len(self.commands):
            print('sending so')
            SimpleProtocol.switchToBinary(self, length=self.commands[0]['nb'])
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
    hw.protocol._comand_end_character = ''  # the device just expects 4 bytes, the it acts

    if options.debug:
        daemon._protocol._debug = True
        hw.protocol._debug = True

    obj['daemon'] = daemon
    obj['hw'] = hw

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
