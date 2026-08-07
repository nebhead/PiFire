#!/usr/bin/env python3

import argparse
import csv
import importlib
import json
import logging
import math
import sys
import types
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Generator, Optional, Sequence

from controller import runtime as controller_runtime


CONTROLLER_NAMES = (
    "pid",
    "pid_clamping",
    "pid_clamping_percent_pb",
    "pid_parallel",
    "pid_ac",
    "pid_sp",
)
SETPOINT_MODES = ("production-reset", "continuous")
U_MIN = 0.05
U_MAX = 0.9
SETTLING_WINDOW_SECONDS = 10 * 60


@dataclass(frozen=True)
class PlantConfig:
    thermal_mass: float = 400.0
    heat_input_per_second: float = 55.0
    heat_loss_coefficient: float = 0.085
    ambient_f: float = 70.0
    firebox_delay_seconds: int = 35



PLANT_PROFILES = {
    "small": PlantConfig(250.0, 48.0, 0.075, 70.0, 20),
    "medium": PlantConfig(400.0, 55.0, 0.085, 70.0, 35),
    "large": PlantConfig(650.0, 70.0, 0.100, 70.0, 50),
}

@dataclass(frozen=True)
class Scenario:
    name: str
    duration_seconds: int
    initial_pit_f: float
    transitions: tuple[tuple[int, float], ...]

    def setpoint_at(self, second: int) -> float:
        target = self.transitions[0][1]
        for transition_second, transition_target in self.transitions:
            if transition_second > second:
                break
            target = transition_target
        return target


@dataclass(frozen=True)
class Sample:
    second: int
    setpoint_f: float
    pit_temp_f: float
    duty_ratio: float
    auger_fraction: float
    auger_on: bool
    setpoint_mode: str
    model_applied_duty: float
    prediction_active: bool
    predicted_temperature: Optional[float]
    estimated_gain_f_per_duty: Optional[float]
    estimated_tau_seconds: Optional[float]
    estimated_theta_seconds: Optional[float]
    model_confidence: Optional[float]
    model_residual: Optional[float]


@dataclass(frozen=True)
class SegmentMetrics:
    segment_number: int
    target_f: float
    start_second: int
    end_second: int
    integrated_absolute_error: float
    percent_within_five_f: float
    max_overshoot: float
    settling_time_minutes: Optional[float]
    mean_duty_ratio: float


@dataclass(frozen=True)
class SimulationResult:
    scenario_name: str
    controller_name: str
    setpoint_mode: str
    integrated_absolute_error: float
    percent_within_five_f: float
    max_overshoot: float
    mean_duty_ratio: float
    segment_metrics: tuple[SegmentMetrics, ...]
    samples: tuple[Sample, ...]
    controller_update_seconds: tuple[int, ...]
    controller_start_seconds: tuple[int, ...]
    model_applied_duty: float
    prediction_active: bool
    predicted_temperature: Optional[float]
    estimated_gain_f_per_duty: Optional[float]
    estimated_tau_seconds: Optional[float]
    estimated_theta_seconds: Optional[float]
    model_confidence: Optional[float]
    model_residual: Optional[float]
    identifier_activation_second: Optional[int]


SCENARIOS = {
    "250": Scenario(
        "250",
        14_400,
        200.0,
        ((0, 250.0), (5_400, 275.0), (10_800, 250.0)),
    ),
    "350": Scenario(
        "350",
        14_400,
        300.0,
        ((0, 350.0), (5_400, 325.0), (10_800, 350.0)),
    ),
    "450": Scenario(
        "450",
        14_400,
        400.0,
        ((0, 450.0), (5_400, 425.0), (10_800, 450.0)),
    ),
    "600": Scenario(
        "600",
        14_400,
        550.0,
        ((0, 600.0),),
    ),
}


def build_identification_scenario(plant: PlantConfig) -> Scenario:
    tau_seconds = plant.thermal_mass / plant.heat_loss_coefficient
    return Scenario(
        "identification",
        round(4.5 * tau_seconds),
        200.0,
        (
            (0, 250.0),
            (round(tau_seconds), 350.0),
            (round(2.0 * tau_seconds), 450.0),
            (round(3.0 * tau_seconds), 300.0),
        ),
    )


class SimulationClock:
    def __init__(self) -> None:
        self.current = 0.0

    def time(self) -> float:
        return self.current


def _create_noop_logger(*args, **_) -> logging.Logger:
    name = str(args[0]) if args else "controller"
    logger = logging.Logger(f"pid_simulator.{name}")
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    logger.disabled = True
    return logger


def load_controller_module(controller_name: str) -> types.ModuleType:
    if controller_name not in CONTROLLER_NAMES:
        raise ValueError(f"Unknown controller: {controller_name}")

    module_name = f"controller.{controller_name}"
    controller_package = importlib.import_module("controller")
    had_package_attribute = hasattr(controller_package, controller_name)
    previous_package_attribute = getattr(controller_package, controller_name, None)
    previous_controller = sys.modules.pop(module_name, None)
    previous_common = sys.modules.pop("common", None)
    common_shim = types.ModuleType("common")
    setattr(common_shim, "create_logger", _create_noop_logger)
    sys.modules["common"] = common_shim

    try:
        module = importlib.import_module(module_name)
    finally:
        sys.modules.pop(module_name, None)
        if previous_controller is not None:
            sys.modules[module_name] = previous_controller
        if had_package_attribute:
            setattr(controller_package, controller_name, previous_package_attribute)
        elif hasattr(controller_package, controller_name):
            delattr(controller_package, controller_name)
        sys.modules.pop("common", None)
        if previous_common is not None:
            sys.modules["common"] = previous_common

    return module


def _controller_defaults(controller_name: str) -> dict:
    metadata_path = Path(__file__).parent / "controller" / "controllers.json"
    metadata = json.loads(metadata_path.read_text())["metadata"][controller_name]
    return {
        option["option_name"]: option["option_default"] for option in metadata["config"]
    }


@contextmanager
def _module_clock(
    controller_module, clock: SimulationClock
) -> Generator[None, None, None]:
    clock_modules = [controller_module]
    controller_base = sys.modules.get("controller.base")
    if controller_base is not None and hasattr(controller_base, "time"):
        clock_modules.append(controller_base)
    original_times = [(module, module.time) for module in clock_modules]
    for module, _ in original_times:
        module.time = clock
    try:
        yield
    finally:
        for module, original_time in reversed(original_times):
            module.time = original_time


def _finite_optional_float(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _model_diagnostics(
    controller, applied_duty: float
) -> tuple[
    float,
    bool,
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    status = (
        controller_runtime.diagnostics(controller)
        if controller_runtime.supports(controller, "get_status")
        else {}
    )
    if not isinstance(status, dict):
        status = {}
    return (
        float(applied_duty),
        bool(status.get("prediction_active", False)),
        _finite_optional_float(status.get("predicted_temperature")),
        _finite_optional_float(status.get("estimated_gain_f_per_duty")),
        _finite_optional_float(status.get("estimated_tau_seconds")),
        _finite_optional_float(status.get("estimated_theta_seconds")),
        _finite_optional_float(status.get("model_confidence")),
        _finite_optional_float(status.get("model_residual")),
    )


def _validate_simulation_inputs(
    scenario: Scenario,
    plant: PlantConfig,
    cycle_seconds: int,
    setpoint_mode: str,
) -> None:
    if setpoint_mode not in SETPOINT_MODES:
        raise ValueError(f"Unknown setpoint mode: {setpoint_mode}")
    if cycle_seconds <= 0:
        raise ValueError("cycle_seconds must be positive")
    if plant.firebox_delay_seconds < 0:
        raise ValueError("firebox_delay_seconds must be non-negative")
    if not math.isfinite(plant.ambient_f):
        raise ValueError("ambient_f must be finite")
    if not math.isfinite(plant.thermal_mass) or plant.thermal_mass <= 0:
        raise ValueError("thermal_mass must be a positive finite number")
    if (
        not math.isfinite(plant.heat_input_per_second)
        or plant.heat_input_per_second <= 0
    ):
        raise ValueError("heat_input_per_second must be a positive finite number")
    if (
        not math.isfinite(plant.heat_loss_coefficient)
        or plant.heat_loss_coefficient <= 0
    ):
        raise ValueError("heat_loss_coefficient must be a positive finite number")
    if not scenario.transitions or scenario.transitions[0][0] != 0:
        raise ValueError("scenario must have an initial transition at second zero")
    if scenario.duration_seconds <= scenario.transitions[-1][0]:
        raise ValueError("scenario duration must extend past its final transition")


def _fractional_auger_duty(
    second: int,
    cycle_start_second: int,
    cycle_seconds: int,
    duty_ratio: float,
) -> float:
    cycle_phase = (second - cycle_start_second) % cycle_seconds
    on_window_end = duty_ratio * cycle_seconds
    return max(0.0, min(cycle_phase + 1.0, on_window_end) - cycle_phase)


def _segment_metrics(
    segment_number: int,
    target_f: float,
    heating_step: bool,
    start_second: int,
    end_second: int,
    samples: Sequence[Sample],
) -> SegmentMetrics:
    segment_samples = samples[start_second:end_second]
    absolute_errors = [abs(sample.pit_temp_f - target_f) for sample in segment_samples]
    integrated_absolute_error = sum(absolute_errors) / 60.0
    percent_within_five_f = (
        100.0 * sum(error <= 5.0 for error in absolute_errors) / len(segment_samples)
    )
    if heating_step:
        overshoot_values = (sample.pit_temp_f - target_f for sample in segment_samples)
    else:
        overshoot_values = (target_f - sample.pit_temp_f for sample in segment_samples)
    max_overshoot = max(0.0, max(overshoot_values))
    mean_duty_ratio = sum(sample.auger_fraction for sample in segment_samples) / len(
        segment_samples
    )

    settling_time_minutes = None
    consecutive_in_band = 0
    for index, error in enumerate(absolute_errors):
        consecutive_in_band = consecutive_in_band + 1 if error <= 5.0 else 0
        if consecutive_in_band >= SETTLING_WINDOW_SECONDS:
            window_start = index - SETTLING_WINDOW_SECONDS + 1
            settling_time_minutes = window_start / 60.0
            break

    return SegmentMetrics(
        segment_number=segment_number,
        target_f=target_f,
        start_second=start_second,
        end_second=end_second,
        integrated_absolute_error=integrated_absolute_error,
        percent_within_five_f=percent_within_five_f,
        max_overshoot=max_overshoot,
        settling_time_minutes=settling_time_minutes,
        mean_duty_ratio=mean_duty_ratio,
    )


def _simulate_with_clock(
    controller_name: str,
    scenario: Scenario,
    plant: PlantConfig,
    cycle_seconds: int,
    setpoint_mode: str,
    controller_module: types.ModuleType,
    controller_config: dict,
    cycle_data: dict,
    clock: SimulationClock,
) -> SimulationResult:
    def create_controller(target: float):
        controller = controller_module.Controller(
            dict(controller_config),
            "F",
            dict(cycle_data),
        )
        controller.set_target(target)
        controller_runtime.record_output(controller, U_MIN)
        return controller

    current_target = scenario.setpoint_at(0)
    controller = create_controller(current_target)
    pit_temperature = scenario.initial_pit_f
    duty_ratio = U_MIN
    cycle_start_second = 0
    next_controller_update = cycle_seconds
    controller_start_seconds = [0]
    controller_update_seconds = []
    samples = []
    transitions = dict(scenario.transitions)
    delay_line = deque([0.0] * plant.firebox_delay_seconds)
    model_applied_duty = U_MIN
    prediction_active = False
    predicted_temperature = None
    estimated_gain_f_per_duty = None
    estimated_tau_seconds = None
    estimated_theta_seconds = None
    model_confidence = None
    model_residual = None
    identifier_activation_second = None

    def refresh_model_diagnostics() -> None:
        nonlocal model_applied_duty
        nonlocal prediction_active
        nonlocal predicted_temperature
        nonlocal estimated_gain_f_per_duty
        nonlocal estimated_tau_seconds
        nonlocal estimated_theta_seconds
        nonlocal model_confidence
        nonlocal model_residual
        nonlocal identifier_activation_second
        (
            model_applied_duty,
            prediction_active,
            predicted_temperature,
            estimated_gain_f_per_duty,
            estimated_tau_seconds,
            estimated_theta_seconds,
            model_confidence,
            model_residual,
        ) = _model_diagnostics(controller, duty_ratio)
        if identifier_activation_second is None and prediction_active:
            identifier_activation_second = int(clock.current)

    refresh_model_diagnostics()

    for second in range(scenario.duration_seconds):
        clock.current = float(second)

        if second != 0 and second in transitions:
            current_target = transitions[second]
            if setpoint_mode == "production-reset":
                controller = create_controller(current_target)
                controller_start_seconds.append(second)
                duty_ratio = U_MIN
                cycle_start_second = second
                refresh_model_diagnostics()
            else:
                controller.set_target(current_target)
            next_controller_update = second + cycle_seconds

        if second >= next_controller_update:
            raw_output = controller.update(pit_temperature)
            if not math.isfinite(raw_output):
                raise ValueError(
                    f"{controller_name} returned non-finite output at second {second}"
                )
            duty_ratio = float(min(max(raw_output, U_MIN), U_MAX))
            controller_runtime.record_output(controller, duty_ratio)
            refresh_model_diagnostics()
            controller_update_seconds.append(second)
            cycle_start_second = second
            next_controller_update = second + cycle_seconds

        auger_fraction = _fractional_auger_duty(
            second,
            cycle_start_second,
            cycle_seconds,
            duty_ratio,
        )
        if delay_line:
            delayed_auger_fraction = delay_line.popleft()
            delay_line.append(auger_fraction)
        else:
            delayed_auger_fraction = auger_fraction

        heat_input = plant.heat_input_per_second * delayed_auger_fraction
        heat_loss = plant.heat_loss_coefficient * (pit_temperature - plant.ambient_f)
        pit_temperature += (heat_input - heat_loss) / plant.thermal_mass
        if not math.isfinite(pit_temperature):
            raise ValueError(f"Plant temperature became non-finite at second {second}")

        samples.append(
            Sample(
                second=second,
                setpoint_f=current_target,
                pit_temp_f=pit_temperature,
                duty_ratio=duty_ratio,
                auger_fraction=auger_fraction,
                auger_on=auger_fraction > 0.0,
                setpoint_mode=setpoint_mode,
                model_applied_duty=model_applied_duty,
                prediction_active=prediction_active,
                predicted_temperature=predicted_temperature,
                estimated_gain_f_per_duty=estimated_gain_f_per_duty,
                estimated_tau_seconds=estimated_tau_seconds,
                estimated_theta_seconds=estimated_theta_seconds,
                model_confidence=model_confidence,
                model_residual=model_residual,
            )
        )

    segment_metrics = []
    for index, (start_second, target_f) in enumerate(scenario.transitions):
        end_second = (
            scenario.transitions[index + 1][0]
            if index + 1 < len(scenario.transitions)
            else scenario.duration_seconds
        )
        previous_target = (
            scenario.initial_pit_f if index == 0 else scenario.transitions[index - 1][1]
        )
        segment_metrics.append(
            _segment_metrics(
                segment_number=index + 1,
                target_f=target_f,
                heating_step=target_f >= previous_target,
                start_second=start_second,
                end_second=end_second,
                samples=samples,
            )
        )

    absolute_errors = [abs(sample.pit_temp_f - sample.setpoint_f) for sample in samples]
    return SimulationResult(
        scenario_name=scenario.name,
        controller_name=controller_name,
        setpoint_mode=setpoint_mode,
        integrated_absolute_error=sum(absolute_errors) / 60.0,
        percent_within_five_f=(
            100.0 * sum(error <= 5.0 for error in absolute_errors) / len(samples)
        ),
        max_overshoot=max(segment.max_overshoot for segment in segment_metrics),
        mean_duty_ratio=(
            sum(sample.auger_fraction for sample in samples) / len(samples)
        ),
        segment_metrics=tuple(segment_metrics),
        samples=tuple(samples),
        controller_update_seconds=tuple(controller_update_seconds),
        controller_start_seconds=tuple(controller_start_seconds),
        model_applied_duty=model_applied_duty,
        prediction_active=prediction_active,
        predicted_temperature=predicted_temperature,
        estimated_gain_f_per_duty=estimated_gain_f_per_duty,
        estimated_tau_seconds=estimated_tau_seconds,
        estimated_theta_seconds=estimated_theta_seconds,
        model_confidence=model_confidence,
        model_residual=model_residual,
        identifier_activation_second=identifier_activation_second,
    )


def simulate_controller(
    controller_name: str,
    scenario: Scenario,
    plant: PlantConfig,
    cycle_seconds: int,
    setpoint_mode: str,
) -> SimulationResult:
    _validate_simulation_inputs(scenario, plant, cycle_seconds, setpoint_mode)
    controller_module = load_controller_module(controller_name)
    controller_config = _controller_defaults(controller_name)
    cycle_data = {
        "HoldCycleTime": cycle_seconds,
        "u_min": U_MIN,
        "u_max": U_MAX,
    }
    clock = SimulationClock()
    with _module_clock(controller_module, clock):
        return _simulate_with_clock(
            controller_name,
            scenario,
            plant,
            cycle_seconds,
            setpoint_mode,
            controller_module,
            controller_config,
            cycle_data,
            clock,
        )


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def run_scenarios(
    controller_names: Optional[Sequence[str]],
    scenarios: Sequence[Scenario],
    plant: PlantConfig,
    cycle_seconds: int,
    setpoint_modes: Optional[Sequence[str]] = None,
) -> list[SimulationResult]:
    selected_controllers = _unique(
        CONTROLLER_NAMES if controller_names is None else controller_names
    )
    selected_modes = _unique(
        SETPOINT_MODES if setpoint_modes is None else setpoint_modes
    )

    unknown_controllers = set(selected_controllers) - set(CONTROLLER_NAMES)
    if unknown_controllers:
        raise ValueError(f"Unknown controllers: {sorted(unknown_controllers)}")
    unknown_modes = set(selected_modes) - set(SETPOINT_MODES)
    if unknown_modes:
        raise ValueError(f"Unknown setpoint modes: {sorted(unknown_modes)}")

    results = [
        simulate_controller(
            controller_name=controller_name,
            scenario=scenario,
            plant=plant,
            cycle_seconds=cycle_seconds,
            setpoint_mode=setpoint_mode,
        )
        for scenario in scenarios
        for setpoint_mode in selected_modes
        for controller_name in selected_controllers
    ]
    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    mode_order = {mode: index for index, mode in enumerate(selected_modes)}
    results.sort(
        key=lambda result: (
            scenario_order[result.scenario_name],
            mode_order[result.setpoint_mode],
            result.integrated_absolute_error,
            result.controller_name,
        )
    )
    return results


def _csv_optional_float(value: Optional[float]) -> str:
    return "" if value is None else f"{value:.6f}"


def write_csv(path: Path, results: Sequence[SimulationResult]) -> None:
    fieldnames = (
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
    )
    with Path(path).open("w", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for sample in result.samples:
                writer.writerow(
                    {
                        "scenario": result.scenario_name,
                        "controller": result.controller_name,
                        "setpoint_mode": result.setpoint_mode,
                        "second": sample.second,
                        "setpoint_f": f"{sample.setpoint_f:.3f}",
                        "pit_temp_f": f"{sample.pit_temp_f:.6f}",
                        "duty_ratio": f"{sample.duty_ratio:.6f}",
                        "auger_fraction": f"{sample.auger_fraction:.6f}",
                        "auger_on": int(sample.auger_on),
                        "model_applied_duty": f"{sample.model_applied_duty:.6f}",
                        "prediction_active": int(sample.prediction_active),
                        "predicted_temperature": _csv_optional_float(
                            sample.predicted_temperature
                        ),
                        "estimated_gain_f_per_duty": _csv_optional_float(
                            sample.estimated_gain_f_per_duty
                        ),
                        "estimated_tau_seconds": _csv_optional_float(
                            sample.estimated_tau_seconds
                        ),
                        "estimated_theta_seconds": _csv_optional_float(
                            sample.estimated_theta_seconds
                        ),
                        "model_confidence": _csv_optional_float(
                            sample.model_confidence
                        ),
                        "model_residual": _csv_optional_float(sample.model_residual),
                    }
                )


def _profile_name(plant: PlantConfig) -> str:
    return next(
        (
            name
            for name, profile in PLANT_PROFILES.items()
            if profile == plant
        ),
        "custom",
    )


def _summary_optional_float(value: Optional[float], precision: int) -> str:
    return "n/a" if value is None else f"{value:.{precision}f}"


def format_summary(
    results: Sequence[SimulationResult],
    plant: PlantConfig,
    plant_name: Optional[str] = None,
) -> str:
    profile_name = plant_name or _profile_name(plant)
    lines = [
        "PID controller simulation",
        (
            f"Plant: {profile_name}, ambient={plant.ambient_f:.1f}F, "
            f"delay={plant.firebox_delay_seconds}s, "
            f"thermal_mass={plant.thermal_mass:.1f}, "
            f"heat_input={plant.heat_input_per_second:.1f}"
        ),
        "",
        (
            f"{'Scenario':>8}  {'Mode':<16}  {'Controller':<25}  "
            f"{'IAE F-min':>10}  {'Within 5F':>10}  {'Over F':>8}  {'Duty':>7}"
        ),
        "-" * 105,
    ]
    for result in results:
        lines.append(
            f"{result.scenario_name:>8}  {result.setpoint_mode:<16}  "
            f"{result.controller_name:<25}  "
            f"{result.integrated_absolute_error:>10.1f}  "
            f"{result.percent_within_five_f:>9.1f}%  "
            f"{result.max_overshoot:>8.1f}  "
            f"{result.mean_duty_ratio:>7.3f}"
        )
        for segment in result.segment_metrics:
            settling = (
                f"{segment.settling_time_minutes:.1f} min"
                if segment.settling_time_minutes is not None
                else "not settled"
            )
            lines.append(
                f"           Segment {segment.segment_number}: "
                f"target={segment.target_f:.0f}F, "
                f"IAE={segment.integrated_absolute_error:.1f}, "
                f"within5={segment.percent_within_five_f:.1f}%, "
                f"overshoot={segment.max_overshoot:.1f}F, "
                f"settling={settling}, duty={segment.mean_duty_ratio:.3f}"
            )
        activation = (
            f"{result.identifier_activation_second}s"
            if result.identifier_activation_second is not None
            else "not active"
        )
        lines.append(
            "           Model: "
            f"active={'yes' if result.prediction_active else 'no'}, "
            f"activation={activation}, "
            f"applied_duty={result.model_applied_duty:.3f}, "
            f"predicted={_summary_optional_float(result.predicted_temperature, 1)}, "
            f"gain={_summary_optional_float(result.estimated_gain_f_per_duty, 3)}, "
            f"tau={_summary_optional_float(result.estimated_tau_seconds, 1)}, "
            f"theta={_summary_optional_float(result.estimated_theta_seconds, 1)}, "
            f"confidence={_summary_optional_float(result.model_confidence, 3)}, "
            f"residual={_summary_optional_float(result.model_residual, 3)}"
        )
    return "\n".join(lines)


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be finite")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare PiFire PID controllers with a deterministic grill model."
    )
    parser.add_argument(
        "--plant",
        choices=tuple(PLANT_PROFILES),
        default="medium",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS) + ("all",),
        default="all",
    )
    parser.add_argument(
        "--controller",
        action="append",
        choices=CONTROLLER_NAMES,
        dest="controllers",
    )
    parser.add_argument(
        "--setpoint-mode",
        action="append",
        choices=SETPOINT_MODES,
        dest="setpoint_modes",
    )
    parser.add_argument("--ambient-f", type=_finite_float, default=None)
    parser.add_argument("--duration-hours", type=_finite_float, default=4.0)
    parser.add_argument("--cycle-seconds", type=_positive_int, default=15)
    parser.add_argument("--delay-seconds", type=_non_negative_int, default=None)
    parser.add_argument("--csv", type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.duration_hours <= 3.0:
        parser.error("--duration-hours must be greater than 3")

    duration_seconds = round(args.duration_hours * 60 * 60)
    if duration_seconds <= 10_800:
        parser.error("duration must extend past the final setpoint transition")

    selected_scenarios = (
        list(SCENARIOS.values())
        if args.scenario == "all"
        else [SCENARIOS[args.scenario]]
    )
    selected_scenarios = [
        replace(scenario, duration_seconds=duration_seconds)
        for scenario in selected_scenarios
    ]
    plant = PLANT_PROFILES[args.plant]
    if args.ambient_f is not None:
        plant = replace(plant, ambient_f=args.ambient_f)
    if args.delay_seconds is not None:
        plant = replace(plant, firebox_delay_seconds=args.delay_seconds)
    results = run_scenarios(
        controller_names=args.controllers,
        scenarios=selected_scenarios,
        plant=plant,
        cycle_seconds=args.cycle_seconds,
        setpoint_modes=args.setpoint_modes,
    )
    print(format_summary(results, plant, args.plant))
    if args.csv is not None:
        write_csv(args.csv, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
