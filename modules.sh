#!/usr/bin/env bash

# USAGE: At the bash prompt: 
#
# $ bash modules.sh 
#

# Must be root to configure settings
if [[ $EUID -eq 0 ]];then
    echo "You are root."
else
    echo "SUDO will be used for the install."
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo "Please install sudo or run this as root."
        exit 1
    fi
fi

# Find the rows and columns. Will default to 80x24 if it can not be detected.
screen_size=$(stty size 2>/dev/null || echo 24 80)
rows=$(echo $screen_size | awk '{print $1}')
columns=$(echo $screen_size | awk '{print $2}')

# Divide by two so the dialogs take up half of the screen.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# If the screen is small, modify defaults
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))

# =========================================================================
# Configure Settings for Modules
# =========================================================================

GRILLPLAT=$(whiptail --title "Select your Grill Platform module to use." --radiolist "Select the Grill Platform module for PiFire to use.  This module initializes GPIOs to control input / output to Grill Platform components like the fan, auger, igniter, etc." 20 78 2 "PIFIRE" "Standard Rasperry Pi <- DEFAULT" ON "PROTOTYPE" "Prototype - Not Platform Dependant (for test only)" OFF 3>&1 1>&2 2>&3)

if [[ $GRILLPLAT = "PIFIRE" ]];then
    $SUDO python3 settings.py -g pifire
	TRIGGERLEVEL=$(whiptail --title "Set the Trigger Level" --radiolist "Select your relay's trigger level.  (Trigger level High or trigger Low)" 20 78 2 "LOW" "Active Low/Trigger Low" ON "HIGH" "Active High/Trigger High" OFF 3>&1 1>&2 2>&3)
	if [[ $TRIGGERLEVEL = "LOW" ]];then
		python3 settings.py -t LOW
	fi
	if [[ $TRIGGERLEVEL = "HIGH" ]];then
		python3 settings.py -t HIGH
	fi
fi

if [[ $GRILLPLAT = "PROTOTYPE" ]];then
    $SUDO python3 settings.py -g prototype
fi

ADC=$(whiptail --title "Select your ADC module to use." --radiolist "This module gets temperature data from the attached probes such as the RTD Grill Probe, the food probes, etc." 20 78 2 "ADS1115" "Standard ADC <- Default" ON "PROTOTYPE" "Prototype/Simulated (for test only)" OFF 3>&1 1>&2 2>&3)

if [[ $ADC = "ADS1115" ]];then
    $SUDO python3 settings.py -a ads1115
	$SUDO pip3 install ADS1115
fi

if [[ $ADC = "PROTOTYPE" ]];then
    $SUDO python3 settings.py -a prototype
fi

UNITS=$(whiptail --title "Select Temperature Units." --radiolist "Select the temperature units to use globally. (this can be changed later)" 20 78 2 "F" "Fahrenheit <- Default" ON "C" "Celsius" OFF 3>&1 1>&2 2>&3)

if [[ $UNITS = "F" ]];then
    $SUDO python3 settings.py -u F
fi

if [[ $UNITS = "C" ]];then
    $SUDO python3 settings.py -u C
fi

DISPLAY=$(whiptail --title "Select your Display module to use." \
                   --radiolist "Select display type (and input) module for PiFire to use.  Some displays may also have menu button functions indicated by a B appended to the name." 20 78 8 \
                   "SSD1306" "OLED Display (128x64) <- DEFAULT" ON \
                   "SSD1306B" "OLED Display (128x64) w/Button Input" OFF \
                   "ST7789P" "IPS/TFT SPI Display (240x240)P-Pimoroni Libs" OFF \
                   "ILI9341" "TFT Color Display (240x320)" OFF \
                   "ILI9341B" "TFT Color Display (240x320) w/Buttons" OFF \
                   "ILI9341_encoder" "TFT Color Display (240x320) w/Encoder (KY040)" OFF \
                   "PROTOTYPE" "Prototype/Console Output (for test only)" OFF \
                   "PYGAME" "Prototype/PyGame Desktop Output (for test only)" OFF \
                   "PYGAME240320" "Prototype/PyGame (240x320) (for test only)" OFF \
                   "PYGAME240320B" "Prototype/PyGame B(240x320) (for test only)" OFF \
                   "PYGAME64128" "Prototype/PyGame (64x128) (for test only)" OFF \
                   3>&1 1>&2 2>&3)

if [[ $DISPLAY = "SSD1306" ]];then
    $SUDO python3 settings.py -d ssd1306
	$SUDO pip3 install luma.oled
fi

if [[ $DISPLAY = "SSD1306B" ]];then
    $SUDO python3 settings.py -d ssd1306b
	$SUDO pip3 install luma.oled
	BUTTONSLEVEL=$(whiptail --title "Set the Button Level" --radiolist "Select how your button hardware is configured. (HIGH - Pullups, LOW - Pulldowns)" 20 78 2 "LOW" "Pulldowns" ON "HIGH" "Pullups" OFF 3>&1 1>&2 2>&3)
	if [[ $BUTTONSLEVEL = "LOW" ]];then
		$SUDO python3 settings.py -b LOW
	fi
	if [[ $BUTTONSLEVEL = "HIGH" ]];then
		$SUDO python3 settings.py -b HIGH
	fi
fi

if [[ $DISPLAY = "ST7789P" ]];then
    $SUDO python3 settings.py -d st7789p
	echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO apt install python3-rpi.gpio python3-spidev python3-pip python3-pil python3-numpy
    $SUDO pip3 install st7789
fi

if [[ $DISPLAY = "ILI9341" ]];then
    $SUDO python3 settings.py -d ili9341
	echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO pip3 install luma.lcd
fi

if [[ $DISPLAY = "ILI9341_encoder" ]];then
    $SUDO python3 settings.py -d ili9341_encoder
	echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO pip3 install pyky040==0.1.4
fi

if [[ $DISPLAY = "ILI9341B" ]];then
    $SUDO python3 settings.py -d ili9341b
	echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO pip3 install luma.lcd
	BUTTONSLEVEL=$(whiptail --title "Set the Button Level" --radiolist "Select how your button hardware is configured. (HIGH - Pullups, LOW - Pulldowns)" 20 78 2 "LOW" "Pulldowns" ON "HIGH" "Pullups" OFF 3>&1 1>&2 2>&3)
	if [[ $BUTTONSLEVEL = "LOW" ]];then
		$SUDO python3 settings.py -b LOW
	fi
	if [[ $BUTTONSLEVEL = "HIGH" ]];then
		$SUDO python3 settings.py -b HIGH
	fi
fi

if [[ $DISPLAY = "PROTOTYPE" ]];then
    $SUDO python3 settings.py -d prototype
fi

if [[ $DISPLAY = "PYGAME" ]];then
    $SUDO python3 settings.py -d pygame
	$SUDO pip3 install pygame 
fi

if [[ $DISPLAY = "PYGAME240320" ]];then
    $SUDO python3 settings.py -d pygame_240x320
	$SUDO pip3 install pygame 
fi

if [[ $DISPLAY = "PYGAME240320B" ]];then
    $SUDO python3 settings.py -d pygame_240x320b
	$SUDO pip3 install pygame 
fi

if [[ $DISPLAY = "PYGAME64128" ]];then
    $SUDO python3 settings.py -d pygame_64x128
	$SUDO pip3 install pygame 
fi

DIST=$(whiptail --title "Select your Range module to use." --radiolist "Optional distance sensor for hopper/pellet level reporting.  Default is prototype/none, which is equivalent to no attached sensor." 20 78 3 "PROTOTYPE" "Prototype/None <- DEFAULT" ON "VL53L0X" "Time of Flight Light Range Sensor" OFF "HCSR04" "Ultrasonic Range Sensor" OFF 3>&1 1>&2 2>&3)

if [[ $DIST = "VL53L0X" ]];then
    $SUDO python3 settings.py -r vl53l0x 
	$SUDO apt install python3-smbus -y
    $SUDO pip3 install git+https://github.com/pimoroni/VL53L0X-python.git
fi

if [[ $DIST = "HCSR04" ]];then
    $SUDO python3 settings.py -r hcsr04
	$SUDO pip3 install hcsr04sensor
fi

if [[ $DIST = "PROTOTYPE" ]];then
    $SUDO python3 settings.py -r prototype
fi
