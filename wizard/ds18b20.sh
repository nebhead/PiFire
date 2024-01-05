# This file will add the kernel support for 1-wire on pin 31 (GPIO 6)

if grep -wq "dtoverlay=w1-gpio,gpiopin=6,pullup=\"y\"" /boot/config.txt; then 
    echo "1-Wire enabling already exists in /boot/config.txt" 
else 
    echo "Adding 1-Wire support in /boot/config.txt" 
    echo "dtoverlay=w1-gpio,gpiopin=6,pullup=\"y\"" | sudo tee -a /boot/config.txt > /dev/null
fi