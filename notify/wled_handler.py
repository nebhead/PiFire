"""
WLED Handler - Send notifications to a WLED device

This module provides functionality to interact with WLED-compatible LED devices.
WLED (Wireless Light Effect Daemon) is an open-source software that allows controlling
addressable RGB(W) LEDs from an ESP8266/ESP32 microcontroller over WiFi.

This handler supports:
- Communicating with WLED devices via HTTP API
- Triggering LED presets based on different grill states and events
- Managing notification durations and cooldowns
- Reading device info and sending state commands

Required settings format:
{
    'notify_services': {
        'wled': {
            'device_address': 'ip_address_or_hostname',
            'mode_presets': {
                'Startup': preset_number,
                'Smoke': preset_number,
                'Shutdown': preset_number,
                ...
            },
            'event_presets': {
                'Temp_Achieved': preset_number,
                'Timer_Expired': preset_number,
                'Pellet_Level_Low': preset_number,
                'Grill_Error': preset_number,
                ...
            },
            'notify_duration': seconds_between_notifications
        }
    }
}
"""
import time
import requests
from common import create_logger

class WLEDNotificationHandler:
    """
    Handler for sending notifications to WLED devices.
    
    This class manages the connection to a WLED device and provides methods
    to send notifications based on different grill events and states.
    
    Attributes:
        device_address (str): Cleaned IP address or hostname of the WLED device
        logger: Logger instance for recording events and errors
        last_updated (float): Timestamp of the last notification sent
        last_mode (str): The last grill mode that was notified
        config (dict): WLED-specific configuration from settings
        notify_duration (int): Minimum time between notifications in seconds
        state (dict): Current state information from the WLED device
    """
    def __init__(self, settings):
        """
        Initialize the WLED notification handler.
        
        Args:
            settings (dict): Application settings containing WLED configuration
                             under the 'notify_services' > 'wled' key
        
        The initialization process:
        1. Extracts and cleans the device address
        2. Sets up logging
        3. Initializes tracking variables
        4. Attempts to retrieve the initial device state
        """
        self.device_address = settings['notify_services']['wled'].get("device_address")
        if 'http://' in self.device_address:
            self.device_address = self.device_address.replace('http://', '')
        if 'https://' in self.device_address:
            self.device_address = self.device_address.replace('https://', '')
        self.device_address = self.device_address.strip().rstrip('/')
        self.logger = create_logger("control")
        self.last_updated = time.time()
        self.last_mode = None
        self.logger.info(f"WLED Notification Handler initialized for device at {self.device_address}")
        self.config = settings['notify_services']['wled']
        self.notify_duration = 1
        self.state = self.get_info()
        if self.state is None:
            self.logger.error(f"Failed to get initial info from WLED device at {self.device_address}")
        else:
            self.logger.info(f"Initial state retrieved from WLED device at {self.device_address}: {self.state}")

    def get_info(self):
        """
        Retrieve information about the WLED device.
        
        Makes an HTTP GET request to the WLED JSON API endpoint to fetch
        device information such as version, name, and capabilities.
        
        Returns:
            dict: JSON response containing device information if successful
            None: If the request fails for any reason
        
        Note:
            Errors are logged but not raised to the caller
        """
        url = f"http://{self.device_address}/json/info"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Error getting info from WLED device at {self.device_address}: {e}")
            return None

    def send_notification(self, preset=1):
        """
        Send a notification to the WLED device by activating a specific preset.
        
        Makes an HTTP POST request to the WLED JSON API endpoint to change
        the device state and activate the specified preset.
        
        Args:
            preset (int, optional): Preset number to activate. Defaults to 1.
                                    Presets must be configured in the WLED device.
        
        Note:
            - Sets the device to ON state
            - Sets brightness to 128 (50%)
            - Updates the last_updated timestamp
            - Errors are logged but not raised to the caller
        """
        url = f"http://{self.device_address}/json/state"
        payload = {
            "on": True,
            "bri": 128,
            "ps": preset
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Error sending notification to WLED device at {self.device_address}: {e}")
        self.last_updated = time.time()

    def notify(self, notifyevent, control, settings):
        """
        Process notification events and trigger WLED presets based on event type.
        
        This is the main method called by the notification system. It handles different
        types of events and maps them to appropriate WLED presets defined in the configuration.
        
        Args:
            notifyevent (str): The type of notification event. Supported events:
                               - GRILL_STATE: Regular grill status updates
                               - Test_Notify: Test notification
                               - Probe_Temp_Achieved: Temperature goal reached
                               - Timer_Expired: Timer has ended
                               - Pellet_Level_Low: Pellet level is low
                               - Grill_Error: Any grill error
                               - Control_Process_Stopped: Control process stopped
            control (dict): Control data containing the current grill state and mode
            settings (dict): Application settings
        
        Note:
            - For GRILL_STATE events, notifications are only sent when the mode changes
            - For other events, a cooldown period is enforced based on notify_duration
            - A preset value of -1 means no notification will be sent
            - When a non-GRILL_STATE event is processed, the last_mode is reset to
              allow immediate notification of the next state change
        """
        preset = -1    
        if notifyevent == "GRILL_STATE" and self.last_updated < time.time() - self.notify_duration:
            if control is None:
                self.logger.warning("Control data is None, cannot determine grill state.")
                return
            elif control['mode'] != self.last_mode:
                self.last_mode = control['mode']
                self.notify_duration = 1  # Reset duration for state changes
                if control['mode'] in list(self.config['mode_presets'].keys()):
                    preset = self.config['mode_presets'][control['mode']]

        elif notifyevent == 'Test_Notify':
            preset = self.config['mode_presets'].get('Startup', -1)
            self.logger.info(f"WLED Test Notification Triggered: {preset}")

        elif notifyevent == 'Probe_Temp_Achieved':
            preset = self.config['event_presets'].get('Temp_Achieved', -1)

        elif notifyevent == 'Timer_Expired':
            preset = self.config['event_presets'].get('Timer_Expired', -1)

        elif notifyevent == 'Pellet_Level_Low':
            preset = self.config['event_presets'].get('Pellet_Level_Low', -1)

        elif 'Grill_Error' in notifyevent or notifyevent == 'Control_Process_Stopped':
            preset = self.config['event_presets'].get('Grill_Error', -1)

        if preset != -1:
            self.send_notification(preset)
            if notifyevent != 'GRILL_STATE':
                self.notify_duration = self.config.get('notify_duration', 120)
                self.last_mode = None # Reset last mode to allow state change notifications
                self.logger.info(f"WLED Notification Sent for event {notifyevent} with preset {preset}")
    