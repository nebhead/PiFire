# This file will add the PWM pin definition if it does not already exist in the file

if grep -wq "dtoverlay=pwm,pin=13,func=4" /boot/config.txt; then 
    echo "PWM pin definition exists in /boot/config.txt" 
else 
    echo "Adding PWM definition in /boot/config.txt" 
    echo "dtoverlay=pwm,pin=13,func=4" | sudo tee -a /boot/config.txt > /dev/null
fi