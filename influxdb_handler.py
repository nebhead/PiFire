import time
from datetime import datetime
import threading


class InfluxNotificationHandler:

	def __init__(self, settings) -> None:
		self.queue = []
		self.last_updated = time.time()

		t1 = threading.Thread(target=self.publishing_thread, daemon=True,
							  args=(
								  settings['notify_services']['influxdb']['url'],
								  settings['notify_services']['influxdb']['token'],
								  settings['notify_services']['influxdb']['org'],
								  settings['notify_services']['influxdb']['bucket']))
		t1.start()

	def publishing_thread(self, url, token, org, bucket):
		from influxdb_client import InfluxDBClient

		bucket = bucket

		client = InfluxDBClient(url=url, token=token,
								org=org)

		from influxdb_client import WriteOptions
		write_api = None

		while True:
			time.sleep(1)
			if not write_api:

				write_api = client.write_api(write_options=WriteOptions(batch_size=100,
																		flush_interval=5_000,
																		jitter_interval=2_000,
																		retry_interval=2_000,
																		max_retries=3,
																		max_retry_delay=30_000,
																		exponential_base=2))

			try:
				buf = self.queue.copy()
				self.queue.clear()
				if len(buf) > 0:
					write_api.write(bucket, org, buf)
				time.sleep(5)
			except:
				write_api = None
				time.sleep(10)

	def notify(self, notifyevent, control, settings, pelletdb, in_data, grill_platform):
		if time.time() - self.last_updated < 1:
			return

		from influxdb_client import Point
		name = settings['globals']['grill_name']
		if len(name) == 0:
			name = 'Smoker'

		def get_or_default(data, k, default):
			if data is not None and k in data:
				return data[k]
			return default

		PrimaryKey = list(in_data['probe_history']['primary'].keys())[0]
		Probe1Key = list(in_data['probe_history']['food'].keys())[0]
		Probe2Key = list(in_data['probe_history']['food'].keys())[1]
		
		PrimaryTemp = in_data['probe_history']['primary'][PrimaryKey]
		PrimarySetpoint = in_data['primary_setpoint']
		PrimaryNotify = in_data['notify_targets'][PrimaryKey]
		Probe1Temp = in_data['probe_history']['food'][Probe1Key]
		Probe1Notify = in_data['notify_targets'][Probe1Key]
		Probe2Temp = in_data['probe_history']['food'][Probe2Key]
		Probe2Notify = in_data['notify_targets'][Probe2Key]

		p = Point(name).time(time=datetime.utcnow()) \
			.field("GrillTemp", float(PrimaryTemp)) \
			.field('GrillSetPoint', float(PrimarySetpoint)) \
			.field('GrillNotifyPoint', float(PrimaryNotify)) \
			.field('Probe1Temp', float(Probe1Temp)) \
			.field('Probe1SetPoint', float(Probe1Notify)) \
			.field('Probe2Temp', float(Probe2Temp)) \
			.field('Probe2SetPoint', float(Probe2Notify)) \
			.field("Mode", str(get_or_default(control, "mode", 'unknown'))) \
			.field('PelletLevel', int(get_or_default(get_or_default(pelletdb, 'current', {}), 'hopper_level', 100)))
		if grill_platform is not None:
			outputs = grill_platform.GetOutputStatus()
			for key in outputs:
				p = p.field(key, int(outputs[key]))

		if notifyevent and 'GRILL_STATE' != notifyevent:
			p = p.field('Event', str(notifyevent))

		self.queue.append(p)

		self.last_updated = time.time()
