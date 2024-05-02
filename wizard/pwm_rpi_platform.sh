# This file will add the PWM pin definition if it does not already exist in the file
# Enable Hardware PWM - Needed for hardware PWM support 
if test -f /boot/firmware/config.txt; then
    CONFIG='/boot/firmware/config.txt'
else
    CONFIG='/boot/config.txt'
fi

if grep -wq "dtoverlay=pwm" $CONFIG; then 
    echo "PWM pin definition exists in $CONFIG" 
else 
    echo "Adding PWM definition in $CONFIG" 
    echo "dtoverlay=pwm,gpiopin=13,func=4" | sudo tee -a $CONFIG > /dev/null
fi