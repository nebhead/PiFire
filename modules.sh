#!/usr/bin/env bash

# USAGE: At the bash prompt: 
#
# $ bash modules.sh 
#


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
    python3 settings.py -g pifire
fi

if [[ $GRILLPLAT = "PROTOTYPE" ]];then
    python3 settings.py -g prototype
fi

ADC=$(whiptail --title "Select your ADC module to use." --radiolist "This module gets temperature data from the attached probes such as the RTD Grill Probe, the food probes, etc." 20 78 2 "ADS1115" "Standard ADC <- Default" ON "PROTOTYPE" "Prototype/Simulated (for test only)" OFF 3>&1 1>&2 2>&3)

if [[ $ADC = "ADS1115" ]];then
    python3 settings.py -a ads1115
fi

if [[ $ADC = "PROTOTYPE" ]];then
    python3 settings.py -a prototype
fi

DISPLAY=$(whiptail --title "Select your Display module to use." --radiolist "Select display type (and input) module for PiFire to use.  Some displays may also have menu button functions indicated by a B appended to the name." 20 78 8 "SSD1306" "OLED Display (128x64) <- DEFAULT" ON "SSD1306B" "OLED Display (128x64) w/Button Input" OFF "ST7789P" "IPS/TFT SPI Display (240x240)P-Pimoroni Libs" OFF "ILI9341" "TFT Color Display (240x320)" OFF "ILI9341B" "TFT Color Display (240x320) w/Buttons" OFF "PROTOTYPE" "Prototype/Console Output (for test only)" OFF "PYGAME" "Prototype/PyGame Desktop Output (for test only)" OFF "PYGAME240320" "Prototype/PyGame (240x320) (for test only)" OFF "PYGAME240320B" "Prototype/PyGame B(240x320) (for test only)" OFF 3>&1 1>&2 2>&3)

if [[ $DISPLAY = "SSD1306" ]];then
    python3 settings.py -d ssd1306
fi

if [[ $DISPLAY = "SSD1306B" ]];then
    python3 settings.py -d ssd1306b
fi

if [[ $DISPLAY = "ST7789P" ]];then
    python3 settings.py -d st7789p
fi

if [[ $DISPLAY = "ILI9341" ]];then
    python3 settings.py -d ili9341
fi

if [[ $DISPLAY = "ILI9341B" ]];then
    python3 settings.py -d ili9341b
fi

if [[ $DISPLAY = "PROTOTYPE" ]];then
    python3 settings.py -d prototype
fi

if [[ $DISPLAY = "PYGAME" ]];then
    python3 settings.py -d pygame
fi

if [[ $DISPLAY = "PYGAME240320" ]];then
    python3 settings.py -d pygame_240x320
fi

if [[ $DISPLAY = "PYGAME240320B" ]];then
    python3 settings.py -d pygame_240x320b
fi

DIST=$(whiptail --title "Select your Range module to use." --radiolist "Optional distance sensor for hopper/pellet level reporting.  Default is prototype/none, which is equivalent to no attached sensor." 20 78 3 "PROTOTYPE" "Prototype/None <- DEFAULT" ON "VL53L0X" "Time of Flight Light Range Sensor" OFF "HCSR04" "Ultrasonic Range Sensor" OFF 3>&1 1>&2 2>&3)

if [[ $DIST = "VL53L0X" ]];then
    python3 settings.py -r vl53l0x 
fi

if [[ $DIST = "HCSR04" ]];then
    python3 settings.py -r hcsr04
fi

if [[ $DIST = "PROTOTYPE" ]];then
    python3 settings.py -r prototype
fi
