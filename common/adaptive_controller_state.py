"""Crash-safe persistence for trusted adaptive-controller model snapshots.

Only the small, validated physical model crosses a process restart.  Live RLS
covariance, command history, predictor branches, and confirmation windows remain
runtime state and are rebuilt after restore.

Callers stage newer revisions after PID updates.  Routine flushes are throttled
to protect storage; shutdown forces a final attempt.  A write becomes committed
only after a same-directory temporary file is flushed, fsynced, and atomically
replaced over the prior state file.
"""

import logging
import json
import math
import os
from pathlib import Path
import tempfile
import time


LOGGER = logging.getLogger(__name__)


_ROOT_VERSION = 1
_MODEL_VERSION = 1
_ROOT_KEYS = {"version", "models"}
_MODEL_KEYS = {
    "version",
    "gain_f_per_duty",
    "tau_seconds",
    "theta_seconds",
    "confidence",
    "residual",
    "observations",
    "revision",
}
_NUMERIC_MODEL_KEYS = (
    "gain_f_per_duty",
    "tau_seconds",
    "theta_seconds",
    "confidence",
    "residual",
)


class AdaptiveControllerStateStore:
    """Validate, stage, and atomically persist trusted physical models.

    ``_models`` is the last durable generation and ``_pending`` is newer
    in-memory work.  Pending entries are cleared only after a successful atomic
    replacement, so a transient write failure can be retried without losing the
    latest learned model.
    """

    def __init__(
        self,
        path=Path("adaptive_controller_state.json"),
        clock=time.time,
        min_write_interval=1800.0,
    ):
        interval = float(min_write_interval)
        if not math.isfinite(interval) or interval < 0.0:
            raise ValueError("min_write_interval must be a non-negative finite number")

        self.path = Path(path)
        self._clock = clock
        self._min_write_interval = interval
        # Treat a missing or invalid file as an empty store.  A corrupt snapshot
        # must never partially restore model parameters into a controller.
        loaded_models = self._read_models()
        self._models = {} if loaded_models is None else loaded_models
        self._pending = {}
        self._last_successful_write = (
            self._now() if loaded_models is not None else None
        )

    def load(self, name):
        # Return a copy so controller restore code cannot mutate durable state
        # before a newer, explicitly validated revision is staged.
        """Return a copy of a persisted trusted snapshot, if it is valid."""
        snapshot = self._models.get(name)
        return None if snapshot is None else dict(snapshot)

    def stage(self, name, snapshot):
        """Stage a newer trusted snapshot without writing dynamic controller state."""
        if not isinstance(name, str) or not name:
            return False

        # Validate the complete snapshot at the storage boundary.  Persistence
        # accepts no extra keys, booleans-as-numbers, NaN, or unphysical values.
        validated = self._validate_model(snapshot)
        if validated is None:
            return False

        # Revisions are monotonic per controller name.  Compare against pending
        # first so repeated staging cannot replace newer unsaved work.
        current = self._pending.get(name, self._models.get(name))
        if current is not None and validated["revision"] <= current["revision"]:
            return False

        self._pending[name] = validated
        return True

    def flush(self, force=False):
        """Atomically write pending models when the routine-write interval permits."""
        # No pending generation means there is nothing to commit.  ``False`` is
        # intentionally also used for a throttled/no-op flush.
        if not self._pending:
            return False
        # Routine writes are rate limited, but ``force=True`` bypasses only the
        # timer—not validation or atomic-write safety.
        if (
            not force
            and self._last_successful_write is not None
            and self._now() - self._last_successful_write
            < self._min_write_interval
        ):
            return False

        # Build the next complete generation without mutating the durable view.
        # If writing fails, both _models and _pending remain retryable.
        models = dict(self._models)
        models.update(self._pending)
        root = {"version": _ROOT_VERSION, "models": models}
        if not self._write(root):
            return False

        # Publish the in-memory generation only after os.replace succeeded.
        self._models = models
        self._pending.clear()
        self._last_successful_write = self._now()
        return True

    def _now(self):
        return float(self._clock())

    def _read_models(self):
        # Loading is fail-closed: any I/O, JSON, root-schema, or member error
        # rejects the entire file rather than mixing trusted and suspect models.
        try:
            with self.path.open("r", encoding="utf-8") as state_file:
                root = json.load(state_file)
        except (OSError, TypeError, ValueError):
            return None

        if type(root) is not dict or set(root) != _ROOT_KEYS:
            return None
        if type(root["version"]) is not int or root["version"] != _ROOT_VERSION:
            return None
        if type(root["models"]) is not dict:
            return None

        models = {}
        for name, snapshot in root["models"].items():
            if not isinstance(name, str) or not name:
                return None
            validated = self._validate_model(snapshot)
            if validated is None:
                return None
            models[name] = validated
        return models

    def _validate_model(self, snapshot):
        # Exact versioned schemas make forward/backward incompatibility explicit
        # and keep persistence limited to immutable physical model parameters.
        if type(snapshot) is not dict or set(snapshot) != _MODEL_KEYS:
            return None
        if type(snapshot["version"]) is not int or snapshot["version"] != _MODEL_VERSION:
            return None
        if any(
            isinstance(snapshot[key], bool)
            or not isinstance(snapshot[key], (int, float))
            or not math.isfinite(snapshot[key])
            for key in _NUMERIC_MODEL_KEYS
        ):
            return None
        if any(type(snapshot[key]) is not int for key in ("observations", "revision")):
            return None
        if not 50.0 <= snapshot["gain_f_per_duty"] <= 2000.0:
            return None
        if not 300.0 <= snapshot["tau_seconds"] <= 20000.0:
            return None
        if not 0.0 <= snapshot["theta_seconds"] <= 120.0:
            return None
        if not 0.0 <= snapshot["confidence"] <= 1.0:
            return None
        if snapshot["residual"] < 0.0:
            return None
        if snapshot["observations"] < 0 or snapshot["revision"] < 0:
            return None
        return dict(snapshot)

    def _write(self, root):
        temporary_path = None
        try:
            # The temporary file shares the destination directory, allowing
            # os.replace to provide an atomic same-filesystem cutover.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=self.path.name + ".tmp-",
                delete=False,
                encoding="utf-8",
            ) as state_file:
                temporary_path = Path(state_file.name)
                # Flush Python buffers and then the OS file descriptor before
                # replacement so a successful return represents durable bytes.
                json.dump(root, state_file, sort_keys=True, indent=2)
                state_file.flush()
                os.fsync(state_file.fileno())
            # Atomic replacement preserves the previous complete generation if
            # the process fails before this point.
            os.replace(temporary_path, self.path)
            temporary_path = None
            return True
        except Exception:
            LOGGER.exception(
                "Unable to atomically write adaptive controller model state"
            )
            return False
        finally:
            # A failed write may leave a named temporary file; remove it without
            # masking the original persistence error.  Pending state is retained.
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
