'''
==============================================================================
 Server Status Module
==============================================================================

Description: 
  This module provides functions to set and get the server status across
  different Flask blueprints.
'''

from flask import current_app

def set_server_status(status):
    """
    Set the server status in the Flask application context.
    
    Args:
        status (str): The server status (e.g., 'available', 'rebooting', 'shutdown', 'restarting')
    """
    if not hasattr(current_app, 'server_status'):
        current_app.server_status = 'available'
    
    current_app.server_status = status
    return current_app.server_status

def get_server_status():
    """
    Get the current server status from the Flask application context.
    
    Returns:
        str: The current server status
    """
    if not hasattr(current_app, 'server_status'):
        current_app.server_status = 'available'
    
    return current_app.server_status
