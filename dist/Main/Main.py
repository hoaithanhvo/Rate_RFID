# coding=UTF-8

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QHeaderView
from ctypes import *
import os
import sys
import time
import datetime
import logging
import logging.config
from logging.handlers import RotatingFileHandler
from configparser import ConfigParser
import decimal
import threading
from queue import Queue

from ui_GUI import Ui_MainWindow

import SocketModule
import SerialportModule
import ReaderModule
import SuperIOModule
import EncodeTag
import RecordModule
import Database

def trap_exc_during_debug(*args):
    # when app raises uncaught exception, print info
    print (args)

# install exception hook: without this, uncaught exception would cause application to exit
sys.excepthook = trap_exc_during_debug

class Worker(QtCore.QThread):

    inventorySignal = QtCore.pyqtSignal()

    def __init__(self, gpio):
        QtCore.QThread.__init__(self)
        self.gpio = gpio

    @QtCore.pyqtSlot()
    def monitor(self):
        try:
            while True:
                self.gpio.detect_sensor()
                if self.gpio.inventory_check():
                    self.inventorySignal.emit()
                time.sleep(0.05)
                app.processEvents()
        except Exception as ex:
            print ('Monitor exception: '.format(ex))
            print (sys.exc_info())

class MainWindow(QMainWindow, Ui_MainWindow):

    monitorSignal = QtCore.pyqtSignal()
    inventorySingal = QtCore.pyqtSignal(dict)
    readAsciiSingal = QtCore.pyqtSignal(str)

    def __init__(self, gpio, parent=None):
        
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        sys.setrecursionlimit(10000000)

        print ("Program start initialize...")
        self.lbAppStatus.setText("Program start initialize...")
        self.gpio = gpio

        # Create worker object
        self.worker = Worker(self.gpio)
        
        # Connect worker thread to inventory_data
        self.worker.inventorySignal.connect(self.processUI)
        
        # Connect main thread to worker monitor
        self.monitorSignal.connect(self.worker.monitor)
        
        self.worker.start()
        #self.monitorSignal.emit()
        
        self.inventorySingal.connect(self.inventoryUI)
        self.readAsciiSingal.connect(self.readAsciiUI)

        # logging setting
        logging.config.fileConfig('logging.conf')
        self.logger = logging.getLogger('root')
        #handler = RotatingFileHandler('reader.log','a',1*1024*1024,1)
        #self.logger.addHandler(handler)
        self.logger.debug("APPLICATION START!")
        
        # Connect Mode
        self.socketMode = 0x01
        self.rs232Mode = 0x02

        # Inventory Mode
        self.InventoryStart = 0x00
        self.InventoryStop = 0x01
        self.blInventory = False

        # Idel Time & Change Antenna
        self.btWorkAntenna = 0
        self.nCommand = 0
        
        # ConfigParser
        self.configManager = ConfigParser()
        self.configManager.read('config.ini')

        # Restore Config
        self.session = 0
        self.target = 0
        self.region = 'VN (918.9 - 922.9)'
        self.cfgIp = self.configManager.get('Network', 'ip')
        self.cfgPort = self.configManager.get('Network', 'port')
        self.cfgRS232Port = self.configManager.get('RS232', 'serialport')
        self.cfgRS232Baudrate = self.configManager.get('RS232', 'baudrate')
        self.readerId = self.configManager.get('Reader', 'id')

        # Tag quantity
        self.quantity = 0
        
        # Connection Mode     
        self.socket = SocketModule.SocketModule(self.cfgIp, int(self.cfgPort))
        self.rs232 = SerialportModule.RS232(self.cfgRS232Port, self.cfgRS232Baudrate)
        self.configMode = self.configManager.get('Mode', 'mode')
        if self.configMode == "1": # Socket Mode
            try:
                self.connection = self.socket
            except Exception as err:
                self.logger.debug(err)
            self.logger.debug("Socket connect status: " + str(self.socket.isConnect()))
        elif self.configMode == "2": # Serial Mode
            try:
                self.connection = self.rs232
            except Exception as err:
                self.logger.debug(err)
            self.logger.debug("RS232 connect status: " + str(self.rs232.isConnect()))
            
        # Current Setting
        self.curRegion = 0
        self.curPower = [0,0,0,0]
        
        self.url = self.configManager.get('Database', 'url')
        self.dbType = ['SQLSERVER', 'MYSQL', 'RESTAPI']
        self.dbDBMS = Database.DBType[self.configManager.get('Database', 'dbms')]
        self.dbIp = self.configManager.get('Database', 'IP')
        self.dbPort = self.configManager.get('Database', 'Port')
        self.dbUser = self.configManager.get('Database', 'User')
        self.dbPass = self.configManager.get('Database', 'Pass')
        self.dbDb = self.configManager.get('Database', 'DB')
        self.dbTable = self.configManager.get('Database', 'Table')
        self.dbStoredCheckLink = self.configManager.get('Database', 'checklink')
        self.dbStoredAssignLocation = self.configManager.get('Database', 'assignlocation')
        self.dbStoredInsertError = self.configManager.get('Database', 'inserterror')
        
        # Database column
        self.epcCol = self.configManager.get('Column', 'EPC')
        self.materialCol = self.configManager.get('Column', 'materialcode')
        self.descCol = self.configManager.get('Column', 'description')
        self.lotCol = self.configManager.get('Column', 'lotnumber')
        self.quantityCol = self.configManager.get('Column', 'quantity')
        self.boxCol = self.configManager.get('Column', 'box')
        self.timeCol = self.configManager.get('Column', 'Time')

        # Recording Option, check is "on" or "off"
        self.recordDb = self.configManager.get('Record', 'db')
        self.recordLocal = self.configManager.get('Record', 'local')
        
        # RF Power
        self.rfPowerList = self.configManager.get('RF', 'dbm').split(',')
        
        # Init UI Status
        self.disable_Connect_Group(True)

        #Antenna
        self.antenna = self.configManager.get('Reader', 'antenna').split(',')

        # set GPIO initial
        self.activeDO = self.configManager.get('DO', 'active')
        self.activeDOList = []
        self.activeDOPortList = []
        if self.activeDO == "on":
            self.channelDO = self.configManager.get('DO', 'channel').split(',')
            # Channel values: 1,2,3,4
        else:
            self.channelDO = []
            self.activeDO = "off"

        self.activeDI = self.configManager.get('DI', 'active')
        self.activeDIList = []
        if self.activeDI == "on":
            self.gpio.isDI = True
            self.channelDI = self.configManager.get('DI', 'channel').split(',')
            for curDI in self.channelDI:
                if curDI == '1':
                    self.activeDIList.append('1')
                if curDI == '2':
                    self.activeDIList.append('2')
                if curDI == '3':
                    self.activeDIList.append('3')
                if curDI == '4':
                    self.activeDIList.append('4')
            self.gpio.DIList = self.activeDIList
        else:
            self.gpio.DIList = []
            self.channelDI = []
            self.gpio.isDI = False

        # Database
        self.db = Database.Database(self.dbDBMS, self.dbIp, self.dbPort, self.dbUser, self.dbPass, self.dbDb)
        
        # Local Recorder to CSV
        self.localRecorder = RecordModule.RecordModule()

        # Reader Moudle
        self.reader = ReaderModule.ReaderModule()                
        
        # Database Column
        if self.epcCol != "":
            self.dbColumn = self.epcCol
        if self.timeCol != "":
            self.dbColumn = self.dbColumn + "," +self.timeCol
        
        print ("Database Setting...OK")
        self.lbAppStatus.setText("Database Setting...OK")

        # tableview
        self.model = QtGui.QStandardItemModel(self.tableView)
        self.model.setColumnCount(7)
        self.model.setHeaderData(0, QtCore.Qt.Horizontal, 'EPC')
        self.model.setHeaderData(1, QtCore.Qt.Horizontal, 'Material Code')
        self.model.setHeaderData(2, QtCore.Qt.Horizontal, 'Description')
        self.model.setHeaderData(3, QtCore.Qt.Horizontal, 'Lot Number')
        self.model.setHeaderData(4, QtCore.Qt.Horizontal, 'Quantity')
        self.model.setHeaderData(5, QtCore.Qt.Horizontal, 'Box')
        self.model.setHeaderData(6, QtCore.Qt.Horizontal, 'Time')
        self.tableView.setModel(self.model)
        header = self.tableView. horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        #tableview_2
        self.model2 = QtGui.QStandardItemModel(self.tableView_2)
        self.model2.setColumnCount(7)
        self.model2.setHeaderData(0, QtCore.Qt.Horizontal, 'EPC')
        self.model2.setHeaderData(1, QtCore.Qt.Horizontal, 'Material Code')
        self.model2.setHeaderData(2, QtCore.Qt.Horizontal, 'Description')
        self.model2.setHeaderData(3, QtCore.Qt.Horizontal, 'Lot Number')
        self.model2.setHeaderData(4, QtCore.Qt.Horizontal, 'Quantity')
        self.model2.setHeaderData(5, QtCore.Qt.Horizontal, 'Box')
        self.model2.setHeaderData(6, QtCore.Qt.Horizontal, 'Time')
        self.tableView_2.setModel(self.model2)
        header2 = self.tableView_2. horizontalHeader()
        header2.setSectionResizeMode(0, QHeaderView.Stretch)
        header2.setSectionResizeMode(1, QHeaderView.Stretch)
        header2.setSectionResizeMode(2, QHeaderView.Stretch)
        header2.setSectionResizeMode(3, QHeaderView.Stretch)
        header2.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header2.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header2.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        self.tags = []
        
        # Inventory Time Consume
        self.passingTime = 0

        # Picture
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(os.getcwd() + "/logo.jpg")
        self.lbLogo.setPixmap(pixmap)
        self.lbLogo.setScaledContents(True)

        # buttons
        self.btnInventoryStart.clicked.connect(self.btn_start_click)
        self.btnInventoryStop.clicked.connect(self.btn_stop_click)
        self.btnInventoryReset.clicked.connect(self.btn_refresh_click)

        # Tag Encode Module
        self.m_oEncodeTag = EncodeTag.EncodeTag('0000000003171327', '01327A01')
        self.epcFormat = self.configManager.get('Tag', 'format')
        self.epcFormat = self.epcFormat.upper() 
        
        #self.queue = Queue()
        self._sentinel = object()
        
        self.inventoryRate = 1 # Use to dynamic control inventory command frequency
        self.blSetPower = False
        self.blSetFrequency = False
        
        
    """
    Close Window
    """
    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure to quit?", QMessageBox.Yes,
                                           QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logger.debug("APPLICATION EXIT!")
            self.btn_stop_click()
            print ("Application exit")
            self.lbAppStatus.setText("Application exit")
            self.socket.disConnect()
            self.rs232.disConnect()
            event.accept()
        else:
            event.ignore()

    """
    Check connect status
    """
    def check_connect(self):
        if self.socket.isConnect() == False and self.rs232.isConnect() == False:
            return False
        else:
            return True

    """
    Realtime Inventory Process
    """
    #@QtCore.pyqtSlot()
    def inventory_data(self):
        self.logger.debug("Start Inventory Data!")
        self.lbAppStatus.setText("Start Inventory Data!")
        self.btn_refresh_click()

        # Check antenna selected and power set
        if not len(self.antenna) > 0:
            print ("Antenna not choosen. Please check config file.")
            self.lbAppStatus.setText("Antenna not choosen. Please check config file.")
            self.btn_stop_click()
            self.blInventory = False
        else:
            self.btWorkAntenna = int(self.antenna[0])
        
        if self.blInventory:
            print (f"Initializing...", end="")
            self.initialize_power()
            self.initialize_region()
            print ("Done")
            self.lbAppStatus.setText("Initializing...Done")
            
            #reader.log set upper limit
            self.readLogReset()
            
            # Initial Setting
            nIndexAntenna = 0
            self.nCommand = 0
            self.session = 0
            self.target = 0
            print ("Start reading...")
            self.lbAppStatus.setText("Start reading...")

        while self.blInventory:  
            # Local and DB Recording Process
            self.gpio.detect_sensor()
            if not self.gpio.inventory_check() or not self.check_connect():
                self.blInventory = False
                self.reset_inventory_buffer()
                self.logger.debug("No Sensor Detect and Start Monitor!")
                self.connection.clear()
            try:
                # Test get reader temperature
                self.connection.serWrite(self.reader.getReaderTemperature())

                # Inventory command
                if nIndexAntenna < len(self.antenna)-1 or self.nCommand == 0:
                    if self.nCommand == 0:
                        self.nCommand = 1
                        self.logger.debug("Send Realtime Inventory Command!")
                        self.connection.serWrite(self.reader.realtimeInventory(self.reader.realtimeInventoryRepeat))
                        #self.connection.serWrite(self.reader.customizeSessionTargetInventory(self.session, self.target, 0x01))
                    else:
                        # Change antenna command
                        self.nCommand = 0
                        nIndexAntenna = nIndexAntenna + 1
                        self.btWorkAntenna = int(self.antenna[nIndexAntenna]) - 1
                        self.connection.serWrite(self.reader.setWorkingAntenna(self.btWorkAntenna))
                else:
                    # Set antenna to 1
                    self.nCommand = 0
                    nIndexAntenna = 0
                    self.btWorkAntenna = int(self.antenna[nIndexAntenna]) - 1
                    self.connection.serWrite(self.reader.setWorkingAntenna(self.btWorkAntenna))
                
                # When Tag Quantity is small, sleep short. When quantity is large, sleep long
                # Dynamic Inventory Time Delay
                time.sleep(self.inventoryRate/100)
                
            except Exception as err:
                self.logger.debug("Error: {0}".format(err))
                
                
    @QtCore.pyqtSlot()            
    def processUI(self):
        while threading.active_count() > 2: time.sleep(0.1)
        
        self.blInventory = True
        inventoryThread = threading.Thread(target=self.inventory_data)
        inventoryThread.start()
        readMsgThread = threading.Thread(target=self.message_receive)
        readMsgThread.start()
        
        while self.blInventory:
            app.processEvents()
            time.sleep(0.05)
        
        inventoryThread.join()
        readMsgThread.join()
        
        # Clean out data in serial port
        while self.connection.serInWaiting():
            self.connection.serRead()
            
        self.monitorSignal.emit()

    """
    Thread receive com or serial data
    """
    def message_receive(self):
        while self.blInventory:
            data = self.connection.serRead()
            if data:
                msgTranArr = self.reader.analyzeDataAll(data)
                self.analyze_data(msgTranArr)

    """
    Analyze Data Process
    """
    def analyze_data(self, msgTranlist):
        for msgTran in msgTranlist:
            if msgTran.cmd == 0x00:
                self.logger.debug("Error: Checksum is not correct!")
                continue
            elif msgTran.cmd == 0x81:
                self.process_read_tag(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x82:
                self.process_write_tag(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x89:
                self.process_realtime_inventory(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x8B:
                try:
                    self.process_realtime_inventory(msgTran.databarr)
                except ex:
                    self.logger.debug(ex)
                continue
            elif msgTran.cmd == 0x66:
                self.process_set_temporary_output_power(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x67:
                self.process_set_reader_id(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x68:
                self.process_get_reader_id(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x71:
                self.process_set_baudrate(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x74:
                self.process_set_work_antenna(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x76:
                self.process_set_output_power(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x77:
                self.process_get_output_power(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x78:
                self.process_set_frequency_region(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x7B:
                self.process_get_reader_temperature(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x93:
                self.process_reset_inventory_buffer(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x98:
                self.process_tag_select(msgTran.databarr)
                continue
            else:
                self.logger.debug("Cannot Recognize")

    """
    Return Data Process
    """
    def process_set_reader_id(self, databarr):
        self.process_error_code(databarr)

    def process_get_reader_id(self, databarr):
        readerIdStr = ""
        for d in databarr:
            readerIdStr += hex(d)[2:].upper() + " "

    def process_set_baudrate(self, databarr):
        if self.process_error_code(databarr):
            self.configManager.set('RS232', 'baudrate', self.cmbSetBauRate.currentText())
            self.configManager.write(open('config.ini', 'wb'))

    def process_set_work_antenna(self, databarr):
        intCurrentAnt = 0
        intCurrentAnt = self.btWorkAntenna + 1
        strCmd = "Successfully set working antenna, current working antenna : Ant {0}".format(str(intCurrentAnt))

        if self.process_error_code(databarr):
            self.logger.debug(strCmd)
        else:
            self.nCommand = 1

    """  
    Initialize Power and Region
    """
    def initialize_power(self):
        if not (self.curPower[0] == int(self.rfPowerList[0]) and
                self.curPower[1] == int(self.rfPowerList[1]) and
                self.curPower[2] == int(self.rfPowerList[2]) and
                self.curPower[3] == int(self.rfPowerList[3])):
            self.curPower = list(map(int, [self.rfPowerList[0], self.rfPowerList[1], self.rfPowerList[2], self.rfPowerList[3]]))
            for i in range(len(self.curPower)-1):
                if self.curPower[i] != self.curPower[i+1]:
                    self.set_output_power(self.curPower)
                    break
                if i == len(self.curPower)-2:
                    self.set_temporary_output_power(self.curPower[0])                      
        
    def initialize_region(self):
        if not self.curRegion == self.region:
            self.curRegion = self.region
            self.set_frequency_region(self.curRegion)
    
    def set_output_power(self, powerList):
        print (f"Set output power Ant1: {powerList[0]}dbm, Ant2: {powerList[1]}dbm, Ant3: {powerList[2]}dbm, Ant4: {powerList[3]}dbm ... ", end="")
        self.blSetPower = False
        while not self.blSetPower:
            self.connection.serWrite(self.reader.setOutputPower(powerList))
            time.sleep(0.2)
        print ("Done")
        self.lbAntennaPower.setText(str(powerList[0]) + " dBm")
        self.logger.debug("Set output power successfully")
        self.lbAppStatus.setText(f"Set output power {powerList[0]} | {powerList[1]} | {powerList[2]} | {powerList[3]} dBm  successfully")
        
    def set_temporary_output_power(self, power):
        print (f"Set Temporary Output Power {int(power)}dbm ... ", end="")
        self.blSetPower = False
        while not self.blSetPower:
            self.connection.serWrite(self.reader.setTemporaryOutputPower(int(power)))
            time.sleep(0.2)
        print ("Done")
        self.lbAntennaPower.setText(str(power) + " dBm")
        self.logger.debug("Set Temporary Output Power successfully")
        self.lbAppStatus.setText(f"Set output power {power} dBm successfully")
        
    def set_frequency_region(self, region):
        print (f"Set Frequency Region {region} ... ", end="")
        self.blSetFrequency = False
        while not self.blSetFrequency:
            self.connection.serWrite(self.reader.setFrequencyRegionByCountry(str(region)))
            time.sleep(0.2)
        print ("Done")
        self.logger.debug("Set frequency region successfully")
        self.lbAppStatus.setText("Set frequency region successfully")

    def process_set_output_power(self, databarr):
        self.blSetPower = self.process_error_code(databarr)

    def process_get_output_power(self, databarr):
        if len(databarr) == 1:
            power = str(databarr[0])
            print ("CurrentOutputPower: " + power)
            return False
        elif len(databarr) == 4:
            for d in databarr:
                print (d)
            return False
        else:
            print ("Error")
    
    def process_set_temporary_output_power(self, databarr):
        self.blSetPower = self.process_error_code(databarr)
            
    def process_set_frequency_region(self, databarr):
        self.blSetFrequency = self.process_error_code(databarr)

    def process_get_reader_temperature(self, databarr):
        for d in databarr:
            if int(d) > 1:
                self.lbReaderTemp.setText(str(d))

    def process_read_tag(self, databarr):
        dataLen = len(databarr)
        try:
            if dataLen == 1:
                self.process_error_code(databarr)
            else:
                # Turn Digital Output on
                for port in self.activeDOPortList:
                    self.gpio.set_gpio(port, self.gpio.on)
                
                """
                N:len(databarr)
                0:2bytes[Tag Count]
                2:DataLen[]
                3~N-4:PC(2),EPC(),CRC(2),ReadData()
                N-3:ReadLen
                N-2:AntId
                N-1:ReadCount
                """
                
                nDataLen = databarr[dataLen - 3]
                nEpcLen = databarr[2] - nDataLen - 4
                # PC
                strPC = ""
                for b in range(3, 5):
                    strPC += str(hex(databarr[b]))[2:].zfill(2) + ' '
                strPC = strPC.upper()
                # EPC
                strEPC = ""
                epcEnd = 5 + nEpcLen
                
                if epcEnd <= dataLen:
                    for b in range(3, epcEnd):
                        nextEPC = str(hex(databarr[b]))[2:].zfill(2)
                        strEPC += nextEPC + ' '
                strEPC = strEPC.upper().replace(' ', '')

                # Show Inventory Result         
                # Antenna
                if (databarr[dataLen-1] & 0x80) == 0:
                    ant = (databarr[dataLen-2] & 0x03) + 1
                else:
                    ant = (databarr[dataLen-2] & 0x03) + 5
                
                if (int(strPC[0:2], 16)/4) <= (epcEnd-4):
                    if str(ant) in self.antenna:
                        dtNow = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f').split(".")[0]
                        tagInfo = {
                            self.epcCol: strEPC,
                            self.materialCol: 'Get from SQL',
                            self.descCol: 'Get from SQL',
                            self.lotCol: 'Get from SQL',
                            self.quantityCol: 'Get from SQL',
                            self.boxCol: 'Get from SQL',
                            self.timeCol: dtNow
                        }
                        self.inventorySingal.emit(tagInfo)
                        time.sleep(0.01)   
                    
        except Exception as e:
            print (e)

    """
    RealTimeInventoryDataAnalyze
    Customized Session Target Inventory Data Analyze
    """
    def process_realtime_inventory(self, databarr):
        dataLen = len(databarr)
        try:
            if dataLen == 1:
                print ("Datalen: 1")
                self.process_error_code(databarr)
            elif dataLen == 7:
                self.logger.debug("Get Total Count Response!")
                nReadRate = databarr[1] * 256 + databarr[2]
                nDataCount = databarr[3] * 256 * 256 * 256 + databarr[4] * 256 * 256 + databarr[5] * 256 + databarr[6]
                self.logger.debug("Tag Count: " + str(nDataCount))
                # TODO: calculate related average value
                self.inventoryRate = (lambda x: x if x>=1 else 1)((self.inventoryRate+nDataCount)/2)
                if self.inventoryRate > 100:
                    self.inventoryRate = 1
                    
            else:
                nEpcLen = dataLen - 2
                rssiLocation = 1 + nEpcLen
                strEPC = ""
                # EPC= PC + EPC, change range to 3, previously 1
                for b in range(1, 1 + nEpcLen):
                    strEPC += str(hex(databarr[b]))[2:].zfill(2) + " "
                strEPC = strEPC.upper().replace(' ', '')
                dRSSI = databarr[rssiLocation] - 129
                self.lbRSSI.setText(str(dRSSI))
                self.logger.debug("Tag: " + strEPC)
                self.lbAppStatus.setText(f"Tag read: {strEPC}")
                
                # Antenna
                if (databarr[rssiLocation] & 0x80) == 0:
                    ant = (databarr[0] & 0x03) + 1
                else:
                    ant = (databarr[0] & 0x03) + 5
                
                if (int(strEPC[0:2], 16)/4) <= (nEpcLen-1):
                    if str(ant) in self.antenna:
                        dtNow = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f').split(".")[0]
                        tagInfo = {
                            self.epcCol: strEPC,
                            self.materialCol: 'Get from SQL',
                            self.descCol: 'Get from SQL',
                            self.lotCol: 'Get from SQL',
                            self.quantityCol: 'Get from SQL',
                            self.boxCol: 'Get from SQL',
                            self.timeCol: dtNow
                        }
                        self.inventorySingal.emit(tagInfo)
                        time.sleep(0.01)

        except Exception as e:
            print (e)

    #TODO: Major function here, change the viewTable in this function to suitable function.
    #      Call Sql Server here when we get the tag EPC, return the sql server result and populate viewTable
    @QtCore.pyqtSlot(dict)        
    def inventoryUI(self, tagDict):

        if self.blInventory:
            # Detect Duplicate
            hasExist = False
            
            readEPC = tagDict[self.epcCol]
            readTime = tagDict[self.timeCol]
            strData = readEPC
            
            i = self.model.rowCount()
            k = self.model2.rowCount()
            if len(self.tags) > 0:
                if (strData) in self.tags:
                    hasExist = True
            
            if not hasExist:
                # Update Tags
                self.tags.append(strData)
                strEpcSQL = readEPC[4:]
                print(f"Tag Read: {strEpcSQL}...", end="")
                
                if self.recordDb == "on":
                    # TODO: use strEPC send to SQL Server to get pallet information
                    result = self.db.select_sqlserver(self.dbStoredCheckLink, strEpcSQL)
                    
                    # Update TableView with all result sets from SQL Server
                    if len(result) > 0 and str(result) != 'NOT FOUND' and str(result) != 'ERROR':
                        j = 0
                        for row in result:
                            #tableview
                            self.model.setItem(i + j, 0, QtGui.QStandardItem(strEpcSQL))
                            self.model.setItem(i + j, 1, QtGui.QStandardItem(str(row['MaterialCode'])))
                            self.model.setItem(i + j, 2, QtGui.QStandardItem(str(row['Description'])))
                            self.model.setItem(i + j, 3, QtGui.QStandardItem(str(row['LotNumber'])))
                            self.model.setItem(i + j, 4, QtGui.QStandardItem(str(row['Quantity'])))
                            self.model.setItem(i + j, 5, QtGui.QStandardItem(str(row['Box'])))
                            self.model.setItem(i + j, 6, QtGui.QStandardItem(readTime))
                            #tableview_2
                            self.model2.setItem(k + j, 0, QtGui.QStandardItem(strEpcSQL))
                            self.model2.setItem(k + j, 1, QtGui.QStandardItem(str(row['MaterialCode'])))
                            self.model2.setItem(k + j, 2, QtGui.QStandardItem(str(row['Description'])))
                            self.model2.setItem(k + j, 3, QtGui.QStandardItem(str(row['LotNumber'])))
                            self.model2.setItem(k + j, 4, QtGui.QStandardItem(str(row['Quantity'])))
                            self.model2.setItem(k + j, 5, QtGui.QStandardItem(str(row['Box'])))
                            self.model2.setItem(k + j, 6, QtGui.QStandardItem(readTime))
                            j += 1
                        #result = self.db.assignlocation_sqlserver(self.dbStoredAssignLocation, strEpcSQL)
                        result = self.db.insert_RestfulApi(self.url, strEpcSQL)
                        print(result)
                        if result == 'Success':
                        # if int(result[0]['Success']) == 1:
                            self.lbGate.setText("PASSED")
                            self.lbGate.setStyleSheet("background-color:rgb(0, 170, 0);")
                            lightThread = threading.Thread(target=self.turnonLight_Green, args=[])
                            lightThread.start()
                            
                            # update Tag Count
                            print("Passed") 
                            self.lbInventoryQuantity.setText(str(self.model.rowCount()).zfill(3))
                            self.lbTime.setText(str(self.passingTime) + " sec.")
                            totalCount = self.quantity + self.model.rowCount()
                            self.lbTotalQuantity.setText(str(totalCount))
                        else:
                            # errmsg = str(result[0]['Error Message'])
                            errmsg = result
                            self.lbGate.setText(errmsg)
                            self.lbGate.setWordWrap(True)
                            
                            # if errmsg == 'Pallet already have location':
                            #     print("Pallet already have location")
                            #     self.lbGate.setStyleSheet("background-color:rgb(0, 170, 0);")
                            #     lightThread = threading.Thread(target=self.turnonLight_Green, args=[])
                            #     lightThread.start()
                            # else:
                            self.lbGate.setStyleSheet("background-color:rgb(255, 0, 0);")
                            lightThread = threading.Thread(target=self.turnonLight_Red, args=[])
                            lightThread.start()
                            
                            # insert error table
                            print("Failed")
                            lists = []
                            lists.append(strEpcSQL)
                            lists.append(errmsg)
                            lists.append("OUT_PRODUCTION")
                            result = self.db.inserterror_sqlserver(self.dbStoredInsertError, lists)
                            if int(result[0]['Success']) == 1:
                                print("Insert Error Success")
                            else:
                                print(result[0]['Error Message'])
                            
                    elif str(result) == 'NOT FOUND':
                        #tableview
                        self.model.setItem(i, 0, QtGui.QStandardItem(strEpcSQL))
                        self.model.setItem(i, 1, QtGui.QStandardItem('NOT FOUND'))
                        self.model.setItem(i, 2, QtGui.QStandardItem('NOT FOUND'))
                        self.model.setItem(i, 3, QtGui.QStandardItem('NOT FOUND'))
                        self.model.setItem(i, 4, QtGui.QStandardItem('NOT FOUND'))
                        self.model.setItem(i, 5, QtGui.QStandardItem('NOT FOUND'))
                        self.model.setItem(i, 6, QtGui.QStandardItem(readTime))
                        #tableview_2
                        self.model2.setItem(k, 0, QtGui.QStandardItem(strEpcSQL))
                        self.model2.setItem(k, 1, QtGui.QStandardItem('NOT FOUND'))
                        self.model2.setItem(k, 2, QtGui.QStandardItem('NOT FOUND'))
                        self.model2.setItem(k, 3, QtGui.QStandardItem('NOT FOUND'))
                        self.model2.setItem(k, 4, QtGui.QStandardItem('NOT FOUND'))
                        self.model2.setItem(k, 5, QtGui.QStandardItem('NOT FOUND'))
                        self.model2.setItem(k, 6, QtGui.QStandardItem(readTime))
                        self.lbGate.setText("NOT FOUND")
                        self.lbGate.setStyleSheet("background-color:rgb(255, 0, 0);")
                        lightThread = threading.Thread(target=self.turnonLight_Red, args=[])
                        lightThread.start()
                        
                        # insert error table
                        print("Failed")
                        lists = []
                        lists.append(strEpcSQL)
                        lists.append("NOT FOUND")
                        lists.append("OUT_PRODUCTION")
                        result = self.db.inserterror_sqlserver(self.dbStoredInsertError, lists)
                        if int(result[0]['Success']) == 1:
                            print("Insert Error Success")
                        else:
                            print(result[0]['Error Message'])
                        
                    else:
                        #tableview
                        self.model.setItem(i, 0, QtGui.QStandardItem(strEpcSQL))
                        self.model.setItem(i, 1, QtGui.QStandardItem('ERROR'))
                        self.model.setItem(i, 2, QtGui.QStandardItem('ERROR'))
                        self.model.setItem(i, 3, QtGui.QStandardItem('ERROR'))
                        self.model.setItem(i, 4, QtGui.QStandardItem('ERROR'))
                        self.model.setItem(i, 5, QtGui.QStandardItem('ERROR'))
                        self.model.setItem(i, 6, QtGui.QStandardItem(readTime))
                        #tableview_2
                        self.model2.setItem(k, 0, QtGui.QStandardItem(strEpcSQL))
                        self.model2.setItem(k, 1, QtGui.QStandardItem('ERROR'))
                        self.model2.setItem(k, 2, QtGui.QStandardItem('ERROR'))
                        self.model2.setItem(k, 3, QtGui.QStandardItem('ERROR'))
                        self.model2.setItem(k, 4, QtGui.QStandardItem('ERROR'))
                        self.model2.setItem(k, 5, QtGui.QStandardItem('ERROR'))
                        self.model2.setItem(k, 6, QtGui.QStandardItem(readTime))
                        self.lbGate.setText("ERROR")
                        self.lbGate.setStyleSheet("background-color:rgb(255, 0, 0);")
                        lightThread = threading.Thread(target=self.turnonLight_Red, args=[])
                        lightThread.start()
                        
                        # insert error table
                        print("Failed")
                        lists = []
                        lists.append(strEpcSQL)
                        lists.append("ERROR")
                        lists.append("OUT_PRODUCTION")
                        result = self.db.inserterror_sqlserver(self.dbStoredInsertError, lists)
                        if int(result[0]['Success']) == 1:
                            print("Insert Error Success")
                        else:
                            print(result[0]['Error Message'])
                        
                else:
                    #tableview
                    self.model.setItem(i, 0, QtGui.QStandardItem(strEpcSQL))
                    self.model.setItem(i, 1, QtGui.QStandardItem('DISABLE'))
                    self.model.setItem(i, 2, QtGui.QStandardItem('DISABLE'))
                    self.model.setItem(i, 3, QtGui.QStandardItem('DISABLE'))
                    self.model.setItem(i, 4, QtGui.QStandardItem('DISABLE'))
                    self.model.setItem(i, 5, QtGui.QStandardItem('DISABLE'))
                    self.model.setItem(i, 6, QtGui.QStandardItem(readTime))
                    #tableview_2
                    self.model2.setItem(k, 0, QtGui.QStandardItem(strEpcSQL))
                    self.model2.setItem(k, 1, QtGui.QStandardItem('DISABLE'))
                    self.model2.setItem(k, 2, QtGui.QStandardItem('DISABLE'))
                    self.model2.setItem(k, 3, QtGui.QStandardItem('DISABLE'))
                    self.model2.setItem(k, 4, QtGui.QStandardItem('DISABLE'))
                    self.model2.setItem(k, 5, QtGui.QStandardItem('DISABLE'))
                    self.model2.setItem(k, 6, QtGui.QStandardItem(readTime))
                    self.lbGate.setText("DISABLE")
                    self.lbGate.setStyleSheet("background-color:rgb(0, 170, 0);")
                    lightThread = threading.Thread(target=self.turnonLight_Green, args=[])
                    lightThread.start()
                    print("Disable")

                #Record
                tagDict[self.epcCol] = strEpcSQL # Change readList's EPC to Decode Data
                #self.queue.put(tagDict)
                
                # Caculate Time Consuming
                firstTimeTag = datetime.datetime.strptime(str(self.model.data(self.model.index(0, 6))), '%Y/%m/%d %H:%M:%S')
                lastTimeTag = datetime.datetime.strptime(str(self.model.data(self.model.index(i, 6))), '%Y/%m/%d %H:%M:%S')
                self.passingTime = round( (lastTimeTag - firstTimeTag).total_seconds(), 3)
                self.tableView.setModel(self.model)
                self.tableView_2.setModel(self.model2)
        
    @QtCore.pyqtSlot(str)        
    def readAsciiUI(self, epc):
        asciiReadLen = int(self.txtEPCasciiRLen.text())
        epcAscii = self.m_oEncodeTag.ToASCII(epc)
        
        # Show On Ascii Page
        print ("Read Tag Successfully, EPC: {0} | Trans Ascii: {1}".format(epc, epcAscii))
        self.logger.debug("EPC: {0} | Trans Ascii: {1}".format(epc, epcAscii))

        self.txtEPCasciiR.setText(epcAscii[0:asciiReadLen])
        app.processEvents()

    """
    ErrorCode Logging
    """
    def process_error_code(self, databarr):
        rtncode = databarr[0]
        if rtncode == 0x10:
            self.logger.debug("Success")
            return True
        else:
            # print "Error"
            # switch Error Code
            if rtncode == 0x11:
                self.logger.debug("Command Fail")
                return False
            elif rtncode == 0x20:
                self.logger.debug("MCU Reset Error")
                return False
            elif rtncode == 0x21:
                self.logger.debug("CW On Error")
                return False
            elif rtncode == 0x22:
                self.logger.debug("Antenna Mission Error")
                return False
            elif rtncode == 0x23:
                self.logger.debug("Write Flash Error")
                return False
            elif rtncode == 0x24:
                self.logger.debug("Read Flash Error")
                return False
            elif rtncode == 0x25:
                self.loggger.debug("Set Output Power Error")
                return False
            elif rtncode == 0x31:
                self.logger.debug("Tag Inventory Error")
                return False
            elif rtncode == 0x32:
                self.logger.debug("Tag Read Error")
                return False
            elif rtncode == 0x33:
                self.logger.debug("Tag Write Error")
                return False
            elif rtncode == 0x34:
                self.logger.debug("Tag Lock Error")
                return False
            elif rtncode == 0x35:
                self.logger.debug("Tag Kill Error")
                return False
            elif rtncode == 0x36:
                self.logger.debug("No Tag Error")
                return False
            elif rtncode == 0x37:
                self.logger.debug("Inventory Ok But Access Fail")
                return False
            elif rtncode == 0x38:
                self.logger.debug("Buffer Is Empty Error")
                return False
            elif rtncode == 0x40:
                self.logger.debug("Access Or Password Error")
                return False
            elif rtncode == 0x41:
                self.logger.debug("Parameter Invalid")
                return False
            elif rtncode == 0x42:
                self.logger.debug("Parameter Invalid WordCnt Too Long")
                return False
            elif rtncode == 0x43:
                self.logger.debug("Parameter Invalid Membank Out Of Range")
                return False
            elif rtncode == 0x44:
                self.logger.debug("Parameter Invalid Lock Region Out Of Range")
                return False
            elif rtncode == 0x45:
                self.logger.debug("Parameter Invalid Lock Action Out Of Range")
                return False
            elif rtncode == 0x46:
                self.logger.debug("Parameter Reader Address Invalid")
                return False
            elif rtncode == 0x47:
                self.logger.debug("Parameter Invalid AntennaId Out Of Range")
                return False
            elif rtncode == 0x48:
                self.logger.debug("Parameter Invalid Output Power Out Of Range")
                return False
            elif rtncode == 0x49:
                self.logger.debug("Parameter Invalid Frequency Region Out Of Range")
                return False
            elif rtncode == 0x4A:
                self.logger.debug("Parameter Invalid Baudrate Out Of Range")
                return False
            elif rtncode == 0x4B:
                self.logger.debug("Parameter Beeper Mode Out Of Range")
                return False
            elif rtncode == 0x4C:
                self.logger.debug("Parameter Epc Match Len Too Long")
                return False
            elif rtncode == 0x4D:
                self.logger.debug("Parameter Epc Match Len Error")
                return False
            elif rtncode == 0x4E:
                self.logger.debug("Parameter Invalid Epc Match Mode")
                return False
            elif rtncode == 0x4F:
                self.logger.debug("Parameter Invalid Frequency Range")
                return False
            elif rtncode == 0x50:
                self.logger.debug("Fail To Get RN16 From Tag")
                return False
            elif rtncode == 0x51:
                self.logger.debug("Parameter Invalid Drm Mode")
                return False
            elif rtncode == 0x52:
                self.logger.debug("Pll Lock Fail")
                return False
            elif rtncode == 0x53:
                self.logger.debug("Rf Chip Fail To Response")
                return False
            elif rtncode == 0x54:
                self.logger.debug("Fail To Achieve Desired Output Power")
                return False
            elif rtncode == 0x55:
                self.logger.debug("Copyright Authentication Fail")
                return False
            elif rtncode == 0x56:
                self.logger.debug("Spectrum Regulation Error")
                return False
            elif rtncode == 0x57:
                self.logger.debug("Output Power Too Low")
                return False
            
    """
    Turn on DO Port, [0] is Green, [1] is Red
    """
    def turnonLight_Green(self):
        self.gpio.set_gpio(self.activeDOPortList[3], self.gpio.on)
        self.gpio.set_gpio(self.activeDOPortList[2], self.gpio.on)
        time.sleep(1)
        self.gpio.set_gpio(self.activeDOPortList[3], self.gpio.off)
        time.sleep(4)
        self.gpio.set_gpio(self.activeDOPortList[2], self.gpio.off)
        
    def turnonLight_Red(self):
        self.gpio.set_gpio(self.activeDOPortList[3], self.gpio.on)
        time.sleep(5)
        self.gpio.set_gpio(self.activeDOPortList[3], self.gpio.off)

    """
    Refresh TableView
    """
    def btn_refresh_click(self):
        self.quantity += self.model.rowCount()
        self.lbInventoryQuantity.setText(str(0).zfill(3))
        self.lbTime.setText("0.0 sec.")
        self.lbGate.setText("WAITING")
        self.lbGate.setStyleSheet("background-color:rgb(0, 170, 0);")
        self.model.removeRows(0, self.model.rowCount())
        self.tableView.setModel(self.model)
        self.tableView_2.setModel(self.model2)
        self.tags[:] = []
        
    """
    Btn Start Inventory
    """
    def btn_start_click(self):
        self.gpio.btn_start_click()
        self.btnInventoryStart.setDisabled(True)
        self.btnInventoryStop.setDisabled(False)
        
    """
    Btn Stop Inventory
    """
    def btn_stop_click(self):
        print ("Stop reading")
        self.lbAppStatus.setText("Stop reading")
        self.gpio.btn_stop_click()
        self.btnInventoryStart.setDisabled(False)
        self.btnInventoryStop.setDisabled(True)   
        
    """
    Btn Reader Connect
    """
    def btn_reader_connect_click(self):
        self.set_digital_input()
        self.set_digital_output()
        if not window.rs232.isConnect():
            print ("Connecting...", end="")
            self.rs232.connect()
            self.lbConnectStatus.setText("Connected")
            self.lbConnectStatus.setStyleSheet("background-color:rgb(0, 170, 0)")
            self.disable_Connect_Group(False)
            self.btnInventoryStop.setDisabled(True)
            if len(self.activeDIList) > 0:
                self.gpio.btn_stop_click()
                self.btnInventoryStart.setDisabled(True)
            print ("OK")
            self.lbAppStatus.setText("Connecting...OK")
            self.monitorSignal.emit()
        else:
            self.gpio.btn_stop_click()
            self.rs232.disConnect()
            self.lbConnectStatus.setText("Disconnected")
            self.lbConnectStatus.setStyleSheet("background-color:rgb(255, 0, 0)")
            self.disable_Connect_Group(True)
        app.processEvents()

    """
    Connect to reader
    """
    def connect(self):
        self.btn_reader_connect_click()

    """
    Enable/Disable Buttons
    """
    def disable_Connect_Group(self, bool):
        self.btnInventoryStart.setDisabled(bool)
        self.btnInventoryStop.setDisabled(bool)
        self.btnInventoryReset.setDisabled(bool)

    """
    Set DI/DO
    """
    def set_digital_output(self):
        self.activeDOPortList = []
        self.activeDOList = []
        if len(self.channelDO) > 0:
            self.activeDO = "on"
            for curDO in self.channelDO:
                if curDO == '1':
                    self.activeDOList.append('1')
                    self.activeDOPortList.append(self.gpio.DO1)
                if curDO == '2':
                    self.activeDOList.append('2')
                    self.activeDOPortList.append(self.gpio.DO2)
                if curDO == '3':
                    self.activeDOList.append('3')
                    self.activeDOPortList.append(self.gpio.DO3)
                if curDO == '4':
                    self.activeDOList.append('4')
                    self.activeDOPortList.append(self.gpio.DO4)
        else:
            self.activeDOPortList = []
            self.activeDOList = []
            self.activeDO = "off"

    def set_digital_input(self):
        self.activeDIList = []
        self.activeDI = "off"
        if len(self.channelDI) > 0:
            self.activeDI ="on"
            for curDI in self.channelDI:
                if curDI == '1':
                    self.activeDIList.append('1')
                if curDI == '2':
                    self.activeDIList.append('2')
                if curDI == '3':
                    self.activeDIList.append('3')
                if curDI == '4':
                    self.activeDIList.append('4')
            self.lbAppStatus.setText("Set DI Successfully")
        else:
            self.activeDIList = []
            self.activeDI = "off"
           
        if len(self.activeDIList)>0:
            self.gpio.isDI = True
        else:
            self.gpio.isDI = False

    """
    Reset Inventory
    """
    def reset_inventory_buffer(self):
        self.connection.serWrite(self.reader.reset_inventoryBuffer())
        while self.connection.serInWaiting():
            data = self.connection.serRead()
            if data:
                if len(data) > 0:
                    msgTran = self.reader.analyzeDataAll(data)
                if len(msgTran) == 0:
                    self.reset_inventory_buffer()
                else:
                    self.analyze_data(msgTran)
                    time.sleep(0.1)

    def process_reset_inventory_buffer(self, databarr):
        blResetInventoryBuffer = self.process_error_code(databarr)
        if blResetInventoryBuffer:
            self.logger.debug("Reset Inventory Buffer Successfully")
            print ("Reset Inventory Buffer Successfully")
            self.lbAppStatus.setText("Reset Inventory Buffer Successfully")

    """
    Send commands
    """
    def sendSerialCommand(self, readerCommand):
        self.connection.serWrite(readerCommand)
        time.sleep(0.3)
        while self.connection.serInWaiting():
            data = self.connection.serRead()
            if data:
                if len(data) > 0:
                    msgTran = self.reader.analyzeDataAll(data)
                if len(msgTran) == 0:
                    self.connection.serWrite(readerCommand)
                else:
                    self.analyze_data(msgTran)
                    time.sleep(0.1)
    
    def readLogReset(self):
        print(f"Check log file limit...", end="")
        with open(os.getcwd()+"/reader.log") as file:
            filedata = file.readlines()
            fileLen = len(filedata)
            new_data = ""
            if fileLen > 10000:
                print(f"Create new log file...", end="")
                for i in range (0,fileLen - 10000):
                    filedata[i] = ""
                for i in range(0,fileLen):
                    if filedata[i] != '':
                        new_data += filedata[i] 
                with open(os.getcwd()+"/reader.log",'w') as new_file:
                    new_file.write(new_data)
        print("Done")
        
if __name__ == '__main__':
    
    app = QtWidgets.QApplication(sys.argv)

    # new object
    gpio = SuperIOModule.GPIO()
    window = MainWindow(gpio)

    # Set Application name
    window.setWindowTitle('NIDEC - RFID Warehouse Gate')

    # Fullscreen
    window.showMaximized()

    # Display UI
    window.show()
    window.connect()

    sys.exit(app.exec_())
