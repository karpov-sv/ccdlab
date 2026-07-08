#!/usr/bin/env python3
"""
Allows for communication with GMH 3200 series thermometers and possibly other easyBus instruments.
Sensor value decoding inspired by https://github.com/rgieseke/pyEasybus/tree/main.
@author: Tomas Havel
@contact: haveltom@pm.me
"""
import os
import sys
import re
import numpy as np
import struct
import logging

from daemon import SimpleFactory, SerialUSBProtocol, SimpleProtocol
from command import Command
from daemon import catch

logger = logging.getLogger(__name__)


class DaemonProtocol(SimpleProtocol):
    _debug = False  # Display all traffic for debug purposes
    _simulator = False

    @catch
    def processMessage(self, string):
        # It will handle some generic messages and return pre-parsed Command object
        cmd = SimpleProtocol.processMessage(self, string)
        if cmd is None:
            return

        hw = obj["hw"]
        if cmd.name == "get_status":
            msg = f'status hw_connected={self.object["hw_connected"]} status={self.object["status"]}'
            for i in range(self.object["n_channels"]):
                msg += f' temperature{i}={self.object[f"temperature{i}"]}'
            self.message(msg)


class GMHException(Exception):
    pass


class GMHProtocol(SerialUSBProtocol):
    _binary_length = 9
    ERROR_CODES = {
        16352: "Measuring range overrun",
        16353: "Measuring range underrun",
        16362: "Calculation not possible",
        16363: "System error",
        16364: "Battery empty",
        16365: "Sensor defective",
    }

    @catch
    def __init__(self, serial_num, obj, debug=False):
        self.commands = (
            []
        )  # Queue of command sent to the device which will provide replies, each entry is a dict with keys "cmd","source"
        self.name = "hw"
        self.type = "hw"
        self.n_channels = obj["n_channels"]
        self.status_commands = [
            (254 - x).to_bytes() + b"\x00" + self.crc(254 - x, 0).to_bytes()
            for x in range(self.n_channels)
        ]
        super().__init__(
            obj=obj,
            serial_num=serial_num,
            refresh=1,
            baudrate=4800,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=400,
            debug=debug,
        )

    @catch
    def temp_decode(self, response: bytes) -> float:
        b3, b4, b6, b7 = struct.unpack_from(">BBxBBx", response, 3)

        high_word = ((~b3 & 0xFF) << 8) | b4
        low_word = ((~b6 & 0xFF) << 8) | b7

        u32 = (high_word << 16) | low_word

        exponent = ((~b3 & 0xFF) >> 3) - 15

        payload = u32 & 0x07FFFFFF

        if payload >= 125554432:
            error_code = payload - 0x02000000 - 100000000
            msg = self.ERROR_CODES.get(error_code, "Unknown hardware error")
            self.object["status"] = msg
            raise GMHException(msg)

        if payload & 0x04000000:
            payload -= 0x08000000

        value = (payload + 0x02000000) / (10**exponent)
        return value

    @catch
    def crc(self, byte1: int, byte2: int) -> int:
        ui_hilf = (byte1 << 8) + byte2

        for _ in range(16):
            if ui_hilf & 0x8000:
                ui_hilf = ((ui_hilf << 1) ^ 0x700) & 0xFFFF
            else:
                ui_hilf = (ui_hilf << 1) & 0xFFFF

        return (~(ui_hilf >> 8)) & 0xFF

    @catch
    def connectionMade(self):
        self.commands = []
        super().connectionMade()
        self.object["hw_connected"] = 1
        self.object["status"] = "ok"

    @catch
    def connectionLost(self, reason):
        super().connectionLost(self, reason)
        self.object["hw_connected"] = 0
        self.object["status"] = "----"
        for i in range(self.object["n_channels"]):
            self.object[f"temperature{i}"] = "nan"

    @catch
    def processMessage(self, string):
        logger.debug(f"hw cc > {string}")
        self.commands.pop(0)

    @catch
    def update(self):
        logger.debug(
            "----------------------- command queue ----------------------------"
        )
        for k in self.commands:
            logger.debug(f"{k["cmd"]}, {k["source"]}, {k["status"]}")
        logger.debug(
            "===================== command queue end =========================="
        )

        if len(self.commands) and obj["hw_connected"]:
            self.message(self.commands[0]["cmd"])
        else:
            for k in self.status_commands:
                self.commands.append({"cmd": k, "source": "itself", "status": "status"})

    def processBinary(self, bstring):
        # Process the device reply
        self._bs = bstring
        logger.debug(f"hw bb > {self._bs}")
        ch = 254 - self._bs[0] 
        if ch < self.n_channels:
            result = self.temp_decode(self._bs)
            logger.debug(f"{ch=} {result=}")
            self.object[f"temperature{ch}"] = result
            self.object["status"] = "ok"
        self.commands.pop(0)

if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(usage="usage: %prog [options] arg")

    parser.add_option(
        "-s",
        "--serial-num",
        help="Serial number of the device to connect to.",
        action="store",
        dest="serial_num",
        type="str",
        default="A50285BI",
    )
    parser.add_option(
        "-p",
        "--port",
        help="Daemon port",
        action="store",
        dest="port",
        type="int",
        default=7040,
    )
    parser.add_option(
        "-n",
        "--name",
        help="Daemon name",
        action="store",
        dest="name",
        default="gmh3200",
    )
    parser.add_option(
        "-D", "--debug", help="Debug mode", action="store_true", dest="debug"
    )
    parser.add_option(
        "-S",
        "--simulator",
        help="Simulator mode",
        action="store_true",
        dest="simulator",
    )
    parser.add_option(
        "-c",
        "--channels",
        help="Number of channels of connected device",
        action="store",
        dest="n_channels",
        type="int",
        default=2,
    )

    (options, args) = parser.parse_args()

    obj = {"hw_connected": 0, "status": "----"}
    for i in range(options.n_channels):
        obj[f"temperature{i}"] = 0
    obj["n_channels"] = options.n_channels

    daemon = SimpleFactory(DaemonProtocol, obj)
    daemon.name = options.name
    obj["daemon"] = daemon

    proto = GMHProtocol(
        serial_num=options.serial_num,
        obj=obj,
        debug=options.debug,
    )
    obj["hw"] = proto
    if options.debug:
        daemon._protocol._debug = True
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if options.simulator:
        daemon._protocol._simulator = True

    # Incoming connections
    daemon.listen(options.port)

    daemon._reactor.run()
