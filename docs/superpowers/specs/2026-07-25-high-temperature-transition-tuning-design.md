# PID-SP High-Temperature Transition Tuning Design

## Goal

Recover the original 450°F first-segment overshoot and settling envelope without giving up the adaptive Smith implementation's aggregate accuracy gains, 600°F capability, plant-independent identification, or production safety behavior.

The tuning must remain setpoint- and plant-independent. It must not add a 450°F threshold, grill-profile constants, an untrusted process model, or a second rate-extrapolation predictor.

## Observed Cause

The deterministic medium-plant 450°F simulation peaks at 455.38°F at second 1693. No Smith model is active during that first segment; identification first activates after the segment. The regression therefore is not caused by the Smith correction or identified model.

During the fresh-model rise, PID-SP leaves transition damping at second 600 and accumulates integral output while the pit still has substantial upward momentum. Integral output peaks at `0.2499`; the medium plant's modeled 450°F steady-state correction is about `0.047`. The excessive stored integral produces the 5.4°F overshoot and longer settling tail.

## Selected Approach

Use a rate-gated integral-release state for output-limited upward setpoint transitions.

This extends PID-SP's existing `new_target` transition bookkeeping. It does not change the Smith predictor, identifier, controller output clamps, persistence schema, or production integration.

## Controller State

PID-SP adds two bounded scalar fields:

- `output_limited_approach`: whether the current upward transition reached its halfway point while the complete candidate output remained at or above `u_max`.
- `slow_approach_samples`: consecutive controller updates whose raw selected-temperature rate toward the target is at or below `r_release`.

Both fields reset in the constructor, `set_target()`, and controller reinitialization through the existing constructor path. They never persist and never enter the trusted physical-model snapshot.

## Native-Unit Scaling

The transition capture band is the existing canonical 3°F band:

- Fahrenheit: `3.0°F`
- Celsius: `3.0 × 5/9 = 1.666666…°C`

The slow-approach threshold is half the capture-band rate over the configured integration time:

\[
r_{release} = \frac{capture\_band}{2 T_i}
\]

For the default `Ti=180s`, this is `0.008333…°F/s` or `0.004629…°C/s`, equivalent to 0.5°F/minute. A deterministic parameter sweep found that the unscaled `capture_band / Ti` rule released damping at 442.3°F and produced 3.2601°F overshoot; the half-rate threshold produced 2.1043°F overshoot while preserving every nominal, 600°F, and identification gate. No new user-facing tuning option is introduced.

If `Ti <= 0`, integral action is disabled already. An output-limited halfway transition completes without rate gating, and no division is performed.

## Update Flow

For each PID update:

1. PID-SP obtains the one selected Smith-or-measured controller temperature exactly as it does now. P, I, D, transition error, and a raw local approach rate all use that same selected temperature. The raw rate is calculated before any derivative-term suppression.
2. Entering the canonical capture band completes transition state immediately and clears both new fields. An upward transition also completes if a discrete sample crosses to or above the target without landing inside the capture band.
3. The existing halfway test remains: at least three Hold cycles have elapsed and the selected error is no more than half the initial selected-temperature error.
4. The existing integral reset remains active outside the stable window and while a not-yet-complete target is at or beyond halfway. This retains only the current update's integration contribution instead of accumulated windup.
5. PID-SP computes P, I, D, startup scaling, and the complete candidate output.
6. If an upward halfway transition's complete candidate is at or above `u_max`, PID-SP sets `output_limited_approach=True` but does not clear `new_target`.
7. While `output_limited_approach` is active, `Ti > 0`, and the upward target remains below and outside the capture band:
   - A raw selected-temperature rate faster than `r_release` resets `slow_approach_samples` to zero.
   - A raw rate at or below `r_release`, including a stall or reversal, increments `slow_approach_samples`.
   - Three consecutive slow samples complete `new_target` and clear the approach state. Normal integral accumulation then resumes on subsequent updates and removes a high-temperature P-only residual.
8. Output continues through the existing production `u_min`/`u_max` clamps and applied-duty feedback path.

A single noisy slow sample cannot release the integrator. A target update restarts the state machine. Lowering transitions and ordinary non-output-limited steps retain their existing behavior.

## Error and Safety Behavior

- Non-finite controller inputs continue through the existing predictor/controller safety paths; this tuning introduces no fallback output.
- `Ti <= 0` performs no division, completes the output-limited halfway state immediately, and cannot enable an integral that is configured off.
- Manual auger changes, lid-open intervals, fan-PID modulation, controller reinitialization, and mode changes retain their existing identification and applied-duty handling.
- The new state is runtime-only, bounded, and JSON-independent.
- No controller other than PID-SP changes.

## Verification

### Focused controller tests

Deterministic clock tests must prove:

1. A fast, output-limited upward approach remains transition-damped and does not accumulate historical integral.
2. Three consecutive slow/stalled samples release integral action below the capture band.
3. One or two slow samples followed by a faster approach do not release it.
4. Entering the capture band releases immediately.
5. A target change clears all approach state.
6. Non-output-limited 250°F-style transitions retain existing behavior.
7. Celsius and Fahrenheit thresholds represent the same physical rate.
8. `Ti=0` is finite and leaves integral disabled.

### Simulator acceptance

For the medium plant in both `production-reset` and `continuous` modes:

- 450°F first segment maximum directional overshoot is at most `2.2°F`.
- 450°F first segment settling time is at most `25.6 minutes`.
- Aggregate 450°F IAE remains no worse than the pre-Smith baseline: `1078.7` production-reset and `1075.6` continuous.
- Aggregate 450°F within-5°F remains no worse than the pre-Smith baseline: `79.4%` production-reset and `79.5%` continuous.
- Aggregate mean duty in each 450°F mode stays within `0.005` of the current adaptive value `0.595`.

Regression gates retain the pre-Smith aggregate envelope for the other nominal scenarios:

| Scenario/mode | Maximum IAE | Minimum within-5°F |
| --- | ---: | ---: |
| 250°F production-reset | 831.7 | 83.1% |
| 250°F continuous | 834.8 | 83.0% |
| 350°F production-reset | 877.6 | 82.5% |
| 350°F continuous | 878.7 | 82.5% |

Existing requirements also remain mandatory:

- Small, medium, and large plants sustain 600°F within ±5°F over the final 600 seconds below `u_max`.
- Closed-loop identification on every plant remains within gain ±10%, tau ±15%, and delay ±5 seconds.
- Every output and metric remains finite and bounded.
- The complete before/current/tuned comparison reports every scenario and mode; it may not select favorable rows.

## Files in Scope

Expected implementation scope:

- `controller/pid_sp.py`
- `tests/test_pid_sp.py`
- `tests/test_pid_simulator.py`
- Runtime comparison artifacts under `/tmp`

`pid_simulator.py`, Smith model/identifier modules, persistence, production `control.py`, and controller metadata must remain unchanged. A failure that requires modifying one of them is a design blocker to report rather than silent scope expansion.
