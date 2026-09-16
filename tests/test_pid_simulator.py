import controller
import csv
import io
import importlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
import types
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from pid_simulator import (
    PLANT_PROFILES,
    U_MAX,
    U_MIN,
    PlantConfig,
    SCENARIOS,
    Scenario,
    build_identification_scenario,
    format_summary,
    load_controller_module,
    main,
    run_scenarios,
    simulate_controller,
    write_csv,
)


def short_scenario():
    return Scenario("short", 60, 200.0, ((0, 250.0),))


class PidSimulatorTests(unittest.TestCase):
    def test_default_plant_uses_35_second_delay_and_400_thermal_mass(self):
        self.assertEqual(PlantConfig().firebox_delay_seconds, 35)
        self.assertEqual(PlantConfig().thermal_mass, 400.0)

    def test_named_plants_match_exact_physics_and_reach_600(self):
        expected = {
            "small": (250.0, 48.0, 0.075, 20, 640.0, 3333.3333333333335),
            "medium": (400.0, 55.0, 0.085, 35, 647.0588235294117, 4705.882352941177),
            "large": (650.0, 70.0, 0.100, 50, 700.0, 6500.0),
        }

        self.assertEqual(set(PLANT_PROFILES), set(expected))
        for name, (mass, heat, loss, delay, gain, tau) in expected.items():
            with self.subTest(plant=name):
                plant = PLANT_PROFILES[name]
                self.assertEqual(
                    (
                        plant.thermal_mass,
                        plant.heat_input_per_second,
                        plant.heat_loss_coefficient,
                        plant.firebox_delay_seconds,
                    ),
                    (mass, heat, loss, delay),
                )
                self.assertAlmostEqual(plant.heat_input_per_second / loss, gain)
                self.assertAlmostEqual(plant.thermal_mass / loss, tau)
                required_duty = (600.0 - plant.ambient_f) / gain
                self.assertLess(required_duty, U_MAX)

    def test_600_scenario_is_a_four_hour_hold_beginning_at_550f(self):
        self.assertEqual(
            SCENARIOS["600"],
            Scenario("600", 14_400, 550.0, ((0, 600.0),)),
        )
        self.assertEqual(set(SCENARIOS), {"250", "350", "450", "600"})

    def test_identification_scenario_scales_with_plant_time_constant(self):
        for name, plant in PLANT_PROFILES.items():
            with self.subTest(plant=name):
                tau = plant.thermal_mass / plant.heat_loss_coefficient
                scenario = build_identification_scenario(plant)
                self.assertEqual(scenario.name, "identification")
                self.assertEqual(scenario.initial_pit_f, 200.0)
                self.assertEqual(
                    scenario.transitions,
                    (
                        (0, 250.0),
                        (round(tau), 350.0),
                        (round(2 * tau), 450.0),
                        (round(3 * tau), 300.0),
                    ),
                )
                self.assertEqual(scenario.duration_seconds, round(4.5 * tau))

    def test_cli_selects_large_plant_and_600_scenario(self):
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(
                main(
                    [
                        "--plant",
                        "large",
                        "--scenario",
                        "600",
                        "--controller",
                        "pid_sp",
                        "--setpoint-mode",
                        "continuous",
                    ]
                ),
                0,
            )

        report = stdout.getvalue()
        self.assertIn("Plant: large", report)
        self.assertIn("600", report)

    def test_cli_applies_explicit_overrides_to_the_selected_profile(self):
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(
                main(
                    [
                        "--plant",
                        "small",
                        "--ambient-f",
                        "75",
                        "--delay-seconds",
                        "10",
                        "--scenario",
                        "600",
                        "--controller",
                        "pid",
                        "--setpoint-mode",
                        "continuous",
                    ]
                ),
                0,
            )

        report = stdout.getvalue()
        self.assertIn("Plant: small", report)
        self.assertIn("ambient=75.0F", report)
        self.assertIn("delay=10s", report)
        self.assertIn("thermal_mass=250.0", report)
        self.assertIn("heat_input=48.0", report)

    def test_simulator_records_only_clamped_duty_through_adaptive_hook(self):
        set_output_calls = []
        raw_outputs = iter((U_MIN - 0.25, U_MAX + 0.25, U_MIN - 0.50))

        class ClampingSpyController:
            def __init__(self, _config, _units, _cycle_data):
                pass

            def supported_functions(self):
                return ("set_output",)

            def set_target(self, _target):
                pass

            def update(self, _pit_temperature):
                return next(raw_outputs)

            def set_output(self, duty, identification_allowed=True):
                set_output_calls.append((duty, identification_allowed))

        controller_module = types.ModuleType("clamping_spy")
        setattr(controller_module, "Controller", ClampingSpyController)
        setattr(controller_module, "time", types.SimpleNamespace())
        scenario = Scenario("clamp-spy", 16, 200.0, ((0, 250.0),))

        with patch(
            "pid_simulator.load_controller_module",
            return_value=controller_module,
        ):
            simulate_controller(
                "pid_sp",
                scenario,
                PLANT_PROFILES["medium"],
                5,
                "continuous",
            )

        self.assertEqual(
            set_output_calls,
            [
                (U_MIN, True),
                (U_MIN, True),
                (U_MAX, True),
                (U_MIN, True),
            ],
        )

    def test_model_diagnostics_are_scalar_and_json_safe(self):
        result = simulate_controller(
            "pid_sp",
            short_scenario(),
            PLANT_PROFILES["medium"],
            15,
            "continuous",
        )
        sample = result.samples[15]
        sample_diagnostics = {
            "model_applied_duty": sample.model_applied_duty,
            "prediction_active": sample.prediction_active,
            "predicted_temperature": sample.predicted_temperature,
            "estimated_gain_f_per_duty": sample.estimated_gain_f_per_duty,
            "estimated_tau_seconds": sample.estimated_tau_seconds,
            "estimated_theta_seconds": sample.estimated_theta_seconds,
            "model_confidence": sample.model_confidence,
            "model_residual": sample.model_residual,
        }
        result_diagnostics = {
            "model_applied_duty": result.model_applied_duty,
            "prediction_active": result.prediction_active,
            "predicted_temperature": result.predicted_temperature,
            "estimated_gain_f_per_duty": result.estimated_gain_f_per_duty,
            "estimated_tau_seconds": result.estimated_tau_seconds,
            "estimated_theta_seconds": result.estimated_theta_seconds,
            "model_confidence": result.model_confidence,
            "model_residual": result.model_residual,
            "identifier_activation_second": result.identifier_activation_second,
        }

        self.assertIsInstance(sample.prediction_active, bool)
        self.assertIsInstance(result.prediction_active, bool)
        self.assertEqual(
            json.loads(json.dumps(sample_diagnostics)),
            sample_diagnostics,
        )
        self.assertEqual(
            json.loads(json.dumps(result_diagnostics)),
            result_diagnostics,
        )

    def test_default_plant_reaches_250f_band_within_twenty_minutes(self):
        result = run_scenarios(
            controller_names=["pid_sp"],
            scenarios=[SCENARIOS["250"]],
            plant=PlantConfig(),
            cycle_seconds=15,
            setpoint_modes=["continuous"],
        )[0]

        first_segment = result.segment_metrics[0]
        settling_time = first_segment.settling_time_minutes
        if settling_time is None:
            self.fail("250F segment did not settle")
        self.assertLess(settling_time, 20.0)
        self.assertLess(first_segment.max_overshoot, 5.0)

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
                self.assertLessEqual(
                    result.integrated_absolute_error,
                    limits["iae_max"],
                )
                self.assertGreaterEqual(
                    result.percent_within_five_f,
                    limits["within_min"],
                )
                self.assertLessEqual(
                    abs(result.mean_duty_ratio - 0.595),
                    0.005,
                )
    def test_downward_step_counts_undershoot_not_initial_temperature(self):
        result = run_scenarios(
            controller_names=["pid_sp"],
            scenarios=[SCENARIOS["250"]],
            plant=PlantConfig(),
            cycle_seconds=15,
            setpoint_modes=["continuous"],
        )[0]

        downward_segment = result.segment_metrics[2]
        segment_samples = result.samples[10_800:14_400]
        self.assertGreater(segment_samples[0].pit_temp_f, downward_segment.target_f)
        expected_undershoot = max(
            0.0,
            max(
                downward_segment.target_f - sample.pit_temp_f
                for sample in segment_samples
            ),
        )
        self.assertAlmostEqual(
            downward_segment.max_overshoot,
            expected_undershoot,
        )
        self.assertEqual(
            result.max_overshoot,
            max(segment.max_overshoot for segment in result.segment_metrics),
        )

    def test_all_default_controllers_produce_finite_metrics_for_every_scenario_and_mode(
        self,
    ):
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
        self.assertEqual(
            {result.controller_name for result in results}, expected_controllers
        )
        self.assertEqual({result.scenario_name for result in results}, set(SCENARIOS))
        self.assertEqual(
            {result.setpoint_mode for result in results},
            {"production-reset", "continuous"},
        )
        for result in results:
            self.assertTrue(math.isfinite(result.integrated_absolute_error))
            self.assertTrue(math.isfinite(result.percent_within_five_f))
            self.assertTrue(math.isfinite(result.max_overshoot))
            self.assertTrue(math.isfinite(result.mean_duty_ratio))
            self.assertEqual(
                len(result.segment_metrics),
                len(SCENARIOS[result.scenario_name].transitions),
            )
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

    def test_explicitly_empty_filters_produce_no_results(self):
        for controller_names, setpoint_modes in (
            ([], ["continuous"]),
            (["pid"], []),
        ):
            with self.subTest(
                controller_names=controller_names,
                setpoint_modes=setpoint_modes,
            ):
                results = run_scenarios(
                    controller_names=controller_names,
                    scenarios=[SCENARIOS["250"]],
                    plant=PlantConfig(),
                    cycle_seconds=15,
                    setpoint_modes=setpoint_modes,
                )
                self.assertEqual(results, [])

    def test_controller_loader_restores_package_and_module_cache(self):
        module_name = "controller.pid_sp"
        previous_module = importlib.import_module(module_name)
        previous_package_attribute = getattr(controller, "pid_sp")

        loaded_module = load_controller_module("pid_sp")

        self.assertIsNot(loaded_module, previous_module)
        self.assertIs(sys.modules[module_name], previous_module)
        self.assertIs(getattr(controller, "pid_sp"), previous_package_attribute)

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
            {
                "scenario",
                "controller",
                "setpoint_mode",
                "second",
                "setpoint_f",
                "pit_temp_f",
                "duty_ratio",
                "auger_fraction",
                "auger_on",
                "model_applied_duty",
                "prediction_active",
                "predicted_temperature",
                "estimated_gain_f_per_duty",
                "estimated_tau_seconds",
                "estimated_theta_seconds",
                "model_confidence",
                "model_residual",
            },
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
        self.assertIn("Model", report)

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

        self.assertEqual(
            by_mode["production-reset"].controller_start_seconds,
            (0, 5_400, 10_800),
        )
        self.assertEqual(by_mode["continuous"].controller_start_seconds, (0,))
        self.assertAlmostEqual(
            by_mode["production-reset"].samples[5_400].duty_ratio,
            0.05,
        )

    def test_invalid_cli_timing_values_are_rejected(self):
        for arguments in (
            ["--duration-hours", "3"],
            ["--cycle-seconds", "0"],
            ["--delay-seconds", "-1"],
            ["--ambient-f", "nan"],
        ):
            with self.subTest(arguments=arguments):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
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
        self.assertAlmostEqual(
            sum(sample.auger_fraction for sample in first_cycle),
            0.75,
        )

    def test_default_plant_can_sustain_highest_target_below_maximum_duty(self):
        plant = PlantConfig()
        max_equilibrium_f = (
            plant.ambient_f
            + plant.heat_input_per_second * 0.9 / plant.heat_loss_coefficient
        )
        highest_target_f = max(
            target
            for scenario in SCENARIOS.values()
            for _, target in scenario.transitions
        )

        self.assertGreater(max_equilibrium_f, highest_target_f)

    def test_pid_sp_identifies_every_named_plant_from_closed_loop_data(self):
        for name, plant in PLANT_PROFILES.items():
            with self.subTest(plant=name):
                scenario = build_identification_scenario(plant)
                result = simulate_controller(
                    "pid_sp",
                    scenario,
                    plant,
                    15,
                    "continuous",
                )
                exact_gain = (
                    plant.heat_input_per_second / plant.heat_loss_coefficient
                )
                exact_tau = plant.thermal_mass / plant.heat_loss_coefficient

                self.assertIsNotNone(result.identifier_activation_second)
                estimated_gain = result.estimated_gain_f_per_duty
                estimated_tau = result.estimated_tau_seconds
                estimated_theta = result.estimated_theta_seconds
                self.assertIsNotNone(
                    estimated_gain,
                    f"{name} identifier did not estimate gain",
                )
                self.assertIsNotNone(
                    estimated_tau,
                    f"{name} identifier did not estimate time constant",
                )
                self.assertIsNotNone(
                    estimated_theta,
                    f"{name} identifier did not estimate delay",
                )
                assert estimated_gain is not None
                assert estimated_tau is not None
                assert estimated_theta is not None
                self.assertAlmostEqual(
                    estimated_gain,
                    exact_gain,
                    delta=0.10 * exact_gain,
                )
                self.assertAlmostEqual(
                    estimated_tau,
                    exact_tau,
                    delta=0.15 * exact_tau,
                )
                self.assertAlmostEqual(
                    estimated_theta,
                    plant.firebox_delay_seconds,
                    delta=5.0,
                )
                self.assertTrue(
                    all(math.isfinite(sample.pit_temp_f) for sample in result.samples)
                )
                self.assertTrue(
                    all(U_MIN <= sample.duty_ratio <= U_MAX for sample in result.samples)
                )

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
                self.assertGreaterEqual(
                    result.percent_within_five_f,
                    within_min,
                )
    def test_every_named_plant_sustains_600_below_maximum_duty(self):
        for name, plant in PLANT_PROFILES.items():
            with self.subTest(plant=name):
                result = simulate_controller(
                    "pid_sp",
                    SCENARIOS["600"],
                    plant,
                    15,
                    "continuous",
                )
                final_window = result.samples[-600:]
                self.assertLessEqual(
                    max(
                        abs(sample.pit_temp_f - 600.0)
                        for sample in final_window
                    ),
                    5.0,
                )
                final_applied_duty_mean = sum(
                    sample.duty_ratio for sample in final_window
                ) / len(final_window)
                self.assertLess(final_applied_duty_mean, U_MAX)

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
