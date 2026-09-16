# Adaptive Smith Predictor Design

## Goal

Replace PID-SP's rate-of-change temperature extrapolator with a real Smith predictor for a first-order-plus-dead-time (FOPDT) pellet-grill plant. The predictor will use the actual clamped auger command, identify process gain, time constant, and dead time passively from closed-loop operation, retain trusted physical parameters across restarts and Hold setpoint changes, and fall back to measured-temperature PID whenever prediction is not trustworthy.

The deterministic simulator will validate identification and control against small, medium, and large grill models whose exact physical parameters are known.

## Scope

This change covers:

- a standard-library adaptive FOPDT identifier and Smith predictor;
- PID-SP integration using one predicted temperature consistently for P, I, and D;
- feedback of the applied, externally clamped auger ratio;
- live Hold-to-Hold setpoint updates without recreating PID-SP;
- durable storage of trusted physical model parameters;
- simulator plant profiles, a 600°F scenario, estimator diagnostics, and before/after metrics;
- deterministic unit, integration, persistence, and simulation tests.

It does not add deliberate plant excitation, identify nonlinear or multi-zone models, model fan/combustion physics, persist delayed command history, or change other PID implementations' equations.

## Process Model and Smith Equation

Write the FOPDT plant as a constant offset plus a delayed heat-response state:

```text
T(t) = T_offset + x_d(t)
dx/dt = (K × u - x) / tau
x_d(t) = x(t - theta)
```

where:

- `u` is actual applied auger duty in `[0, 1]`;
- `K` is steady-state temperature gain per unit duty;
- `tau` is the first-order time constant in seconds;
- `theta` is firebox dead time in seconds;
- `T_offset` captures ambient and other constant heat balance terms.

The Smith predictor maintains two heat-response states:

- an undelayed state, `x_hat_0`, driven by current applied duty;
- a delayed state, `x_hat_d`, driven by the same duty history shifted by `theta`.

The controller input is:

```text
T_smith = T_measured + x_hat_0 - x_hat_d
```

This is the measured-output Smith formulation. The measured term preserves feedback for plant/model mismatch and disturbances, while the state difference removes identified delay from the feedback signal. The unknown constant offset cancels, so it is estimated for identification but is not required in the persisted predictor model.

Delayed command changes are applied at their exact due timestamps. A command due between two 15-second controller updates divides model integration into segments; delay is not rounded to the controller interval.

## Architecture

### `controller/smith_predictor.py`

This new standard-library module contains two components.

#### `AdaptiveFOPDTIdentifier`

The identifier receives timestamped temperature observations and the applied-duty history. It owns one recursive least-squares estimator for each dead-time candidate from 0 through 120 seconds in 5-second increments.

For candidate `theta_j`, each accepted observation updates:

```text
(T_k - T_(k-1)) / dt = beta_0 + beta_T × T_(k-1) + beta_u × delayed_average_duty
```

The delayed input is the time-weighted average applied duty over:

```text
[t_(k-1) - theta_j, t_k - theta_j]
```

Recovered physical parameters are:

```text
tau = -1 / beta_T
K = -beta_u / beta_T
T_offset = -beta_0 / beta_T
```

RLS uses a forgetting factor of `0.9995`, fixed-size 3×3 covariance matrices initialized to `1e6`, and an exponentially weighted squared-residual factor of `0.02`. Temperature regressors are centered and scaled before each update, then transformed back to physical coefficients, avoiding poor conditioning from absolute grill temperatures. Work is incremental and bounded: 25 delay candidates and fixed-size matrices, with no growing regression window.

The identifier exposes a diagnostic snapshot containing sample counts, excitation measures, best and runner-up residuals, covariance-derived uncertainty, candidate estimates, trusted estimates, and trust state.

#### `SmithPredictor`

The predictor owns:

- trusted `K`, `tau`, and `theta`;
- the undelayed and delayed model states;
- the timestamped applied-duty queue needed by the maximum candidate delay and active Smith model;
- finite-state validation and safe reset logic.

It returns measured temperature until trusted model parameters exist. On initial trust, restoration, or a safety reset, both model branches initialize to equal states so the Smith correction starts at zero.

The module accepts native Fahrenheit or Celsius observations. Bounds and persisted gain use canonical Fahrenheit internally; the predicted temperature returned to PID-SP uses the controller's configured units.
The predictor and identifier accept an injected clock callable. PID-SP supplies its module-local `time.time`, which production leaves real and the simulator already replaces with its deterministic clock.

### `controller/pid_sp.py`

PID-SP will compose the identifier and predictor rather than implement model identification itself.

- Remove the rate-of-change extrapolator and its `roc`-based predicted temperature.
- `update(current)` advances identification/model state and selects measured or Smith-predicted temperature.
- Proportional error, integral accumulation, and derivative all use that same selected temperature.
- Derivative compares consecutive selected controller-input temperatures; it never subtracts an actual sample from a predicted sample.
- Existing auto-center behavior, integral bounds, output construction, and startup reduction remain, with startup reduction applied to the newly calculated output.
- `set_output(applied_ratio, identification_allowed=True)` records the actual externally clamped command. The command always enters predictor history. Invalid/disturbed intervals pause identification only.
- `set_target(set_point)` resets target-dependent PID terms and timing while preserving learned physical parameters, RLS state, model states, and duty history.
- `get_model_snapshot()` returns a serializable trusted physical model with a monotonically increasing revision when model persistence is supported.
- `restore_model(snapshot)` validates and restores trusted physical parameters.

PID-SP adds `get_status()`, returning only JSON-serializable diagnostics: prediction-active state, predicted temperature, model states, estimated gain/tau/delay, confidence, residual, and accepted sample count. `control.py` uses this method instead of exposing PID-SP's `__dict__`; internal estimator objects, matrices, and histories never enter the notification payload. Controllers without `get_status()` retain the existing diagnostics path.

### Production `control.py`

Immediately after creating a supported controller, production control seeds it with the initial applied `CycleRatio` so the first Hold interval is present in command history. After each normal Hold-mode calculation and all min/max/lid-open clamping, production control calls `set_output(CycleRatio, identification_allowed=...)`. PID-SP therefore models the command that will actually drive auger timing, not its unclamped raw output.

Identification is disallowed for explicit disturbance intervals, including lid-open handling, manual auger override, and low-output fan-PID modulation where auger duty alone no longer represents heat input. A manual override records duty `1.0` or `0.0` at override start and restores the current clamped `CycleRatio` at override end, both with identification disabled. These commands still advance Smith history. Re-entry starts a fresh observation interval so RLS never computes a temperature slope across excluded time.

A target-only Hold-to-Hold control update calls `set_target()` on the live controller, clears the update, writes the revised control state, and continues the current work cycle. Controller state is still recreated for mode changes, unit changes, controller selection/configuration changes, and process startup.

### Durable trusted-model state

`control.py` owns persistence so controller modules and the simulator remain filesystem/Redis independent.

The runtime file `adaptive_controller_state.json`, beside `settings.json`, stores a versioned PID-SP record containing:

- gain in °F per unit duty;
- tau and theta in seconds;
- confidence/residual summary;
- observation count;
- trusted-model revision;
- save timestamp.

The physical grill model is an explicit invariant: a process restart does not reduce trust in identified `K`, `tau`, or `theta`. Trusted parameters therefore have no age expiration and restore as trusted immediately.

Persistence behavior:

- reject malformed, non-finite, out-of-bound, or schema-incompatible records;
- write atomically through a same-directory temporary file and `os.replace`;
- write only after a material trusted-model revision, no more than once per 30 minutes during ordinary operation;
- flush a pending trusted revision when the work cycle exits.

RLS matrices, dynamic model states, and delayed command history are not persisted. They describe estimator confidence and past time evolution, not fixed grill physics. After restoration, model branches initialize equally for zero correction while a fresh RLS bank passively verifies and refines the restored model.

## Confidence and Safety

The predictor remains inactive before a restored or newly trusted model exists. New identification uses the following profile-independent gates:

| Gate | Threshold |
| --- | ---: |
| Accepted observation time | at least 3600 seconds |
| Accepted observations at a 15-second cycle | at least 240 |
| Applied-duty standard deviation | at least 0.05 |
| Sustained duty transition | change of at least 0.05 held for 60 seconds |
| Observed temperature span | at least 15°F, or Celsius equivalent |
| Process gain | 50–2000°F per unit duty |
| Time constant | 300–20,000 seconds |
| Gain relative standard error | at most 20% |
| Tau relative standard error | at most 25% |
| Winning delay residual | at least 10% below the runner-up |
| Confirmation window | 20 accepted observations |
| Confirmation stability | gain within 5%, tau within 7.5%, unchanged delay candidate |

A delay candidate is not promoted merely because it has the lowest residual. If candidates are statistically indistinguishable, PID-SP remains measured-temperature PID.

After initial trust, a candidate is a material revision only if gain or tau changes by at least 5% or delay changes by at least 5 seconds. A passing revision is blended into gain and tau with factor `0.1`; delay changes only after the full confirmation window. Abrupt estimates outside the confirmation limits are rejected. The trusted model remains in use while fresh RLS confidence rebuilds after restart because the physical-model invariant makes restart age irrelevant.

Prediction disables immediately if model state or predicted temperature becomes non-finite, leaves the broad physical range of -100°F to 1200°F (converted for Celsius), or the one-step temperature prediction residual exceeds 100°F for four consecutive accepted observations. Both model branches then reinitialize equally and control falls back to measured temperature. The last valid physical parameters remain observable; use resumes only after safe model-state initialization.

All controller outputs continue through existing `[u_min, u_max]` production clamps. The Smith predictor cannot bypass actuator bounds.

## Simulator Changes

### Plant profiles

`pid_simulator.py` adds `--plant {small,medium,large}` and keeps CLI parameter overrides. The profiles are:

| Profile | Thermal mass | Heat input/s | Loss coefficient | Delay | Exact K | Exact tau | Max equilibrium at 70°F |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Small | 250 | 48 | 0.075 | 20s | 640°F/duty | 3333.33s | 710°F |
| Medium | 400 | 55 | 0.085 | 35s | 647.06°F/duty | 4705.88s | 717.06°F |
| Large | 650 | 70 | 0.100 | 50s | 700°F/duty | 6500s | 770°F |

At a 600°F target and 70°F ambient, required steady duties are approximately 0.828, 0.819, and 0.757. Each is reachable below the simulator's existing 0.90 maximum duty with control margin.

The existing default model becomes the `medium` profile. The existing 250°F, 350°F, and 450°F scenarios remain unchanged for before/after continuity. A deterministic 600°F Hold scenario is added for plant-capability verification.

### Applied-duty feedback and diagnostics

The simulator seeds the initial applied duty and calls `set_output()` after the same min/max clamping used in production. PID-SP passes its module-local `time.time` callable into the identifier and predictor, so the simulator's existing controller-module clock replacement controls every timestamp deterministically.

`SimulationResult`, terminal output, and optional CSV diagnostics add:

- identifier activation time;
- final estimated gain, tau, and delay;
- final model confidence/residual;
- prediction-active flag and predicted temperature.

Normal time-series CSV output retains one row per simulated second. Controller/model estimates are sampled without mutating controller state.

### Identification runs

Closed-loop recovery runs execute on all three profiles. Duration is profile-aware and long enough to observe several time constants rather than forcing the large grill into the medium grill's four-hour window. The same identifier settings and confidence gates apply to every profile.

For each profile, the estimator must activate from passive controller behavior and recover:

- gain within ±10%;
- tau within ±15%;
- delay within ±5 seconds.

No profile-specific estimator tuning is permitted.

## Verification

### Predictor tests

Deterministic tests will prove:

- exact undelayed and delayed first-order trajectories;
- segmented integration at delay boundaries between controller samples;
- the measured-output Smith equation;
- equal-state initialization and zero initial correction;
- safe fallback for invalid model state.

### Identifier tests

Synthetic FOPDT tests with variable sample intervals will prove:

- recovery of `K`, `tau`, and `theta` within acceptance tolerances;
- no promotion with constant duty or insufficient temperature span;
- no promotion when delay residuals are ambiguous;
- rejection of non-finite, negative-gain, unstable, and out-of-bound estimates;
- paused intervals do not create a cross-gap slope observation;
- fixed memory and bounded duty-history retention.

### PID-SP and control integration tests

Tests will prove:

- measured temperature is used before model trust;
- one Smith temperature drives P, I, and D after trust;
- startup reduction scales the newly calculated output;
- integral accumulation remains bounded;
- applied clamped duty, not raw output, reaches the predictor;
- target updates retain identification and model state;
- mode/unit/controller/config changes still recreate controller state;
- explicit disturbances update exact command history while pausing identification;
- model persistence flushes atomically on material updates and work-cycle exit.

### Persistence tests

Tests will prove:

- trusted physical parameters round-trip without age expiry;
- corrupted, non-finite, out-of-bound, and incompatible snapshots are ignored;
- restored dynamics begin with zero Smith correction;

### Simulation acceptance

The full existing regression suite must pass. Every controller/profile/mode combination must produce finite metrics and bounded commands.

The medium-profile 250/350/450°F PID-SP report will be captured before implementation and rerun after implementation. Per segment, comparison reports:

- integrated absolute error;
- percentage within ±5°F;
- directional overshoot;
- settling time;
- mean applied duty;
- identifier activation time and final `K`, `tau`, and `theta`.

Results will be reported as measured; the implementation will not tune the test to manufacture a performance win. The existing 250°F acceptance remains: no more than 5°F overshoot and entry into the ±5°F band within 20 minutes. Each plant profile must also sustain the 600°F scenario below maximum configured duty.

## Failure Handling

- Missing or invalid persisted state logs a warning and starts measured-temperature PID with fresh identification.
- Identifier numerical failure resets only the affected candidate; repeated bank failure resets adaptive state without interrupting PID control.
- Predictor numerical failure disables prediction and reinitializes model dynamics; it does not stop the work cycle.
- Persistence failure logs an error and retains the in-memory trusted model.
- Unsupported controllers ignore the optional applied-output/model-state hooks and retain current behavior.

## Constraints

- Runtime estimator/predictor and simulator remain Python-standard-library only.
- Incremental controller work and memory are bounded for Raspberry Pi operation.
- No deliberate excitation is injected into production auger commands.
- No raw controller output may enter the Smith command model after external clamping is available.
- No compatibility shim retains the old rate-of-change predictor.
- Other PID controller equations remain unchanged.
