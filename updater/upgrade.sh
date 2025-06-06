#!/usr/bin/env bash

# Upgrade Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/pifire/master/auto-install/upgrade.sh

echo "Starting PiFire Upgrade Script..." | tee -a /usr/local/bin/pifire/logs/upgrade.log

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo "You are root." | tee -a /usr/local/bin/pifire/logs/upgrade.log
else
    echo "SUDO will be used for the install." | tee -a /usr/local/bin/pifire/logs/upgrade.log
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo "Please install sudo. Exiting." | tee -a /usr/local/bin/pifire/logs/upgrade.log
        exit 1
    fi
fi

export HOME=$(eval echo ~${SUDO_USER})

#export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

if ! command -v /bin/curl >/dev/null 2>&1; then
    echo "WARNING: curl is required but not found. Please install curl. Exiting" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    exit 1
fi

# Setup Python VENV & Install Python dependencies
#clear
echo " * Setting up Python VENV and Installing Modules..." | tee -a /usr/local/bin/pifire/logs/upgrade.log
sleep 1
echo " - Setting Up PiFire Group" | tee -a /usr/local/bin/pifire/logs/upgrade.log
cd /usr/local/bin
$SUDO groupadd pifire 
USERNAME=$(id -un)
$SUDO usermod -a -G pifire $USERNAME
$SUDO usermod -a -G pifire root 
# Change ownership to group=pifire for all files/directories in pifire 
$SUDO chown -R $USERNAME:pifire pifire 
# Change ability for pifire group to read/write/execute 
$SUDO chmod -R 777 /usr/local/bin

echo " - Installing module dependencies... " | tee -a /usr/local/bin/pifire/logs/upgrade.log

if ! /bin/python -c "import sys; assert sys.version_info[:2] >= (3,11)" > /dev/null 2>&1; then
    echo " + System is running a python version lower than 3.11, skipping uv install.";
    # Check if /usr/local/bin/pifire/bin exists
    if [ -d "/usr/local/bin/pifire/bin" ]; then
        echo " + Legacy VENV found. " | tee -a /usr/local/bin/pifire/logs/upgrade.log
    else
        echo " + Legacy VENV not found. Creating new legacy VENV." | tee -a /usr/local/bin/pifire/logs/upgrade.log
        cd /usr/local/bin
        # Setup VENV
        /bin/python -m venv --system-site-packages pifire
    fi
    cd /usr/local/bin/pifire    
    source bin/activate
    echo " + Installing eventlet==0.30.2 and requirements" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python -m pip install "eventlet==0.30.2"
    echo " + Installing requirements.txt... " | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python -m pip install -r /usr/local/bin/pifire/auto-install/requirements.txt
    # Find all bluepy-helper executables in various possible locations
    BLUEPY_HELPERS=$(find /usr/local/bin/pifire/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo " ! No bluepy-helper found in the standard Python library locations" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo " + Setting capabilities for $helper" | tee -a /usr/local/bin/pifire/logs/upgrade.log
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo " + All bluepy-helper executables have been configured" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    fi

    # Get PIP List into JSON file
    echo " - Setting Legacy VENV flag in settings.json" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python updater.py --legacyvenv

    # Run wizard to update module dependencies
    echo " - Running wizard to update module dependencies" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python wizard.py --existing

    # Get PIP List into JSON file
    echo " - Getting PIP List into JSON file" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python updater.py --piplist
else
    echo " + System is running a python version 3.11 or greater, installing uv and latest requirements" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    # Install latest UV
    echo " + Installing UV" | tee -a /usr/local/bin/pifire/logs/upgrade.log

    if ! /bin/curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" /bin/sh; then
        echo "ERROR: Failed to download or install UV. Exiting." | tee -a /usr/local/bin/pifire/logs/upgrade.log
        exit 1
    fi

    # Setup VENV
    echo " + Setting up VENV" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    cd /usr/local/bin/pifire
    uv venv --system-site-packages

    # Activate VENV
    source .venv/bin/activate
    
    # Install latest eventlet
    echo " + Installing latest eventlet" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    uv pip install eventlet
    echo " + Installing requirements.txt... " | tee -a /usr/local/bin/pifire/logs/upgrade.log      
    uv pip install -r /usr/local/bin/pifire/auto-install/requirements.txt

    # Find all bluepy-helper executables in various possible locations
    BLUEPY_HELPERS=$(find /usr/local/bin/pifire/.venv/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo " ! No bluepy-helper found in the standard Python library locations" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo " + Setting capabilities for $helper" | tee -a /usr/local/bin/pifire/logs/upgrade.log
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo " + All bluepy-helper executables have been configured" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    fi

    # Set UV flag in settings.json
    echo " - Setting UV flag in settings.json" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python updater.py --uv

    # Run wizard to update module dependencies
    echo " - Running wizard to update module dependencies" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python wizard.py --existing

    # Get PIP List into JSON file
    echo " - Getting PIP List into JSON file" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    python updater.py --piplist
fi

### Setup Supervisor to Start Apps on Boot / Restart on Failures
echo " + Configuring Supervisord..." | tee -a /usr/local/bin/pifire/logs/upgrade.log

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
if ! python -c "import sys; assert sys.version_info[:2] >= (3,11)" > /dev/null 2>&1; then
    echo " + System is running a python version lower than 3.11, skipping supervisor configuration update" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    cd /usr/local/bin/pifire/auto-install/supervisor/legacy
else
    echo " + System is running a python version 3.11 or greater, configuring supervisor for uv" | tee -a /usr/local/bin/pifire/logs/upgrade.log
    cd /usr/local/bin/pifire/auto-install/supervisor
fi
# Add the current username to the configuration files 
USERNAME=$(id -un)
echo "user=$USERNAME" | tee -a control.conf > /dev/null
echo "user=$USERNAME" | tee -a webapp.conf > /dev/null
$SUDO cp *.conf /etc/supervisor/conf.d/

echo " - Upgrade Script Finished." | tee -a /usr/local/bin/pifire/logs/upgrade.log
