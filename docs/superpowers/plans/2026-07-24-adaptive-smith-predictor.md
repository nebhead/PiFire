# Adaptive Smith Predictor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PID-SP's rate extrapolation with a confidence-gated adaptive FOPDT Smith predictor driven by applied auger duty, persist trusted physical parameters, and verify it across small, medium, and large simulated grills through 600°F.

**Architecture:** `controller/smith_predictor.py` owns bounded command history, exact first-order model propagation, banked-delay RLS identification, and immutable physical-model snapshots. PID-SP composes those objects and exposes optional runtime hooks; pure runtime/persistence adapters keep `control.py` changes narrow and JSON-safe. The simulator supplies deterministic time, exact applied-duty feedback, three named plants, and model diagnostics.

**Tech Stack:** Python 3.14 standard library, `unittest`, existing PiFire controller interface, JSON, deterministic simulator.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-24-adaptive-smith-predictor-design.md` exactly.
- Runtime estimator/predictor and simulator remain Python-standard-library only.
- Keep all per-update work and memory bounded for Raspberry Pi operation.
- Do not inject identification excitation into production commands.
- Feed the model only actual applied duty after clamping; record manual 0/1 override transitions exactly.
- Preserve other PID controllers' equations and behavior.
- Use one Smith temperature consistently for PID-SP proportional, integral, and derivative terms.
- Persist trusted `K`, `tau`, and `theta` indefinitely; never persist dynamic model state or command history.
- Keep Python syntax compatible with 3.9; do not use `X | Y` annotations or parameterized built-in collections where existing compatibility checks reject them.
- Use the repository-safe VCS workflow from the required `jujutsu` skill before every commit/status operation.

---

### Task 1: Capture the pre-change PID-SP baseline

**Files:**
- Read: `pid_simulator.py`
- Create runtime artifact only: `/tmp/adaptive-smith-before.txt`

**Interfaces:**
- Consumes: Current `pid_simulator.py` CLI.
- Produces: Immutable before-results used by Task 8; no source changes.

- [ ] **Step 1: Run the existing medium-plant PID-SP comparison**

Run:

```bash
python3 pid_simulator.py --scenario all --controller pid_sp > /tmp/adaptive-smith-before.txt
```

Expected: exit 0; output begins with `PID controller simulation` and contains six summary rows: three scenarios × two setpoint modes.

- [ ] **Step 2: Verify the baseline artifact is complete**

Run:

```bash
python3 -c "from pathlib import Path; p=Path('/tmp/adaptive-smith-before.txt'); s=p.read_text(); assert s.startswith('PID controller simulation'); assert all(x in s for x in ('250','350','450','production-reset','continuous','pid_sp')); print(len(s.splitlines()))"
```

Expected: a positive line count and exit 0.

---

### Task 2: Implement bounded duty history and exact Smith model propagation

**Files:**
- Create: `controller/smith_predictor.py`
- Create: `tests/test_smith_predictor.py`

**Interfaces:**
- Produces:
  - `FOPDTModel(gain_f_per_duty, tau_seconds, theta_seconds, confidence, residual, observations, revision)` immutable dataclass.
  - `DutyHistory(max_age_seconds=300.0)` with `record(timestamp, duty, identification_allowed)`, `value_at(timestamp)`, `average(start, end, delay_seconds=0.0)`, `interval_allowed(start, end)`, and `prune(now)`.
  - `SmithPredictor(units, clock)` with `record_output(duty, identification_allowed=True, timestamp=None)`, `set_model(model)`, `clear_dynamic_state()`, `update(measured_temperature, timestamp=None)`, and `status()`.
- Consumes: A zero-argument clock callable and native-unit temperatures.

- [ ] **Step 1: Write failing history and predictor tests**

Add tests with a deterministic callable clock:

```python
class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def model(gain=600.0, tau=300.0, delay=20.0, revision=1):
    return FOPDTModel(gain, tau, delay, 0.95, 0.1, 300, revision)
```

Required test contracts:

```python
def test_duty_history_time_weights_fractional_boundaries(self):
    history = DutyHistory(max_age_seconds=300.0)
    history.record(0.0, 0.2, True)
    history.record(10.0, 0.8, True)
    self.assertAlmostEqual(history.average(5.0, 15.0), 0.5)
    self.assertAlmostEqual(history.average(25.0, 35.0, delay_seconds=20.0), 0.5)


def test_duty_history_retains_one_predecessor_when_pruned(self):
    history = DutyHistory(max_age_seconds=30.0)
    for second in range(0, 101, 10):
        history.record(float(second), second / 100.0, True)
    history.prune(100.0)
    self.assertEqual(history.value_at(70.0), 0.7)
    self.assertLessEqual(history.command_count, 5)


def test_smith_predictor_starts_with_zero_correction(self):
    clock = FakeClock()
    predictor = SmithPredictor("F", clock)
    predictor.record_output(0.2)
    predictor.set_model(model())
    self.assertEqual(predictor.update(250.0), 250.0)


def test_smith_predictor_integrates_delayed_boundary_exactly(self):
    clock = FakeClock()
    predictor = SmithPredictor("F", clock)
    predictor.record_output(0.2)
    predictor.set_model(model(gain=600.0, tau=300.0, delay=20.0))
    predictor.update(250.0)
    clock.now = 10.0
    predictor.record_output(0.8)
    clock.now = 40.0
    predicted = predictor.update(250.0)
    undelayed = 120.0 * math.exp(-30.0 / 300.0) + 480.0 * (1.0 - math.exp(-30.0 / 300.0))
    delayed = 120.0 * math.exp(-10.0 / 300.0) + 480.0 * (1.0 - math.exp(-10.0 / 300.0))
    self.assertAlmostEqual(predicted, 250.0 + undelayed - delayed, places=9)


def test_invalid_model_and_nonfinite_state_fall_back_to_measured(self):
    predictor = SmithPredictor("F", FakeClock())
    with self.assertRaises(ValueError):
        predictor.set_model(model(tau=0.0))
    predictor.record_output(0.2)
    predictor.set_model(model())
    predictor._undelayed_state = math.nan
    self.assertEqual(predictor.update(275.0), 275.0)
    self.assertFalse(predictor.status()["prediction_active"])


def test_celsius_uses_the_same_fahrenheit_model_correction(self):
    fahrenheit_clock = FakeClock()
    celsius_clock = FakeClock()
    fahrenheit = SmithPredictor("F", fahrenheit_clock)
    celsius = SmithPredictor("C", celsius_clock)
    for predictor in (fahrenheit, celsius):
        predictor.record_output(0.2)
        predictor.set_model(model())
    fahrenheit.update(250.0)
    celsius.update((250.0 - 32.0) * 5.0 / 9.0)
    fahrenheit_clock.now = celsius_clock.now = 10.0
    fahrenheit.record_output(0.8)
    celsius.record_output(0.8)
    fahrenheit_clock.now = celsius_clock.now = 40.0
    f_correction = fahrenheit.update(250.0) - 250.0
    measured_c = (250.0 - 32.0) * 5.0 / 9.0
    c_correction = celsius.update(measured_c) - measured_c
    self.assertAlmostEqual(c_correction, f_correction * 5.0 / 9.0)


def test_four_implausible_one_step_residuals_disable_prediction(self):
    clock = FakeClock()
    predictor = SmithPredictor("F", clock)
    predictor.record_output(0.2)
    predictor.set_model(model())
    predictor.update(250.0)
    for index, temperature in enumerate((400.0, 550.0, 700.0, 850.0), 1):
        clock.now = index * 15.0
        predictor.update(temperature)
    self.assertFalse(predictor.status()["prediction_active"])
```

- [ ] **Step 2: Run the new tests and confirm the missing-module failure**

Run:

```bash
python3 -m unittest tests.test_smith_predictor -v
```

Expected: FAIL because `controller.smith_predictor` does not exist.

- [ ] **Step 3: Implement immutable model validation and bounded history**

Use these exact invariants in `controller/smith_predictor.py`:

```python
MIN_GAIN_F = 50.0
MAX_GAIN_F = 2000.0
MIN_TAU_SECONDS = 300.0
MAX_TAU_SECONDS = 20000.0
MIN_PREDICTED_F = -100.0
MAX_PREDICTED_F = 1200.0

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
        values = (self.gain_f_per_duty, self.tau_seconds, self.theta_seconds,
                  self.confidence, self.residual)
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
```

`DutyHistory.record()` must reject non-finite timestamps/duties and duty outside `[0, 1]`; replace the last command at an identical timestamp; collapse only truly identical adjacent commands. `average()` must integrate piecewise-constant duty exactly, treating the first known command as prehistory. `interval_allowed()` must return false if any segment intersecting the interval is marked invalid. `prune()` must retain the command immediately before the cutoff.

- [ ] **Step 4: Implement exact first-order Smith propagation**

Use the closed-form segment update, never Euler stepping:

```python
def _advance_state(state, duty, duration, model):
    equilibrium = model.gain_f_per_duty * duty
    return equilibrium + (state - equilibrium) * math.exp(-duration / model.tau_seconds)
```

At model activation initialize both states to `K × current_duty`. For update interval `[last_time, now]`, advance the undelayed branch at actual command timestamps and the delayed branch at timestamps shifted by `theta`. Convert only the final correction between Fahrenheit and Celsius (`delta_C = delta_F × 5/9`). Track the one-step residual as measured change minus delayed-model change only across identification-allowed intervals; four consecutive absolute residuals above 100°F disable dynamic prediction. Return measured temperature and deactivate dynamic prediction if any state/correction/output is non-finite or outside broad physical bounds.

- [ ] **Step 5: Run predictor tests**

Run:

```bash
python3 -m unittest tests.test_smith_predictor -v
```

Expected: all Task 2 tests PASS.

- [ ] **Step 6: Commit the predictor core**

```bash
git add controller/smith_predictor.py tests/test_smith_predictor.py
git commit -m "Add exact FOPDT Smith model core"
```

---

### Task 3: Implement the banked-delay adaptive identifier

**Files:**
- Modify: `controller/smith_predictor.py`
- Modify: `tests/test_smith_predictor.py`

**Interfaces:**
- Produces `AdaptiveFOPDTIdentifier(units, clock, delay_candidates=None)` with:
  - `record_output(duty, identification_allowed=True, timestamp=None)`
  - `observe(temperature, timestamp=None) -> Optional[FOPDTModel]`
  - `restore_trusted_model(model)`
  - `trusted_model` property
  - `status() -> dict`
- Consumes `FOPDTModel` and `DutyHistory` from Task 2.

- [ ] **Step 1: Write failing estimator recovery and confidence tests**

Add a deterministic FOPDT generator that advances at one-second resolution, changes commanded duty every 300–900 seconds, records controller observations every 15 seconds, and supports irregular observation offsets `(15, 31, 46, 62, ...)`. Use exact plant triples from the specification.

Required contracts:

```python
def test_identifier_recovers_small_medium_and_large_models(self):
    profiles = (
        (640.0, 3333.3333333333335, 20.0),
        (647.0588235294117, 4705.882352941177, 35.0),
        (700.0, 6500.0, 50.0),
    )
    for gain, tau, delay in profiles:
        with self.subTest(gain=gain, tau=tau, delay=delay):
            estimate = identify_synthetic_fopdt(gain, tau, delay)
            self.assertIsNotNone(estimate)
            self.assertAlmostEqual(estimate.gain_f_per_duty, gain, delta=gain * 0.10)
            self.assertAlmostEqual(estimate.tau_seconds, tau, delta=tau * 0.15)
            self.assertAlmostEqual(estimate.theta_seconds, delay, delta=5.0)


def test_identifier_does_not_trust_constant_duty(self):
    estimate, status = identify_constant_duty(duration_seconds=8 * 3600)
    self.assertIsNone(estimate)
    self.assertFalse(status["trusted"])
    self.assertLess(status["duty_stddev"], 0.05)


def test_identifier_rejects_ambiguous_delay(self):
    identifier = AdaptiveFOPDTIdentifier("F", FakeClock())
    feed_data_with_no_delayed_input_separation(identifier)
    self.assertIsNone(identifier.trusted_model)
    self.assertLess(identifier.status()["delay_residual_margin"], 0.10)


def test_disturbed_interval_does_not_create_observation(self):
    clock = FakeClock()
    identifier = AdaptiveFOPDTIdentifier("F", clock)
    identifier.record_output(0.2, True)
    identifier.observe(200.0)
    clock.now = 15.0
    identifier.record_output(1.0, False)
    clock.now = 45.0
    identifier.observe(240.0)
    self.assertEqual(identifier.status()["accepted_observations"], 0)
    clock.now = 60.0
    identifier.record_output(0.3, True)
    identifier.observe(241.0)
    clock.now = 75.0
    identifier.observe(242.0)
    self.assertEqual(identifier.status()["accepted_observations"], 1)
```

Also test negative gain, unstable beta, NaN, and out-of-bounds candidates remain ineligible.

- [ ] **Step 2: Run the identifier tests and confirm failure**

Run:

```bash
python3 -m unittest tests.test_smith_predictor -v
```

Expected: FAIL because `AdaptiveFOPDTIdentifier` is missing.

- [ ] **Step 3: Implement fixed-size RLS candidates**

For every candidate `theta = 0, 5, ..., 120`, maintain only:

```python
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
```

For `z = (T_previous_F - temperature_reference_F) / 500.0`, `phi = [1.0, z, delayed_average_duty]`, and `y = (T_current_F - T_previous_F) / dt`, update with:

```python
p_phi = _matrix_vector(candidate.covariance, phi)
denominator = 0.9995 + _dot(phi, p_phi)
gain_vector = [value / denominator for value in p_phi]
error = y - _dot(phi, candidate.coefficients)
candidate.coefficients = [
    value + gain_component * error
    for value, gain_component in zip(candidate.coefficients, gain_vector)
]
candidate.covariance = [
    [
        (candidate.covariance[row][column]
         - gain_vector[row] * sum(phi[index] * candidate.covariance[index][column] for index in range(3)))
        / 0.9995
        for column in range(3)
    ]
    for row in range(3)
]
candidate.residual_ewma = (
    error * error if candidate.residual_ewma is None
    else 0.98 * candidate.residual_ewma + 0.02 * error * error
)
```

Transform coefficients back with:

```python
beta_t = coefficients[1] / 500.0
beta_u = coefficients[2]
beta_0 = coefficients[0] - beta_t * temperature_reference_f
tau = -1.0 / beta_t
gain_f = -beta_u / beta_t
offset_f = -beta_0 / beta_t
```

Guard every division and update with finite checks. Reset only the failed candidate to its initial matrix.

- [ ] **Step 4: Implement excitation, uncertainty, delay, and confirmation gates**

Use the exact thresholds from the specification: 3600 accepted seconds, 240 observations, duty standard deviation 0.05, a 0.05 duty transition held 60 seconds, 15°F temperature span, physical bounds, relative standard errors 20% for gain and 25% for tau, winning residual margin 10%, and 20 stable estimates with gain spread ≤5%, tau spread ≤7.5%, and one unchanged delay.
Maintain excitation with constant-memory Welford count/mean/M2 statistics for accepted applied duty, running temperature min/max, accepted seconds/count, and a boolean sustained-transition latch. Keep only the 20-sample confirmation deque; never retain an unbounded observation list.

Compute uncertainty with residual-scaled covariance and the delta method:

```python
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
```
For a gate-passing estimate, publish bounded confidence with:

```python
confidence = max(
    0.0,
    min(
        1.0,
        delay_residual_margin / 0.10,
        0.20 / max(gain_relative_standard_error, 1e-12),
        0.25 / max(tau_relative_standard_error, 1e-12),
        confirmation_count / 20.0,
    ),
)
```

On first trust publish revision 1. A later candidate is material only after the same confirmation and a ≥5% gain/tau or ≥5-second delay change; blend gain/tau by 0.1 and increment revision. Restoration sets the trusted model immediately but leaves RLS matrices fresh.

- [ ] **Step 5: Run estimator tests**

Run:

```bash
python3 -m unittest tests.test_smith_predictor -v
```

Expected: predictor and identifier tests PASS for all three physical profiles.

- [ ] **Step 6: Commit adaptive identification**

```bash
git add controller/smith_predictor.py tests/test_smith_predictor.py
git commit -m "Identify FOPDT parameters from applied duty"
```

---

### Task 4: Replace PID-SP extrapolation with the adaptive Smith signal

**Files:**
- Modify: `controller/pid_sp.py`
- Modify: `controller/controllers.json`
- Modify: `tests/test_pid_sp.py`

**Interfaces:**
- Consumes `AdaptiveFOPDTIdentifier`, `FOPDTModel`, and `SmithPredictor` from Task 3.
- Produces optional controller hooks:
  - `set_output(applied_ratio, identification_allowed=True)`
  - `get_model_snapshot() -> Optional[dict]`
  - `restore_model(snapshot) -> bool`
  - `get_status() -> dict`
- Preserves `Controller(config, units, cycle_data)`, `update(current)`, `set_target(set_point)`, `set_gains(...)`, and `get_k()`.

- [ ] **Step 1: Rewrite PID-SP tests around observable Smith behavior**

Remove `tau`/`theta` from `CONFIG`, remove the obsolete configured-parameter rejection and metadata-minimum tests, and retain first-sample, target baseline, startup reduction, and integral-bound contracts without asserting `roc`.

Add:

```python
def trusted_snapshot(gain=647.0588235294117, tau=4705.882352941177, theta=35.0):
    return {
        "version": 1,
        "gain_f_per_duty": gain,
        "tau_seconds": tau,
        "theta_seconds": theta,
        "confidence": 0.95,
        "residual": 0.01,
        "observations": 500,
        "revision": 1,
    }


def test_measured_temperature_is_used_before_model_trust(self):
    controller = self.make_controller()
    controller.set_target(250.0)
    controller.update(240.0)
    self.assertFalse(controller.get_status()["prediction_active"])
    self.assertEqual(controller.get_status()["controller_input_temperature"], 240.0)


def test_restored_model_drives_one_temperature_for_p_i_and_d(self):
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller()
        self.assertTrue(controller.restore_model(trusted_snapshot()))
        controller.set_target(250.0)
        controller.set_output(0.2)
    with patch("controller.pid_sp.time.time", return_value=15.0):
        controller.update(240.0)
        controller.set_output(0.8)
    previous_selected = controller.get_status()["controller_input_temperature"]
    with patch("controller.pid_sp.time.time", return_value=60.0):
        controller.update(242.0)
    status = controller.get_status()
    selected = status["controller_input_temperature"]
    self.assertAlmostEqual(controller.p, controller.kp * (selected - 250.0) + controller.center)
    self.assertAlmostEqual(controller.derv, (selected - previous_selected) / 45.0)


def test_set_target_preserves_model_and_identifier_state(self):
    controller = self.make_controller()
    controller.restore_model(trusted_snapshot())
    controller.set_output(0.3)
    before = controller.get_model_snapshot()
    accepted = controller.get_status()["accepted_observations"]
    controller.set_target(350.0)
    self.assertEqual(controller.get_model_snapshot(), before)
    self.assertEqual(controller.get_status()["accepted_observations"], accepted)


def test_snapshot_validation_and_status_are_json_safe(self):
    controller = self.make_controller()
    self.assertFalse(controller.restore_model(dict(trusted_snapshot(), tau_seconds=0.0)))
    controller.restore_model(trusted_snapshot())
    json.dumps(controller.get_status())
    json.dumps(controller.get_model_snapshot())


def test_metadata_no_longer_exposes_fixed_model_parameters(self):
    metadata = json.loads(Path("controller/controllers.json").read_text())["metadata"]["pid_sp"]
    option_names = {option["option_name"] for option in metadata["config"]}
    self.assertNotIn("tau", option_names)
    self.assertNotIn("theta", option_names)
```

- [ ] **Step 2: Run PID-SP tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_pid_sp -v
```

Expected: FAIL on missing runtime hooks and still-present metadata.

- [ ] **Step 3: Integrate identifier and predictor in PID-SP**

In `__init__`, append `set_output`, `get_model_snapshot`, `restore_model`, and `get_status` to `function_list`; instantiate both components with `clock=lambda: time.time()` so later simulator replacements and unit-test patches remain visible; remove configured `tau`, `theta`, `_validate_predictor_config`, and `roc` state; add `previous_controller_input = None`.

Use this update order:

```python
current_time = time.time()
trusted_update = self._identifier.observe(current, current_time)
if trusted_update is not None:
    self._predictor.set_model(trusted_update)
controller_input = self._predictor.update(current, current_time)
error = controller_input - self.set_point
```

Use `error` for overshoot, reset, P, and I decisions. Compute derivative as zero on the first selected sample, otherwise `(controller_input - previous_controller_input) / dt`. Save measured `current` in `self.last` for setpoint-transition bookkeeping and selected input in `previous_controller_input` for derivative. Preserve the corrected output-first startup reduction and integral accumulator clamp.

`set_output()` must pass the same timestamp and command to identifier and predictor. `set_target()` must not recreate either component or clear model/duty state.

- [ ] **Step 4: Implement snapshots and JSON-safe diagnostics**

Snapshot keys must exactly match `trusted_snapshot()` above. `restore_model()` checks version 1, constructs/validates `FOPDTModel`, restores it into both components, and returns false rather than raising for malformed external data. `get_status()` returns only scalar JSON values and includes `prediction_active`, `controller_input_temperature`, `predicted_temperature`, `undelayed_model`, `delayed_model`, `estimated_gain_f_per_duty`, `estimated_tau_seconds`, `estimated_theta_seconds`, `model_confidence`, `model_residual`, `accepted_observations`, and `model_revision`.

- [ ] **Step 5: Remove fixed model options from metadata**

Delete the complete `tau` and `theta` option objects from PID-SP's `config` array. Update the PID-SP description to say gain, time constant, and dead time are learned from applied duty and temperature. Reformat the JSON with the existing `jq` convention.

- [ ] **Step 6: Run PID-SP and Smith tests**

Run:

```bash
python3 -m unittest tests.test_smith_predictor tests.test_pid_sp -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit PID-SP integration**

```bash
git add controller/pid_sp.py controller/controllers.json tests/test_pid_sp.py
git commit -m "Use adaptive Smith feedback in PID-SP"
```

---

### Task 5: Add atomic durable model storage and optional-controller adapters

**Files:**
- Create: `common/adaptive_controller_state.py`
- Create: `controller/runtime.py`
- Create: `tests/test_adaptive_controller_state.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces `AdaptiveControllerStateStore(path=Path("adaptive_controller_state.json"), clock=time.time, min_write_interval=1800.0)` with `load(name)`, `stage(name, snapshot)`, and `flush(force=False)`.
- Produces runtime adapter functions:
  - `supports(controller, function_name)`
  - `record_output(controller, duty, identification_allowed=True)`
  - `restore_model(controller, store, name)`
  - `stage_model(controller, store, name)`
  - `diagnostics(controller)`
  - `apply_live_hold_target(controller, active_mode, control) -> bool`

- [ ] **Step 1: Write failing state-store and adapter tests**

Use `tempfile.TemporaryDirectory`, fake clocks, and fake controllers. Required contracts:

```python
def test_state_store_round_trips_without_age_expiry(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "adaptive.json"
        clock = FakeClock()
        store = AdaptiveControllerStateStore(path, clock)
        store.stage("pid_sp", trusted_snapshot())
        self.assertTrue(store.flush(force=True))
        clock.now = 10 * 365 * 24 * 3600
        restored = AdaptiveControllerStateStore(path, clock).load("pid_sp")
        self.assertEqual(restored["gain_f_per_duty"], trusted_snapshot()["gain_f_per_duty"])


def test_state_store_throttles_then_force_flushes_atomically(self):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "adaptive.json"
        clock = FakeClock()
        store = AdaptiveControllerStateStore(path, clock)
        store.stage("pid_sp", trusted_snapshot())
        self.assertTrue(store.flush())
        clock.now = 10.0
        store.stage("pid_sp", dict(trusted_snapshot(), revision=2))
        self.assertFalse(store.flush())
        self.assertTrue(store.flush(force=True))
        self.assertFalse(list(path.parent.glob(path.name + ".tmp-*")))


def test_corrupt_state_is_ignored(self):
    path.write_text("not json")
    self.assertIsNone(AdaptiveControllerStateStore(path).load("pid_sp"))


def test_runtime_uses_optional_hooks_and_json_status(self):
    controller = FakeAdaptiveController()
    record_output(controller, 0.4, False)
    self.assertEqual(controller.outputs[-1], (0.4, False))
    self.assertEqual(diagnostics(controller), controller.get_status())


def test_live_hold_target_update_only_handles_target_only_hold_change(self):
    controller = FakeAdaptiveController(set_point=250.0)
    control = {"updated": True, "mode": "Hold", "primary_setpoint": 275.0,
               "units_change": False}
    self.assertTrue(apply_live_hold_target(controller, "Hold", control))
    self.assertEqual(controller.targets, [275.0])
    self.assertFalse(control["updated"])
    control.update(updated=True, mode="Stop")
    self.assertFalse(apply_live_hold_target(controller, "Hold", control))
```

Also prove plain controllers without hooks are no-ops and that `diagnostics()` returns `dict(controller.__dict__)`, preserving the existing diagnostics payload for every non-adaptive controller.

- [ ] **Step 2: Run the new tests and verify missing-module failures**

Run:

```bash
python3 -m unittest tests.test_adaptive_controller_state -v
```

Expected: FAIL because the new modules do not exist.

- [ ] **Step 3: Implement atomic throttled storage**

Persist this root schema:

```json
{
  "version": 1,
  "models": {
    "pid_sp": {
      "version": 1,
      "gain_f_per_duty": 647.0588235294117,
      "tau_seconds": 4705.882352941177,
      "theta_seconds": 35.0,
      "confidence": 0.95,
      "residual": 0.01,
      "observations": 500,
      "revision": 1
    }
  }
}
```

`stage()` ignores snapshots whose revision is not newer than the stored/pending revision. `flush(False)` writes only when pending and 1800 seconds have elapsed since the last successful write; the first routine write may occur immediately when no file exists. `flush(True)` writes any pending state. Write with `tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=path.name + ".tmp-", delete=False)`, `json.dump(..., sort_keys=True, indent=2)`, `flush()`, `os.fsync()`, and `os.replace()`. Always remove an un-replaced temp file in `finally`.

- [ ] **Step 4: Implement optional runtime adapters**

`supports()` calls `controller.supported_functions()` and never assumes an adaptive method exists. `record_output`, restore, stage, and diagnostics dispatch only when supported; diagnostics returns `dict(controller.__dict__)` unchanged when `get_status` is unsupported. `apply_live_hold_target()` returns true only when active mode and requested mode are both `Hold`, `updated` is true, `units_change` is false, target differs, and `set_target` is supported; it calls `set_target`, clears `updated`, and leaves every other update for normal work-cycle teardown.

- [ ] **Step 5: Ignore runtime state and run tests**

Append `/adaptive_controller_state.json` to `.gitignore`, then run:

```bash
python3 -m unittest tests.test_adaptive_controller_state -v
```

Expected: all state and adapter tests PASS.

- [ ] **Step 6: Commit persistence support**

```bash
git add .gitignore common/adaptive_controller_state.py controller/runtime.py tests/test_adaptive_controller_state.py
git commit -m "Persist trusted adaptive controller models"
```

---

### Task 6: Wire applied duty, live targets, diagnostics, and persistence into production

**Files:**
- Modify: `control.py:257-277` (`_init_controller` call path)
- Modify: `control.py:430-450` (work-cycle controller initialization)
- Modify: `control.py:574-615` (control updates and reinitialization)
- Modify: `control.py:650-735` (manual override and PID output clamping)
- Modify: `control.py:744-746` (PID diagnostics)
- Modify: `control.py:1079-1113` (work-cycle cleanup)
- Modify: `tests/test_adaptive_controller_state.py`

**Interfaces:**
- Consumes `AdaptiveControllerStateStore` and all `controller.runtime` adapters from Task 5.
- Produces production behavior only; no controller API changes.

- [ ] **Step 1: Add a source-isolated production integration regression**

Because importing `control.py` initializes hardware/Redis dependencies, inspect the work-cycle through a small AST/source-isolated test that executes only newly extracted pure helper functions; do not assert source text. Move these decisions into testable functions in `controller/runtime.py` if needed:

```python
def identification_allowed(lid_open, manual_override_active, fan_pid_active):
    return not (lid_open or manual_override_active or fan_pid_active)


def manual_override_duty(output):
    return 1.0 if output else 0.0
```

Tests must cover every truth-table input and exact 0/1 duty conversion. The production smoke check in Step 6 verifies imports/compilation after call-site edits.

- [ ] **Step 2: Restore and seed adaptive state at every controller creation**

Create one `AdaptiveControllerStateStore` per `_work_cycle`. After each successful `_init_controller`:

```python
restore_model(controllerCore, adaptive_store, settings["controller"]["selected"])
record_output(controllerCore, CycleRatio, identification_allowed=True)
```

Apply this after initial construction and controller-settings reinitialization. Seeding must happen under the current command timestamp and before the first PID update.

- [ ] **Step 3: Retain live PID-SP for target-only Hold changes**

Immediately after `control = read_control()` and before the generic `if control['updated']: break`:

```python
if apply_live_hold_target(controllerCore, mode, control):
    write_control(control, direct_write=True, origin="control")
elif control["updated"]:
    break
```

Do not intercept unit, mode, controller, or controller-configuration changes.

- [ ] **Step 4: Feed exact normal and manual commands**

After normal min/max/lid clamp calculation:

```python
record_output(
    controllerCore,
    CycleRatio,
    identification_allowed=identification_allowed(
        LidOpenDetect,
        manual_override["auger"] >= now,
        ControlFanPid,
    ),
)
```

At manual auger override start call `record_output(controllerCore, manual_override_duty(control['manual']['output']), False)`. At override expiration call `record_output(controllerCore, CycleRatio, False)` before normal cyclic control resumes.

- [ ] **Step 5: Use JSON-safe diagnostics and stage model revisions**

Replace PID-SP's direct `controllerCore.__dict__` notification payload with `diagnostics(controllerCore)`. After each controller update:

```python
stage_model(controllerCore, adaptive_store, settings["controller"]["selected"])
adaptive_store.flush()
```

At every work-cycle exit, stage once more and call `adaptive_store.flush(force=True)` before returning. Persistence failure must log and continue without clearing the in-memory model.

- [ ] **Step 6: Run focused production compatibility checks**

Run:

```bash
python3 -m unittest tests.test_adaptive_controller_state tests.test_pid_sp -v
python3 -m py_compile control.py common/adaptive_controller_state.py controller/runtime.py controller/pid_sp.py controller/smith_predictor.py
```

Expected: all tests PASS and `py_compile` exits 0.

- [ ] **Step 7: Commit production integration**

```bash
git add control.py tests/test_adaptive_controller_state.py
git commit -m "Feed applied auger duty to PID-SP"
```

---

### Task 7: Add grill profiles, 600°F coverage, and model diagnostics to the simulator

**Files:**
- Modify: `pid_simulator.py`
- Modify: `tests/test_pid_simulator.py`

**Interfaces:**
- Produces:
  - `PLANT_PROFILES: dict[str, PlantConfig]` with `small`, `medium`, `large`.
  - `--plant {small,medium,large}`, default `medium`.
  - Scenario `600`.
  - `build_identification_scenario(plant) -> Scenario`.
  - Model diagnostic fields on `Sample`/`SimulationResult`.
- Consumes PID-SP optional `set_output` and `get_status` hooks through `controller.runtime`.

- [ ] **Step 1: Write failing plant-profile and CLI tests**

Add contracts:

```python
def test_named_plants_match_exact_physics_and_reach_600(self):
    expected = {
        "small": (250.0, 48.0, 0.075, 20, 640.0, 3333.3333333333335),
        "medium": (400.0, 55.0, 0.085, 35, 647.0588235294117, 4705.882352941177),
        "large": (650.0, 70.0, 0.100, 50, 700.0, 6500.0),
    }
    for name, (mass, heat, loss, delay, gain, tau) in expected.items():
        plant = PLANT_PROFILES[name]
        self.assertEqual((plant.thermal_mass, plant.heat_input_per_second,
                          plant.heat_loss_coefficient, plant.firebox_delay_seconds),
                         (mass, heat, loss, delay))
        self.assertAlmostEqual(plant.heat_input_per_second / loss, gain)
        self.assertAlmostEqual(plant.thermal_mass / loss, tau)
        required_duty = (600.0 - plant.ambient_f) / gain
        self.assertLess(required_duty, U_MAX)


def test_cli_selects_large_plant_and_600_scenario(self):
    with redirect_stdout(io.StringIO()) as stdout:
        self.assertEqual(main(["--plant", "large", "--scenario", "600",
                               "--controller", "pid_sp", "--setpoint-mode", "continuous"]), 0)
    report = stdout.getvalue()
    self.assertIn("Plant: large", report)
    self.assertIn("600", report)


def test_simulator_feedback_uses_clamped_duty(self):
    result = simulate_controller("pid_sp", short_scenario(), PLANT_PROFILES["medium"], 15, "continuous")
    self.assertTrue(all(U_MIN <= sample.duty_ratio <= U_MAX for sample in result.samples))
    self.assertEqual(result.samples[15].model_applied_duty, result.samples[15].duty_ratio)
```

Update existing scenario-count tests for four scenarios and preserve explicit-empty-filter behavior.

- [ ] **Step 2: Run simulator tests and verify failures**

Run:

```bash
python3 -m unittest tests.test_pid_simulator -v
```

Expected: FAIL on missing profiles, scenario, CLI option, and diagnostics.

- [ ] **Step 3: Add immutable profiles and profile-aware CLI overrides**

Define:

```python
PLANT_PROFILES = {
    "small": PlantConfig(250.0, 48.0, 0.075, 70.0, 20),
    "medium": PlantConfig(400.0, 55.0, 0.085, 70.0, 35),
    "large": PlantConfig(650.0, 70.0, 0.100, 70.0, 50),
}
```

Add `--plant`, default `medium`. Change `--ambient-f` and `--delay-seconds` parser defaults to `None`; apply them with `dataclasses.replace` only when explicitly supplied, so named profile values survive ordinary CLI use. Add `600` as a four-hour constant Hold beginning at 550°F.

- [ ] **Step 4: Feed initial and clamped applied duty under deterministic time**

After controller creation and target assignment, call the optional output hook with initial `U_MIN`. After every `update()` clamp, call it with the new duty before advancing the plant. For production-reset transitions, seed the new controller at `U_MIN`; continuous transitions retain controller/model history.

Sample model diagnostics only through `get_status()` and add JSON/CSV-safe scalar fields: applied model duty, prediction active, predicted temperature, estimated gain/tau/theta, confidence, and residual. Add final model fields and activation second to `SimulationResult` and `format_summary()`.

- [ ] **Step 5: Build a profile-aware identification scenario**

For `tau = plant.thermal_mass / plant.heat_loss_coefficient`, create a scenario with transitions at `0`, `round(tau)`, `round(2*tau)`, and `round(3*tau)`, targets `250`, `350`, `450`, and `300`, initial pit 200°F, and duration `round(4.5*tau)`. This scenario is an API/test fixture, not part of default `--scenario all` output.

- [ ] **Step 6: Run simulator unit tests**

Run:

```bash
python3 -m unittest tests.test_pid_simulator -v
```

Expected: all existing and new simulator tests PASS.

- [ ] **Step 7: Commit simulator profiles and diagnostics**

```bash
git add pid_simulator.py tests/test_pid_simulator.py
git commit -m "Simulate adaptive PID-SP across grill sizes"
```

---

### Task 8: Prove closed-loop identification on all plants and compare performance

**Files:**
- Modify: `tests/test_pid_simulator.py`
- Runtime artifacts: `/tmp/adaptive-smith-after.txt`, `/tmp/adaptive-smith-identification.txt`

**Interfaces:**
- Consumes `PLANT_PROFILES`, `build_identification_scenario`, simulator model diagnostics, and `/tmp/adaptive-smith-before.txt`.
- Produces regression gates and measured before/after evidence.

- [ ] **Step 1: Add failing closed-loop recovery tests**

Add:

```python
def test_pid_sp_identifies_every_named_plant_from_closed_loop_data(self):
    for name, plant in PLANT_PROFILES.items():
        with self.subTest(plant=name):
            scenario = build_identification_scenario(plant)
            result = simulate_controller("pid_sp", scenario, plant, 15, "continuous")
            exact_gain = plant.heat_input_per_second / plant.heat_loss_coefficient
            exact_tau = plant.thermal_mass / plant.heat_loss_coefficient
            self.assertIsNotNone(result.identifier_activation_second)
            self.assertAlmostEqual(result.estimated_gain_f_per_duty, exact_gain, delta=0.10 * exact_gain)
            self.assertAlmostEqual(result.estimated_tau_seconds, exact_tau, delta=0.15 * exact_tau)
            self.assertAlmostEqual(result.estimated_theta_seconds, plant.firebox_delay_seconds, delta=5.0)
            self.assertTrue(all(math.isfinite(sample.pit_temp_f) for sample in result.samples))
            self.assertTrue(all(U_MIN <= sample.duty_ratio <= U_MAX for sample in result.samples))


def test_every_named_plant_sustains_600_below_maximum_duty(self):
    for name, plant in PLANT_PROFILES.items():
        result = simulate_controller("pid_sp", SCENARIOS["600"], plant, 15, "continuous")
        final_window = result.samples[-600:]
        self.assertLessEqual(max(abs(sample.pit_temp_f - 600.0) for sample in final_window), 5.0)
        self.assertLess(result.segment_metrics[0].mean_duty_ratio, U_MAX)
```

- [ ] **Step 2: Run recovery tests and use failures only to correct source defects**

Run:

```bash
python3 -m unittest \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_identifies_every_named_plant_from_closed_loop_data \
  tests.test_pid_simulator.PidSimulatorTests.test_every_named_plant_sustains_600_below_maximum_duty -v
```

Expected: PASS. If a profile fails, inspect estimator diagnostics. Fix incorrect history alignment, coefficient scaling, uncertainty math, or confidence bookkeeping at the source. Do not add profile-specific constants, loosen the approved ±10%/±15%/±5-second tolerances, or inject excitation.

- [ ] **Step 3: Re-run focused estimator and closed-loop tests after any correction**

Run:

```bash
python3 -m unittest tests.test_smith_predictor tests.test_pid_sp tests.test_pid_simulator -v
```

Expected: all focused tests PASS.

- [ ] **Step 4: Generate after and identification reports**

Run:

```bash
python3 pid_simulator.py --plant medium --scenario all --controller pid_sp > /tmp/adaptive-smith-after.txt
python3 -c "from pid_simulator import PLANT_PROFILES, build_identification_scenario, format_summary, run_scenarios; p=PLANT_PROFILES; r=[]; [r.extend(run_scenarios(['pid_sp'], [build_identification_scenario(v)], v, 15, ['continuous'])) for v in p.values()]; print('\n\n'.join(format_summary([x], v) for x, v in zip(r, p.values())))" > /tmp/adaptive-smith-identification.txt
```

Expected: both commands exit 0; after report contains all default PID-SP rows; identification report contains trusted estimates for small, medium, and large.

- [ ] **Step 5: Print a factual before/after comparison**

Run a standard-library comparison script that parses the summary rows/segment lines from `/tmp/adaptive-smith-before.txt` and `/tmp/adaptive-smith-after.txt` and prints per scenario/mode deltas for IAE, within-5°F, directional overshoot, settling, and mean duty. Preserve the raw files; do not select only favorable rows.

Expected: all 250/350/450°F × production-reset/continuous segments appear. There is no required performance win; values must be finite and commands bounded.

- [ ] **Step 6: Commit closed-loop recovery gates and any source correction**

```bash
git add controller/smith_predictor.py controller/pid_sp.py pid_simulator.py tests/test_smith_predictor.py tests/test_pid_sp.py tests/test_pid_simulator.py
git commit -m "Verify adaptive Smith identification end to end"
```

---

### Task 9: Complete regression, compatibility, smoke, and artifact review

**Files:**
- Review: all files changed by Tasks 2–8
- Modify only if verification identifies a source defect.

**Interfaces:**
- Consumes every prior deliverable.
- Produces completion evidence and a clean implementation ready for branch integration.

- [ ] **Step 1: Run the full permanent regression suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests PASS.

- [ ] **Step 2: Verify Python 3.14 syntax compatibility**

Run:

```bash
uv run --python 3.14 python -m py_compile \
  control.py pid_simulator.py \
  controller/pid_sp.py controller/smith_predictor.py controller/runtime.py \
  common/adaptive_controller_state.py \
  tests/test_pid_sp.py tests/test_smith_predictor.py \
  tests/test_adaptive_controller_state.py tests/test_pid_simulator.py
```

Expected: exit 0 with no output.

- [ ] **Step 3: Run CLI smoke scenarios**

Run:

```bash
python3 pid_simulator.py --plant small --scenario 600 --controller pid_sp --setpoint-mode continuous
python3 pid_simulator.py --plant medium --scenario 250 --controller pid_sp --setpoint-mode production-reset
python3 pid_simulator.py --plant large --scenario 600 --controller pid_sp --setpoint-mode continuous --csv /tmp/adaptive-smith-large.csv
```

Expected: every command exits 0 with finite metrics; the CSV has exactly one header plus one row per simulated second.

- [ ] **Step 4: Run LSP diagnostics on every changed Python file**

Use `xd://lsp` diagnostics for:

```text
control.py
pid_simulator.py
controller/pid_sp.py
controller/smith_predictor.py
controller/runtime.py
common/adaptive_controller_state.py
tests/test_pid_sp.py
tests/test_smith_predictor.py
tests/test_adaptive_controller_state.py
tests/test_pid_simulator.py
```

Expected: no errors. Fix real type/syntax findings and rerun the affected diagnostic/test.

- [ ] **Step 5: Review the implementation against the approved specification**

Check each contract explicitly: applied clamped duty and manual transitions, all-PID-term Smith input, bounded histories, exact fractional delay propagation, all three online parameters, confidence fallback, indefinite physical-parameter persistence, live Hold target retention, JSON-safe diagnostics, three plants, 600°F capability, profile-independent recovery, and measured before/after output.

Expected: every item maps to implemented code and a passing test or smoke scenario; no obsolete `tau`/`theta` configuration or rate-extrapolation path remains.

- [ ] **Step 6: Request code review and address only source-grounded findings**

Use the `requesting-code-review` skill. Review all commits from the pre-Task-2 baseline through final HEAD, including production `control.py`, numerical estimator code, persistence, simulator changes, and tests. Apply valid Important/Critical findings, then repeat Steps 1–4.

- [ ] **Step 7: Commit final review corrections if any**

```bash
git add control.py pid_simulator.py controller common tests .gitignore
git commit -m "Harden adaptive Smith predictor"
```

Skip this commit only when review produces no changes.
