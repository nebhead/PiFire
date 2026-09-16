# PID Controller Simulator Design

## Goal

Provide a deterministic, offline Python CLI that runs PiFire's production PID controllers against a representative pellet-grill thermal plant and prints comparable cooking metrics. Use it to measure the effect of correcting confirmed PID-SP defects without adding dashboard, GPIO, Redis, or third-party dependencies.

## Scope

The CLI will be runnable from the repository root as:

```console
python3 pid_simulator.py
```

It will compare `pid`, `pid_clamping`, `pid_clamping_percent_pb`, `pid_parallel`, `pid_ac`, and `pid_sp` under two setpoint-transition modes: `production-reset`, which reproduces current PiFire behavior, and `continuous`, which calls the live controller's existing `set_target()` method. It will run three four-hour Hold-mode cooking profiles: 250°F, 350°F, and 450°F. Each profile begins from a realistic post-startup pit temperature 50°F below its initial target, then contains two deterministic setpoint changes around its nominal cook temperature. Ambient temperature affects heat loss throughout the simulation but is not the controller-entry temperature.

The terminal report will include one row per controller, profile, and setpoint-transition mode, plus PID-SP before/after results recorded by implementation verification:

- integrated absolute error (°F·min)
- percentage of simulated cook time within ±5°F of the active setpoint
- maximum overshoot (°F)
- settling time after each setpoint change (minutes)
- mean auger duty ratio
- per-setpoint-segment values for the same tracking measures

The simulator is an engineering comparison, not a physical calibration tool. It will use documented default plant parameters and CLI flags to override them. It will not model fuel geometry, weather transients, fan control, combustion chemistry, probe noise, startup/reignite modes, or the web UI.

## Architecture

### CLI and scenarios

`pid_simulator.py` will use only the standard library (`argparse`, `dataclasses`, `statistics`, and `textwrap`). It will expose:

- `--scenario {250,350,450,all}`; default `all`
- `--controller NAME`; repeatable filter, default all supported PID controllers
- `--setpoint-mode {production-reset,continuous}`; repeatable filter, default both modes
- `--ambient-f`; default 70°F
- `--duration-hours`; default 4, and must be greater than 3 so the final segment contains samples
- `--cycle-seconds`; default 15
- `--delay-seconds`; default 35
- `--csv PATH`; optional time-series output for independent plotting

Built-in scenarios will be stable and explicit:

| Scenario | Setpoint profile |
| --- | --- |
| 250 | 250°F → 275°F at 90 min → 250°F at 180 min |
| 350 | 350°F → 325°F at 90 min → 350°F at 180 min |
| 450 | 450°F → 425°F at 90 min → 450°F at 180 min |

The final hour verifies steady-state recovery after the second change.

### Controller adapter

The simulator will instantiate the production controller modules through the same `Controller(config, units, cycle_data)` interface used by `control.py`. A local deterministic clock object will temporarily replace the module-local `time` reference for the duration of each simulated controller call. Controller imports that normally initialize PiFire's Redis-backed logger will receive a temporary standard-library no-op `create_logger` shim, keeping the offline CLI free of Redis and third-party dependencies without changing control equations.

At each controller boundary, the adapter passes the current simulated pit temperature to `Controller.update()`, clamps the returned raw ratio exactly as Hold mode does (`u_min`/`u_max`), and holds the result until the next update. One-second plant samples preserve fractional auger on-time by applying the exact overlap between each sample interval and the floating-point on-window; they do not round duty up to a whole second.

The model begins where PiFire's PID controllers actually begin: after Startup hands control to Hold. The first PID update occurs after one complete Hold cycle, with the initial minimum auger ratio applied during that interval. In `production-reset` mode, a target change reproduces current PiFire behavior: create a fresh controller, restore minimum duty, anchor a new auger cycle, and wait one full interval. In `continuous` mode, call `set_target()` on the existing controller, retain the current duty and auger phase until that cycle completes, and defer the next update until one full interval after the target change. This second mode exercises each controller's own intended state-reset policy without inventing shared PID-state rules.

### Thermal plant

The plant advances in one-second steps. A FIFO delay line turns commanded auger-on time into delayed heat at the firebox. The pit then follows a discrete first-order energy balance:

```text
dT/dt = (delayed_heat_input - heat_loss_coefficient × (pit_temperature - ambient_temperature)) / thermal_mass
```

Default parameters (`thermal_mass=400`, `heat_input_per_second=55`, and `heat_loss_coefficient=0.085`) will produce plausible pellet-grill warm-up, steady-state duty, cooling, and delayed response. With PID-SP controlling the 250°F profile from 200°F, the pit must enter and remain in the ±5°F band within 20 minutes without exceeding 5°F overshoot. At maximum configured duty, the default plant's equilibrium temperature must exceed the highest 450°F target so the comparison does not make that scenario physically unreachable. Parameters will be isolated in one immutable `PlantConfig` dataclass so users can tune a grill model without changing controller code.

### Metrics

The simulator will record a sample each second. Every result and CSV row identifies its setpoint-transition mode. Metrics begin after each segment's setpoint transition and use the active target for that segment. A segment is settled when the temperature remains inside ±5°F for a continuous 10-minute window. Unsettled segments report `not settled`. Overshoot is directional: upward steps measure temperature above target, downward steps measure temperature below target, and the pre-transition temperature is not mislabeled as overshoot. Overshoot is floored at zero when the response never crosses the target; mean duty uses actual fractional auger actuation. The report will sort results by integrated absolute error within each scenario and mode and print all controllers rather than silently choosing a winner.

## PID-SP Corrections

`controller/pid_sp.py` will receive narrowly scoped changes.

1. Replace the hard-coded initial `last = 150` sentinel with an uninitialized prior-sample state. On the first `update(current)`, seed prior temperature and the initial setpoint-change temperature from `current`, use zero rate of change and zero derivative, and then save the real sample. Later cycles retain the existing rate-of-change behavior.
2. Compute `p + i + d` before applying the documented 35% startup reduction. Apply that reduction to the newly computed output only while the actual error is within the proportional band and the setpoint-change window is active.
3. Require a positive finite `tau` and a non-negative finite `theta` when constructing/configuring PID-SP. Set corresponding UI metadata minimums to 1 second and 0 seconds. Invalid direct construction will raise `ValueError`; the settings UI prevents ordinary invalid submissions.
4. Turn the existing `inter_max` calculation into a real bound on `self.inter`, recalculated whenever gains or the center value changes. This prevents hidden integral windup while preserving the existing clamp on `self.i`.

The fixes will not change controller dispatch, auger timing, or any other PID implementation.

## Testing and Verification

New deterministic `unittest` coverage will:

- prove first PID-SP update uses zero rate/derivative from a real first sample rather than a synthetic 150°F sample;
- prove an initial target safely retains its real first-sample baseline through subsequent pre-setpoint updates;
- prove the startup reduction changes the newly calculated output;
- reject zero, negative, NaN, and infinite predictor parameters;
- prove the integral accumulator remains bounded;
- execute all built-in simulation scenarios with every controller, asserting finite metrics and complete output;
- exercise CLI filtering and optional CSV output.

Before production changes, the simulator will produce a saved baseline for each default scenario. After the fixes, it will run the same scenarios and the implementation report will state PID-SP metric deltas. The checked-in CLI reports the current production behavior; it will not preserve a duplicate buggy PID-SP implementation.

## Constraints

- Python standard library only for the simulator and tests.
- The CLI must run from the repository root on supported PiFire Python versions.
- No hardware, Redis, Flask, browser, real-time sleeps, or network access.
- No behavior changes outside PID-SP and its parameter metadata.
- Simulation defaults must be deterministic and documented in source.
