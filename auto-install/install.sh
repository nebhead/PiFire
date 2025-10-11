#!/usr/bin/env bash

# Automatic Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/pifire/main/auto-install/install.sh | bash
#
# NOTE: Pre-Requisites to run Raspi-Config first.  See README.md.
# 
# Usage: 
# ./install.sh [-dev]
# -dev: Use this option to run the installation script from the development branch of PiFire instead of the main branch.
#        This is useful for testing new features or bug fixes that are not yet in the main branch.
#        If this option is not used, the main branch will be installed by default.
# -devrepo: Used to pull the development branch repository instead of the main branch.
#          Uses the current installation script running with the development branch of the repository.
#          This is useful for testing new features or bug fixes that are not yet in the main branch.
#          If this option is not used, the main branch will be installed by default.
#          Note: This option is ignored if -dev is also used.
#          Example usage: curl https://raw.githubusercontent.com/nebhead/pifire/development/auto-install/install.sh | bash -s -- -devrepo
# -venv: Use this option to force vanilla venv install
# -uv:   Use this option to force the use of UV 

# Install script version variable for logging
INSTALL_SCRIPT_VERSION="1.10.x"
DEV_INSTALLER="false"
for arg in "$@"; do
  if [[ "$arg" == "-dev" ]]; then
    DEV_INSTALLER="true"
  fi
done

DEV_REPO="false"
for arg in "$@"; do
  if [[ "$arg" == "-devrepo" ]]; then
    DEV_REPO="true"
  fi
done

# Create logs directory if it doesn't exist
mkdir -p ~/logs

# Check if -dev flag is used and run install from development branch and exit this script
if [[ $DEV_INSTALLER == "true" ]]; then
    echo " + Running installation script from development branch..." | tee -a ~/logs/pifire_install.log
    # Pass through all arguments except -dev to the development branch installer
    # Build a new argument list excluding -dev
    passthrough_args=()
    for arg in "$@"; do
        if [[ "$arg" != "-dev" ]]; then
            passthrough_args+=("$arg")
        fi
    done
    echo " + Passing through arguments to development branch installer: ${passthrough_args[*]}" | tee -a ~/logs/pifire_install.log
    curl -SL https://raw.githubusercontent.com/nebhead/pifire/development/auto-install/install.sh | bash -s -- -devrepo "${passthrough_args[@]}"
    exit 0
elif [[ $DEV_REPO == "true" ]]; then
    echo " + Running installation script from development branch based on version $INSTALL_SCRIPT_VERSION..." | tee -a ~/logs/pifire_install.log
else
    echo " + Running installation script from main branch based on version $INSTALL_SCRIPT_VERSION..." | tee -a ~/logs/pifire_install.log
fi

# Start logging
echo "*************************************************************************" | tee ~/logs/pifire_install.log
echo "PiFire Installation Started at $(date '+%Y-%m-%d %H:%M:%S')" | tee ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo " ** Logging to ~/logs/pifire_install.log **" | tee -a ~/logs/pifire_install.log

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo " + You are root." | tee -a ~/logs/pifire_install.log
else
    echo " + SUDO will be used for the install." | tee -a ~/logs/pifire_install.log
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo " !! Installation Failed, 'sudo' not found. Please install sudo.  Exiting" | tee -a ~/logs/pifire_install.log
        exit 1
    fi
fi

# Detect OS architecture
ARCH=$(uname -m)
echo " + Detecting system architecture: $ARCH" | tee -a ~/logs/pifire_install.log

case $ARCH in
    aarch64)
        echo " + 64-bit ARM OS detected (Raspberry Pi running 64-bit OS)" | tee -a ~/logs/pifire_install.log
        OS_BITS="64"
        ;;
    armv7l|armv6l)
        echo " + 32-bit ARM OS detected (Raspberry Pi running 32-bit OS)" | tee -a ~/logs/pifire_install.log
        OS_BITS="32"
        ;;
    *)
        echo " !! Warning: Non-standard Raspberry Pi architecture detected: $ARCH" | tee -a ~/logs/pifire_install.log
        echo " !! This script is designed for Raspberry Pi systems" | tee -a ~/logs/pifire_install.log
        if ! whiptail --backtitle "Architecture Warning" --title "Non-standard Architecture" --yesno "This script is designed for Raspberry Pi systems but detected architecture: $ARCH\n\nDo you want to continue anyway?" 12 60; then
            echo " !! Installation cancelled by user" | tee -a ~/logs/pifire_install.log
            exit 1
        fi
        ;;
esac
echo " + System architecture set to: $OS_BITS-bit" | tee -a ~/logs/pifire_install.log

# Determine OS version number
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
    OS_VERSION=$VERSION_ID
    echo " + Detected OS: $OS_NAME Version: $OS_VERSION" | tee -a ~/logs/pifire_install.log
else
    echo " !! Unable to determine OS version. /etc/os-release not found." | tee -a ~/logs/pifire_install.log
    exit 1
fi  

if [[ " $@ " =~ " -venv " ]]; then
    echo " + Vanilla venv install selected" | tee -a ~/logs/pifire_install.log
    VENV_TYPE="vanilla"
elif [[ " $@ " =~ " -uv " ]]; then
    echo " + UV install selected" | tee -a ~/logs/pifire_install.log
    VENV_TYPE="uv"
else
    VENV_TYPE="auto"
    echo " + Auto venv type selected" | tee -a ~/logs/pifire_install.log
fi

sleep 2
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
whiptail --msgbox --backtitle "Welcome" --title "PiFire Automated Installer" "This installer will transform your Single Board Computer into a connected Smoker Controller.  NOTE: This installer is intended to be run on a fresh install of Raspberry Pi OS Lite 32/64-Bit Bullseye or later." ${r} ${c}

# Supervisor WebUI Settings
SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Supervisor Configured" "After this installation is completed, you should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
    echo "No Supervisor WebUI Setup." | tee -a ~/logs/pifire_install.log
fi

echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Running Apt Update... (This could take several minutes)        **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
# Update package list, exit if failed
$SUDO apt update 2>&1 | tee -a ~/logs/pifire_install.log || exit 1

echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Running Apt Upgrade... (This could take several minutes)       **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
# Upgrade packages, exit if failed
$SUDO DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    -o Dpkg::Options::=--force-confdef \
    -o Dpkg::Options::=--force-confold 2>&1 | tee -a ~/logs/pifire_install.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo " !! Failed to upgrade packages. Installation cannot continue." | tee -a ~/logs/pifire_install.log
    exit 1
fi

# Install APT dependencies
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Installing Dependencies... (This could take several minutes)   **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
# Install dependencies, exit if failed
$SUDO apt install python3-dev python3-pip python3-venv python3-scipy nginx git supervisor ttf-mscorefonts-installer redis-server gfortran libopenblas-dev liblapack-dev libopenjp2-7 libglib2.0-dev -y 2>&1 | tee -a ~/logs/pifire_install.log
if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo " !! Failed to install dependencies. Installation cannot continue." | tee -a ~/logs/pifire_install.log
    exit 1
fi
# If OS_Version is 11 or 12, install libatlas-base-dev
if [[ "$OS_VERSION" == "11" || "$OS_VERSION" == "12" ]]; then
    echo " + OS Version $OS_VERSION detected, installing libatlas-base-dev" | tee -a ~/logs/pifire_install.log
    $SUDO apt install libatlas-base-dev -y 2>&1 | tee -a ~/logs/pifire_install.log
else
    echo " + Skipping libatlas-base-dev installation for OS Version $OS_VERSION" | tee -a ~/logs/pifire_install.log
fi
# If Raspberry Pi 5, install python3-rpi-lgpio
if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    echo " + Raspberry Pi 5 detected, installing python3-rpi-lgpio" | tee -a ~/logs/pifire_install.log
    $SUDO apt install python3-rpi-lgpio -y
fi

# Grab project files
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Cloning PiFire from GitHub...                                  **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
cd /usr/local/bin

# Check if -devrepo option is used
if [[ $DEV_REPO == "true" ]]; then
    echo " + Cloning development branch..." | tee -a ~/logs/pifire_install.log
    # Replace the below command to fetch development branch
    $SUDO git clone --depth 1 --branch development https://github.com/nebhead/pifire 2>&1 | tee -a ~/logs/pifire_install.log
else
    echo " + Cloning main branch..." | tee -a ~/logs/pifire_install.log 2>&1 | tee -a ~/logs/pifire_install.log
    # Use a shallow clone to reduce download size
    $SUDO git clone --depth 1 https://github.com/nebhead/pifire
fi

# Setup Python VENV & Install Python dependencies
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Setting up Python VENV and Installing Modules...               **" | tee -a ~/logs/pifire_install.log
echo "**            (This could take several minutes)                        **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo ""
echo " + Setting Up PiFire Group"
cd /usr/local/bin
$SUDO groupadd pifire 
$SUDO usermod -a -G pifire $USER 
$SUDO usermod -a -G pifire root 
# Change ownership to group=pifire for all files/directories in pifire 
$SUDO chown -R $USER:pifire pifire 
# Change ability for pifire group to read/write/execute 
$SUDO chmod -R 777 /usr/local/bin

# Install UV (Universal Virtualenv) for Python 3.11+
# If using 64-bit OS OR -uv option is set
if [ "$OS_BITS" = "64" ] && [ ! "$VENV_TYPE" = "vanilla" ]; then
    echo " + Setting up UV configuration (64-Bit)" | tee -a ~/logs/pifire_install.log
    # Add any 64-bit specific configurations here if needed
    echo " + Installing UV" | tee -a ~/logs/pifire_install.log
    if ! /bin/curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" /bin/sh; then
        echo " ! Failed to download or install UV. Exiting." | tee -a ~/logs/pifire_install.log
        exit 1
    fi

    echo " + Setting up VENV" | tee -a ~/logs/pifire_install.log
    # Setup VENV
    cd /usr/local/bin/pifire
    uv venv --system-site-packages

    # Activate VENV
    source .venv/bin/activate

    # Installing module dependencies
    echo " - Installing module dependencies... " | tee -a ~/logs/pifire_install.log

    # Install latest eventlet
    if ! uv pip install eventlet 2>&1 | tee -a ~/logs/pifire_install.log; then
        echo " !! Failed to install eventlet. Installation cannot continue." | tee -a ~/logs/pifire_install.log
        exit 1
    fi

    # Install influxdb_client with CISO support for better performance
    if ! uv pip install "influxdb_client[ciso]==1.48.0" 2>&1 | tee -a ~/logs/pifire_install.log; then
        echo " !! Failed to install influxdb_client. Installation cannot continue." | tee -a ~/logs/pifire_install.log
        exit 1
    fi
    
    # If Raspberry Pi 5, skip rpi.gpio installation as it is not supported
    if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
        echo " + Raspberry Pi 5 detected, skipping install of rpi.gpio" | tee -a ~/logs/pifire_install.log
    else
        echo " + Installing rpi.gpio==0.7.1" | tee -a ~/logs/pifire_install.log
        if ! uv pip install rpi.gpio==0.7.1 2>&1 | tee -a ~/logs/pifire_install.log; then
            echo " !! Failed to install rpi.gpio. Installation cannot continue." | tee -a ~/logs/pifire_install.log
            exit 1
        fi
    fi

    # If OS_version is "11" or "12", install scikit-learn==1.4.2 else install scikit-learn==1.7.2
    if [[ "$OS_VERSION" == "11" || "$OS_VERSION" == "12" ]]; then
        echo " + Installing scikit-learn==1.4.2" | tee -a ~/logs/pifire_install.log
        if ! uv pip install scikit-learn==1.4.2 2>&1 | tee -a ~/logs/pifire_install.log; then
            echo " !! Failed to install scikit-learn. Installation cannot continue." | tee -a ~/logs/pifire_install.log
            exit 1
        fi
    else
        # if OSBITS is 64, install scikit-learn==1.7.2
        if [ "$OS_BITS" = "64" ]; then
            echo " + Installing scikit-learn==1.7.2" | tee -a ~/logs/pifire_install.log
            if ! uv pip install scikit-learn==1.7.2 2>&1 | tee -a ~/logs/pifire_install.log; then
                echo " !! Failed to install scikit-learn. Installation cannot continue." | tee -a ~/logs/pifire_install.log
                exit 1
            fi
        else
            echo " + Skipping scikit-learn installation for 32-bit OS" | tee -a ~/logs/pifire_install.log
        fi
    fi

    echo " + Installing modules from requirements.txt one at a time... " | tee -a ~/logs/pifire_install.log
    while IFS= read -r req || [ -n "$req" ]; do
        # Strip inline comments and trim whitespace
        req="${req%%#*}"
        req="$(echo "$req" | xargs)"
        # Skip empty lines
        [ -z "$req" ] && continue
        # Skip requirement file/options directives
        case "$req" in
            -r*|--requirement*|--find-links*|-f*|--index-url*|--extra-index-url*|--trusted-host*|--no-binary*|--only-binary*|--*)
                echo " - Skipping requirement option: $req" | tee -a ~/logs/pifire_install.log
                continue
                ;;
        esac
        echo " - Installing $req ..." | tee -a ~/logs/pifire_install.log
        uv pip install "$req" 2>&1 | tee -a ~/logs/pifire_install.log
        status=${PIPESTATUS[0]}
        if [ $status -ne 0 ]; then
            echo " !! Failed to install $req. Installation cannot continue." | tee -a ~/logs/pifire_install.log
            exit 1
        fi
    done < /usr/local/bin/pifire/auto-install/requirements.txt
    echo " + requirements.txt installation complete." | tee -a ~/logs/pifire_install.log
    
    # Find all bluepy-helper executables in various possible locations
        BLUEPY_HELPERS=$(find /usr/local/bin/pifire/.venv/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo " ! No bluepy-helper found in the standard Python library locations" | tee -a ~/logs/pifire_install.log
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo " + Setting capabilities for $helper" | tee -a ~/logs/pifire_install.log
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo " + All bluepy-helper executables have been configured" | tee -a ~/logs/pifire_install.log
    fi
else
    # Add any 32-bit specific configurations here if needed
    echo " + Setting up Vanilla VENV" | tee -a ~/logs/pifire_install.log
    # Setup VENV
    cd /usr/local/bin
    /bin/python -m venv --system-site-packages pifire
    cd /usr/local/bin/pifire
    source bin/activate
    if ! /bin/python -c "import sys; assert sys.version_info[:2] >= (3,11)" > /dev/null 2>&1; then
        echo " + System is running a python version lower than 3.11, installing eventlet==0.30.2." | tee -a ~/logs/pifire_install.log;
        python -m pip install "greenlet==3.1.1" "eventlet==0.30.2" 2>&1 | tee -a ~/logs/pifire_install.log
        python -m pip install "influxdb_client==1.48.0" 2>&1 | tee -a ~/logs/pifire_install.log
    else
        echo " + System is running a python version 3.11 or higher." | tee -a ~/logs/pifire_install.log
        python -m pip install eventlet 2>&1 | tee -a ~/logs/pifire_install.log
        python -m pip install "influxdb_client[ciso]==1.48.0" 2>&1 | tee -a ~/logs/pifire_install.log
    fi
    if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
        echo " + Raspberry Pi 5 detected, skipping install of rpi.gpio" | tee -a ~/logs/pifire_install.log
    else
        echo " + Installing rpi.gpio==0.7.1" | tee -a ~/logs/pifire_install.log
        if ! python -m pip install rpi.gpio==0.7.1 2>&1 | tee -a ~/logs/pifire_install.log; then
            echo " !! Failed to install rpi.gpio. Installation cannot continue." | tee -a ~/logs/pifire_install.log
            exit 1
        fi
    fi
    # Installing module dependencies from requirements.txt one at a time
    echo " + Installing modules from requirements.txt one at a time... " | tee -a ~/logs/pifire_install.log
    while IFS= read -r req || [ -n "$req" ]; do
        # Strip inline comments and trim whitespace
        req="${req%%#*}"
        req="$(echo "$req" | xargs)"
        # Skip empty lines
        [ -z "$req" ] && continue
        # Skip requirement file/options directives
        case "$req" in
            -r*|--requirement*|--find-links*|-f*|--index-url*|--extra-index-url*|--trusted-host*|--no-binary*|--only-binary*|--*)
                echo " - Skipping requirement option: $req" | tee -a ~/logs/pifire_install.log
                continue
                ;;
        esac
        echo " - Installing $req ..." | tee -a ~/logs/pifire_install.log
        python -m pip install "$req" 2>&1 | tee -a ~/logs/pifire_install.log
        status=${PIPESTATUS[0]}
        if [ $status -ne 0 ]; then
            echo " !! Failed to install $req. Installation cannot continue." | tee -a ~/logs/pifire_install.log
            exit 1
        fi
    done < /usr/local/bin/pifire/auto-install/requirements.txt
    echo " + requirements.txt installation complete." | tee -a ~/logs/pifire_install.log
    # Find all bluepy-helper executables in various possible locations
    BLUEPY_HELPERS=$(find /usr/local/bin/pifire/lib/ -path "*/bluepy/bluepy-helper" 2>/dev/null)

    if [ -z "$BLUEPY_HELPERS" ]; then
        echo " ! No bluepy-helper found in the standard Python library locations" | tee -a ~/logs/pifire_install.log
    else
        # Apply capabilities to each found bluepy-helper
        for helper in $BLUEPY_HELPERS; do
            echo " + Setting capabilities for $helper" | tee -a ~/logs/pifire_install.log
            $SUDO setcap "cap_net_raw,cap_net_admin+eip" "$helper"
            
            # Verify the capabilities were set
            getcap "$helper"
        done
        echo " + All bluepy-helper executables have been configured" | tee -a ~/logs/pifire_install.log
    fi

    # Get PIP List into JSON file
    echo " - Setting Legacy VENV flag in settings.json" | tee -a ~/logs/pifire_install.log
    python updater.py --legacyvenv 2>&1 | tee -a ~/logs/pifire_install.log
fi

# Get PIP List into JSON file
echo " - Getting PIP List into JSON file" | tee -a ~/logs/pifire_install.log
python updater.py --piplist 2>&1 | tee -a ~/logs/pifire_install.log

# Get OS Information into JSON file
echo " - Getting OS Information into JSON file" | tee -a ~/logs/pifire_install.log
python board-config.py -ov 2>&1 | tee -a ~/logs/pifire_install.log

### Setup nginx to proxy to gunicorn
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Configuring nginx...                                           **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
# Move into install directory
cd /usr/local/bin/pifire/auto-install/nginx

# Generate Self-Signed SSL Certificate
echo " + Generating Self-Signed SSL Certificate" | tee -a ~/logs/pifire_install.log
if ! $SUDO openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /etc/ssl/private/localhost.key -out /etc/ssl/certs/localhost.crt -subj "/CN=localhost" -batch; then
    echo " !! Failed to generate SSL certificate. HTTPS may not function correctly." | tee -a ~/logs/pifire_install.log
else
    echo " + SSL Certificate generation successful." | tee -a ~/logs/pifire_install.log
fi

# Delete default configuration
$SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
$SUDO cp pifire.nginx /etc/nginx/sites-available/pifire

# Create link in sites-enabled
$SUDO ln -s /etc/nginx/sites-available/pifire /etc/nginx/sites-enabled

# Copy server_error.html to /usr/share/nginx/html
$SUDO cp server_error.html /usr/share/nginx/html

# Restart nginx
$SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "**      Configuring Supervisord...                                     **" | tee -a ~/logs/pifire_install.log
echo "**                                                                     **" | tee -a ~/logs/pifire_install.log
echo "*************************************************************************" | tee -a ~/logs/pifire_install.log

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
if [ "$OS_BITS" = "64" ] && [ ! "$VENV_TYPE" = "vanilla" ]; then
    cd /usr/local/bin/pifire/auto-install/supervisor
else
    cd /usr/local/bin/pifire/auto-install/supervisor/legacy
fi

# Add the current username to the configuration files 
echo "user=$USER" | tee -a control.conf > /dev/null
echo "user=$USER" | tee -a webapp.conf > /dev/null

$SUDO cp *.conf /etc/supervisor/conf.d/

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
else
   echo "No WebUI Setup." | tee -a ~/logs/pifire_install.log
fi

# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start 2>&1 | tee -a ~/logs/pifire_install.log

# Installation Complete, Reboot Prompt
echo "+ Installation completed at $(date '+%Y-%m-%d %H:%M:%S')" | tee -a ~/logs/pifire_install.log

# Ask user if they want to reboot
if whiptail --backtitle "Install Complete" --title "Installation Completed" --yesno "Congratulations, the installation is complete.\n\nIt's recommended to reboot your system now for all changes to take effect. On first boot, the wizard will guide you through the remaining setup steps.\n\nYou should be able to access your application by opening a browser on your PC or other device and using the IP address (or http://[hostname].local) for this device.\n\nWould you like to reboot now?" ${r} ${c}; then
    echo "Rebooting system..." | tee -a ~/logs/pifire_install.log
    $SUDO cp ~/logs/pifire_install.log /usr/local/bin/pifire/logs/pifire_install_$(date '+%Y%m%d_%H%M%S').log
    $SUDO reboot
else
    echo "Reboot skipped. Please reboot manually when convenient." | tee -a ~/logs/pifire_install.log
    $SUDO cp ~/logs/pifire_install.log /usr/local/bin/pifire/logs/pifire_install_$(date '+%Y%m%d_%H%M%S').log
    exit 0
fi

