import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# The production package initializer imports optional application dependencies.
# These focused stdlib-only tests load the new submodule without those imports.
common_package = types.ModuleType("common")
common_package.__path__ = [str(Path(__file__).parents[1] / "common")]
sys.modules.setdefault("common", common_package)

from common.adaptive_controller_state import AdaptiveControllerStateStore
import controller.runtime as controller_runtime
from controller.smith_predictor import AdaptiveFOPDTIdentifier
from controller.runtime import (
    apply_live_hold_target,
    apply_live_hold_target_and_restart_cycle,
    controller_reinit_output_seed,
    diagnostics,
    identification_allowed,
    hold_pid_update_due,
    manual_override_duty,
    normal_pid_output_recording_allowed,
    record_output,
    restore_model,
    stage_model,
    supports,
)


def trusted_snapshot(revision=1):
    return {
        "version": 1,
        "gain_f_per_duty": 647.0588235294117,
        "tau_seconds": 4705.882352941177,
        "theta_seconds": 35.0,
        "confidence": 0.95,
        "residual": 0.01,
        "observations": 500,
        "revision": revision,
    }


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeAdaptiveController:
    def __init__(self, set_point=250.0):
        self.set_point = set_point
        self.outputs = []
        self.restored = []
        self.targets = []
        self.snapshot = trusted_snapshot()

    def supported_functions(self):
        return (
            "set_output",
            "get_model_snapshot",
            "restore_model",
            "get_status",
            "set_target",
        )

    def set_output(self, duty, identification_allowed=True):
        self.outputs.append((duty, identification_allowed))

    def get_model_snapshot(self):
        return dict(self.snapshot)

    def restore_model(self, snapshot):
        self.restored.append(dict(snapshot))
        return True

    def get_status(self):
        return {"adaptive": True, "revision": self.snapshot["revision"]}

    def set_target(self, target):
        self.targets.append(target)
        self.set_point = target


class PlainController:
    def __init__(self):
        self.name = "plain"
        self.set_point = 225.0

    def supported_functions(self):
        return ("update",)

    def set_output(self, *_args, **_kwargs):
        raise AssertionError("unsupported output hook was called")

    def get_model_snapshot(self):
        raise AssertionError("unsupported snapshot hook was called")

    def restore_model(self, _snapshot):
        raise AssertionError("unsupported restore hook was called")

    def get_status(self):
        raise AssertionError("unsupported status hook was called")


class StoreSpy:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.loaded_names = []
        self.staged = []

    def load(self, name):
        self.loaded_names.append(name)
        return self.snapshot

    def stage(self, name, snapshot):
        self.staged.append((name, dict(snapshot)))
        return True


class AdaptiveControllerStateStoreTests(unittest.TestCase):
    def test_state_store_round_trips_without_age_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            clock = FakeClock()
            store = AdaptiveControllerStateStore(path, clock)
            self.assertTrue(store.stage("pid_sp", trusted_snapshot()))
            self.assertTrue(store.flush(force=True))

            clock.now = 10 * 365 * 24 * 3600
            restored = AdaptiveControllerStateStore(path, clock).load("pid_sp")

            self.assertEqual(restored, trusted_snapshot())

    def test_state_store_throttles_then_force_flushes_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            clock = FakeClock()
            store = AdaptiveControllerStateStore(path, clock)
            self.assertTrue(store.stage("pid_sp", trusted_snapshot()))
            self.assertTrue(store.flush())

            clock.now = 10.0
            self.assertTrue(store.stage("pid_sp", trusted_snapshot(revision=2)))
            self.assertFalse(store.flush())
            self.assertTrue(store.flush(force=True))

            self.assertEqual(store.load("pid_sp"), trusted_snapshot(revision=2))
            self.assertFalse(list(path.parent.glob(path.name + ".tmp-*")))

    def test_stage_ignores_non_newer_revisions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            store = AdaptiveControllerStateStore(path, FakeClock())
            self.assertTrue(store.stage("pid_sp", trusted_snapshot(revision=2)))
            self.assertFalse(store.stage("pid_sp", trusted_snapshot(revision=1)))
            self.assertFalse(store.stage("pid_sp", trusted_snapshot(revision=2)))
            self.assertTrue(store.flush(force=True))

            self.assertEqual(
                AdaptiveControllerStateStore(path).load("pid_sp"),
                trusted_snapshot(revision=2),
            )

    def test_corrupt_or_invalid_root_state_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            for state in (
                "not json",
                json.dumps({"version": 2, "models": {"pid_sp": trusted_snapshot()}}),
                json.dumps(
                    {
                        "version": 1,
                        "models": {
                            "pid_sp": dict(
                                trusted_snapshot(), transient_temperature=225.0
                            )
                        },
                    }
                ),
            ):
                with self.subTest(state=state):
                    path.write_text(state)
                    self.assertIsNone(
                        AdaptiveControllerStateStore(path).load("pid_sp")
                    )

    def test_corrupt_file_allows_immediate_recovery_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            path.write_text("not json")
            clock = FakeClock()
            store = AdaptiveControllerStateStore(path, clock)

            self.assertTrue(store.stage("pid_sp", trusted_snapshot()))
            self.assertTrue(store.flush())
            self.assertEqual(store.load("pid_sp"), trusted_snapshot())

    def test_failed_replace_removes_temporary_file_and_keeps_pending_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.json"
            store = AdaptiveControllerStateStore(path, FakeClock())
            self.assertTrue(store.stage("pid_sp", trusted_snapshot()))

            with self.assertLogs(
                "common.adaptive_controller_state", level="ERROR"
            ) as logged:
                with patch(
                    "common.adaptive_controller_state.os.replace",
                    side_effect=OSError("replace failed"),
                ):
                    self.assertFalse(store.flush(force=True))

            self.assertIn("replace failed", "\n".join(logged.output))
            self.assertEqual(store._pending, {"pid_sp": trusted_snapshot()})
            self.assertFalse(list(path.parent.glob(path.name + ".tmp-*")))
            self.assertTrue(store.flush(force=True))
            self.assertEqual(store.load("pid_sp"), trusted_snapshot())


class RuntimeAdapterTests(unittest.TestCase):
    def test_runtime_uses_optional_hooks_and_json_status(self):
        controller = FakeAdaptiveController()

        self.assertTrue(supports(controller, "set_output"))
        record_output(controller, 0.4, False)

        self.assertEqual(controller.outputs[-1], (0.4, False))
        self.assertEqual(diagnostics(controller), controller.get_status())

    def test_runtime_restores_and_stages_only_adaptive_snapshots(self):
        controller = FakeAdaptiveController()
        store = StoreSpy(trusted_snapshot())

        self.assertTrue(restore_model(controller, store, "pid_sp"))
        self.assertEqual(store.loaded_names, ["pid_sp"])
        self.assertEqual(controller.restored, [trusted_snapshot()])
        self.assertTrue(stage_model(controller, store, "pid_sp"))
        self.assertEqual(store.staged, [("pid_sp", trusted_snapshot())])

    def test_plain_controllers_are_untouched_and_keep_existing_diagnostics(self):
        controller = PlainController()
        store = StoreSpy(trusted_snapshot())

        self.assertFalse(supports(controller, "set_output"))
        self.assertIsNone(record_output(controller, 0.4, False))
        self.assertFalse(restore_model(controller, store, "pid_sp"))
        self.assertFalse(stage_model(controller, store, "pid_sp"))
        self.assertEqual(diagnostics(controller), dict(controller.__dict__))
        self.assertEqual(store.loaded_names, [])
        self.assertEqual(store.staged, [])

    def test_identification_gate_requires_every_override_to_be_inactive(self):
        cases = (
            (False, False, False, True),
            (False, False, True, False),
            (False, True, False, False),
            (False, True, True, False),
            (True, False, False, False),
            (True, False, True, False),
            (True, True, False, False),
            (True, True, True, False),
        )

        for lid_open, manual_override_active, fan_pid_active, expected in cases:
            with self.subTest(
                lid_open=lid_open,
                manual_override_active=manual_override_active,
                fan_pid_active=fan_pid_active,
            ):
                self.assertIs(
                    identification_allowed(
                        lid_open, manual_override_active, fan_pid_active
                    ),
                    expected,
                )

    def test_manual_override_duty_is_exactly_binary(self):
        self.assertEqual(manual_override_duty(False), 0.0)
        self.assertEqual(manual_override_duty(True), 1.0)

    def test_lid_open_transition_disables_next_identifier_interval_until_fresh_command(
        self,
    ):
        clock = FakeClock()
        identifier = AdaptiveFOPDTIdentifier(
            "F", clock, delay_candidates=(0.0,)
        )

        class IdentifierOutputController:
            def __init__(self):
                self.outputs = []

            def supported_functions(self):
                return ("set_output",)

            def set_output(self, duty, identification_allowed=True):
                self.outputs.append((duty, identification_allowed))
                identifier.record_output(duty, identification_allowed)

        controller = IdentifierOutputController()
        identifier.record_output(0.4)
        identifier.observe(250.0)

        clock.now = 5.0
        controller_runtime.record_lid_open_transition(controller)

        self.assertEqual(controller.outputs, [(0.0, False)])
        clock.now = 10.0
        identifier.observe(240.0)
        self.assertEqual(identifier.status()["accepted_observations"], 0)

        identifier.record_output(0.4)
        clock.now = 20.0
        identifier.observe(242.0)
        self.assertEqual(identifier.status()["accepted_observations"], 1)

    def test_live_hold_target_update_only_handles_target_only_hold_change(self):
        controller = FakeAdaptiveController(set_point=250.0)
        control = {
            "updated": True,
            "mode": "Hold",
            "primary_setpoint": 275.0,
            "units_change": False,
        }

        self.assertTrue(apply_live_hold_target(controller, "Hold", control))
        self.assertEqual(controller.targets, [275.0])
        self.assertFalse(control["updated"])

        control.update(updated=True, mode="Stop")
        self.assertFalse(apply_live_hold_target(controller, "Hold", control))
        self.assertTrue(control["updated"])

    def test_live_hold_target_update_leaves_other_updates_for_work_cycle(self):
        controller = FakeAdaptiveController(set_point=250.0)
        for control in (
            {
                "updated": True,
                "mode": "Hold",
                "primary_setpoint": 250.0,
                "units_change": False,
            },
            {
                "updated": True,
                "mode": "Hold",
                "primary_setpoint": 275.0,
                "units_change": True,
            },
            {
                "updated": True,
                "mode": "Hold",
                "primary_setpoint": 275.0,
                "units_change": False,
                "controller_update": True,
            },
        ):
            with self.subTest(control=control):
                self.assertFalse(apply_live_hold_target(controller, "Hold", control))
                self.assertTrue(control["updated"])
                self.assertEqual(controller.targets, [])


    def test_live_target_update_restarts_hold_pid_cycle(self):
        controller = FakeAdaptiveController(set_point=250.0)
        control = {
            "updated": True,
            "mode": "Hold",
            "primary_setpoint": 275.0,
            "units_change": False,
        }
        now = 500.0

        restart_at = apply_live_hold_target_and_restart_cycle(
            controller, "Hold", control, now
        )

        self.assertEqual(restart_at, now)
        self.assertEqual(controller.targets, [275.0])
        self.assertFalse(control["updated"])
        self.assertFalse(hold_pid_update_due(now + 30.0, restart_at, 30.0))
        self.assertTrue(hold_pid_update_due(now + 30.001, restart_at, 30.0))

    def test_pid_tick_keeps_manual_output_until_auger_override_expires(self):
        now = 100.0

        self.assertTrue(hold_pid_update_due(now, 70.0, 20.0))
        self.assertFalse(normal_pid_output_recording_allowed(110.0, now))
        self.assertFalse(normal_pid_output_recording_allowed(now, now))
        self.assertTrue(normal_pid_output_recording_allowed(99.999, now))

    def test_reinit_seed_uses_active_manual_auger_duty(self):
        for auger_output, expected_duty in ((False, 0.0), (True, 1.0)):
            with self.subTest(auger_output=auger_output):
                self.assertEqual(
                    controller_reinit_output_seed(
                        0.42, False, True, False, auger_output
                    ),
                    (expected_duty, False),
                )

    def test_reinit_seed_uses_lid_and_fan_identification_gate_when_manual_is_idle(
        self,
    ):
        for lid_open, fan_pid_active, expected_allowed in (
            (False, False, True),
            (False, True, False),
            (True, False, False),
            (True, True, False),
        ):
            with self.subTest(
                lid_open=lid_open, fan_pid_active=fan_pid_active
            ):
                self.assertEqual(
                    controller_reinit_output_seed(
                        0.42, lid_open, False, fan_pid_active, True
                    ),
                    (0.42, expected_allowed),
                )

if __name__ == "__main__":
    unittest.main()
