#!/usr/bin/env bash

# Upgrade Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/pifire/master/auto-install/upgrade.sh

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
        echo "Please install sudo."
        exit 1
    fi
fi

# Starting actual steps of the upgrade
#clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Update... (This could take several minutes)        **"
echo "**                                                                     **"
echo "*************************************************************************"
#$SUDO apt update
#clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Upgrade... (This could take several minutes)       **"
echo "**                                                                     **"
echo "*************************************************************************"
#$SUDO apt upgrade -y

# Refresh default APT dependencies
#clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Installing Dependencies... (This could take several minutes)   **"
echo "**                                                                     **"
echo "*************************************************************************"
#$SUDO apt install python3-dev python3-pip python3-venv python3-rpi.gpio python3-scipy nginx git supervisor ttf-mscorefonts-installer redis-server gfortran libatlas-base-dev libopenblas-dev liblapack-dev libopenjp2-7 libglib2.0-dev -y

# Setup Python VENV & Install Python dependencies
#clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Setting up Python VENV and Installing Modules...               **"
echo "**            (This could take several minutes)                        **"
echo "**                                                                     **"
echo "*************************************************************************"
echo ""
echo " - Setting Up PiFire Group"
cd /usr/local/bin
$SUDO groupadd pifire 
$SUDO usermod -a -G pifire $USER 
$SUDO usermod -a -G pifire root 
# Change ownership to group=pifire for all files/directories in pifire 
$SUDO chown -R $USER:pifire pifire 
# Change ability for pifire group to read/write/execute 
$SUDO chmod -R 777 /usr/local/bin

echo " - Installing module dependencies... "

if ! python -c "import sys; assert sys.version_info[:2] >= (3,11)" > /dev/null 2>&1; then
    echo " + System is running a python version lower than 3.11, skipping uv install.";
    # Check if /usr/local/bin/pifire/bin exists
    if [ -d "/usr/local/bin/pifire/bin" ]; then
        echo " + Legacy VENV found. "
    else
        echo " + Legacy VENV not found. Creating new legacy VENV."
        cd /usr/local/bin
        # Setup VENV
        python -m venv --system-site-packages pifire
    fi
    cd /usr/local/bin/pifire    
    source bin/activate
    echo " + Installing eventlet==0.30.2 and requirements"
    python -m pip install "eventlet==0.30.2"
    echo " + Installing requirements.txt... "
    python -m pip install -r /usr/local/bin/pifire/auto-install/requirements.txt
    # Find all bluepy-helper executables in various possible locations
    BLUEPY_HELPERS=$(find /usr/local/bin/pifire/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo "No bluepy-helper found in the standard Python library locations"
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo "Setting capabilities for $helper"
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo "All bluepy-helper executables have been configured"
    fi

    # Get PIP List into JSON file
    echo " - Setting Legacy VENV flag in settings.json"
    python updater.py --legacyvenv

    # Run wizard to update module dependencies
    echo " - Running wizard to update module dependencies"
    python wizard.py --existing

    # Get PIP List into JSON file
    echo " - Getting PIP List into JSON file"
    python updater.py --piplist
else
    echo " + System is running a python version 3.11 or greater, installing uv and latest requirements"
    # Install latest UV
    echo " + Installing UV"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

    # Setup VENV
    echo " + Setting up VENV"
    cd /usr/local/bin/pifire
    uv venv --system-site-packages

    # Activate VENV
    source .venv/bin/activate
    
    # Install latest eventlet
    echo " + Installing latest eventlet"
    uv pip install eventlet
    echo " + Installing requirements.txt... "      
    uv pip install -r /usr/local/bin/pifire/auto-install/requirements.txt

    # Find all bluepy-helper executables in various possible locations
    BLUEPY_HELPERS=$(find /usr/local/bin/pifire/.venv/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo "No bluepy-helper found in the standard Python library locations"
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo "Setting capabilities for $helper"
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo "All bluepy-helper executables have been configured"
    fi

    # Set UV flag in settings.json
    echo " - Setting UV flag in settings.json"
    python updater.py --uv

    # Run wizard to update module dependencies
    echo " - Running wizard to update module dependencies"
    python wizard.py --existing

    # Get PIP List into JSON file
    echo " - Getting PIP List into JSON file"
    python updater.py --piplist
fi

### Setup Supervisor to Start Apps on Boot / Restart on Failures
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Supervisord...                                     **"
echo "**                                                                     **"
echo "*************************************************************************"

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
if ! python -c "import sys; assert sys.version_info[:2] >= (3,11)" > /dev/null 2>&1; then
    echo " + System is running a python version lower than 3.11, skipping supervisor configuration update";
    cd /usr/local/bin/pifire/auto-install/supervisor/legacy
else
    echo " + System is running a python version 3.11 or greater, configuring supervisor for uv"
    cd /usr/local/bin/pifire/auto-install/supervisor
fi
# Add the current username to the configuration files 
echo "user=$USER" | tee -a control.conf > /dev/null
echo "user=$USER" | tee -a webapp.conf > /dev/null
$SUDO cp *.conf /etc/supervisor/conf.d/

# Restart Supervisor
$SUDO service supervisor restart

echo " - Upgrade Script Finished."
