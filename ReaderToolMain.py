# coding=UTF-8

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from ctypes import *
import os
import sys
import time
import datetime
import logging
import logging.config
from configparser import ConfigParser
import decimal
import threading
from queue import Queue

from UiReaderTool import Ui_MainWindow

import SocketModule
import SerialportModule
import ReaderModule
import SuperIOModule
import EncodeTag
import RecordModule
import Database

def trap_exc_during_debug(*args):
    # when app raises uncaught exception, print info
    print(args)

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
        self.tabWidget.removeTab(4)
        self.chkShowUser.hide()

        print ("Program start initialize...")
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

        # Session & Target & Region
        self.sessionList = ['S0']
        self.targetList = ['A', 'B']
        self.regionList = ['VN (918.9 - 922.9)']
        self.cmbSession.addItems(self.sessionList)
        self.cmbTarget.addItems(self.targetList)
        self.cmbRegion.addItems(self.regionList)

        # ConfigParser
        self.configManager = ConfigParser()
        self.configManager.read('config.ini')

        # Restore Config
        self.cmbSession.setCurrentIndex(self.cmbSession.findText(self.configManager.get('Reader', 'session')))
        self.cmbTarget.setCurrentIndex(self.cmbTarget.findText(self.configManager.get('Reader', 'target')))
        self.cmbRegion.setCurrentIndex(self.cmbRegion.findText(self.configManager.get('Reader', 'region')))
        self.session = self.cmbSession.currentIndex()
        self.target = self.cmbTarget.currentIndex()
        self.region = self.cmbRegion.currentText()
        self.cfgIp = self.configManager.get('Network', 'ip')
        self.cfgPort = self.configManager.get('Network', 'port')
        self.cfgRS232Port = self.configManager.get('RS232', 'serialport')
        self.cfgRS232Baudrate = self.configManager.get('RS232', 'baudrate')
        self.readerId = self.configManager.get('Reader', 'id')
        self.txtReaderId.setText(self.readerId)

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
            
        self.dbType = ['SQLSERVER', 'MYSQL', 'RESTAPI']
        self.cmbDbType.addItems(self.dbType)
        self.dbDBMS = Database.DBType[self.configManager.get('Database', 'dbms')]
        index = self.cmbDbType.findText(self.dbDBMS.name, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.cmbDbType.setCurrentIndex(index)
        self.dbIp = self.configManager.get('Database', 'IP')
        self.dbPort = self.configManager.get('Database', 'Port')
        self.dbUser = self.configManager.get('Database', 'User')
        self.dbPass = self.configManager.get('Database', 'Pass')
        self.dbDb = self.configManager.get('Database', 'DB')
        self.dbTable = self.configManager.get('Database', 'Table')
        self.txtDbIP.setText(self.dbIp)
        self.txtDbPort.setText(self.dbPort)
        self.txtDbUser.setText(self.dbUser)
        self.txtDbPassword.setText(self.dbPass)
        self.txtDbName.setText(self.dbDb)
        self.txtDbTableName.setText(self.dbTable)

        self.epcCol = self.configManager.get('Column', 'EPC')
        self.tidCol = self.configManager.get('Column', 'tid')
        self.readerIdCol = self.configManager.get('Column', 'ReaderID')
        self.timeCol = self.configManager.get('Column', 'Time')
        self.antennaCol = self.configManager.get('Column', 'antenna')
        self.userCol = self.configManager.get('Column', 'user')
        self.txtFieldEPC.setText(self.epcCol)
        self.txtFieldReaderId.setText(self.readerIdCol)
        self.txtFieldTime.setText(self.timeCol)
        self.txtFieldAntId.setText(self.antennaCol)
        self.txtFieldTid.setText(self.tidCol)
        self.txtFieldUser.setText(self.userCol)

        # Recording Option, check is "on" or "off"
        self.recordDb = self.configManager.get('Record', 'db')
        self.recordLocal = self.configManager.get('Record', 'local')
        
        # RF Power
        self.rfPowerList = self.configManager.get('RF', 'dbm').split(',')
        self.txtPower1.setText(self.rfPowerList[0])
        self.txtPower2.setText(self.rfPowerList[1])
        self.txtPower3.setText(self.rfPowerList[2])
        self.txtPower4.setText(self.rfPowerList[3])
        
        # Init UI Status
        self.disable_Connect_Group(True)
        if self.recordDb == "on":
            self.chkSaveDb.setChecked(True)
            self.disable_Db_Group(False)
        else:
            self.chkSaveDb.setChecked(False)
            self.disable_Db_Group(True)

        if self.recordLocal == "on":
            self.chkSaveDisk.setChecked(True)
        else:
            self.chkSaveDisk.setChecked(False)

        #Antenna
        self.antenna = self.configManager.get('Reader', 'antenna').split(',')
        for currantenna in self.antenna:
            if currantenna == '1':
                self.chkAntenna1.setChecked(True)
            if currantenna == '2':
                self.chkAntenna2.setChecked(True)
            if currantenna == '3':
                self.chkAntenna3.setChecked(True)
            if currantenna == '4':
                self.chkAntenna4.setChecked(True)

        # set GPIO initial
        self.activeDO = self.configManager.get('DO', 'active')
        self.activeDOList = []
        self.activeDOPortList = []
        if self.activeDO == "on":
            self.chkActiveDO.setChecked(True)
            self.channelDO = self.configManager.get('DO', 'channel').split(',')
            for curDO in self.channelDO:
                if curDO == '1':
                    self.chkDO1.setChecked(True)
                if curDO == '2':
                    self.chkDO2.setChecked(True)
                if curDO == '3':
                    self.chkDO3.setChecked(True)
                if curDO == '4':
                    self.chkDO4.setChecked(True)
        else:
            self.chkActiveDO.setChecked(False)

        self.activeDI = self.configManager.get('DI', 'active')
        self.activeDIList = []
        if self.activeDI == "on":
            self.gpio.isDI = True
            self.chkActiveDI.setChecked(True)
            self.channelDI = self.configManager.get('DI', 'channel').split(',')
            for curDI in self.channelDI:
                if curDI == '1':
                    self.chkDI1.setChecked(True)
                    self.activeDIList.append('1')
                if curDI == '2':
                    self.chkDI2.setChecked(True)
                    self.activeDIList.append('2')
                if curDI == '3':
                    self.chkDI3.setChecked(True)
                    self.activeDIList.append('3')
                if curDI == '4':
                    self.chkDI4.setChecked(True)
                    self.activeDIList.append('4')
            self.gpio.DIList = self.activeDIList
        else:
            self.gpio.DIList = []
            self.gpio.isDI = False
            self.chkActiveDI.setChecked(False)

        # Database
        self.db = Database.Database(self.dbDBMS, self.dbIp, self.dbPort, self.dbUser, self.dbPass, self.dbDb)
        
        # Local Recorder to CSV
        self.localRecorder = RecordModule.RecordModule()

        # Reader Moudle
        self.reader = ReaderModule.ReaderModule()                
        
        # TID & User Memory Check
        if self.configManager.get('Show', 'tid') == "on":
            self.chkShowTID.setChecked(True)
            self.blTIDCheck = True
            self.TIDWidth = 250
        else:
            self.chkShowTID.setChecked(False)
            self.blTIDCheck = False
            self.TIDWidth = 30
            
        if self.configManager.get('Show', 'user') == "on":
            self.chkShowUser.setChecked(True)
            self.blUserMemoryCheck = True
            self.UserMemoryWidth = 400
        else:
            self.chkShowUser.setChecked(False)
            self.blUserMemoryCheck = False
            self.UserMemoryWidth = 120
            
        # Database Column
        if self.epcCol != "":
            self.dbColumn = self.epcCol
        if self.readerIdCol != "":
            self.dbColumn = self.dbColumn + "," +self.readerIdCol
        if self.antennaCol != "":
            self.dbColumn = self.dbColumn + "," +self.antennaCol
        if self.timeCol != "":
            self.dbColumn = self.dbColumn + "," +self.timeCol
        if self.tidCol != "":
            self.dbColumn = self.dbColumn + "," +self.tidCol
        if self.userCol != "":
            self.dbColumn = self.dbColumn + "," +self.userCol
        print ("Database Setting...OK")
        
        # tableView
        self.model = QtGui.QStandardItemModel(self.tableView)
        self.model.setColumnCount(7)
        self.model.setHeaderData(0, QtCore.Qt.Horizontal, 'EPC')
        self.model.setHeaderData(1, QtCore.Qt.Horizontal, 'TID')
        self.model.setHeaderData(2, QtCore.Qt.Horizontal, 'ReaderID')
        self.model.setHeaderData(3, QtCore.Qt.Horizontal, 'Time')
        self.model.setHeaderData(4, QtCore.Qt.Horizontal, 'Ant')
        self.model.setHeaderData(5, QtCore.Qt.Horizontal, 'Count')
        #self.model.setHeaderData(6, QtCore.Qt.Horizontal, 'User Memory')
        self.tableView.setModel(self.model)
        self.tableView.setColumnWidth(0, 250)
        self.tableView.setColumnWidth(1, self.TIDWidth)
        self.tableView.setColumnWidth(2, 150)
        self.tableView.setColumnWidth(3, 150)
        self.tableView.setColumnWidth(4, 50)
        self.tableView.setColumnWidth(5, 80)
        self.tableView.setColumnWidth(6, 0)
        #self.tableView.setColumnWidth(6, self.UserMemoryWidth)
        self.tags = []
        
        # Inventory Time Consume
        self.passingTime = 0

        # pictrue
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(os.getcwd() + "/logo.jpg")
        self.lbLogo.setPixmap(pixmap)
        self.lbLogo.setScaledContents(True)

        self.redLight = QPixmap(os.getcwd() + "/Red.png")
        self.greenLight = QPixmap(os.getcwd() + "/Green.png")
        self.lbConnectLight.setPixmap(self.redLight)
        self.lbConnectLight.setScaledContents(True)

        # buttons
        self.btnReaderConnect.clicked.connect(self.btn_reader_connect_click)
        self.btnInventoryStart.clicked.connect(self.btn_start_click)
        self.btnInventoryStop.clicked.connect(self.btn_stop_click)
        self.btnInventoryReset.clicked.connect(self.btn_refresh_click)
        self.btnDbSettingSave.clicked.connect(self.btn_DbSettingSave_click)
        self.btnWriteEPCascii.clicked.connect(self.btn_write_ascii_click)
        self.btnReadEPCascii.clicked.connect(self.btn_read_ascii_click)
        self.btnSaveConfig.clicked.connect(self.btn_save_config_click)
        
        # Tab Widiget Change
        self.tabWidget.currentChanged.connect(self.tab_changed)

        # checkbox
        self.chkSaveDb.clicked.connect(self.chk_save_db_click)
        self.chkSaveDisk.clicked.connect(self.chk_save_dist_click)
        self.chkShowTID.clicked.connect(self.chk_show_TID_click)
        self.chkShowUser.clicked.connect(self.chk_show_UserMemory_click)
        
        # Bool: is "Read" click by ascii page?
        self.blReadAsciiClick = False
        
        # Checkbox auto read checked, then auto connect and read
        if self.configManager.get('Auto', 'read') == "on":
            self.chkAutoRead.setChecked(True)
        else:
            self.chkAutoRead.setChecked(False)
        
        # Tag Encode Module
        self.m_oEncodeTag = EncodeTag.EncodeTag('0000000003171327', '01327A01')
        self.epcFormat = self.configManager.get('Tag', 'format')
        self.epcFormat = self.epcFormat.upper() 
        
        self.epcAscii = ""
        self.readEPC = ""
        self.readTID = ""
        self.readUserBank = ""
        self.readAnt = 0
        self.queue = Queue()
        self._sentinel = object()

        self.inventoryRate = 1 # Use to dynamic control inventory command frequency
        self.blSetPower = False
        self.blSetFrequency = False

        recordThread = threading.Thread(target=self.dataRecord, args=(self.queue, ))
        recordThread.start()
        
    """
    Close Window
    """
    def closeEvent(self, event):

        reply = QMessageBox.question(self, 'Message', "Are you sure to quit?", QMessageBox.Yes,
                                           QMessageBox.No)
        if reply == QMessageBox.Yes:

            self.btn_save_config_click()

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
        self.btn_refresh_click()

        # Check antenna selected and power set
        self.antenna_check()
        if not len(self.antenna) > 0:
            print ("Antenna no choosen")
            self.btn_stop_click()
            self.blInventory = False
        else:
            self.btWorkAntenna = int(self.antenna[0])
        
        self.power_check()
        if min(self.rfPowerList) <= 0:
            print ("Power incorrect")
            self.btn_stop_click()
            self.blInventory = False
        
        if self.blInventory:
            print("Initializing...")
            self.initialize_power()
            self.initialize_region()
            
            # Initial Setting
            nIndexAntenna = 0
            self.nCommand = 0
            self.session = self.cmbSession.currentIndex()
            self.target = self.cmbTarget.currentIndex()
            print("Start reading...")

        while self.blInventory:  
            # Local and DB Recording Process
            self.gpio.detect_sensor()
            if not self.gpio.inventory_check() or not self.check_connect():
                self.blInventory = False
                self.reset_inventory_buffer()
                self.logger.debug("No Sensor Detect and Start Monitor!")
                self.connection.clear()
            try:
                # Inventory command
                if nIndexAntenna < len(self.antenna)-1 or self.nCommand == 0:
                    if self.nCommand == 0:
                        self.nCommand = 1
                        if(self.blTIDCheck and not self.blUserMemoryCheck):
                            self.logger.debug("Send Read TID Command!")
                            self.connection.serWrite(self.reader.readMutiTag(0x00, 0x00, 0x00, 0x06, 0x00, 0x00, self.session, self.target, 0x02, 0x01))
                        elif (not self.blTIDCheck and self.blUserMemoryCheck):
                            self.logger.debug("Send Read User Command!")
                            self.connection.serWrite(self.reader.readMutiTag(0x00, 0x00, 0x00, 0x00, 0x00, 0x02, self.session, self.target, 0x02, 0x01))
                        elif (self.blTIDCheck and self.blUserMemoryCheck):
                            self.logger.debug("Send Read TID and User Command!")
                            self.connection.serWrite(self.reader.readMutiTag(0x00, 0x00, 0x00, 0x06, 0x00, 0x04, self.session, self.target, 0x02, 0x01))
                        else:
                            self.logger.debug("Send Realtime/Customize Inventory Command!")
                            #self.connection.serWrite(self.reader.realtimeInventory(self.reader.realtimeInventoryRepeat))
                            self.connection.serWrite(self.reader.customizeSessionTargetInventory(self.session, self.target, 0x01))
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
        
        for port in self.activeDOPortList:
            self.gpio.set_gpio(port, self.gpio.on)
        
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
            
        for port in self.activeDOPortList:
            self.gpio.set_gpio(port, self.gpio.off)
        
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
                self.process_realtime_inventory(msgTran.databarr)
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
        self.txtGetReaderId.setText(readerIdStr)

    def process_set_baudrate(self, databarr):
        if self.process_error_code(databarr):
            self.configManager.set('RS232', 'baudrate', self.cmbSetBauRate.currentText())
            self.configManager.write(open('config.ini', 'wb'))
            self.cmbBaudrate.setCurrentIndex(self.rs232.getBaudRate().index(self.cmbSetBauRate.currentText()))

    def process_set_work_antenna(self, databarr):
        intCurrentAnt = 0
        intCurrentAnt = self.btWorkAntenna + 1
        strCmd = "Successfully set working antenna, current working antenna : Ant {0}".format(str(intCurrentAnt))

        if self.process_error_code(databarr):
            self.logger.debug(strCmd)
        else:
            self.nCommand = 1

    def process_get_work_antenna(self, databarr):
        antenna = databarr[0]
        if antenna == 0x00:
            print ("Antenna1")
            self.set_antenna_active_change(1)
            return False
        if antenna == 0x01:
            print ("Antenna2")
            self.set_antenna_active_change(2)
            return False
        if antenna == 0x02:
            print ("Antenna3")
            self.set_antenna_active_change(3)
            return False
        if antenna == 0x03:
            print ("Antenna4")
            self.set_antenna_active_change(4)
            return False

    def set_antenna_active_change(self, antNum):
        if antNum == 1:
            self.chkAnt1.setChecked(True)
            self.chkAnt2.setChecked(False)
            return False
        elif antNum == 2:
            self.chkAnt1.setChecked(False)
            self.chkAnt2.setChecked(True)
            return False
        
    """  
    Initialize Power and Region
    """
    def initialize_power(self):
        if not (self.curPower[0] == self.txtPower1.text() and
                self.curPower[1] == self.txtPower2.text() and
                self.curPower[2] == self.txtPower3.text() and
                self.curPower[3] == self.txtPower4.text()):
            self.curPower = list(map(int, [self.txtPower1.text(), self.txtPower2.text(), self.txtPower3.text(), self.txtPower4.text()]))
            
            for i in range(len(self.curPower)-1):
                if self.curPower[i] != self.curPower[i+1]:
                    self.set_output_power(self.curPower)
                    break
                if i == len(self.curPower)-2:
                    self.set_temporary_output_power(self.curPower[0])                   
        
    """  
    Initialize Power and Region
    """
    def initialize_region(self):
        if not self.curRegion == self.cmbRegion.currentText() or self.start1 != self.FrequencyStart.text() or self.end1 != self.FrequencyEnd.text():
            self.curRegion = self.cmbRegion.currentText()
            self.set_frequency_region(self.curRegion)

    def set_output_power(self, powerList):
        print (f"Set output power Ant1: {powerList[0]}dbm, Ant2: {powerList[1]}dbm, Ant3: {powerList[2]}dbm, Ant4: {powerList[3]}dbm ... ", end="")
        self.blSetPower = False
        while not self.blSetPower:
            self.connection.serWrite(self.reader.setOutputPower(powerList))
            time.sleep(0.2)
        print ("Done")
        self.logger.debug("Set output power successfully")
        
    def set_temporary_output_power(self, power):
        print (f"Set Temporary Output Power {int(power)}dbm ... ", end="")
        self.blSetPower = False
        while not self.blSetPower:
            self.connection.serWrite(self.reader.setTemporaryOutputPower(int(power)))
            time.sleep(0.2)
        print ("Done")
        self.logger.debug("Set Temporary Output Power successfully")
        
    def set_frequency_region(self, region):
        print (f"Set Frequency Region {region} ... ", end="")
        self.blSetFrequency = False
        while not self.blSetFrequency:
            self.connection.serWrite(self.reader.setFrequencyRegionByCountry(str(region)))
            time.sleep(0.2)
        print ("Done")
        self.logger.debug("Set frequency region successfully")

    def process_set_output_power(self, databarr):
        self.blSetPower = self.process_error_code(databarr)

    def process_get_output_power(self, databarr):
        if len(databarr) == 1:
            power = str(databarr[0])
            print ("CurrentOutputPower: " + power)
            self.txtPower1.setText(power)
            self.txtPower1.setText(power)
            self.txtPower1.setText(power)
            self.txtPower1.setText(power)
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

    def process_write_tag(self, databarr):
        dataLen = len(databarr)
        if dataLen == 1:
            self.process_error_code(databarr)
        else:
            """
            N:len(databarr)
            0:2bytes[Tag Count]
            2:DataLen[]
            3~N-4:PC(2),EPC(),CRC(2)
            N-3:Errcode
            N-2:AntId
            N-1:WriteCount
            """ 
            nEpcLen = databarr[2] - 4
            strEPC = ""
            epcEnd = 5 + nEpcLen
            if epcEnd <= dataLen:
                for b in range(5, epcEnd):
                    strEPC += str(hex(databarr[b]))[2:].zfill(2) + ' '
            strEPC = strEPC.upper()
            self.logger.debug("Write EPC: {0} Successfully".format(strEPC))
            print ("Write EPC: {0} Successfully".format(strEPC))
            
    def process_get_reader_temperature(self, databarr):
        for d in databarr:
            print (d)

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

                if(self.blReadAsciiClick):
                    self.readAsciiSingal.emit(strEPC)
                else: 
                    # Show Inventory Result         
                    # TID and User
                    strData = ""
                    DataEnd = 7 + nEpcLen + nDataLen
                    if DataEnd <= dataLen:
                        for b in range(7 + nEpcLen, DataEnd):
                            strData += str(hex(databarr[b]))[2:].zfill(2) + ' '
                    strData = strData.upper()
                    strTid = ""
                    strUser = ""
                    tidColVal = ""
                    userColVal = ""
                    if(self.blTIDCheck and not self.blUserMemoryCheck):
                        strTid = strData
                        tidColVal = strTid.replace(' ', '')
                    elif (not self.blTIDCheck and self.blUserMemoryCheck):
                        strUser = strData
                        userColVal = strUser.replace(' ', '')
                    elif (self.blTIDCheck and self.blUserMemoryCheck):
                        strTid = strData[:36]
                        strUser = strData[36:]
                        tidColVal = strTid.replace(' ', '')
                        userColVal = strUser.replace(' ', '')
                    
                    # Antenna
                    if (databarr[dataLen-1] & 0x80) == 0:
                        ant = (databarr[dataLen-2] & 0x03) + 1
                    else:
                        ant = (databarr[dataLen-2] & 0x03) + 5
                    
                    if (int(strPC[0:2], 16)/4) <= (epcEnd-4):
                        if str(ant) in self.antenna:
                            dtNow = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f').split(".")[0]
                            tagDict = {
                                self.epcCol: strEPC,
                                self.readerIdCol: self.readerId,
                                self.antennaCol: ant,
                                self.timeCol: dtNow,
                                self.tidCol: tidColVal
                            }
                            self.inventorySingal.emit(tagDict)
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
                
            else: 
                nEpcLen = dataLen - 2
                rssiLocation = 1 + nEpcLen
                strEPC = ""
                # EPC= PC + EPC
                for b in range(1, 1 + nEpcLen):
                    strEPC += str(hex(databarr[b]))[2:].zfill(2) + " "
                strEPC = strEPC.upper().replace(' ', '')
                dRSSI = databarr[rssiLocation] -129
                self.logger.debug('Tag: ' + strEPC)
                
                # Antenna
                if (databarr[rssiLocation] & 0x80) == 0:
                    ant = (databarr[0] & 0x03) + 1
                else:
                    ant = (databarr[0] & 0x03) + 5
                
                if (int(strEPC[0:2], 16)/4) <= (nEpcLen-1):
                    if str(ant) in self.antenna:
                        dtNow = datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S.%f').split(".")[0]
                        tagDict = {
                            self.epcCol: strEPC,
                            self.readerIdCol: self.readerId,
                            self.antennaCol: ant,
                            self.timeCol: dtNow,
                            self.tidCol: ""
                        }
                        self.inventorySingal.emit(tagDict)
                        time.sleep(0.01)

        except Exception as e:
            print (e)


    @QtCore.pyqtSlot(dict)        
    def inventoryUI(self, tagDict):

        if self.blInventory:
            # Detect Duplicate
            hasExist = False
            
            readEPC = tagDict[self.epcCol]
            readerId = tagDict[self.readerIdCol]
            readAnt = tagDict[self.antennaCol]
            readTime = tagDict[self.timeCol]
            readTID = tagDict[self.tidCol] if self.tidCol else ""
            #readUserBank = tagDict[self.userCol] if self.userCol else ""
                 
            #strData = readEPC + readTID + readUserBank
            strData = readEPC + readTID
            
            i = self.model.rowCount()
            if len(self.tags) > 0:
                if (strData) in self.tags:
                    index = self.tags.index(strData)
                    if readAnt == int(self.model.data(self.model.index(index, 4))):
                        tagCount = int(self.model.data(self.model.index(index, 5))) + 1
                        self.model.setItem(index, 5, QtGui.QStandardItem(str(tagCount)))
                        self.tableView.setModel(self.model)
                    hasExist = True
            
            if not hasExist:
                # Update Tags
                self.tags.append(strData)

                # Decode EPC
                decodeData = self.epcDecoder(readEPC)
                if type(decodeData) is tuple:
                    serialNumber = decodeData[1]
                    itemName = decodeData[0]
                    tagData = itemName + "-" + str(serialNumber)
                else:
                    tagData = decodeData
                             
                # Update TableView
                self.model.setItem(i, 0, QtGui.QStandardItem(tagData))
                self.model.setItem(i, 1, QtGui.QStandardItem(readTID))
                self.model.setItem(i, 2, QtGui.QStandardItem(self.readerId))
                self.model.setItem(i, 3, QtGui.QStandardItem(readTime))
                self.model.setItem(i, 4, QtGui.QStandardItem(str(readAnt)))
                self.model.setItem(i, 5, QtGui.QStandardItem("1"))
                #self.model.setItem(i, 6, QtGui.QStandardItem(readUserBank))
                
                #Record
                tagDict[self.epcCol] = tagData # Change readList's EPC to Decode Data
                if not readTID:
                    tagDict.pop(self.tidCol, None)
                self.queue.put(tagDict)
                
                # Caculate Time Consuming
                firstTimeTag = datetime.datetime.strptime(str(self.model.data(self.model.index(0, 3))), '%Y/%m/%d %H:%M:%S')
                lastTimeTag = datetime.datetime.strptime(str(self.model.data(self.model.index(i, 3))), '%Y/%m/%d %H:%M:%S')
                self.passingTime = round( (lastTimeTag -firstTimeTag).total_seconds(), 3)
                self.tableView.setModel(self.model)
                
            # update Tag Count
            self.lbInventoryQuantity.setText(str(self.model.rowCount()).zfill(4))
            self.lbTime.setText(str(self.passingTime) + " sec.")
        
            
        
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
    EPC Formatter: return itemName, serialNumber
    """
    def epcDecoder(self, epc):
        try:
            if self.epcFormat =="EPC":
                return epc
            if self.epcFormat =="ASCII":
                epcAscii = self.m_oEncodeTag.ToASCII(epc)
                return epcAscii
            if self.epcFormat=="UDC":
                udc = self.m_oEncodeTag.ToUDC(epc)
                return udc
            if self.epcFormat=="EAN":
                itemName, serialNumber = self.m_oEncodeTag.parseSGTIN96HexString(epc)
                return (itemName, serialNumber)
            if self.epcFormat=="TITAS":
                decodeEPC = self.m_oEncodeTag.ToBarcode(epc).Text()
                return decodeEPC
            if self.epcFormat=="TITAS_XIYUAN":
                itemName, serialNumber = self.m_oEncodeTag.ToTitasCode(epc)
                return (itemName, serialNumber)
        except Exception as e:
            print (e)                

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
    Data record process (DB & Disk)
    # recordList: Tag Dictionary, key is the db column name, like {EPC, TID, USERBANK, ANTENNA, TIME}
    """
    def dataRecord(self, tagDict):
        for tagDict in iter(self.queue.get, self._sentinel):
            blInsertDB = 0
            if self.recordDb == "on":
                blInsertDB = self.db.insert(self.dbTable, tagDict)    
            if self.recordLocal == "on":
                row = []
                for k in tagDict:
                    row.append(tagDict[k])
                if blInsertDB:
                    blInsertDB = 1
                else:
                    blInsertDB = 0
                self.localRecorder.writeLog(row, blInsertDB)

    
    """
    Check unInsert Tag Log
    """
    def check_unInsert_tag(self):
        unInsertDict = self.localRecorder.ckFileDateToDB()
        for key in unInsertDict:
            for dataList in unInsertDict.get(key):
                insertFail_count = 0
                blInsertDB = self.db.insert(self.dbTable, self.dbColumn, dataList)
                if blInsertDB == 1:
                    self.localRecorder.writeLog(dataList, blInsertDB, key, "a")
                else:
                    insertFail_count = insertFail_count + 1
                    self.localRecorder.writeLog(dataList, blInsertDB, key, "w")
            if insertFail_count == 0:
                self.localRecorder.deleteFile(self.localRecorder.getFullLocation(key+"-0.csv"))
        print ("Check uninsert tag log done")

    """
    Refresh TableView
    """
    def btn_refresh_click(self):
        self.model.removeRows(0, self.model.rowCount())
        self.tableView.setModel(self.model)
        self.lbInventoryQuantity.setText(str(0).zfill(4))
        self.lbTime.setText("0.0 sec.")
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
        self.gpio.btn_stop_click()
        self.btnInventoryStart.setDisabled(False)
        self.btnInventoryStop.setDisabled(True)   
        
    def antenna_check(self):
        self.antenna = []
        if self.chkAntenna1.isChecked():
            self.antenna.append('1')
        if self.chkAntenna2.isChecked():
            self.antenna.append('2')
        if self.chkAntenna3.isChecked():
            self.antenna.append('3')
        if self.chkAntenna4.isChecked():
            self.antenna.append('4')
    
    def power_check(self):
        self.rfPowerList = []
        self.rfPowerList.append(int(self.txtPower1.text()))
        self.rfPowerList.append(int(self.txtPower2.text()))
        self.rfPowerList.append(int(self.txtPower3.text()))
        self.rfPowerList.append(int(self.txtPower4.text()))

    """
    Btn Reader Connect
    """
    def btn_reader_connect_click(self):
        self.set_digital_input()
        self.set_digital_output()
        if not window.rs232.isConnect():
            print ("Connecting...")
            self.rs232.connect()
            self.btnReaderConnect.setText("Disconnect")
            self.lbConnectStatus.setText("Connected")
            self.lbConnectLight.setPixmap(self.greenLight)
            self.lbConnectLight.setScaledContents(True)
            self.disable_Connect_Group(False)
            self.btnInventoryStop.setDisabled(True)
            if len(self.activeDIList) > 0:
                self.gpio.btn_stop_click()
                self.btnInventoryStart.setDisabled(True)
            self.monitorSignal.emit()
        else:
            self.gpio.btn_stop_click()
            self.rs232.disConnect()
            self.btnReaderConnect.setText("Connect")
            self.lbConnectStatus.setText("Disconnected")
            self.lbConnectLight.setPixmap(self.redLight)
            self.lbConnectLight.setScaledContents(True)
            self.disable_Connect_Group(True)
        app.processEvents()

    """
    Chk Save Disk click
    """
    def chk_save_dist_click(self):
        if self.chkSaveDisk.isChecked():
            self.recordLocal = "on"
        else: 
            self.recordLocal = "off"

    """
    Chk Save DB click
    """
    def chk_save_db_click(self):
        if self.chkSaveDb.isChecked():
            self.disable_Db_Group(False)
            self.recordDb = "on"
        else:
            self.disable_Db_Group(True)
            self.recordDb = "off"
            
    """
    Chk Show TID click
    """
    def chk_show_TID_click(self):
        if self.chkShowTID.isChecked():
            self.blTIDCheck = True
            self.TIDWidth = 220
        else:
            self.blTIDCheck = False
            self.TIDWidth = 30
        self.tableView.setColumnWidth(1, self.TIDWidth)
        app.processEvents()

    """
    Chk Show User Memory click
    """
    def chk_show_UserMemory_click(self):            
        if self.chkShowUser.isChecked():
            self.blUserMemoryCheck = True
            self.UserMemoryWidth = 400
        else:
            self.blUserMemoryCheck = False
            self.UserMemoryWidth = 120
        self.tableView.setColumnWidth(6, self.UserMemoryWidth)
        app.processEvents()
  
    """
    Check auto read
    """
    def auto_connect(self):           
        if self.chkAutoRead.isChecked():
            self.btn_reader_connect_click()
            
    """
    Btn Save Config
    """
    def btn_save_config_click(self):
        try:
            # Reader and Antenna
            self.configManager.set('Reader', 'id', str(self.txtReaderId.text()))
            self.configManager.set('Reader', 'session', str(self.cmbSession.currentText()))
            self.configManager.set('Reader', 'target', str(self.cmbTarget.currentText()))
            self.configManager.set('Reader', 'region', str(self.cmbRegion.currentText()))
            self.antennaSetting = []
            if self.chkAntenna1.isChecked():
                self.antennaSetting.append('1')
            if self.chkAntenna2.isChecked():
                self.antennaSetting.append('2')
            if self.chkAntenna3.isChecked():
                self.antennaSetting.append('3')
            if self.chkAntenna4.isChecked():
                self.antennaSetting.append('4')
            self.configManager.set('Reader', 'antenna', str(','.join(self.antennaSetting)))
            self.configManager.set('Reader', 'id', str(self.readerId))
            
            # Checkbox: Show TID, Show User, Auto Read
            if self.chkShowTID.isChecked():
                self.configManager.set('Show', 'tid', "on")
            else:
                self.configManager.set('Show', 'tid', "off")
            if self.chkShowUser.isChecked():
                self.configManager.set('Show', 'user', "on")
            else:
                self.configManager.set('Show', 'user', "off")
            if self.chkAutoRead.isChecked():
                self.configManager.set('Auto', 'read', "on")
            else:
                self.configManager.set('Auto', 'read', "off")

            #Record
            self.configManager.set('Record', 'db', str(self.recordDb))
            self.configManager.set('Record', 'local', str(self.recordLocal))

            # RF
            self.configManager.set('RF', 'dbm', f"{self.txtPower1.text()},{self.txtPower2.text()},{self.txtPower3.text()},{self.txtPower4.text()}")
            
            # Db Setting
            self.configManager.set('Database', 'dbms', str(self.cmbDbType.currentText()))
            self.configManager.set('Database', 'IP', str(self.txtDbIP.text()))
            self.configManager.set('Database', 'Port', str(self.txtDbPort.text()))
            self.configManager.set('Database', 'Db', str(self.txtDbName.text()))
            self.configManager.set('Database', 'Table', str(self.txtDbTableName.text()))
            self.configManager.set('Database', 'User', str(self.txtDbUser.text()))
            self.configManager.set('Database', 'Pass', str(self.txtDbPassword.text()))
            
            # Db Field Column
            self.configManager.set('Column', 'EPC', str(self.txtFieldEPC.text()))
            self.configManager.set('Column', 'tid', str(self.txtFieldTid.text()))
            self.configManager.set('Column', 'ReaderID', str(self.txtFieldReaderId.text()))
            self.configManager.set('Column', 'Time', str(self.txtFieldTime.text()))
            self.configManager.set('Column', 'antenna', str(self.txtFieldAntId.text()))
            self.configManager.set('Column', 'user', str(self.txtFieldUser.text()))

            #DI & DO
            self.set_digital_output()
            self.set_digital_input()
            self.configManager.set('DO', 'active', str(self.activeDO))
            self.configManager.set('DI', 'active', str(self.activeDI))
            self.configManager.set('DO', 'channel', str(','.join(self.activeDOList)))
            self.configManager.set('DI', 'channel', str(','.join(self.activeDIList)))
            
            with open('config.ini', 'w') as configfile:
                self.configManager.write(configfile)

        except Exception as ex:
            print (ex)
        

    """
    Btn Save DB Setting click
    """
    def btn_DbSettingSave_click(self):
        self.readerId = self.txtReaderId.text()
        self.dbDBMS = Database.DBType[self.cmbDbType.currentText()]
        self.dbIp = self.txtDbIP.text()
        self.dbPort = self.txtDbPort.text()
        self.dbUser = self.txtDbUser.text()
        self.dbPass = self.txtDbPassword.text()
        self.dbDb = self.txtDbName.text()
        self.dbTable = self.txtDbTableName.text()
        
        self.epcCol = self.txtFieldEPC.text()
        self.tidCol = self.txtFieldTid.text()
        self.readerIdCol = self.txtFieldReaderId.text()
        self.timeCol = self.txtFieldTime.text()
        self.antennaCol = self.txtFieldAntId.text()
        self.userCol = self.txtFieldUser.text()
        
        # Database Column
        if self.epcCol != "":
            self.dbColumn = self.epcCol
        if self.readerIdCol != "":
            self.dbColumn = self.dbColumn + "," +self.readerIdCol
        if self.antennaCol != "":
            self.dbColumn = self.dbColumn + "," +self.antennaCol
        if self.timeCol != "":
            self.dbColumn = self.dbColumn + "," +self.timeCol
        if self.tidCol != "":
            self.dbColumn = self.dbColumn + "," +self.tidCol
        if self.userCol != "":
            self.dbColumn = self.dbColumn + "," +self.userCol
        
        self.db.dbType = Database.DBType[str(self.dbDBMS.name)]
        self.db.dbIp = str(self.dbIp)
        self.db.dbPort = str(self.dbPort)
        self.db.dbUser = str(self.dbUser)
        self.db.dbPass = str(self.dbPass)
        self.db.dbDb = str(self.dbDb)


    def disable_Connect_Group(self, bool):
        self.txtPower1.setDisabled(bool)
        self.txtPower2.setDisabled(bool)
        self.txtPower3.setDisabled(bool)
        self.txtPower4.setDisabled(bool)
        self.chkAntenna1.setDisabled(bool)
        self.chkAntenna2.setDisabled(bool)
        self.chkAntenna3.setDisabled(bool)
        self.chkAntenna4.setDisabled(bool)
        self.cmbRegion.setDisabled(bool)
        self.cmbTarget.setDisabled(bool)
        self.cmbSession.setDisabled(bool)
        self.btnInventoryStart.setDisabled(bool)
        self.btnInventoryStop.setDisabled(bool)
        self.btnInventoryReset.setDisabled(bool)


    def disable_Db_Group(self, bool):
        self.cmbDbType.setDisabled(bool)
        self.txtDbName.setDisabled(bool)
        self.txtDbIP.setDisabled(bool)
        self.txtDbPassword.setDisabled(bool)
        self.txtDbPort.setDisabled(bool)
        self.txtDbTableName.setDisabled(bool)
        self.txtDbUser.setDisabled(bool)
        self.txtFieldAntId.setDisabled(bool)
        self.txtFieldEPC.setDisabled(bool)
        self.txtFieldReaderId.setDisabled(bool)
        self.txtFieldTime.setDisabled(bool)
        self.txtFieldTid.setDisabled(bool)
        self.txtFieldUser.setDisabled(bool)
        self.txtReaderId.setDisabled(bool)
        

    def set_digital_output(self):
        self.activeDOList = []
        self.activeDOPortList = []
        if self.chkActiveDO.isChecked():
            self.activeDO = "on"
            if self.chkDO1.isChecked():
                self.activeDOList.append('1')
                self.activeDOPortList.append(self.gpio.DO1)
            if self.chkDO2.isChecked():
                self.activeDOList.append('2')
                self.activeDOPortList.append(self.gpio.DO2)
            if self.chkDO3.isChecked():
                self.activeDOList.append('3')
                self.activeDOPortList.append(self.gpio.DO3)
            if self.chkDO4.isChecked():
                self.activeDOList.append('4')
                self.activeDOPortList.append(self.gpio.DO4)
        else:
            self.activeDOPortList = []
            self.activeDOList = []
            self.activeDO = "off"


    def set_digital_input(self):
        self.activeDIList = []
        if self.chkActiveDI.isChecked():
            self.activeDI ="on"
            if self.chkDI1.isChecked():
                self.activeDIList.append('1')
            if self.chkDI2.isChecked():
                self.activeDIList.append('2')
            if self.chkDI3.isChecked():
                self.activeDIList.append('3')
            if self.chkDI4.isChecked():
                self.activeDIList.append('4')        
        else:
            self.activeDIList = []
            self.activeDI = "off"
            
        if len(self.activeDIList)>0:
            self.gpio.isDI = True
        else:
            self.gpio.isDI = False
     

    def tab_changed(self):
        self.set_digital_input()
        self.set_digital_output()
        
        if not window.rs232.isConnect():
            self.btnInventoryStart.setDisabled(True)
        else:
            self.btnInventoryStart.setDisabled(False)

        self.btnInventoryStop.setDisabled(True)
        if len(self.activeDIList) > 0:
            self.gpio.DIList = self.activeDIList
            self.gpio.btn_stop_click()
            self.btnInventoryStart.setDisabled(True)
        else:
            self.gpio.DIList = []
            self.gpio.btn_stop_click()
            
        app.processEvents()
        
        
    def btn_write_ascii_click(self):
        epcWritten = self.txtEPCasciiW.text()
        asciiWriteLen = int(self.txtEPCasciiWLen.text())
        
        password = bytearray([0x00, 0x00, 0x00, 0x00])
        memBank = 0x01 # Write EPC
        wordAdd = 0x01 # Write EPC start with position 2
        btAryData = bytearray()
        for i in range(2):
            epcAscii = ""
            for word in str(epcWritten):
                epcAscii = epcAscii + hex(ord(word))[2:]
            if asciiWriteLen == 2:
                pc = "0800"
            else:
                pc = hex(int(((asciiWriteLen)/2)*8))[2:] + "00"
            epcAscii = pc + epcAscii
            while len(epcAscii)%4!=0:
                epcAscii = epcAscii + "00"
            btAryData = bytearray.fromhex(epcAscii)
            
            #wordAdd = 0x00
            wordCnt = int(asciiWriteLen / 2) + 2
            
            try:
                self.sendSerialCommand(self.reader.writeTag(password, memBank, wordAdd, wordCnt, btAryData))     
            except Exception as ex:
                print (ex)
                self.logger.debug("Write EPC ASCII Error")


    def btn_read_ascii_click(self):
        self.blReadAsciiClick = True
        password = bytearray([0x00, 0x00, 0x00, 0x00])
        memBank = 0x01  # Read EPC
        wordAdd = 0x00  
        wordCnt = 0x08
        
        try:
            self.sendSerialCommand(self.reader.readTag(memBank, wordAdd, wordCnt))     
        except Exception as ex:
            print (ex)
            self.logger.debug("Write EPC ASCII Error")
        
        self.blReadAsciiClick = False
    

    def reset_inventory_buffer(self):
        self.connection.serWrite(self.reader.reset_inventoryBuffer())
        while self.connection.serInWaiting():
            data = self.connection.serRead()
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
    
    def sendSerialCommand(self, readerCommand):
        self.connection.serWrite(readerCommand)
        time.sleep(0.3)
        while self.connection.serInWaiting():
            data = self.connection.serRead()
            if len(data) > 0:
                msgTran = self.reader.analyzeDataAll(data)
            if len(msgTran) == 0:
                self.connection.serWrite(readerCommand)
            else:
                self.analyze_data(msgTran)
                time.sleep(0.1)

if __name__ == '__main__':
    
    app = QtWidgets.QApplication(sys.argv)

    # new object
    gpio = SuperIOModule.GPIO()
    window = MainWindow(gpio)

    # Set Application name
    window.setWindowTitle('ReaderTool V.2.816.22.VN')

    # Display UI
    window.show()
    window.auto_connect()

    sys.exit(app.exec_())

