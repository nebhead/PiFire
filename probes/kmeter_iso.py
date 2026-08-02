#!/usr/bin/env python3

'''
*****************************************
PiFire Probes M5Stack KMeter-ISO Module
*****************************************

Description:
  This module reads one K-type thermocouple from an M5Stack KMeter-ISO Unit.
  It uses the Raspberry Pi I2C bus at /dev/i2c-1 and the smbus2 module.

  Additional units can share the bus after each unit has been assigned a
  unique address using M5Stack-supported firmware or external tooling.  PiFire
  only reads the KMeter-ISO registers and does not change device addresses.
  Ready register 0x20 reports 0 when ready and a nonzero value when not ready.

	Ex Device Definition:

	device = {
		'device' : 'your_device_name',	# Unique name for the device
		'module' : 'kmeter_iso',		# Must be populated for this module to load properly
		'ports' : ['KTT0'],			# One K-type thermocouple port
		'config' : {
			'i2c_bus_addr' : '0x66'		# Usable 7-bit unicast address string
		}
	}
'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

import logging
import re

from smbus2 import SMBus, i2c_msg

from probes.base import ProbeInterface


I2C_DEVICE = '/dev/i2c-1'
MIN_I2C_ADDRESS = 0x08
MAX_I2C_ADDRESS = 0x77
TEMPERATURE_REGISTER = 0x00
READY_STATUS_REGISTER = 0x20
FIRMWARE_REGISTER = 0xFE
MIN_K_TYPE_C = -200.0
MAX_K_TYPE_C = 1350.0

ERROR_MESSAGES = {
	'i2c-read': 'I2C register read failed.',
	'probe-read': 'Probe read failed.',
	'short-read': 'returned a short register read.',
	'not-ready': 'Device reported not ready',
	'out-of-range': 'returned an out-of-range temperature.',
}


class ShortReadError(Exception):
	'''Raised when an I2C register returns fewer bytes than requested.'''


class I2CReadError(Exception):
	'''Raised when an I2C register transaction fails.'''


class KMeterISODevice:
	'''M5Stack KMeter-ISO device accessed through a dedicated SMBus object.'''

	def __init__(self, i2c_bus_addr='0x66'):
		self.logger = logging.getLogger('control')
		self._last_logged_error = None
		self.address_text = str(i2c_bus_addr)
		self.connected = False
		self.ready = False
		self.error = ''

		self.address = self._parse_address(i2c_bus_addr)
		self.address_text = f'0x{self.address:02X}'
		self.bus = SMBus(I2C_DEVICE)
		try:
			self.firmware = str(self._read_register(FIRMWARE_REGISTER, 1)[0])
		except (I2CReadError, ShortReadError) as error:
			self.firmware = 'Unavailable'
			self.logger.error(
				f'KMeter-ISO [{self.address_text}]: Could not read firmware version: {error}'
			)

	@staticmethod
	def _parse_address(address):
		if not isinstance(address, str):
			raise TypeError(f'address {address!r} is not a string')

		address_text = address.strip()
		if re.fullmatch(r'0[xX][0-9a-fA-F]+', address_text) is None:
			raise ValueError(f'address {address!r} is not an explicit hexadecimal string')

		value = int(address_text, 16)
		if value < MIN_I2C_ADDRESS or value > MAX_I2C_ADDRESS:
			raise ValueError(f'address {address!r} is outside the usable 7-bit unicast range')
		return value

	def _read_register(self, register, length):
		try:
			write = i2c_msg.write(self.address, [register])
			read = i2c_msg.read(self.address, length)
			self.bus.i2c_rdwr(write, read)
			data = bytes(read)
		except Exception as error:
			raise I2CReadError(f'register 0x{register:02X}: {error}') from error
		if len(data) != length:
			raise ShortReadError(
				f'register 0x{register:02X} expected {length} bytes but received {len(data)}'
			)
		return data

	def _fail(self, error, *, connected=False, detail=None):
		self.connected = connected
		self.ready = False
		self.error = error
		if self._last_logged_error != error:
			message = ERROR_MESSAGES[error]
			if detail:
				message = f'{message} {detail}'
			self.logger.error(f'KMeter-ISO [{self.address_text}]: {message}')
			self._last_logged_error = error

	def _record_success(self):
		if self._last_logged_error is not None:
			self.logger.info(f'KMeter-ISO [{self.address_text}]: recovered and is reading normally.')
			self._last_logged_error = None
		self.error = ''

	@property
	def temperature(self):
		try:
			ready_status = self._read_register(READY_STATUS_REGISTER, 1)[0]
			self.connected = True
			self.ready = ready_status == 0
			if not self.ready:
				return self._fail(
					'not-ready',
					connected=True,
					detail=f'(register: 0x{ready_status:02X}).',
				)

			raw_temperature = self._read_register(TEMPERATURE_REGISTER, 4)
			temperature_c = int.from_bytes(raw_temperature, byteorder='little', signed=True) / 100
			if temperature_c < MIN_K_TYPE_C or temperature_c > MAX_K_TYPE_C:
				return self._fail(
					'out-of-range',
					connected=True,
					detail=f'decoded value was {temperature_c:.2f} C.',
				)

			self._record_success()
			return temperature_c
		except ShortReadError as error:
			return self._fail('short-read', detail=str(error))
		except I2CReadError as error:
			return self._fail('i2c-read', detail=str(error))
		except Exception as error:
			return self._fail('probe-read', detail=str(error))

	def get_status(self):
		return {
			'connected': self.connected,
			'address': self.address_text,
			'ready': self.ready,
			'firmware': self.firmware,
			'error': self.error,
		}


class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		# ProbeInterface calls _init_device before assigning its logger.
		self.logger = logging.getLogger('control')
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['KTT0']
		address = self.device_info.get('config', {}).get('i2c_bus_addr', '0x66')
		self.device = KMeterISODevice(i2c_bus_addr=address)

	def update_units(self, units):
		# Avoid ProbeInterface.update_units(), which reinitializes the device.
		self.units = 'C' if units == 'C' else 'F'

	def read_all_ports(self, output_data):
		'''Read the thermocouple and return zero for a failed fixed probe.'''
		port = self.device_info['ports'][0]
		if port not in self.port_map:
			return self.output_data

		value = self.device.temperature
		if value is None:
			value = 0
		else:
			value = round(value, 1)
			if self.units == 'F':
				value = self._to_fahrenheit(value)
		self.output_data['tr'][self.port_map[port]] = 0

		if port == self.primary_port:
			self.output_data['primary'][self.port_map[port]] = value
		elif port in self.food_ports:
			self.output_data['food'][self.port_map[port]] = value
		elif port in self.aux_ports:
			self.output_data['aux'][self.port_map[port]] = value

		return self.output_data
