"""Capability-based bridge between ``control.py`` and adaptive controllers.

Production control calls these helpers without knowing which controller module
is active.  Adaptive methods run only when a controller explicitly advertises
them; legacy controllers keep their existing behavior through safe no-ops.

This boundary also centralizes which actuator periods are valid identification
data.  Prediction may consume every applied command, but the identifier must not
learn from lid-open safety, manual auger commands, or fan-PID modulation.
"""


def supports(controller, function_name):
    """Check the controller's advertised optional-function protocol.

    Attribute presence alone is insufficient: controllers define their public
    runtime surface through ``supported_functions``.  Malformed legacy objects
    are treated as unsupported rather than breaking the control loop.
    """
    supported_functions = getattr(controller, "supported_functions", None)
    if not callable(supported_functions):
        return False
    try:
        return function_name in supported_functions()
    except (AttributeError, TypeError):
        return False


def record_output(controller, duty, identification_allowed=True):
    """Feed back the duty that reached the actuator, when supported.

    Call this after every production clamp or override decision.  Recording the
    raw PID request would teach the model an input the grill never received.
    ``identification_allowed`` affects learning only; prediction still needs the
    complete applied-duty timeline.
    """
    method = _supported_method(controller, "set_output")
    if method is not None:
        method(duty, identification_allowed)



def record_lid_open_transition(controller):
    """Record the immediate auger-off command imposed by lid-open safety.

    The predictor needs the zero-duty transition at the time it occurred, while
    the identifier must ignore the safety-disturbed response.
    """
    record_output(controller, 0.0, identification_allowed=False)


def identification_allowed(lid_open, manual_override_active, fan_pid_active):
    """Gate learning during actuator paths the PID model did not command."""
    return not (lid_open or manual_override_active or fan_pid_active)


def manual_override_duty(output):
    """Map manual auger state to its exact binary applied duty."""
    return 1.0 if output else 0.0


def controller_reinit_output_seed(
    cycle_ratio,
    lid_open,
    manual_override_active,
    fan_pid_active,
    auger_output,
):
    """Describe actuator state inherited by a replacement controller.

    Reinitialization discards command history, so the new controller must be
    seeded with what the auger is doing now.  Manual output takes precedence and
    is never eligible identification data.
    """
    if manual_override_active:
        return manual_override_duty(auger_output), False
    return cycle_ratio, identification_allowed(
        lid_open, manual_override_active, fan_pid_active
    )

def restore_model(controller, store, name):
    """Restore durable physical knowledge into an adaptive controller.

    Runtime estimator history is intentionally not restored.  Unsupported
    controllers and absent snapshots are normal no-op cases.
    """
    method = _supported_method(controller, "restore_model")
    if method is None:
        return False

    snapshot = store.load(name)
    if snapshot is None:
        return False
    return bool(method(snapshot))


def stage_model(controller, store, name):
    """Validate and stage the controller's newest trusted physical model.

    Staging is separate from flushing so frequent PID updates do not translate
    into frequent storage writes.
    """
    method = _supported_method(controller, "get_model_snapshot")
    if method is None:
        return False

    snapshot = method()
    if snapshot is None:
        return False
    return bool(store.stage(name, snapshot))


def diagnostics(controller):
    """Expose adaptive diagnostics without changing legacy controller payloads."""
    method = _supported_method(controller, "get_status")
    if method is not None:
        return method()
    return dict(controller.__dict__)


def apply_live_hold_target(controller, active_mode, control):
    """Apply a target-only Hold change without rebuilding the controller.

    Preserving the object preserves its trusted model, predictor branches, and
    applied-duty history.  Unit, mode, or gain/configuration changes are left for
    the normal reinitialization path and are not consumed here.
    """
    if active_mode != "Hold" or control.get("mode") != "Hold":
        return False
    if (
        not control.get("updated")
        or control.get("units_change") is not False
        or control.get("controller_update", False)
    ):
        return False
    if "primary_setpoint" not in control or not hasattr(controller, "set_point"):
        return False

    target = control["primary_setpoint"]
    if target == controller.set_point:
        return False

    method = _supported_method(controller, "set_target")
    if method is None:
        return False

    method(target)
    control["updated"] = False
    return True


def apply_live_hold_target_and_restart_cycle(controller, active_mode, control, now):
    """Apply a live target and restart PID timing at the same instant."""
    if not apply_live_hold_target(controller, active_mode, control):
        return None
    return now


def hold_pid_update_due(now, controller_cycle_start, cycle_time):
    """Keep PID scheduling semantics in one testable runtime boundary."""
    return now - controller_cycle_start > cycle_time


def normal_pid_output_recording_allowed(manual_override_until, now):
    """Prevent a normal PID result from overwriting active manual-duty history."""
    return manual_override_until < now


def _supported_method(controller, function_name):
    # Resolve only methods the controller deliberately exposed.  This avoids
    # accidentally invoking similarly named implementation details.
    if not supports(controller, function_name):
        return None
    method = getattr(controller, function_name, None)
    return method if callable(method) else None
