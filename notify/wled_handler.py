"""
WLED Handler - Send notifications to a WLED device

This module provides functionality to interact with WLED-compatible LED devices.
WLED (Wireless Light Effect Daemon) is an open-source software that allows controlling
addressable RGB(W) LEDs from an ESP8266/ESP32 microcontroller over WiFi.

This handler supports:
- Communicating with WLED devices via HTTP API
- Triggering LED presets based on different grill states and events
- Direct color and effect control for suggested presets
- Managing notification durations and cooldowns
- Reading device info and sending state commands

Required settings format:
{
    'notify_services': {
        'wled': {
            'device_address': 'ip_address_or_hostname',
            'use_suggested_presets': bool,
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
            'suggested_config': {
                'cooking_color': 'blue',
                'idle_brightness': 20,
                'night_mode': False,
                'led_count': 6
            },
            'notify_duration': seconds_between_notifications
        }
    }
}
"""
import time
import requests
from common import create_logger

# Color definitions for suggested presets (RGB values)
WLED_COLORS = {
    'white': [255, 255, 255],
    'red': [255, 0, 0],
    'green': [0, 255, 0],
    'blue': [0, 0, 255],
    'orange': [255, 165, 0],
    'yellow': [255, 255, 0],
    'amber': [255, 191, 0],
    'purple': [128, 0, 128],
    'rainbow': 'rainbow'  # Special case for rainbow effect
}

# Effect definitions for WLED
WLED_EFFECTS = {
    'solid': 0,
    'blink': 1,
    'breathe': 2,
    'wipe': 3,
    'rainbow': 9,
    'strobe': 12,
    'fade': 2,
    'chase': 28
}

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

    def send_direct_command(self, color=None, brightness=None, effect=None, speed=None, intensity=None, on=True):
        """
        Send direct color and effect commands to WLED device (for suggested presets).
        
        Args:
            color (str or list): Color name from WLED_COLORS or RGB list [r,g,b]
            brightness (int): Brightness 0-255
            effect (str or int): Effect name from WLED_EFFECTS or effect number
            speed (int): Effect speed 0-255
            intensity (int): Effect intensity 0-255  
            on (bool): Turn device on/off
        """
        url = f"http://{self.device_address}/json/state"
        payload = {"on": on}
        
        if brightness is not None:
            payload["bri"] = max(0, min(255, brightness))
            
        if color is not None:
            if isinstance(color, str) and color in WLED_COLORS:
                if color == 'rainbow':
                    payload["fx"] = WLED_EFFECTS['rainbow']
                else:
                    payload["col"] = [WLED_COLORS[color]]
            elif isinstance(color, list) and len(color) == 3:
                payload["col"] = [color]
                
        if effect is not None:
            if isinstance(effect, str) and effect in WLED_EFFECTS:
                payload["fx"] = WLED_EFFECTS[effect]
            elif isinstance(effect, int):
                payload["fx"] = effect
                
        if speed is not None:
            payload["sx"] = max(0, min(255, speed))
            
        if intensity is not None:
            payload["ix"] = max(0, min(255, intensity))
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            self.logger.debug(f"Direct WLED command sent: {payload}")
        except requests.RequestException as e:
            self.logger.error(f"Error sending direct command to WLED device at {self.device_address}: {e}")
        
        self.last_updated = time.time()

    def send_suggested_preset(self, state, config):
        """
        Send suggested preset based on PiFire state using direct color/effect control.
        
        This method implements the PiFire suggested LED behaviors:
        - idle: Dim white solid glow (or dim amber in night mode)
        - booting: Slow white pulse (1s fade in/out)  
        - preheat: Orange slow pulse (1s fade in/out)
        - cooking: Solid blue or green (user-configurable)
        - cooldown: Fade from orange → blue over 10s
        - target_reached: Green flash (3x, 0.5s each)
        - overshoot_alarm: Rapid red strobe (5x, 0.2s each), then revert
        - probe_alarm: Red/white alternating flash (5s)
        - low_pellets: Yellow pulse (1s fade, every 10s)
        - timer_done: Rainbow chase (2s)
        - error: Solid red
        
        Args:
            state (str): PiFire state (idle, booting, cooking, etc.)
            config (dict): Suggested preset configuration from settings
        """
        night_mode = config.get('night_mode', False)
        cooking_color = config.get('cooking_color', 'blue')
        idle_brightness = int(config.get('idle_brightness', 20) * 2.55)  # Convert % to 0-255
        
        if state == 'idle':
            if night_mode:
                self.send_direct_command(color='amber', brightness=int(idle_brightness * 0.3), effect='solid')
            else:
                self.send_direct_command(color='white', brightness=idle_brightness, effect='solid')
                
        elif state == 'booting':
            self.send_direct_command(color='white', brightness=128, effect='breathe', speed=100)
            
        elif state == 'preheat':
            self.send_direct_command(color='orange', brightness=128, effect='breathe', speed=100)
            
        elif state == 'cooking':
            if night_mode:
                brightness = int(idle_brightness * 0.5)
            else:
                brightness = 128
            self.send_direct_command(color=cooking_color, brightness=brightness, effect='solid')
            
        elif state == 'cooldown':
            # Fade from orange to blue - using orange for now, effect could be enhanced
            self.send_direct_command(color='orange', brightness=128, effect='fade', speed=50)
            
        elif state == 'target_reached':
            # Green flash 3x
            self.send_direct_command(color='green', brightness=255, effect='blink', speed=200, intensity=255)
            
        elif state == 'overshoot_alarm':
            # Rapid red strobe
            self.send_direct_command(color='red', brightness=255, effect='strobe', speed=255, intensity=255)
            
        elif state == 'probe_alarm':
            # Red/white alternating flash - using strobe with red for now
            self.send_direct_command(color='red', brightness=255, effect='strobe', speed=150, intensity=200)
            
        elif state == 'low_pellets':
            # Yellow pulse every 10s
            self.send_direct_command(color='yellow', brightness=128, effect='breathe', speed=80)
            
        elif state == 'timer_done':
            # Rainbow chase
            self.send_direct_command(effect='rainbow', brightness=200, speed=150)
            
        elif state == 'error':
            # Solid red
            self.send_direct_command(color='red', brightness=255, effect='solid')
            
        else:
            # Default to idle state
            self.send_suggested_preset('idle', config)

    def notify(self, notifyevent, control, settings):
        """
        Process notification events and trigger WLED presets based on event type.
        
        This is the main method called by the notification system. It handles different
        types of events and maps them to appropriate WLED presets or suggested behaviors.
        
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
        use_suggested = self.config.get('use_suggested_presets', False)
        
        if use_suggested:
            # Use suggested preset system with direct color/effect control
            suggested_config = self.config.get('suggested_config', {})
            
            if notifyevent == "GRILL_STATE" and self.last_updated < time.time() - self.notify_duration:
                if control is None:
                    self.logger.warning("Control data is None, cannot determine grill state.")
                    return
                elif control['mode'] != self.last_mode:
                    self.last_mode = control['mode']
                    self.notify_duration = 1  # Reset duration for state changes
                    
                    # Map PiFire modes to suggested states
                    if control['mode'] == 'Stop':
                        self.send_suggested_preset('idle', suggested_config)
                    elif control['mode'] in ['Startup', 'Prime']:
                        self.send_suggested_preset('booting', suggested_config)
                    elif control['mode'] == 'Reignite':
                        self.send_suggested_preset('preheat', suggested_config)
                    elif control['mode'] in ['Smoke', 'Hold']:
                        self.send_suggested_preset('cooking', suggested_config)
                    elif control['mode'] == 'Shutdown':
                        self.send_suggested_preset('cooldown', suggested_config)
                    else:
                        self.send_suggested_preset('idle', suggested_config)

            elif notifyevent == 'Test_Notify':
                self.send_suggested_preset('booting', suggested_config)
                self.logger.info(f"WLED Test Notification Triggered with suggested preset")

            elif notifyevent == 'Probe_Temp_Achieved':
                self.send_suggested_preset('target_reached', suggested_config)

            elif 'Probe_Temp_Limit_Alarm' in notifyevent:
                self.send_suggested_preset('probe_alarm', suggested_config)

            elif notifyevent == 'Timer_Expired':
                self.send_suggested_preset('timer_done', suggested_config)

            elif notifyevent == 'Pellet_Level_Low':
                self.send_suggested_preset('low_pellets', suggested_config)

            elif 'Grill_Warning' in notifyevent:
                # Use low_pellets for warnings (yellow pulse)
                self.send_suggested_preset('low_pellets', suggested_config)

            elif 'Recipe_Step_Message' in notifyevent:
                # Use target_reached for recipe steps (green flash)
                self.send_suggested_preset('target_reached', suggested_config)

            elif 'Grill_Error' in notifyevent or notifyevent == 'Control_Process_Stopped':
                self.send_suggested_preset('error', suggested_config)
                
            # Set cooldown for non-state events
            if notifyevent != 'GRILL_STATE':
                self.notify_duration = self.config.get('notify_duration', 120)
                self.last_mode = None # Reset last mode to allow state change notifications
                self.logger.info(f"WLED Suggested Notification Sent for event {notifyevent}")
        
        else:
            # Use traditional preset system
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

            elif 'Probe_Temp_Limit_Alarm' in notifyevent:
                preset = self.config['event_presets'].get('Grill_Error', -1)  # Use error preset for alarms

            elif notifyevent == 'Timer_Expired':
                preset = self.config['event_presets'].get('Timer_Expired', -1)

            elif notifyevent == 'Pellet_Level_Low':
                preset = self.config['event_presets'].get('Pellet_Level_Low', -1)

            elif 'Grill_Warning' in notifyevent:
                preset = self.config['event_presets'].get('Pellet_Level_Low', -1)  # Use pellet low preset for warnings

            elif 'Recipe_Step_Message' in notifyevent:
                preset = self.config['event_presets'].get('Recipe_Next', -1)

            elif 'Grill_Error' in notifyevent or notifyevent == 'Control_Process_Stopped':
                preset = self.config['event_presets'].get('Grill_Error', -1)

            if preset != -1:
                self.send_notification(preset)
                if notifyevent != 'GRILL_STATE':
                    self.notify_duration = self.config.get('notify_duration', 120)
                    self.last_mode = None # Reset last mode to allow state change notifications
                    self.logger.info(f"WLED Notification Sent for event {notifyevent} with preset {preset}")
    