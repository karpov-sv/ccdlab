#!/usr/bin/env python

# This application is provided as-is as an example of using the Monochromator library
# This sample may be modified and distributed
# Camlin Technologies accepts no liability in using this program
#
# This script requires Python architecture to match the Monochromator library, typically 64 bit.
# It has been tested with
#  - Python 2.7.15 32 bit and Python 3.7.1 64 bit on Windows 10
#  - Python 2.7.15rc1 on Windows subsystem for Linux (WSL - Ubuntu 18.04)
#  - Python 2.7.15rc1 64 bit on kubuntu 18.04 64 bit
#

from __future__ import print_function

import os
import sys
import time
import threading
import platform
import struct
from ctypes import*


def GetPortAndPaths():
    # configure serial port and paths to dll / config depending on the OS

    bits = struct.calcsize("P") * 8
    print("Python: %d.%d.%d %d bit" % (sys.version_info.major, sys.version_info.minor, sys.version_info.micro, bits))
    print("OS: %s %s" % (platform.system(), platform.architecture()[0]))

    # os.chdir("..")
    basedir = os.getcwd()

    calibFilePath = os.path.join(basedir, "Atlas300-00105.cal")

    dllpath = basedir
    if platform.system() == 'Windows':
        dllpath = os.path.join(basedir, "Monochromator.dll")
        dllpath_devel = os.path.join(basedir, "cmake-win/Monochromator/Debug/Monochromator.dll")

        port = "COM11"
    else:
        # Linux
        dllpath = os.path.join("/usr/local/lib/libMonochromator.so")
        dllpath_devel = os.path.join(basedir, "cmake-build/Monochromator/libMonochromator.so")

        port = "/dev/ttyACM0"

    if os.path.isfile(dllpath) == False:
        dllpath = dllpath_devel


    if os.path.isfile(calibFilePath) == False:
        calibFilePath = os.path.join(basedir, "Installer", "Atlas300-00105.cal")

    return port, dllpath, calibFilePath

#def GetPort():
# Prerequisities:
#  - pyserial module for windows
#  - python-serial package for linux
#
#    from serial.tools.list_ports import comports
#    p = ""
#    for port in sorted(comports()):
#        if port.vid == 0x2047 and port.pid == 0x09D1:
#            p = port.device
#
#    if p == "":
#        print("Monochromator USB not found")
#        p = "COM3"
#
#    print(p)
#    return p

class MonoChromator(object):

    def __init__(self, port, path, calfile):
        self.comport = port
        self.calfile = calfile
        print ('Load DLL ' + path)
        self.monodll = cdll.LoadLibrary(path) # loads the monochromator dll
        print('finished')

        self.MAX_NUM_MIRRORS = 2
        self.MAX_NUM_SHUTTERS = 2
        self.MAX_NUM_FILTERWHEELS = 2
        self.MAX_NUM_GRATINGS = 3
        self.MAX_NUM_SLITS = 4

        self.result = 0

    def GetErrorName(self, error_numb):
        self.monodll.StrError.restype = c_char_p
        return self.monodll.StrError(error_numb)

    def connect(self):
        print("Connecting to Mono. Please wait...")
        b_port = self.comport.encode('utf-8')
        b_calibFile = self.calfile.encode('utf-8')
        print("Using port", b_port, "and calibration file", b_calibFile)
        self.result = self.monodll.Connect(b_port, b_calibFile)
        print(self.result, self.GetErrorName(self.result))
        return self.result

    def disconnect(self):
        self.result = self.monodll.Disconnect()
        print(self.GetErrorName(self.result))

    def get_dll_version(self):
        buf = create_string_buffer(10)
        self.result = self.monodll.GetDllVersion(buf, sizeof(buf))
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return buf.value

    def get_serial_number(self):
        buf = create_string_buffer(20)
        self.result = self.monodll.GetSerialNumber(buf, sizeof(buf))
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return buf.value

    def get_firmware_version(self):
        buf = create_string_buffer(20)
        self.result = self.monodll.GetFirmwareVersion(buf, sizeof(buf))
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return buf.value

    def get_model(self):
        buf = create_string_buffer(20)
        self.result = self.monodll.GetModel(buf, sizeof(buf))
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return buf.value

    def get_focal_length(self):
        focal_length = c_int(0);
        self.monodll.GetFocalLength.argtypes = [POINTER(c_int)]
        self.result = self.monodll.GetFocalLength(focal_length)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return focal_length.value

    def get_wavelength(self):
        wavelength = c_float(0);
        self.monodll.GetWavelength.argtypes = [POINTER(c_float)]
        self.result = self.monodll.GetWavelength(wavelength)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return wavelength.value

    def get_max_wavelength(self, num=1):
        wavelength = c_float(0);
        self.monodll.GetMaxWavelength.argtypes = [c_int, POINTER(c_float)]
        self.result = self.monodll.GetMaxWavelength(num, wavelength)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return wavelength.value

    def get_init_wavelength(self, num=1):
        wavelength = c_float(0);
        self.monodll.GetInitWavelength.argtypes = [c_int, POINTER(c_float)]
        self.result = self.monodll.GetInitWavelength(num, wavelength)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return wavelength.value

    def get_number_of_gratings(self):
        number_of_gratings = c_int(0);
        self.monodll.GetNumberOfGratings.argtypes = [POINTER(c_int)]
        self.result = self.monodll.GetNumberOfGratings(number_of_gratings)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return number_of_gratings.value

    def get_current_grating(self):
        current_grating = c_int(0)
        self.monodll.GetCurrentGrating.argtypes = [POINTER(c_int)]
        self.result = self.monodll.GetCurrentGrating(current_grating)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return current_grating.value

    def get_grooves(self, num=1):
        grooves = c_int(0)
        self.monodll.GetGrooves.argtypes = [c_int, POINTER(c_int)]
        self.result = self.monodll.GetGrooves(num, grooves)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return grooves.value

    def get_blaze(self, num=1):
        blaze = c_int(0)
        self.monodll.GetBlaze.argtypes = [c_int, POINTER(c_int)]
        self.result = self.monodll.GetBlaze(num, blaze)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return blaze.value

    def get_max_slit_width(self):
        max_slit_width = c_float(0)
        self.monodll.GetMaxSlitWidthMM.argtypes = [POINTER(c_float)]
        self.result = self.monodll.GetMaxSlitWidthMM(max_slit_width)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return max_slit_width.value

    def get_min_slit_width(self):
        min_slit_width = c_float(0)
        self.monodll.GetMinSlitWidthMM.argtypes = [POINTER(c_float)]
        self.result = self.monodll.GetMinSlitWidthMM(min_slit_width)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return min_slit_width.value

    def get_slit_width(self, num=1):
        slit_width = c_float(0)
        self.monodll.GetSlitWidthMM.argtypes = [c_int, POINTER(c_float)]
        self.result = self.monodll.GetSlitWidthMM(num, slit_width)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return slit_width.value

    def set_slit_width(self, num=1):
        width = self.get_input("Enter slit width (mm): ")
        self.monodll.SetSlitWidthMM.argtypes = [c_int, c_float]
        self.result = self.monodll.SetSlitWidthMM(num, width)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def get_mirror_position(self, num=1):
        mirror_position = c_int(0)
        self.monodll.GetMirrorPosition.argtypes = [c_int, POINTER(c_int)]
        self.result = self.monodll.GetMirrorPosition(num, mirror_position)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return mirror_position.value

    def set_mirror_position(self, num=1, pos=0):
        self.result = self.monodll.SetMirrorPosition(num, pos)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def get_filterwheel_position(self, num=1):
        filterwheel_position = c_int(0)
        self.monodll.GetFilterWheelPosition.argtypes = [c_int, POINTER(c_int)]
        self.result = self.monodll.GetFilterWheelPosition(num, filterwheel_position)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return filterwheel_position.value

    def set_filterwheel_position(self, num=1, pos=1):
        # pos = self.get_input("\nEnter position (1 - 6): ")
        self.result = self.monodll.SetFilterWheelPosition(num, pos)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def initialise_device(self, num=1):
        # num = self.get_input("\nEnter motor number, 1 - 9: ")
        self.result = self.monodll.InitialiseDevice(num)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def move_to_wavelength(self, num=1, wavelength=0):
        self.monodll.MoveToWavelength.argtypes = [c_int, c_float]
        self.result = self.monodll.MoveToWavelength(num, wavelength)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def is_shutter_present(self, num=1):
        present = c_bool(False)
        self.monodll.IsShutterPresent.argtypes = [c_int, POINTER(c_bool)]
        self.result = self.monodll.IsShutterPresent(num, present)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return present.value

    def is_shutter_open(self, num=1):
        shutter_open = c_bool(False)
        self.monodll.IsShutterOpen.argtypes = [c_int, POINTER(c_bool)]
        self.result = self.monodll.IsShutterOpen(num, shutter_open)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return shutter_open.value

    def open_shutter(self, num=1):
        self.result = self.monodll.OpenShutter(num)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def close_shutter(self, num=1):
        self.result = self.monodll.CloseShutter(num)
        if self.result != 0:
            print(self.GetErrorName(self.result))
        return self.result

    def is_filter_wheel_present(self, num):
        present = c_bool(False)
        self.monodll.IsFilterWheelPresent.argtypes = [c_int, POINTER(c_bool)]
        self.result = self.monodll.IsFilterWheelPresent(num, present)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return present.value

    def is_mirror_present(self, num=1):
        present = c_bool(False)
        self.monodll.IsMirrorPresent.argtypes = [c_int, POINTER(c_bool)]
        self.result = self.monodll.IsMirrorPresent(num, present)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return shutter_open.value

    def is_slit_present(self, num=1):
        present = c_bool(False)
        self.monodll.IsSlitPresent.argtypes = [c_int, POINTER(c_bool)]
        self.result = self.monodll.IsSlitPresent(num, present)
        if self.result != 0:
            print(self.GetErrorName(self.result))
            return None
        else:
            return shutter_open.value
