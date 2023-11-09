# Adds permissions to backlight and backlight power for connected screen (DSI)
echo 'SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"' | sudo tee -a /etc/udev/rules.d/backlight-permissions.rules > /dev/null
echo 'Rules added to /etc/udev/rules.d/backlight-permissions'