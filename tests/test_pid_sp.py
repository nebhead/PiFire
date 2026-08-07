import math
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from controller.pid_sp import Controller
from controller.smith_predictor import FOPDTModel


CONFIG = {
    "PB": 60.0,
    "Ti": 180.0,
    "Td": 45.0,
    "center_factor": 0.001,
    "stable_window": 12.0,
}
CYCLE_DATA = {
    "HoldCycleTime": 15,
    "u_min": 0.05,
    "u_max": 0.90,
}


def update_at(controller, second, temperature):
    with patch("controller.pid_sp.time.time", return_value=float(second)):
        return controller.update(float(temperature))


def trusted_snapshot(
    gain=647.0588235294117,
    tau=4705.882352941177,
    theta=35.0,
):
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


class PidSmithPredictorTests(unittest.TestCase):
    def make_controller(self, config=None):
        return Controller(CONFIG if config is None else config, "F", CYCLE_DATA)

    def test_first_sample_has_zero_derivative(self):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(225.0)
        with patch("controller.pid_sp.time.time", return_value=15.0):
            controller.update(225.0)

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
    def test_slow_approach_scaled_rate_boundary_confirms_exactly(self):
        for exact_boundary in (True, False):
            with self.subTest(exact_boundary=exact_boundary):
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
                self.assertTrue(controller.output_limited_approach)
                self.assertEqual(controller.slow_approach_samples, 2)

                boundary_temperature = 575.0 + (
                    controller._target_capture_band()
                    / (2.0 * controller.ti)
                    * controller.cycle_time
                )
                temperature = (
                    boundary_temperature
                    if exact_boundary
                    else math.nextafter(boundary_temperature, math.inf)
                )
                update_at(controller, 75, temperature)

                self.assertEqual(controller.slow_approach_samples, 0)
                if exact_boundary:
                    self.assertFalse(controller.output_limited_approach)
                    self.assertFalse(controller.new_target)
                else:
                    self.assertTrue(controller.output_limited_approach)
                    self.assertTrue(controller.new_target)
    def test_halfway_transition_remains_active_when_derivative_reduces_output(
        self,
    ):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(600.0)

        for second, temperature in ((15.0, 550.0), (30.0, 565.0), (45.0, 575.0)):
            with patch("controller.pid_sp.time.time", return_value=second):
                controller.update(temperature)

        u_max = controller.cycle_data.get("u_max", 1.0)
        self.assertGreaterEqual(controller.p, u_max)
        self.assertLess(controller.d, 0.0)
        self.assertLess(controller.u, u_max)
        self.assertTrue(controller.new_target)
        self.assertEqual(controller.inter, -25.0 * controller.cycle_time)
        self.assertFalse(controller.output_limited_approach)
        self.assertEqual(controller.slow_approach_samples, 0)

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
    def test_set_gains_zero_ti_completes_active_approach_without_division(
        self,
    ):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(600.0)

        for second, temperature in ((15, 550), (30, 575), (45, 575)):
            update_at(controller, second, temperature)
        self.assertTrue(controller.output_limited_approach)

        controller.set_gains(CONFIG["PB"], 0.0, CONFIG["Td"])
        output = update_at(controller, 60, 550)

        self.assertTrue(math.isfinite(output))
        self.assertFalse(controller.output_limited_approach)
        self.assertFalse(controller.new_target)
        self.assertEqual(controller.i, 0.0)

    def test_set_gains_zero_ti_clears_active_approach_below_proportional_band(
        self,
    ):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(600.0)

        for second, temperature in ((15, 550), (30, 575), (45, 575)):
            update_at(controller, second, temperature)
        self.assertTrue(controller.output_limited_approach)

        controller.set_gains(CONFIG["PB"], 0.0, CONFIG["Td"])
        output = update_at(controller, 60, 500)

        self.assertTrue(math.isfinite(output))
        self.assertFalse(controller.output_limited_approach)
        self.assertFalse(controller.new_target)

    def test_output_limited_approach_counts_slow_rate_below_proportional_band(
        self,
    ):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(600.0)

        for second, temperature in ((15, 550), (30, 575), (45, 575)):
            update_at(controller, second, temperature)
        self.assertTrue(controller.output_limited_approach)

        update_at(controller, 60, 577)
        self.assertEqual(controller.slow_approach_samples, 0)
        self.assertTrue(controller.new_target)

        update_at(controller, 75, 500)

        self.assertEqual(controller.slow_approach_samples, 1)
        self.assertTrue(controller.output_limited_approach)
        self.assertTrue(controller.new_target)

    def test_negative_ti_constructor_disables_integral_and_completes_transition(
        self,
    ):
        config = dict(CONFIG)
        config["Ti"] = -1.0
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller(config)
            controller.set_target(600.0)

        for second, temperature in ((15, 550), (30, 575), (45, 575)):
            output = update_at(controller, second, temperature)

        self.assertTrue(math.isfinite(output))
        self.assertEqual(controller.ki, 0.0)
        self.assertEqual(controller.i, 0.0)
        self.assertFalse(controller.output_limited_approach)
        self.assertFalse(controller.new_target)

    def test_set_gains_negative_ti_disables_integral_and_completes_active_approach(
        self,
    ):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(600.0)

        for second, temperature in ((15, 550), (30, 575), (45, 575)):
            update_at(controller, second, temperature)
        self.assertTrue(controller.output_limited_approach)

        controller.set_gains(CONFIG["PB"], -1.0, CONFIG["Td"])
        self.assertEqual(controller.inter, 0.0)
        output = update_at(controller, 60, 500)

        self.assertTrue(math.isfinite(output))
        self.assertEqual(controller.ki, 0.0)
        self.assertEqual(controller.i, 0.0)
        self.assertFalse(controller.output_limited_approach)
        self.assertFalse(controller.new_target)

    def test_startup_reduction_scales_newly_calculated_output(self):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            controller.set_target(100.0)
        controller.last = 100.0
        controller.last_update = 0.0
        with patch("controller.pid_sp.time.time", return_value=15.0):
            output = controller.update(100.0)

        self.assertAlmostEqual(
            output,
            (controller.p + controller.i + controller.d) * 0.65,
        )

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

    def test_adaptive_hooks_are_supported(self):
        controller = self.make_controller()

        self.assertTrue(
            {
                "set_output",
                "get_model_snapshot",
                "restore_model",
                "get_status",
            }.issubset(controller.supported_functions())
        )

    def test_measured_temperature_is_used_before_model_trust(self):
        controller = self.make_controller()
        controller.set_target(250.0)
        controller.update(240.0)

        self.assertFalse(controller.get_status()["prediction_active"])
        self.assertEqual(controller.get_status()["controller_input_temperature"], 240.0)

    def test_promotion_keeps_prediction_active_when_clock_advances(self):
        with patch(
            "controller.pid_sp.time.time",
            side_effect=(0.0, 0.0, 0.0),
        ):
            controller = self.make_controller()
        model = FOPDTModel(
            647.0588235294117,
            4705.882352941177,
            35.0,
            0.95,
            0.01,
            500,
            1,
        )
        controller._identifier.observe = lambda current, timestamp: model

        with patch(
            "controller.pid_sp.time.time",
            side_effect=(15.0, 16.0, 17.0),
        ):
            controller.update(240.0)

        self.assertTrue(controller.get_status()["prediction_active"])


    def test_live_target_uses_selected_input_for_outside_band_crossing(self):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            self.assertTrue(controller.restore_model(trusted_snapshot()))
            controller.previous_controller_input = 590.0
            controller.last = 610.0
            controller.set_target(600.0)

        self.assertTrue(controller.get_status()["prediction_active"])
        with patch.object(controller._predictor, "update", return_value=604.0):
            update_at(controller, 15, 596.0)

        self.assertFalse(controller.new_target)
        self.assertFalse(controller.output_limited_approach)

    def test_first_selected_input_sets_halfway_transition_boundary(self):
        with patch("controller.pid_sp.time.time", return_value=0.0):
            controller = self.make_controller()
            self.assertTrue(controller.restore_model(trusted_snapshot()))
            controller.set_target(600.0)

        self.assertTrue(controller.get_status()["prediction_active"])
        with patch.object(
            controller._predictor,
            "update",
            side_effect=(550.0, 570.0, 570.0),
        ):
            for second in (15, 30, 45):
                update_at(controller, second, 530.0)

        self.assertEqual(controller.start_change_temp, 550.0)
        self.assertFalse(controller.output_limited_approach)
        self.assertTrue(controller.new_target)

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

        self.assertAlmostEqual(
            controller.p,
            controller.kp * (selected - 250.0) + controller.center,
        )
        self.assertAlmostEqual(
            controller.derv,
            (selected - previous_selected) / 45.0,
        )
        expected_selected_inter = (
            (previous_selected - 250.0) * 15.0
            + (selected - 250.0) * 45.0
        )
        expected_measured_inter = (240.0 - 250.0) * 15.0 + (
            242.0 - 250.0
        ) * 45.0
        self.assertAlmostEqual(controller.inter, expected_selected_inter)
        self.assertAlmostEqual(
            controller.i, controller.ki * expected_selected_inter
        )
        self.assertNotAlmostEqual(controller.inter, expected_measured_inter)
        self.assertNotAlmostEqual(
            controller.i, controller.ki * expected_measured_inter
        )

    def test_set_target_preserves_model_and_identifier_state(self):
        controller = self.make_controller()
        self.assertTrue(controller.restore_model(trusted_snapshot()))
        controller.set_output(0.3)
        before = controller.get_model_snapshot()
        accepted = controller.get_status()["accepted_observations"]

        controller.set_target(350.0)

        self.assertEqual(controller.get_model_snapshot(), before)
        self.assertEqual(controller.get_status()["accepted_observations"], accepted)

    def test_snapshot_validation_and_status_are_json_safe(self):
        controller = self.make_controller()
        for snapshot in (
            None,
            {},
            dict(trusted_snapshot(), tau_seconds=0.0),
            dict(trusted_snapshot(), version=2),
        ):
            with self.subTest(snapshot=snapshot):
                self.assertFalse(controller.restore_model(snapshot))

        self.assertTrue(controller.restore_model(trusted_snapshot()))
        self.assertEqual(controller.get_model_snapshot(), trusted_snapshot())
        json.dumps(controller.get_status(), allow_nan=False)
        json.dumps(controller.get_model_snapshot(), allow_nan=False)

    def test_metadata_no_longer_exposes_fixed_model_parameters(self):
        metadata = json.loads(Path("controller/controllers.json").read_text())[
            "metadata"
        ]["pid_sp"]
        option_names = {option["option_name"] for option in metadata["config"]}

        self.assertNotIn("tau", option_names)
        self.assertNotIn("theta", option_names)


if __name__ == "__main__":
    unittest.main()
