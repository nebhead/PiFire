import math
import unittest
from dataclasses import FrozenInstanceError

from controller.smith_predictor import (
    AdaptiveFOPDTIdentifier,
    DutyHistory,
    FOPDTModel,
    SmithPredictor,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def model(gain=600.0, tau=300.0, delay=20.0, revision=1):
    return FOPDTModel(gain, tau, delay, 0.95, 0.1, 300, revision)


def _to_native_temperature(temperature_f, units):
    if units == "F":
        return temperature_f
    return (temperature_f - 32.0) * 5.0 / 9.0


def _command_schedule(duration_seconds):
    duties = (0.15, 0.75, 0.30, 0.85, 0.20, 0.65, 0.40, 0.90, 0.10, 0.70)
    intervals = (300, 450, 600, 750, 900)
    commands = [(0.0, duties[0])]
    timestamp = 0
    duty_index = 1
    interval_index = 0
    while timestamp < duration_seconds:
        timestamp += intervals[interval_index % len(intervals)]
        if timestamp > duration_seconds:
            break
        commands.append((float(timestamp), duties[duty_index % len(duties)]))
        duty_index += 1
        interval_index += 1
    return commands


def _feed_synthetic_fopdt(
    identifier,
    clock,
    gain,
    tau,
    delay,
    duration_seconds=26 * 3600,
    observation_intervals=(15, 16),
):
    ambient_f = 125.0
    commands = _command_schedule(duration_seconds)
    current_temperature_f = ambient_f + gain * commands[0][1]
    command_index = 0
    delayed_command_index = 0
    interval_index = 0
    next_observation = observation_intervals[0]

    identifier.record_output(commands[0][1])
    identifier.observe(_to_native_temperature(current_temperature_f, identifier.units))
    one_second_decay = math.exp(-1.0 / tau)
    for second in range(1, duration_seconds + 1):
        delayed_time = float(second - 1) - delay
        while (
            delayed_command_index + 1 < len(commands)
            and commands[delayed_command_index + 1][0] <= delayed_time
        ):
            delayed_command_index += 1
        equilibrium_f = ambient_f + gain * commands[delayed_command_index][1]
        current_temperature_f = equilibrium_f + (
            current_temperature_f - equilibrium_f
        ) * one_second_decay

        clock.now = float(second)
        while (
            command_index + 1 < len(commands)
            and commands[command_index + 1][0] == clock.now
        ):
            command_index += 1
            identifier.record_output(commands[command_index][1])
        if second == next_observation:
            identifier.observe(
                _to_native_temperature(current_temperature_f, identifier.units)
            )
            interval_index = (interval_index + 1) % len(observation_intervals)
            next_observation += observation_intervals[interval_index]
    return identifier


def identify_synthetic_fopdt(gain, tau, delay, units="F"):
    clock = FakeClock()
    identifier = AdaptiveFOPDTIdentifier(units, clock)
    _feed_synthetic_fopdt(identifier, clock, gain, tau, delay)
    return identifier.trusted_model


def identify_constant_duty(duration_seconds):
    clock = FakeClock()
    identifier = AdaptiveFOPDTIdentifier("F", clock)
    identifier.record_output(0.4)
    identifier.observe(365.0)
    for second in range(15, duration_seconds + 1, 15):
        clock.now = float(second)
        identifier.observe(365.0)
    return identifier.trusted_model, identifier.status()




class FOPDTModelTests(unittest.TestCase):
    def test_model_is_immutable_and_validates_physical_bounds(self):
        valid_model = model()
        valid_model.validate()

        with self.assertRaises(FrozenInstanceError):
            setattr(valid_model, "gain_f_per_duty", 700.0)
        with self.assertRaises(ValueError):
            model(gain=49.0).validate()
        with self.assertRaises(ValueError):
            model(tau=math.nan).validate()


class DutyHistoryTests(unittest.TestCase):
    def test_duty_history_time_weights_fractional_boundaries(self):
        history = DutyHistory(max_age_seconds=300.0)
        history.record(0.0, 0.2, True)
        history.record(10.0, 0.8, True)

        self.assertAlmostEqual(history.average(-5.0, 5.0), 0.2)
        self.assertAlmostEqual(history.average(5.0, 15.0), 0.5)
        self.assertAlmostEqual(history.average(25.0, 35.0, delay_seconds=20.0), 0.5)

    def test_duty_history_retains_one_predecessor_when_pruned(self):
        history = DutyHistory(max_age_seconds=30.0)
        for second in range(0, 101, 10):
            history.record(float(second), second / 100.0, True)

        history.prune(100.0)

        self.assertEqual(history.value_at(70.0), 0.7)
        self.assertLessEqual(history.command_count, 5)

    def test_duty_history_replaces_timestamps_and_preserves_permission_changes(self):
        history = DutyHistory()
        history.record(0.0, 0.2, True)
        history.record(10.0, 0.2, False)
        history.record(10.0, 0.7, True)
        history.record(20.0, 0.7, True)

        self.assertEqual(history.command_count, 2)
        self.assertEqual(history.value_at(10.0), 0.7)
        self.assertTrue(history.interval_allowed(0.0, 10.0))
        self.assertTrue(history.interval_allowed(10.0, 20.0))

    def test_duty_history_rejects_invalid_commands_and_tracks_invalid_segments(self):
        history = DutyHistory()
        for timestamp, duty in ((math.nan, 0.2), (0.0, math.inf), (0.0, -0.1), (0.0, 1.1)):
            with self.subTest(timestamp=timestamp, duty=duty):
                with self.assertRaises(ValueError):
                    history.record(timestamp, duty, True)

        history.record(0.0, 0.2, True)
        history.record(10.0, 0.2, False)
        history.record(20.0, 0.2, True)

        self.assertTrue(history.interval_allowed(0.0, 10.0))
        self.assertFalse(history.interval_allowed(5.0, 15.0))
        self.assertTrue(history.interval_allowed(20.0, 30.0))


class SmithPredictorTests(unittest.TestCase):
    def test_smith_predictor_starts_with_zero_correction(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        predictor.record_output(0.2)
        predictor.set_model(model())

        self.assertEqual(predictor.update(250.0), 250.0)

    def test_inactive_predictor_bounds_alternating_history(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        for second in range(0, 1001, 10):
            clock.now = float(second)
            predictor.record_output(0.2 if second % 20 == 0 else 0.8)

        self.assertLessEqual(predictor._history.command_count, 32)
        predictor.set_model(model())
        self.assertEqual(predictor._undelayed_state, 120.0)

    def test_set_model_prunes_inactive_alternating_history(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        for second in range(0, 1001, 10):
            predictor._history.record(
                float(second), 0.2 if second % 20 == 0 else 0.8, True
            )

        clock.now = 1000.0
        predictor.set_model(model())

        self.assertLessEqual(predictor._history.command_count, 32)
        self.assertEqual(predictor._undelayed_state, 120.0)

    def test_active_predictor_rejects_stale_output_timestamps(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        predictor.record_output(0.2)
        predictor.set_model(model())
        clock.now = 10.0
        predictor.update(250.0)

        with self.assertRaises(ValueError):
            predictor.record_output(0.8, timestamp=5.0)

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
        undelayed = 120.0 * math.exp(-30.0 / 300.0) + 480.0 * (
            1.0 - math.exp(-30.0 / 300.0)
        )
        delayed = 120.0 * math.exp(-10.0 / 300.0) + 480.0 * (
            1.0 - math.exp(-10.0 / 300.0)
        )
        self.assertAlmostEqual(predicted, 250.0 + undelayed - delayed, places=9)

    def test_smith_predictor_retains_unadvanced_command_transitions(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        predictor.record_output(0.2)
        predictor.set_model(model(gain=600.0, tau=300.0, delay=20.0))
        predictor.update(250.0)
        clock.now = 10.0
        predictor.record_output(0.8)
        clock.now = 20.0
        predictor.record_output(0.2)
        clock.now = 400.0
        predictor.record_output(0.8)

        predicted = predictor.update(250.0)
        undelayed = 120.0 * math.exp(-10.0 / 300.0) + 480.0 * (
            1.0 - math.exp(-10.0 / 300.0)
        )
        undelayed = 120.0 + (undelayed - 120.0) * math.exp(-380.0 / 300.0)
        delayed = 120.0 * math.exp(-10.0 / 300.0) + 480.0 * (
            1.0 - math.exp(-10.0 / 300.0)
        )
        delayed = 120.0 + (delayed - 120.0) * math.exp(-360.0 / 300.0)
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

    def test_safety_fallback_resets_every_failure_mode_and_recovers(self):
        for failure_mode in ("nonfinite", "out_of_range", "residual"):
            with self.subTest(failure_mode=failure_mode):
                clock = FakeClock()
                predictor = SmithPredictor("F", clock)
                predictor.record_output(0.2)
                trusted_model = model()
                predictor.set_model(trusted_model)
                predictor.update(250.0)
                clock.now = 1.0
                predictor.record_output(0.8)
                clock.now = 15.0

                if failure_mode == "nonfinite":
                    predictor._undelayed_state = math.nan
                    predictor._delayed_state = 120.0
                    measured_temperature = 275.0
                elif failure_mode == "out_of_range":
                    predictor._undelayed_state = 1201.0
                    predictor._delayed_state = 120.0
                    measured_temperature = 275.0
                else:
                    predictor._consecutive_implausible_residuals = 3
                    measured_temperature = 500.0

                self.assertEqual(
                    predictor.update(measured_temperature), measured_temperature
                )
                self.assertFalse(predictor.status()["prediction_active"])
                self.assertIs(predictor._model, trusted_model)
                undelayed_state = predictor._undelayed_state
                delayed_state = predictor._delayed_state
                self.assertIsNotNone(undelayed_state)
                self.assertIsNotNone(delayed_state)
                assert undelayed_state is not None
                assert delayed_state is not None
                self.assertTrue(math.isfinite(undelayed_state))
                self.assertTrue(math.isfinite(delayed_state))
                self.assertEqual(undelayed_state, delayed_state)
                self.assertEqual(undelayed_state - delayed_state, 0.0)
                self.assertIsNone(predictor._last_measured_f)
                self.assertEqual(predictor._consecutive_implausible_residuals, 0)

                self.assertEqual(
                    predictor.update(measured_temperature), measured_temperature
                )
                self.assertTrue(predictor.status()["prediction_active"])

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

    def test_residuals_ignore_delayed_invalid_source_intervals(self):
        clock = FakeClock()
        predictor = SmithPredictor("F", clock)
        predictor.record_output(0.2)
        predictor.set_model(model(delay=120.0))
        predictor.update(250.0)
        for timestamp, allowed in (
            (10.0, False),
            (20.0, True),
            (25.0, False),
            (35.0, True),
            (40.0, False),
            (50.0, True),
        ):
            clock.now = timestamp
            predictor.record_output(0.2, identification_allowed=allowed)

        clock.now = 100.0
        predictor.update(250.0)
        for timestamp, temperature in (
            (130.0, 400.0),
            (145.0, 550.0),
            (160.0, 700.0),
            (175.0, 850.0),
        ):
            clock.now = timestamp
            predictor.update(temperature)

        self.assertTrue(predictor.status()["prediction_active"])



class AdaptiveFOPDTIdentifierTests(unittest.TestCase):
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
                assert estimate is not None
                self.assertAlmostEqual(
                    estimate.gain_f_per_duty, gain, delta=gain * 0.10
                )
                self.assertAlmostEqual(estimate.tau_seconds, tau, delta=tau * 0.15)
                self.assertAlmostEqual(estimate.theta_seconds, delay, delta=5.0)

    def test_identifier_does_not_trust_constant_duty(self):
        estimate, status = identify_constant_duty(duration_seconds=8 * 3600)

        self.assertIsNone(estimate)
        self.assertFalse(status["trusted"])
        self.assertLess(status["duty_stddev"], 0.05)

    def test_identifier_rejects_ambiguous_delay(self):
        identifier = AdaptiveFOPDTIdentifier(
            "F", FakeClock(), delay_candidates=(20, 25)
        )
        identifier._temperature_reference_f = 200.0
        identifier._accepted_seconds = 3600.0
        identifier._accepted_observations = 240
        identifier._duty_count = 2
        identifier._duty_m2 = 0.02
        identifier._sustained_transition = True
        identifier._temperature_min_f = 200.0
        identifier._temperature_max_f = 220.0
        beta_t = -1.0 / 3333.3333333333335
        beta_u = 640.0 / 3333.3333333333335
        beta_0 = -beta_t * 125.0
        for candidate, residual in zip(identifier._candidates, (1e-8, 1.05e-8)):
            candidate.coefficients = [
                beta_0 + beta_t * identifier._temperature_reference_f,
                beta_t * 500.0,
                beta_u,
            ]
            candidate.covariance = [
                [0.001, 0.0, 0.0],
                [0.0, 0.001, 0.0],
                [0.0, 0.0, 0.001],
            ]
            candidate.residual_ewma = residual
            candidate.valid_updates = 240

        for _ in range(20):
            self.assertIsNone(identifier._consider_estimate())

        status = identifier.status()
        self.assertEqual(status["eligible_candidates"], 2)
        self.assertLess(status["delay_residual_margin"], 0.10)
        self.assertIsNone(identifier.trusted_model)

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

    def test_temperature_span_includes_the_baseline_endpoint(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock)
        identifier.record_output(0.2)
        identifier.observe(200.0)
        clock.now = 15.0
        identifier.observe(215.0)

        self.assertEqual(identifier.status()["temperature_span_f"], 15.0)

    def test_celsius_samples_recover_the_canonical_fahrenheit_model(self):
        estimate = identify_synthetic_fopdt(
            647.0588235294117, 4705.882352941177, 35.0, units="C"
        )

        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertAlmostEqual(estimate.gain_f_per_duty, 647.0588235294117, delta=65.0)
        self.assertAlmostEqual(estimate.tau_seconds, 4705.882352941177, delta=706.0)
        self.assertAlmostEqual(estimate.theta_seconds, 35.0, delta=5.0)

    def test_repeated_duty_records_preserve_a_sustained_transition(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock)
        identifier.record_output(0.2)
        clock.now = 10.0
        identifier.record_output(0.8)
        clock.now = 25.0
        identifier.record_output(0.8)
        clock.now = 70.0
        identifier.record_output(0.8)

        self.assertTrue(identifier.status()["sustained_transition"])

    def test_same_timestamp_replacement_does_not_create_a_transition(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock)
        identifier.record_output(0.2)
        clock.now = 300.0
        identifier.record_output(0.8)
        identifier.record_output(0.2)
        clock.now = 400.0
        identifier.record_output(0.2)

        self.assertFalse(identifier.status()["sustained_transition"])

    def test_same_timestamp_correction_restores_the_original_hold(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock)
        identifier.record_output(0.2)
        clock.now = 10.0
        identifier.record_output(0.8)
        clock.now = 20.0
        identifier.record_output(0.7)
        identifier.record_output(0.8)
        clock.now = 70.0
        identifier.record_output(0.8)

        self.assertTrue(identifier.status()["sustained_transition"])

    def test_restore_trusted_model_is_immediate_and_keeps_rls_fresh(self):
        identifier = AdaptiveFOPDTIdentifier("F", FakeClock())
        identifier._candidates[0].coefficients = [1.0, 2.0, 3.0]
        identifier._candidates[0].valid_updates = 4
        restored = model(gain=640.0, tau=3333.0, delay=20.0, revision=7)

        identifier.restore_trusted_model(restored)

        self.assertIs(identifier.trusted_model, restored)
        self.assertTrue(identifier.status()["trusted"])
        self.assertEqual(identifier.status()["model_revision"], 7)
        self.assertEqual(identifier._candidates[0].coefficients, [0.0, 0.0, 0.0])
        self.assertEqual(identifier._candidates[0].valid_updates, 0)

    def test_delay_candidates_require_a_unique_grid_subset(self):
        valid_grid = tuple(range(0, 121, 5))
        invalid_candidates = (
            (2.5,),
            (5, 5),
            valid_grid + (0,),
        )
        for delay_candidates in invalid_candidates:
            with self.subTest(delay_candidates=delay_candidates):
                with self.assertRaises(ValueError):
                    AdaptiveFOPDTIdentifier(
                        "F", FakeClock(), delay_candidates=delay_candidates
                    )

    def test_material_check_without_a_trusted_model_is_false(self):
        identifier = AdaptiveFOPDTIdentifier("F", FakeClock())

        self.assertFalse(identifier._is_material((640.0, 3333.0, 20.0, 0.0, 0.0, 0.0)))

    def test_invalid_candidates_never_become_eligible(self):
        cases = (
            ("negative gain", [-0.1, -0.5, -0.6]),
            ("unstable beta", [0.3, 0.5, 0.6]),
            ("non-finite coefficient", [math.nan, -0.5, 0.6]),
            ("out-of-bounds gain", [-0.1, -0.5, 3.0]),
        )
        for name, coefficients in cases:
            with self.subTest(name=name):
                identifier = AdaptiveFOPDTIdentifier("F", FakeClock())
                identifier._temperature_reference_f = 200.0
                candidate = identifier._candidates[0]
                candidate.coefficients = coefficients
                candidate.covariance = [
                    [0.001, 0.0, 0.0],
                    [0.0, 0.001, 0.0],
                    [0.0, 0.0, 0.001],
                ]
                candidate.residual_ewma = 1e-9
                candidate.valid_updates = 240

                self.assertEqual(identifier.status()["eligible_candidates"], 0)

    def test_failed_candidate_resets_without_poisoning_others(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock, delay_candidates=(0, 5))
        identifier.record_output(0.2)
        identifier.observe(200.0)
        clock.now = 15.0
        identifier.record_output(0.8)
        identifier.observe(202.0)
        identifier._candidates[0].covariance[0][0] = math.nan
        clock.now = 30.0
        identifier.observe(204.0)

        self.assertEqual(identifier._candidates[0].valid_updates, 0)
        self.assertGreater(identifier._candidates[1].valid_updates, 1)

    def test_candidate_uses_the_exact_delayed_interval_average(self):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier("F", clock, delay_candidates=(0, 5))
        identifier.record_output(0.2)
        identifier.observe(200.0)
        clock.now = 10.0
        identifier.record_output(1.0)
        identifier.observe(200.0)
        delayed_candidate = identifier._candidates[1]
        delayed_candidate.coefficients = [0.0, 0.0, 0.0]
        delayed_candidate.covariance = [
            [1e6, 0.0, 0.0],
            [0.0, 1e6, 0.0],
            [0.0, 0.0, 1e6],
        ]
        delayed_candidate.residual_ewma = None
        delayed_candidate.valid_updates = 0
        clock.now = 20.0

        identifier.observe(210.0)

        delayed_average = 0.6
        expected = (
            delayed_average * 1e6
            / (0.9995 + 1e6 + delayed_average ** 2 * 1e6)
        )
        self.assertAlmostEqual(
            identifier._candidates[1].coefficients[2], expected, places=12
        )

    def test_material_estimate_blends_gain_tau_and_bumps_revision(self):
        identifier = AdaptiveFOPDTIdentifier(
            "F", FakeClock(), delay_candidates=(20, 25)
        )
        identifier.restore_trusted_model(model(gain=600.0, tau=3000.0, delay=10.0, revision=4))
        identifier._temperature_reference_f = 200.0
        identifier._accepted_seconds = 3600.0
        identifier._accepted_observations = 240
        identifier._duty_count = 2
        identifier._duty_m2 = 0.02
        identifier._sustained_transition = True
        identifier._temperature_min_f = 200.0
        identifier._temperature_max_f = 220.0
        for candidate, residual in zip(identifier._candidates, (1e-9, 1e-5)):
            beta_t = -1.0 / 4000.0
            beta_u = 800.0 / 4000.0
            beta_0 = -beta_t * 125.0
            candidate.coefficients = [
                beta_0 + beta_t * identifier._temperature_reference_f,
                beta_t * 500.0,
                beta_u,
            ]
            candidate.covariance = [
                [0.001, 0.0, 0.0],
                [0.0, 0.001, 0.0],
                [0.0, 0.0, 0.001],
            ]
            candidate.residual_ewma = residual
            candidate.valid_updates = 240

        published = None
        for _ in range(20):
            published = identifier._consider_estimate()

        self.assertIsNotNone(published)
        assert published is not None
        self.assertAlmostEqual(published.gain_f_per_duty, 620.0)
        self.assertAlmostEqual(published.tau_seconds, 3100.0)
        self.assertEqual(published.theta_seconds, 20.0)
        self.assertEqual(published.revision, 5)
if __name__ == "__main__":
    unittest.main()
