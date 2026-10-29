#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import math
from math import exp, isfinite


def wheel_speed_estimate(v_est, last_cmd, dt, accel):
    """Forward speed the wheels have now: the drive bridge ramps towards the last command at accel.

    The braking cap needs the real speed, not the command: while the robot slows down the wheels
    still turn faster than the (lower) command.
    """
    step = max(0.0, accel * dt)
    return v_est + max(-step, min(step, last_cmd - v_est))


def camera_bearing(cx, image_width, hfov_deg):
    """Bearing of image column cx (left positive, radians), pinhole model as in sync_fusion."""
    f = (image_width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return math.atan2(image_width / 2.0 - cx, f)


def bearing_turn(bearing, rate, latency_s, gain, limit, deadband):
    """Turn rate towards where the target will be once this frame's latency has passed.

    rate is the bearing's rate of change as seen in the image (target and robot motion together),
    so bearing + rate * latency is where the target is now rather than where the frame showed it.
    """
    pred = bearing + rate * latency_s
    if abs(pred) < deadband:
        return 0.0
    return max(-limit, min(limit, gain * pred))


def target_is_stale(now_s, last_msg_s, timeout_s):
    """True once no target message has arrived for timeout_s (0 = never stale)."""
    return timeout_s > 0.0 and last_msg_s is not None and now_s - last_msg_s > timeout_s


def speed_command(error_dist, speed_ff, dt, linear_gain, tolerance, max_linear_speed,
                  ff_gain, ff_max, ff_decay_s, max_decel=0.0, latency_s=0.0, prev_linear=0.0):
    """Linear command and the updated speed feed-forward, both in /cmd_vel linear.x units.

    The feed-forward learns the command that keeps pace with a walking target (an integral of the
    gap error), so the gap settles near the set-point instead of where P-only control balances.
    It only grows while the target is farther than the set-point and bleeds off quickly once the
    robot is closer, so a target that stops does not get run into.

    max_decel (in /cmd_vel units per second, 0 = off) caps the forward speed at the speed the robot
    can still stop from within the remaining gap, sqrt(2 * max_decel * error). The drive bridge
    ramps the wheels, so without this a fast robot overshoots a target that stops.
    latency_s: the gap was measured this long ago (camera + detector), and the robot has kept moving
    at prev_linear (its estimated wheel speed, see wheel_speed_estimate) since, so the cap uses the gap
    that is left now.
    """
    dt = max(0.0, min(dt, 0.5))
    if error_dist > 0.0:
        speed_ff = min(ff_max, speed_ff + ff_gain * error_dist * dt)
    elif ff_decay_s > 0.0:
        speed_ff *= exp(-dt / ff_decay_s)
    else:
        speed_ff = 0.0

    if error_dist < -tolerance:
        linear_x = linear_gain * error_dist
    elif error_dist <= tolerance:
        linear_x = speed_ff
    else:
        linear_x = linear_gain * error_dist + speed_ff
    if max_decel > 0.0 and linear_x > 0.0:
        left = error_dist - max(0.0, prev_linear) * latency_s
        linear_x = min(linear_x, math.sqrt(2.0 * max_decel * max(0.0, left)))
    linear_x = max(min(linear_x, max_linear_speed), -max_linear_speed)
    return linear_x, speed_ff

def corridor_clearance(points, half_width, direction=1.0, exclude=None, exclude_r=0.0, curvature=0.0):
    """Distance along the path to the nearest return inside the robot's swept corridor, or inf.

    points: (x, y) in the robot frame (x ahead, metres). direction 1 looks ahead, -1 behind. curvature
    (1/m, left positive) bends the corridor along the arc the robot is turning on, so something the turn
    will pass is not a reason to stop, and something on the turn is. A return within exclude_r of exclude
    (x, y), the target being followed, does not count: the follower keeps its own gap to the target.
    Anything else counts, person or not, seen by the camera or not.
    """
    best = math.inf
    for x, y in points:
        if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) <= exclude_r:
            continue
        xd = x * direction
        if abs(curvature) < 1e-3:
            along, off = xd, abs(y)
        else:
            r = 1.0 / curvature  # turning centre at (0, r)
            ang = math.atan2(xd, (r - y) if r > 0 else (y - r))
            along, off = abs(r) * ang, abs(math.hypot(xd, y - r) - abs(r))
        if along <= 0.0 or off > half_width:
            continue
        best = min(best, along)
    return best


def obstacle_speed_cap(clearance, stop_m, max_decel, latency_s, v_now):
    """Fastest speed the robot can still stop from before stop_m short of the obstacle (0 when closer)."""
    left = clearance - stop_m - max(0.0, v_now) * latency_s
    if left <= 0.0:
        return 0.0
    return math.sqrt(2.0 * max(max_decel, 0.1) * left)


def swerve_path(k, swerve_m=0.8, horizon_m=1.6, step_m=0.1):
    """Robot-centre samples (s, x, y) along a swerve: curvature k for swerve_m, -k for swerve_m (heading back
    to where it was), then straight, up to horizon_m."""
    out, x, y, th, s = [], 0.0, 0.0, 0.0, 0.0
    while s < horizon_m - 1e-9:
        kk = k if s < swerve_m - 1e-9 else (-k if s < 2.0 * swerve_m - 1e-9 else 0.0)
        if abs(kk) < 1e-9:
            x, y = x + step_m * math.cos(th), y + step_m * math.sin(th)
        else:
            nth = th + kk * step_m
            x, y, th = x + (math.sin(nth) - math.sin(th)) / kk, y + (math.cos(th) - math.cos(nth)) / kk, nth
        s += step_m
        out.append((s, x, y))
    return out


def path_clearance(points, half_width, path, exclude=None, exclude_r=0.0):
    """Path length before the robot (a disc of half_width) along path first touches a return, or inf."""
    reach = (path[-1][0] + half_width) ** 2 if path else 0.0
    near = [(x, y) for x, y in points if x > -half_width and x * x + y * y <= reach
            and not (exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) <= exclude_r)]
    hw2 = half_width * half_width
    for s, px, py in path:
        if any((x - px) ** 2 + (y - py) ** 2 <= hw2 for x, y in near):
            return s
    return math.inf


def avoid_arc(clearance_of, k_want, target_bearing, k_prev=None, horizon_m=1.6, k_max=1.2, steps=13,
              view_rad=0.8, swerve_m=0.8, turn_cost=0.05):
    """The swerve curvature (1/m, left positive) with the most free path, up to horizon_m, toward the target.

    clearance_of(k) is the free path of the swerve with curvature k. Each is scored by that free path, less
    turn_cost metres per 1/m away from the turn the follower wanted (and from the last swerve, so the robot
    does not swap sides). A swerve that turns the robot more than view_rad away from the target is not
    taken: past the camera's 35 deg half view, LiDAR edge tracking holds the target for a short while. Returns (curvature, free path), or None if no swerve may be taken.
    """
    best = None
    for i in range(steps):
        k = -k_max + 2.0 * k_max * i / (steps - 1)
        if target_bearing is not None and abs(target_bearing - k * swerve_m) > view_rad:
            continue
        c = clearance_of(k)
        score = min(c, horizon_m) - turn_cost * abs(k - k_want) \
            - (turn_cost * abs(k - k_prev) if k_prev is not None else 0.0)
        if best is None or score > best[0]:
            best = (score, k, c)
    return None if best is None else (best[1], best[2])


class FollowStopNode(Node):
    def __init__(self):
        super().__init__('follow_stop_node')

        # ---------- Parameters ----------
        self.declare_parameter('target_distance', 0.5)
        self.declare_parameter('tolerance', 0.1)
        self.declare_parameter('p_fused_threshold', 0.6)

        # motion
        self.declare_parameter('linear_gain', 1.5)
        self.declare_parameter('max_linear_speed', 3.5)
        # speed feed-forward (Arena 2): learns the command that keeps pace with the target
        self.declare_parameter('speed_ff_gain', 1.0)      # per (m · s)
        self.declare_parameter('speed_ff_max', 1.0)       # the bridge saturates at 1.0 (40 RPM)
        self.declare_parameter('speed_ff_decay_s', 0.3)   # time constant once closer than the set-point
        # braking: never faster than the robot can stop from within the gap (bridge ramp is 1.0 m/s^2).
        # In m/s, for the bridge's "mps" mode; with speed_mode:=legacy set max_decel:=0.0
        self.declare_parameter('max_decel', 0.8)
        self.declare_parameter('latency_s', 0.2)          # capture -> command; measure it as E2 on robot day
        self.declare_parameter('bridge_accel_mps2', 1.0)  # the drive bridge's max_accel_mps2 (wheel ramp)

        # init dist
        self.declare_parameter('init_dist_min', 0.5)
        self.declare_parameter('init_dist_max', 1.0)

        # angular / sector logic
        self.declare_parameter('center_sector', 4)        # sector กลาง
        self.declare_parameter('front_band_radius', 1)    # 4±1 = [3,5] = กลาง
        self.declare_parameter('wide_front_radius', 1)    # 4±1 = [3,5]; sector 2/6 starts a turn
        self.declare_parameter('angular_gain', 0.3)
        self.declare_parameter('angular_limit', 0.8)
        self.declare_parameter('edge_consistency', 1)     # หมุนเมื่อเป้าหมายเริ่มออกจากแถบกลาง
        # steer_mode "bearing": turn rate proportional to the target's bearing, predicted over latency_s.
        # "sector" (default) is the original sector logic above.
        self.declare_parameter('steer_mode', 'sector')
        self.declare_parameter('bearing_gain', 2.5)          # rad/s per rad
        self.declare_parameter('bearing_limit', 0.8)         # rad/s; faster turns outrun the target gate
        self.declare_parameter('bearing_deadband_deg', 3.0)
        self.declare_parameter('camera_hfov_deg', 70.0)
        self.declare_parameter('image_width', 640)
        # bearing mode only: publish a stop when target messages stop for this long, instead of leaving
        # the bridge to repeat the last turn until its own 1 s timeout (Codex, T12)
        self.declare_parameter('target_timeout_s', 0.3)
        # obstacle stop: anything the LiDAR sees in the corridor ahead (or behind when reversing), other than
        # the target, caps the speed so the robot stops stop_m short of it. No physical E-stop exists.
        self.declare_parameter('obstacle_stop', True)
        self.declare_parameter('obstacle_half_width_m', 0.30)   # robot 0.47 m wide (thesis slides) + 6.5 cm margin
        self.declare_parameter('obstacle_stop_m', 0.45)         # stop this far from the LiDAR to the obstacle
        self.declare_parameter('obstacle_target_exclude_m', 0.30)  # returns this close to the target are the target
        # obstacle avoid: when the corridor toward the target is blocked, take the nearest clear arc that
        # keeps the target in view instead of only stopping (blind_corner: someone beside the corner)
        self.declare_parameter('obstacle_avoid', True)
        self.declare_parameter('avoid_min_speed_mps', 0.12)  # an arc slower than this is no better than stopping
        self.declare_parameter('avoid_horizon_m', 1.6)       # look this far along the path for a way round
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('lidar_angle_offset_deg', 180.0)  # as sync_fusion_node / lidar_sectorizer_node
        self.declare_parameter('scan_max_age_s', 0.3)

        # ---------- Load ----------
        self.target_distance   = float(self.get_parameter('target_distance').value)
        self.tolerance         = float(self.get_parameter('tolerance').value)
        self.p_fused_threshold = float(self.get_parameter('p_fused_threshold').value)
        self.linear_gain       = float(self.get_parameter('linear_gain').value)
        self.max_linear_speed  = float(self.get_parameter('max_linear_speed').value)
        self.speed_ff_gain     = float(self.get_parameter('speed_ff_gain').value)
        self.speed_ff_max      = float(self.get_parameter('speed_ff_max').value)
        self.speed_ff_decay_s  = float(self.get_parameter('speed_ff_decay_s').value)
        self.max_decel         = float(self.get_parameter('max_decel').value)
        self.latency_s         = float(self.get_parameter('latency_s').value)
        self.bridge_accel      = float(self.get_parameter('bridge_accel_mps2').value)
        self.init_dist_min     = float(self.get_parameter('init_dist_min').value)
        self.init_dist_max     = float(self.get_parameter('init_dist_max').value)

        self.center_sector     = int(self.get_parameter('center_sector').value)
        self.front_band_radius = int(self.get_parameter('front_band_radius').value)
        self.wide_front_radius = int(self.get_parameter('wide_front_radius').value)
        self.angular_gain      = float(self.get_parameter('angular_gain').value)
        self.angular_limit     = float(self.get_parameter('angular_limit').value)
        self.edge_consistency  = int(self.get_parameter('edge_consistency').value)
        self.steer_mode        = str(self.get_parameter('steer_mode').value)
        if self.steer_mode not in ('sector', 'bearing'):
            raise ValueError(f"steer_mode must be 'sector' or 'bearing', got {self.steer_mode!r}")
        self.bearing_gain      = float(self.get_parameter('bearing_gain').value)
        self.bearing_limit     = float(self.get_parameter('bearing_limit').value)
        self.bearing_deadband  = math.radians(float(self.get_parameter('bearing_deadband_deg').value))
        self.camera_hfov_deg   = float(self.get_parameter('camera_hfov_deg').value)
        self.image_width       = int(self.get_parameter('image_width').value)
        self.prev_bearing      = None
        self.prev_bearing_time = None
        self.bearing_rate      = 0.0
        self.target_timeout    = float(self.get_parameter('target_timeout_s').value) if self.steer_mode == 'bearing' else 0.0
        self.last_msg_time     = None
        self.stale_stopped     = False
        self.obstacle_stop     = bool(self.get_parameter('obstacle_stop').value)
        self.obstacle_half_w   = float(self.get_parameter('obstacle_half_width_m').value)
        self.obstacle_stop_m   = float(self.get_parameter('obstacle_stop_m').value)
        self.obstacle_excl     = float(self.get_parameter('obstacle_target_exclude_m').value)
        self.lidar_offset      = math.radians(float(self.get_parameter('lidar_angle_offset_deg').value))
        self.scan_max_age      = float(self.get_parameter('scan_max_age_s').value)
        self.scan_xy           = []     # latest scan in the robot frame
        self.scan_time         = None
        self.obstacle_capped   = False  # last [OBST] state written to the log
        self.obstacle_avoid    = bool(self.get_parameter('obstacle_avoid').value)
        self.avoid_min_speed   = float(self.get_parameter('avoid_min_speed_mps').value)
        self.avoid_horizon     = float(self.get_parameter('avoid_horizon_m').value)
        self.avoid_k           = None   # curvature of the arc being taken around an obstacle
        self.moving_cmd        = None   # last command sent while moving, re-checked on every scan
        self.moving_target     = None   # (x, y, time) of the target point that command was checked with

        # ---------- State ----------
        self.initialized   = False
        self.last_good_cmd = Twist()
        self.last_good_time = self.get_clock().now()
        self.p_buffer      = []
        self.speed_ff      = 0.0
        self.last_linear   = 0.0   # last forward command
        self.v_wheels      = 0.0   # estimated forward wheel speed (bridge ramp towards last_linear)
        self.v_wheels_time = None
        self.last_ctrl_time = None

        # previous sector, for the turn hysteresis below (not a Bayesian prior)
        self.prev_sector   = None
        self.edge_counter  = 0   # นับเฟรมที่อยู่นอก wide-front ติดกัน

        # ---------- ROS ----------
        self.sub = self.create_subscription(Float32MultiArray, '/target_fused_prob', self.cb_fused, 10)
        if self.obstacle_stop:
            self.create_subscription(LaserScan, str(self.get_parameter('scan_topic').value), self.cb_scan, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        if self.target_timeout > 0.0:
            self.stale_timer = self.create_timer(0.05, self.check_stale)

        self.get_logger().info(
            f"FollowStopNode ✅ started | Target={self.target_distance:.2f} m "
            f"(init {self.init_dist_min}-{self.init_dist_max} m)"
        )

    # ==================================================
    def cb_scan(self, msg: LaserScan):
        pts = []
        for i, r in enumerate(msg.ranges):
            if math.isfinite(r) and msg.range_min < r < msg.range_max:
                a = msg.angle_min + i * msg.angle_increment + self.lidar_offset
                pts.append((r * math.cos(a), r * math.sin(a)))
        self.scan_xy = pts
        self.scan_time = self.get_clock().now().nanoseconds / 1e9
        self.recheck_last_cmd()

    def recheck_last_cmd(self):
        """Each scan re-checks the last moving command against the new returns. Target messages can stop
        (a lost target, a single false box), and the bridge keeps the last command until the stale stop and
        its own ramp; whoever walks into the corridor meanwhile still slows the robot (blind_corner run)."""
        cmd = self.moving_cmd
        if cmd is None or cmd.linear.x == 0.0:
            return
        tgt = self.moving_target
        target_xy = tgt[:2] if tgt is not None and self.scan_time - tgt[2] <= self.scan_max_age else None
        capped = self.obstacle_limited(cmd.linear.x, target_xy, cmd.angular.z)
        if abs(capped) < abs(cmd.linear.x):
            twist = Twist()
            twist.linear.x = capped
            twist.angular.z = cmd.angular.z
            self.send(twist)
            self.last_linear = capped

    def send(self, twist, target_xy=None):
        """Publish a command and keep it for the per-scan re-check while it moves the robot."""
        self.pub.publish(twist)
        now = self.get_clock().now().nanoseconds / 1e9
        self.moving_cmd = twist if twist.linear.x != 0.0 else None
        if target_xy is not None:
            self.moving_target = (target_xy[0], target_xy[1], now)

    def obstacle_limited(self, linear_x, target_xy, angular_z=0.0):
        """linear_x capped by the corridor clearance; a stale or missing scan stops forward and reverse motion."""
        if not self.obstacle_stop or linear_x == 0.0:
            return linear_x
        now = self.get_clock().now().nanoseconds / 1e9
        fresh = self.scan_time is not None and 0.0 <= now - self.scan_time <= self.scan_max_age
        direction = 1.0 if linear_x > 0.0 else -1.0
        curvature = angular_z / linear_x if abs(linear_x) > 0.05 else 0.0
        clearance = corridor_clearance(self.scan_xy, self.obstacle_half_w, direction,
                                       target_xy, self.obstacle_excl, curvature) if fresh else 0.0
        cap = obstacle_speed_cap(clearance, self.obstacle_stop_m, self.max_decel, self.latency_s,
                                 abs(self.v_wheels))
        capped = abs(linear_x) > cap
        if capped != self.obstacle_capped:
            self.get_logger().info(f"[OBST] {'on' if capped else 'off'} clearance={clearance:.2f} m"
                                   + ('' if fresh else ' (no fresh scan)'))
            self.obstacle_capped = capped
        return direction * min(abs(linear_x), cap)

    def obstacle_command(self, linear_x, angular_z, target_xy, target_bearing):
        """(linear, angular) after the obstacle stop. With obstacle_avoid, a forward command whose corridor is
        blocked within avoid_horizon_m takes the arc with the most free path that keeps the target in view."""
        now = self.get_clock().now().nanoseconds / 1e9
        fresh = self.scan_time is not None and 0.0 <= now - self.scan_time <= self.scan_max_age
        if self.obstacle_stop and self.obstacle_avoid and fresh and linear_x > self.avoid_min_speed:
            clear = lambda k: path_clearance(self.scan_xy, self.obstacle_half_w,
                                             swerve_path(k, horizon_m=self.avoid_horizon),
                                             target_xy, self.obstacle_excl)
            k_want = angular_z / linear_x
            c_want = path_clearance(self.scan_xy, self.obstacle_half_w,
                                    swerve_path(k_want, swerve_m=self.avoid_horizon, horizon_m=self.avoid_horizon),
                                    target_xy, self.obstacle_excl)
            arc = avoid_arc(clear, k_want, target_bearing, self.avoid_k, self.avoid_horizon) \
                if c_want < self.avoid_horizon else None
            # start only for a clearly better way round; once started, keep going round until the wanted
            # path is free again, so the robot does not swerve and straighten on alternate frames
            if arc is not None and arc[1] > c_want + (0.0 if self.avoid_k is not None else 0.3):
                k = arc[0]
                v = linear_x
                if abs(k * v) > self.angular_limit:
                    v = self.angular_limit / abs(k)
                if v >= self.avoid_min_speed:
                    if self.avoid_k is None:
                        self.get_logger().info(f"[AVOID] on k={k:+.2f}/m free={arc[1]:.2f} m "
                                               f"(wanted {c_want:.2f} m)")
                    self.avoid_k = k
                    return self.obstacle_limited(v, target_xy, k * v), k * v
        if self.avoid_k is not None:
            self.get_logger().info("[AVOID] off")
            self.avoid_k = None
        return self.obstacle_limited(linear_x, target_xy, angular_z), angular_z

    def cb_fused(self, msg: Float32MultiArray):
        if len(msg.data) < 8:
            return
        cx, cy, dist, sector, P_C, P_L, P_fused, dt_ms = msg.data
        sector = int(sector)
        self.last_msg_time = self.get_clock().now().nanoseconds / 1e9
        self.stale_stopped = False

        # ---------- Initial distance check ----------
        if not self.initialized:
            if not (self.init_dist_min <= dist <= self.init_dist_max):
                self.publish_stop()
                self.get_logger().info(
                    f"[WAIT] dist={dist:.2f} m outside init range ({self.init_dist_min}-{self.init_dist_max} m)"
                )
                return
            else:
                self.initialized = True
                self.prev_sector = sector
                self.get_logger().info(f"[INIT ✅] Target locked at {dist:.2f} m — starting follow mode")

        # ---------- Smooth confidence ----------
        self.p_buffer.append(P_fused)
        if len(self.p_buffer) > 5:
            self.p_buffer.pop(0)
        P_fused_smooth = sum(self.p_buffer) / len(self.p_buffer)

        # ---------- Confidence check ----------
        now = self.get_clock().now()
        if self.v_wheels_time is not None:
            dtw = min(5.0, (now - self.v_wheels_time).nanoseconds / 1e9)
            self.v_wheels = wheel_speed_estimate(self.v_wheels, self.last_linear, dtw, self.bridge_accel)
        self.v_wheels_time = now
        if P_fused_smooth < self.p_fused_threshold or not isfinite(dist):
            if (now - self.last_good_time).nanoseconds / 1e9 < 1.0:
                held = Twist()
                held.linear.x = self.obstacle_limited(self.last_good_cmd.linear.x, None,
                                                      self.last_good_cmd.angular.z)
                held.angular.z = self.last_good_cmd.angular.z
                self.send(held)
                self.get_logger().info(f"[HOLD] Low conf {P_fused_smooth:.2f} → keep last cmd")
            else:
                self.publish_stop()
                self.speed_ff = 0.0
                self.last_linear = 0.0
                self.last_ctrl_time = None
                self.get_logger().info(f"[STOP] P_fused={P_fused_smooth:.2f} (low confidence)")
            return

        # ---------- Distance control (P + speed feed-forward) ----------
        error_dist = dist - self.target_distance
        dt = 0.0 if self.last_ctrl_time is None else (now - self.last_ctrl_time).nanoseconds / 1e9
        self.last_ctrl_time = now
        linear_x, self.speed_ff = speed_command(
            error_dist, self.speed_ff, dt, self.linear_gain, self.tolerance, self.max_linear_speed,
            self.speed_ff_gain, self.speed_ff_max, self.speed_ff_decay_s, self.max_decel,
            self.latency_s, self.v_wheels)
        self.last_linear = linear_x

        # ---------- Angular control (hysteresis on the previous sector) ----------
        center = self.center_sector
        front_min = center - self.front_band_radius
        front_max = center + self.front_band_radius
        wide_min  = center - self.wide_front_radius
        wide_max  = center + self.wide_front_radius

        angular_z = 0.0  # ค่าเริ่มต้น: ไม่หมุน

        # 1) ถ้าเฟรมก่อนหน้าอยู่แถวกลาง (3–5) → ถือว่าคนอยู่ด้านหน้า
        if self.prev_sector is not None and (front_min <= self.prev_sector <= front_max):
            # เฟรมใหม่อยู่ใน wide-front (2–6) → ยังไม่ต้องหมุน
            if wide_min <= sector <= wide_max:
                angular_z = 0.0  # ✅ ตามที่เจ้าว่า: 4 → 2,3,5,6 ไม่หมุน
                self.edge_counter = 0
            else:
                # หลุดออกจาก wide-front แล้ว → เริ่มนับ edge
                self.edge_counter += 1
        else:
            # 2) เฟรมก่อนหน้าอยู่ปลาย ๆ แล้ว (เช่น 7–8)
            if sector < wide_min or sector > wide_max:
                self.edge_counter += 1
            else:
                self.edge_counter = 0

        # 3) ถ้าอยู่ edge หลายเฟรมติด → หมุนจริง
        if self.edge_counter >= self.edge_consistency:
            error_sector = sector - center
            angular_z = -self.angular_gain * error_sector
            angular_z = max(min(angular_z, self.angular_limit), -self.angular_limit)
        # else: angular_z = 0 (ยังถือว่า noise / ขยับตัวเล็กน้อย)

        # remember the sector for the next frame
        self.prev_sector = sector

        if self.steer_mode == 'bearing' and (cx <= 0 or cx >= self.image_width - 1):
            # LiDAR edge tracking (sync_fusion) reports the image edge, not a camera bearing: turn that
            # way at the full sector rate and drop the rate estimate, which the jump to the edge spoils
            angular_z = self.angular_limit if cx <= 0 else -self.angular_limit
            self.prev_bearing = None
            self.bearing_rate = 0.0
        elif self.steer_mode == 'bearing':
            bearing = camera_bearing(cx, self.image_width, self.camera_hfov_deg)
            if self.prev_bearing is not None:
                dtb = (now - self.prev_bearing_time).nanoseconds / 1e9
                if 0.02 <= dtb <= 0.5:
                    raw = max(-2.0, min(2.0, (bearing - self.prev_bearing) / dtb))
                    self.bearing_rate = 0.5 * self.bearing_rate + 0.5 * raw
                elif dtb > 0.5:
                    self.bearing_rate = 0.0
            self.prev_bearing, self.prev_bearing_time = bearing, now
            angular_z = bearing_turn(bearing, self.bearing_rate, self.latency_s,
                                     self.bearing_gain, self.bearing_limit, self.bearing_deadband)

        # ---------- Obstacle stop ----------
        tb = (math.radians(self.camera_hfov_deg / 2.0) * (1.0 if cx <= 0 else -1.0)
              if cx <= 0 or cx >= self.image_width - 1 else camera_bearing(cx, self.image_width, self.camera_hfov_deg))
        target_xy = (dist * math.cos(tb), dist * math.sin(tb))
        linear_x, angular_z = self.obstacle_command(linear_x, angular_z, target_xy, tb)
        self.last_linear = linear_x

        # ---------- Publish ----------
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self.send(twist, target_xy)

        self.last_good_cmd = twist
        self.last_good_time = now

        self.get_logger().info(
            f"[MOVE] dist={dist:.2f}m (err={error_dist:+.2f}) "
            f"sec_prev={self.prev_sector} sec_now={sector} "
            f"P={P_fused_smooth:.2f} edge_cnt={self.edge_counter} ff={self.speed_ff:.2f} "
            f"→ v=({linear_x:.2f}, {angular_z:.2f})"
        )

    # ==================================================
    def check_stale(self):
        """Stop once target messages have stopped; the next message resumes control."""
        if self.stale_stopped or not target_is_stale(self.get_clock().now().nanoseconds / 1e9,
                                                     self.last_msg_time, self.target_timeout):
            return
        self.publish_stop()
        self.stale_stopped = True
        self.speed_ff = 0.0
        self.last_linear = 0.0
        self.last_ctrl_time = None
        self.prev_bearing = None
        self.bearing_rate = 0.0
        self.get_logger().info(f"[STALE] no target message for {self.target_timeout:.2f} s → stop")

    def publish_stop(self):
        twist = Twist()
        self.pub.publish(twist)
        self.moving_cmd = None


def main():
    rclpy.init()
    node = FollowStopNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.publish_stop()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
