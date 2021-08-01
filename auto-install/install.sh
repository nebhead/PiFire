#!/usr/bin/env bash

# Automatic Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/pifire/master/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/pifire/master/auto-install/install.sh | bash
#
# NOTE: Pre-Requisites to run Raspi-Config first.  See README.md.

# Must be root to install
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

# Display the welcome dialog
whiptail --msgbox --backtitle "Welcome" --title "PiFire Automated Installer" "This installer will transform your Raspberry Pi into a connected Smoker Controller.  NOTE: This installer is intended to be run on a fresh install of Raspbian Lite Stretch +.  This script is currently in Alpha testing so there may be bugs." ${r} ${c}

# Starting actual steps for installation
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting /tmp to RAM based storage in /etc/fstab                **"
echo "**                                                                     **"
echo "*************************************************************************"
echo "tmpfs /tmp  tmpfs defaults,noatime 0 0" | sudo tee -a /etc/fstab > /dev/null
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Update... (This could take several minutes)        **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt update
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Upgrade... (This could take several minutes)       **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt upgrade -y

# Install dependancies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Installing Dependancies... (This could take several minutes)   **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt install python3-dev python3-pip python3-rpi.gpio python3-pil libfreetype6-dev libjpeg-dev build-essential libopenjp2-7 libtiff5 nginx git gunicorn3 supervisor ttf-mscorefonts-installer -y
$SUDO pip3 install flask
$SUDO pip3 install pushbullet.py

# Grab project files
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Cloning PiFire from GitHub...                                  **"
echo "**                                                                     **"
echo "*************************************************************************"
git clone https://github.com/nebhead/pifire

### Setup nginx to proxy to gunicorn
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring nginx...                                           **"
echo "**                                                                     **"
echo "*************************************************************************"
# Move into install directory
cd ~/pifire

# Delete default configuration
$SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
$SUDO cp pifire.nginx /etc/nginx/sites-available/pifire

# Create link in sites-enabled
$SUDO ln -s /etc/nginx/sites-available/pifire /etc/nginx/sites-enabled

# Restart nginx
$SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Supervisord...                                     **"
echo "**                                                                     **"
echo "*************************************************************************"

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for the installation then make sure you edit the *.conf files appropriately
cd ~/pifire/supervisor

$SUDO cp *.conf /etc/supervisor/conf.d/

SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Setup Completed" "You now should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
   echo "No WebUI Setup."
fi

# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start

clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Modules...                                         **"
echo "**                                                                     **"
echo "*************************************************************************"

cd ~/pifire # Change dir to where the settings.py application is (and common.py)

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
    $SUDO pip3 install ADS1115
fi

if [[ $ADC = "PROTOTYPE" ]];then
    python3 settings.py -a prototype
fi

DISPLAY=$(whiptail --title "Select your Display module to use." --radiolist "Select display type (and input) module for PiFire to use.  Some displays may also have menu button functions indicated by a B appended to the name." 20 78 8 "SSD1306" "OLED Display (128x64) <- DEFAULT" ON "SSD1306B" "OLED Display (128x64) w/Button Input" OFF "ST7789P" "IPS/TFT SPI Display (240x240)P-Pimoroni Libs" OFF "ILI9341" "TFT Color Display (240x320)" OFF "ILI9341B" "TFT Color Display (240x320) w/Buttons" OFF "PROTOTYPE" "Prototype/Console Output (for test only)" OFF "PYGAME" "Prototype/PyGame Desktop Output (for test only)" OFF "PYGAME240320" "Prototype/PyGame (240x320) (for test only)" OFF 3>&1 1>&2 2>&3)

if [[ $DISPLAY = "SSD1306" ]];then
    python3 settings.py -d ssd1306
    $SUDO pip3 install luma.oled
fi

if [[ $DISPLAY = "SSD1306B" ]];then
    python3 settings.py -d ssd1306b
    $SUDO pip3 install luma.oled
fi

if [[ $DISPLAY = "ST7789P" ]];then
    python3 settings.py -d st7789p
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO apt install python3-rpi.gpio python3-spidev python3-pip python3-pil python3-numpy
    $SUDO pip3 install st7789
fi

if [[ $DISPLAY = "ILI9341" ]];then
    python3 settings.py -d ili9341
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO pip3 install luma.lcd
fi

if [[ $DISPLAY = "ILI9341B" ]];then
    python3 settings.py -d ili9341b
    echo "dtparam=spi=on" | sudo tee -a /boot/config.txt > /dev/null
    $SUDO pip3 install luma.lcd
fi

if [[ $DISPLAY = "PROTOTYPE" ]];then
    python3 settings.py -d prototype
fi

if [[ $DISPLAY = "PYGAME" ]];then
    python3 settings.py -d pygame
    $SUDO pip3 install pygame 
fi

if [[ $DISPLAY = "PYGAME240320" ]];then
    python3 settings.py -d pygame_240x320
    $SUDO pip3 install pygame 
fi

DIST=$(whiptail --title "Select your Range module to use." --radiolist "Optional distance sensor for hopper/pellet level reporting.  Default is prototype/none, which is equivalent to no attached sensor." 20 78 3 "PROTOTYPE" "Prototype/None <- DEFAULT" ON "VL53L0X" "Time of Flight Light Range Sensor" OFF "HCSR04" "Ultrasonic Range Sensor" OFF 3>&1 1>&2 2>&3)

if [[ $DIST = "VL53L0X" ]];then
    python3 settings.py -r vl53l0x
    $SUDO apt install python3-smbus -y
    $SUDO pip3 install git+https://github.com/pimoroni/VL53L0X-python.git
fi

if [[ $DIST = "HCSR04" ]];then
    python3 settings.py -r hcsr04
    $SUDO pip3 install hcsr04sensor
fi

if [[ $DIST = "PROTOTYPE" ]];then
    python3 settings.py -r prototype
fi

# Rebooting
whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  Enjoy!" ${r} ${c}
clear
$SUDO reboot
