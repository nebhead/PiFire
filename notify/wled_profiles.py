"""
WLED Profile Management Module

This module provides functionality to push predefined LED profiles to WLED devices
based on PiFire grill states and events. It creates WLED presets that can be
easily modified by users while maintaining automatic state-based control.

Profile Mapping:
- Idle: Dim white solid glow  
- Booting: Slow white pulse
- Preheat: Orange slow pulse
- Cooking: Solid blue/green (user selectable)
- Cooldown: Fade from orange to blue
- Target Reached: Green flash 3x
- Overshoot Alarm: Rapid red strobe 5x
- Probe Alarm: Red/white alternating flash
- Low Pellets: Yellow pulse every 10s
- Timer Done: Rainbow chase
- Error: Solid red
- Night Mode: Very dim amber glow
"""

import requests
import json
import time

# Color definitions for WLED profiles (RGB values)
WLED_COLORS = {
    'white': [255, 255, 255],
    'red': [255, 0, 0],
    'green': [0, 255, 0],
    'blue': [0, 0, 255],
    'orange': [255, 165, 0],
    'orange_cooking': [255, 120, 0],  # Specific orange for cooking
    'yellow': [255, 255, 0],
    'amber': [255, 191, 0],
    'purple': [128, 0, 128],
    'rainbow': 'rainbow'  # Special case for rainbow effect
}

# Effect definitions for WLED (effect IDs may vary by WLED version)
WLED_EFFECTS = {
    'solid': 0,
    'blink': 1,
    'breathe': 2,
    'wipe': 3,
    'wipe_random': 4,
    'random_colors': 5,
    'sweep': 6,
    'dynamic': 7,
    'colorloop': 8,
    'rainbow': 9,
    'scan': 10,
    'dual_scan': 11,
    'strobe': 12,
    'strobe_rainbow': 13,
    'multi_strobe': 14,
    'running': 15,
    'fade': 16,
    'theater_chase': 17,
    'chase': 28,
    'rainbow_chase': 30,
    'saw': 31,
    'twinkle': 32
}

# Default profile numbers for each PiFire state
DEFAULT_PROFILE_NUMBERS = {
    'idle': 1,
    'booting': 2, 
    'preheat': 3,
    'cooking': 4,
    'cooldown': 5,
    'target_reached': 6,
    'overshoot_alarm': 7,
    'probe_alarm': 8,
    'low_pellets': 9,
    'timer_done': 10,
    'error': 11,
    'night_mode': 12
}

# WLED profile definitions based on PiFire requirements
WLED_PROFILE_DEFINITIONS = {
    'idle': {
        'id': 200,
        'name': 'PiFire - Idle',
        'config': {
            'on': True,
            'bri': 51,  # 20% brightness (51/255)
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['solid'],
                'col': [WLED_COLORS['white']]
            }]
        }
    },
    'booting': {
        'id': 201,
        'name': 'PiFire - Booting',
        'config': {
            'on': True,
            'bri': 128,
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['breathe'],
                'sx': 100,  # Slow speed
                'col': [WLED_COLORS['white']]
            }]
        }
    },
    'preheat': {
        'id': 202,
        'name': 'PiFire - Preheat',
        'config': {
            'on': True,
            'bri': 128,
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['breathe'],
                'sx': 100,  # Slow speed
                'col': [WLED_COLORS['orange']]
            }]
        }
    },
    'cooking': {
        'id': 203,
        'name': 'PiFire - Cooking',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['solid'],
                'col': [WLED_COLORS['blue']]  # Default, will be updated based on user preference
            }]
        }
    },
    'cooldown': {
        'id': 204,
        'name': 'PiFire - Cooldown',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 100,  # 10 second fade
            'seg': [{
                'fx': WLED_EFFECTS['fade'],
                'sx': 50,  # Medium speed for fade
                'col': [WLED_COLORS['orange'], WLED_COLORS['blue']]
            }]
        }
    },
    'target_reached': {
        'id': 205,
        'name': 'PiFire - Target Reached',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 5,
            'seg': [{
                'fx': WLED_EFFECTS['blink'],
                'sx': 200,  # Fast blink for 3x flash
                'col': [WLED_COLORS['green']]
            }]
        }
    },
    'overshoot_alarm': {
        'id': 206,
        'name': 'PiFire - Overshoot Alarm',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 2,
            'seg': [{
                'fx': WLED_EFFECTS['strobe'],
                'sx': 255,  # Very fast strobe
                'col': [WLED_COLORS['red']]
            }]
        }
    },
    'probe_alarm': {
        'id': 207,
        'name': 'PiFire - Probe Alarm',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 5,
            'seg': [{
                'fx': WLED_EFFECTS['blink'],
                'sx': 150,  # Medium blink speed
                'col': [WLED_COLORS['red'], WLED_COLORS['white']]
            }]
        }
    },
    'low_pellets': {
        'id': 208,
        'name': 'PiFire - Low Pellets',
        'config': {
            'on': True,
            'bri': 128,
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['breathe'],
                'sx': 80,  # Slow pulse
                'col': [WLED_COLORS['yellow']]
            }]
        }
    },
    'timer_done': {
        'id': 209,
        'name': 'PiFire - Timer Done',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 20,
            'seg': [{
                'fx': WLED_EFFECTS['rainbow_chase'],
                'sx': 120,  # Medium speed for 2s effect
                'col': [WLED_COLORS['red'], WLED_COLORS['green'], WLED_COLORS['blue']]
            }]
        }
    },
    'error_fault': {
        'id': 210,
        'name': 'PiFire - Error/Fault',
        'config': {
            'on': True,
            'bri': 255,
            'transition': 5,
            'seg': [{
                'fx': WLED_EFFECTS['solid'],
                'col': [WLED_COLORS['red']]
            }]
        }
    },
    'night_mode': {
        'id': 211,
        'name': 'PiFire - Night Mode',
        'config': {
            'on': True,
            'bri': 25,  # Very dim (10% brightness)
            'transition': 10,
            'seg': [{
                'fx': WLED_EFFECTS['solid'],
                'col': [WLED_COLORS['amber']]
            }]
        }
    }
}

class WLEDProfileManager:
    """
    Manages WLED profiles for PiFire states and events.
    
    This class handles creating, updating, and managing WLED presets
    that correspond to different PiFire operational states.
    """
    
    def __init__(self, device_address, settings=None):
        """
        Initialize the WLED Profile Manager.
        
        Args:
            device_address (str): IP address or hostname of WLED device
            settings (dict): PiFire settings containing WLED configuration
        """
        self.device_address = device_address.strip().rstrip('/')
        if 'http://' in self.device_address:
            self.device_address = self.device_address.replace('http://', '')
        if 'https://' in self.device_address:
            self.device_address = self.device_address.replace('https://', '')
            
        self.settings = settings or {}
        
        # Import logger locally to avoid circular imports
        try:
            from common import create_logger
            self.logger = create_logger("control")
        except ImportError:
            # Fallback if common module not available
            import logging
            self.logger = logging.getLogger("wled_profiles")
            
        self.profile_numbers = self._get_profile_numbers()
        
    def _get_profile_numbers(self):
        """Get profile numbers from settings or use defaults."""
        wled_config = self.settings.get('notify_services', {}).get('wled', {})
        custom_profiles = wled_config.get('profile_numbers', {})
        
        # Merge custom profile numbers with defaults
        profile_numbers = DEFAULT_PROFILE_NUMBERS.copy()
        profile_numbers.update(custom_profiles)
        
        return profile_numbers
    
    def _apply_user_customizations(self, profile_name, profile_data):
        """Apply user customizations to profile data."""
        wled_config = self.settings.get('notify_services', {}).get('wled', {})
        suggested_config = wled_config.get('suggested_config', {})
        
        # Apply cooking color customization
        if profile_name == 'cooking':
            cooking_color = suggested_config.get('cooking_color', 'blue')
            if cooking_color == 'green':
                profile_data['seg'][0]['col'] = [[0, 255, 0]]  # Green
            else:
                profile_data['seg'][0]['col'] = [[0, 0, 255]]  # Blue (default)
        
        # Apply idle brightness customization
        if profile_name == 'idle':
            idle_brightness = suggested_config.get('idle_brightness', 20)
            profile_data['bri'] = int(idle_brightness * 2.55)  # Convert % to 0-255
        
        # Apply night mode modifications
        if suggested_config.get('night_mode', False):
            if profile_name in ['idle', 'cooking']:
                # Use night mode variations
                if profile_name == 'idle':
                    profile_data['bri'] = int(profile_data['bri'] * 0.3)  # Extra dim
                    profile_data['seg'][0]['col'] = [[255, 191, 0]]  # Amber
                elif profile_name == 'cooking':
                    profile_data['bri'] = int(profile_data['bri'] * 0.5)  # Dimmed
        
        return profile_data
    
    def get_device_info(self):
        """Get WLED device information."""
        url = f"http://{self.device_address}/json/info"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Error getting WLED device info: {e}")
            return None
    
    def create_preset(self, preset_number, profile_data):
        """Create or update a WLED preset."""
        url = f"http://{self.device_address}/json/state"
        
        # First, apply the profile state
        try:
            response = requests.post(url, json=profile_data, timeout=5)
            response.raise_for_status()
            
            # Then save it as a preset
            save_payload = {"psave": preset_number}
            response = requests.post(url, json=save_payload, timeout=5)
            response.raise_for_status()
            
            self.logger.info(f"Created WLED preset {preset_number}: {profile_data.get('name', 'Unnamed')}")
            return True
            
        except requests.RequestException as e:
            self.logger.error(f"Error creating WLED preset {preset_number}: {e}")
            return False
    
    def push_all_profiles(self, custom_profile_numbers=None):
        """Push all PiFire profiles to the WLED device.
        
        Args:
            custom_profile_numbers (dict, optional): Custom profile numbers to use
                                                     instead of the defaults from settings
        """
        device_info = self.get_device_info()
        if not device_info:
            return {
                'success': False,
                'message': 'Could not connect to WLED device',
                'profiles_pushed': 0
            }
        
        # Use custom profile numbers if provided, otherwise use settings
        profile_numbers = custom_profile_numbers or self.profile_numbers
        
        results = {
            'success': True,
            'message': '',
            'profiles_pushed': 0,
            'profiles': [],
            'errors': []
        }
        
        self.logger.info(f"Pushing WLED profiles to device: {device_info.get('name', self.device_address)}")
        
        for profile_name, profile_number in profile_numbers.items():
            if profile_name in WLED_PROFILE_DEFINITIONS:
                # Get base profile definition
                profile_data = WLED_PROFILE_DEFINITIONS[profile_name].copy()
                
                # Apply user customizations
                profile_data = self._apply_user_customizations(profile_name, profile_data)
                
                # Create the preset
                success = self.create_preset(profile_number, profile_data)
                
                if success:
                    results['profiles_pushed'] += 1
                    results['profiles'].append({
                        'name': profile_name,
                        'number': profile_number,
                        'description': profile_data.get('description', '')
                    })
                    # Small delay between presets
                    time.sleep(0.1)
                else:
                    results['errors'].append(f"Failed to create {profile_name} (preset {profile_number})")
        
        if results['errors']:
            results['success'] = False
            results['message'] = f"Created {results['profiles_pushed']} profiles with {len(results['errors'])} errors"
        else:
            results['message'] = f"Successfully created {results['profiles_pushed']} profiles"
        
        return results
    
    def delete_profile(self, preset_number):
        """Delete a WLED preset."""
        url = f"http://{self.device_address}/json/state"
        payload = {"pdel": preset_number}
        
        try:
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            self.logger.info(f"Deleted WLED preset {preset_number}")
            return True
        except requests.RequestException as e:
            self.logger.error(f"Error deleting WLED preset {preset_number}: {e}")
            return False
    
    def clear_all_pifire_profiles(self):
        """Clear all PiFire-created profiles from the WLED device."""
        results = {
            'success': True,
            'message': '',
            'profiles_deleted': 0,
            'errors': []
        }
        
        for profile_name, profile_number in self.profile_numbers.items():
            success = self.delete_profile(profile_number)
            if success:
                results['profiles_deleted'] += 1
            else:
                results['errors'].append(f"Failed to delete {profile_name} (preset {profile_number})")
        
        if results['errors']:
            results['success'] = False
            results['message'] = f"Deleted {results['profiles_deleted']} profiles with {len(results['errors'])} errors"
        else:
            results['message'] = f"Successfully deleted {results['profiles_deleted']} profiles"
        
        return results
    
    def get_profile_number_for_state(self, state):
        """Get the profile number for a PiFire state."""
        # Map PiFire modes to profile states
        state_mapping = {
            'Stop': 'idle',
            'Startup': 'booting',
            'Prime': 'booting',
            'Reignite': 'preheat',
            'Smoke': 'cooking',
            'Hold': 'cooking',
            'Shutdown': 'cooldown'
        }
        
        profile_state = state_mapping.get(state, 'idle')
        return self.profile_numbers.get(profile_state, self.profile_numbers['idle'])
    
    def get_profile_number_for_event(self, event):
        """Get the profile number for a PiFire event."""
        # Map PiFire events to profile states
        event_mapping = {
            'Probe_Temp_Achieved': 'target_reached',
            'Probe_Temp_Limit_Alarm': 'overshoot_alarm',
            'Timer_Expired': 'timer_done',
            'Pellet_Level_Low': 'low_pellets',
            'Grill_Warning': 'low_pellets',
            'Recipe_Step_Message': 'target_reached',
            'Grill_Error': 'error',
            'Control_Process_Stopped': 'error'
        }
        
        # Handle events that contain certain keywords
        for keyword, profile_state in event_mapping.items():
            if keyword in event:
                return self.profile_numbers.get(profile_state, self.profile_numbers['error'])
        
        # Default fallback
        return self.profile_numbers.get('error', self.profile_numbers['idle'])
