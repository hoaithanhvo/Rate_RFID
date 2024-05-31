import datetime
import EncodeTag 

class TagInfo:
    def __init__(self, epc, antenna, rssi, tid="", userMemory=""):
        self.EPC = epc
        self.Rssi = rssi
        self.Antenna = antenna
        self.Tid = tid
        self.UserMemory = userMemory
        

