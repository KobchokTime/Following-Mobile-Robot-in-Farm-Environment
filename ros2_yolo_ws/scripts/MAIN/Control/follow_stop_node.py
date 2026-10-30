#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
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

# The robot's own body (thesis slides: 47 cm wide, 52 cm long, LiDAR at the centre). A return no farther along
# the path than the body's front is beside the robot, not ahead of it: driving on slides past it unless it is
# inside the body's own half width (pass_by s3/s8: the robot stopped level with the worker for good).
FLANK = (0.26, 0.235)


def corridor_clearance(points, half_width, direction=1.0, exclude=None, exclude_r=0.0, curvature=0.0, flank=FLANK):
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
        if along <= 0.0 or off > (flank[1] if along <= flank[0] else half_width):
            continue
        best = min(best, along)
    return best


def obstacle_speed_cap(clearance, stop_m, max_decel, latency_s, v_now):
    """Fastest speed the robot can still stop from before stop_m short of the obstacle (0 when closer)."""
    left = clearance - stop_m - max(0.0, v_now) * latency_s
    if left <= 0.0:
        return 0.0
    return math.sqrt(2.0 * max(max_decel, 0.1) * left)


def segment_blocked(points, half_width, end, exclude=None, exclude_r=0.0, flank=FLANK):
    """True if a return, other than within exclude_r of exclude, lies within half_width of the straight
    path from the robot to end (x, y)."""
    length = math.hypot(end[0], end[1])
    if length < 1e-6:
        return False
    ux, uy = end[0] / length, end[1] / length
    for x, y in points:
        if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) <= exclude_r:
            continue
        along = x * ux + y * uy
        if 0.0 < along <= length and abs(y * ux - x * uy) <= (flank[1] if along <= flank[0] else half_width):
            return True
    return False


def aim_offset(points, half_width, target_xy, exclude_r, prefer=0.0, step_m=0.1, max_angle_rad=0.5):
    """How far (m, left positive) to aim beside the target so the straight path there is clear.

    0.0 when the path to the target itself is clear; the smallest clear shift otherwise, trying the side of
    prefer first (the side already taken, so the robot does not swap); None when no shift within
    max_angle_rad of the target's direction is clear (the camera still sees the target there).
    """
    tx, ty = target_xy
    d = math.hypot(tx, ty)
    if d < 1e-6 or not segment_blocked(points, half_width, target_xy, target_xy, exclude_r):
        return 0.0
    nx, ny = -ty / d, tx / d  # left of the line to the target
    sides = (-1.0, 1.0) if prefer < 0.0 else (1.0, -1.0)
    n = 1
    while n * step_m <= d * math.tan(max_angle_rad) + 1e-9:
        for side in sides:
            o = side * n * step_m
            if not segment_blocked(points, half_width, (tx + o * nx, ty + o * ny), target_xy, exclude_r):
                return o
        n += 1
    return None


def trail_aim(crumbs, pose, points, half_width, exclude=None, exclude_r=0.0, min_dist=0.35,
              shifts=(0.0, -0.1, 0.1, -0.2, 0.2, -0.3, 0.3)):
    """The newest breadcrumb of the target's path the robot can reach in a clear straight line, in the robot
    frame, or None. A crumb whose line is blocked is tried shifted sideways (smallest shift first), so the
    robot can pass someone whose edge reaches into the lane along the target's path (blind_corner).
    crumbs: world (x, y) oldest first; pose: the robot's dead-reckoned (x, y, heading)."""
    c, s = math.cos(pose[2]), math.sin(pose[2])
    for wx, wy in reversed(crumbs):
        dx, dy = wx - pose[0], wy - pose[1]
        lx, ly = c * dx + s * dy, -s * dx + c * dy
        d = math.hypot(lx, ly)
        if lx < 0.05 or d < min_dist:
            continue  # behind the robot, or already reached
        for o in shifts:
            px, py = lx - o * ly / d, ly + o * lx / d
            if not segment_blocked(points, half_width, (px, py), exclude, exclude_r):
                return px, py
    return None


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
        self.declare_parameter('spin_clear_radius_m', 0.40)  # corners sweep 0.35 m (47 x 52 cm) + 5 cm
        self.declare_parameter('recheck_max_s', 1.0)  # re-check a command on new scans this long (bridge timeout)
        self.declare_parameter('obstacle_target_exclude_m', 0.30)  # returns this close to the target are the target
        # obstacle avoid: when the corridor toward the target is blocked, take the nearest clear arc that
        # keeps the target in view instead of only stopping (blind_corner: someone beside the corner)
        self.declare_parameter('obstacle_avoid', True)
        self.declare_parameter('avoid_min_speed_mps', 0.12)  # an arc slower than this is no better than stopping
        self.declare_parameter('avoid_hold_s', 0.5)          # keep the shift this long once the path is clear
        self.declare_parameter('avoid_delay_s', 1.0)         # go round only what blocks the path this long
        # when nothing beside the target clears the way (a corner, the target at the image edge), follow the
        # target's own path: breadcrumbs of where it walked, kept trail_s, in a dead-reckoned frame
        self.declare_parameter('avoid_trail', True)
        self.declare_parameter('trail_s', 6.0)
        # going round on the trail can turn the target out of the camera's view (blind_corner s2): keep
        # following the crumbs this long without target messages, then stop as before
        self.declare_parameter('trail_hold_s', 3.0)
        # stopped close in front of someone with no way round that keeps the target in view (blind_corner s2 on
        # f01dd98 stood 14 s at 0.68 m from the bystander): back off slowly, the stop checking behind, to make
        # room for a way round; at most avoid_back_s each time the path is blocked
        self.declare_parameter('avoid_back_mps', 0.1)
        self.declare_parameter('avoid_back_s', 3.0)
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
        self.avoid_hold        = float(self.get_parameter('avoid_hold_s').value)
        self.avoid_delay       = float(self.get_parameter('avoid_delay_s').value)
        self.blocked_since     = None   # when the straight path to the target was first seen blocked
        self.avoid_trail       = bool(self.get_parameter('avoid_trail').value)
        self.trail_s           = float(self.get_parameter('trail_s').value)
        self.pose              = [0.0, 0.0, 0.0]  # dead reckoning from the commands sent (no odometry topic)
        self.pose_time         = None
        self.last_angular      = 0.0
        self.crumbs            = []     # (x, y, time) of the target in the dead-reckoned frame, oldest first
        self.trailing          = False  # last [TRAIL] state written to the log
        self.trail_hold        = float(self.get_parameter('trail_hold_s').value)
        self.avoid_back_mps    = float(self.get_parameter('avoid_back_mps').value)
        self.avoid_back_s      = float(self.get_parameter('avoid_back_s').value)
        self.backing           = False  # last [BACK] state written to the log
        self.back_since        = None   # when backing off began in this blocked spell
        self.trail_since_msg   = False  # the trail is driving on its own, without target messages
        self.avoid_offset      = 0.0    # m beside the target the robot aims at to pass an obstacle
        self.avoid_time        = 0.0    # when the current shift was last needed
        self.last_clearance    = math.inf  # corridor clearance of the last command, for the [MOVE] line
        self.moving_cmd        = None   # last command sent while moving, re-checked on every scan
        self.moving_target     = None   # (x, y, time) of the target point that command was checked with
        self.moving_time       = 0.0    # when that command was sent
        self.recheck_max       = float(self.get_parameter('recheck_max_s').value)
        self.spin_clear_r      = float(self.get_parameter('spin_clear_radius_m').value)

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
            # the LiDAR driver publishes best effort; a reliable subscriber would never connect (T18, Codex)
            self.create_subscription(LaserScan, str(self.get_parameter('scan_topic').value), self.cb_scan,
                                     qos_profile_sensor_data)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        if self.target_timeout > 0.0:
            self.stale_timer = self.create_timer(0.05, self.check_stale)
        if self.obstacle_stop and self.obstacle_avoid and self.avoid_trail:
            self.trail_timer = self.create_timer(0.1, self.trail_tick)

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
        self.advance_pose()
        self.recheck_last_cmd()

    def advance_pose(self):
        """Dead-reckon the robot from the bridge's estimated wheel speed and the last turn rate sent."""
        now = self.get_clock().now().nanoseconds / 1e9
        if self.pose_time is not None:
            dt = min(0.5, max(0.0, now - self.pose_time))
            th = self.pose[2] + 0.5 * self.last_angular * dt
            self.pose[0] += self.v_wheels * dt * math.cos(th)
            self.pose[1] += self.v_wheels * dt * math.sin(th)
            self.pose[2] += self.last_angular * dt
        self.pose_time = now
        return now

    def add_crumb(self, target_xy, now):
        """Remember where the target is, in the dead-reckoned frame, every 0.1 m it walks."""
        c, s = math.cos(self.pose[2]), math.sin(self.pose[2])
        wx = self.pose[0] + c * target_xy[0] - s * target_xy[1]
        wy = self.pose[1] + s * target_xy[0] + c * target_xy[1]
        if not self.crumbs or math.hypot(wx - self.crumbs[-1][0], wy - self.crumbs[-1][1]) >= 0.1:
            self.crumbs.append((wx, wy, now))
        self.crumbs = [cr for cr in self.crumbs if now - cr[2] <= self.trail_s]

    def recheck_last_cmd(self):
        """Each scan re-checks the last moving command, turns in place included, against the new returns.
        Target messages can stop (a lost target, a single false box), and the bridge keeps the last command
        until the stale stop and its own ramp; whoever walks into the corridor meanwhile still slows the robot
        (blind_corner run), and whoever comes inside the spin circle stops a turn (T18, Codex 10:43)."""
        cmd = self.moving_cmd
        if cmd is None or (cmd.linear.x == 0.0 and cmd.angular.z == 0.0):
            return
        if self.scan_time - self.moving_time > self.recheck_max:
            # only the window the bridge would still run it (its 1 s timeout): each resend restarts that
            # timeout, so an unbounded re-check would keep the robot creeping after the target is gone (T18)
            self.moving_cmd = None
            return
        tgt = self.moving_target
        target_xy = tgt[:2] if tgt is not None and self.scan_time - tgt[2] <= self.scan_max_age else None
        capped = self.obstacle_limited(cmd.linear.x, target_xy, cmd.angular.z)
        # a moving command stopped by the cap stops turning too; a turn in place keeps its turn for the spin check
        turn = cmd.angular.z if capped != 0.0 or cmd.linear.x == 0.0 else 0.0
        # a lowered resend is a tighter arc, and a turn may have someone new in its circle: both go through the
        # spin check like any other command (T18)
        linear, angular = self.stopped_turn(capped, turn, target_xy)
        if abs(linear) < abs(cmd.linear.x) or angular != cmd.angular.z:
            twist = Twist()
            twist.linear.x, twist.angular.z = linear, angular
            self.send(twist, keep_time=True)
            self.last_linear = linear

    def send(self, twist, target_xy=None, keep_time=False):
        """Publish a command and keep it for the per-scan re-check while it moves the robot. keep_time: a
        re-check's lowered resend, still dated from the command it lowers."""
        self.pub.publish(twist)
        now = self.get_clock().now().nanoseconds / 1e9
        self.last_angular = twist.angular.z
        self.moving_cmd = twist if twist.linear.x != 0.0 or twist.angular.z != 0.0 else None
        if not keep_time:
            self.moving_time = now
        if target_xy is not None:
            self.moving_target = (target_xy[0], target_xy[1], now)

    def obstacle_limited(self, linear_x, target_xy, angular_z=0.0):
        """linear_x capped by the corridor clearance; a stale or missing scan stops forward and reverse motion."""
        if not self.obstacle_stop or linear_x == 0.0:
            return linear_x
        now = self.get_clock().now().nanoseconds / 1e9
        fresh = self.scan_time is not None and 0.0 <= now - self.scan_time <= self.scan_max_age
        direction = 1.0 if linear_x > 0.0 else -1.0
        # a slow start with a turn is a tight arc; past 2/m treat it as straight (a near spin, not a path)
        curvature = angular_z / linear_x if abs(linear_x) > 0.05 and abs(angular_z / linear_x) <= 2.0 else 0.0
        clearance = corridor_clearance(self.scan_xy, self.obstacle_half_w, direction,
                                       target_xy, self.obstacle_excl, curvature) if fresh else 0.0
        cap = obstacle_speed_cap(clearance, self.obstacle_stop_m, self.max_decel, self.latency_s,
                                 abs(self.v_wheels))
        self.last_clearance = clearance
        capped = abs(linear_x) > cap
        if capped != self.obstacle_capped:
            self.get_logger().info(f"[OBST] {'on' if capped else 'off'} clearance={clearance:.2f} m"
                                   + ('' if fresh else ' (no fresh scan)'))
            self.obstacle_capped = capped
        return direction * min(abs(linear_x), cap)

    def turn_allowed(self, target_xy=None):
        """A turn in place is allowed only with a fresh scan and nothing but the target inside the circle the
        robot's corners sweep (spin_clear_radius_m). Without it a stopped robot sends no turn either (T18)."""
        if not self.obstacle_stop:
            return True
        now = self.get_clock().now().nanoseconds / 1e9
        if self.scan_time is None or not 0.0 <= now - self.scan_time <= self.scan_max_age:
            return False
        for x, y in self.scan_xy:
            if target_xy is not None and math.hypot(x - target_xy[0], y - target_xy[1]) <= self.obstacle_excl:
                continue
            if math.hypot(x, y) <= self.spin_clear_r:
                return False
        return True

    def stopped_turn(self, linear_x, angular_z, target_xy):
        """(linear, angular) unchanged, or without the turn for a near spin the spin circle does not allow.

        A near spin is no forward motion, a creep (|v| <= 0.05 m/s) or an arc tighter than 2/m: the corridor
        check treats those as straight, so the body's corners sweeping round are checked here instead (T18
        integration probe: (0.06, -0.8) with a post beside the rear quarter was sent). A refused near spin
        keeps its straight creep, which the corridor did check, so a robot beside someone can still edge
        past them instead of standing for good (pass_by s4).
        """
        near_spin = abs(linear_x) <= 0.05 or abs(angular_z / linear_x) > 2.0
        if angular_z != 0.0 and near_spin and not self.turn_allowed(target_xy):
            return linear_x, 0.0
        return linear_x, angular_z

    def moving_turn(self, linear_x, angular_z, target_xy, target_bearing=None):
        """(linear, angular) for a way round: the wanted turn, or a gentler one (2/3, 1/3, none) if the wanted
        arc is held by the stop and a gentler one still moves; a turn in place only if none does. Spinning
        hard with the robot held turned the target out of the camera's view (pass_by s0 on 4caa707)."""
        tries = [(linear_x, angular_z)]
        if linear_x > self.avoid_min_speed:
            # fast, the same turn is near straight and held like straight; at a crawl it is a real arc that clears
            # (pass_by s2 on a30c90d stood 5 s beside the worker asked for 1.3 m/s)
            tries.append((self.avoid_min_speed, max(-2.0 * self.avoid_min_speed, min(2.0 * self.avoid_min_speed, angular_z))))
        for v0, w0 in tries:
            for f in (1.0, 2.0 / 3.0, 1.0 / 3.0, 0.0):
                v = self.obstacle_limited(v0, target_xy, w0 * f)
                if v > 0.0:
                    return self.stopped_turn(v, w0 * f, target_xy)
        # nothing moves: turn in place towards the way round, slowly, and not so far that the target leaves the
        # camera's view (pass_by s2 on 7ac1cd1 spun at 0.8 rad/s and lost the target). With the target already
        # 20 deg or more off to one side, turn towards it instead (blind_corner s2 on bddf0ba stood still while
        # the target walked out of view round the corner).
        w = max(-0.4, min(0.4, angular_z))
        if target_bearing is not None and abs(target_bearing) >= 0.35:
            w = 0.4 if target_bearing > 0.0 else -0.4
        elif target_bearing is not None and w * target_bearing < 0.0 and abs(target_bearing) >= 0.2:
            w = 0.0
        return self.stopped_turn(0.0, w, target_xy)

    def obstacle_command(self, linear_x, angular_z, target_xy, target_bearing, at_edge=False):
        """(linear, angular) after the obstacle stop. With obstacle_avoid, when something other than the target
        lies on the straight path to the target, aim beside the target by the smallest clear shift (aim_offset)
        and steer by that bearing; the stop still caps the speed. Not at the image edge, where the target's
        bearing is not known."""
        now = self.get_clock().now().nanoseconds / 1e9
        fresh = self.scan_time is not None and 0.0 <= now - self.scan_time <= self.scan_max_age
        offset = 0.0
        found = 0.0
        if self.obstacle_stop and self.obstacle_avoid and fresh and at_edge and (linear_x > 0.0 or angular_z != 0.0):
            # at the image edge the target's bearing is not known well enough to aim beside it; blocked means
            # the follower's own command would be held by the stop
            v_try = max(linear_x, self.avoid_min_speed)
            held = self.obstacle_limited(v_try, target_xy, max(-2.0 * v_try, min(2.0 * v_try, angular_z))) < v_try
            found = None if held or not self.turn_allowed(target_xy) else 0.0
            if found == 0.0:
                self.blocked_since = self.back_since = None
            elif self.blocked_since is None:
                self.blocked_since = now
        if self.obstacle_stop and self.obstacle_avoid and fresh and not at_edge and linear_x > 0.0:
            found = aim_offset(self.scan_xy, self.obstacle_half_w, target_xy, self.obstacle_excl, self.avoid_offset)
            if found == 0.0:
                self.blocked_since = self.back_since = None
            elif self.blocked_since is None:
                self.blocked_since = now
            # someone walking across the path is gone within about a second; going round them turned the
            # target out of the image (twin crossing runs). Only what stays in the way is gone round.
            waited = self.blocked_since is not None and now - self.blocked_since >= self.avoid_delay
            if found and (waited or self.avoid_offset != 0.0):
                offset, self.avoid_time = found, now  # None: no shift clears it; the stop alone applies
            elif found == 0.0 and self.avoid_offset != 0.0 and now - self.avoid_time < self.avoid_hold:
                offset = self.avoid_offset  # just past it: keep the shift a moment so the robot does not clip it
        waited = self.blocked_since is not None and now - self.blocked_since >= self.avoid_delay
        if offset == 0.0 and found is None and waited and self.avoid_trail and fresh:
            aim = trail_aim([cr[:2] for cr in self.crumbs], self.pose, self.scan_xy, self.obstacle_half_w,
                            None if at_edge else target_xy, self.obstacle_excl)
            if aim is not None:
                if not self.trailing:
                    self.get_logger().info(f"[TRAIL] on: follow the target's path to ({aim[0]:.2f}, {aim[1]:.2f}) m")
                    self.trailing = True
                angular_z = bearing_turn(math.atan2(aim[1], aim[0]), 0.0, self.latency_s, self.bearing_gain,
                                         self.angular_limit, self.bearing_deadband)
                linear_x = max(linear_x, self.avoid_min_speed)
                angular_z = max(-2.0 * linear_x, min(2.0 * linear_x, angular_z))
                if not at_edge and angular_z * target_bearing < 0.0 and abs(target_bearing) >= 0.35:
                    # the crumb is one way and the target already 20 deg or more the other: going straight
                    # on along the trail keeps it in the image (blind_corner s0 on a30c90d turned it out)
                    angular_z = 0.0
                return self.moving_turn(linear_x, angular_z, None if at_edge else target_xy,
                                        None if at_edge else target_bearing)
        if self.trailing:
            self.get_logger().info("[TRAIL] off")
            self.trailing = False
        far = target_xy is not None and math.hypot(*target_xy) > self.target_distance + 0.3
        if offset == 0.0 and found is None and waited and fresh and not at_edge and linear_x > 0.0 and far \
                and self.avoid_back_mps > 0.0 \
                and (self.back_since is None or now - self.back_since <= self.avoid_back_s):
            back = self.obstacle_limited(-self.avoid_back_mps, None, 0.0)
            if back < 0.0:
                if self.back_since is None:
                    self.back_since = now  # counted from the first step back, not from the block (s2 on 3a4ac4a)
                if not self.backing:
                    self.get_logger().info("[BACK] on: no way round from here, backing off")
                    self.backing = True
                return back, 0.0
        if self.backing:
            self.get_logger().info("[BACK] off")
            self.backing = False
        if offset != 0.0:
            if offset != self.avoid_offset:
                self.get_logger().info(f"[AVOID] aim {offset:+.2f} m beside the target")
            self.avoid_offset = offset
            d = math.hypot(*target_xy)
            aim = (target_xy[0] - offset * target_xy[1] / d, target_xy[1] + offset * target_xy[0] / d)
            angular_z = bearing_turn(math.atan2(aim[1], aim[0]), 0.0, self.latency_s, self.bearing_gain,
                                     self.angular_limit, self.bearing_deadband)
            # from a near stop too (pass_by s4); the turn is limited to an arc of at least 0.5 m radius, which the
            # corridor checks as the arc it is (slower and sharper, it is a near spin checked as straight; beside
            # the worker both were refused, pass_by s1 on 838598d). The turn is eased, not the speed raised, so
            # the robot never closes on the target faster than the follower asks (T18 integration review).
            linear_x = max(linear_x, self.avoid_min_speed)
            angular_z = max(-2.0 * linear_x, min(2.0 * linear_x, angular_z))
            return self.moving_turn(linear_x, angular_z, target_xy, target_bearing)
        if self.avoid_offset != 0.0:
            self.get_logger().info("[AVOID] off")
            self.avoid_offset = 0.0
        capped = self.obstacle_limited(linear_x, target_xy, angular_z)
        if linear_x > 0.0 and capped == 0.0 and angular_z != 0.0 and not at_edge:
            # the arc towards the target brushes someone it passes; a gentler one, or straight on, may still go
            # (blind_corner s2 on f47c6d7 stood 4 s with the target in view and the straight line clear)
            for f in (2.0 / 3.0, 1.0 / 3.0, 0.0):
                v = self.obstacle_limited(linear_x, target_xy, angular_z * f)
                if v > 0.0:
                    return self.stopped_turn(v, angular_z * f, target_xy)
        return self.stopped_turn(capped, angular_z, target_xy)

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
                held.linear.x, held.angular.z = self.stopped_turn(held.linear.x, self.last_good_cmd.angular.z, None)
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
        crumb_now = self.advance_pose()
        if not (cx <= 0 or cx >= self.image_width - 1):
            self.add_crumb(target_xy, crumb_now)
        linear_x, angular_z = self.obstacle_command(linear_x, angular_z, target_xy, tb,
                                                    at_edge=cx <= 0 or cx >= self.image_width - 1)
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
            + (f" clr={self.last_clearance:.2f}" if self.obstacle_stop and math.isfinite(self.last_clearance) else "")
        )

    # ==================================================
    def trail_tick(self):
        """While the trail is being followed and target messages have stopped (the way round turned the target
        out of view), keep driving along the crumbs for trail_hold_s, every command through the stop; then
        stop. A new target message hands control back to the follower."""
        now = self.get_clock().now().nanoseconds / 1e9
        quiet = self.last_msg_time is not None and now - self.last_msg_time
        if not self.trailing or quiet is None or quiet < 0.25:
            self.trail_since_msg = False
            return
        if quiet > self.trail_hold or self.scan_time is None or not 0.0 <= now - self.scan_time <= self.scan_max_age:
            self.get_logger().info(f"[TRAIL] off: no target message for {quiet:.1f} s")
            self.trailing = self.trail_since_msg = False
            self.publish_stop()
            return
        self.advance_pose()
        aim = trail_aim([cr[:2] for cr in self.crumbs], self.pose, self.scan_xy, self.obstacle_half_w)
        if aim is None:
            self.get_logger().info("[TRAIL] off: no crumb reachable")
            self.trailing = self.trail_since_msg = False
            self.publish_stop()
            return
        if not self.trail_since_msg:
            self.get_logger().info("[TRAIL] driving on the crumbs without target messages")
            self.trail_since_msg = True
        angular_z = bearing_turn(math.atan2(aim[1], aim[0]), 0.0, self.latency_s, self.bearing_gain,
                                 self.angular_limit, self.bearing_deadband)
        linear_x = self.avoid_min_speed
        angular_z = max(-2.0 * linear_x, min(2.0 * linear_x, angular_z))
        # where the target was last seen: the newest crumb. Do not turn away from it once it is 20 deg or more
        # the other way (blind_corner s2 on 1b5dc92 turned right to the crumbs as the target went left)
        cx, cy = self.crumbs[-1][0] - self.pose[0], self.crumbs[-1][1] - self.pose[1]
        last = math.atan2(-math.sin(self.pose[2]) * cx + math.cos(self.pose[2]) * cy,
                          math.cos(self.pose[2]) * cx + math.sin(self.pose[2]) * cy)
        if angular_z * last < 0.0 and abs(last) >= 0.35:
            angular_z = 0.0
        linear_x, angular_z = self.moving_turn(linear_x, angular_z, None)
        twist = Twist()
        twist.linear.x, twist.angular.z = linear_x, angular_z
        self.send(twist)
        self.last_linear = linear_x

    def check_stale(self):
        """Stop once target messages have stopped; the next message resumes control."""
        if self.trailing and self.trail_since_msg:
            return  # the trail is driving; trail_tick stops it after trail_hold_s
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
        self.last_angular = 0.0


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
