# coding=UTF-8

import sys
import glob
import serial
import time

class RS232:
    def __init__(self, port, baudrate):
        self.Baudrates = ["115200", "38400"]
        self.Port = port
        self.Baudrate = baudrate
        self.Serial = serial.Serial()
        self.dataBuffer = ""

    def connect(self):
        self.Serial = serial.Serial(port=self.Port, baudrate=self.Baudrate,timeout=0.2)
        if not self.Serial.isOpen:
            self.Serial.open()

    def isConnect(self):
        return self.Serial.isOpen()

    def serWrite(self, cmd):
        self.Serial.write(cmd)

    def serRead(self):
        try:
            data = self.Serial.read(4096)
            return data
        except Exception as err:
            print ("GetReceiveDataError: {0}".format(err))
    
    def serInWaiting(self):
        return self.Serial.inWaiting()

    def sendCmd(self, cmd):
        try:
            data = self.Serial.read(4096)
            if data == "":
                self.Serial.write(cmd)
            return data
        except Exception as err:
            print ("GetReceiveDataError: {0}".format(err))
    
    def clear(self):
        self.Serial.reset_input_buffer()
        self.Serial.reset_output_buffer()

    def disConnect(self):
        self.Serial.close()

    def getBaudRate(self):
        return self.Baudrate

    def getBaudRates(self):
        return self.Baudrates

    # ShowSerialPortsList(For Test)
    def getSerialPorts(self):
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
            """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
            except (IOError, serial.SerialException):
                pass

        return result
    
"""
import ReaderModule
reader = ReaderModule.ReaderModule()
rs232 = RS232('/dev/ttyUSB0', 115200)
rs232.connect()

while True: 
    rs232.serWrite(reader.getFirmwareVersion())
    time.sleep(1)
    data = rs232.serRead()
    msgTranArr = reader.analyzeDataAll(data)
    for msgTran in msgTranArr:
        for d in msgTran.databarr:
            print (d)
"""
        
    


