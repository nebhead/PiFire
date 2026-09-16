# PID-SP High-Temperature Transition Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent output-limited upward transitions from accumulating approach integral, recovering the original 450°F overshoot and settling envelope while preserving nominal and 600°F behavior.

**Architecture:** Extend PID-SP's existing `new_target` bookkeeping with two runtime-only fields. An output-limited upward transition retains integral damping until it enters the canonical 3°F capture band, crosses the target, or produces three consecutive selected-temperature rates at or below `capture_band / (2 × Ti)`; no Smith, identifier, persistence, simulator, or production-control interface changes.

**Tech Stack:** Python 3.14 standard library, `unittest`, existing PID-SP/controller interface, deterministic simulator.

## Global Constraints

- Follow `docs/superpowers/specs/2026-07-25-high-temperature-transition-tuning-design.md` exactly.
- Modify only `controller/pid_sp.py`, `tests/test_pid_sp.py`, and `tests/test_pid_simulator.py`; `/tmp` comparison artifacts are runtime-only.
- Do not add a setpoint threshold, plant/profile constant, user-facing option, nominal process model, or rate-extrapolation predictor.
- P, I, D, transition error, and approach rate use the same selected Smith-or-measured controller temperature.
- The approach rate is the raw selected-temperature rate before any derivative-term suppression.
- Fahrenheit capture is exactly `3.0°F`; Celsius capture is exactly `3.0 * 5.0 / 9.0°C`.
- Slow-rate release is exactly `capture_band / (2.0 * Ti)`, requires three consecutive qualifying updates, and performs no division when `Ti <= 0`.
- Existing `u_min`/`u_max`, applied-duty, Smith trust/fallback, persistence, lid/manual/fan, and generic-controller behavior remains unchanged.
- Use TDD and commit each task atomically. Run focused commands only within Task 1; run the complete suite once in Task 2.

---

### Task 1: Implement rate-gated transition integral release

**Files:**
- Modify: `controller/pid_sp.py:51-235`
- Modify: `tests/test_pid_sp.py:10-108`
- Modify: `tests/test_pid_simulator.py:232-247,547-568`
- Runtime artifact: `/tmp/pid-sp-transition-current.txt`

**Interfaces:**
- Consumes: existing `Controller.update(current) -> float`, `Controller.set_target(set_point)`, configured `Ti`, `Controller.cycle_data`, `Controller.previous_controller_input`, `simulate_controller(...)`, and immutable `SimulationResult` metrics.
- Produces: stored `Controller.ti: float`, runtime-only `Controller.output_limited_approach: bool`, `Controller.slow_approach_samples: int`, `_target_capture_band() -> float`, `_reset_approach_state() -> None`, and the unchanged public controller API.

- [ ] **Step 1: Capture the current deterministic comparison before editing**

Run:

```bash
python3 pid_simulator.py --plant medium --scenario all --controller pid_sp \
  > /tmp/pid-sp-transition-current.txt
```

Expected: exit `0`; eight PID-SP summary rows are present, including both 450°F modes and both 600°F modes. Preserve this file unchanged.

- [ ] **Step 2: Add focused unit-test setup for the transition state**

In `tests/test_pid_sp.py`, extend `CYCLE_DATA` so unit tests exercise the production clamp and add a deterministic update helper:

```python
CYCLE_DATA = {
    "HoldCycleTime": 15,
    "u_min": 0.05,
    "u_max": 0.90,
}


def update_at(controller, second, temperature):
    with patch("controller.pid_sp.time.time", return_value=float(second)):
        return controller.update(float(temperature))
```

Use native controller attributes in assertions; do not inspect source text.

- [ ] **Step 3: Replace the old saturation assertion and add stalled/noisy approach tests**

Replace `test_halfway_transition_resets_integral_and_completes_when_saturated` with the first test below, then add the other two tests to `PidSmithPredictorTests`:

```python
def test_output_limited_approach_keeps_integral_damped_while_rising(self):
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller()
        controller.set_target(600.0)

    for second, temperature in ((15, 550), (30, 575), (45, 575)):
        update_at(controller, second, temperature)

    self.assertTrue(controller.output_limited_approach)
    self.assertTrue(controller.new_target)
    self.assertLessEqual(
        abs(controller.inter),
        abs(controller.error * controller.cycle_time),
    )

    update_at(controller, 60, 577.0)
    self.assertEqual(controller.slow_approach_samples, 0)
    self.assertTrue(controller.new_target)


def test_output_limited_approach_releases_after_three_slow_samples(self):
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller()
        controller.set_target(600.0)

    for second, temperature in (
        (15, 550),
        (30, 575),
        (45, 575),
        (60, 575),
        (75, 575),
    ):
        update_at(controller, second, temperature)

    self.assertFalse(controller.output_limited_approach)
    self.assertFalse(controller.new_target)
    self.assertEqual(controller.slow_approach_samples, 0)


def test_fast_sample_breaks_slow_approach_confirmation(self):
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller()
        controller.set_target(600.0)

    for second, temperature in (
        (15, 550),
        (30, 575),
        (45, 575),
        (60, 575),
    ):
        update_at(controller, second, temperature)
    self.assertGreater(controller.slow_approach_samples, 0)

    update_at(controller, 75, 575.18)
    self.assertEqual(controller.slow_approach_samples, 0)
    self.assertTrue(controller.new_target)
```

The first update that enters `output_limited_approach` participates in slow-sample confirmation, matching the design's Step 6 → Step 7 order.

Extend the existing derivative-reduced counterexample with:

```python
self.assertFalse(controller.output_limited_approach)
self.assertEqual(controller.slow_approach_samples, 0)
```

- [ ] **Step 4: Add failing unit tests for capture, reset, units, and disabled integral**

Add:

```python
def test_capture_band_and_target_crossing_clear_approach_state(self):
    for temperature in (598.0, 604.0):
        with self.subTest(temperature=temperature):
            with patch("controller.pid_sp.time.time", return_value=0.0):
                controller = self.make_controller()
                controller.set_target(600.0)
            controller.output_limited_approach = True
            controller.slow_approach_samples = 2
            controller.previous_controller_input = 590.0
            controller.last_update = 0.0

            update_at(controller, 15, temperature)

            self.assertFalse(controller.new_target)
            self.assertFalse(controller.output_limited_approach)
            self.assertEqual(controller.slow_approach_samples, 0)


def test_set_target_clears_approach_state(self):
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller()
    controller.output_limited_approach = True
    controller.slow_approach_samples = 2

    with patch("controller.pid_sp.time.time", return_value=15.0):
        controller.set_target(350.0)

    self.assertFalse(controller.output_limited_approach)
    self.assertEqual(controller.slow_approach_samples, 0)


def test_capture_and_slow_rate_thresholds_scale_between_units(self):
    fahrenheit = self.make_controller()
    celsius = Controller(CONFIG, "C", CYCLE_DATA)

    self.assertAlmostEqual(fahrenheit._target_capture_band(), 3.0)
    self.assertAlmostEqual(celsius._target_capture_band(), 3.0 * 5.0 / 9.0)
    self.assertAlmostEqual(
        celsius._target_capture_band() / celsius.ti,
        (fahrenheit._target_capture_band() / fahrenheit.ti) * 5.0 / 9.0,
    )


def test_zero_ti_completes_output_limited_halfway_without_division(self):
    config = dict(CONFIG)
    config["Ti"] = 0.0
    with patch("controller.pid_sp.time.time", return_value=0.0):
        controller = self.make_controller(config)
        controller.set_target(600.0)

    for second, temperature in ((15, 550), (30, 575), (45, 575)):
        output = update_at(controller, second, temperature)

    self.assertTrue(math.isfinite(output))
    self.assertFalse(controller.output_limited_approach)
    self.assertFalse(controller.new_target)
    self.assertEqual(controller.i, 0.0)
```

Add `import math` to `tests/test_pid_sp.py`.

The `604.0°F` subcase is outside the `±3.0°F` capture band and therefore exercises the upward-crossing disjunct rather than ordinary capture-band clearance.

- [ ] **Step 5: Add the failing end-to-end 450°F acceptance test**

In `tests/test_pid_simulator.py`, add:

```python
def test_pid_sp_recovers_450_transition_without_losing_aggregate_gain(self):
    expected = {
        "production-reset": {
            "iae_max": 1078.7,
            "within_min": 79.4,
        },
        "continuous": {
            "iae_max": 1075.6,
            "within_min": 79.5,
        },
    }
    for mode, limits in expected.items():
        with self.subTest(mode=mode):
            result = simulate_controller(
                "pid_sp",
                SCENARIOS["450"],
                PLANT_PROFILES["medium"],
                15,
                mode,
            )
            first = result.segment_metrics[0]
            settling = first.settling_time_minutes
            self.assertIsNotNone(settling)
            assert settling is not None
            self.assertLessEqual(first.max_overshoot, 2.2)
            self.assertLessEqual(settling, 25.6)
            self.assertLessEqual(result.integrated_absolute_error, limits["iae_max"])
            self.assertGreaterEqual(result.percent_within_five_f, limits["within_min"])
            self.assertLessEqual(abs(result.mean_duty_ratio - 0.595), 0.005)
```

Also add an aggregate 250/350 baseline-envelope regression:

```python
def test_pid_sp_nominal_aggregate_gains_remain_above_pre_smith_baseline(self):
    limits = {
        ("250", "production-reset"): (831.7, 83.1),
        ("250", "continuous"): (834.8, 83.0),
        ("350", "production-reset"): (877.6, 82.5),
        ("350", "continuous"): (878.7, 82.5),
    }
    for (scenario_name, mode), (iae_max, within_min) in limits.items():
        with self.subTest(scenario=scenario_name, mode=mode):
            result = simulate_controller(
                "pid_sp",
                SCENARIOS[scenario_name],
                PLANT_PROFILES["medium"],
                15,
                mode,
            )
            self.assertLessEqual(result.integrated_absolute_error, iae_max)
            self.assertGreaterEqual(result.percent_within_five_f, within_min)
```

- [ ] **Step 6: Run the new tests and verify the expected RED state**

Run:

```bash
python3 -m unittest \
  tests.test_pid_sp.PidSmithPredictorTests.test_output_limited_approach_keeps_integral_damped_while_rising \
  tests.test_pid_sp.PidSmithPredictorTests.test_output_limited_approach_releases_after_three_slow_samples \
  tests.test_pid_sp.PidSmithPredictorTests.test_fast_sample_breaks_slow_approach_confirmation \
  tests.test_pid_sp.PidSmithPredictorTests.test_capture_band_and_target_crossing_clear_approach_state \
  tests.test_pid_sp.PidSmithPredictorTests.test_set_target_clears_approach_state \
  tests.test_pid_sp.PidSmithPredictorTests.test_capture_and_slow_rate_thresholds_scale_between_units \
  tests.test_pid_sp.PidSmithPredictorTests.test_zero_ti_completes_output_limited_halfway_without_division \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_recovers_450_transition_without_losing_aggregate_gain \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_nominal_aggregate_gains_remain_above_pre_smith_baseline -v
```

Expected: unit tests fail because the new state/helper members do not exist; the 450°F test fails at `5.4°F > 2.2°F` and `30.0 min > 25.6 min`. Record the exact failure summary.

- [ ] **Step 7: Add bounded transition state and helper methods**

In `Controller.__init__`, initialize:

```python
self.output_limited_approach = False
self.slow_approach_samples = 0
```

Store the configured integration time in `_calculate_gains()` so constructor and `set_gains()` changes use the same threshold:

```python
def _calculate_gains(self, pb, ti, td):
    self.ti = float(ti)
    if pb == 0:
        self.kp = 0
    else:
        self.kp = -1 / pb
    if self.ti <= 0.0:
        self.ki = 0.0
    else:
        self.ki = self.kp / self.ti
    self.kd = self.kp * td
```

When `set_gains()` makes `Ti <= 0.0`, clear `inter` and `i` along with disabling `ki`, so a live gain change cannot retain an integral contribution.

Add these private methods before `update()`:

```python
def _target_capture_band(self):
    if self.units == "F":
        return 3.0
    return 3.0 * 5.0 / 9.0


def _reset_approach_state(self):
    self.output_limited_approach = False
    self.slow_approach_samples = 0
```

Call `_reset_approach_state()` from `set_target()` immediately after resetting `inter` and `derv`.

- [ ] **Step 8: Implement the exact update-state ordering**

In `update()`, compute the raw selected rate once, before transition/PID decisions:

```python
previous_controller_input = self.previous_controller_input
if previous_controller_input is None:
    selected_rate = 0.0
else:
    selected_rate = (controller_input - previous_controller_input) / dt

if first_selected_sample and self.new_target:
    self.start_change_temp = controller_input

capture_band = self._target_capture_band()
upward_transition = self.set_point > self.start_change_temp
captured_target = abs(error) <= capture_band or (
    upward_transition and error >= 0.0
)
if self.new_target and captured_target:
    self.new_target = False
    self._reset_approach_state()
```

Reuse `selected_rate` for `self.derv` instead of recalculating it. Preserve the existing first-sample derivative zero rule.

On a live target change, seed `start_change_temp` from `previous_controller_input` when one exists; use the measured `last` value only before any selected controller input exists.

After complete candidate output and startup scaling are calculated, keep activation in that candidate-output branch, then process an already-active approach after every outer output-selection branch:

```python
# Inside the candidate-output branch:
u_max = self.cycle_data.get("u_max", 1.0)
if reached_halfway and upward_transition and self.u >= u_max:
    if self.ti <= 0.0:
        self.new_target = False
        self._reset_approach_state()
    else:
        self.output_limited_approach = True

# After all outer output-selection branches:
if self.output_limited_approach and self.new_target:
    if self.ti <= 0.0:
        self.new_target = False
        self._reset_approach_state()
    else:
        rate_threshold = capture_band / (2.0 * self.ti)
        if selected_rate <= rate_threshold:
            self.slow_approach_samples += 1
        else:
            self.slow_approach_samples = 0
        if self.slow_approach_samples >= 3:
            self.new_target = False
            self._reset_approach_state()
```

Do not clamp `self.u` in PID-SP; production/simulator external clamping and applied-duty feedback remain unchanged.

- [ ] **Step 9: Run focused unit tests and correct only state-order defects**

Run:

```bash
python3 -m unittest tests.test_pid_sp -v
```

Expected: all PID-SP tests pass. If a test disagrees about whether the activation update counts, preserve the design order: the activation update counts as the first confirmation sample.

- [ ] **Step 10: Run simulator acceptance and all adaptive focused tests**

Run:

```bash
python3 -m unittest \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_recovers_450_transition_without_losing_aggregate_gain \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_nominal_aggregate_gains_remain_above_pre_smith_baseline \
  tests.test_pid_simulator.PidSimulatorTests.test_every_named_plant_sustains_600_below_maximum_duty \
  tests.test_pid_simulator.PidSimulatorTests.test_pid_sp_identifies_every_named_plant_from_closed_loop_data -v

python3 -m unittest \
  tests.test_smith_predictor tests.test_pid_sp \
  tests.test_adaptive_controller_state tests.test_pid_simulator -v
```

Expected: all commands exit `0`; 450°F satisfies both first-segment limits; existing 600°F and identification tolerances remain unchanged. Do not relax thresholds or modify simulator physics.

- [ ] **Step 11: Run source diagnostics and Python 3.14 compilation**

Run `xd://lsp` diagnostics for:

```text
controller/pid_sp.py
tests/test_pid_sp.py
tests/test_pid_simulator.py
```

Fix real new diagnostics. The worktree-root artifact may resolve PID-SP tests against the parent checkout; distinguish that from changed-line errors.

Run:

```bash
uv run --python 3.14 python -m py_compile \
  controller/pid_sp.py tests/test_pid_sp.py tests/test_pid_simulator.py
```

Expected: exit `0` with no output.

- [ ] **Step 12: Review and commit the controller change**

Review against every Task 1 design invariant. Request independent spec and quality review; fix every Critical/Important source-grounded finding and rerun Steps 9–11.

Commit:

```bash
git add controller/pid_sp.py tests/test_pid_sp.py tests/test_pid_simulator.py
git commit -m "Gate PID-SP integral during hot approaches"
```

---

### Task 2: Prove complete performance and integration behavior

**Files:**
- Review: all implementation files from Task 1
- Runtime artifacts: `/tmp/pid-sp-transition-current.txt`, `/tmp/pid-sp-transition-tuned.txt`, `/tmp/pid-sp-transition-comparison.txt`, `/tmp/pid-sp-transition-large.csv`
- Modify only if final verification identifies a source defect required by the approved design.

**Interfaces:**
- Consumes: Task 1 controller state machine and simulator acceptance tests.
- Produces: complete deterministic comparison, full regression evidence, Python 3.14 compatibility evidence, and final independent review verdict.

- [ ] **Step 1: Generate the tuned medium-plant report**

Run:

```bash
python3 pid_simulator.py --plant medium --scenario all --controller pid_sp \
  > /tmp/pid-sp-transition-tuned.txt
```

Expected: exit `0`; eight PID-SP rows are present.

- [ ] **Step 2: Generate a strict current-versus-tuned comparison**

Create `/tmp/pid-sp-transition-comparison.py` with this complete standard-library parser:

```python
import math
import re
from pathlib import Path


SUMMARY = re.compile(
    r"^\s*(250|350|450|600)\s+"
    r"(production-reset|continuous)\s+pid_sp\s+"
    r"([0-9.]+)\s+([0-9.]+)%\s+([0-9.]+)\s+([0-9.]+)$"
)
SEGMENT = re.compile(
    r"^\s*Segment (\d+): target=([0-9.]+)F, "
    r"IAE=([0-9.]+), within5=([0-9.]+)%, "
    r"overshoot=([0-9.]+)F, settling=([0-9.]+|n/a) min, "
    r"duty=([0-9.]+)$"
)
EXPECTED_KEYS = {
    (scenario, mode)
    for scenario in ("250", "350", "450", "600")
    for mode in ("production-reset", "continuous")
}
EXPECTED_SEGMENTS = {"250": 3, "350": 3, "450": 3, "600": 1}


def parse(path):
    rows = {}
    current_key = None
    for line in Path(path).read_text().splitlines():
        summary = SUMMARY.match(line)
        if summary:
            scenario, mode = summary.group(1, 2)
            current_key = (scenario, mode)
            if current_key in rows:
                raise AssertionError(f"duplicate summary: {current_key}")
            values = tuple(float(value) for value in summary.groups()[2:])
            if not all(math.isfinite(value) for value in values):
                raise AssertionError(f"non-finite summary: {current_key}")
            rows[current_key] = {"summary": values, "segments": []}
            continue
        segment = SEGMENT.match(line)
        if segment:
            if current_key is None:
                raise AssertionError("segment before summary")
            number = int(segment.group(1))
            target, iae, within, overshoot = (
                float(value) for value in segment.group(2, 3, 4, 5)
            )
            settling_text = segment.group(6)
            settling = (
                None if settling_text == "n/a" else float(settling_text)
            )
            duty = float(segment.group(7))
            finite = (target, iae, within, overshoot, duty)
            if not all(math.isfinite(value) for value in finite):
                raise AssertionError(f"non-finite segment: {current_key}/{number}")
            if settling is None or not math.isfinite(settling):
                raise AssertionError(f"missing/non-finite settling: {current_key}/{number}")
            if not 0.05 <= duty <= 0.90:
                raise AssertionError(f"unbounded duty: {current_key}/{number}")
            rows[current_key]["segments"].append(
                (number, target, iae, within, overshoot, settling, duty)
            )
    if set(rows) != EXPECTED_KEYS:
        raise AssertionError(
            f"inventory mismatch: missing={EXPECTED_KEYS - set(rows)}, "
            f"extra={set(rows) - EXPECTED_KEYS}"
        )
    for (scenario, mode), row in rows.items():
        expected = EXPECTED_SEGMENTS[scenario]
        if len(row["segments"]) != expected:
            raise AssertionError(
                f"segment count {scenario}/{mode}: "
                f"{len(row['segments'])} != {expected}"
            )
        numbers = [segment[0] for segment in row["segments"]]
        if numbers != list(range(1, expected + 1)):
            raise AssertionError(f"segment order {scenario}/{mode}: {numbers}")
    return rows


current = parse("/tmp/pid-sp-transition-current.txt")
tuned = parse("/tmp/pid-sp-transition-tuned.txt")
for key in EXPECTED_KEYS:
    current_shape = [
        (segment[0], segment[1]) for segment in current[key]["segments"]
    ]
    tuned_shape = [
        (segment[0], segment[1]) for segment in tuned[key]["segments"]
    ]
    if current_shape != tuned_shape:
        raise AssertionError(
            f"segment target/order mismatch: {key}: "
            f"{current_shape} != {tuned_shape}"
        )

nominal_limits = {
    ("250", "production-reset"): (831.7, 83.1),
    ("250", "continuous"): (834.8, 83.0),
    ("350", "production-reset"): (877.6, 82.5),
    ("350", "continuous"): (878.7, 82.5),
    ("450", "production-reset"): (1078.7, 79.4),
    ("450", "continuous"): (1075.6, 79.5),
}
for key, (iae_max, within_min) in nominal_limits.items():
    iae, within, _overshoot, duty = tuned[key]["summary"]
    assert iae <= iae_max, (key, iae, iae_max)
    assert within >= within_min, (key, within, within_min)
    if key[0] == "450":
        assert abs(duty - 0.595) <= 0.005, (key, duty)
        first = tuned[key]["segments"][0]
        assert first[4] <= 2.2, (key, "overshoot", first[4])
        assert first[5] is not None and first[5] <= 25.6, (
            key,
            "settling",
            first[5],
        )

for key in sorted(EXPECTED_KEYS):
    before_summary = current[key]["summary"]
    after_summary = tuned[key]["summary"]
    summary_delta = tuple(
        after - before for before, after in zip(before_summary, after_summary)
    )
    print(
        f"{key[0]} {key[1]} summary "
        f"current={before_summary} tuned={after_summary} delta={summary_delta}"
    )
    before_segments = current[key]["segments"]
    after_segments = tuned[key]["segments"]
    for before, after in zip(before_segments, after_segments):
        numeric_before = tuple(
            math.nan if value is None else float(value) for value in before[2:]
        )
        numeric_after = tuple(
            math.nan if value is None else float(value) for value in after[2:]
        )
        deltas = tuple(
            new - old
            if math.isfinite(old) and math.isfinite(new)
            else math.nan
            for old, new in zip(numeric_before, numeric_after)
        )
        print(
            f"  segment {after[0]} target={after[1]:.0f} "
            f"current={numeric_before} tuned={numeric_after} delta={deltas}"
        )
```

This parses all rows before emitting results and preserves every favorable and unfavorable delta.

Run:

```bash
python3 /tmp/pid-sp-transition-comparison.py \
  > /tmp/pid-sp-transition-comparison.txt
```

Expected: exit `0`; all eight rows and every segment appear. Preserve unfavorable deltas.

- [ ] **Step 3: Run the complete permanent suite**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: all tests pass with zero failures/errors.

- [ ] **Step 4: Run Python 3.14 compilation**

Run:

```bash
uv run --python 3.14 python -m py_compile \
  control.py pid_simulator.py \
  controller/pid_sp.py controller/smith_predictor.py controller/runtime.py \
  common/adaptive_controller_state.py \
  tests/test_pid_sp.py tests/test_smith_predictor.py \
  tests/test_adaptive_controller_state.py tests/test_pid_simulator.py
```

Expected: exit `0` with no output.

- [ ] **Step 5: Run production-shape CLI smokes and validate CSV cardinality**

Run:

```bash
python3 pid_simulator.py --plant medium --scenario 450 --controller pid_sp --setpoint-mode production-reset
python3 pid_simulator.py --plant medium --scenario 450 --controller pid_sp --setpoint-mode continuous
python3 pid_simulator.py --plant small --scenario 600 --controller pid_sp --setpoint-mode continuous
python3 pid_simulator.py --plant large --scenario 600 --controller pid_sp --setpoint-mode continuous --csv /tmp/pid-sp-transition-large.csv
```

Expected: all commands exit `0` with finite metrics. The CSV has one 17-column header and exactly 14,400 rows for contiguous seconds `0..14399`; numeric diagnostics are finite or empty and JSON serializes with `allow_nan=False`.

- [ ] **Step 6: Run final LSP diagnostics and contract audit**

Run `xd://lsp` diagnostics on every changed Python file. Expected: no new errors.

Map every specification requirement to a passing test or smoke artifact. Explicitly confirm:

- no 450°F/setpoint/profile constant was added to production code;
- no nominal model or rate forecast was introduced;
- P/I/D and the gate share selected controller input;
- target/reset/Celsius/`Ti=0` paths are covered;
- 250/350/600 and identification gates pass;
- output remains externally clamped and applied-duty feedback is unchanged.

- [ ] **Step 7: Request whole-change review and address findings**

Request independent review from the Task 1 base through final HEAD. Require separate Spec, Quality, Production safety, and Numerical state verdicts. Fix every Critical/Important source-grounded issue, then repeat Steps 1–6.

- [ ] **Step 8: Commit final corrections only if review changed source**

If review required changes:

```bash
git add controller/pid_sp.py tests/test_pid_sp.py tests/test_pid_simulator.py
git commit -m "Harden PID-SP transition integral gating"
```

If review is clean, create no empty commit. Preserve all `/tmp` artifacts for factual reporting.
