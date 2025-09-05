#!/usr/bin/env python3
"""
WLED Device Discovery Module
Discovers WLED devices on the network using mDNS/Bonjour and HTTP queries
"""

import socket
import requests
import json
import threading
import time
from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo
from typing import List, Dict, Optional

class WLEDDeviceInfo:
    """Class to store WLED device information"""
    def __init__(self, name: str, ip: str, port: int = 80):
        self.name = name
        self.ip = ip  
        self.port = port
        self.led_count = 0
        self.version = ""
        self.product = ""
        self.mac = ""
        self.online = False
        
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'ip': self.ip,
            'port': self.port,
            'led_count': self.led_count,
            'version': self.version,
            'product': self.product,
            'mac': self.mac,
            'online': self.online
        }

class WLEDDiscovery:
    """WLED Device Discovery using mDNS and HTTP"""
    
    def __init__(self, discovery_timeout: int = 10):
        self.discovery_timeout = discovery_timeout
        self.discovered_devices: List[WLEDDeviceInfo] = []
        self.zeroconf = None
        self.browser = None
        
    def __enter__(self):
        self.zeroconf = Zeroconf()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.browser:
                self.browser.cancel()
        except Exception:
            pass  # Ignore cleanup errors
        try:
            if self.zeroconf:
                self.zeroconf.close()
        except Exception:
            pass  # Ignore cleanup errors
    
    def add_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Callback when a new service is discovered"""
        try:
            info = zeroconf.get_service_info(type_, name)
            if info:
                # Parse the service info
                device_name = name.replace('._http._tcp.local.', '')
                ip_address = socket.inet_ntoa(info.addresses[0])
                port = info.port
                
                # Check if this looks like a WLED device
                if self._is_wled_device(device_name, info):
                    device = WLEDDeviceInfo(device_name, ip_address, port)
                    
                    # Try to get device details via HTTP
                    self._get_device_info(device)
                    
                    # Only add if we got valid device info
                    if device.online:
                        self.discovered_devices.append(device)
                        print(f"Discovered WLED device: {device.name} at {device.ip}:{device.port}")
                        
        except Exception as e:
            # Suppress common zeroconf errors that don't affect functionality
            if "NoneType" not in str(e):
                print(f"Error processing service {name}: {e}")
    
    def remove_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Callback when a service is removed"""
        pass
        
    def update_service(self, zeroconf: Zeroconf, type_: str, name: str) -> None:
        """Callback when a service is updated"""
        pass
    
    def _is_wled_device(self, device_name: str, info: ServiceInfo) -> bool:
        """Check if the discovered service is likely a WLED device"""
        # Check common WLED device name patterns
        wled_patterns = ['wled', 'esp8266', 'esp32', 'led']
        device_name_lower = device_name.lower()
        
        # Check device name
        for pattern in wled_patterns:
            if pattern in device_name_lower:
                return True
                
        # Check TXT records for WLED-specific info
        if info.properties:
            txt_records = {k.decode('utf-8'): v.decode('utf-8') for k, v in info.properties.items()}
            if 'app' in txt_records and 'wled' in txt_records['app'].lower():
                return True
            if 'product' in txt_records and 'wled' in txt_records['product'].lower():
                return True
                
        return True  # Default to true for HTTP services, we'll validate via HTTP
    
    def _get_device_info(self, device: WLEDDeviceInfo) -> None:
        """Get device information via HTTP/JSON API"""
        try:
            # Try the WLED JSON info endpoint
            url = f"http://{device.ip}:{device.port}/json/info"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                info_data = response.json()
                
                # Check if this is actually a WLED device
                if 'ver' in info_data or 'name' in info_data:
                    device.version = info_data.get('ver', '')
                    device.name = info_data.get('name', device.name)
                    device.mac = info_data.get('mac', '')
                    device.product = info_data.get('product', 'WLED')
                    
                    # Get LED count from state endpoint
                    state_url = f"http://{device.ip}:{device.port}/json/state"
                    state_response = requests.get(state_url, timeout=5)
                    
                    if state_response.status_code == 200:
                        state_data = state_response.json()
                        
                        # Extract LED count from segments
                        if 'seg' in state_data and len(state_data['seg']) > 0:
                            segment = state_data['seg'][0]
                            if 'stop' in segment:
                                device.led_count = segment['stop']
                            elif 'len' in segment:
                                device.led_count = segment['len']
                        
                        # Alternative: get from info if available
                        if device.led_count == 0 and 'leds' in info_data:
                            device.led_count = info_data['leds'].get('count', 0)
                    
                    device.online = True
                    
        except Exception as e:
            print(f"Error getting device info for {device.ip}: {e}")
            # Still mark as online if we can reach it, even if we can't get full info
            try:
                simple_response = requests.get(f"http://{device.ip}:{device.port}/", timeout=3)
                if simple_response.status_code == 200:
                    device.online = True
                    device.product = "WLED (Unknown Version)"
                    device.led_count = 0  # Unknown
            except:
                pass
    
    def discover_mdns_devices(self) -> List[WLEDDeviceInfo]:
        """Discover WLED devices using mDNS/Bonjour"""
        print(f"Starting mDNS discovery for {self.discovery_timeout} seconds...")
        
        # Start the service browser
        self.browser = ServiceBrowser(self.zeroconf, "_http._tcp.local.", self)
        
        # Wait for discovery
        time.sleep(self.discovery_timeout)
        
        # Stop browsing with better error handling
        try:
            if self.browser:
                self.browser.cancel()
        except Exception:
            pass  # Ignore cleanup errors
            
        print(f"mDNS discovery completed. Found {len(self.discovered_devices)} WLED devices.")
        return self.discovered_devices.copy()
    
    def discover_network_scan(self, network_range: str = "192.168.1.0/24") -> List[WLEDDeviceInfo]:
        """Discover WLED devices by scanning IP range (fallback method)"""
        print(f"Starting network scan for WLED devices in {network_range}...")
        devices = []
        
        # This is a basic implementation - could be enhanced with proper network scanning
        # For now, just scan common IP ranges
        base_ip = "192.168.1."  # Could be made configurable
        
        def check_ip(ip):
            try:
                device = WLEDDeviceInfo(f"WLED-{ip.split('.')[-1]}", ip)
                self._get_device_info(device)
                if device.online:
                    devices.append(device)
            except:
                pass
        
        # Use threading to speed up scanning
        threads = []
        for i in range(1, 255):
            ip = base_ip + str(i)
            thread = threading.Thread(target=check_ip, args=(ip,))
            threads.append(thread)
            thread.start()
            
            # Limit concurrent threads
            if len(threads) >= 20:
                for t in threads:
                    t.join()
                threads = []
        
        # Wait for remaining threads
        for thread in threads:
            thread.join()
            
        print(f"Network scan completed. Found {len(devices)} WLED devices.")
        return devices
    
    def discover_all(self) -> List[WLEDDeviceInfo]:
        """Discover WLED devices using all available methods"""
        all_devices = []
        device_ips = set()
        
        # Try mDNS first
        try:
            mdns_devices = self.discover_mdns_devices()
            for device in mdns_devices:
                if device.ip not in device_ips:
                    all_devices.append(device)
                    device_ips.add(device.ip)
        except Exception as e:
            print(f"mDNS discovery failed: {e}")
        
        # Note: Network scan disabled by default as it can be slow
        # Uncomment the following lines to enable network scanning
        """
        try:
            scan_devices = self.discover_network_scan()
            for device in scan_devices:
                if device.ip not in device_ips:
                    all_devices.append(device)
                    device_ips.add(device.ip)
        except Exception as e:
            print(f"Network scan failed: {e}")
        """
        
        return all_devices

def discover_wled_devices(timeout: int = 10) -> List[Dict]:
    """
    Convenience function to discover WLED devices
    Returns a list of device dictionaries suitable for JSON serialization
    
    This function handles web server environments by using a subprocess approach
    when needed to avoid threading conflicts with eventlet/gunicorn.
    """
    try:
        # Try direct discovery first
        with WLEDDiscovery(timeout) as discovery:
            devices = discovery.discover_all()
            result = [device.to_dict() for device in devices]
            
            # If we got devices, return them
            if result:
                return result
                
        # If no devices found with direct method, try subprocess approach
        # This helps in web server environments where threading might be restricted
        import subprocess
        import json
        import sys
        
        script_code = f'''
import sys
sys.path.insert(0, ".")
from notify.wled_discovery import WLEDDiscovery
import json

try:
    with WLEDDiscovery({timeout}) as discovery:
        devices = discovery.discover_mdns_devices()
        result = [device.to_dict() for device in devices]
        print(json.dumps(result))
except Exception as e:
    print(json.dumps([]))
'''
        
        # Run discovery in a separate process to avoid threading conflicts
        process = subprocess.Popen(
            [sys.executable, '-c', script_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd='/usr/local/bin/pifire'
        )
        
        stdout, stderr = process.communicate(timeout=timeout + 10)
        
        if process.returncode == 0 and stdout:
            try:
                return json.loads(stdout.decode())
            except json.JSONDecodeError:
                pass
                
        return []
        
    except Exception as e:
        print(f"WLED discovery error: {e}")
        return []

# Test function
if __name__ == "__main__":
    print("Testing WLED Discovery...")
    devices = discover_wled_devices()
    
    if devices:
        print(f"\nFound {len(devices)} WLED devices:")
        for device in devices:
            print(f"  Name: {device['name']}")
            print(f"  IP: {device['ip']}:{device['port']}")
            print(f"  LED Count: {device['led_count']}")
            print(f"  Version: {device['version']}")
            print(f"  Product: {device['product']}")
            print(f"  Online: {device['online']}")
            print()
    else:
        print("No WLED devices found.")
