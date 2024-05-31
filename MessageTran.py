class Messagetran:
    def __init__(self, cmd, databarr):
        self.__cmd = cmd
        self.__databarr = databarr

    @property
    def cmd(self):
        return self.__cmd

    @property
    def databarr(self):
        return self.__databarr
