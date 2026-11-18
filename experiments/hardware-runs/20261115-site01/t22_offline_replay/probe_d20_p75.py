"""Per-callback fusion state around the remaining wrong turn (delay 20 ms, phase 75 ms)."""
import sys
import offline_replay as R

LO, HI = 586.0, 588.25
rows = []
orig_load = R.load


def rel():
    return (R.CLOCK["ns"] - R.META["t0"]) * 1e-9 if "t0" in R.META else -1


def load(path, name):
    m = orig_load(path, name)
    if name == "replay_sync_fusion":
        N = m.SyncFusionNode
        f_sync = N.try_sync_from_yolo
        def try_sync(self, ty, cx, cy, sector_id, *a, **k):
            n_before = len(R.BUS.out["/synced_target"])
            latch0 = self.camera_lidar_conflict
            # recompute the early-exit reason
            why = ""
            if not self.buf_lidar or not self.lidar_angles:
                why = "no-lidar-buf"
            else:
                best_dt = min(abs(tl - ty) for tl, _ in self.buf_lidar)
                if best_dt > self.max_dt:
                    why = f"best_dt {best_dt*1000:.0f}ms > max_dt {self.max_dt*1000:.0f}ms"
            pred = ""
            if self.gate.locked and self.gate.t is not None:
                pb, pr = self.gate._predict(ty)
                b = m.camera_bearing_rad(cx, self.image_width, self.camera_hfov_deg)
                own = m.box_range(self.scan_points, b)
                pred = f"pred {m.math.degrees(pb):+.1f}deg {pr:.2f}m gate.t-age {ty-self.gate.t:.2f}s box_range {own} edge {m.math.degrees(self.edge_rad):.0f}"
            r = f_sync(self, ty, cx, cy, sector_id, *a, **k)
            why = why or pred
            if LO <= rel() <= HI:
                pub = R.BUS.out["/synced_target"][n_before:]
                rows.append((round(rel(), 3), "yolo", f"cx={cx} b={m.math.degrees(m.camera_bearing_rad(cx, self.image_width, self.camera_hfov_deg)):+.1f}",
                             why, f"latch {latch0}->{self.camera_lidar_conflict}", f"locked {self.gate.locked}",
                             f"pub {[d[:3] for _, d in pub]}"))
            return r
        N.try_sync_from_yolo = try_sync
        f_tr = N.track_with_lidar
        def track(self, assisted=None):
            n_before = len(R.BUS.out["/synced_target"])
            pb0 = m.math.degrees(self.gate._predict(self.now_sec())[0]) if self.gate.locked and self.gate.t is not None else None
            lb = m.math.degrees(self.last_camera_bearing) if self.last_camera_bearing is not None else None
            r = f_tr(self, assisted)
            pub = R.BUS.out["/synced_target"][n_before:]
            if LO <= rel() <= HI and pub:
                rows.append((round(rel(), 3), "track", f"assisted={assisted is not None}", "",
                             f"latch {self.camera_lidar_conflict}", f"locked {self.gate.locked}",
                             f"pub {[d[:3] for _, d in pub]} since_fix {self.now_sec()-self.last_camera_fix:.2f}s pred_before {pb0:+.1f} last_cam_b {lb:+.1f} covered {self.covered_fix == self.last_camera_fix}"))
            return r
        N.track_with_lidar = track
    return m


R.load = load
sys.argv = ["offline_replay.py", r"C:\Users\Time\Documents\robot_day_data\20261115-site01\20261115T060903Z_e6_session",
            "--code", sys.argv[1], "--preset", "e6", "--yolo-delay-ms", "20", "--timer-phase-ms", "75"]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    R.main()
for r in rows:
    print(*r, sep=" | ")
