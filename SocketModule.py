# coding=UTF-8
# Echo client program
import socket

class SocketModule:
    def __init__(self, host, port):
        self.Host = host
        self.Port = port
        self.Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.isconnect = False

    def connect(self):
        self.Socket.connect((self.Host, self.Port))
        self.isconnect = True

    def isConnect(self):
        return self.isconnect

    def sendCmd(self, cmd):
        self.Socket.send(cmd)
        try:
            data = self.Socket.recv(4096)
            return data
        except Exception as err:
            print ("GetReceiveDataError: {0}".format(err.message))
        # try:
        #     self.Socket.send(cmd)
        #     data = self.Socket.recv(4096)
        #     return data
        # except socket.timeout as tout:
        #     print "Socket Timeout: {0}".format(tout.message)
        # except socket.error as err:
        #     print "Socket Error: {0}".format(err.message)
        return None

    def disConnect(self):
        #self.Socket.shutdown(socket.SHUT_RDWR)
        self.Socket.close()
        self.isconnect = False

    def readData(self):
        data = self.Socket.recv(4096)
        return data




