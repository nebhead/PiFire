'''
*****************************************
 PiFire ThermoMaven Cloud Probe Module
*****************************************

Description:
  Reads ThermoMaven wireless thermometers (G1/WT10, G2/WT07, G4/WT09, P1/WT11,
  P2/WT02, P4/WT06). These devices do not talk BLE to the Pi: the base station
  pushes readings to ThermoMaven's cloud (AWS IoT Core) and this module
  subscribes to that stream over MQTT, exactly like the official app does.

  Protocol reverse-engineered by https://github.com/djiesr/thermomaven-ha (MIT).
  It depends on an app key extracted from the Android app; if ThermoMaven
  rotates it the module reports the device as disconnected and the rest of
  PiFire keeps working.

  Ports (per probe n = 1..num_probes):
      P{n}_MEAT     internal / tip temperature  (curTemperature)
      P{n}_AMBIENT  ambient sensor on the probe  (curAmbientTemperature)
      P{n}_AREA1..5 zone temperatures along the probe (areaTemperature[]), tip to handle

  Ex Device Definition:

	device_info = {
			'device' : 'thermomaven',
			'module' : 'cloud_thermomaven',
			'ports' : ['P1_MEAT', 'P1_AMBIENT'],
			'config' : {
				'email' : 'you@example.com',
				'password' : '...',          # write-only; never returned by the API
				'region' : 'US',             # ISO country code used by the app
				'device_id' : '',            # empty = first device on the account
				'num_probes' : 1,
				'transient' : 'True',
			}
		}
'''

from __future__ import annotations

import hashlib
import json
import logging
import random
import ssl
import tempfile
import threading
import time
import uuid

from probes.base import ProbeInterface

DEFAULT_APP_KEY = 'bcd4596f1bb8419a92669c8017bf25e8'
DEFAULT_APP_ID = 'ap4060eff28137181bd'
API_BASE_URL_COM = 'https://api.iot.thermomaven.com'
API_BASE_URL_DE = 'https://api.iot.thermomaven.de'
EUROPEAN_COUNTRIES = {
	'AT', 'BE', 'BG', 'CH', 'CZ', 'DE', 'DK', 'ES', 'FI', 'FR', 'HU', 'IE', 'IS', 'IT', 'LU', 'NL', 'NO',
	'PL', 'PT', 'RO', 'RS', 'SE', 'SK', 'TR', 'UK', 'GB',
}
MQTT_BROKERS = {
	'US': 'a2ubmaqm3a642j-ats.iot.us-west-2.amazonaws.com',
	'EU': 'a2ubmaqm3a642j-ats.iot.eu-central-1.amazonaws.com',
}
MQTT_PORT = 8883
PROBE_COUNTS = {'WT02': 2, 'WT06': 4, 'WT07': 2, 'WT09': 4, 'WT10': 1, 'WT11': 1}
STALE_AFTER_S = 180  # readings older than this are reported as None (probe detached / offline)
AUTOSTART = True  # tests set this False so no network thread is started


class ThermoMavenClient:
	'''Signed REST client for the ThermoMaven app API. Pure, no threads.'''

	def __init__(self, email, password, region='US', app_key=DEFAULT_APP_KEY, app_id=DEFAULT_APP_ID,
				 session=None, timeout=15):
		self.email = email
		self.password = password
		self.region = (region or 'US').upper()
		self.app_key = app_key
		self.app_id = app_id
		self.timeout = timeout
		self.token = None
		self.user_id = None
		self.device_sn = ''.join(random.choices('0123456789abcdef', k=16))
		self.base_url = API_BASE_URL_DE if self.region in EUROPEAN_COUNTRIES else API_BASE_URL_COM
		self._session = session

	@property
	def session(self):
		if self._session is None:
			import requests

			self._session = requests.Session()
		return self._session

	# ----- signing ---------------------------------------------------------
	@staticmethod
	def sign(app_key, params: dict, body_str: str = '') -> str:
		params_str = ';'.join(f'{k}={v}' for k, v in sorted(params.items()))
		sign_str = f'{app_key}|{params_str}'
		if body_str:
			sign_str += f'|{body_str}'
		return hashlib.md5(sign_str.replace('\n', '').encode('utf-8')).hexdigest()

	@staticmethod
	def encode_body(body: dict | None) -> str:
		return json.dumps(body, separators=(',', ':'), ensure_ascii=False) if body else ''

	def build_headers(self, body: dict | None = None, *, nonce=None, timestamp_ms=None) -> dict:
		params = {
			'x-appId': self.app_id,
			'x-appVersion': '1804',
			'x-deviceSn': self.device_sn,
			'x-lang': 'en_US',
			'x-nonce': nonce or uuid.uuid4().hex,
			'x-region': self.region,
			'x-timestamp': str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)),
			'x-token': self.token or 'none',
		}
		headers = dict(params)
		headers['x-sign'] = self.sign(self.app_key, params, self.encode_body(body))
		headers['Content-Type'] = 'application/json'
		headers['User-Agent'] = 'okhttp/4.12.0'
		return headers

	# ----- requests --------------------------------------------------------
	def post(self, endpoint: str, body: dict | None = None) -> dict:
		body = body if body is not None else {}
		headers = self.build_headers(body)
		resp = self.session.post(f'{self.base_url}{endpoint}', data=self.encode_body(body).encode('utf-8'),
								 headers=headers, timeout=self.timeout)
		resp.raise_for_status()
		data = resp.json()
		if str(data.get('code')) != '0':
			raise RuntimeError(f'ThermoMaven API error on {endpoint}: {data.get("msg") or data}')
		return data.get('data', {})

	def login(self) -> dict:
		password_md5 = hashlib.md5(self.password.encode('utf-8')).hexdigest()
		data = self.post('/app/account/login', {
			'accountName': self.email,
			'accountPassword': password_md5,
			'deviceInfo': 'google sdk_gphone_x86_64 11',
		})
		self.token = data['token']
		self.user_id = data.get('userId')
		return data

	def get_devices(self) -> list[dict]:
		devices = []
		for endpoint in ('/app/device/share/my/device/list', '/app/device/share/shared/device/list'):
			try:
				devices.extend(self.post(endpoint) or [])
			except Exception:
				# shared list may legitimately fail for accounts with no shares
				if endpoint.endswith('my/device/list'):
					raise
		return devices

	def get_mqtt_certificate(self) -> dict:
		return self.post('/app/mqtt/cert/apply')


class ThermoMavenDevice:
	'''Background MQTT subscriber that keeps the latest readings per probe.'''

	def __init__(self, port_map, primary_port, units, config: dict, autostart=True, logger=None):
		self.logger = logger or logging.getLogger('control')
		self.port_map = port_map
		self.primary_port = primary_port
		self.units = units
		self.config = config
		self.email = config.get('email', '')
		self.password = config.get('password', '')
		self.region = (config.get('region') or 'US').upper()
		self.device_id = str(config.get('device_id') or '').strip()
		self.num_probes = int(config.get('num_probes', 1) or 1)
		self.app_key = config.get('app_key') or DEFAULT_APP_KEY
		self.app_id = config.get('app_id') or DEFAULT_APP_ID

		self.client: ThermoMavenClient | None = None
		self.mqtt = None
		self.mqtt_config = None
		self._cert_files: list[str] = []
		self._subscribed_topics: set[str] = set()
		self._devices: list[dict] = []
		self._lock = threading.Lock()
		self._stop = threading.Event()

		# readings[probe_index] = {'meat_f', 'ambient_f', 'areas_f', 'battery', 'updated'}
		self.readings: dict[int, dict] = {}
		self.device_model = None
		self.device_battery = None
		self.rssi = None
		self.device_online: bool | None = None  # None until the cloud has told us
		self.connected = False
		self.last_error = None
		self.last_report = 0.0

		self.thread = threading.Thread(target=self._run, name='thermomaven', daemon=True)
		if autostart and self.email and self.password:
			self.thread.start()
		elif autostart:
			self.last_error = 'ThermoMaven credentials not configured'

	# ----- lifecycle -------------------------------------------------------
	def _run(self):
		backoff = 5
		while not self._stop.is_set():
			try:
				self._connect()
				backoff = 5
				while not self._stop.is_set() and self.connected:
					self._stop.wait(5)
			except Exception as e:
				self.connected = False
				self.last_error = str(e)
				self.logger.warning(f'ThermoMaven: {e}; retrying in {backoff}s')
			self._teardown_mqtt()
			if self._stop.wait(backoff):
				break
			backoff = min(backoff * 2, 300)

	def stop(self):
		self._stop.set()
		self._teardown_mqtt()

	def _connect(self):
		import paho.mqtt.client as mqtt

		self.client = ThermoMavenClient(self.email, self.password, self.region, self.app_key, self.app_id)
		self.client.login()
		self.mqtt_config = self.client.get_mqtt_certificate()
		cert_file, key_file = self._materialize_cert(self.mqtt_config)

		client_id = self.mqtt_config['clientId']
		region_from_client = client_id.split('-')[2] if client_id.count('-') >= 2 else self.region
		broker = MQTT_BROKERS['EU' if region_from_client in EUROPEAN_COUNTRIES else 'US']

		self.mqtt = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311,
								callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
		self.mqtt.on_connect = self._on_connect
		self.mqtt.on_message = self._on_message
		self.mqtt.on_disconnect = self._on_disconnect
		self.mqtt.tls_set(certfile=cert_file, keyfile=key_file, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)
		self.mqtt.connect(broker, MQTT_PORT, keepalive=60)
		self.mqtt.loop_start()

		# Poking the device list endpoint makes the broker publish user:device:list
		self._devices = self.client.get_devices()
		self._subscribe_device_topics(self._devices)

	def _materialize_cert(self, mqtt_config):
		import requests
		from cryptography.hazmat.primitives import serialization
		from cryptography.hazmat.primitives.serialization import pkcs12

		resp = requests.get(mqtt_config['p12Url'], timeout=15)
		resp.raise_for_status()
		key, cert, _ = pkcs12.load_key_and_certificates(resp.content, mqtt_config['p12Password'].encode())
		cert_file = tempfile.NamedTemporaryFile(delete=False, suffix='.crt')
		cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
		cert_file.close()
		key_file = tempfile.NamedTemporaryFile(delete=False, suffix='.key')
		key_file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
										 serialization.NoEncryption()))
		key_file.close()
		self._cert_files += [cert_file.name, key_file.name]
		return cert_file.name, key_file.name

	def _teardown_mqtt(self):
		if self.mqtt is not None:
			try:
				self.mqtt.loop_stop()
				self.mqtt.disconnect()
			except Exception:
				pass
			self.mqtt = None
		self._subscribed_topics.clear()
		import os

		for f in self._cert_files:
			try:
				os.unlink(f)
			except OSError:
				pass
		self._cert_files = []

	# ----- MQTT callbacks --------------------------------------------------
	def _on_connect(self, client, userdata, flags, rc):
		if rc == 0:
			self.connected = True
			self.last_error = None
			for topic in self.mqtt_config.get('subTopics', []):
				client.subscribe(topic)
				self._subscribed_topics.add(topic)
			self.logger.info('ThermoMaven: MQTT connected')
		else:
			self.connected = False
			self.last_error = f'MQTT connect failed rc={rc}'

	def _on_disconnect(self, client, userdata, rc):
		self.connected = False
		if rc != 0:
			self.last_error = f'MQTT disconnected rc={rc}'

	def _on_message(self, client, userdata, msg):
		try:
			self.handle_message(msg.topic, msg.payload.decode('utf-8'))
		except Exception as e:
			self.logger.debug(f'ThermoMaven: bad message on {msg.topic}: {e}')

	def _subscribe_device_topics(self, devices):
		for device in devices:
			if not self._device_matches(device):
				continue
			self.device_model = device.get('deviceModel') or self.device_model
			for topic in device.get('subTopics', []) or []:
				if self.mqtt is not None and topic not in self._subscribed_topics:
					self.mqtt.subscribe(topic)
					self._subscribed_topics.add(topic)

	def _device_matches(self, device: dict) -> bool:
		if not self.device_id:
			return True
		return str(device.get('deviceId')) == self.device_id

	# ----- message parsing (pure; unit-tested) -----------------------------
	@staticmethod
	def device_id_from_topic(topic: str):
		# device/WT10/<deviceId>/pub  or  app/WT10/<deviceId>/sub ; app/user/<uid>/sub is not a device topic
		parts = topic.split('/')
		if len(parts) >= 4 and parts[0] in ('device', 'app') and parts[1].upper().startswith('WT'):
			return parts[2]
		return None

	def handle_message(self, topic: str, payload: str):
		data = json.loads(payload)
		cmd_type = data.get('cmdType', '')
		cmd_data = data.get('cmdData', {}) or {}
		if cmd_type == 'user:device:list':
			self._devices = cmd_data.get('devices', []) or []
			self._subscribe_device_topics(self._devices)
			# The list carries each device's last status report: seed our state from it so
			# an offline thermometer is reported as such instead of "no data yet".
			for device in self._devices:
				last = device.get('lastStatusCmd') if self._device_matches(device) else None
				if isinstance(last, dict) and 'status:report' in str(last.get('cmdType', '')):
					self._apply_report(last.get('cmdData') or {}, at=(last.get('serverTime') or 0) / 1000 or None)
			return
		if 'status:report' not in cmd_type:
			return
		device_id = data.get('deviceId') or cmd_data.get('deviceId') or self.device_id_from_topic(topic)
		if self.device_id and device_id and str(device_id) != self.device_id:
			return
		self._apply_report(cmd_data)

	def _apply_report(self, cmd_data: dict, at: float | None = None) -> None:
		now = at or time.time()
		with self._lock:
			self.device_battery = cmd_data.get('batteryValue', self.device_battery)
			self.rssi = cmd_data.get('wifiRssi', cmd_data.get('rssi', self.rssi))
			online = cmd_data.get('globalStatus', 'online') == 'online'
			self.device_online = online
			for index, probe in enumerate(cmd_data.get('probes', []) or []):
				self.readings[index] = {
					'meat_f': self._tenths(probe.get('curTemperature')) if online else None,
					'ambient_f': self._tenths(probe.get('curAmbientTemperature')) if online else None,
					'areas_f': [self._tenths(v) for v in (probe.get('areaTemperature') or [])] if online else [],
					'battery': probe.get('batteryValue'),
					'updated': now,
				}
			self.last_report = max(self.last_report, now)

	@staticmethod
	def _tenths(value):
		if value is None:
			return None
		try:
			return float(value) / 10.0
		except (TypeError, ValueError):
			return None

	# ----- readings --------------------------------------------------------
	def get_port_values_f(self) -> dict:
		'''Return {port_name: temp_f or None} for every known port name.'''
		now = time.time()
		values = {}
		with self._lock:
			for n in range(1, self.num_probes + 1):
				r = self.readings.get(n - 1)
				fresh = r is not None and (now - r['updated']) < STALE_AFTER_S
				values[f'P{n}_MEAT'] = r['meat_f'] if fresh else None
				values[f'P{n}_AMBIENT'] = r['ambient_f'] if fresh else None
				areas = r['areas_f'] if fresh else []
				for a in range(1, 6):
					values[f'P{n}_AREA{a}'] = areas[a - 1] if len(areas) >= a else None
		return values

	def get_status(self) -> dict:
		with self._lock:
			batteries = [r.get('battery') for r in self.readings.values() if r.get('battery') is not None]
		error = self.last_error
		if error is None and self.connected and self.device_online is False:
			error = 'Thermometer is offline (base station off or not on WiFi)'
		return {
			'connected': self.connected and self.device_online is not False,
			'cloud_connected': self.connected,
			'device_online': self.device_online,
			'error': error,
			'battery_percentage': batteries[0] if batteries else self.device_battery,
			'battery_charging': False,
			'device_model': self.device_model,
			'rssi': self.rssi,
			'last_report': self.last_report,
		}


class ReadProbes(ProbeInterface):
	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device = ThermoMavenDevice(self.port_map, self.primary_port, self.units, self.device_info['config'],
										autostart=AUTOSTART)

	def _convert(self, temp_f):
		if temp_f is None:
			return None
		return round((temp_f - 32) * 5 / 9, 1) if self.units == 'C' else int(round(temp_f))

	def read_all_ports(self, output_data):
		values = self.device.get_port_values_f()
		for port in self.port_map:
			value = self._convert(values.get(port))
			label = self.port_map[port]
			self.output_data['tr'][label] = 0
			if value is not None:
				self.port_queues[port].enqueue(value)
				output_value = self.port_queues[port].average()
			else:
				output_value = None
			if port == self.primary_port:
				self.output_data['primary'][label] = output_value
			elif port in self.food_ports:
				self.output_data['food'][label] = output_value
			elif port in self.aux_ports:
				self.output_data['aux'][label] = output_value
		return self.output_data

	def update_units(self, units):
		# Keep the MQTT session; only the conversion and the averaging queues change.
		self.units = 'C' if units == 'C' else 'F'
		self._build_ports()
