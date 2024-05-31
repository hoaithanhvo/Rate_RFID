# coding=UTF-8

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QMessageBox
import sys
import glob
import serial
import logging
import logging.config
from configparser import SafeConfigParser

import frmSetting
from frmSetting import Ui_MainWindow
import SerialportModule
import SocketModule
import ReaderModule
import SuperIOModule

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)

        # logging setting
        logging.config.fileConfig('logging.conf')
        self.logger = logging.getLogger('root')

        # Connect Mode
        self.socketMode = 0x01
        self.rs232Mode = 0x02
        self.Mode = self.socketMode

        # Inventory Mode
        self.InventoryStart = 0x00
        self.InventoryStop = 0x01
        self.InventoryMode = self.InventoryStart

        # ConfigParser
        self.configManager = SafeConfigParser()
        self.configManager.read('config.ini')

        # Restore Config
        self.cfgIp = self.configManager.get('Network', 'ip')
        self.cfgPort = self.configManager.get('Network', 'port')
        self.cfgSerialPort = self.configManager.get('RS232', 'serialport')
        self.cfgBaudrate = self.configManager.get('RS232', 'baudrate')
        self.txtIP.setText(self.cfgIp)
        self.txtPort.setText(self.cfgPort)

        self.readerId = self.configManager.get('Reader', 'id')
        self.antenna = self.configManager.get('Reader', 'antenna').split(',')
        self.txtReaderId.setText(self.readerId)
        for currantenna in self.antenna:
            if currantenna == '1':
                self.chkAnt1.setChecked(True)
            if currantenna == '2':
                self.chkAnt2.setChecked(True)
            if currantenna == '3':
                self.chkAnt3.setChecked(True)
            if currantenna == '4':
                self.chkAnt4.setChecked(True)
        self.dbIp = self.configManager.get('Database', 'IP')
        self.dbPort = self.configManager.get('Database', 'Port')
        self.dbUser = self.configManager.get('Database', 'User')
        self.dbPass = self.configManager.get('Database', 'Pass')
        self.dbDb = self.configManager.get('Database', 'DB')
        self.dbTable = self.configManager.get('Database', 'Table')
        self.txtDbIP.setText(self.dbIp)
        self.txtDbPort.setText(self.dbPort)
        self.txtDbUser.setText(self.dbUser)
        self.txtDbPass.setText(self.dbPass)
        self.txtDbName.setText(self.dbDb)
        self.txtDbTableName.setText(self.dbTable)

        # Other Module
        # Serial Port
        self.rs232 = SerialportModule.RS232(self.cfgSerialPort, self.cfgBaudrate)
        self.cmbBaudrate.addItems(self.rs232.getBaudRates())
        self.cmbSetBauRate.addItems(self.rs232.getBaudRates())
        currentIndex = self.rs232.getBaudRate().index(str(self.configManager.get('RS232', 'baudrate')))
        self.cmbBaudrate.setCurrentIndex(currentIndex)
        self.cmbSerialPort.addItems(self.rs232.getSerialPorts())
        #self.cmbSerialPort.addItems(self.rs232.getSerialPorts())

        # Socket
        self.txtIP.setText(self.cfgIp)
        self.txtPort.setText(self.cfgPort)
        self.socket = SocketModule.SocketModule(self.txtIP.text(), int(self.txtPort.text()))

        # Reader
        self.reader = ReaderModule.ReaderModule()

        # Socket mode by default
        configMode = self.configManager.get('Mode', 'mode')

        if not configMode:
            self.configManager.set('Mode', 'mode', '1')
            self.rbTCPIP.setChecked(True)
            self.configManager.write(open('config.ini', 'wb'))
            self.enableTCPIPGroup()
        elif str(configMode) == '1':  # 0x01 TCP/IP
            self.rbTCPIP.setChecked(True)
            self.enableTCPIPGroup()
        elif str(configMode) == '2':  # 0x02 RS232
            self.rbRS232.setChecked(True)
            self.enableRS232Group()

        # Inputs
        self.txtGetReaderId.setDisabled(True)

        # Buttons
        self.btnRS232SetBaudrate.clicked.connect(self.btnRS232SetBaudrate_Click)
        self.btnRS232Connect.clicked.connect(self.btnRS232Connect_Click)
        self.btnRS232Disconnect.clicked.connect(self.btnRS232Disconnect_Click)
        self.btnIPConnect.clicked.connect(self.btnIPConnect_Click)
        self.btnIPDisconnect.clicked.connect(self.btnIPDisconnect_Click)
        self.btnResetReader.clicked.connect(self.btnResetReader_Click)
        self.btnSave.clicked.connect(self.btnSave_Click)
        self.rbTCPIP.clicked.connect(self.rbTCPIP_Click)
        self.rbRS232.clicked.connect(self.rbRS232_Click)
        self.btnGetReaderId.clicked.connect(self.btnGetReaderId_Click)
        self.btnSetReaderId.clicked.connect(self.btnSetReaderId_Click)
        self.btnGetDbm.clicked.connect(self.btnGetOutputPower_Click)
        self.btnSetDbm.clicked.connect(self.btnSetOutputPower_Click)

    def check_connect(self):
        if self.socket.isConnect() == False and self.rs232.isConnect() == False:
            return False
        else:
            return True

    def btnGetReaderId_Click(self):
        if not self.check_connect():
            print ("No Connection")
            return False
        if self.Mode == self.socketMode:
            data = self.socket.sendCmd(self.reader.getReaderId())
            print ("data transfer")
        else:
            data = self.rs232.sendCmd(self.reader.getReaderId())
        msgTran = self.reader.analyzeData(data)
        self.analyze_data(msgTran)

    def btnSetReaderId_Click(self):
        if not self.check_connect():
            print ("No Connection")
            return False

        dataLen = len(self.txtSetReaderId.text())
        readerIdTxt = self.txtSetReaderId.text()
        if dataLen == 24:
            if self.Mode == self.socketMode:
                data = self.socket.sendCmd(self.reader.setReaderId(readerIdTxt))
            else:
                data = self.rs232.sendCmd(self.reader.setReaderId(readerIdTxt))
            msgTran = self.reader.analyzeData(data)
            self.analyze_data(msgTran)
        else:
            print ("Error")

    def btnGetOutputPower_Click(self):
        # Check Connection
        if not self.check_connect():
            self.logger.debug("No Connection!")
            print ("No Connection")
            return False
        if self.Mode == self.socketMode:
            data = self.socket.sendCmd(self.reader.getOutputPower())
            print ("data transfer")
        else:
            data = self.rs232.sendCmd(self.reader.getOutputPower())
            print ("data transfer RS232")
        msgTran = self.reader.analyzeData(data)
        self.analyze_data(msgTran)

    def btnSetOutputPower_Click(self):
        # Check Connection
        if not self.check_connect():
            self.logger.debug("No Connection!")
            print ("No Connection")
            return False
        if self.Mode == self.socketMode:
            data = self.socket.sendCmd(self.reader.setOutputPower(int(self.txtDbm.text())))
            print ("data transfer")
        else:
            data = self.rs232.sendCmd(self.reader.setOutputPower(int(self.txtDbm.text())))
        msgTran = self.reader.analyzeData(data)
        self.analyze_data(msgTran)

    def btnRS232SetBaudrate_Click(self):
        if not self.check_connect():
            print ("No Connection")
            return False

        baudRate = self.cmbSetBauRate.currentText()

        if self.Mode == self.socketMode:
            if baudRate == "38400":
                data = self.socket.sendCmd(self.reader.setUartBaudrate(self.reader.baudrate_38400))
            else:
                data = self.socket.sendCmd(self.reader.setUartBaudrate(self.reader.baudrate_115200))
        else:
            if baudRate == "38400":
                data = self.rs232.sendCmd(self.reader.setUartBaudrate(self.reader.baudrate_38400))
            else:
                data = self.rs232.sendCmd(self.reader.setUartBaudrate(self.reader.baudrate_115200))
        msgTran = self.reader.analyzeData(data)
        self.analyze_data(msgTran)

    def btnRS232Disconnect_Click(self):
        print ('click RS232 Disconnect')
        self.rs232.disConnect()
        if not self.rs232.isConnect():
            # DisConnect
            self.btnRS232Connect.setDisabled(False)
            self.btnRS232Disconnect.setDisabled(True)

    def btnRS232Connect_Click(self):
        # if you want to trigger monitor in monitorThread you should do this
        self.Mode = self.rs232Mode
        if self.cmbSerialPort.currentText() == "":
            print ('There is no serial port list')
        else:
            self.rs232 = SerialportModule.RS232(str(self.cmbSerialPort.currentText()), int(self.cmbBaudrate.currentText()))
            self.rs232.connect()
            if self.rs232.isConnect():
                # Connect
                print ('Connect rs232')
                self.logger.debug("socket connect status: " + str(self.rs232.isConnect()))
                self.btnRS232Connect.setDisabled(True)
                self.btnRS232Disconnect.setDisabled(False)
            else:
                # DisConnect
                print ('Not connect rs232')
                self.btnRS232Connect.setDisabled(False)
                self.btnRS232Disconnect.setDisabled(True)
                

    def btnIPConnect_Click(self):
        # if you want to trigger monitor in monitorThread you should do this
        self.Mode = self.socketMode

        if self.txtIP.text() == "" and self.txtPort.text() == "":
            if self.txtIP.text() == "":
                print ("IPAddress is required")
            if self.txtPort.text() == "":
                print ("Port is required")
        else:
            # new Socket
            self.socket = SocketModule.SocketModule(self.txtIP.text(), int(self.txtPort.text()))
            self.socket.connect()
            if self.socket.isConnect():
                self.logger.debug("socket connect status: " + str(self.socket.isConnect()))
                # Connect
                self.btnIPConnect.setDisabled(True)
                self.btnIPDisconnect.setDisabled(False)
                

    def btnIPDisconnect_Click(self):
        self.socket.disConnect()
        if not self.socket.isConnect():
            # DisConnect
            self.btnIPConnect.setDisabled(False)
            self.btnIPDisconnect.setDisabled(True)

    def btnResetReader_Click(self):
        print ('click')

    def rbTCPIP_Click(self):
        self.enableTCPIPGroup()

    def rbRS232_Click(self):
        self.enableRS232Group()

    def enableRS232Group(self):
        self.Mode = self.rs232Mode
        self.txtIP.setDisabled(True)
        self.txtPort.setDisabled(True)
        self.btnIPConnect.setDisabled(True)
        self.btnIPDisconnect.setDisabled(True)
        self.cmbSerialPort.setDisabled(False)
        self.cmbSetBauRate.setDisabled(False)
        self.btnRS232Disconnect.setDisabled(False)
        self.cmbBaudrate.setDisabled(False)
        if self.rs232.isConnect():
            self.btnRS232Connect.setDisabled(True)
            self.btnRS232Disconnect.setDisabled(False)
        else:
            self.btnRS232Connect.setDisabled(False)
            self.btnRS232Disconnect.setDisabled(True)

    def enableTCPIPGroup(self):
        self.Mode = self.socketMode
        self.cmbSerialPort.setDisabled(True)
        self.cmbSetBauRate.setDisabled(True)
        self.cmbBaudrate.setDisabled(True)
        self.btnRS232SetBaudrate.setDisabled(True)
        self.btnRS232Connect.setDisabled(True)
        self.btnRS232Disconnect.setDisabled(True)
        self.txtIP.setDisabled(False)
        self.txtPort.setDisabled(False)
        if self.socket.isConnect():
            self.btnIPConnect.setDisabled(True)
            self.btnIPDisconnect.setDisabled(False)
        else:
            self.btnIPConnect.setDisabled(False)
            self.btnIPDisconnect.setDisabled(True)

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
            elif msgTran.cmd == 0x89:
                self.process_realtime_inventory(msgTran.databarr)
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
            elif msgTran.cmd == 0x76:
                self.process_set_output_power(msgTran.databarr)
                continue
            elif msgTran.cmd == 0x77:
                self.process_get_output_power(msgTran.databarr)
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
        self.process_error_code(databarr)

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

    def process_set_output_power(self, databarr):
        self.process_error_code(databarr)

    def process_get_output_power(self, databarr):
        if len(databarr) == 1:
            print ("CurrentOutputPower: " + str(databarr[0]))
            self.txtDbm.setText(str(databarr[0]))
            return False
        elif len(databarr) == 4:
            for d in databarr:
                print (d)
            return False
        else:
            print ("Error")

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

    def btnSave_Click(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)

        msg.setWindowTitle("Save Setting Result")
        msg.setText("Save Result")
        msg.setStandardButtons(QMessageBox.Ok)

        infoTxt = "Success"
        detailTxt = ""
        try:
            #Connection Mode
            print (self.Mode)
            self.configManager.set('Mode', 'mode', str(self.Mode))
            # Network
            self.configManager.set('Network', 'ip', str(self.txtIP.text()))
            self.configManager.set('Network', 'port', str(self.txtPort.text()))
            # Reader and Antenna
            self.configManager.set('Reader', 'id', str(self.txtReaderId.text()))
            self.antennaSetting = []
            if self.chkAnt1.isChecked():
                self.antennaSetting.append('1')
            if self.chkAnt2.isChecked():
                self.antennaSetting.append('2')
            if self.chkAnt3.isChecked():
                self.antennaSetting.append('3')
            if self.chkAnt4.isChecked():
                self.antennaSetting.append('4')
            self.configManager.set('Reader', 'antenna', str(','.join(self.antennaSetting)))

            # RF
            self.configManager.set('RF', 'dbm', str(self.txtDbm.text())) #New1

            # Db Related
            self.configManager.set('Database', 'IP', str(self.txtDbIP.text()))
            self.configManager.set('Database', 'Port', str(self.txtDbPort.text()))
            self.configManager.set('Database', 'Db', str(self.txtDbName.text()))
            self.configManager.set('Database', 'Table', str(self.txtDbTableName.text()))
            self.configManager.set('Database', 'User', str(self.txtDbUser.text()))
            self.configManager.set('Database', 'Pass', str(self.txtDbPass.text()))
            self.configManager.write(open('config.ini', 'wb'))
        except Exception as ex:
            infoTxt = "Error"
            detailTxt = ex.message

        msg.setInformativeText(infoTxt)
        msg.setDetailedText(detailTxt)
        msg.exec_()

    def serial_ports(self):
        """
            Lists serial port names
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
        return result

if __name__ == '__main__':
    app = frmSetting.QtGui.QApplication(sys.argv)

    # new object
    window = MainWindow()

    # object show and start
    window.show()

    # window.tabMain.show()
    sys.exit(app.exec_())