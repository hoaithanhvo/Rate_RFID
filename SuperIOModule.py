import RPi.GPIO as RGPIO

class GPIO:
    
    def __init__(self):
        self.DI1 = 37
        self.DI2 = 35
        self.DI3 = 33
        self.DI4 = 31
        self.DO1 = 40
        self.DO2 = 38
        self.DO3 = 36
        self.DO4 = 32
        self.on = True
        self.off = False
        self.init_gpio()
        self.blStart = 0
        self.blSensor = False
        self.isDI = False
        self.DIList = []
    
    def init_gpio(self):
        RGPIO.setmode(RGPIO.BOARD)
        RGPIO.setwarnings(False)
        RGPIO.setup(self.DI1, RGPIO.IN, pull_up_down=RGPIO.PUD_UP)
        RGPIO.setup(self.DI2, RGPIO.IN, pull_up_down=RGPIO.PUD_UP)
        RGPIO.setup(self.DI3, RGPIO.IN, pull_up_down=RGPIO.PUD_UP)
        RGPIO.setup(self.DI4, RGPIO.IN, pull_up_down=RGPIO.PUD_UP)
        RGPIO.setup(self.DO1, RGPIO.OUT)
        RGPIO.setup(self.DO2, RGPIO.OUT)
        RGPIO.setup(self.DO3, RGPIO.OUT)
        RGPIO.setup(self.DO4, RGPIO.OUT)

    
    def set_gpio(self, pin, value):
        RGPIO.output(pin, value)
    
    def get_gpio(self, pin):
        button_state = RGPIO.input(pin)
        return button_state
    
    def detect_sensor(self):
        self.blSensor = False
        first = not self.get_gpio(self.DI1)
        second = not self.get_gpio(self.DI2)
        third = not self.get_gpio(self.DI3)
        forth = not self.get_gpio(self.DI4)
        #second = self.get_gpio(self.second_sensor)
        #third = self.get_gpio(self.third_sensor)
        
        if self.isDI:
            if len(self.DIList) > 0:
                if "1" in self.DIList:
                    self.blSensor = self.blSensor or first
                if "2" in self.DIList:
                    self.blSensor = self.blSensor or second
                if "3" in self.DIList:
                    self.blSensor = self.blSensor or third
                if "4" in self.DIList:
                    self.blSensor = self.blSensor or forth
            else:
                self.blSensor = False
        else:
            self.blSensor = False
            
    def detect_no_sensor(self):
        first = self.get_gpio(self.DI1)
        second = self.get_gpio(self.DI2)
        third = self.get_gpio(self.DI3)
        forth = self.get_gpio(self.DI4)
        self.blSensor = not (first)
    
    def inventory_check(self):
        if self.blSensor or self.blStart:
            return True
        else:
            return False
    
    def btn_start_click(self):
        self.blStart = True
    
    def btn_stop_click(self):
        self.blStart = False
        
    def set_blStart(self, state):
        self.blStart = state
 
