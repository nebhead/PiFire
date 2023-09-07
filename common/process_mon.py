#!/usr/bin/env python3

'''
==============================================================================
 PiFire Process Monitor
==============================================================================

Description: This class object can be generated to both generate heartbeats 
    and monitor heartbeats from a running process.  If the heartbeat fails to 
    register before a set timeout, then the monitor will log the incident, fire off a command
    and stop.  

    process = (str) Name of the process being monitored, used in logging
    command = (list) Command in subprocess format (i.e. ['echo', 'This is an example message.'])
    timeout = (int/float) Time in seconds to wait before logging an error and running the command 

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''
import time 
import threading 
import subprocess 
import logging 
from common import create_logger, is_raspberry_pi

'''
==============================================================================
 Class Definition
==============================================================================
'''

class Process_Monitor:
    def __init__(self, process, command, timeout=5):
        self.process = process  # name of the process to monitor 
        self.timeout = timeout  # time in seconds to wait before logging an error and running the specified command 
        self.command = command  # subprocess formatted command to run when a timeout occurs
        
        self.last_heartbeat = time.time()
        self.active = False 
        self.kill = False 

        self.is_pi = is_raspberry_pi() 

        # Setup logging
        log_level = logging.ERROR
        self.process_logger = create_logger(self.process, filename=f'./logs/{self.process}.log', level=log_level)
        self.event_logger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)

        # Setup process monitoring thread 
        self.process_thread = threading.Thread(target=self._heartbeat_check)
        self.process_thread.start()

    def heartbeat(self):
        self.last_heartbeat = time.time() 

    def start_monitor(self):
        self.active = True 

    def stop_monitor(self): 
        self.active = False 

    def kill_monitor(self):
        self.active = False
        self.kill = True 

    def status(self):
        if self.kill:
            return 'killed'
        if self.active: 
            return 'active'
        else:
            return 'inactive'

    def _heartbeat_check(self):
        while True:
            while self.active: 
                now = time.time()
                if now - self.last_heartbeat > self.timeout: 
                    # Log error
                    message = f'The {self.process} process experienced a timeout event (no heartbeat detected in {self.timeout} seconds) and is being reset.'
                    self.event_logger.error(message)
                    self.process_logger.error(message)
                    # Execute command on raspberry pi only 
                    if self.is_pi:
                        subprocess.run(self.command)
                    else: 
                        print(message)
                    self.active = False  # Pause thread 
                time.sleep(1)
            if self.kill:
                break
            time.sleep(0.25)
