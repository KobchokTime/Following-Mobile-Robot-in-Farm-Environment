extends Node3D

const SAVE_PATH := "user://thesis_quest_save.json"
const GRIB_CELL_SIZE := 1.5
const GRIB_COLUMNS := 18
const GRIB_ROWS := 12
const GRIB_ORIGIN := Vector2(-13.5, -9.0)
const FOLLOW_STOP_DISTANCE_M := 0.70
const FOLLOW_DISTANCE_M := 1.20
const FOLLOW_STALE_TIMEOUT_S := 0.30
const FOLLOW_MIN_CONFIDENCE := 0.70
const FOLLOW_MAX_LINEAR_MPS := 0.15
const FOLLOW_MAX_DISTANCE_M := 2.0
const FOLLOW_CATCHUP_MAX_LINEAR_MPS := 1.75
const FOLLOW_MAX_ANGULAR_RADPS := 0.40
const FOLLOW_LINEAR_GAIN := 0.35
const FOLLOW_ANGULAR_GAIN := 0.60
const FOLLOW_SIMULATION_SPEED_SCALE := 8.0
const FOLLOW_SIMULATION_TURN_SCALE := 10.0
const PLAYER_COLLISION_RADIUS_M := 0.32
const INTERACTION_RADIUS_M := 2.0
const ROBOT_SWEEP_RADIUS_M := 0.83
const GRID_PATH_REPLAN_COOLDOWN_S := 0.20
const FOLLOW_GRID_ALIGNMENT_TOLERANCE_DEG := 12.0
const FOLLOW_WAYPOINT_TOLERANCE_M := 0.30
const FOLLOW_MIN_WAYPOINT_SPEED_MPS := 0.05
const REID_ENABLED := false
const GRID_FALLBACK_ENABLED := false
const CAMERA_FOV_DEG := 70.0
const CAMERA_MIN_RANGE_M := 0.25
const CAMERA_MAX_RANGE_M := 5.0
const CAMERA_IDEAL_RANGE_M := 2.0
const CAMERA_REID_NOISE := 0.05
const FORCED_TARGET_LOSS_MS := 900
const LIDAR_MAX_RANGE_M := 6.0
const LIDAR_RAY_COUNT := 72
const LIDAR_SCAN_PERIOD_S := 0.125
const LIDAR_STOP_FOV_DEG := 70.0
const LIDAR_STOP_DISTANCE_M := 0.55
const FOLLOW_LOG_PATH := "res://../follow_log.csv"
const FOLLOW_LOG_SAMPLE_PERIOD_S := 0.15
const FOLLOW_LOG_HEADER := "ts_ms,event,state,robot_x,robot_z,heading_deg,target_heading_deg,angular_radps,linear_mps,player_x,player_z,waypoint_idx,waypoint_count,note"
const CAMERA_TRACK_GAIN := 1.0
const CAMERA_TRACK_MAX_RADPS := 0.8
const CAMERA_TRACK_DEADZONE_DEG := 2.0
const LIDAR_FIX_SCORE_THRESHOLD := 12.0
const LIDAR_FIX_SCORE_HIT := 1.0
const LIDAR_FIX_SCORE_DECAY_PER_S := 0.5
const FOLLOW_MODE_SWITCH_LOCK_S := 0.35
const FOLLOW_CORNER_CONFIRM_TIMEOUT_S := 1.2

var player: CharacterBody3D
var robot_root: CharacterBody3D
var camera: Camera3D
var world_root: Node3D
var office_root: Node3D
var field_root: Node3D
var prediction_path_root: Node3D
var ui: CanvasLayer
var hud_label: Label
var robot_speed_label: Label
var hint_label: Label
var choice_row: HBoxContainer
var speed_panel: PanelContainer
var robot_panel: PanelContainer
var robot_panel_box: VBoxContainer
var robot_panel_follow_button: Button
var robot_pov_wrap: Control
var robot_pov_viewport: SubViewport
var robot_pov_camera: Camera3D
var robot_pov_reticle: Panel
var robot_pov_reticle_style: StyleBoxFlat
var robot_pov_status_label: Label
var robot_pov_label_bg: ColorRect
var robot_pov_label_text: Label
var walk_speed_input: SpinBox
var sprint_speed_input: SpinBox
var dialog_panel: PanelContainer
var dialog_label: Label
var quest_panel: PanelContainer
var quest_text: RichTextLabel
var current_scene_name := "office"
var active_station: Dictionary = {}
var quests: Array = []
var save_data: Dictionary = {}
var total_xp := 0
var walk_speed_mps := 5.2
var sprint_speed_mps := 7.5
var walk_phase := 0.0
var is_moving := false
var follow_active := false
var follow_state := "STOPPED"
var follow_control_mode := "GRID"
var follow_mode_lock_timer := 0.0
var follow_corner_confirm_timer := 0.0
var follow_target_available := true
var follow_target_confidence := 1.0
var follow_last_observation_msec := 0
var follow_linear_proposal_mps := 0.0
var follow_angular_proposal_radps := 0.0
var grib_boundary_blocked: Dictionary = {}
var grib_route_cells: Dictionary = {}
var grib_learned_blocked: Dictionary = {}
var grib_fix_score: Dictionary = {}
var lidar_move_points: Array[Vector3] = []
var grib_map_markers_root: Node3D
var lidar_move_points_root: Node3D
var follow_grid_path: Array[Vector2i] = []
var follow_path_index := 0
var follow_replan_timer := 0.0
var follow_planned_target_cell := Vector2i(-99, -99)
var follow_has_grid_path := false
var follow_needs_replan := false
var forced_target_loss_until_msec := 0
var camera_target_visible := false
var camera_last_confidence := 0.0
var camera_last_reason := "IDLE"
var camera_last_distance_m := 0.0
var camera_last_bearing_deg := 0.0
var camera_last_signed_bearing_rad := 0.0
var camera_last_frame_offset := 0.0
var camera_yaw := 0.0
var camera_fov_root: Node3D
var camera_fov_left: MeshInstance3D
var camera_fov_right: MeshInstance3D
var lidar_scan_root: Node3D
var lidar_scan_timer := 0.0
var lidar_min_forward_distance_m := INF
var follow_log_file: FileAccess
var follow_log_last_state := ""
var follow_log_sample_timer := 0.0

const PALETTE := {
	"wall": Color("34384a"), "wall_trim": Color("b7a07b"), "floor": Color("4c8078"),
	"tile": Color("5a9187"), "desk": Color("a95d3c"), "wood": Color("744a39"),
	"metal": Color("707f89"), "screen": Color("82c8bd"), "plant": Color("43805a"),
	"navy": Color("192342"), "gold": Color("f0cb6c"), "robot": Color("d8dfd2"),
	"field": Color("86aa5d"), "track": Color("bda16e"), "sky": Color("91cfe0")
}

func _ready() -> void:
	_read_project_data()
	_load_save()
	_open_follow_log()
	_build_world()
	_build_player()
	_build_ui()
	set_scene(String(save_data.get("scene", "office")), true)
	_update_hud()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

func _process(delta: float) -> void:
	if not is_instance_valid(player):
		return
	var target := player.global_position + Vector3(0, 10.5, 12.0)
	camera.global_position = camera.global_position.lerp(target, min(delta * 4.5, 1.0))
	camera.look_at(player.global_position + Vector3(0, 0.8, 0), Vector3.UP)
	if is_moving:
		walk_phase += delta * 11.0
		var model: Node3D = player.get_node("Model")
		model.position.y = 0.06 + absf(sin(walk_phase)) * 0.07
	else:
		player.get_node("Model").position.y = lerpf(player.get_node("Model").position.y, 0.06, delta * 8.0)

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player):
		return
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := Vector3(input.x, 0.0, input.y)
	is_moving = direction.length_squared() > 0.01
	if is_moving:
		direction = direction.normalized()
		var player_speed := 1.2 if follow_active else walk_speed_mps
		if Input.is_action_pressed("sprint"):
			player_speed = sprint_speed_mps
		player.velocity.x = direction.x * player_speed
		player.velocity.z = direction.z * player_speed
		player.get_node("Model").rotation.y = atan2(direction.x, direction.z)
	else:
		player.velocity.x = move_toward(player.velocity.x, 0.0, 24.0 * delta)
		player.velocity.z = move_toward(player.velocity.z, 0.0, 24.0 * delta)
	player.velocity.y -= 24.0 * delta
	player.move_and_slide()
	var x_limit := 13.475-PLAYER_COLLISION_RADIUS_M-0.05
	var z_min := -9.475+PLAYER_COLLISION_RADIUS_M+0.05
	var z_max := 9.65
	if current_scene_name == "field":
		x_limit = 13.38-PLAYER_COLLISION_RADIUS_M-0.05
		z_min = -9.13+PLAYER_COLLISION_RADIUS_M+0.05
		z_max = 9.13-PLAYER_COLLISION_RADIUS_M-0.05
	player.global_position.x = clampf(player.global_position.x,-x_limit,x_limit)
	player.global_position.z = clampf(player.global_position.z,z_min,z_max)
	_keep_player_outside_robot()
	_update_lidar_scan(delta)
	_update_camera_detection()
	_update_camera_tracking(delta)
	_update_nearby()
	_update_robot_follow(delta)
	_log_follow_sample(delta)
	_update_robot_speed_hud()
	_update_follow_hint()
	_render_camera_fov()
	_update_robot_pov()

func _keep_player_outside_robot() -> void:
	# The robot stays on a separate collision layer so it never physically blocks the player
	# while it is maneuvering (see _set_scene_collisions), but the player still shouldn't be
	# able to walk through its body, so push the player back out of its footprint directly.
	if not is_instance_valid(robot_root) or current_scene_name != "field":
		return
	var min_separation := PLAYER_COLLISION_RADIUS_M+ROBOT_SWEEP_RADIUS_M
	var from_robot := Vector2(player.global_position.x-robot_root.global_position.x,player.global_position.z-robot_root.global_position.z)
	var separation := from_robot.length()
	if separation >= min_separation:
		return
	var push_dir := from_robot/separation if separation > 0.001 else Vector2(0.0,1.0)
	player.global_position.x = robot_root.global_position.x+push_dir.x*min_separation
	player.global_position.z = robot_root.global_position.z+push_dir.y*min_separation

func _update_robot_speed_hud() -> void:
	if not is_instance_valid(robot_root) or not is_instance_valid(robot_speed_label):
		return
	var simulated_speed := Vector2(robot_root.velocity.x, robot_root.velocity.z).length()
	var lidar_text := "%.2fm" % lidar_min_forward_distance_m if lidar_min_forward_distance_m < LIDAR_MAX_RANGE_M else ">%.0fm" % LIDAR_MAX_RANGE_M
	var cam_text := "person %.2f (%s)" % [camera_last_confidence, _frame_side_text()] if camera_target_visible else "%s (brg %.0f°/%.0f°, %.1fm)" % [camera_last_reason, camera_last_bearing_deg, CAMERA_FOV_DEG*0.5, camera_last_distance_m]
	var mode_text := follow_control_mode if follow_active else "-"
	robot_speed_label.text = "PLAYER %.1f/%.1f m/s  |  FARM %.2f sim / %.3f ctrl  |  %s (%s)  |  CAM-YOLO %s  |  LIDAR %s  |  FIX %d / MOVE %d" % [walk_speed_mps, sprint_speed_mps, simulated_speed, follow_linear_proposal_mps, follow_state, mode_text, cam_text, lidar_text, grib_learned_blocked.size(), lidar_move_points.size()]

func _render_prediction_path() -> void:
	if not is_instance_valid(prediction_path_root):
		return
	for child in prediction_path_root.get_children():
		child.queue_free()
	prediction_path_root.visible = follow_active and follow_state != "TOO_CLOSE" and current_scene_name == "field" and follow_has_grid_path and follow_path_index < follow_grid_path.size()
	if not prediction_path_root.visible:
		return
	var line_material := StandardMaterial3D.new()
	line_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	line_material.albedo_color = Color("3ce4d1")
	line_material.emission_enabled = true
	line_material.emission = Color("20a99d")
	var marker_material := StandardMaterial3D.new()
	marker_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_material.albedo_color = Color("c7fff1")
	marker_material.emission_enabled = true
	marker_material.emission = Color("5de8c9")
	var goal_material := StandardMaterial3D.new()
	goal_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	goal_material.albedo_color = Color("ffe08a")
	goal_material.emission_enabled = true
	goal_material.emission = Color("ffbb42")
	var previous := robot_root.global_position
	for index in range(follow_path_index,follow_grid_path.size()):
		var point := _grib_cell(follow_grid_path[index].x,follow_grid_path[index].y)
		_add_forecast_segment(previous,point,line_material)
		_add_forecast_marker(point,goal_material if index == follow_grid_path.size()-1 else marker_material,index == follow_grid_path.size()-1)
		previous = point

func _add_forecast_segment(from: Vector3, to: Vector3, material: Material) -> void:
	var segment := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	var delta := to-from
	mesh.size = Vector3(0.13,0.035,delta.length())
	segment.mesh = mesh
	segment.material_override = material
	segment.position = (from+to)*0.5+Vector3(0,0.15,0)
	segment.rotation.y = atan2(delta.x,delta.z)
	prediction_path_root.add_child(segment)

func _add_forecast_marker(point: Vector3, material: Material, is_goal: bool) -> void:
	var marker := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 0.27 if is_goal else 0.15
	mesh.bottom_radius = mesh.top_radius
	mesh.height = 0.045
	marker.mesh = mesh
	marker.material_override = material
	marker.position = point+Vector3(0,0.13,0)
	prediction_path_root.add_child(marker)

func _open_follow_log() -> void:
	# Plain text file next to the project (not Godot's user:// AppData folder, which this
	# environment has had write-permission trouble with) so it can be read directly from disk
	# to diagnose follow behavior (e.g. unexpected spins) after the fact.
	var path := ProjectSettings.globalize_path(FOLLOW_LOG_PATH)
	var existed := FileAccess.file_exists(path)
	follow_log_file = FileAccess.open(path, FileAccess.READ_WRITE if existed else FileAccess.WRITE)
	if follow_log_file == null:
		return
	if existed:
		follow_log_file.seek_end()
	else:
		follow_log_file.store_line(FOLLOW_LOG_HEADER)
	follow_log_file.store_line("# session_start %s" % Time.get_datetime_string_from_system())
	follow_log_file.flush()

func _log_follow_row(event: String, target_heading_deg: float, note: String) -> void:
	if follow_log_file == null or not is_instance_valid(robot_root):
		return
	var player_pos := player.global_position if is_instance_valid(player) else Vector3.ZERO
	follow_log_file.store_line("%d,%s,%s,%.3f,%.3f,%.2f,%.2f,%.3f,%.3f,%.3f,%.3f,%d,%d,%s" % [
		Time.get_ticks_msec(), event, follow_state,
		robot_root.global_position.x, robot_root.global_position.z, rad_to_deg(robot_root.rotation.y),
		target_heading_deg, follow_angular_proposal_radps, follow_linear_proposal_mps,
		player_pos.x, player_pos.z,
		follow_path_index, follow_grid_path.size(), note
	])
	follow_log_file.flush()

func _log_follow_sample(delta: float) -> void:
	if follow_log_file == null or not is_instance_valid(robot_root):
		return
	follow_log_sample_timer -= delta
	if not follow_active or follow_log_sample_timer > 0.0:
		return
	follow_log_sample_timer = FOLLOW_LOG_SAMPLE_PERIOD_S
	var target_heading_deg := 0.0
	if follow_control_mode == "CAMERA":
		target_heading_deg = rad_to_deg(robot_root.rotation.y+camera_last_signed_bearing_rad)
	elif not follow_grid_path.is_empty() and follow_path_index < follow_grid_path.size():
		var waypoint := _grib_cell(follow_grid_path[follow_path_index].x,follow_grid_path[follow_path_index].y)
		var to_waypoint := waypoint-robot_root.global_position
		target_heading_deg = rad_to_deg(atan2(to_waypoint.x,to_waypoint.z))
	_log_follow_row("SAMPLE",target_heading_deg,"mode=%s" % follow_control_mode)

func _update_robot_follow(delta: float) -> void:
	if not is_instance_valid(robot_root):
		return
	if not follow_active:
		robot_root.velocity = Vector3.ZERO
		return
	if not is_instance_valid(player):
		return
	var observation_age_s := float(Time.get_ticks_msec()-follow_last_observation_msec)/1000.0
	if REID_ENABLED and (not follow_target_available or follow_target_confidence < FOLLOW_MIN_CONFIDENCE or observation_age_s >= FOLLOW_STALE_TIMEOUT_S):
		follow_active = false
		follow_state = "LOST"
		follow_linear_proposal_mps = 0.0
		follow_angular_proposal_radps = 0.0
		robot_root.velocity = Vector3.ZERO
		_render_prediction_path()
		return
	var to_player := player.global_position-robot_root.global_position
	to_player.y = 0.0
	var distance_m := to_player.length()
	if distance_m <= FOLLOW_STOP_DISTANCE_M:
		follow_linear_proposal_mps = 0.0
		follow_angular_proposal_radps = 0.0
		robot_root.velocity = Vector3.ZERO
		follow_state = "TOO_CLOSE"
		_render_prediction_path()
		return
	# Camera has priority over the GRID prediction path: steer directly by the actual camera/YOLO
	# bearing (classic vision-based pursuit) whenever it has a lock AND the straight line to the
	# target isn't known to cut through an obstacle. If the camera CAN see the target but the
	# direct line is blocked (typically right at an obstacle corner — the camera's thin raycast
	# can see past it while the robot's body footprint can't drive through that cell), don't
	# immediately commit to a full GRID detour around the whole obstacle: stop and turn in place
	# to directly face the camera-observed bearing first (CORNER mode) to reconfirm exactly where
	# the target is, the way a real robot would pause and look rather than blindly route-plan.
	# Only fall back to the full GRID A* route if that doesn't resolve within
	# FOLLOW_CORNER_CONFIRM_TIMEOUT_S (a real wall, not just a viewing-angle issue). If the camera
	# can't see the target at all, go straight to GRID (there's no bearing to confirm toward).
	# GRID_FALLBACK_ENABLED is off for now (disabled at the user's request while the LiDAR
	# fix-point/move-point approach below is explored as its replacement) — same on/off pattern
	# as REID_ENABLED elsewhere in this file. The GRID branch and its functions are left intact,
	# just unreachable, so it can be flipped back on later.
	var direct_clear := _is_direct_path_clear(robot_root.global_position,player.global_position)
	var desired_mode: String
	if camera_target_visible and direct_clear:
		desired_mode = "CAMERA"
	elif camera_target_visible and follow_corner_confirm_timer < FOLLOW_CORNER_CONFIRM_TIMEOUT_S:
		desired_mode = "CORNER"
	elif GRID_FALLBACK_ENABLED:
		desired_mode = "GRID"
	else:
		desired_mode = "HOLD"
	if desired_mode == "CORNER":
		follow_corner_confirm_timer += delta
	else:
		follow_corner_confirm_timer = 0.0
	# A hysteresis lock on the mode switch itself (not just the raw per-frame check above) is
	# required: near a borderline spot the clearance check can flip true/false between
	# consecutive frames (the number of direct-path sample steps shifts slightly with distance),
	# and without the lock the controller would alternate target headings every other frame —
	# which reads as the robot spinning erratically in place instead of completing either turn.
	follow_mode_lock_timer = maxf(0.0,follow_mode_lock_timer-delta)
	if desired_mode != follow_control_mode and follow_mode_lock_timer <= 0.0:
		follow_control_mode = desired_mode
		follow_mode_lock_timer = FOLLOW_MODE_SWITCH_LOCK_S
	var target_heading: float
	var waypoint_error_m: float
	if follow_control_mode == "CAMERA" or follow_control_mode == "CORNER":
		target_heading = robot_root.rotation.y+camera_last_signed_bearing_rad
		waypoint_error_m = 0.0 if follow_control_mode == "CORNER" else maxf(0.0,camera_last_distance_m-FOLLOW_DISTANCE_M)
	elif follow_control_mode == "HOLD":
		# No GRID fallback right now and the camera can't directly confirm the target. If LiDAR
		# currently has any "move point" (a hit that hasn't proven stationary long enough to be
		# map — see _update_lidar_point_classification, most likely the target walking around),
		# turn toward the nearest one as a rough sensor-only guess. This never drives forward —
		# there's no distance/identity confidence in a raw LiDAR blob, only a bearing guess.
		target_heading = robot_root.rotation.y
		waypoint_error_m = 0.0
		if not lidar_move_points.is_empty():
			var nearest_point: Vector3 = lidar_move_points[0]
			var nearest_distance := robot_root.global_position.distance_to(nearest_point)
			for point in lidar_move_points:
				var point_distance := robot_root.global_position.distance_to(point)
				if point_distance < nearest_distance:
					nearest_distance = point_distance
					nearest_point = point
			var to_point := nearest_point-robot_root.global_position
			target_heading = atan2(to_point.x,to_point.z)
	else:
		follow_replan_timer = maxf(0.0,follow_replan_timer-delta)
		var target_cell := _world_to_grib_cell(player.global_position)
		if target_cell != follow_planned_target_cell:
			follow_needs_replan = true
		if follow_needs_replan and follow_replan_timer <= 0.0:
			_plan_follow_grid_path()
			follow_replan_timer = GRID_PATH_REPLAN_COOLDOWN_S
			_render_prediction_path()
		if follow_grid_path.is_empty() or follow_path_index >= follow_grid_path.size():
			follow_linear_proposal_mps = 0.0
			follow_angular_proposal_radps = 0.0
			robot_root.velocity = Vector3.ZERO
			follow_state = "NO_PATH" if not follow_has_grid_path else "LOCKED"
			return
		var waypoint := _grib_cell(follow_grid_path[follow_path_index].x, follow_grid_path[follow_path_index].y)
		var to_waypoint := waypoint-robot_root.global_position
		to_waypoint.y = 0.0
		if to_waypoint.length() <= FOLLOW_WAYPOINT_TOLERANCE_M:
			follow_path_index += 1
			if follow_path_index >= follow_grid_path.size():
				follow_linear_proposal_mps = 0.0
				follow_angular_proposal_radps = 0.0
				robot_root.velocity = Vector3.ZERO
				follow_state = "LOCKED"
				_render_prediction_path()
				return
			_render_prediction_path()
			waypoint = _grib_cell(follow_grid_path[follow_path_index].x, follow_grid_path[follow_path_index].y)
			to_waypoint = waypoint-robot_root.global_position
			to_waypoint.y = 0.0
			_log_follow_row("WAYPOINT_ADVANCE",rad_to_deg(atan2(to_waypoint.x,to_waypoint.z)),"idx=%d" % follow_path_index)
		target_heading = atan2(to_waypoint.x,to_waypoint.z)
		waypoint_error_m = maxf(0.0,to_waypoint.length()-FOLLOW_WAYPOINT_TOLERANCE_M)
	var bearing_rad := angle_difference(robot_root.rotation.y,target_heading)
	follow_angular_proposal_radps = clampf(FOLLOW_ANGULAR_GAIN*bearing_rad,-FOLLOW_MAX_ANGULAR_RADPS,FOLLOW_MAX_ANGULAR_RADPS)
	if follow_control_mode == "CORNER":
		# Stopped on purpose: turn to reconfirm the camera bearing, don't drive, until either the
		# direct line clears (back to CAMERA) or the confirm timeout elapses (fall back to GRID).
		follow_linear_proposal_mps = 0.0
		follow_state = "CONFIRMING"
	elif follow_control_mode == "HOLD":
		follow_linear_proposal_mps = 0.0
		follow_state = "HOLDING"
	else:
		# Feed-forward the target's own current speed (as a fraction of their own walk/sprint
		# range, not an absolute m/s match — the player can move far faster than this research-
		# scale proposal was ever meant to) on top of the distance-error term, so the robot
		# proactively speeds up to keep pace with a sprinting target and slows as they slow,
		# instead of only ever reacting after it has already fallen behind.
		var target_speed_mps := Vector2(player.velocity.x,player.velocity.z).length()
		var target_speed_ratio := clampf(target_speed_mps/sprint_speed_mps,0.0,1.0)
		var speed_feedforward_mps := target_speed_ratio*FOLLOW_MAX_LINEAR_MPS*0.6
		# The distance-error term above already scales up correctly as the gap grows — the thing
		# that was stopping the robot from ever closing a growing gap was this cap, fixed at the
		# gentle research-accurate pace regardless of how urgent catching up had become. Past
		# FOLLOW_MAX_DISTANCE_M, relax the cap so the robot can actually keep the gap bounded
		# instead of falling further behind a target moving faster than the normal pace allows.
		var catching_up := distance_m > FOLLOW_MAX_DISTANCE_M
		var linear_cap_mps := FOLLOW_CATCHUP_MAX_LINEAR_MPS if catching_up else FOLLOW_MAX_LINEAR_MPS
		follow_linear_proposal_mps = clampf(FOLLOW_LINEAR_GAIN*waypoint_error_m+speed_feedforward_mps,0.0,linear_cap_mps)
		if waypoint_error_m > 0.0 and follow_control_mode == "GRID":
			follow_linear_proposal_mps = maxf(follow_linear_proposal_mps,FOLLOW_MIN_WAYPOINT_SPEED_MPS)
		if absf(bearing_rad) > deg_to_rad(FOLLOW_GRID_ALIGNMENT_TOLERANCE_DEG):
			follow_linear_proposal_mps = 0.0
			follow_state = "ALIGNING"
		elif follow_linear_proposal_mps > 0.0 and catching_up:
			follow_state = "CATCHING_UP"
		else:
			follow_state = "MOVING" if follow_linear_proposal_mps > 0.0 else "LOCKED"
		if follow_linear_proposal_mps > 0.0 and lidar_min_forward_distance_m < LIDAR_STOP_DISTANCE_M:
			follow_linear_proposal_mps = 0.0
			follow_state = "LIDAR_OBSTACLE"
	# Scale only the on-screen simulation so the research-limited proposal is visible in the game.
	# Turning uses its own scale (not FOLLOW_SIMULATION_SPEED_SCALE, which also drives linear
	# speed) so it can be tuned independently without touching driving speed.
	var simulated_turn_rate := FOLLOW_MAX_ANGULAR_RADPS*FOLLOW_SIMULATION_TURN_SCALE
	robot_root.rotation.y = rotate_toward(robot_root.rotation.y,target_heading,simulated_turn_rate*delta)
	var robot_forward := Vector3(sin(robot_root.rotation.y),0.0,cos(robot_root.rotation.y))
	robot_root.velocity = robot_forward*follow_linear_proposal_mps*FOLLOW_SIMULATION_SPEED_SCALE
	robot_root.move_and_slide()
	if robot_root.get_slide_collision_count() > 0:
		follow_linear_proposal_mps = 0.0
		robot_root.velocity = Vector3.ZERO
		follow_state = "OBSTACLE_STOP"
		follow_grid_path.clear()
		follow_path_index = 0
		follow_replan_timer = GRID_PATH_REPLAN_COOLDOWN_S
		follow_has_grid_path = false
		follow_needs_replan = true
		_render_prediction_path()
	elif follow_linear_proposal_mps > 0.0:
		follow_state = "MOVING"

func _update_follow_hint() -> void:
	if follow_state != follow_log_last_state:
		_log_follow_row("STATE_CHANGE",0.0,"from=%s to=%s" % [follow_log_last_state,follow_state])
		follow_log_last_state = follow_state
	if is_instance_valid(robot_panel) and robot_panel.visible and is_instance_valid(robot_panel_follow_button):
		robot_panel_follow_button.text = "หยุด Follow" if follow_active else "เริ่ม Follow ฉัน"
	if follow_state == "NO_PATH":
		hint_label.text = "NO GRID PATH  ·  ROBOT STOPPED"
	elif follow_state == "OBSTACLE_STOP":
		hint_label.text = "OBSTACLE  ·  ROBOT STOPPED  ·  replanning on GRIB grid"
	elif follow_active and follow_state == "LIDAR_OBSTACLE":
		hint_label.text = "LIDAR OBSTACLE AHEAD (%.2f m)  ·  ROBOT HOLDING" % lidar_min_forward_distance_m
	elif follow_active and follow_state == "TOO_CLOSE":
		hint_label.text = "TARGET INSIDE 0.7 m STOP ZONE  ·  ROBOT HOLDING"
	elif follow_active and follow_state == "HOLDING":
		var hold_note := "tracking nearest LiDAR move point" if not lidar_move_points.is_empty() else "no LiDAR move point nearby"
		hint_label.text = "NO CAMERA LOCK  ·  GRID DISABLED  ·  HOLDING  ·  %s" % hold_note
	elif follow_active and follow_state == "CONFIRMING":
		hint_label.text = "CORNER AHEAD  ·  STOPPED, TURNING TO CONFIRM TARGET BEARING  ·  %.1fs" % follow_corner_confirm_timer
	elif follow_active and follow_state == "ALIGNING":
		var turn_target := "CAMERA BEARING" if follow_control_mode == "CAMERA" else "GRID WAYPOINT"
		hint_label.text = "TURNING TO %s  ·  %.2f rad/s" % [turn_target,follow_angular_proposal_radps]
	elif follow_active:
		var distance_m := Vector2(player.global_position.x-robot_root.global_position.x,player.global_position.z-robot_root.global_position.z).length()
		var remaining_waypoints := maxi(0,follow_grid_path.size()-follow_path_index)
		var cam_text := "YOLO person %.2f (%s)" % [camera_last_confidence,_frame_side_text()] if camera_target_visible else "YOLO NO DETECTION"
		var catchup_note := "  ·  CATCHING UP (>%.0fm)" % FOLLOW_MAX_DISTANCE_M if follow_state == "CATCHING_UP" else ""
		if follow_control_mode == "CAMERA":
			hint_label.text = "CAMERA FOLLOW (priority)  ·  %.1f m  ·  %s%s  ·  E = STOP" % [distance_m,cam_text,catchup_note]
		else:
			hint_label.text = "GRID FOLLOW (fallback, no camera lock)  ·  %d WAYPOINTS  ·  %.1f m  ·  %s%s  ·  E = STOP" % [remaining_waypoints,distance_m,cam_text,catchup_note]
	elif follow_state == "LOST":
		hint_label.text = "TARGET LOST  ·  ROBOT STOPPED  ·  กด E ที่ไหนก็ได้ใน Test Field เพื่อเลือกใหม่"
	elif follow_state == "STOPPED":
		hint_label.text = "FOLLOW STOPPED  ·  กด E ที่ไหนก็ได้ใน Test Field เพื่อเริ่มใหม่"

func _toggle_follow() -> void:
	if follow_active:
		_stop_follow()
	else:
		_start_follow()

func _start_follow() -> void:
	if not is_instance_valid(player) or not is_instance_valid(robot_root):
		return
	follow_target_available = true
	follow_target_confidence = 1.0
	follow_last_observation_msec = Time.get_ticks_msec()
	forced_target_loss_until_msec = 0
	follow_active = true
	follow_state = "LOCKED"
	follow_grid_path.clear()
	follow_path_index = 0
	follow_replan_timer = 0.0
	follow_planned_target_cell = Vector2i(-99, -99)
	follow_has_grid_path = false
	follow_needs_replan = true
	follow_mode_lock_timer = 0.0
	follow_corner_confirm_timer = 0.0
	_render_prediction_path()
	_log_follow_row("START",rad_to_deg(robot_root.rotation.y),"")
	if String(active_station.get("kind","")) == "run":
		_show_choices()

func _stop_follow() -> void:
	_log_follow_row("STOP",0.0,"")
	follow_active = false
	follow_state = "STOPPED"
	follow_linear_proposal_mps = 0.0
	follow_angular_proposal_radps = 0.0
	follow_grid_path.clear()
	follow_path_index = 0
	follow_has_grid_path = false
	follow_needs_replan = false
	if is_instance_valid(robot_root):
		robot_root.velocity = Vector3.ZERO
	_render_prediction_path()
	if String(active_station.get("kind","")) == "run":
		_show_choices()

func _simulate_follow_target_loss() -> void:
	if not follow_active:
		_start_follow()
	forced_target_loss_until_msec = Time.get_ticks_msec() + FORCED_TARGET_LOSS_MS
	follow_target_available = false
	follow_target_confidence = 0.0
	camera_target_visible = false
	camera_last_confidence = 0.0
	_update_robot_follow(0.0)
	_update_follow_hint()

func _update_camera_detection() -> void:
	# Fixed-mount webcam: the sensor does NOT pan independently of the chassis (unlike a
	# pan-tilt turret), so its heading is simply the chassis heading. re-id/identity gating
	# is disabled for now (REID_ENABLED = false) — this only simulates what a plain camera +
	# YOLO-style person detector would see each frame, it does not drive Follow.
	camera_target_visible = false
	camera_last_confidence = 0.0
	camera_last_reason = "NO ROBOT/TARGET"
	if not is_instance_valid(robot_root) or not is_instance_valid(player) or current_scene_name != "field":
		return
	camera_yaw = robot_root.rotation.y
	if REID_ENABLED and follow_active and Time.get_ticks_msec() < forced_target_loss_until_msec:
		camera_last_reason = "SIMULATED DROPOUT"
		return
	var camera_pos := robot_root.global_position+Vector3(0,1.0,0.1)
	var target_pos := player.global_position+Vector3(0,0.9,0)
	var to_player := target_pos-camera_pos
	var planar_to_player := Vector3(to_player.x,0.0,to_player.z)
	var distance_m := planar_to_player.length()
	var bearing_to_player := atan2(planar_to_player.x,planar_to_player.z)
	# Signed angle to add to the chassis heading to face the player directly. The camera's
	# on-screen "right" is world -X when heading=0 (see _update_robot_pov's basis.x derivation
	# after the +PI lens correction), which is the opposite sign convention from this bearing,
	# so frame_offset (positive = person exits right of frame, YOLO/image-coordinate style) is
	# the negated, FOV-normalized version of it.
	var signed_bearing_rad := angle_difference(robot_root.rotation.y,bearing_to_player)
	var bearing_error := absf(signed_bearing_rad)
	camera_last_distance_m = distance_m
	camera_last_bearing_deg = rad_to_deg(bearing_error)
	camera_last_signed_bearing_rad = signed_bearing_rad
	camera_last_frame_offset = clampf(-signed_bearing_rad/deg_to_rad(CAMERA_FOV_DEG*0.5),-1.0,1.0)
	if distance_m < CAMERA_MIN_RANGE_M or distance_m > CAMERA_MAX_RANGE_M:
		camera_last_reason = "OUT OF RANGE"
		return
	if bearing_error > deg_to_rad(CAMERA_FOV_DEG*0.5):
		camera_last_reason = "OUT OF FOV"
		return
	var space_state := get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(camera_pos,target_pos)
	query.collision_mask = 1
	var hit := space_state.intersect_ray(query)
	if hit and hit.collider != player:
		camera_last_reason = "OCCLUDED"
		return
	var range_factor := 1.0
	if distance_m > CAMERA_IDEAL_RANGE_M:
		range_factor = clampf(1.0-(distance_m-CAMERA_IDEAL_RANGE_M)/(CAMERA_MAX_RANGE_M-CAMERA_IDEAL_RANGE_M),0.0,1.0)
	var angle_factor := clampf(1.0-bearing_error/deg_to_rad(CAMERA_FOV_DEG*0.5),0.0,1.0)
	var confidence := clampf(0.95*range_factor*angle_factor+randf_range(-CAMERA_REID_NOISE,CAMERA_REID_NOISE),0.0,1.0)
	camera_target_visible = true
	camera_last_confidence = confidence
	camera_last_reason = "VISIBLE"
	if REID_ENABLED and follow_active and confidence >= FOLLOW_MIN_CONFIDENCE:
		follow_target_available = true
		follow_target_confidence = confidence
		follow_last_observation_msec = Time.get_ticks_msec()

func _frame_side_text() -> String:
	if absf(camera_last_frame_offset) < 0.05:
		return "CENTER"
	return "RIGHT" if camera_last_frame_offset > 0.0 else "LEFT"

func _update_camera_tracking(delta: float) -> void:
	# Visual-servo yaw: turn the chassis toward wherever the YOLO box currently sits in frame
	# (left/right of center), proportional to how far off-center it is, instead of snapping to
	# an exact bearing. Only active when Follow's own GRID-path rotation isn't already driving
	# robot_root.rotation.y, so the two don't fight over the same value.
	if follow_active or not is_instance_valid(robot_root) or current_scene_name != "field":
		return
	if not camera_target_visible:
		return
	if camera_last_bearing_deg < CAMERA_TRACK_DEADZONE_DEG:
		return
	var angular_correction := clampf(CAMERA_TRACK_GAIN*camera_last_signed_bearing_rad,-CAMERA_TRACK_MAX_RADPS,CAMERA_TRACK_MAX_RADPS)
	robot_root.rotation.y += angular_correction*delta

func _update_lidar_scan(delta: float) -> void:
	if not is_instance_valid(robot_root) or current_scene_name != "field":
		lidar_min_forward_distance_m = INF
		return
	lidar_scan_timer -= delta
	if lidar_scan_timer > 0.0:
		return
	lidar_scan_timer = LIDAR_SCAN_PERIOD_S
	var space_state := get_world_3d().direct_space_state
	var origin := robot_root.global_position+Vector3(0,0.30,0)
	var heading := robot_root.rotation.y
	var points: Array[Vector3] = []
	var distances: Array[float] = []
	var forward_min := INF
	# No more "exclude the player's own collider" ground-truth shortcut — every hit goes through
	# the same fix/move classification below, same as a real LiDAR point cloud would have to.
	var hit_cells: Dictionary = {}
	for i in range(LIDAR_RAY_COUNT):
		var angle := heading+TAU*float(i)/float(LIDAR_RAY_COUNT)
		var ray_dir := Vector3(sin(angle),0.0,cos(angle))
		var query := PhysicsRayQueryParameters3D.create(origin,origin+ray_dir*LIDAR_MAX_RANGE_M)
		query.collision_mask = 1
		var hit := space_state.intersect_ray(query)
		var hit_point := origin+ray_dir*LIDAR_MAX_RANGE_M
		var hit_distance := LIDAR_MAX_RANGE_M
		if hit:
			hit_point = hit.position
			hit_distance = origin.distance_to(hit_point)
			hit_cells[_world_to_grib_cell(hit_point)] = true
		points.append(hit_point)
		distances.append(hit_distance)
		if absf(angle_difference(heading,angle)) <= deg_to_rad(LIDAR_STOP_FOV_DEG*0.5):
			forward_min = minf(forward_min,hit_distance)
	lidar_min_forward_distance_m = forward_min
	# Sensor fusion (matching the paper's Sect. 4.3): while the camera currently has the target
	# identified, the cell it's estimated to occupy is excluded from fix/move classification below
	# — this is the camera's OWN belief about the target's position (whatever _update_camera_detection
	# computed this frame), not a ground-truth collider check, but it's what stops a target who
	# revisits the same spot often enough over a long session from slowly scoring high enough to
	# get permanently mapped as static scenery and blocking the direct line to themselves.
	var camera_target_cell := _world_to_grib_cell(player.global_position) if camera_target_visible else Vector2i(-999999,-999999)
	_update_lidar_point_classification(hit_cells,camera_target_cell)
	_render_lidar_scan(points,distances)
	_render_lidar_move_points()

func _update_lidar_point_classification(hit_cells: Dictionary, camera_target_cell: Vector2i) -> void:
	# "Fix point" = a LiDAR hit that stays put scan after scan -> assume it's part of the static
	# map. "Move point" = a hit that doesn't (yet) prove stationary -> assume it's the moving
	# target, not scenery. No per-hit "is this literally the player's collider" shortcut: a cell's
	# own score (built up by repeated hits, decaying when not re-hit) is what decides which it is,
	# the way a real point-cloud classifier would have to work from geometry/persistence alone —
	# except for camera_target_cell (see _update_lidar_scan), which is sensor-fusion input, not that.
	var decay := LIDAR_FIX_SCORE_DECAY_PER_S*LIDAR_SCAN_PERIOD_S
	for cell in grib_fix_score.keys():
		if grib_learned_blocked.has(cell):
			grib_fix_score.erase(cell)
			continue
		if not hit_cells.has(cell) or cell == camera_target_cell:
			var decayed: float = grib_fix_score[cell]-decay
			if decayed <= 0.0:
				grib_fix_score.erase(cell)
			else:
				grib_fix_score[cell] = decayed
	lidar_move_points.clear()
	var newly_learned := false
	for cell in hit_cells.keys():
		if grib_learned_blocked.has(cell):
			continue
		if cell == camera_target_cell or grib_route_cells.has(cell):
			continue
		var score: float = float(grib_fix_score.get(cell,0.0))+LIDAR_FIX_SCORE_HIT
		if score >= LIDAR_FIX_SCORE_THRESHOLD:
			grib_learned_blocked[cell] = true
			grib_fix_score.erase(cell)
			newly_learned = true
		else:
			grib_fix_score[cell] = score
			lidar_move_points.append(_grib_cell(cell.x,cell.y))
	if newly_learned:
		_render_learned_map()
		_save()

func _render_learned_map() -> void:
	if not is_instance_valid(grib_map_markers_root):
		return
	for child in grib_map_markers_root.get_children():
		child.queue_free()
	for cell in grib_learned_blocked.keys():
		var marker := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(GRIB_CELL_SIZE*0.85,0.045,GRIB_CELL_SIZE*0.85)
		marker.mesh = mesh
		marker.position = _grib_cell(cell.x,cell.y)+Vector3(0,0.06,0)
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		material.albedo_color = Color(0.56,0.38,0.86,0.4)
		marker.material_override = material
		grib_map_markers_root.add_child(marker)

func _render_lidar_scan(points: Array[Vector3], distances: Array[float]) -> void:
	if not is_instance_valid(lidar_scan_root):
		return
	for child in lidar_scan_root.get_children():
		child.queue_free()
	for i in range(points.size()):
		var marker := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.045
		mesh.bottom_radius = 0.045
		mesh.height = 0.03
		marker.mesh = mesh
		marker.position = points[i]+Vector3(0,0.02,0)
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		var ratio := clampf(distances[i]/LIDAR_MAX_RANGE_M,0.0,1.0)
		var dot_color := Color("ff7a5c").lerp(Color("3ce4d1"),ratio)
		material.albedo_color = dot_color
		material.emission = dot_color
		marker.material_override = material
		lidar_scan_root.add_child(marker)

func _render_lidar_move_points() -> void:
	if not is_instance_valid(lidar_move_points_root):
		return
	for child in lidar_move_points_root.get_children():
		child.queue_free()
	for point in lidar_move_points:
		var marker := MeshInstance3D.new()
		var mesh := CylinderMesh.new()
		mesh.top_radius = 0.08
		mesh.bottom_radius = 0.08
		mesh.height = 0.05
		marker.mesh = mesh
		marker.position = point+Vector3(0,0.1,0)
		var material := StandardMaterial3D.new()
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		material.emission_enabled = true
		material.albedo_color = Color("ff4fd8")
		material.emission = Color("ff4fd8")
		marker.material_override = material
		lidar_move_points_root.add_child(marker)

func _render_camera_fov() -> void:
	if not is_instance_valid(robot_root) or not is_instance_valid(camera_fov_left) or current_scene_name != "field":
		return
	var color := Color("57e0a0") if camera_target_visible else Color("77828c")
	var alpha := 0.55 if camera_target_visible else 0.3
	var heading := camera_yaw
	var half_fov := deg_to_rad(CAMERA_FOV_DEG*0.5)
	_update_fov_edge(camera_fov_left,heading-half_fov,color,alpha)
	_update_fov_edge(camera_fov_right,heading+half_fov,color,alpha)

func _update_fov_edge(edge: MeshInstance3D, angle: float, color: Color, alpha: float) -> void:
	var origin := robot_root.global_position+Vector3(0,0.05,0)
	var direction := Vector3(sin(angle),0.0,cos(angle))
	var mesh: BoxMesh = edge.mesh
	mesh.size.z = CAMERA_MAX_RANGE_M
	edge.position = origin+direction*(CAMERA_MAX_RANGE_M*0.5)
	edge.rotation.y = angle
	var material: StandardMaterial3D = edge.material_override
	material.albedo_color = Color(color.r,color.g,color.b,alpha)

func _make_fov_edge_mesh() -> MeshInstance3D:
	var edge := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.05,0.02,1.0)
	edge.mesh = mesh
	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = Color(1,1,1,0.3)
	edge.material_override = material
	return edge

func _unhandled_key_input(event: InputEvent) -> void:
	if event.is_action_pressed("interact") and not event.is_echo():
		_interact()
	elif event.is_action_pressed("escape_game") and not event.is_echo():
		_toggle_quest_panel()

func _read_project_data() -> void:
	var path := ProjectSettings.globalize_path("res://../thesis_data.json")
	if not FileAccess.file_exists(path):
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return
	var parsed = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		for task in parsed.get("tasks", []):
			if not task.get("archived", false):
				quests.append(task)

func _load_save() -> void:
	if FileAccess.file_exists(SAVE_PATH):
		var file := FileAccess.open(SAVE_PATH, FileAccess.READ)
		if file:
			var parsed = JSON.parse_string(file.get_as_text())
			if parsed is Dictionary:
				save_data = parsed
	if save_data.is_empty():
		save_data = {"scene": "office", "player_name": "Time", "robot_name": "FARM-01", "simulation_xp": 0, "runs": []}
	total_xp = int(save_data.get("simulation_xp", 0))
	walk_speed_mps = clampf(float(save_data.get("walk_speed_mps", 5.2)), 1.0, 11.5)
	sprint_speed_mps = clampf(float(save_data.get("sprint_speed_mps", 7.5)), walk_speed_mps + 0.5, 12.0)
	# The learned LiDAR map intentionally does NOT persist across relaunches (always starts
	# empty) — wipe both the in-memory map and any legacy "lidar_map" key from an older save so
	# it doesn't linger and get silently rewritten by _save().
	grib_learned_blocked.clear()
	save_data.erase("lidar_map")

func _save() -> void:
	save_data["scene"] = current_scene_name
	save_data["simulation_xp"] = total_xp
	save_data["walk_speed_mps"] = walk_speed_mps
	save_data["sprint_speed_mps"] = sprint_speed_mps
	var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(save_data, "  "))

func _build_world() -> void:
	var environment := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color("3d536e")
	sky_mat.sky_horizon_color = Color("d1a77d")
	sky.sky_material = sky_mat
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("b8c7d6")
	env.ambient_light_energy = 0.65
	environment.environment = env
	add_child(environment)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-52, -28, 0)
	sun.light_energy = 1.25
	add_child(sun)
	world_root = Node3D.new()
	world_root.name = "World"
	add_child(world_root)
	office_root = Node3D.new()
	office_root.name = "Office"
	world_root.add_child(office_root)
	field_root = Node3D.new()
	field_root.name = "TestField"
	world_root.add_child(field_root)
	_build_office()
	_build_field()
	camera = Camera3D.new()
	camera.name = "GameCamera"
	camera.fov = 56
	camera.current = true
	add_child(camera)

func _build_office() -> void:
	_box(office_root, "Office floor", Vector3(0, -0.2, 0), Vector3(28, 0.4, 20), PALETTE.floor)
	for x in range(-13, 14, 2):
		for z in range(-9, 10, 2):
			_box(office_root, "Floor tile", Vector3(x, 0.015, z), Vector3(1.94, 0.025, 1.94), PALETTE.tile, false)
	_box(office_root, "Back wall", Vector3(0, 2.25, -9.7), Vector3(28, 4.5, 0.45), PALETTE.wall)
	_box(office_root, "Left wall", Vector3(-13.7, 2.25, 0), Vector3(0.45, 4.5, 20), PALETTE.wall)
	_box(office_root, "Right wall", Vector3(13.7, 2.25, 0), Vector3(0.45, 4.5, 20), PALETTE.wall)
	_box(office_root, "Window glow", Vector3(-7.7, 2.7, -9.43), Vector3(6.6, 2.4, 0.08), Color("79aebc"), false)
	_box(office_root, "Window glow", Vector3(7.2, 2.7, -9.43), Vector3(6.6, 2.4, 0.08), Color("79aebc"), false)
	for x in [-11.0, -4.4, 4.0, 10.4]:
		_box(office_root, "Window mullion", Vector3(x, 2.7, -9.32), Vector3(0.12, 2.6, 0.12), PALETTE.wall_trim, false)
	_box(office_root, "Window rail", Vector3(-7.7, 2.7, -9.28), Vector3(6.8, 0.12, 0.15), PALETTE.wall_trim, false)
	_box(office_root, "Window rail", Vector3(7.2, 2.7, -9.28), Vector3(6.8, 0.12, 0.15), PALETTE.wall_trim, false)
	_desk(office_root, Vector3(-7.8, 0, -5.7), 2.9)
	_desk(office_root, Vector3(-3.6, 0, -5.7), 2.9)
	_desk(office_root, Vector3(2.2, 0, -6.1), 3.2)
	_desk(office_root, Vector3(7.0, 0, -5.9), 3.1)
	_desk(office_root, Vector3(-7.1, 0, 1.2), 3.2)
	_desk(office_root, Vector3(7.2, 0, 1.0), 3.2)
	_box(office_root, "Meeting table", Vector3(0.2, 0.9, -0.3), Vector3(5.0, 0.22, 2.0), Color("8c5942"))
	for x in [-1.5, 0.0, 1.5]:
		_chair(office_root, Vector3(x, 0, -2.1))
		_chair(office_root, Vector3(x, 0, 1.4))
	_box(office_root, "Quest board", Vector3(-11.2, 1.8, -5.7), Vector3(0.18, 2.2, 3.2), Color("8d6446"))
	for i in range(3):
		_box(office_root, "Pinned quest", Vector3(-11.08, 2.2 - i * 0.62, -6.7 + i * 0.9), Vector3(0.08, 0.42, 0.55), [Color("e6cb79"), Color("db8868"), Color("94c3ac")][i], false)
	for p in [Vector3(-10.6,0,-1.8),Vector3(10.8,0,-2.2),Vector3(-10.9,0,5.7),Vector3(10.5,0,5.2)]:
		_plant(office_root,p)
	for x in [-12.2, -9.8, 9.8, 12.2]:
		_box(office_root, "Storage cabinet", Vector3(x, 0.95, -8.75), Vector3(1.1, 1.8, 1.0), Color("6e7881"))
	_npc(office_root, "Research mentor", Vector3(-1.2, 0, 4.3), Color("80577f"), "mentor")
	_npc(office_root, "Robot engineer", Vector3(9.5, 0, 4.5), Color("47707a"), "engineer")
	_station(office_root,"Quest Board",Vector3(-10.2,0,5.8),"board",Color("e2b65f"))
	_station(office_root,"Research Desk",Vector3(0,0,6.8),"desk",Color("76bcae"))
	_station(office_root,"Robot Bay",Vector3(10.2,0,6.2),"robot",Color("90aa81"))
	_world_sign(office_root, "OFFICE  /  RESEARCH HUB", Vector3(0, 4.65, -9.25))

func _build_field() -> void:
	# GRIB map: Grid-registered cells, connected Routes, cell-anchored Interactions, solid Boundaries.
	_box(field_root,"Field ground",Vector3(0,-0.2,0),Vector3(30,0.4,22),Color("d5d8d4"))
	_box(field_root,"Course surface",Vector3(0,0.015,0),Vector3(27,0.05,18.0),Color("dce2d8"),false)
	_grib_draw_grid()
	var fence := Color("47515a")
	_box(field_root,"North boundary",Vector3(0,0.24,-9.25),Vector3(27,0.48,0.24),fence)
	_box(field_root,"West boundary",Vector3(-13.5,0.24,0),Vector3(0.24,0.48,18.5),fence)
	_box(field_root,"East boundary",Vector3(13.5,0.24,0),Vector3(0.24,0.48,18.5),fence)
	_box(field_root,"South boundary west",Vector3(-12.3,0.24,9.25),Vector3(2.4,0.48,0.24),fence)
	_box(field_root,"South boundary east",Vector3(2.55,0.24,9.25),Vector3(21.9,0.48,0.24),fence)
	# Raised beds occupy known grid cells and use solid collision as blocked map regions.
	# Row 8 already sits exactly centered between the middle lane (row 6) and south lane (row
	# 10): both are 6 m apart, so the midpoint (z=3.75) lands exactly on row 8's own cell center.
	# Row 3 (the old top-row placement) does NOT have the same property between the north lane
	# (row 2) and middle lane (row 6): that midpoint (z=-2.25) is row 4's cell center, not row
	# 3's — so the top beds were sitting a full grid row (1.5 m) too far north, close enough to
	# the north lane to visibly crowd it. Row 4 is the correct mirror of row 8.
	for plot_x in [6,12]:
		for plot_row in [4,8]:
			_crop_plot(_grib_cell(plot_x,plot_row))
	# The route graph is a loop with a central cross-aisle and a south entry spur.
	var route := Color("b9a879")
	_grib_route(2,10,15,10,route)
	_grib_route(2,2,15,2,route)
	_grib_route(2,2,2,10,route)
	_grib_route(15,2,15,10,route)
	_grib_route(9,2,9,10,route)
	_grib_route(2,6,15,6,route)
	_grib_route(2,10,2,11,route)
	for cell in [Vector2i(2,10),Vector2i(9,10),Vector2i(15,10),Vector2i(2,6),Vector2i(9,6),Vector2i(15,6),Vector2i(2,2),Vector2i(9,2),Vector2i(15,2)]:
		_decision_marker(cell)
	var robot_pos := _grib_cell(2,10)
	_box(field_root,"Robot start pad",robot_pos+Vector3(0,0.075,0),Vector3(1.35,0.08,1.35),Color("b8c5c2"),false)
	_build_follow_robot(robot_pos)
	prediction_path_root = Node3D.new()
	prediction_path_root.name = "RobotForecastPath"
	prediction_path_root.visible = false
	field_root.add_child(prediction_path_root)
	lidar_scan_root = Node3D.new()
	lidar_scan_root.name = "LidarScan"
	field_root.add_child(lidar_scan_root)
	grib_map_markers_root = Node3D.new()
	grib_map_markers_root.name = "LearnedMap"
	grib_map_markers_root.visible = false
	field_root.add_child(grib_map_markers_root)
	lidar_move_points_root = Node3D.new()
	lidar_move_points_root.name = "LidarMovePoints"
	field_root.add_child(lidar_move_points_root)
	camera_fov_root = Node3D.new()
	camera_fov_root.name = "CameraFovCone"
	field_root.add_child(camera_fov_root)
	camera_fov_left = _make_fov_edge_mesh()
	camera_fov_right = _make_fov_edge_mesh()
	camera_fov_root.add_child(camera_fov_left)
	camera_fov_root.add_child(camera_fov_right)
	_station(field_root,"Robot Run · C02 R09",_grib_cell(1,8),"run",Color("e1b952"))
	_station(field_root,"Camera · C17 R10",_grib_cell(16,9),"camera",Color("82c9c5"))
	_station(field_root,"Motor · C17 R03",_grib_cell(16,2),"motor",Color("d68b65"))
	_build_grib_obstacle_map()
	_render_learned_map()
	_world_sign(field_root,"GRIB TEST FIELD  /  GRID 18 × 12  /  CELL 1.5 m",Vector3(0,4.8,-9.0))
	_world_sign(field_root,"G GRID   ·   R ROUTES   ·   I INTERACTIONS   ·   B BOUNDARIES",Vector3(0,4.25,-8.2))
	field_root.visible = false

func _build_follow_robot(pos: Vector3) -> void:
	robot_root = CharacterBody3D.new()
	robot_root.name = "FARM_01_Simulation"
	# Keep world collision against scenery, but let the avatar walk past the follower.
	robot_root.collision_layer = 2
	robot_root.collision_mask = 1
	robot_root.position = pos
	var body_collision := CollisionShape3D.new()
	var body_shape := BoxShape3D.new()
	body_shape.size = Vector3(1.22,0.66,1.10)
	body_collision.shape = body_shape
	body_collision.position.y = 0.34
	robot_root.add_child(body_collision)
	_box(robot_root,"Robot chassis",Vector3(0,0.38,0),Vector3(0.92,0.38,0.82),Color("e5e9df"),false)
	_box(robot_root,"Robot upper deck",Vector3(0,0.61,-0.04),Vector3(0.62,0.16,0.5),Color("b7c9bc"),false)
	_box(robot_root,"Robot front bumper",Vector3(0,0.23,0.47),Vector3(0.88,0.16,0.12),Color("d5ab58"),false)
	_box(robot_root,"Robot camera mast",Vector3(0,0.83,-0.08),Vector3(0.13,0.36,0.13),Color("596a72"),false)
	_box(robot_root,"Robot camera",Vector3(0,1.02,0.02),Vector3(0.32,0.20,0.22),Color("385461"),false)
	for side in [-1.0,1.0]:
		for axle_z in [-0.25,0.25]:
			_box(robot_root,"Robot wheel",Vector3(side*0.51,0.20,axle_z),Vector3(0.18,0.38,0.23),Color("394450"),false)
	_world_sign(robot_root,"FARM-01  ·  SIM",Vector3(0,1.27,0))
	field_root.add_child(robot_root)

func _grib_cell(column: int, row: int) -> Vector3:
	return Vector3(GRIB_ORIGIN.x+(float(column)+0.5)*GRIB_CELL_SIZE,0,GRIB_ORIGIN.y+(float(row)+0.5)*GRIB_CELL_SIZE)

func _world_to_grib_cell(position: Vector3) -> Vector2i:
	var column := roundi((position.x-GRIB_ORIGIN.x)/GRIB_CELL_SIZE-0.5)
	var row := roundi((position.z-GRIB_ORIGIN.y)/GRIB_CELL_SIZE-0.5)
	return Vector2i(column,row)

func _build_grib_obstacle_map() -> void:
	# Only the field's operating boundary/geofence (edges + fence gaps) is known in advance —
	# that's structural (where the course physically ends), not something that needs sensing.
	# Crop beds, stations, and anything else inside the field are NOT pre-known: they are only
	# added to grib_learned_blocked once the robot's own LiDAR has actually detected them
	# (see _update_lidar_point_classification), mirroring how a real deployment would need a prior
	# mapping/survey pass rather than being handed a perfect map of the plot.
	grib_boundary_blocked.clear()
	for column in range(GRIB_COLUMNS):
		for row in range(GRIB_ROWS):
			var cell := Vector2i(column,row)
			var center := _grib_cell(column,row)
			var half_x := ROBOT_SWEEP_RADIUS_M+0.12
			var half_z := ROBOT_SWEEP_RADIUS_M+0.12
			var left := center.x-half_x
			var right := center.x+half_x
			var north := center.z-half_z
			var south := center.z+half_z
			if left < -13.38 or right > 13.38 or north < -9.13 or south > 9.13:
				grib_boundary_blocked[cell] = true
				continue
			if _rects_overlap(left,right,north,south,-13.5,-11.1,9.13,9.37) or _rects_overlap(left,right,north,south,-8.4,13.5,9.13,9.37):
				grib_boundary_blocked[cell] = true

func _rects_overlap(left_a: float, right_a: float, top_a: float, bottom_a: float, left_b: float, right_b: float, top_b: float, bottom_b: float) -> bool:
	return left_a < right_b and right_a > left_b and top_a < bottom_b and bottom_a > top_b

func _is_grib_cell_walkable(cell: Vector2i) -> bool:
	if cell.x < 0 or cell.x >= GRIB_COLUMNS or cell.y < 0 or cell.y >= GRIB_ROWS:
		return false
	if grib_boundary_blocked.has(cell):
		return false
	return not grib_learned_blocked.has(cell)

func _is_direct_path_clear(from: Vector3, to: Vector3) -> bool:
	var distance := Vector2(to.x-from.x,to.z-from.z).length()
	if distance < 0.01:
		return true
	var steps := maxi(1,ceili(distance/(GRIB_CELL_SIZE*0.5)))
	for i in range(steps+1):
		var sample := from.lerp(to,float(i)/float(steps))
		if not _is_grib_cell_walkable(_world_to_grib_cell(sample)):
			return false
	return true

func _nearest_walkable_grib_cell(position: Vector3) -> Vector2i:
	var nearest := Vector2i(-99,-99)
	var nearest_distance := INF
	for column in range(GRIB_COLUMNS):
		for row in range(GRIB_ROWS):
			var cell := Vector2i(column,row)
			if not _is_grib_cell_walkable(cell):
				continue
			var cell_position := _grib_cell(column,row)
			var distance := Vector2(position.x-cell_position.x,position.z-cell_position.z).length_squared()
			if distance < nearest_distance:
				nearest = cell
				nearest_distance = distance
	return nearest

func _plan_follow_grid_path() -> void:
	follow_grid_path.clear()
	follow_path_index = 0
	follow_has_grid_path = false
	follow_needs_replan = false
	follow_planned_target_cell = _world_to_grib_cell(player.global_position)
	var start_cell := _nearest_walkable_grib_cell(robot_root.global_position)
	if start_cell.x < 0:
		_log_follow_row("REPLAN",0.0,"no walkable start cell")
		return
	var target_cell := follow_planned_target_cell
	var found_goal := false
	var best_score := INF
	var best_path: Array[Vector2i] = []
	for column in range(maxi(0,target_cell.x-2),mini(GRIB_COLUMNS,target_cell.x+3)):
		for row in range(maxi(0,target_cell.y-2),mini(GRIB_ROWS,target_cell.y+3)):
			var candidate := Vector2i(column,row)
			if not _is_grib_cell_walkable(candidate):
				continue
			var candidate_position := _grib_cell(column,row)
			var target_distance := Vector2(candidate_position.x-player.global_position.x,candidate_position.z-player.global_position.z).length()
			if target_distance < FOLLOW_STOP_DISTANCE_M+0.08 or target_distance > FOLLOW_DISTANCE_M+1.8:
				continue
			var candidate_path := _find_grib_path(start_cell,candidate)
			if candidate != start_cell and candidate_path.is_empty():
				continue
			var score := float(candidate_path.size())+absf(target_distance-FOLLOW_DISTANCE_M)*1.2
			if score < best_score:
				best_score = score
				best_path = candidate_path
				found_goal = true
	if found_goal:
		follow_grid_path = best_path
		if follow_grid_path.is_empty():
			# Degenerate case only: the chosen stopping cell IS start_cell (no real multi-cell
			# path), so give the controller a single waypoint to hold at (feeds LOCKED).
			# Do NOT do this when a real path exists: the robot is continuously moving through
			# cells, so it is almost always >0.24 m from the exact center of whatever cell it is
			# nominally "in" — unconditionally snapping back to that center on every replan could
			# point backward relative to its current travel direction (if it had already passed
			# the center), causing a near-180 degree spin-in-place instead of smooth progress.
			follow_grid_path.push_front(start_cell)
		follow_has_grid_path = true
	var replan_heading_deg := 0.0
	if not follow_grid_path.is_empty():
		var first_point := _grib_cell(follow_grid_path[0].x,follow_grid_path[0].y)
		var to_first := first_point-robot_root.global_position
		replan_heading_deg = rad_to_deg(atan2(to_first.x,to_first.z))
	_log_follow_row("REPLAN",replan_heading_deg,"found=%s path_len=%d start=(%d,%d) target=(%d,%d)" % [str(found_goal),follow_grid_path.size(),start_cell.x,start_cell.y,target_cell.x,target_cell.y])

func _find_grib_path(start: Vector2i, goal: Vector2i) -> Array[Vector2i]:
	var path: Array[Vector2i] = []
	if not _is_grib_cell_walkable(start) or not _is_grib_cell_walkable(goal):
		return path
	if start == goal:
		return path
	var frontier: Array[Vector2i] = [start]
	var came_from: Dictionary = {start: start}
	var cost_so_far: Dictionary = {start: 0}
	while not frontier.is_empty():
		var best_frontier_index := 0
		var best_estimated_cost := INF
		for index in range(frontier.size()):
			var option: Vector2i = frontier[index]
			var estimated_cost := float(cost_so_far[option]+absi(goal.x-option.x)+absi(goal.y-option.y))
			if estimated_cost < best_estimated_cost:
				best_estimated_cost = estimated_cost
				best_frontier_index = index
		var current: Vector2i = frontier.pop_at(best_frontier_index)
		if current == goal:
			break
		for step in [Vector2i(1,0),Vector2i(-1,0),Vector2i(0,1),Vector2i(0,-1)]:
			var neighbor: Vector2i = current+step
			if not _is_grib_cell_walkable(neighbor):
				continue
			var new_cost := int(cost_so_far[current])+1
			if cost_so_far.has(neighbor) and new_cost >= int(cost_so_far[neighbor]):
				continue
			cost_so_far[neighbor] = new_cost
			came_from[neighbor] = current
			if not frontier.has(neighbor):
				frontier.append(neighbor)
	if not came_from.has(goal):
		return path
	var cursor := goal
	while cursor != start:
		path.push_front(cursor)
		cursor = came_from[cursor]
	return path

func _grib_draw_grid() -> void:
	var grid_color := Color("c7d0c4")
	for column in range(1,GRIB_COLUMNS):
		var x := GRIB_ORIGIN.x+float(column)*GRIB_CELL_SIZE
		_box(field_root,"GRIB grid column %02d" % column,Vector3(x,0.047,0),Vector3(0.025,0.012,GRIB_ROWS*GRIB_CELL_SIZE),grid_color,false)
	for row in range(1,GRIB_ROWS):
		var z := GRIB_ORIGIN.y+float(row)*GRIB_CELL_SIZE
		_box(field_root,"GRIB grid row %02d" % row,Vector3(0,0.047,z),Vector3(GRIB_COLUMNS*GRIB_CELL_SIZE,0.012,0.025),grid_color,false)

func _grib_route(start_column: int, start_row: int, end_column: int, end_row: int, color: Color) -> void:
	var start := _grib_cell(start_column,start_row)
	var finish := _grib_cell(end_column,end_row)
	var center := (start+finish)*0.5+Vector3(0,0.062,0)
	var length := start.distance_to(finish)
	var size := Vector3(0.18,0.018,length) if start_column == end_column else Vector3(length,0.018,0.18)
	_box(field_root,"GRIB route %02d-%02d to %02d-%02d" % [start_column,start_row,end_column,end_row],center,size,color,false)
	# The route is deliberately laid out to stay open, so every cell it passes through is immune
	# to LiDAR obstacle-learning (see _update_lidar_point_classification) regardless of what a
	# sensor reading near it might suggest.
	if start_column == end_column:
		for row in range(mini(start_row,end_row),maxi(start_row,end_row)+1):
			grib_route_cells[Vector2i(start_column,row)] = true
	else:
		for column in range(mini(start_column,end_column),maxi(start_column,end_column)+1):
			grib_route_cells[Vector2i(column,start_row)] = true

func _crop_plot(center: Vector3) -> void:
	var width := 5.7
	var length := 3.35
	var wood := Color("8d6248")
	var soil := Color("705644")
	_box(field_root,"Plot bed",center+Vector3(0,0.20,0),Vector3(width,0.40,length),wood,true)
	_box(field_root,"Plot soil",center+Vector3(0,0.36,0),Vector3(width-0.28,0.08,length-0.28),soil,false)
	var leaf_colors := [Color("61955a"),Color("6da463"),Color("588a53"),Color("77a96a")]
	# Row/column positions use (index - (count-1)/2) * spacing, which is symmetric around
	# center.z/center.x by construction for any count/spacing — the previous hand-picked offsets
	# (e.g. "-length*0.34 + row*0.22") were not actually centered, and the earlier fix only
	# widened the single row-strip-worth of margin instead of fixing the systemic issue. Filling
	# more of the bed (was a small 2.1 x 0.66 m patch inside a 5.7 x 3.35 m bed) also removes the
	# large empty margins that made "is this centered" hard to judge at the camera's steep angle.
	var row_count := 4
	var row_spacing := 0.85
	var col_count := 12
	var col_spacing := 0.44
	for row in range(row_count):
		var z := center.z+(float(row)-float(row_count-1)*0.5)*row_spacing
		_box(field_root,"Crop row",Vector3(center.x,0.56,z),Vector3(width-0.65,0.34,0.18),leaf_colors[row],false)
		for col in range(col_count):
			var x := center.x+(float(col)-float(col_count-1)*0.5)*col_spacing
			_box(field_root,"Crop leaf",Vector3(x,0.73,z),Vector3(0.34,0.12,0.24),leaf_colors[(row+col)%leaf_colors.size()],false)

func _decision_marker(cell: Vector2i) -> void:
	# Visual-only reference point at a route junction (no collision, never an obstacle) — labeled
	# with its grid coordinate, same "C.. R.." convention as station signs, purely so it can be
	# identified/referenced (e.g. "the robot stalled near C03 R11") rather than meaning anything
	# to the path planner.
	var pos := _grib_cell(cell.x,cell.y)
	var marker := MeshInstance3D.new()
	var ring := CylinderMesh.new()
	ring.top_radius = 0.55
	ring.bottom_radius = 0.55
	ring.height = 0.035
	marker.mesh = ring
	marker.position = pos+Vector3(0,0.075,0)
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("e5c66f")
	marker.material_override = material
	field_root.add_child(marker)
	var label := Label3D.new()
	label.text = "C%02d R%02d" % [cell.x+1,cell.y+1]
	label.position = pos+Vector3(0,0.42,0)
	label.font_size = 26
	label.pixel_size = 0.0045
	label.modulate = Color("e5c66f")
	label.outline_size = 6
	field_root.add_child(label)

func _build_player() -> void:
	player = CharacterBody3D.new()
	player.name = "Player"
	var capsule := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.height = 1.9
	shape.radius = PLAYER_COLLISION_RADIUS_M
	capsule.shape = shape
	capsule.position.y = 0.95
	player.add_child(capsule)
	var model := Node3D.new()
	model.name = "Model"
	model.position.y = 0.06
	player.add_child(model)
	_box(model,"Player body",Vector3(0,0.9,0),Vector3(0.62,0.72,0.38),Color("386b58"),false)
	_box(model,"Player head",Vector3(0,1.5,0),Vector3(0.48,0.48,0.44),Color("e5bb91"),false)
	_box(model,"Player hair",Vector3(0,1.74,-0.02),Vector3(0.5,0.16,0.47),Color("493a34"),false)
	_box(model,"Player leg L",Vector3(-0.16,0.34,0),Vector3(0.2,0.5,0.24),Color("344354"),false)
	_box(model,"Player leg R",Vector3(0.16,0.34,0),Vector3(0.2,0.5,0.24),Color("344354"),false)
	_box(model,"Player eye L",Vector3(-0.11,1.54,0.224),Vector3(0.045,0.055,0.025),Color("27323b"),false)
	_box(model,"Player eye R",Vector3(0.11,1.54,0.224),Vector3(0.045,0.055,0.025),Color("27323b"),false)
	add_child(player)
	# Player spawn position is intentionally not persisted — always starts fresh each launch
	# (set_scene(..., true) at startup places it at the scene-appropriate default below).
	player.position = Vector3(-5.5,0,5.8)
	_add_input("move_forward", [KEY_W, KEY_UP])
	_add_input("move_back", [KEY_S, KEY_DOWN])
	_add_input("move_left", [KEY_A, KEY_LEFT])
	_add_input("move_right", [KEY_D, KEY_RIGHT])
	_add_input("sprint", [KEY_SHIFT])
	_add_input("interact", [KEY_E, KEY_SPACE, KEY_ENTER])
	_add_input("escape_game", [KEY_ESCAPE])

func _add_input(action: String, keys: Array) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	for keycode in keys:
		var event := InputEventKey.new()
		event.physical_keycode = keycode
		InputMap.action_add_event(action,event)

func _build_ui() -> void:
	ui = CanvasLayer.new()
	add_child(ui)
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_PASS
	ui.add_child(root)
	var top := PanelContainer.new()
	top.position = Vector2(22,18)
	top.custom_minimum_size = Vector2(650,92)
	_style_panel(top,Color("182342"),Color("b9a66d"))
	root.add_child(top)
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation",18)
	top.add_child(top_row)
	top_row.add_child(_make_portrait())
	var stats := VBoxContainer.new()
	top_row.add_child(stats)
	hud_label = Label.new()
	hud_label.add_theme_font_size_override("font_size",19)
	hud_label.add_theme_color_override("font_color",Color("fff0cb"))
	stats.add_child(hud_label)
	var sub := Label.new()
	sub.text = "FARM ROBOT ADVENTURE  ·  LOCAL GAME"
	sub.add_theme_font_size_override("font_size",11)
	sub.add_theme_color_override("font_color",Color("a8c6c0"))
	stats.add_child(sub)
	robot_speed_label = Label.new()
	robot_speed_label.add_theme_font_size_override("font_size",13)
	robot_speed_label.add_theme_color_override("font_color",Color("9fe0cd"))
	stats.add_child(robot_speed_label)
	var nav := HBoxContainer.new()
	nav.anchor_left = 1.0
	nav.anchor_right = 1.0
	nav.offset_left = -990
	nav.offset_right = -22
	nav.offset_top = 26
	nav.offset_bottom = 76
	nav.add_theme_constant_override("separation",8)
	root.add_child(nav)
	_button(nav,"OFFICE",func():set_scene("office"))
	_button(nav,"TEST FIELD",func():set_scene("field"))
	_button(nav,"QUESTS",_toggle_quest_panel)
	_button(nav,"SPEED",_toggle_speed_panel)
	_button(nav,"LIDAR",_toggle_lidar_visibility)
	_button(nav,"MAP",_toggle_learned_map_visibility)
	_button(nav,"ROBOT",_toggle_robot_panel)
	_button(nav,"POV",_toggle_robot_pov)
	robot_panel = PanelContainer.new()
	robot_panel.anchor_left = 1.0
	robot_panel.anchor_right = 1.0
	robot_panel.offset_left = -600
	robot_panel.offset_right = -380
	robot_panel.offset_top = 86
	robot_panel.offset_bottom = 340
	robot_panel.visible = false
	_style_panel(robot_panel,Color("182342"),Color("d5b765"))
	root.add_child(robot_panel)
	robot_panel_box = VBoxContainer.new()
	robot_panel.add_child(robot_panel_box)
	robot_pov_wrap = Control.new()
	robot_pov_wrap.anchor_left = 0.0
	robot_pov_wrap.anchor_top = 1.0
	robot_pov_wrap.anchor_right = 0.0
	robot_pov_wrap.anchor_bottom = 1.0
	robot_pov_wrap.offset_left = 22
	robot_pov_wrap.offset_top = -340
	robot_pov_wrap.offset_right = 22+360
	robot_pov_wrap.offset_bottom = -116
	robot_pov_wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(robot_pov_wrap)
	var pov_container := SubViewportContainer.new()
	pov_container.stretch = true
	pov_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	pov_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	robot_pov_wrap.add_child(pov_container)
	robot_pov_viewport = SubViewport.new()
	robot_pov_viewport.size = Vector2i(360,224)
	pov_container.add_child(robot_pov_viewport)
	robot_pov_camera = Camera3D.new()
	robot_pov_camera.fov = CAMERA_FOV_DEG
	robot_pov_viewport.add_child(robot_pov_camera)
	var pov_frame := Panel.new()
	pov_frame.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	pov_frame.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_style_panel(pov_frame,Color(0,0,0,0),Color("d5b765"))
	robot_pov_wrap.add_child(pov_frame)
	var pov_title := Label.new()
	pov_title.text = "FARM-01  ·  WEBCAM POV / YOLO"
	pov_title.position = Vector2(8,4)
	pov_title.add_theme_font_size_override("font_size",13)
	pov_title.add_theme_color_override("font_color",Color("fff0cb"))
	robot_pov_wrap.add_child(pov_title)
	robot_pov_status_label = Label.new()
	robot_pov_status_label.position = Vector2(8,198)
	robot_pov_status_label.add_theme_font_size_override("font_size",12)
	robot_pov_status_label.add_theme_color_override("font_color",Color("9fe0cd"))
	robot_pov_wrap.add_child(robot_pov_status_label)
	robot_pov_reticle = Panel.new()
	robot_pov_reticle.visible = false
	robot_pov_reticle.mouse_filter = Control.MOUSE_FILTER_IGNORE
	robot_pov_reticle_style = StyleBoxFlat.new()
	robot_pov_reticle_style.bg_color = Color(0,0,0,0)
	robot_pov_reticle_style.border_color = Color("57e0a0")
	robot_pov_reticle_style.set_border_width_all(2)
	robot_pov_reticle_style.set_corner_radius_all(2)
	robot_pov_reticle.add_theme_stylebox_override("panel",robot_pov_reticle_style)
	robot_pov_wrap.add_child(robot_pov_reticle)
	robot_pov_label_bg = ColorRect.new()
	robot_pov_label_bg.visible = false
	robot_pov_label_bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	robot_pov_label_bg.color = Color("57e0a0")
	robot_pov_wrap.add_child(robot_pov_label_bg)
	robot_pov_label_text = Label.new()
	robot_pov_label_text.visible = false
	robot_pov_label_text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	robot_pov_label_text.add_theme_font_size_override("font_size",13)
	robot_pov_label_text.add_theme_color_override("font_color",Color("12241c"))
	robot_pov_wrap.add_child(robot_pov_label_text)
	speed_panel = PanelContainer.new()
	speed_panel.anchor_left = 1.0
	speed_panel.anchor_right = 1.0
	speed_panel.offset_left = -365
	speed_panel.offset_right = -22
	speed_panel.offset_top = 86
	speed_panel.offset_bottom = 250
	speed_panel.visible = false
	_style_panel(speed_panel,Color("182342"),Color("d5b765"))
	root.add_child(speed_panel)
	var speed_box := VBoxContainer.new()
	speed_panel.add_child(speed_box)
	var speed_title := Label.new()
	speed_title.text = "PLAYER SPEED  ·  m/s"
	speed_title.add_theme_color_override("font_color",Color("fff0cb"))
	speed_box.add_child(speed_title)
	var walk_row := HBoxContainer.new()
	speed_box.add_child(walk_row)
	var walk_label := Label.new()
	walk_label.text = "Walk"
	walk_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	walk_row.add_child(walk_label)
	walk_speed_input = SpinBox.new()
	walk_speed_input.min_value = 1.0
	walk_speed_input.max_value = 11.5
	walk_speed_input.step = 0.1
	walk_speed_input.value = walk_speed_mps
	walk_speed_input.value_changed.connect(_on_walk_speed_changed)
	walk_row.add_child(walk_speed_input)
	var sprint_row := HBoxContainer.new()
	speed_box.add_child(sprint_row)
	var sprint_label := Label.new()
	sprint_label.text = "Shift / Sprint"
	sprint_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	sprint_row.add_child(sprint_label)
	sprint_speed_input = SpinBox.new()
	sprint_speed_input.min_value = walk_speed_mps + 0.5
	sprint_speed_input.max_value = 12.0
	sprint_speed_input.step = 0.1
	sprint_speed_input.value = sprint_speed_mps
	sprint_speed_input.value_changed.connect(_on_sprint_speed_changed)
	sprint_row.add_child(sprint_speed_input)
	_button(speed_box,"CLOSE",_toggle_speed_panel)
	var bottom := PanelContainer.new()
	bottom.anchor_left = 0.5
	bottom.anchor_right = 0.5
	bottom.anchor_top = 1.0
	bottom.anchor_bottom = 1.0
	bottom.offset_left = -360
	bottom.offset_right = 360
	bottom.offset_top = -92
	bottom.offset_bottom = -20
	_style_panel(bottom,Color("182342"),Color("d5b765"))
	root.add_child(bottom)
	var bottom_box := VBoxContainer.new()
	bottom.add_child(bottom_box)
	hint_label = Label.new()
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.add_theme_color_override("font_color",Color("fff2d2"))
	hint_label.add_theme_font_size_override("font_size",16)
	bottom_box.add_child(hint_label)
	choice_row = HBoxContainer.new()
	choice_row.alignment = BoxContainer.ALIGNMENT_CENTER
	choice_row.add_theme_constant_override("separation",8)
	bottom_box.add_child(choice_row)
	dialog_panel = PanelContainer.new()
	dialog_panel.anchor_left = 0.5
	dialog_panel.anchor_right = 0.5
	dialog_panel.anchor_top = 0.5
	dialog_panel.anchor_bottom = 0.5
	dialog_panel.offset_left = -300
	dialog_panel.offset_right = 300
	dialog_panel.offset_top = -105
	dialog_panel.offset_bottom = 105
	dialog_panel.visible = false
	_style_panel(dialog_panel,Color("d69a62"),Color("ffe4a4"))
	root.add_child(dialog_panel)
	var dialog_box := VBoxContainer.new()
	dialog_panel.add_child(dialog_box)
	dialog_label = Label.new()
	dialog_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	dialog_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	dialog_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	dialog_label.add_theme_color_override("font_color",Color("302b35"))
	dialog_label.add_theme_font_size_override("font_size",19)
	dialog_box.add_child(dialog_label)
	_button(dialog_box,"รับทราบ",func():dialog_panel.visible=false)
	quest_panel = PanelContainer.new()
	quest_panel.position = Vector2(24,112)
	quest_panel.custom_minimum_size = Vector2(430,560)
	quest_panel.visible = false
	_style_panel(quest_panel,Color("182342"),Color("d5b765"))
	root.add_child(quest_panel)
	var quest_box := VBoxContainer.new()
	quest_panel.add_child(quest_box)
	var quest_head := Label.new()
	quest_head.text = "QUEST JOURNAL"
	quest_head.add_theme_font_size_override("font_size",22)
	quest_head.add_theme_color_override("font_color",Color("fff0cb"))
	quest_box.add_child(quest_head)
	quest_text = RichTextLabel.new()
	quest_text.bbcode_enabled = true
	quest_text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	quest_box.add_child(quest_text)
	_button(quest_box,"ปิด",_toggle_quest_panel)
	_refresh_quest_text()

func _make_portrait() -> Control:
	var face := ColorRect.new()
	face.custom_minimum_size = Vector2(50,50)
	face.color = Color("39695a")
	var face_label := Label.new()
	face_label.text = "◆"
	face_label.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	face_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	face_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	face_label.add_theme_color_override("font_color",Color("f1d18b"))
	face_label.add_theme_font_size_override("font_size",27)
	face.add_child(face_label)
	return face

func _toggle_speed_panel() -> void:
	if speed_panel:
		speed_panel.visible = not speed_panel.visible

func _toggle_lidar_visibility() -> void:
	if is_instance_valid(lidar_scan_root):
		lidar_scan_root.visible = not lidar_scan_root.visible

func _toggle_learned_map_visibility() -> void:
	if is_instance_valid(grib_map_markers_root):
		grib_map_markers_root.visible = not grib_map_markers_root.visible

func _reset_learned_map() -> void:
	grib_learned_blocked.clear()
	grib_fix_score.clear()
	lidar_move_points.clear()
	_render_learned_map()
	_save()

func _toggle_robot_pov() -> void:
	if is_instance_valid(robot_pov_wrap):
		robot_pov_wrap.visible = not robot_pov_wrap.visible

func _update_robot_pov() -> void:
	if not is_instance_valid(robot_pov_wrap) or not robot_pov_wrap.visible:
		return
	if not is_instance_valid(robot_pov_camera) or not is_instance_valid(robot_root) or current_scene_name != "field":
		robot_pov_status_label.text = "OFFLINE  ·  ไม่ได้อยู่ใน Test Field"
		_hide_robot_pov_detection()
		return
	var camera_pos := robot_root.global_position+Vector3(0,1.0,0.1)
	robot_pov_camera.global_position = camera_pos
	# Camera3D looks down its local -Z, but camera_yaw follows this file's "local +Z = forward"
	# convention (matching the robot's bumper mesh), so add PI to point the lens the right way.
	robot_pov_camera.global_rotation = Vector3(0,camera_yaw+PI,0)
	robot_pov_camera.fov = CAMERA_FOV_DEG
	if not camera_target_visible:
		_hide_robot_pov_detection()
		robot_pov_status_label.text = "NO DETECTION · %s  (dist %.1fm, brg %.0f°/%.0f°)" % [camera_last_reason,camera_last_distance_m,camera_last_bearing_deg,CAMERA_FOV_DEG*0.5]
		return
	var torso_point := player.global_position+Vector3(0,0.9,0)
	if robot_pov_camera.is_position_behind(torso_point):
		_hide_robot_pov_detection()
		robot_pov_status_label.text = "NO DETECTION · %s" % camera_last_reason
		return
	# Project the player's actual head/feet/shoulder-width points (YOLO-style person box),
	# instead of a fixed-size reticle, so the box scales correctly with camera perspective.
	var right := robot_pov_camera.global_transform.basis.x
	var screen_head := robot_pov_camera.unproject_position(player.global_position+Vector3(0,1.85,0))
	var screen_feet := robot_pov_camera.unproject_position(player.global_position+Vector3(0,0.05,0))
	var screen_left := robot_pov_camera.unproject_position(player.global_position+Vector3(0,0.95,0)-right*0.33)
	var screen_right := robot_pov_camera.unproject_position(player.global_position+Vector3(0,0.95,0)+right*0.33)
	var box_left := minf(screen_left.x,screen_right.x)
	var box_top := minf(screen_head.y,screen_feet.y)
	var box_size := Vector2(maxf(screen_left.x,screen_right.x)-box_left,maxf(screen_head.y,screen_feet.y)-box_top)
	robot_pov_reticle.position = Vector2(box_left,box_top)
	robot_pov_reticle.size = box_size
	robot_pov_reticle.visible = true
	robot_pov_label_text.text = "person %.2f" % camera_last_confidence
	var label_size := robot_pov_label_text.get_minimum_size()+Vector2(8,4)
	robot_pov_label_bg.position = Vector2(box_left,box_top-label_size.y)
	robot_pov_label_bg.size = label_size
	robot_pov_label_text.position = robot_pov_label_bg.position+Vector2(4,2)
	robot_pov_label_bg.visible = true
	robot_pov_label_text.visible = true
	robot_pov_status_label.text = "YOLO person %.2f  ·  %.1f m  ·  %s of center (offset %.2f)" % [camera_last_confidence,camera_last_distance_m,_frame_side_text(),camera_last_frame_offset]

func _hide_robot_pov_detection() -> void:
	robot_pov_reticle.visible = false
	robot_pov_label_bg.visible = false
	robot_pov_label_text.visible = false

func _toggle_robot_panel() -> void:
	if not is_instance_valid(robot_panel):
		return
	robot_panel.visible = not robot_panel.visible
	if robot_panel.visible:
		_refresh_robot_panel()

func _refresh_robot_panel() -> void:
	if not is_instance_valid(robot_panel_box):
		return
	for child in robot_panel_box.get_children():
		child.queue_free()
	var title := Label.new()
	title.text = "สั่งงาน FARM-01  ·  ใช้ได้ทุกจุดใน Test Field"
	title.add_theme_color_override("font_color",Color("fff0cb"))
	robot_panel_box.add_child(title)
	if current_scene_name != "field" or not is_instance_valid(robot_root):
		var note := Label.new()
		note.text = "ไปที่ Test Field ก่อนเพื่อสั่งงาน FARM-01"
		note.add_theme_color_override("font_color",Color("e0c9a0"))
		robot_panel_box.add_child(note)
		return
	robot_panel_follow_button = _button(robot_panel_box,"หยุด Follow" if follow_active else "เริ่ม Follow ฉัน",_toggle_follow)
	_button(robot_panel_box,"ทดสอบ Target หาย",func():_run_activity("tracking");_refresh_robot_panel())
	_button(robot_panel_box,"ตรง",func():_run_activity("straight"))
	_button(robot_panel_box,"ซ้าย",func():_run_activity("turn_left"))
	_button(robot_panel_box,"ขวา",func():_run_activity("turn_right"))
	_button(robot_panel_box,"ล้าง LiDAR MAP ที่เก็บไว้",func():_reset_learned_map();_refresh_robot_panel())
	_button(robot_panel_box,"CLOSE",_toggle_robot_panel)

func _on_walk_speed_changed(value: float) -> void:
	walk_speed_mps = minf(value, sprint_speed_mps - 0.5)
	if walk_speed_input and not is_equal_approx(walk_speed_input.value, walk_speed_mps):
		walk_speed_input.value = walk_speed_mps
	sprint_speed_mps = maxf(sprint_speed_mps, walk_speed_mps + 0.5)
	if sprint_speed_input:
		sprint_speed_input.min_value = walk_speed_mps + 0.5
		sprint_speed_input.value = sprint_speed_mps
	_update_robot_speed_hud()
	_save()

func _on_sprint_speed_changed(value: float) -> void:
	sprint_speed_mps = maxf(value, walk_speed_mps + 0.5)
	if sprint_speed_input and not is_equal_approx(sprint_speed_input.value, sprint_speed_mps):
		sprint_speed_input.value = sprint_speed_mps
	_update_robot_speed_hud()
	_save()

func _button(parent: Node, text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.custom_minimum_size = Vector2(112,42)
	button.add_theme_color_override("font_color",Color("fff1cf"))
	button.add_theme_color_override("font_hover_color",Color("ffffff"))
	button.add_theme_stylebox_override("normal",_stylebox(Color("29375c"),Color("8799bb")))
	button.add_theme_stylebox_override("hover",_stylebox(Color("455a82"),Color("e0c77f")))
	button.add_theme_stylebox_override("pressed",_stylebox(Color("785a38"),Color("ffe4a4")))
	button.pressed.connect(action)
	parent.add_child(button)
	return button

func _style_panel(panel: Control, color: Color, border: Color) -> void:
	panel.add_theme_stylebox_override("panel",_stylebox(color,border))

func _stylebox(color: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(3)
	style.set_corner_radius_all(2)
	style.content_margin_left = 14
	style.content_margin_right = 14
	style.content_margin_top = 10
	style.content_margin_bottom = 10
	return style

func _update_hud() -> void:
	if hud_label:
		var level := int(total_xp / 100) + 1
		hud_label.text = "%s   ·   LV. %d   ·   %d XP" % [String(save_data.get("player_name","Time")),level,total_xp]

func _update_nearby() -> void:
	var previous_id := String(active_station.get("id", ""))
	var nearby: Dictionary = {}
	var best := INTERACTION_RADIUS_M
	var source: Node3D = office_root if current_scene_name == "office" else field_root
	for node in source.get_children():
		if node is Node3D and node.has_meta("station_id"):
			var distance := Vector2(player.position.x,player.position.z).distance_to(Vector2(node.position.x,node.position.z))
			if distance < best:
				best = distance
				nearby = {"id":node.get_meta("station_id"),"title":node.get_meta("station_title"),"kind":node.get_meta("station_kind")}
	active_station = nearby
	if not active_station.is_empty():
		hint_label.text = "E  คุย/เล่น: %s" % active_station.title
		if previous_id != String(active_station.id):
			_show_choices()
	else:
		if current_scene_name == "field" and is_instance_valid(robot_root):
			hint_label.text = "WASD เดิน  ·  SHIFT วิ่ง  ·  E = สั่ง FARM-01 (ได้ทุกจุดใน Test Field)  ·  ROBOT = คำสั่งอื่น  ·  ESC เควส"
		else:
			hint_label.text = "WASD เดิน  ·  SHIFT วิ่ง  ·  E โต้ตอบ  ·  ESC เควส"
		if previous_id != "":
			_clear_choices()

func _interact() -> void:
	if follow_active:
		_stop_follow()
		return
	if active_station.is_empty():
		if current_scene_name == "field" and is_instance_valid(robot_root):
			_toggle_follow()
		else:
			hint_label.text = "เดินเข้าใกล้ตัวละครหรือสถานี แล้วกด E"
		return
	match String(active_station.kind):
		"mentor":
			_show_dialog("พี่นักวิจัย", "ยินดีต้อนรับสู่แล็บ! คุยกับทีมได้ แล้วไป Test Field เพื่อเริ่มภารกิจทดลองนะ")
		"engineer":
			_show_dialog("วิศวกรหุ่นยนต์", "FARM-01 พร้อมแล้ว เลือก Robot Run, Camera หรือ Motor ที่ Test Field เพื่อเล่นการทดสอบ")
		"board":
			_toggle_quest_panel()
		"desk":
			_show_dialog("Research Desk", "เปิด Quest Journal จากปุ่ม QUESTS หรือเลือกสถานีใน Test Field เพื่อเริ่ม mini-game")
		"robot":
			set_scene("field")
		"run":
			_toggle_follow()
		"camera":
			_run_activity("camera")
		"motor":
			_run_activity("motor")

func _show_choices() -> void:
	_clear_choices()
	var kind := String(active_station.kind)
	if kind == "run":
		_button(choice_row,"หยุด Follow" if follow_active else "เริ่ม Follow ฉัน",_toggle_follow)
		_button(choice_row,"ทดสอบ Target หาย",func():_run_activity("tracking"))
		_button(choice_row,"ตรง",func():_run_activity("straight"))
		_button(choice_row,"ซ้าย",func():_run_activity("turn_left"))
		_button(choice_row,"ขวา",func():_run_activity("turn_right"))
	elif kind == "camera":
		_button(choice_row,"Camera Test",func():_run_activity("camera"))
	elif kind == "motor":
		_button(choice_row,"Motor Test",func():_run_activity("motor"))
	elif kind in ["mentor","engineer"]:
		_button(choice_row,"คุย",_interact)
	elif kind == "board":
		_button(choice_row,"เปิด Quest Journal",_toggle_quest_panel)
	elif kind == "robot":
		_button(choice_row,"ไป Test Field",func():set_scene("field"))

func _clear_choices() -> void:
	if not choice_row:
		return
	for child in choice_row.get_children():
		child.queue_free()

func _run_activity(activity: String) -> void:
	if activity == "tracking":
		_simulate_follow_target_loss()
	var outcomes := {
		"run":"จำลองวิ่งในเลน 8 เมตร · ผ่านกรวย 6 จุด · จบเส้นทาง!",
		"straight":"หุ่นวิ่งตรงผ่าน decision point · รักษาระยะเป้าหมายประมาณ 1.2 เมตร",
		"turn_left":"หุ่นเลี้ยวซ้ายรอบแปลง · กลับเข้าทางวิ่งและจับเป้าหมายต่อได้",
		"turn_right":"หุ่นเลี้ยวขวารอบแปลง · กลับเข้าทางวิ่งและจับเป้าหมายต่อได้",
		"tracking":("re-id ปิดใช้งานอยู่ (REID_ENABLED = false) → ปุ่มนี้ยังไม่มีผลกับ Follow ตอนนี้ กล้อง/YOLO detection ยังทำงานแยกเป็นอิสระที่ POV" if not REID_ENABLED else "จำลองกล้องมองไม่เห็นเป้าหมาย (%d ms) → re-id confidence หล่นต่ำกว่า %.2f → STOP ทันที (proposal = 0); ต้อง Interact ใหม่เพื่อเลือก target อีกครั้ง" % [FORCED_TARGET_LOSS_MS, FOLLOW_MIN_CONFIDENCE]),
		"camera":"จำลองกล้อง webcam ธรรมดา (ไม่ใช่ fisheye): FOV %.0f° · ระยะ %.1f–%.1f m · ตรวจ line-of-sight ด้วย raycast · YOLO person detection: %s" % [CAMERA_FOV_DEG, CAMERA_MIN_RANGE_M, CAMERA_MAX_RANGE_M, ("person %.2f" % camera_last_confidence) if camera_target_visible else "NO DETECTION (%s)" % camera_last_reason],
		"motor":"จำลองมอเตอร์ซ้าย/ขวา · ตอบสนองสมดุล · ไม่มีคำสั่งส่งออกฮาร์ดแวร์"
	}
	total_xp += 10
	var runs: Array = save_data.get("runs",[])
	runs.append({"type":activity,"result":outcomes[activity],"simulation_only":true,"date":Time.get_date_string_from_system()})
	save_data["runs"] = runs.slice(maxi(0,runs.size()-99))
	save_data["simulation_xp"] = total_xp
	_show_dialog("ภารกิจสำเร็จ!  +10 XP",outcomes[activity] + "\n\nผลนี้เป็น Simulation ในเกม ไม่ได้ทดสอบฮาร์ดแวร์จริง")
	_update_hud()
	_save()

func _show_dialog(title: String, message: String) -> void:
	dialog_label.text = title + "\n\n" + message
	dialog_panel.visible = true

func _toggle_quest_panel() -> void:
	quest_panel.visible = not quest_panel.visible

func _refresh_quest_text() -> void:
	if not quest_text:
		return
	var main_quests := quests.filter(func(q): return q.get("quest_type","") == "Main Quest")
	main_quests.sort_custom(func(a,b): return int(a.get("quest_order",999)) < int(b.get("quest_order",999)))
	var content := "[b]MAIN QUEST · 7 CHAPTERS[/b]\n\n"
	for quest in main_quests:
		var status := String(quest.get("status","รอเริ่ม"))
		var mark := "✓" if status == "เสร็จแล้ว" else "◆"
		content += "%s  %02d  %s\n[color=#a9c6ba]%s[/color]\n\n" % [mark,int(quest.get("quest_order",0)),String(quest.get("title","")),status]
	content += "[color=#e8cd84]Side quests และรายละเอียดเพิ่มเติมอยู่ในไฟล์ thesis_data.json[/color]"
	quest_text.text = content

func set_scene(scene_name: String, save: bool = true) -> void:
	var next_scene := "field" if scene_name == "field" else "office"
	if follow_active and next_scene != current_scene_name:
		_stop_follow()
	current_scene_name = next_scene
	office_root.visible = current_scene_name == "office"
	field_root.visible = current_scene_name == "field"
	_set_scene_collisions(office_root, current_scene_name == "office")
	_set_scene_collisions(field_root, current_scene_name == "field")
	if is_instance_valid(player):
		if save:
			player.position = Vector3(-5.5,0,5.8) if current_scene_name == "office" else _grib_cell(2,11)
	active_station = {}
	if hint_label:
		hint_label.text = "เข้าสู่ %s · สำรวจและคุยกับทีมได้เลย" % ("OFFICE" if current_scene_name == "office" else "TEST FIELD")
	if save:
		_save()

func _set_scene_collisions(node: Node, enabled: bool) -> void:
	if node is CollisionObject3D:
		if node == robot_root:
			node.collision_layer = 2 if enabled else 0
			node.collision_mask = 1 if enabled else 0
		else:
			node.collision_layer = 1 if enabled else 0
			node.collision_mask = 1 if enabled else 0
	for child in node.get_children():
		_set_scene_collisions(child, enabled)

func _box(parent: Node, label: String, pos: Vector3, size: Vector3, color: Color, solid: bool = true) -> Node3D:
	var holder: Node3D = StaticBody3D.new() if solid else Node3D.new()
	holder.name = label.replace(" ","")
	holder.position = pos
	parent.add_child(holder)
	var mesh := MeshInstance3D.new()
	var cube := BoxMesh.new()
	cube.size = size
	mesh.mesh = cube
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.92
	mesh.material_override = material
	holder.add_child(mesh)
	if solid:
		var collision := CollisionShape3D.new()
		var box_shape := BoxShape3D.new()
		box_shape.size = size
		collision.shape = box_shape
		holder.add_child(collision)
	return holder

func _desk(parent: Node, pos: Vector3, width: float) -> void:
	_box(parent,"Desk top",pos+Vector3(0,0.82,0),Vector3(width,0.18,1.65),PALETTE.desk)
	for x in [-width*0.38,width*0.38]:
		_box(parent,"Desk leg",pos+Vector3(x,0.4,0),Vector3(0.12,0.8,1.3),PALETTE.wood)
	_box(parent,"Monitor",pos+Vector3(0,1.32,-0.43),Vector3(0.95,0.78,0.12),Color("303b4c"))
	_box(parent,"Screen",pos+Vector3(0,1.35,-0.35),Vector3(0.78,0.56,0.035),PALETTE.screen,false)
	_box(parent,"Keyboard",pos+Vector3(0,0.96,0.35),Vector3(0.78,0.045,0.3),Color("d7d0bd"),false)
	_chair(parent,pos+Vector3(0,0,-1.35))

func _chair(parent: Node, pos: Vector3) -> void:
	_box(parent,"Chair seat",pos+Vector3(0,0.52,0),Vector3(0.85,0.16,0.78),Color("53677b"))
	_box(parent,"Chair back",pos+Vector3(0,1.0,-0.29),Vector3(0.82,0.8,0.16),Color("46596c"))
	_box(parent,"Chair post",pos+Vector3(0,0.24,0),Vector3(0.12,0.45,0.12),PALETTE.metal)

func _plant(parent: Node, pos: Vector3) -> void:
	_box(parent,"Plant pot",pos+Vector3(0,0.28,0),Vector3(0.72,0.55,0.72),Color("a35c49"))
	var foliage := SphereMesh.new()
	foliage.radius = 0.62
	foliage.height = 1.15
	var tree := MeshInstance3D.new()
	tree.mesh = foliage
	tree.position = pos+Vector3(0,1.12,0)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = PALETTE.plant
	tree.material_override = mat
	parent.add_child(tree)

func _npc(parent: Node, label: String, pos: Vector3, shirt: Color, npc_kind: String) -> void:
	var npc := Node3D.new()
	npc.name = label.replace(" ","")
	npc.position = pos
	npc.set_meta("station_id",label)
	npc.set_meta("station_title",label)
	npc.set_meta("station_kind",npc_kind)
	parent.add_child(npc)
	var blocker := StaticBody3D.new()
	blocker.name = "NPC collision"
	var blocker_shape := CollisionShape3D.new()
	var blocker_capsule := CapsuleShape3D.new()
	blocker_capsule.height = 1.9
	blocker_capsule.radius = 0.34
	blocker_shape.shape = blocker_capsule
	blocker_shape.position.y = 0.95
	blocker.add_child(blocker_shape)
	npc.add_child(blocker)
	_box(npc,"NPC body",Vector3(0,0.86,0),Vector3(0.62,0.78,0.42),shirt,false)
	_box(npc,"NPC head",Vector3(0,1.54,0),Vector3(0.48,0.48,0.45),Color("e3b98e"),false)
	_box(npc,"NPC hair",Vector3(0,1.78,-0.03),Vector3(0.5,0.16,0.47),Color("514038"),false)
	_box(npc,"NPC leg",Vector3(-0.17,0.28,0),Vector3(0.2,0.48,0.24),Color("374251"),false)
	_box(npc,"NPC leg",Vector3(0.17,0.28,0),Vector3(0.2,0.48,0.24),Color("374251"),false)
	_world_sign(npc,label,Vector3(0,2.15,0))

func _station(parent: Node, label: String, pos: Vector3, kind: String, color: Color) -> void:
	var station := Node3D.new()
	station.name = label.replace(" ","")
	station.position = pos
	station.set_meta("station_id",label)
	station.set_meta("station_title",label)
	station.set_meta("station_kind",kind)
	parent.add_child(station)
	var station_blocker := StaticBody3D.new()
	station_blocker.name = "Station hitbox"
	var station_collision := CollisionShape3D.new()
	var station_shape := BoxShape3D.new()
	station_shape.size = Vector3(1.74,2.05,1.3)
	station_collision.shape = station_shape
	station_collision.position.y = 1.025
	station_blocker.add_child(station_collision)
	station.add_child(station_blocker)
	_box(station,"Station base",Vector3(0,0.48,0),Vector3(1.6,0.9,1.2),color,false)
	_box(station,"Station top",Vector3(0,0.98,0),Vector3(1.74,0.12,1.3),Color("ded2b8"),false)
	_box(station,"Station beacon",Vector3(0,1.6,0),Vector3(0.24,0.9,0.24),PALETTE.gold,false)
	_world_sign(station,label,Vector3(0,2.3,0))

func _cone(parent: Node, pos: Vector3, color: Color) -> void:
	var mesh := MeshInstance3D.new()
	var cone := CylinderMesh.new()
	cone.top_radius = 0.03
	cone.bottom_radius = 0.28
	cone.height = 0.68
	mesh.mesh = cone
	mesh.position = pos+Vector3(0,0.34,0)
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	mesh.material_override = material
	parent.add_child(mesh)

func _world_sign(parent: Node, text: String, pos: Vector3) -> void:
	var label := Label3D.new()
	label.text = text
	label.position = pos
	label.font_size = 42
	label.pixel_size = 0.006
	label.modulate = Color("fff0ca")
	label.outline_size = 8
	parent.add_child(label)
