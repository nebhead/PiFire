#!/usr/bin/env python3

# *****************************************
# PiFire OEM Interface Library
# *****************************************
#
# Description: This library supports 
#  controlling the PiFire Outputs, alongside 
#  the OEM controller outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import RPi.GPIO as GPIO
from time import sleep
from common import ReadCurrent 

class GrillPlatform:

    def __init__(self, outpins, inpins, triggerlevel='LOW'):
        self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
        self.inpins = inpins # { 'selector' : 17 }
        frequency = 1000
        self.duty = 50
        
        
        if triggerlevel == 'LOW': 
            # Defines for Active LOW relay
            self.RELAY_ON = 0
            self.RELAY_OFF = 1
            
        else:
            # Defines for Active HIGH relay
            self.RELAY_ON = 1
            self.RELAY_OFF = 0
            

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        for item in self.inpins:
            GPIO.setup(self.inpins[item], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if GPIO.input(self.inpins['selector']) == 0:
            GPIO.setup(self.outpins['power'], GPIO.OUT, initial=self.RELAY_ON)
            GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=self.RELAY_OFF)
            GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=self.RELAY_OFF)
            GPIO.setup(self.outpins['dcfan'], GPIO.OUT)
            self.pi_pwm = GPIO.PWM(self.outpins['dcfan'], frequency)		#create PWM instance with frequency
            self.pi_pwm.start(0)
            GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=self.RELAY_OFF)
        else:
            GPIO.setup(self.outpins['power'], GPIO.OUT, initial=self.RELAY_OFF)
            GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=self.RELAY_OFF)
            GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=self.RELAY_OFF)
            GPIO.setup(self.outpins['dcfan'], GPIO.OUT)
            self.pi_pwm = GPIO.PWM(self.outpins['dcfan'], frequency)		#create PWM instance with frequency
            self.pi_pwm.start(0)
            GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=self.RELAY_OFF)

    def GetTemp(self, current_GT):
        self.current_GT = self.WorkCycle['AvgGT']

    def AugerOn(self):
        GPIO.output(self.outpins['auger'], self.RELAY_ON)

    def AugerOff(self):
        GPIO.output(self.outpins['auger'], self.RELAY_OFF)

    def VarFanOn(self):
        WAIT_TIME = 1  # [s] Time to wait between each refresh
        MIN_TEMP = 65
        MAX_TEMP = 400
        FAN_LOW = 10
        FAN_HIGH = 50
        FAN_OFF = 0
        FAN_MAX = 50
        setFanSpeed = 10
        current_temps = ReadCurrent()
        temp = float(current_temps[0])
        #temp = float(self.current_temp)
        if temp < MIN_TEMP:
            setFanSpeed = (FAN_OFF)
            print("Fan OFF") # Uncomment for testing
        # Set fan speed to MAXIMUM if the temperature is above MAX_TEMP
        elif temp > MAX_TEMP:
            setFanSpeed = (FAN_MAX)
            print("Fan MAX") # Uncomment for testing
        # Caculate dynamic fan speed
        else:
            step = (FAN_HIGH - FAN_LOW)/(MAX_TEMP - MIN_TEMP)   
            temp -= MIN_TEMP
            setFanSpeed = (FAN_LOW + ( round(temp) * step ))
            self.duty = setFanSpeed
            self.pi_pwm.start(setFanSpeed)
            #print(FAN_LOW + ( round(temp) * step )) # Uncomment for testing
        return ()
        
    def FanOn(self):
        GPIO.output(self.outpins['fan'], self.RELAY_ON)
        self.pi_pwm.start(self.duty)

    def FanOff(self):
        GPIO.output(self.outpins['fan'], self.RELAY_OFF)
        self.pi_pwm.start(0)

    def FanToggle(self):
        if(GPIO.input(self.outpins['fan']) == self.RELAY_ON):
            GPIO.output(self.outpins['fan'], self.RELAY_OFF)
        else:
            GPIO.output(self.outpins['fan'], self.RELAY_ON)

    def IgniterOn(self):
        GPIO.output(self.outpins['igniter'], self.RELAY_ON)

    def IgniterOff(self):
        GPIO.output(self.outpins['igniter'], self.RELAY_OFF)

    def PowerOn(self):
        GPIO.output(self.outpins['power'], self.RELAY_ON)

    def PowerOff(self):
        GPIO.output(self.outpins['power'], self.RELAY_OFF)

    def GetInputStatus(self):
        return (GPIO.input(self.inpins['selector']))

    def GetOutputStatus(self):
        self.current = {}
        for item in self.outpins:
            self.current[item] = GPIO.input(self.outpins[item])
        return self.current

    def FanRamp(self):
        self.pi_pwm.start(0)
        for duty in range(0,40,1):
            self.pi_pwm.ChangeDutyCycle(duty) #provide duty cycle in the range 0-100
            sleep(0.1)
            sleep(0.05)
    
        for duty in range(40,-1,-1):
            self.pi_pwm.ChangeDutyCycle(duty)
            sleep(0.1)
            sleep(0.05)