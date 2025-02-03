#! /bin/bash
#
# This file will add the cap_net_raw,cap_net_admin+eip capability to the bluepy-helper file to ensure proper permissions
sudo setcap "cap_net_raw,cap_net_admin+eip" "/usr/local/bin/pifire/lib/python3.*/site-packages/bluepy/bluepy-helper"
echo "Added cap_net_raw,cap_net_admin+eip capability to the bluepy-helper file"