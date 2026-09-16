# PID Controller Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic Python CLI that compares PiFire PID controllers in realistic pellet-grill scenarios, then correct the confirmed PID-SP defects and quantify their effect.

**Architecture:** `pid_simulator.py` is a standard-library-only executable that instantiates PiFire's actual controller classes, supplies a deterministic per-module clock, and advances a delayed first-order thermal plant one second at a time. Every scenario runs in both `production-reset` and `continuous` setpoint-transition modes by default. Its scenario runner returns structured results for terminal formatting and optional CSV export. PID-SP remains a production controller; its testable state/validation fixes stay confined to `controller/pid_sp.py` and controller metadata.

**Tech Stack:** Python 3 standard library (`argparse`, `csv`, `dataclasses`, `math`, `statistics`, `unittest`); existing PiFire controller modules.

## Global Constraints

- Run from the repository root as `python3 pid_simulator.py`; use no third-party packages, real-time sleeps, hardware, Redis, Flask, or network access.
- Simulate exactly the production controller classes: `pid`, `pid_clamping`, `pid_clamping_percent_pb`, `pid_parallel`, `pid_ac`, and `pid_sp`.
- Model a delayed first-order pellet-grill plant at one-second resolution; default controller interval is 15 seconds and default auger-to-firebox delay is 35 seconds.
- Default scenarios are 4-hour Hold-mode 250°F, 350°F, and 450°F cooks. Each starts 50°F below its initial target, then changes target at 90 and 180 minutes.
- Compare both `production-reset` and `continuous` setpoint-transition modes by default; permit repeatable CLI filtering.
- Report IAE, ±5°F time, maximum overshoot, 10-minute-window settling time, mean duty ratio, and per-segment metrics.
- Retain no legacy/broken PID-SP implementation in shipped code. Record baseline and fixed CLI output during implementation verification instead.
- Add deterministic `unittest` tests and make `tests/` trackable despite the repository’s broad ignored-test-file patterns.
- Change no controller other than PID-SP and no production behavior outside PID-SP predictor configuration metadata.

---

### Task 1: Build the deterministic simulator CLI

**Files:**
- Create: `pid_simulator.py`
- Create: `tests/__init__.py`
- Create: `tests/test_pid_simulator.py`
- Modify: `.gitignore:100-104`

**Interfaces:**
- Produces `PlantConfig`, `Scenario`, `SegmentMetrics`, `SimulationResult`, `simulate_controller()`, `run_scenarios()`, `write_csv()`, `format_summary()`, and `main()` from `pid_simulator.py`.
- `simulate_controller(controller_name: str, scenario: Scenario, plant: PlantConfig, cycle_seconds: int, setpoint_mode: str) -> SimulationResult` returns finite scalar metrics, one `Sample` per one-second timestep with `auger_fraction: float`, `controller_update_seconds: tuple[int, ...]`, and `controller_start_seconds: tuple[int, ...]`.
- `run_scenarios(controller_names: Sequence[str] | None, scenarios: Sequence[Scenario], plant: PlantConfig, cycle_seconds: int, setpoint_modes: Sequence[str] | None) -> list[SimulationResult]` runs the Cartesian product of selected production controllers, scenarios, and modes; `None` selects every supported value.
- Task 2 consumes the CLI to capture PID-SP baseline and fixed results.

- [ ] **Step 1: Make tests trackable and write the failing simulator contract tests.**

  Add these negations after the existing generic test-file ignores in `.gitignore`:

  ```gitignore
  !tests/
  !tests/**/*.py
  ```

  Create `tests/__init__.py` as an empty file and create `tests/test_pid_simulator.py`:

  ```python
  import csv
  import io
  import math
  import tempfile
  import subprocess
  import sys
  import unittest
  from contextlib import redirect_stdout
  from pathlib import Path

  from pid_simulator import (
      PlantConfig,
      SCENARIOS,
      format_summary,
      main,
      run_scenarios,
      write_csv,
  )


  class PidSimulatorTests(unittest.TestCase):
      def test_all_default_controllers_produce_finite_metrics_for_every_scenario_and_mode(self):
          results = run_scenarios(
              controller_names=None,
              scenarios=list(SCENARIOS.values()),
              plant=PlantConfig(),
              cycle_seconds=15,
              setpoint_modes=None,
          )

          expected_controllers = {
              "pid",
              "pid_clamping",
              "pid_clamping_percent_pb",
              "pid_parallel",
              "pid_ac",
              "pid_sp",
          }
          self.assertEqual(len(results), len(expected_controllers) * len(SCENARIOS) * 2)
          self.assertEqual({result.controller_name for result in results}, expected_controllers)
          self.assertEqual({result.scenario_name for result in results}, set(SCENARIOS))
          self.assertEqual({result.setpoint_mode for result in results}, {"production-reset", "continuous"})
          for result in results:
              self.assertTrue(math.isfinite(result.integrated_absolute_error))
              self.assertTrue(math.isfinite(result.percent_within_five_f))
              self.assertTrue(math.isfinite(result.max_overshoot))
              self.assertTrue(math.isfinite(result.mean_duty_ratio))
              self.assertEqual(len(result.segment_metrics), 3)
              self.assertEqual(len(result.samples), 4 * 60 * 60)

      def test_controller_and_mode_filters_run_only_requested_combination(self):
          results = run_scenarios(
              controller_names=["pid_sp"],
              scenarios=[SCENARIOS["350"]],
              plant=PlantConfig(),
              cycle_seconds=15,
              setpoint_modes=["continuous"],
          )

          self.assertEqual(len(results), 1)
          self.assertEqual(results[0].controller_name, "pid_sp")
          self.assertEqual(results[0].scenario_name, "350")
          self.assertEqual(results[0].setpoint_mode, "continuous")

      def test_csv_contains_one_row_for_every_simulated_second(self):
          result = run_scenarios(
              controller_names=["pid"],
              scenarios=[SCENARIOS["250"]],
              plant=PlantConfig(),
              cycle_seconds=15,
              setpoint_modes=["production-reset"],
          )[0]

          with tempfile.TemporaryDirectory() as directory:
              output_path = Path(directory) / "result.csv"
              write_csv(output_path, [result])
              with output_path.open(newline="") as output_file:
                  rows = list(csv.DictReader(output_file))

          self.assertEqual(len(rows), len(result.samples))
          self.assertEqual(
              set(rows[0]),
              {"scenario", "controller", "setpoint_mode", "second", "setpoint_f", "pit_temp_f", "duty_ratio", "auger_fraction", "auger_on"},
          )

      def test_cli_prints_summary_for_selected_scenario_and_controller(self):
          stdout = io.StringIO()
          with redirect_stdout(stdout):
              exit_code = main(["--scenario", "450", "--controller", "pid_sp"])

          self.assertEqual(exit_code, 0)
          report = stdout.getvalue()
          self.assertIn("PID controller simulation", report)
          self.assertIn("450", report)
          self.assertIn("pid_sp", report)
          self.assertIn("IAE", report)
          self.assertIn("Segment", report)
          self.assertIn("production-reset", report)
          self.assertIn("continuous", report)

      def test_non_divisor_cycle_waits_a_full_interval_after_transition(self):
          result = run_scenarios(
              controller_names=["pid"],
              scenarios=[SCENARIOS["250"]],
              plant=PlantConfig(),
              cycle_seconds=17,
              setpoint_modes=["production-reset"],
          )[0]

          self.assertEqual(result.controller_update_seconds[:2], (17, 34))
          self.assertNotIn(5_406, result.controller_update_seconds)
          self.assertIn(5_417, result.controller_update_seconds)
          self.assertAlmostEqual(result.samples[5_400].duty_ratio, 0.05)
          self.assertAlmostEqual(result.samples[5_400].auger_fraction, 0.85)
          self.assertGreater(result.samples[5_417].auger_fraction, 0.0)

      def test_setpoint_modes_restart_or_retain_the_controller(self):
          results = run_scenarios(
              controller_names=["pid_sp"],
              scenarios=[SCENARIOS["250"]],
              plant=PlantConfig(),
              cycle_seconds=15,
              setpoint_modes=["production-reset", "continuous"],
          )
          by_mode = {result.setpoint_mode: result for result in results}

          self.assertEqual(by_mode["production-reset"].controller_start_seconds, (0, 5_400, 10_800))
          self.assertEqual(by_mode["continuous"].controller_start_seconds, (0,))
          self.assertAlmostEqual(by_mode["production-reset"].samples[5_400].duty_ratio, 0.05)

      def test_invalid_cli_timing_values_are_rejected(self):
          for arguments in (
              ["--duration-hours", "3"],
              ["--cycle-seconds", "0"],
              ["--delay-seconds", "-1"],
              ["--ambient-f", "nan"],
          ):
              with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                  main(arguments)

      def test_fractional_auger_window_preserves_requested_duty(self):
          result = run_scenarios(
              controller_names=["pid"],
              scenarios=[SCENARIOS["250"]],
              plant=PlantConfig(),
              cycle_seconds=15,
              setpoint_modes=["production-reset"],
          )[0]
          first_cycle = result.samples[:15]
          self.assertAlmostEqual(sum(sample.auger_fraction for sample in first_cycle), 0.75)

      def test_default_plant_can_sustain_highest_target_below_maximum_duty(self):
          plant = PlantConfig()
          max_equilibrium_f = (
              plant.ambient_f
              + plant.heat_input_per_second * 0.9 / plant.heat_loss_coefficient
          )
          highest_target_f = max(
              target for scenario in SCENARIOS.values() for _, target in scenario.transitions
          )

          self.assertGreater(max_equilibrium_f, highest_target_f)

      def test_logging_controllers_run_without_site_packages(self):
          completed = subprocess.run(
              [
                  sys.executable,
                  "-S",
                  "pid_simulator.py",
                  "--scenario",
                  "250",
                  "--controller",
                  "pid_clamping",
              ],
              capture_output=True,
              text=True,
              check=False,
          )

          self.assertEqual(completed.returncode, 0, completed.stderr)


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the simulator tests and verify they fail because the CLI module does not exist.**

  Run:

  ```console
  python3 -m unittest tests.test_pid_simulator -v
  ```

  Expected: `ModuleNotFoundError: No module named 'pid_simulator'` during test collection.

- [ ] **Step 3: Implement the CLI, simulator clock, and delayed thermal plant.**

  Create `pid_simulator.py` with these implementation boundaries:

  ```python
  @dataclass(frozen=True)
  class PlantConfig:
      thermal_mass: float = 400.0
      heat_input_per_second: float = 55.0
      heat_loss_coefficient: float = 0.085
      ambient_f: float = 70.0
      firebox_delay_seconds: int = 35


  @dataclass(frozen=True)
  class Scenario:
      name: str
      duration_seconds: int
      initial_pit_f: float
      transitions: tuple[tuple[int, float], ...]

      def setpoint_at(self, second: int) -> float: ...


  SCENARIOS = {
      "250": Scenario("250", 14_400, 200.0, ((0, 250.0), (5_400, 275.0), (10_800, 250.0))),
      "350": Scenario("350", 14_400, 300.0, ((0, 350.0), (5_400, 325.0), (10_800, 350.0))),
      "450": Scenario("450", 14_400, 400.0, ((0, 450.0), (5_400, 425.0), (10_800, 450.0))),
  }
  ```

  Implement a `SimulationClock` exposing `time() -> float`. For every controller instance, temporarily replace only that controller module’s `time` global with the clock object while calling its constructor, `set_target()`, and `update()`. Restore the exact original module object in `finally`. Do not monkeypatch the global `time` module or modify production controller timing.

  In `simulate_controller()`:

  1. Load production controller modules through a `load_controller_module()` helper. For modules that use `from common import create_logger`, temporarily place a synthetic `common` module in `sys.modules` whose only export is `create_logger`; it must return a disabled standard-library logger with a `NullHandler`. Save and remove any existing canonical target controller module before importing; after capturing the new module object, remove it and restore both the exact prior controller module and exact prior `common` entry in `finally`. This prevents Redis/logging imports and process-wide module-cache pollution while preserving production formulas.
  2. Define `create_controller(target)` to instantiate a new production `Controller` under the simulated clock with defaults from `controller/controllers.json`, units `"F"`, and `{"HoldCycleTime": cycle_seconds, "u_min": 0.05, "u_max": 0.9}`, then call `set_target(target)`. At second zero, create the controller for `scenario.setpoint_at(0)`, initialize `pit_temperature = scenario.initial_pit_f`, `duty_ratio = u_min`, `cycle_start_second = 0`, `next_controller_update = cycle_seconds`, `controller_start_seconds = [0]`, and an empty `controller_update_seconds` list.
  3. At each target transition after second zero, branch on `setpoint_mode`. For `production-reset`, discard the old controller, call `create_controller(new_target)`, append the transition second to `controller_start_seconds`, reset `duty_ratio = u_min`, and set `cycle_start_second = second`. For `continuous`, call `controller.set_target(new_target)` under the simulated clock, retaining the live object, current duty ratio, and auger-cycle anchor. In both modes set `next_controller_update = second + cycle_seconds`.
  4. When `second >= next_controller_update`, call `update(pit_temperature)`, append `second` to `controller_update_seconds`, apply PiFire’s Hold clamp, and set both `cycle_start_second = second` and `next_controller_update = second + cycle_seconds`.
  5. Preserve fractional on-times. Set `cycle_phase = (second - cycle_start_second) % cycle_seconds` so continuous mode keeps cycling its prior duty between a target change and the deferred update. For each one-second interval `[cycle_phase, cycle_phase + 1)`, compute `auger_fraction` as its overlap with `[0, duty_ratio * cycle_seconds)`, yielding a value from 0 through 1. Store `auger_fraction` on each sample and derive `auger_on = auger_fraction > 0` only for display/CSV compatibility.
  6. Push `auger_fraction` through a delay line initialized with `firebox_delay_seconds` zeroes. For a positive delay, pop the oldest fraction before appending the current fraction; for zero delay, use the current fraction directly. Apply `heat_input_per_second * delayed_auger_fraction`.
  7. Advance the pit by one Euler step using the specified energy balance, append a `Sample` carrying `setpoint_mode`, and keep all sample fields finite. Return `controller_update_seconds` and `controller_start_seconds` on `SimulationResult`.

  Calculate segment metrics using transition boundaries. Compute IAE as the sum of `abs(pit_temp_f - setpoint_f) / 60`; compute `percent_within_five_f` from samples inside ±5°F; compute directional overshoot as `max(0.0, max(pit_temp_f - setpoint_f))` for upward steps and `max(0.0, max(setpoint_f - pit_temp_f))` for downward steps; compute `mean_duty_ratio` from actual per-second `auger_fraction`; and find the first second whose following 600 samples remain inside ±5°F without crossing that segment's end. Use `None` for an unsettled segment rather than inventing a settling time. Set overall maximum overshoot to the maximum corrected segment overshoot. Sort result rows by IAE within each scenario and mode.

  Implement `argparse` for `--scenario`, repeatable `--controller`, repeatable `--setpoint-mode`, `--ambient-f`, `--duration-hours`, `--cycle-seconds`, `--delay-seconds`, and `--csv`. Default modes are `production-reset` and `continuous`; reject any other mode. `--ambient-f` must be finite; `--delay-seconds` must be a non-negative integer; `--cycle-seconds` must be a positive integer; and `--duration-hours` must be finite and strictly greater than 3. The options override the corresponding default plant/scenario values while retaining the 90/180-minute transitions. Reject unknown controllers/scenarios and every invalid numeric value with `parser.error`. `format_summary()` must print a heading, a mode column in its compact metrics table, then an indented `Segment` line per target segment. `main()` returns `0` on success.

- [ ] **Step 4: Run simulator contract tests and verify they pass.**

  Run:

  ```console
  python3 -m unittest tests.test_pid_simulator -v
  ```

  Expected: all ten tests pass. The complete default comparison may take only seconds because it advances simulated time rather than sleeping.

- [ ] **Step 5: Smoke-test the actual CLI and save the pre-fix PID-SP baseline.**

  Run:

  ```console
  python3 pid_simulator.py
  python3 pid_simulator.py --scenario all --controller pid_sp > /tmp/pid-sp-before-fix.txt
  python3 pid_simulator.py --scenario 350 --controller pid_sp --csv /tmp/pid-sp-350-before-fix.csv
  ```

  Expected: terminal output contains every requested scenario/controller in both modes, compact per-controller metrics, and three segment lines per result. The CSV contains one header plus 28,800 rows for the selected controller/scenario across two modes. Preserve `/tmp/pid-sp-before-fix.txt` through Task 2 for the before/after comparison.

- [ ] **Step 6: Commit the simulator CLI and tests.**

  ```console
  git add .gitignore pid_simulator.py tests/__init__.py tests/test_pid_simulator.py
  git commit -m "Add PID controller simulator"
  ```

### Task 2: Correct PID-SP state, output reduction, and predictor validation

**Files:**
- Create: `tests/test_pid_sp.py`
- Modify: `controller/pid_sp.py:43-190`
- Modify: `controller/controllers.json:245-340`

**Interfaces:**
- `controller.pid_sp.Controller.update(current: float) -> float` keeps its existing public signature and returns a finite raw cycle ratio for finite inputs/configuration.
- `Controller` rejects invalid predictor configuration with `ValueError`: non-finite or non-positive `tau`, and non-finite or negative `theta`.
- PID-SP exposes existing diagnostic fields `roc`, `d`, `inter`, and `inter_max`; after every update `abs(inter) <= inter_max` when `ki != 0`.
- Task 1's simulator uses this fixed controller unchanged and produces the after-fix comparison.

- [ ] **Step 1: Write failing PID-SP regression tests.**

  Create `tests/test_pid_sp.py`:

  ```python
  import json
  import math
  import unittest
  from pathlib import Path
  from unittest.mock import patch

  from controller.pid_sp import Controller


  CONFIG = {
      "PB": 60.0,
      "Ti": 180.0,
      "Td": 45.0,
      "center_factor": 0.001,
      "stable_window": 12.0,
      "tau": 115.0,
      "theta": 65.0,
  }
  CYCLE_DATA = {"HoldCycleTime": 15}


  class PidSmithPredictorTests(unittest.TestCase):
      def make_controller(self, config=None):
          return Controller(config or CONFIG, "F", CYCLE_DATA)

      def test_first_sample_has_zero_rate_and_derivative(self):
          with patch("controller.pid_sp.time.time", return_value=0.0):
              controller = self.make_controller()
              controller.set_target(225.0)
          with patch("controller.pid_sp.time.time", return_value=15.0):
              controller.update(225.0)

          self.assertEqual(controller.roc, 0.0)
          self.assertEqual(controller.d, 0.0)
          self.assertEqual(controller.last, 225.0)

      def test_initial_target_uses_first_real_sample_for_later_reset_logic(self):
          with patch("controller.pid_sp.time.time", return_value=0.0):
              controller = self.make_controller()
              controller.set_target(350.0)
          for second, temperature in ((15.0, 300.0), (30.0, 330.0), (45.0, 340.0)):
              with patch("controller.pid_sp.time.time", return_value=second):
                  controller.update(temperature)

          self.assertEqual(controller.start_change_temp, 300.0)
          self.assertIsInstance(controller.u, float)

      def test_startup_reduction_scales_newly_calculated_output(self):
          with patch("controller.pid_sp.time.time", return_value=0.0):
              controller = self.make_controller()
              controller.set_target(100.0)
          controller.last = 100.0
          controller.last_update = 0.0
          with patch("controller.pid_sp.time.time", return_value=15.0):
              output = controller.update(100.0)

          self.assertAlmostEqual(output, (controller.p + controller.i + controller.d) * 0.65)

      def test_invalid_predictor_parameters_are_rejected(self):
          for key, value in (("tau", 0.0), ("tau", -1.0), ("tau", math.nan), ("tau", math.inf),
                             ("theta", -1.0), ("theta", math.nan), ("theta", math.inf)):
              with self.subTest(key=key, value=value):
                  config = dict(CONFIG, **{key: value})
                  with self.assertRaises(ValueError):
                      self.make_controller(config)

      def test_integral_accumulator_is_bounded(self):
          with patch("controller.pid_sp.time.time", return_value=0.0):
              controller = self.make_controller()
              controller.set_target(100.0)
          controller.set_gains(CONFIG["PB"], CONFIG["Ti"], CONFIG["Td"])
          controller.last = 99.0
          for second in range(15, 3_015, 15):
              with patch("controller.pid_sp.time.time", return_value=float(second)):
                  controller.update(99.0)

          self.assertLessEqual(abs(controller.inter), controller.inter_max)

      def test_pid_sp_metadata_constrains_predictor_values(self):
          metadata = json.loads(Path("controller/controllers.json").read_text())["metadata"]["pid_sp"]
          options = {option["option_name"]: option for option in metadata["config"]}

          self.assertEqual(options["tau"]["option_min"], 1)
          self.assertEqual(options["theta"]["option_min"], 0)


  if __name__ == "__main__":
      unittest.main()
  ```

- [ ] **Step 2: Run the regression tests and verify each failure identifies current buggy behavior.**

  Run:

  ```console
  python3 -m unittest tests.test_pid_sp -v
  ```

  Expected failures:

  - first sample reports a non-zero rate because `last` starts at `150`;
  - an initial target retains the sentinel rather than a real first sample for later reset logic;
  - startup reduction returns the unscaled `p + i + d` because it is overwritten;
  - invalid `tau`/`theta` values construct successfully;
  - `inter` exceeds the unused `inter_max` limit;
  - predictor metadata has unconstrained minimums.

- [ ] **Step 3: Make the narrow PID-SP and metadata corrections.**

  In `controller/pid_sp.py`:

  1. Import `Optional` from `typing` and set `self.last: Optional[float] = None` during initialization.
  2. Add a private `_validate_predictor_config()` using `math.isfinite()` that raises `ValueError("tau must be a positive finite number")` for invalid `tau` and `ValueError("theta must be a non-negative finite number")` for invalid `theta`. Call it immediately after assigning both values in `__init__`.
  3. Add a private `_update_integral_limit()` that sets `inter_max = abs(center / ki)` when `ki != 0`, otherwise `0.0`. Call it after gains/center are initialized, after `set_target()` recalculates `center`, and after `set_gains()` recalculates gains.
  4. In `update()`, capture `current_time` and `dt` as today. If `last is None`, set `roc = 0.0`, use `predicted_temp = current`, set derivative contribution to `0.0`, and set `start_change_temp = current`; otherwise retain the existing rate/prediction calculation. Always persist `last = current` and `last_update = current_time` before returning.
  5. Clamp the accumulator immediately after `self.inter += predicted_error * dt`:

     ```python
     self.inter = max(-self.inter_max, min(self.inter, self.inter_max))
     ```

     Leave the existing `self.i` clamp in place.
  6. Compute `self.u = self.p + self.i + self.d` before the startup-reduction condition. Replace that condition with:

     ```python
     if abs(error) < self.pb and current_time - self.last_set_time < self.cycle_time * 3:
         self.u *= 0.65
     ```

     This applies the documented reduction to the newly calculated output and matches the phrase “within PB”.
  7. Keep all existing public method signatures and normal later-cycle PID-SP equations unchanged.

  In `controller/controllers.json`, set PID-SP `tau.option_min` to `1` and `theta.option_min` to `0`. Do not alter defaults or other controller options.

- [ ] **Step 4: Run the PID-SP regression tests and simulator tests to verify green.**

  Run:

  ```console
  python3 -m unittest tests.test_pid_sp -v
  python3 -m unittest tests.test_pid_simulator -v
  ```

  Expected: all PID-SP regressions and all simulator contracts pass with no warnings or errors.

- [ ] **Step 5: Re-run the same PID-SP simulations and show the effect of the fixes.**

  Run:

  ```console
  python3 pid_simulator.py --scenario all --controller pid_sp > /tmp/pid-sp-after-fix.txt
  diff -u /tmp/pid-sp-before-fix.txt /tmp/pid-sp-after-fix.txt
  python3 pid_simulator.py --scenario all
  ```

  Expected: the diff reports PID-SP metric changes caused by the corrected initial sample, integral state, and startup reduction, separately for `production-reset` and `continuous`. The complete comparison still prints finite metrics for every controller, scenario, and mode. Report the observed before/after metrics and the reset-vs-continuous comparison in the final delivery rather than committing temporary baseline files.

- [ ] **Step 6: Commit the PID-SP corrections and regressions.**

  ```console
  git add controller/pid_sp.py controller/controllers.json tests/test_pid_sp.py
  git commit -m "Fix PID Smith Predictor state handling"
  ```

### Task 3: Final verification and maintainability review

**Files:**
- Modify only if verification reveals a defect in: `pid_simulator.py`, `controller/pid_sp.py`, `tests/test_pid_simulator.py`, or `tests/test_pid_sp.py`

**Interfaces:**
- Verifies the public CLI invocation and the unchanged production `Controller.update(current)` contract.

- [ ] **Step 1: Run the complete new regression suite.**

  Run:

  ```console
  python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```

  Expected: every simulator and PID-SP regression passes. If an existing tracked test is discovered, it must also pass; do not narrow the command to hide it.

- [ ] **Step 2: Run end-to-end CLI smoke scenarios.**

  Run:

  ```console
  python3 pid_simulator.py --scenario 250 --controller pid --setpoint-mode production-reset
  python3 pid_simulator.py --scenario 350 --controller pid_sp --setpoint-mode continuous --ambient-f 85 --delay-seconds 45
  python3 pid_simulator.py --scenario 450 --controller pid_parallel --cycle-seconds 20 --csv /tmp/pid-parallel-450.csv
  ```

  Expected: each command exits zero and prints segment metrics. The first two commands each show only the selected mode; the CSV command includes both modes with the documented header and one record per simulated second per mode.

- [ ] **Step 3: Inspect only the changed files for scope and source hygiene.**

  Confirm the simulator imports no non-standard packages, production code contains no simulator-specific branches, temporary `/tmp` artifacts are not tracked, and `pid_sp.py` retains no hard-coded initial temperature sentinel.

- [ ] **Step 4: Commit any verification-only correction if one was necessary.**

  If and only if Steps 1–3 required a production correction, commit it separately with an imperative message describing that correction. Otherwise make no additional commit.
