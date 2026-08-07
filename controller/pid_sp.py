#!/usr/bin/env python3

'''
*****************************************
 PiFire PID Controller
*****************************************

 Description: This object will be used to calculate PID for maintaining
 temperature in the grill.

 PID-SP keeps the legacy proportional-band PID law, but chooses its controller
 input through an optional adaptive Smith predictor:

 1. Observe the measured pit temperature and update the model identifier.
 2. Promote a newly trusted physical model into the predictor.
 3. Select measured or delay-corrected temperature through the predictor.
 4. Run transition gating and P/I/D from that one selected temperature.
 5. Later, receive the duty actually applied after production safety clamps.

 Model identification and prediction are optional. Invalid or insufficient
 adaptive state falls back to the measured probe temperature.
 This software was developed by GitHub user DBorello as part of his excellent
 PiSmoker project: https://github.com/DBorello/PiSmoker

 Adapted for PiFire

 PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
   u = Kp (e(t)+ 1/Ti INT + Td de/dt)
  PB = Proportional Band
  Ti = Goal of eliminating in Ti seconds
  Td = Predicts error value at Td in seconds
  
  Configuration Defaults: 
  "config": {
      "PB": 60.0,
      "Td": 45.0,
      "Ti": 180.0,
      "center": 0.5
   }

*****************************************
'''

'''
Imported Libraries
'''
import time
import math
from typing import Optional
from controller.base import ControllerBase 
from controller.smith_predictor import AdaptiveFOPDTIdentifier, FOPDTModel, SmithPredictor

'''
Class Definition
'''
class Controller(ControllerBase):
	'''Proportional-band PID composed with optional adaptive Smith feedback.

	``update`` consumes temperature and returns an unclamped duty request.
	``set_output`` is called later with the duty production actually applied.
	Keeping those directions separate prevents safety clamps and overrides from
	being misrepresented as plant behavior commanded by the PID.
	'''
	def __init__(self, config, units, cycle_data):
		super().__init__(config, units, cycle_data)
		self.function_list.append('set_gains') 
		self.function_list.append('get_k')
		self.function_list.append('set_output')
		self.function_list.append('get_model_snapshot')
		self.function_list.append('restore_model')
		self.function_list.append('get_status')
		
		pb = config.get('PB', 60.0)
		ti = config.get('Ti', 180.0)
		td = config.get('Td', 45.0)
		self._calculate_gains(pb, ti, td)

		self.p = 0.0
		self.i = 0.0
		self.d = 0.0
		self.u = 0

		self.pb = pb

		self.units = units
		# The identifier learns a trusted physical model; the predictor consumes
		# that model.  Both receive the same applied-duty history via set_output.
		self._identifier = AdaptiveFOPDTIdentifier(units, clock=lambda: time.time())
		self._predictor = SmithPredictor(units, clock=lambda: time.time())

		self.last_update = time.time()
		self.last_set_time = time.time()
		self.error = 0.0
		self.set_point = 0

		self.center = 0.5
		self.center_factor = config.get('center_factor', 0.0010)
		
		self.stable_window = config.get('stable_window', 12)
		self.cycle_time = cycle_data['HoldCycleTime']

		self.derv = 0.0
		self.inter = 0.0

		self.last: Optional[float] = None
		self.previous_controller_input: Optional[float] = None
		self._predicted_temperature: Optional[float] = None
		self.start_change_temp = 0.0
		self.new_target = False
		self.output_limited_approach = False
		self.slow_approach_samples = 0

		self.set_target(0.0)

	def _calculate_gains(self, pb, ti, td):
		self.ti = float(ti)
		if pb == 0:
			self.kp = 0
		else:
			self.kp = -1 / pb
		if self.ti <= 0.0:
			self.ki = 0
		else:
			self.ki = self.kp / self.ti
		self.kd = self.kp * td

	def _update_integral_limit(self):
		if self.ki == 0:
			self.inter_max = 0.0
		else:
			self.inter_max = abs(self.center / self.ki)

	def _target_capture_band(self):
		if self.units == 'F':
			return 3.0
		return 3.0 * 5.0 / 9.0

	def _reset_approach_state(self):
		self.output_limited_approach = False
		self.slow_approach_samples = 0

	def update(self, current):
		# Phase 1: timestamp this observation before touching either adaptive
		# component so identification, prediction, and PID share one interval.
		current_time = time.time()
		first_selected_sample = self.previous_controller_input is None

		# Identification always sees the measured probe value.  A newly
		# published model is promoted before selecting this cycle's PID input.
		trusted_update = self._identifier.observe(current, current_time)
		if trusted_update is not None:
			self._predictor.set_model(trusted_update)
			current_time = time.time()
		# Prediction returns either a safe delay-corrected temperature or the
		# measured value unchanged.  Every PID and transition term below uses
		# this one selected input; mixing inputs would create false dynamics.
		controller_input = self._predictor.update(current, current_time)
		dt = current_time - self.last_update
		self._predicted_temperature = controller_input
		error = controller_input - self.set_point
	
		previous_controller_input = self.previous_controller_input
		if previous_controller_input is None:
			selected_rate = 0.0
		else:
			selected_rate = (controller_input - previous_controller_input) / dt
	
		# Phase 2: maintain target-transition state in selected-temperature
		# coordinates.  This matters when a trusted prediction differs from the
		# probe measurement during a live setpoint change.
		# Seed setpoint-transition bookkeeping from the first selected sample.
		if first_selected_sample:
			self.derv = 0.0
			if self.new_target:
				self.start_change_temp = controller_input
	
		# Reaching the native-unit capture band—or crossing an upward target
		# between samples—ends approach damping and restores normal integration.
		capture_band = self._target_capture_band()
		upward_transition = self.set_point > self.start_change_temp
		captured_target = abs(error) <= capture_band or (upward_transition and error >= 0.0)
		if self.new_target and captured_target:
			self.new_target = False
			self._reset_approach_state()
	
		# Phase 3: calculate the raw PID request.  Production applies u_min/u_max,
		# lid-open, fan-PID, and manual overrides after this method returns.
		if error < -self.pb:
			self.u = 1.0
		# If overshooting, minimize output
		elif error > self.stable_window:
			self.u = 0.0
		else:

			# Keep normal small-step damping until the target is reached. A
			# halfway transition still resets the integral accumulator, but
			# completes only after its full PID candidate is output-limited.
			reached_halfway = self.new_target and current_time - self.last_set_time >= self.cycle_time * 3 and abs(error) <= abs(self.start_change_temp - self.set_point) / 2
			if abs(error) > self.stable_window or reached_halfway:
				self.inter = 0.0

			# Minimize derivative to maximize descent rate when setting new lower Set Point
			if (self.new_target and self.set_point < controller_input) or (abs(error) > self.pb / 2):
				self.derv = 0.0
	
			# P
			self.p = self.kp * error + self.center
	
			# I
			self.inter += error * dt
			self.inter = max(min(self.inter, self.inter_max), -self.inter_max)
			self.i = self.ki * self.inter
			self.i = max(min(self.i, self.center), -self.center)
	
			# D
			if first_selected_sample:
				self.derv = 0.0
			else:
				self.derv = selected_rate
			self.d = self.kd * self.derv
	
			# PID
			self.u = self.p + self.i + self.d
	
			# If error is within PB, reduce output to prevent overshoots
			if abs(error) < self.pb and current_time - self.last_set_time < self.cycle_time * 3:
				self.u *= 0.65

			# Mark only a genuinely output-limited upward approach.  The complete
			# candidate (including derivative and startup scaling) must reach the
			# external clamp before extended integral damping is justified.
			u_max = self.cycle_data.get('u_max', 1.0)
			if reached_halfway and upward_transition and self.u >= u_max:
				if self.ti <= 0.0:
					self.new_target = False
					self._reset_approach_state()
				else:
					self.output_limited_approach = True

		# Once active, process approach state after every output branch.  A
		# stalled or reversed temperature can cross proportional-band branches;
		# skipping those samples would leave stale confirmation state.
		if self.output_limited_approach and self.new_target:
			if self.ti <= 0.0:
				self.new_target = False
				self._reset_approach_state()
			else:
				# Three slow selected-temperature samples indicate that momentum
				# no longer explains the residual.  Re-enable integral action so
				# it can remove the remaining P-only offset.
				rate_threshold = capture_band / (2.0 * self.ti)
				if selected_rate <= rate_threshold:
					self.slow_approach_samples += 1
				else:
					self.slow_approach_samples = 0
				if self.slow_approach_samples >= 3:
					self.new_target = False
					self._reset_approach_state()

		# Phase 4: commit exactly the selected input and timestamp used above.
		# The next derivative and delay-rate decision compare like with like.
		self.error = error
		self.last = current
		self.previous_controller_input = controller_input
		self.last_update = current_time
	
		return self.u
	
	def set_target(self, set_point):
		# A target change resets PID/approach transients but deliberately keeps
		# learned model, predictor branches, and applied-duty history.
		self.set_point = set_point
		self.error = 0.0
		self.inter = 0.0
		self.derv = 0.0
		self._reset_approach_state()
		self.last_update = time.time()
		self.last_set_time = self.last_update
		# Live changes begin from the last selected controller temperature.
		# Measured temperature is only a startup fallback before selection exists.
		if self.previous_controller_input is not None:
			self.start_change_temp = self.previous_controller_input
		else:
			self.start_change_temp = self.last if self.last is not None else 0.0
		self.new_target = True
		# Center is a feed-forward baseline.  Preserve the legacy high-target
		# scaling while transition damping controls temporary approach integral.
		if self.units == "F":
			if set_point <= 240:
				self.center = set_point * self.center_factor
			else:
				self.center = set_point * self.center_factor * 1.2
		elif self.units == "C":
			if set_point <= 115:
				self.center = (set_point * 9/5 + 32) * self.center_factor
			else:
				self.center = (set_point * 9/5 + 32) * self.center_factor * 1.2
		self._update_integral_limit()
    
	def set_gains(self, pb, ti, td):
		# Gain changes retain the physical model.  Non-positive Ti disables and
		# clears integral state immediately so no stale contribution survives.
		self._calculate_gains(pb,ti,td)
		self._update_integral_limit()
		if self.ti <= 0.0:
			self.inter = 0.0
			self.i = 0.0

	def get_k(self):
		return self.kp, self.ki, self.kd
	def set_output(self, applied_ratio, identification_allowed=True):
		# Feed both adaptive components the duty that production actually
		# applied.  ``identification_allowed`` blocks learning during overrides
		# while retaining the complete command timeline needed for prediction.
		current_time = time.time()
		self._identifier.record_output(applied_ratio, identification_allowed, timestamp=current_time)
		self._predictor.record_output(applied_ratio, identification_allowed, timestamp=current_time)

	def get_model_snapshot(self) -> Optional[dict]:
		# Persist only a trusted immutable physical model.  Dynamic predictor and
		# RLS state are intentionally reconstructed after process restart.
		model = self._identifier.trusted_model
		if model is None:
			return None
		return {
			'version': 1,
			'gain_f_per_duty': model.gain_f_per_duty,
			'tau_seconds': model.tau_seconds,
			'theta_seconds': model.theta_seconds,
			'confidence': model.confidence,
			'residual': model.residual,
			'observations': model.observations,
			'revision': model.revision,
		}

	def restore_model(self, snapshot) -> bool:
		expected_keys = {
			'version',
			'gain_f_per_duty',
			'tau_seconds',
			'theta_seconds',
			'confidence',
			'residual',
			'observations',
			'revision',
		}
		numeric_keys = (
			'gain_f_per_duty',
			'tau_seconds',
			'theta_seconds',
			'confidence',
			'residual',
		)
		try:
			if not isinstance(snapshot, dict) or set(snapshot) != expected_keys:
				return False
			if type(snapshot['version']) is not int or snapshot['version'] != 1:
				return False
			if any(isinstance(snapshot[key], bool) or not isinstance(snapshot[key], (int, float)) for key in numeric_keys):
				return False
			if any(type(snapshot[key]) is not int for key in ('observations', 'revision')):
				return False
			model = FOPDTModel(float(snapshot['gain_f_per_duty']), float(snapshot['tau_seconds']), float(snapshot['theta_seconds']), float(snapshot['confidence']), float(snapshot['residual']), snapshot['observations'], snapshot['revision'])
			model.validate()
			self._identifier.restore_trusted_model(model)
			self._predictor.set_model(model)
		except (KeyError, TypeError, ValueError, OverflowError):
			return False
		return True

	def get_status(self) -> dict:
		model = self._identifier.trusted_model
		predictor_status = self._predictor.status()
		identifier_status = self._identifier.status()
		return {
			'prediction_active': bool(predictor_status['prediction_active']),
			'controller_input_temperature': self._json_scalar(self.previous_controller_input),
			'predicted_temperature': self._json_scalar(self._predicted_temperature),
			'undelayed_model': self._json_scalar(self._predictor._undelayed_state),
			'delayed_model': self._json_scalar(self._predictor._delayed_state),
			'estimated_gain_f_per_duty': self._json_scalar(None if model is None else model.gain_f_per_duty),
			'estimated_tau_seconds': self._json_scalar(None if model is None else model.tau_seconds),
			'estimated_theta_seconds': self._json_scalar(None if model is None else model.theta_seconds),
			'model_confidence': self._json_scalar(None if model is None else model.confidence),
			'model_residual': self._json_scalar(None if model is None else model.residual),
			'accepted_observations': self._json_scalar(identifier_status['accepted_observations']),
			'model_revision': self._json_scalar(None if model is None else model.revision),
		}

	@staticmethod
	def _json_scalar(value):
		if value is None or isinstance(value, (bool, str, int)):
			return value
		if isinstance(value, float) and math.isfinite(value):
			return value
		return None
