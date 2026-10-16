"""Offline, fail-closed target *association* for a human-selected person.

This is not a verified person re-identification system. Embedding cosine scores
are uncalibrated; the thresholds below are conservative example policy values,
not measured probabilities. A caller must explicitly enroll one visible person
and must independently enforce obstacle, stale-sensor, and motion safety rules.

Only a LOCKED result with a non-None ``target`` authorizes use of that detection.
Every other result means stop. Track IDs are deliberately ignored: a tracker ID
can switch at a crossing. Ambiguity or missing evidence never picks another person.
After SAFE_STOP, a new explicit enrollment is required. A single impostor with
near-identical appearance and plausible position cannot be distinguished by
these inputs; this module must not be presented as an identity guarantee.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class LockState(str, Enum):
    SEARCHING = "SEARCHING"
    CANDIDATE = "CANDIDATE"
    LOCKED = "LOCKED"
    LOST = "LOST"
    REACQUIRING = "REACQUIRING"
    SAFE_STOP = "SAFE_STOP"


@dataclass(frozen=True)
class PersonDetection:
    """One visible person; ``x_m, y_m`` share a fixed robot-relative frame.

    ``observed_at_s`` uses the same monotonic clock as ``now_s``. Embeddings
    must come from the same model and have the same dimension on every frame.
    """

    x_m: float
    y_m: float
    embedding: Tuple[float, ...]
    observed_at_s: float

    def __post_init__(self) -> None:
        if not all(_finite_number(v) for v in (self.x_m, self.y_m, self.observed_at_s)):
            raise ValueError("position and observation time must be finite")
        if self.observed_at_s < 0:
            raise ValueError("observation time must be non-negative")
        vector = tuple(self.embedding)
        if not vector or not all(_finite_number(v) for v in vector):
            raise ValueError("embedding must contain finite numbers")
        if math.hypot(*vector) <= 1e-12:
            raise ValueError("embedding must be nonzero")
        object.__setattr__(self, "embedding", vector)


@dataclass(frozen=True)
class LockConfig:
    min_cosine: float = 0.90
    ambiguity_margin: float = 0.12
    max_initial_displacement_m: float = 0.35
    max_speed_m_s: float = 0.8
    max_observation_age_s: float = 0.2
    lost_timeout_s: float = 1.0
    confirmations: int = 2

    def __post_init__(self) -> None:
        numbers = (self.min_cosine, self.ambiguity_margin, self.max_initial_displacement_m,
                   self.max_speed_m_s, self.max_observation_age_s, self.lost_timeout_s)
        if not all(_finite_number(v) for v in numbers):
            raise ValueError("configuration must be finite")
        if not 0 < self.min_cosine <= 1 or not 0 <= self.ambiguity_margin <= 2:
            raise ValueError("invalid appearance thresholds")
        if self.max_initial_displacement_m < 0 or self.max_speed_m_s < 0:
            raise ValueError("motion gates must be non-negative")
        if self.max_observation_age_s <= 0 or self.lost_timeout_s <= 0:
            raise ValueError("timeouts must be positive")
        if isinstance(self.confirmations, bool) or not isinstance(self.confirmations, int) or self.confirmations < 1:
            raise ValueError("confirmations must be a positive integer")


@dataclass(frozen=True)
class LockResult:
    state: LockState
    target: Optional[PersonDetection]
    reason: str

    @property
    def may_follow(self) -> bool:
        return self.state is LockState.LOCKED and self.target is not None


class TargetIdentityLock:
    """Explicitly enrolled target lock; ``update`` never selects a new target.

    ``enroll`` accepts only the observation selected by the operator, not a
    list of people. Call ``update`` once per new frame with all detected people.
    On loss, motion is withheld immediately; reacquisition takes consecutive
    unambiguous matches. ``SAFE_STOP`` is latched until ``enroll`` is called.
    """

    def __init__(self, config: LockConfig = LockConfig()) -> None:
        self.config = config
        self.state = LockState.SEARCHING
        self._template: Optional[Tuple[float, ...]] = None
        self._last: Optional[PersonDetection] = None
        self._last_frame_s: Optional[float] = None
        self._last_lock_s: Optional[float] = None
        self._confirmations = 0

    def enroll(self, selected: PersonDetection, now_s: float) -> LockResult:
        """Start a fresh lock from one *operator-selected* visible detection."""
        self._validate_time(now_s)
        if not self._fresh(selected, now_s):
            raise ValueError("selected detection is stale or from the future")
        self._template = selected.embedding
        self._last = selected
        self._last_frame_s = now_s
        self._last_lock_s = now_s
        self._confirmations = 0
        self.state = LockState.CANDIDATE
        return self._result("explicit_enrollment")

    def update(self, detections: Sequence[PersonDetection], now_s: float) -> LockResult:
        """Associate one new frame; output a target only when safely LOCKED."""
        self._validate_time(now_s)
        if self._last_frame_s is not None and now_s <= self._last_frame_s:
            raise ValueError("frame time must increase")
        self._last_frame_s = now_s
        if self.state in (LockState.SEARCHING, LockState.SAFE_STOP):
            return self._result("explicit_enrollment_required")
        assert self._last is not None and self._template is not None and self._last_lock_s is not None
        if now_s - self._last_lock_s > self.config.lost_timeout_s:
            self.state = LockState.SAFE_STOP
            return self._result("target_timeout")

        eligible = []
        for detection in detections:
            if not isinstance(detection, PersonDetection):
                raise TypeError("detections must be PersonDetection instances")
            if len(detection.embedding) != len(self._template):
                continue
            if not self._fresh(detection, now_s) or detection.observed_at_s <= self._last.observed_at_s:
                continue
            elapsed = max(0.0, detection.observed_at_s - self._last.observed_at_s)
            gate = self.config.max_initial_displacement_m + self.config.max_speed_m_s * elapsed
            distance = math.hypot(detection.x_m - self._last.x_m, detection.y_m - self._last.y_m)
            similarity = self._cosine(self._template, detection.embedding)
            if distance <= gate and similarity >= self.config.min_cosine:
                eligible.append((similarity, distance, detection))

        if len(eligible) != 1:
            self._confirmations = 0
            self.state = LockState.LOST
            return self._result("ambiguous_people" if eligible else "target_missing")

        match = eligible[0][2]
        # A near-threshold rival inside the spatial gate also makes identity
        # uncertain, even if it just missed the acceptance threshold.
        for rival in detections:
            if (rival is match or len(rival.embedding) != len(self._template)
                    or not self._fresh(rival, now_s)
                    or rival.observed_at_s <= self._last.observed_at_s):
                continue
            elapsed = max(0.0, rival.observed_at_s - self._last.observed_at_s)
            gate = self.config.max_initial_displacement_m + self.config.max_speed_m_s * elapsed
            if math.hypot(rival.x_m - self._last.x_m, rival.y_m - self._last.y_m) <= gate:
                if self._cosine(self._template, rival.embedding) >= eligible[0][0] - self.config.ambiguity_margin:
                    self._confirmations = 0
                    self.state = LockState.LOST
                    return self._result("similar_rival")

        self._last = match
        if self.state is LockState.LOCKED:
            self._last_lock_s = now_s
            return LockResult(self.state, match, "continued_lock")
        self._confirmations += 1
        self.state = LockState.REACQUIRING if self.state in (LockState.LOST, LockState.REACQUIRING) else LockState.CANDIDATE
        if self._confirmations >= self.config.confirmations:
            self.state = LockState.LOCKED
            self._last_lock_s = now_s
            return LockResult(self.state, match, "lock_confirmed")
        return self._result("confirmation_pending")

    def safe_stop(self) -> LockResult:
        """Latch a manual safe stop; only explicit re-enrollment clears it."""
        self.state = LockState.SAFE_STOP
        self._confirmations = 0
        return self._result("manual_safe_stop")

    def _result(self, reason: str) -> LockResult:
        return LockResult(self.state, None, reason)

    def _fresh(self, detection: PersonDetection, now_s: float) -> bool:
        return 0 <= now_s - detection.observed_at_s <= self.config.max_observation_age_s

    @staticmethod
    def _cosine(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
        return sum(x * y for x, y in zip(a, b)) / (math.hypot(*a) * math.hypot(*b))

    @staticmethod
    def _validate_time(now_s: float) -> None:
        if not _finite_number(now_s) or now_s < 0:
            raise ValueError("now_s must be finite and non-negative")
