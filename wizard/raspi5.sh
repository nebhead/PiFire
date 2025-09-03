# Post installation script that checks for Raspberry Pi 5, then removes the rpi.gpio package if it exists
if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    echo " + Raspberry Pi 5 detected, removing rpi.gpio" | tee -a /usr/local/bin/pifire/logs/wizard.log
    
    # If using 64-Bit OS use uv
    if [[ $(uname -m) == "aarch64" ]]; then
        echo " + Using 64-Bit OS, using uv to uninstall rpi.gpio" | tee -a /usr/local/bin/pifire/logs/wizard.log
        source /usr/local/bin/pifire/.venv/bin/activate
        uv python -m pip uninstall -y rpi.gpio 2>&1 | tee -a /usr/local/bin/pifire/logs/wizard.log
    else
        echo " + Using 32-Bit OS, using vanilla VENV to uninstall rpi.gpio" | tee -a /usr/local/bin/pifire/logs/wizard.log
        source /usr/local/bin/pifire/bin/activate
        python -m pip uninstall -y rpi.gpio 2>&1 | tee -a /usr/local/bin/pifire/logs/wizard.log
    fi
fi