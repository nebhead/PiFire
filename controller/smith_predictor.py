"""Adaptive FOPDT identification and Smith prediction for PID-SP.

The production lifecycle is:

1. ``record_output`` stores the duty that the grill actually applied.
2. ``AdaptiveFOPDTIdentifier.observe`` updates a bank of fixed-dead-time
   recursive least-squares estimators from eligible temperature intervals.
3. A model is published only after excitation, residual separation, physical
   bounds, uncertainty, and repeated-stability checks all pass.
4. ``SmithPredictor.update`` advances delayed and delay-free copies of that
   model and adds their difference to the measured temperature.

Every unsafe or incomplete path falls back to the measured temperature.  The
adaptive model may improve control, but it is never required for safe control.
"""

import math
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, List, Optional, Sequence, Tuple


# Physical bounds reject mathematically valid fits that cannot represent a
# grill.  They also bound every state used to correct a probe measurement.
MIN_GAIN_F = 50.0
MAX_GAIN_F = 2000.0
MIN_TAU_SECONDS = 300.0
MAX_TAU_SECONDS = 20000.0
MIN_PREDICTED_F = -100.0
MAX_PREDICTED_F = 1200.0

# Dead time is selected from a fixed bank.  Production evaluates all 25
# candidates (0, 5, ..., 120 seconds); it does not narrow around a prior winner.
MAX_DELAY_SECONDS = 120.0
DELAY_CANDIDATE_STEP_SECONDS = 5.0
DELAY_CANDIDATE_GRID = tuple(
    float(delay)
    for delay in range(
        0, int(MAX_DELAY_SECONDS) + 1, int(DELAY_CANDIDATE_STEP_SECONDS)
    )
)
# Publication gates deliberately require much more evidence than one good fit.
# The identifier learns continuously, but promotes only separated and stable
# estimates after the grill has supplied enough input and temperature movement.
RLS_FORGETTING_FACTOR = 0.9995
MIN_ACCEPTED_SECONDS = 3600.0
MIN_ACCEPTED_OBSERVATIONS = 240
MIN_DUTY_STDDEV = 0.05
MIN_DUTY_TRANSITION = 0.05
MIN_TRANSITION_SECONDS = 60.0
MIN_TEMPERATURE_SPAN_F = 15.0
MAX_CONFIRMATION_ESTIMATES = 20
MIN_DELAY_RESIDUAL_MARGIN = 0.10
MAX_GAIN_RELATIVE_STANDARD_ERROR = 0.20
MAX_TAU_RELATIVE_STANDARD_ERROR = 0.25


@dataclass(frozen=True)
class FOPDTModel:
    gain_f_per_duty: float
    tau_seconds: float
    theta_seconds: float
    confidence: float
    residual: float
    observations: int
    revision: int = 0

    def validate(self):
        values = (
            self.gain_f_per_duty,
            self.tau_seconds,
            self.theta_seconds,
            self.confidence,
            self.residual,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("FOPDT model values must be finite")
        if not MIN_GAIN_F <= self.gain_f_per_duty <= MAX_GAIN_F:
            raise ValueError("gain is outside physical bounds")
        if not MIN_TAU_SECONDS <= self.tau_seconds <= MAX_TAU_SECONDS:
            raise ValueError("tau is outside physical bounds")
        if not 0.0 <= self.theta_seconds <= 120.0:
            raise ValueError("theta is outside candidate bounds")
        if not 0.0 <= self.confidence <= 1.0 or self.residual < 0.0:
            raise ValueError("confidence or residual is invalid")
        if self.observations < 0 or self.revision < 0:
            raise ValueError("counts must be non-negative")


@dataclass(frozen=True)
class _DutyCommand:
    timestamp: float
    duty: float
    identification_allowed: bool


class DutyHistory:
    """Timeline of the duty physically applied to the auger.

    Commands are piecewise constant.  The same timeline supplies delayed model
    inputs and marks intervals that identification must ignore, such as lid-open
    handling, manual auger control, or fan-PID modulation.
    """

    def __init__(self, max_age_seconds=300.0):
        if not self._is_finite(max_age_seconds) or max_age_seconds < 0.0:
            raise ValueError("max_age_seconds must be a non-negative finite number")
        self.max_age_seconds = float(max_age_seconds)
        self._commands: List[_DutyCommand] = []

    @property
    def command_count(self):
        return len(self._commands)

    def record(self, timestamp, duty, identification_allowed):
        if not self._is_finite(timestamp) or not self._is_finite(duty):
            raise ValueError("duty history timestamp and duty must be finite")
        if not 0.0 <= duty <= 1.0:
            raise ValueError("duty must be between zero and one")

        command = _DutyCommand(
            float(timestamp), float(duty), bool(identification_allowed)
        )
        index = len(self._commands)
        while index and self._commands[index - 1].timestamp > command.timestamp:
            index -= 1

        if index and self._commands[index - 1].timestamp == command.timestamp:
            self._commands[index - 1] = command
            index -= 1
        else:
            self._commands.insert(index, command)

        self._collapse_adjacent(index)

    def value_at(self, timestamp):
        self._validate_time(timestamp)
        if not self._commands:
            return 0.0

        value = self._commands[0].duty
        for command in self._commands:
            if command.timestamp > timestamp:
                break
            value = command.duty
        return value

    def average(self, start, end, delay_seconds=0.0):
        self._validate_interval(start, end)
        if not self._is_finite(delay_seconds):
            raise ValueError("delay_seconds must be finite")

        # Shift the entire observation interval backward by a candidate's dead
        # time, then integrate every duty command crossing that shifted window.
        shifted_start = float(start) - float(delay_seconds)
        shifted_end = float(end) - float(delay_seconds)
        if shifted_end == shifted_start:
            return self.value_at(shifted_start)
        if not self._commands:
            return 0.0

        duty = self.value_at(shifted_start)
        cursor = shifted_start
        integral = 0.0
        for command in self._commands:
            if command.timestamp <= cursor:
                continue
            if command.timestamp >= shifted_end:
                break
            integral += duty * (command.timestamp - cursor)
            duty = command.duty
            cursor = command.timestamp
        integral += duty * (shifted_end - cursor)
        return integral / (shifted_end - shifted_start)

    def interval_allowed(self, start, end):
        self._validate_interval(start, end)
        if not self._commands:
            return False

        allowed = self._allowed_at(start)
        if not allowed:
            return False
        if start == end:
            return True

        for command in self._commands:
            if command.timestamp <= start:
                continue
            if command.timestamp >= end:
                break
            if not command.identification_allowed:
                return False
        return True

    def prune(self, now):
        # Keep the command immediately before the cutoff: its value remains in
        # force until the first retained command and is needed for integration.
        self._validate_time(now)
        cutoff = float(now) - self.max_age_seconds
        first_at_or_after_cutoff = 0
        while (
            first_at_or_after_cutoff < len(self._commands)
            and self._commands[first_at_or_after_cutoff].timestamp < cutoff
        ):
            first_at_or_after_cutoff += 1

        if first_at_or_after_cutoff > 0:
            del self._commands[: first_at_or_after_cutoff - 1]

    def _allowed_at(self, timestamp):
        allowed = self._commands[0].identification_allowed
        for command in self._commands:
            if command.timestamp > timestamp:
                break
            allowed = command.identification_allowed
        return allowed

    def _collapse_adjacent(self, index):
        if index > 0 and self._same_command_state(
            self._commands[index - 1], self._commands[index]
        ):
            del self._commands[index]
            index -= 1
        if index + 1 < len(self._commands) and self._same_command_state(
            self._commands[index], self._commands[index + 1]
        ):
            del self._commands[index + 1]

    @staticmethod
    def _same_command_state(first, second):
        return (
            first.duty == second.duty
            and first.identification_allowed == second.identification_allowed
        )

    @staticmethod
    def _is_finite(value):
        try:
            return math.isfinite(value)
        except TypeError:
            return False

    def _validate_time(self, timestamp):
        if not self._is_finite(timestamp):
            raise ValueError("timestamp must be finite")

    def _validate_interval(self, start, end):
        self._validate_time(start)
        self._validate_time(end)
        if end < start:
            raise ValueError("interval end must not precede start")


def _advance_state(state, duty, duration, model):
    equilibrium = model.gain_f_per_duty * duty
    return equilibrium + (state - equilibrium) * math.exp(-duration / model.tau_seconds)


class SmithPredictor:
    """Correct measured temperature with a trusted FOPDT model.

    Two model branches see the same applied-duty history.  The delayed branch
    represents the grill response; the undelayed branch represents the response
    without transport delay.  Their difference is the Smith correction.  Probe
    measurement remains the baseline so model drift cannot replace reality.
    """

    def __init__(self, units: str, clock: Callable[[], float]) -> None:
        if units not in ("F", "C"):
            raise ValueError("units must be F or C")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.units = units
        self._clock = clock
        self._history = DutyHistory()
        self._model: Optional[FOPDTModel] = None
        self._last_time: Optional[float] = None
        self._last_measured_f: Optional[float] = None
        self._undelayed_state: Optional[float] = None
        self._delayed_state: Optional[float] = None
        self._consecutive_implausible_residuals = 0
        self._prediction_active = False

    def record_output(
        self,
        duty: float,
        identification_allowed: bool = True,
        timestamp: Optional[float] = None,
    ) -> None:
        if timestamp is None:
            timestamp = self._clock()
        self._history._validate_time(timestamp)
        command_time = float(timestamp)
        if (
            self._prediction_active
            and self._last_time is not None
            and command_time < self._last_time
        ):
            raise ValueError("output timestamp precedes active predictor state")
        self._history.record(command_time, duty, identification_allowed)
        if self._model is None or not self._prediction_active:
            self._history.prune(command_time)

    def set_model(self, model: FOPDTModel) -> None:
        model.validate()
        now = float(self._clock())
        self._history._validate_time(now)
        self._history.prune(now)
        # Start both branches at the equilibrium implied by the currently
        # applied duty.  Equal states mean promotion itself adds no correction.
        state = model.gain_f_per_duty * self._history.value_at(now)

        self._model = model
        self._last_time = now
        self._last_measured_f = None
        self._undelayed_state = state
        self._delayed_state = state
        self._consecutive_implausible_residuals = 0
        self._prediction_active = True

    def clear_dynamic_state(self) -> None:
        self._last_time = None
        self._last_measured_f = None
        self._undelayed_state = None
        self._delayed_state = None
        self._consecutive_implausible_residuals = 0
        self._prediction_active = False

    def update(
        self, measured_temperature: float, timestamp: Optional[float] = None
    ) -> float:
        # Phase 1: validate external data and predictor state.  Any uncertainty
        # disables prediction and returns the probe measurement unchanged.
        if not DutyHistory._is_finite(measured_temperature):
            self._deactivate(timestamp)
            return measured_temperature
        if timestamp is None:
            timestamp = self._clock()
        if not DutyHistory._is_finite(timestamp):
            self._deactivate()
            return measured_temperature

        now = float(timestamp)
        measured_f = self._to_fahrenheit(float(measured_temperature))
        if not DutyHistory._is_finite(measured_f):
            self._deactivate(now)
            return measured_temperature
        if self._model is None:
            return measured_temperature
        if not self._prediction_active and not self._reactivate(now):
            return measured_temperature
        if (
            self._last_time is None
            or self._undelayed_state is None
            or self._delayed_state is None
            or now < self._last_time
        ):
            self._deactivate(now)
            return measured_temperature

        # Phase 2: replay applied-duty changes through both model branches.  The
        # only difference is whether command changes are shifted by theta.
        previous_time = self._last_time
        previous_delayed_state = self._delayed_state
        try:
            undelayed_state = self._advance_branch(
                self._undelayed_state, previous_time, now, 0.0
            )
            delayed_state = self._advance_branch(
                self._delayed_state, previous_time, now, self._model.theta_seconds
            )
        except (OverflowError, ValueError):
            self._deactivate(now)
            return measured_temperature

        self._last_time = now
        self._undelayed_state = undelayed_state
        self._delayed_state = delayed_state
        if not self._states_are_safe(undelayed_state, delayed_state):
            self._deactivate(now)
            return measured_temperature

        # Phase 3: compare measured movement with the delayed model's movement.
        # Four consecutive extreme mismatches indicate a stale or unsafe model;
        # isolated disturbances do not permanently disable prediction.
        if self._last_measured_f is not None and now > previous_time:
            if self._history.interval_allowed(
                previous_time - self._model.theta_seconds,
                now - self._model.theta_seconds,
            ):
                residual = (
                    measured_f
                    - self._last_measured_f
                    - (delayed_state - previous_delayed_state)
                )
                if not DutyHistory._is_finite(residual):
                    self._deactivate(now)
                    return measured_temperature
                if abs(residual) > 100.0:
                    self._consecutive_implausible_residuals += 1
                else:
                    self._consecutive_implausible_residuals = 0
                if self._consecutive_implausible_residuals >= 4:
                    self._deactivate(now)
                    return measured_temperature
            else:
                self._consecutive_implausible_residuals = 0
        self._last_measured_f = measured_f

        # Phase 4: remove only the modeled transport delay.  The correction is
        # added to the fresh measurement rather than using a free-running model.
        correction_f = undelayed_state - delayed_state
        predicted_f = measured_f + correction_f
        if not self._is_safe_prediction(correction_f, predicted_f):
            self._deactivate(now)
            return measured_temperature

        predicted_temperature = self._from_fahrenheit(predicted_f)
        if not DutyHistory._is_finite(predicted_temperature):
            self._deactivate(now)
            return measured_temperature
        self._history.prune(now)
        return predicted_temperature

    def status(self):
        return {
            "prediction_active": self._prediction_active,
            "model_revision": None if self._model is None else self._model.revision,
            "consecutive_implausible_residuals": self._consecutive_implausible_residuals,
        }

    def _advance_branch(self, state, start, end, delay_seconds):
        # Split the interval at each effective command change so a long PID
        # cycle is integrated exactly even when duty changed inside the window.
        duty = self._history.value_at(start - delay_seconds)
        cursor = start
        for command in self._history._commands:
            change_time = command.timestamp + delay_seconds
            if change_time <= cursor:
                continue
            if change_time >= end:
                break
            state = _advance_state(state, duty, change_time - cursor, self._model)
            duty = command.duty
            cursor = change_time
        return _advance_state(state, duty, end - cursor, self._model)

    def _states_are_safe(self, undelayed_state, delayed_state):
        return all(
            DutyHistory._is_finite(state)
            and MIN_PREDICTED_F <= state <= MAX_PREDICTED_F
            for state in (undelayed_state, delayed_state)
        )

    def _is_safe_prediction(self, correction_f, predicted_f):
        return all(
            DutyHistory._is_finite(value)
            and MIN_PREDICTED_F <= value <= MAX_PREDICTED_F
            for value in (correction_f, predicted_f)
        )

    def _deactivate(self, timestamp=None):
        # Deactivation is fail-safe, not destructive: retain the trusted model
        # and seed equal branches so a later valid sample can reactivate it.
        previous_time = self._last_time
        self._prediction_active = False
        self._last_time = None
        self._last_measured_f = None
        self._consecutive_implausible_residuals = 0
        state, initialized_at = self._safe_reinitialization(
            timestamp, previous_time
        )
        self._undelayed_state = state
        self._delayed_state = state
        self._last_time = initialized_at

    def _reactivate(self, now):
        if (
            self._model is None
            or self._last_time is None
            or now < self._last_time
            or not self._states_are_safe(
                self._undelayed_state, self._delayed_state
            )
        ):
            self._deactivate(now)
            return False
        try:
            self._model.validate()
        except ValueError:
            self._deactivate(now)
            return False
        self._prediction_active = True
        return True

    def _safe_reinitialization(self, timestamp, previous_time):
        now = self._reinitialization_time(timestamp, previous_time)
        if self._model is None or now is None:
            return 0.0, None
        try:
            self._model.validate()
            state = self._model.gain_f_per_duty * self._history.value_at(now)
        except (TypeError, ValueError, OverflowError):
            return 0.0, None
        if not DutyHistory._is_finite(state):
            return 0.0, None

        state = min(max(float(state), MIN_PREDICTED_F), MAX_PREDICTED_F)
        if not self._states_are_safe(state, state):
            return 0.0, None
        self._history.prune(now)
        return state, now

    def _reinitialization_time(self, timestamp, previous_time):
        candidates = [timestamp]
        try:
            candidates.append(self._clock())
        except (TypeError, ValueError, OverflowError):
            pass
        candidates.append(previous_time)
        for candidate in candidates:
            if DutyHistory._is_finite(candidate):
                return float(candidate)
        return None

    def _to_fahrenheit(self, temperature):
        if self.units == "F":
            return temperature
        return temperature * 9.0 / 5.0 + 32.0

    def _from_fahrenheit(self, temperature):
        if self.units == "F":
            return temperature
        return (temperature - 32.0) * 5.0 / 9.0


@dataclass
class _RLSCandidate:
    delay_seconds: float
    coefficients: list
    covariance: list
    residual_ewma: Optional[float] = None
    valid_updates: int = 0

    @classmethod
    def create(cls, delay_seconds):
        return cls(
            float(delay_seconds),
            [0.0, 0.0, 0.0],
            [[1e6, 0.0, 0.0], [0.0, 1e6, 0.0], [0.0, 0.0, 1e6]],
        )


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _matrix_vector(matrix, vector):
    return [_dot(row, vector) for row in matrix]


class AdaptiveFOPDTIdentifier:
    """Learn a bounded FOPDT model from eligible applied-duty history.

    Each accepted observation updates every configured dead-time candidate.
    Candidates independently estimate gain and time constant; residual error
    chooses the delay.  Selection is provisional until excitation, runner-up
    separation, uncertainty, and 20 consecutive stability checks all pass.
    """

    def __init__(
        self,
        units: str,
        clock: Callable[[], float],
        delay_candidates: Optional[Sequence[float]] = None,
    ) -> None:
        if units not in ("F", "C"):
            raise ValueError("units must be F or C")
        if not callable(clock):
            raise TypeError("clock must be callable")

        self.units = units
        self._clock = clock
        # Each delay owns independent RLS coefficients, covariance, residual,
        # and update count.  A numerical failure resets only that candidate.
        self._delay_candidates = self._validate_delay_candidates(delay_candidates)
        self._history = DutyHistory(
            max_age_seconds=2.0 * MAX_DELAY_SECONDS + MIN_TRANSITION_SECONDS
        )
        self._candidates = self._fresh_candidates()
        self._last_time: Optional[float] = None
        self._last_temperature_f: Optional[float] = None
        self._temperature_reference_f: Optional[float] = None
        self._last_output_time: Optional[float] = None
        self._transition_started_at: Optional[float] = None
        self._sustained_transition = False
        self._accepted_seconds = 0.0
        self._accepted_observations = 0
        self._duty_count = 0
        self._duty_mean = 0.0
        self._duty_m2 = 0.0
        self._temperature_min_f: Optional[float] = None
        self._temperature_max_f: Optional[float] = None
        self._confirmations: Deque[
            Tuple[float, float, float, float, float, float, float]
        ] = deque(maxlen=MAX_CONFIRMATION_ESTIMATES)
        self._trusted_model: Optional[FOPDTModel] = None

    @property
    def trusted_model(self) -> Optional[FOPDTModel]:
        return self._trusted_model

    def record_output(
        self,
        duty: float,
        identification_allowed: bool = True,
        timestamp: Optional[float] = None,
    ) -> None:
        if timestamp is None:
            timestamp = self._clock()
        self._history._validate_time(timestamp)
        if not DutyHistory._is_finite(duty) or not 0.0 <= duty <= 1.0:
            raise ValueError("duty must be between zero and one")
        now = float(timestamp)
        if self._last_output_time is not None and now < self._last_output_time:
            raise ValueError("output timestamp precedes identifier output history")

        # A material, permitted duty transition starts the excitation clock.
        # Ineligible commands remain in history for prediction but cannot teach
        # the identifier a response caused by an override or safety mechanism.
        self._mark_sustained_transition(now)
        self._history.record(now, float(duty), identification_allowed)
        self._last_output_time = now
        if not self._sustained_transition:
            self._transition_started_at = self._pending_transition_start()
        self._history.prune(now)

    def observe(
        self, temperature: float, timestamp: Optional[float] = None
    ) -> Optional[FOPDTModel]:
        if not DutyHistory._is_finite(temperature):
            return None
        if timestamp is None:
            timestamp = self._clock()
        if not DutyHistory._is_finite(timestamp):
            return None

        now = float(timestamp)
        temperature_f = self._to_fahrenheit(float(temperature))
        if not DutyHistory._is_finite(temperature_f):
            return None
        # Phase 1: establish or repair the temperature baseline.  Non-monotonic
        # timestamps break confirmation continuity because order is meaningful.
        if self._last_time is None:
            self._set_baseline(now, temperature_f)
            self._history.prune(now)
            return None
        if now <= self._last_time:
            self._set_baseline(now, temperature_f)
            self._confirmations.clear()
            self._history.prune(now)
            return None

        # Phase 2: accept only intervals whose complete applied-duty history is
        # eligible.  Rejected intervals still advance the observation baseline.
        previous_time = self._last_time
        previous_temperature_f = self._last_temperature_f
        self._mark_sustained_transition(now)
        published_model = None
        if (
            previous_temperature_f is not None
            and self._is_acceptable_interval(previous_time, now)
        ):
            published_model = self._accept_observation(
                previous_time, now, previous_temperature_f, temperature_f
            )
        else:
            self._confirmations.clear()
        self._last_time = now
        self._last_temperature_f = temperature_f
        self._history.prune(now)
        return published_model

    def restore_trusted_model(self, model: FOPDTModel) -> None:
        # Persisted state is trusted physical knowledge, not live estimator
        # state.  Restore the model, then restart evidence collection and RLS
        # candidates so stale covariance/history cannot cross process restarts.
        model.validate()
        self._trusted_model = model
        self._candidates = self._fresh_candidates()
        self._last_time = None
        self._last_temperature_f = None
        self._temperature_reference_f = None
        self._transition_started_at = None
        self._sustained_transition = False
        self._accepted_seconds = 0.0
        self._accepted_observations = 0
        self._duty_count = 0
        self._duty_mean = 0.0
        self._duty_m2 = 0.0
        self._temperature_min_f = None
        self._temperature_max_f = None
        self._confirmations.clear()

    def status(self) -> dict:
        estimate, delay_margin, eligible_candidates = self._select_candidate()
        return {
            "trusted": self._trusted_model is not None,
            "model_revision": (
                None if self._trusted_model is None else self._trusted_model.revision
            ),
            "accepted_seconds": self._accepted_seconds,
            "accepted_observations": self._accepted_observations,
            "duty_stddev": self._duty_stddev(),
            "temperature_span_f": self._temperature_span_f(),
            "sustained_transition": self._sustained_transition,
            "candidate_count": len(self._candidates),
            "eligible_candidates": eligible_candidates,
            "delay_residual_margin": delay_margin,
            "winning_delay_seconds": None if estimate is None else estimate[2],
            "gain_relative_standard_error": (
                None if estimate is None else estimate[4]
            ),
            "tau_relative_standard_error": None if estimate is None else estimate[5],
            "confirmation_count": len(self._confirmations),
        }

    @staticmethod
    def _validate_delay_candidates(
        delay_candidates: Optional[Sequence[float]],
    ) -> Tuple[float, ...]:
        if delay_candidates is None:
            return DELAY_CANDIDATE_GRID
        try:
            values = tuple(float(delay) for delay in delay_candidates)
        except TypeError as error:
            raise TypeError("delay_candidates must be a finite sequence") from error
        if not values:
            raise ValueError("delay_candidates must not be empty")
        if len(values) > len(DELAY_CANDIDATE_GRID):
            raise ValueError("delay candidates exceed the fixed candidate bank")
        if len(set(values)) != len(values):
            raise ValueError("delay candidates must be unique")
        if not all(delay in DELAY_CANDIDATE_GRID for delay in values):
            raise ValueError("delay candidates must be members of the fixed grid")
        return tuple(sorted(values))

    def _fresh_candidates(self):
        return [_RLSCandidate.create(delay) for delay in self._delay_candidates]

    def _set_baseline(self, timestamp: float, temperature_f: float) -> None:
        self._last_time = timestamp
        self._last_temperature_f = temperature_f
        if self._temperature_reference_f is None:
            self._temperature_reference_f = temperature_f

    def _mark_sustained_transition(self, now: float) -> None:
        if (
            not self._sustained_transition
            and self._transition_started_at is not None
            and now - self._transition_started_at >= MIN_TRANSITION_SECONDS
        ):
            self._sustained_transition = True

    def _pending_transition_start(self) -> Optional[float]:
        commands = self._history._commands
        if len(commands) < 2:
            return None
        previous = commands[-2]
        current = commands[-1]
        if (
            previous.identification_allowed
            and current.identification_allowed
            and abs(current.duty - previous.duty) >= MIN_DUTY_TRANSITION
        ):
            return current.timestamp
        return None

    def _is_acceptable_interval(self, start: float, end: float) -> bool:
        duration = end - start
        if (
            not DutyHistory._is_finite(duration)
            or duration <= 0.0
            or duration
            > self._history.max_age_seconds - max(self._delay_candidates)
        ):
            return False
        return self._history.interval_allowed(start, end)

    def _accept_observation(
        self,
        previous_time: float,
        now: float,
        previous_temperature_f: float,
        temperature_f: float,
    ) -> Optional[FOPDTModel]:
        duration = now - previous_time
        applied_duty = self._history.average(previous_time, now)
        if not DutyHistory._is_finite(applied_duty):
            return None

        # Track excitation globally before evaluating a fit.  These statistics
        # prevent a quiet, nearly constant cook from appearing identifiable.
        self._accepted_seconds += duration
        self._accepted_observations += 1
        self._update_duty_statistics(applied_duty)
        interval_min_f = min(previous_temperature_f, temperature_f)
        interval_max_f = max(previous_temperature_f, temperature_f)
        self._temperature_min_f = (
            interval_min_f
            if self._temperature_min_f is None
            else min(self._temperature_min_f, interval_min_f)
        )
        self._temperature_max_f = (
            interval_max_f
            if self._temperature_max_f is None
            else max(self._temperature_max_f, interval_max_f)
        )
        # Every accepted sample updates the full fixed-delay bank.  Delay is
        # recovered by comparing the candidates, not estimated as an RLS term.
        for index in range(len(self._candidates)):
            self._update_candidate(
                index,
                previous_time,
                now,
                previous_temperature_f,
                temperature_f,
            )
        return self._consider_estimate()

    def _update_duty_statistics(self, duty: float) -> None:
        self._duty_count += 1
        delta = duty - self._duty_mean
        self._duty_mean += delta / self._duty_count
        self._duty_m2 += delta * (duty - self._duty_mean)

    def _update_candidate(
        self,
        index: int,
        previous_time: float,
        now: float,
        previous_temperature_f: float,
        temperature_f: float,
    ) -> None:
        candidate = self._candidates[index]
        try:
            # A candidate sees the applied duty shifted by its assumed delay.
            # If any part of that interval was ineligible, skip this update.
            if not self._history.interval_allowed(
                previous_time - candidate.delay_seconds,
                now - candidate.delay_seconds,
            ):
                return
            delayed_average_duty = self._history.average(
                previous_time, now, candidate.delay_seconds
            )
            duration = now - previous_time
            if (
                self._temperature_reference_f is None
                or not self._candidate_matrix_is_finite(candidate.covariance)
                or not all(
                    DutyHistory._is_finite(value)
                    for value in (
                        duration,
                        previous_temperature_f,
                        temperature_f,
                        delayed_average_duty,
                    )
                )
                or duration <= 0.0
            ):
                raise ValueError("candidate update is non-finite")

            # Regress temperature rate against offset, temperature, and delayed
            # applied duty.  Scaling temperature keeps the covariance well sized.
            z = (
                previous_temperature_f - self._temperature_reference_f
            ) / 500.0
            phi = [1.0, z, delayed_average_duty]
            y = (temperature_f - previous_temperature_f) / duration
            if not all(DutyHistory._is_finite(value) for value in phi + [y]):
                raise ValueError("candidate regression values are non-finite")

            # Standard recursive least squares: compute P*phi, innovation gain,
            # prediction error, then update coefficients and covariance.
            p_phi = _matrix_vector(candidate.covariance, phi)
            denominator = RLS_FORGETTING_FACTOR + _dot(phi, p_phi)
            if (
                not all(DutyHistory._is_finite(value) for value in p_phi)
                or not DutyHistory._is_finite(denominator)
                or denominator <= 1e-12
            ):
                raise ValueError("candidate covariance is numerically invalid")
            gain_vector = [value / denominator for value in p_phi]
            error = y - _dot(phi, candidate.coefficients)
            if not all(
                DutyHistory._is_finite(value) for value in gain_vector + [error]
            ):
                raise ValueError("candidate gain is non-finite")

            coefficients = [
                value + gain_component * error
                for value, gain_component in zip(
                    candidate.coefficients, gain_vector
                )
            ]
            covariance = [
                [
                    (
                        candidate.covariance[row][column]
                        - gain_vector[row]
                        * sum(
                            phi[covariance_index]
                            * candidate.covariance[covariance_index][column]
                            for covariance_index in range(3)
                        )
                    )
                    / RLS_FORGETTING_FACTOR
                    for column in range(3)
                ]
                for row in range(3)
            ]
            # Residual EWMA makes recent prediction quality comparable across
            # candidates without retaining every historical observation.
            squared_error = error * error
            residual_ewma = (
                squared_error
                if candidate.residual_ewma is None
                else 0.98 * candidate.residual_ewma + 0.02 * squared_error
            )
            if not (
                all(DutyHistory._is_finite(value) for value in coefficients)
                and self._candidate_matrix_is_finite(covariance)
                and DutyHistory._is_finite(squared_error)
                and DutyHistory._is_finite(residual_ewma)
            ):
                raise ValueError("candidate update overflowed")
            candidate.coefficients = coefficients
            candidate.covariance = covariance
            candidate.residual_ewma = residual_ewma
            candidate.valid_updates += 1
        except (ArithmeticError, OverflowError, TypeError, ValueError):
            self._candidates[index] = _RLSCandidate.create(candidate.delay_seconds)

    @staticmethod
    def _candidate_matrix_is_finite(matrix) -> bool:
        try:
            return len(matrix) == 3 and all(
                len(row) == 3
                and all(DutyHistory._is_finite(value) for value in row)
                for row in matrix
            )
        except TypeError:
            return False

    def _candidate_estimate(
        self, candidate: _RLSCandidate
    ) -> Optional[Tuple[float, float, float, float, float, float]]:
        if (
            self._temperature_reference_f is None
            or candidate.valid_updates < MIN_ACCEPTED_OBSERVATIONS
            or candidate.residual_ewma is None
            or not all(
                DutyHistory._is_finite(value)
                for value in candidate.coefficients + [candidate.residual_ewma]
            )
            or not self._candidate_matrix_is_finite(candidate.covariance)
            or candidate.residual_ewma < 0.0
        ):
            return None

        beta_t = candidate.coefficients[1] / 500.0
        beta_u = candidate.coefficients[2]
        beta_0 = candidate.coefficients[0] - beta_t * self._temperature_reference_f
        if not (
            all(DutyHistory._is_finite(value) for value in (beta_t, beta_u, beta_0))
            and beta_t < 0.0
        ):
            return None
        try:
            tau = -1.0 / beta_t
            gain_f = -beta_u / beta_t
            offset_f = -beta_0 / beta_t
        except (OverflowError, ZeroDivisionError):
            return None
        if not (
            all(DutyHistory._is_finite(value) for value in (tau, gain_f, offset_f))
            and MIN_GAIN_F <= gain_f <= MAX_GAIN_F
            and MIN_TAU_SECONDS <= tau <= MAX_TAU_SECONDS
            and 0.0 <= candidate.delay_seconds <= MAX_DELAY_SECONDS
        ):
            return None

        residual = candidate.residual_ewma
        covariance = candidate.covariance
        try:
            var_beta_t = residual * covariance[1][1] / (500.0 * 500.0)
            var_beta_u = residual * covariance[2][2]
            cov_beta = residual * covariance[1][2] / 500.0
            var_tau = var_beta_t / (beta_t ** 4)
            d_gain_d_beta_t = beta_u / (beta_t ** 2)
            d_gain_d_beta_u = -1.0 / beta_t
            var_gain = (
                d_gain_d_beta_t ** 2 * var_beta_t
                + d_gain_d_beta_u ** 2 * var_beta_u
                + 2.0 * d_gain_d_beta_t * d_gain_d_beta_u * cov_beta
            )
        except (OverflowError, ZeroDivisionError):
            return None
        if not (
            all(
                DutyHistory._is_finite(value)
                for value in (
                    var_beta_t,
                    var_beta_u,
                    cov_beta,
                    var_tau,
                    d_gain_d_beta_t,
                    d_gain_d_beta_u,
                    var_gain,
                )
            )
            and var_tau >= 0.0
            and var_gain >= 0.0
        ):
            return None
        gain_relative_standard_error = math.sqrt(var_gain) / gain_f
        tau_relative_standard_error = math.sqrt(var_tau) / tau
        if not (
            all(
                DutyHistory._is_finite(value)
                for value in (
                    gain_relative_standard_error,
                    tau_relative_standard_error,
                )
            )
            and gain_relative_standard_error <= MAX_GAIN_RELATIVE_STANDARD_ERROR
            and tau_relative_standard_error <= MAX_TAU_RELATIVE_STANDARD_ERROR
        ):
            return None
        return (
            gain_f,
            tau,
            candidate.delay_seconds,
            residual,
            gain_relative_standard_error,
            tau_relative_standard_error,
        )

    def _select_candidate(
        self,
    ) -> Tuple[
        Optional[Tuple[float, float, float, float, float, float]], float, int
    ]:
        winner = None
        runner_up_residual = None
        eligible_candidates = 0
        # Only physically bounded, sufficiently sampled, low-uncertainty fits
        # compete.  Keep both best residuals so delay must win decisively rather
        # than by numerical noise between adjacent five-second candidates.
        for candidate in self._candidates:
            estimate = self._candidate_estimate(candidate)
            if estimate is None:
                continue
            eligible_candidates += 1
            if winner is None or estimate[3] < winner[3]:
                if winner is not None:
                    runner_up_residual = winner[3]
                winner = estimate
            elif runner_up_residual is None or estimate[3] < runner_up_residual:
                runner_up_residual = estimate[3]
        if winner is None or runner_up_residual is None or runner_up_residual <= 0.0:
            return winner, 0.0, eligible_candidates
        delay_margin = max(
            0.0, (runner_up_residual - winner[3]) / runner_up_residual
        )
        return winner, delay_margin, eligible_candidates

    def _consider_estimate(self) -> Optional[FOPDTModel]:
        # Phase 1: require a viable winner, at least 10% residual separation,
        # and enough independent excitation to identify the plant.
        estimate, delay_margin, _ = self._select_candidate()
        if (
            estimate is None
            or delay_margin < MIN_DELAY_RESIDUAL_MARGIN
            or not self._excitation_is_sufficient()
        ):
            self._confirmations.clear()
            return None

        # Phase 2: avoid republishing insignificant movement around an existing
        # trusted model; such churn would reset predictor state needlessly.
        if self._trusted_model is not None and not self._is_material(estimate):
            self._confirmations.clear()
            return None
        # Phase 3: confirmation is consecutive.  A changing winning delay clears
        # the window because gain/tau stability under different delays is not
        # evidence that any single model is trustworthy.
        if self._confirmations and self._confirmations[0][2] != estimate[2]:
            self._confirmations.clear()
        self._confirmations.append(
            (
                estimate[0],
                estimate[1],
                estimate[2],
                estimate[3],
                estimate[4],
                estimate[5],
                delay_margin,
            )
        )
        if not self._confirmation_is_stable():
            return None

        # Phase 4: publish after 20 stable winners.  Smooth gain and tau when
        # revising a model, but take the discrete winning delay directly.
        confirmation_count = len(self._confirmations)
        confidence = max(
            0.0,
            min(
                1.0,
                delay_margin / 0.10,
                0.20 / max(estimate[4], 1e-12),
                0.25 / max(estimate[5], 1e-12),
                confirmation_count / 20.0,
            ),
        )
        if self._trusted_model is None:
            model = FOPDTModel(
                estimate[0],
                estimate[1],
                estimate[2],
                confidence,
                estimate[3],
                self._accepted_observations,
                1,
            )
        else:
            model = FOPDTModel(
                0.9 * self._trusted_model.gain_f_per_duty + 0.1 * estimate[0],
                0.9 * self._trusted_model.tau_seconds + 0.1 * estimate[1],
                estimate[2],
                confidence,
                estimate[3],
                self._accepted_observations,
                self._trusted_model.revision + 1,
            )
        try:
            model.validate()
        except ValueError:
            self._confirmations.clear()
            return None
        self._trusted_model = model
        self._confirmations.clear()
        return model

    def _excitation_is_sufficient(self) -> bool:
        return (
            self._accepted_seconds >= MIN_ACCEPTED_SECONDS
            and self._accepted_observations >= MIN_ACCEPTED_OBSERVATIONS
            and self._duty_stddev() >= MIN_DUTY_STDDEV
            and self._sustained_transition
            and self._temperature_span_f() >= MIN_TEMPERATURE_SPAN_F
        )

    def _is_material(
        self, estimate: Tuple[float, float, float, float, float, float]
    ) -> bool:
        model = self._trusted_model
        if model is None:
            return False
        return (
            abs(estimate[0] - model.gain_f_per_duty) / model.gain_f_per_duty
            >= 0.05
            or abs(estimate[1] - model.tau_seconds) / model.tau_seconds >= 0.05
            or abs(estimate[2] - model.theta_seconds) >= 5.0
        )

    def _confirmation_is_stable(self) -> bool:
        if len(self._confirmations) < MAX_CONFIRMATION_ESTIMATES:
            return False
        gains = [estimate[0] for estimate in self._confirmations]
        taus = [estimate[1] for estimate in self._confirmations]
        delays = [estimate[2] for estimate in self._confirmations]
        gain_mean = sum(gains) / len(gains)
        tau_mean = sum(taus) / len(taus)
        return (
            all(delay == delays[0] for delay in delays)
            and (max(gains) - min(gains)) / gain_mean <= 0.05
            and (max(taus) - min(taus)) / tau_mean <= 0.075
        )

    def _duty_stddev(self) -> float:
        if self._duty_count == 0:
            return 0.0
        return math.sqrt(max(0.0, self._duty_m2 / self._duty_count))

    def _temperature_span_f(self) -> float:
        if self._temperature_min_f is None or self._temperature_max_f is None:
            return 0.0
        return self._temperature_max_f - self._temperature_min_f

    def _to_fahrenheit(self, temperature: float) -> float:
        if self.units == "F":
            return temperature
        return temperature * 9.0 / 5.0 + 32.0
