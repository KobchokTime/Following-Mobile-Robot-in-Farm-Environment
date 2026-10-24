"""2D kinematic world for the offline robot twin. Standard library only.

The world holds one differential-drive robot and a set of people who walk along
scripted waypoints. It produces what the real robot's sensors would see:

- a 2D LiDAR scan in the LiDAR frame (mounted with a configurable yaw, 180 deg on
  the real robot, which `lidar_sectorizer_node.py` undoes with `angle_offset_deg`);
- person detections in image coordinates, as `ros2_yolo_live.py` would publish them
  (`[cx, cy, sector_id]`, one message per visible person, 9 image sectors).

It also models the current ZLAC drive bridge (`MAIN/Control/zlac_joystick_bridge.py`):
linear command only, `cmd = clamp(linear_x * 40, +-40)` RPM per wheel, and zero
after 1 s without a new `/cmd_vel`. A `diff_drive` mode also uses `angular.z`, to
show what the follower would do once the bridge forwards turning commands.

Each detection also carries the clothing chroma `(Cb, Cr)` that the thesis's appearance model
uses (YCbCr, 0-255, 128 = grey). It is observed with noise, and shade pulls it towards grey. It
comes from its own random stream, so adding it does not change any other simulated value.

Frames: x forward, y left, yaw counter-clockwise (ROS REP-103). Image x grows to
the right, so a person on the robot's left has a small `cx`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

PERSON_RADIUS_M = 0.2


@dataclass
class RobotParams:
    wheel_radius_m: float = 0.085  # assumption: not measured on the real chassis yet
    track_width_m: float = 0.40  # assumption: not measured on the real chassis yet
    bridge_mode: str = "current"  # "current" (linear only), "fixed" (bridge with angular.z) or "diff_drive"
    speed_gain: float = 40.0  # zlac_joystick_bridge.py SPEED_GAIN
    max_cmd_rpm: float = 40.0  # zlac_joystick_bridge.py MAX_CMD
    cmd_timeout_s: float = 1.0  # zlac_joystick_bridge.py TIMEOUT


@dataclass
class SensorParams:
    lidar_rays: int = 720
    lidar_range_min_m: float = 0.05
    lidar_range_max_m: float = 12.0
    lidar_mount_yaw_rad: float = math.pi
    lidar_noise_m: float = 0.01
    camera_hfov_deg: float = 70.0
    image_width: int = 640
    image_height: int = 480
    camera_height_m: float = 0.5
    num_sectors: int = 9
    detect_range_m: Tuple[float, float] = (0.3, 8.0)
    person_height_m: float = 1.7
    person_width_m: float = 0.5
    detect_dropout: float = 0.0
    centroid_noise_px: float = 2.0
    chroma_noise: float = 3.0  # per-frame noise on observed Cb/Cr (0-255 units)


@dataclass
class Person:
    name: str
    waypoints: List[Tuple[float, float, float]]  # (t_s, x_m, y_m), linear in between
    is_target: bool = False
    clothing: Tuple[float, float] = (128.0, 128.0)  # (Cb, Cr) of the torso in full light

    def position(self, t: float) -> Tuple[float, float]:
        pts = self.waypoints
        if t <= pts[0][0]:
            return pts[0][1], pts[0][2]
        for (t0, x0, y0), (t1, x1, y1) in zip(pts, pts[1:]):
            if t <= t1:
                a = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return x0 + a * (x1 - x0), y0 + a * (y1 - y0)
        return pts[-1][1], pts[-1][2]


@dataclass
class Detection:
    person: str
    cx: int
    cy: int
    sector_id: int
    cb: int = 128
    cr: int = 128
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)  # x1, y1, x2, y2, clipped to the image


def shade_factor(x: float, shade: Sequence[Tuple[float, float, float]]) -> float:
    """Colour saturation at world x: 1.0 in full light, lower in the shade bands (x0, x1, factor)."""
    return min([f for x0, x1, f in shade if x0 <= x < x1], default=1.0)


def observe_clothing(people: Sequence["Person"], world_x: Dict[str, float], shade: Sequence[Tuple[float, float, float]],
                     noise: float, rng: random.Random) -> Dict[str, Tuple[int, int]]:
    """Observed (Cb, Cr) per person: shade pulls the chroma towards grey (128), plus noise."""
    out = {}
    for p in people:
        f = shade_factor(world_x[p.name], shade)
        cb, cr = (128.0 + f * (c - 128.0) + rng.gauss(0.0, noise) for c in p.clothing)
        out[p.name] = (int(round(max(0.0, min(255.0, cb)))), int(round(max(0.0, min(255.0, cr)))))
    return out


def bridge_rpm(r: RobotParams, cmd: Tuple[float, float], age_s: Optional[float]) -> Tuple[float, float]:
    """Wheel RPMs (logical left, logical right) for a /cmd_vel of `age_s` seconds."""
    if age_s is None or age_s > r.cmd_timeout_s:
        return 0.0, 0.0
    lin, ang = cmd
    if r.bridge_mode == "current":
        c = max(-r.max_cmd_rpm, min(r.max_cmd_rpm, lin * r.speed_gain))
        return c, c  # angular.z is ignored by the current bridge
    if r.bridge_mode == "fixed":
        # zlac_joystick_bridge.py after angular.z support: same 40-RPM-per-unit gain as "current",
        # differential mix, both wheels scaled together at max_cmd_rpm (turn_dir = +1).
        turn = ang * r.track_width_m / 2.0
        left, right = (lin - turn) * r.speed_gain, (lin + turn) * r.speed_gain
        scale = max(1.0, abs(left) / r.max_cmd_rpm, abs(right) / r.max_cmd_rpm)
        return left / scale, right / scale
    if r.bridge_mode == "diff_drive":
        to_rpm = 60.0 / (2.0 * math.pi * r.wheel_radius_m)
        left = (lin - ang * r.track_width_m / 2.0) * to_rpm
        right = (lin + ang * r.track_width_m / 2.0) * to_rpm
        scale = max(1.0, abs(left) / r.max_cmd_rpm, abs(right) / r.max_cmd_rpm)
        return left / scale, right / scale
    raise ValueError(f"unknown bridge_mode {r.bridge_mode!r}")


def wheel_twist(r: RobotParams, rpm_left: float, rpm_right: float) -> Tuple[float, float]:
    """Body (v m/s, w rad/s) for the given wheel RPMs."""
    k = 2.0 * math.pi * r.wheel_radius_m / 60.0
    vl, vr = rpm_left * k, rpm_right * k
    return (vl + vr) / 2.0, (vr - vl) / r.track_width_m


def _ray_circle(angle: float, cx: float, cy: float, r: float) -> Optional[float]:
    dx, dy = math.cos(angle), math.sin(angle)
    b = dx * cx + dy * cy
    disc = b * b - (cx * cx + cy * cy - r * r)
    if disc < 0:
        return None
    t = b - math.sqrt(disc)
    return t if t > 0 else None


def project_detections(people: Dict[str, Tuple[float, float]], s: "SensorParams",
                       rng: random.Random, chroma: Optional[Dict[str, Tuple[int, int]]] = None) -> List["Detection"]:
    """What ros2_yolo_live.py would publish for people at robot-frame positions."""
    f = (s.image_width / 2.0) / math.tan(math.radians(s.camera_hfov_deg) / 2.0)
    out = []
    for name, (px, py) in people.items():
        d = math.hypot(px, py)
        if px <= 0 or not (s.detect_range_m[0] <= d <= s.detect_range_m[1]):
            continue
        bearing = math.atan2(py, px)
        if abs(math.degrees(bearing)) > s.camera_hfov_deg / 2.0:
            continue
        occluded = False
        for other, (ox, oy) in people.items():
            hit = None if other == name else _ray_circle(bearing, ox, oy, PERSON_RADIUS_M)
            if hit is not None and hit < d - PERSON_RADIUS_M:
                occluded = True
        if occluded or (s.detect_dropout and rng.random() < s.detect_dropout):
            continue
        cx = s.image_width / 2.0 - f * math.tan(bearing)
        cy = s.image_height / 2.0 + f * (s.camera_height_m - 0.9) / px
        cx = int(round(cx + rng.gauss(0.0, s.centroid_noise_px)))
        cx = max(0, min(s.image_width - 1, cx))
        sector = max(0, min(s.num_sectors - 1, (cx * s.num_sectors) // s.image_width))
        cb, cr = (chroma or {}).get(name, (128, 128))
        half_w = f * s.person_width_m / 2.0 / px
        top = s.image_height / 2.0 + f * (s.camera_height_m - s.person_height_m) / px
        bottom = s.image_height / 2.0 + f * s.camera_height_m / px
        box = (int(max(0, cx - half_w)), int(max(0, top)),
               int(min(s.image_width - 1, cx + half_w)), int(min(s.image_height - 1, bottom)))
        out.append(Detection(name, cx, int(round(cy)), sector, cb, cr, box))
    return out


@dataclass
class World:
    people: List[Person]
    robot: RobotParams = field(default_factory=RobotParams)
    sensors: SensorParams = field(default_factory=SensorParams)
    blackouts: Sequence[Tuple[float, float]] = ()  # detector blind windows (t_start, t_end)
    shade: Sequence[Tuple[float, float, float]] = ()  # (x0, x1, saturation factor) bands in world x
    seed: int = 0

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.color_rng = random.Random(self.seed + 7919)  # separate stream: chroma never shifts other noise
        self.t = 0.0
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.v = 0.0
        self.w = 0.0
        self.rpm_left = 0.0
        self.rpm_right = 0.0
        self._cmd: Tuple[float, float] = (0.0, 0.0)
        self._cmd_t: Optional[float] = None

    # ---------------------------------------------------------------- drive
    def command(self, linear_x: float, angular_z: float) -> None:
        """Receive a /cmd_vel at the current sim time."""
        self._cmd = (float(linear_x), float(angular_z))
        self._cmd_t = self.t

    def _bridge(self) -> Tuple[float, float]:
        """Wheel RPMs (logical left, logical right) the drive bridge would send."""
        age = None if self._cmd_t is None else self.t - self._cmd_t
        return bridge_rpm(self.robot, self._cmd, age)

    def step(self, dt: float) -> None:
        self.rpm_left, self.rpm_right = self._bridge()
        self.v, self.w = wheel_twist(self.robot, self.rpm_left, self.rpm_right)
        self.yaw = (self.yaw + self.w * dt + math.pi) % (2.0 * math.pi) - math.pi
        self.x += self.v * math.cos(self.yaw) * dt
        self.y += self.v * math.sin(self.yaw) * dt
        self.t += dt

    # -------------------------------------------------------------- geometry
    def _to_robot(self, px: float, py: float) -> Tuple[float, float]:
        dx, dy = px - self.x, py - self.y
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        return c * dx + s * dy, -s * dx + c * dy

    def people_robot_frame(self) -> Dict[str, Tuple[float, float]]:
        return {p.name: self._to_robot(*p.position(self.t)) for p in self.people}

    def scan(self) -> List[float]:
        """Ranges in the LiDAR frame, angle_min=-pi, increment 2*pi/rays."""
        s = self.sensors
        people = list(self.people_robot_frame().values())
        out = []
        for i in range(s.lidar_rays):
            a_lidar = -math.pi + i * 2.0 * math.pi / s.lidar_rays
            a_robot = a_lidar + s.lidar_mount_yaw_rad
            best = math.inf
            for px, py in people:
                hit = _ray_circle(a_robot, px, py, PERSON_RADIUS_M)
                if hit is not None and hit < best:
                    best = hit
            if math.isfinite(best):
                best += self.rng.gauss(0.0, s.lidar_noise_m)
                if not (s.lidar_range_min_m < best < s.lidar_range_max_m):
                    best = math.inf
            out.append(best)
        return out

    def detections(self) -> List[Detection]:
        if any(a <= self.t < b for a, b in self.blackouts):
            return []
        chroma = observe_clothing(self.people, {p.name: p.position(self.t)[0] for p in self.people},
                                  self.shade, self.sensors.chroma_noise, self.color_rng)
        return project_detections(self.people_robot_frame(), self.sensors, self.rng, chroma)

    def state(self) -> dict:
        people = {}
        for p in self.people:
            rx, ry = self._to_robot(*p.position(self.t))
            people[p.name] = {
                "range_m": math.hypot(rx, ry),
                "bearing_deg": math.degrees(math.atan2(ry, rx)),
                "is_target": p.is_target,
            }
        return {
            "t": round(self.t, 3),
            "robot": {"x": self.x, "y": self.y, "yaw_deg": math.degrees(self.yaw),
                      "v": self.v, "w": self.w,
                      "rpm_left": self.rpm_left, "rpm_right": self.rpm_right},
            "cmd": {"linear_x": self._cmd[0], "angular_z": self._cmd[1],
                    "age_s": None if self._cmd_t is None else self.t - self._cmd_t},
            "people": people,
            "blackout": any(a <= self.t < b for a, b in self.blackouts),
        }
