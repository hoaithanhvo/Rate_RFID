# coding=UTF-8
import SocketModule
import MessageTran
import random

class ReaderModule:
    def __init__(self):
        
        self.btAryBuffer = bytearray()
        
        self.readId = 0x01

        self.baudrate_38400 = 0x03
        self.baudrate_115200 = 0x04

        self.working_antenna1 = 0x00
        self.working_antenna2 = 0x01
        self.working_antenna3 = 0x02
        self.working_antenna4 = 0x03

        self.region_FCC = 0x01
        self.region_ETSI = 0x02
        self.region_CHN = 0x03

        self.cmd_reset = 0x70

        self.cmd_setUartBaudrate = 0x71
        self.cmd_getFirmwareVersion = 0x72

        self.cmd_setReaderAddress = 0x73

        self.cmd_setWorkingAntenna = 0x74
        self.cmd_getWorkingAntenna = 0x75

        self.cmd_setOutputPower = 0x76
        self.cmd_getOutputPower = 0x77

        self.cmd_setFrequencyRegion = 0x78
        self.cmd_getFrequencyRegion = 0x79
        self.frequencyFCC = 0x01
        self.frequencyETSI = 0x02
        self.frequencyCHN = 0x03

        self.cmd_setBeeperMode = 0x7A

        self.cmd_getReaderTemperature = 0x7B

        self.cmd_readGpioValue = 0x60
        self.cmd_writeGpioValue = 0x61

        self.cmd_setAntennaConnectionDetector = 0x62
        self.cmd_getAntennaConnectionDetector = 0x63

        self.cmd_setTemporaryOutputPower = 0x66

        self.cmd_setReaderId = 0x67
        self.cmd_getReaderId = 0x68

        self.cmd_setRfLinkProfile = 0x69
        self.cmd_getRfLinkProfile = 0x6A

        self.cmd_getRfPortReturnLoss = 0x7E

        self.realtimeInventoryRepeat = 0xFF
        self.cmd_read = 0x81
        self.cmd_write = 0x82
        self.cmd_read_type_default = 0x01
        self.cmd_read_type_epc = 0x01
        self.cmd_read_type_tid = 0x02
        self.cmd_read_type_user = 0x03
        self.cmd_realtimeInventory = 0x89
        self.cmd_customizedSessionTargetInventory = 0x8B
        self.cmd_tag_select = 0x98

        self.cmd_reset_inventory_buffer = 0x93



    """
    reader reset
    """
    def readerReset(self):
        return self.getCmd(self.cmd_reset)

    """
    mode: self.baudrate_38400 or self.baudrate_115200
    """
    def setUartBaudrate(self, mode):
        databarr = bytearray()
        databarr.append(mode)
        return self.getCmdWithData(self.cmd_setUartBaudrate, databarr)

    """
    Get Firmware Version
    """
    def getFirmwareVersion(self):
        return self.getCmd(self.cmd_getFirmwareVersion)

    """
    Set Reader Address
    """
    def setReaderAddress(self, databarr):
        return self.getCmdWithData(self.setReaderAddress(), databarr)

    """
    antenna: self.working_antenna1 or self.working_antenna2
            or self.working_antenna3 or self.working_antenna4
    """
    def setWorkingAntenna(self, antenna):
        databarr = bytearray()
        databarr.append(antenna)
        return self.getCmdWithData(self.cmd_setWorkingAntenna, databarr)

    def getWorkingAntenna(self):
        return self.getCmd(self.cmd_getWorkingAntenna)

    """
    power: 0 to 33
    """
    def setOutputPower(self, powerList):
        databarr = bytearray()
        for power in powerList:
            databarr.append(power)
        return self.getCmdWithData(self.cmd_setOutputPower, databarr)
    
    """
    power: 0 to 33
    """
    def setTemporaryOutputPower(self, power):
        databarr = bytearray()
        databarr.append(power)
        return self.getCmdWithData(self.cmd_setTemporaryOutputPower, databarr)

    def getOutputPower(self):
        return self.getCmd(self.cmd_getOutputPower)

    """
    region: FCC, ETSI, CHN
    start: startFrequency
    end: endFrequency
    """
    def setFrequencyRegion(self, region, start, end):
        databarr = bytearray()
        databarr.append(region)
        databarr.append(start)
        databarr.append(end)
        return self.getCmdWithData(self.cmd_setFrequencyRegion, databarr)

    """
    By Country
    """
    def setFrequencyRegionByCountry(self, country):
        if country == "VN (918.9 - 922.9)":
            region = self.frequencyFCC
            start = 0x29
            end = 0x30
        else:
            return False

        return self.setFrequencyRegion(region, start, end)

    def getFrequencyRegion(self):
        return self.getCmd(self.cmd_getFrequencyRegion)

    """
    set, get
    identifier: 12bytes(hex string)
    """
    def setReaderId(self, hexId):
        hex_data = str(hexId).decode('hex')
        databarr = bytearray(hex_data)
        return self.getCmdWithData(self.cmd_setReaderId, databarr)

    def getReaderId(self):
        return  self.getCmd(self.cmd_getReaderId)

    """
    Customized Session Target Inventory
    repeat:0x00(default)
    """
    def customizeSessionTargetInventory(self, session, target, repeat):
        databarr = bytearray()
        databarr.append(session)
        databarr.append(target)
        databarr.append(repeat)
        return self.getCmdWithData(self.cmd_customizedSessionTargetInventory, databarr)

    """
    Read tag
    MemBank:Reserved(default):0x00, EPC:0x01, TID:0x02, USER:0x03
    WordAdd:0x00
    WordCount:0x00
    """
    def readTag(self, memBank, wordAdd, wordCnt):
        databarr = bytearray()
        databarr.append(memBank)
        databarr.append(wordAdd)
        databarr.append(wordCnt)
        return self.getCmdWithData(self.cmd_read, databarr)
    
    """
    Read tag both Reserved, Tid and User
    ResAdd: 0x00
    ResLen: 0x00
    TidAdd: 0x00
    TidLen: 0x00
    UserAdd: 0x00
    UserLen: 0x00
    readMode: 0x00(One tag, fastest), 0x01(One Tag with Session), 0x02(Multi tags with session)
    """
    def readMutiTag(self, resAdd, resLen, tidAdd, tidLen, userAdd, userLen, session, target, readMode, timeout):
        databarr = bytearray()
        databarr.append(resAdd)
        databarr.append(resLen)    
        databarr.append(tidAdd)
        databarr.append(tidLen)
        databarr.append(userAdd)
        databarr.append(userLen)
        databarr.append(0x00)
        databarr.append(0x00)
        databarr.append(0x00)
        databarr.append(0x00)
        databarr.append(session)
        databarr.append(target)
        databarr.append(readMode)
        databarr.append(timeout)
        return self.getCmdWithData(self.cmd_read, databarr)

    """
    Write Tag
    Password: 
    MemBank:Reserved(default):0x00, EPC:0x01, TID:0x02, USER:0x03
    WordAdd:0x00
    WordCount:0x
    """
    def writeTag(self, password, memBank, wordAdd, wordCnt, btAryData):
        databarr = bytearray()
        for i in range(0, len(password)):
            databarr.append(password[i])
        databarr.append(memBank)
        databarr.append(wordAdd)
        databarr.append(wordCnt)
        for i in range(0, len(btAryData)):
            databarr.append(btAryData[i])
            
        return self.getCmdWithData(self.cmd_write, databarr)


    """
    RealtimeInventory
    repeat:0x00(default)
    """
    def realtimeInventory(self, btrepeat):
        databarr = bytearray()
        databarr.append(btrepeat)
        return self.getCmdWithData(self.cmd_realtimeInventory, databarr)
    """
    EPC Select
    """
    def tagSelect(self, maskNo, target, action, membank, startAddress, maskLen, maskValue):
        databarr = bytearray()
        databarr.append(maskNo)
        databarr.append(target)
        databarr.append(action)
        databarr.append(membank)
        databarr.append(startAddress)
        databarr.append(maskLen)
        
        for val in maskValue:
            databarr.append(val)
        
        databarr.append(0x00)
        
        return self.getCmdWithData(self.cmd_tag_select, databarr)
    
    """
    EPC Select Clear
    """
    def tagSelectClear(self, maskNo):
        databarr = bytearray()
        databarr.append(maskNo)
        return self.getCmdWithData(self.cmd_tag_select, databarr)
    
    
    """
    EPC Select Query
    """
    def tagSelectQuery(self):
        databarr = bytearray()
        databarr.append(0x20)
        
        return self.getCmdWithData(self.cmd_tag_select, databarr)

    """
    Reset Inventory Buffer
    """
    def reset_inventoryBuffer(self):
        return self.getCmd(self.cmd_reset_inventory_buffer)

    """
    private Method
    """
    def getCmd(self, cmd):
        bytearr = bytearray()
        bytearr.append(0xA0)#head
        bytearr.append(0x03)#dataLen
        bytearr.append(self.readId)#readId(Address)
        bytearr.append(cmd)#command
        bytearr.append(self.checksum(bytearr, 0, len(bytearr)))#checksum
        return bytearr

    def getCmdWithData(self, cmd, databarr):
        bytearr = bytearray()
        bytearr.append(0xA0)#head
        dataLen = len(databarr)
        totaldataLen = dataLen + 3
        bytearr.append(totaldataLen)#dataLen
        bytearr.append(self.readId)#readId(Address)
        bytearr.append(cmd)#command
        #data array copy
        for index in range(dataLen):
            bytearr.append(databarr[index])
        bytearr.append(self.checksum(bytearr, 0, len(bytearr)))#command
        return bytearr
    
    """
    Get Reader Temperature
    """
    def getReaderTemperature(self):
        return self.getCmd(self.cmd_getReaderTemperature)

    # def analyzeData(self, databarr):
    #     databarr = bytearray(databarr)
    #     dataLen = len(databarr)
    #     btCk = self.checksum(databarr, 0, dataLen - 1)
    #     # check checksum
    #     if btCk != databarr[dataLen - 1]:
    #         msgTran = MessageTran.Messagetran(0x00, bytearray())
    #         return msgTran
    #     else:
    #         # command
    #         cmd = int(hex(databarr[3]), 16)
    #         # dataarr
    #         bytearr = bytearray()
    #         for index in range(4, dataLen - 1):
    #             bytearr.append(databarr[index])
    #         msgTran = MessageTran.Messagetran(cmd, bytearr)
    #         return msgTran

    def analyzeData(self, databarr):
        databarr = bytearray(databarr)
        databarrList = []
        msgTranList = []
        cmdIndex = [] # Record every 0xA0's location
        i = 0
        
        while i < len(databarr):
            if databarr[i] == 0xA0:
                cmdIndex.append(i)
                try:
                    bLen = databarr[i + 1]
                    i += bLen + 2
                    continue
                except:
                    print ("Pass")
            i += 1

        cmdIndexLen = len(cmdIndex)
        # Check for include more byteArray
        if cmdIndexLen > 1:
            for rCount in range(0, cmdIndexLen - 1):
                if rCount < cmdIndexLen - 1:
                    tempbarr = bytearray(databarr[cmdIndex[rCount]: cmdIndex[rCount + 1]])
                    databarrList.append(tempbarr)
                else:
                    tempbarr = bytearray(databarr[cmdIndex[rCount]:])
                    databarrList.append(tempbarr)
        else:
            databarrList.append(databarr)

        for barr in databarrList:
            try:
                dataLen = len(barr)
                btCk = self.checksum(barr, 0, dataLen - 1)
                # check checksum
                if btCk != barr[dataLen - 1]:
                    
                    msgTran = MessageTran.Messagetran(0x00, bytearray())
                    msgTranList.append(msgTran)
                    
                else:
                    # command
                    cmd = int(hex(barr[3]), 16)
                    # dataarr
                    bytearr = bytearray()
                    for index in range(4, dataLen - 1):
                        bytearr.append(barr[index])
                    msgTran = MessageTran.Messagetran(cmd, bytearr)
                    msgTranList.append(msgTran)
            except Exception as ex:
                print (ex.message)
        return msgTranList
    
    def analyzeDataAll(self, databarr):
        databarr = bytearray(databarr)
        if len(self.btAryBuffer) > 0:
            databarr = self.btAryBuffer + databarr
        self.btAryBuffer = bytearray()
        
        databarrList = []
        msgTranList = []
        cmdIndex = [] # Record every 0xA0's location

        i = 0
        previousI = 0
        while i < len(databarr):
            if databarr[i] == 0xA0:
                cmdIndex.append(i)
                try:
                    previousI = i
                    bLen = databarr[i + 1]
                    i += bLen + 2
                    if i > len(databarr):
                        self.btAryBuffer = databarr[previousI:]
                    continue
                except:
                    pass
                    #print ("Pass")
            i += 1

        cmdIndexLen = len(cmdIndex)
        # Check for include more byteArray
        if cmdIndexLen > 1:
            for rCount in range(0, cmdIndexLen):
                if rCount < cmdIndexLen - 1:
                    tempbarr = bytearray(databarr[cmdIndex[rCount]: cmdIndex[rCount + 1]])
                    databarrList.append(tempbarr)
                else:
                    tempbarr = bytearray(databarr[cmdIndex[rCount]:])
                    databarrList.append(tempbarr)
        else:
            databarrList.append(databarr)

        for barr in databarrList:
            try:
                dataLen = len(barr)
                btCk = self.checksum(barr, 0, dataLen - 1)
                # check checksum
                if btCk != barr[dataLen - 1]:
                    msgTran = MessageTran.Messagetran(0x00, bytearray())
                    msgTranList.append(msgTran)
                    
                else:
                    # command
                    cmd = int(hex(barr[3]), 16)
                    # dataarr
                    bytearr = bytearray()
                    for index in range(4, dataLen - 1):
                        bytearr.append(barr[index])
                    msgTran = MessageTran.Messagetran(cmd, bytearr)
                    msgTranList.append(msgTran)
            except Exception as ex:
                print (ex.message)            
        return msgTranList

    def analyzeInventoryData(self, databarr):
        totalCountExist = False
        onlyTotalCountExist = False
        tagBLen = 0
        databarr = bytearray(databarr)
        dataLen = len(databarr)
        cmdIndex = []
        i = 0
        for d in databarr:
            if d == 0xA0:
                cmdIndex.append(i)
            i += 1
        cmdIndexLen = len(cmdIndex)
        lastIndex = cmdIndex[cmdIndexLen - 1]
        bCount = dataLen - lastIndex
        # Total Count Command is exist
        if bCount == 12:
            totalCountExist = True
            if cmdIndexLen > 2:
                tagBLen = cmdIndex[1] - cmdIndex[0]
            elif cmdIndexLen == 1:
                onlyTotalCountExist = True
            else:
                tagBLen = cmdIndex[0]
        else:
            if len(cmdIndex) > 1:
                tagBLen = cmdIndex[1] - cmdIndex[0]
            else:
                tagBLen = cmdIndex[0]

        if onlyTotalCountExist:
            print ("only exist Total Count Response")
        else:
            if totalCountExist:
                print ("Total Count Response Exist")
            else:
                print ("Only Tag Info Exist")


    def checksum(self, arr, startpos, nlen):
        btsum = 0x00
        for index in range(startpos, nlen):
            btsum += arr[index]
        return ((~btsum) + 1 & 0xFF)

    """
    Analyze by Cmd
    """
    def analyzeDataByCmd(self, cmd, databarr):
        dataLen = len(databarr)
        if cmd == 0x8B:
            if dataLen == 1:
                print ("ErrorCode")
            elif dataLen == 7:
                print ("TotalCount")
            else:
                print ("Normal Case")

        if cmd == 0x69:
            print ("Set Profile")

        if cmd == 0x6A:
            print ("Get Profile")

        if cmd == 0x71:
            print ("Analyze ErrorCode")
            print ("Set Uart Baudrate")

        if cmd == 0x72:
            print ("Get Firmware Version")

    def getItemByRandom(self):
        items = ['Dress Shirt', 'Casual Shirt', 'Polo', 'Sweater', 'Blazer'];
        return items[random.randint(0, 4)];

"""
傳送範例
"""
# s = SocketModule.SocketModule('192.168.0.178', 4001)
# s.connect()
# if s.isconnect:
#     reader = ReaderModule()
#     tempbtarr = reader.setWorkingAntenna(reader.working_antenna3)
#     data = s.sendCmd(tempbtarr)
#     print '=====SetWorkingAntenna====='
#     resdata = reader.analyzeData(data)
#     for d in resdata:
#         print d
#         if d == 16:
#             print "success"
#     tempbtarr_getWA = reader.getWorkingAntenna()
#     data_getWA = s.sendCmd(tempbtarr_getWA)
#     print '=====GetWorkingAntenna====='
#     for d in data_getWA:
#         print format(ord(d))
