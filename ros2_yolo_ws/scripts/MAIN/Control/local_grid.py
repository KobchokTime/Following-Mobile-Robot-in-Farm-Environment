"""Rolling local occupancy grid and A* planner for the follower's "grib" option. Pure Python, no ROS imports.

The idea comes from the Thesis Desk Godot game (tools/thesis_desk/godot_game/main.gd, the grib_* functions):
LiDAR hits are scored per cell and the scores decay, so only returns that keep coming back mark a cell as
blocked; A* then finds a way through the walkable cells. Here the grid is local and short-lived: it rolls with
the robot (only cells within size_m / 2 of it are kept) and a cell clears again within about a second of the
returns leaving it, because people move.

Cells are keyed by integer (ix, iy) in the frame the scans are given in (the follower's dead-reckoned frame), so
the grid does not need re-indexing as the robot moves. All distances are metres.
"""
import heapq
import math


class LocalGrid:
    def __init__(self, cell_m=0.1, size_m=6.0, hit=1.0, decay_per_s=2.0, threshold=2.0, max_score=4.0,
                 inflate_m=0.25, clearance_m=0.3, clearance_cost=3.0):
        """hit is added to a cell once per scan that has a return in it; scores lose decay_per_s each second and
        are capped at max_score, so a cell blocked for long clears (max_score - threshold) / decay_per_s seconds
        after its returns stop. A cell is blocked at threshold or above. inflate_m: blocked cells grow by this
        radius (the robot's half width), and nothing inside it is walkable. Within a further clearance_m a step
        costs extra (clearance_cost per metre at the inflated edge, falling to 0), so paths keep off people
        where there is room."""
        self.cell = float(cell_m)
        self.half = float(size_m) / 2.0
        self.hit, self.decay, self.threshold, self.max_score = hit, decay_per_s, threshold, max_score
        self.inflate, self.clearance, self.clearance_cost = inflate_m, clearance_m, clearance_cost
        self.scores = {}
        self.time = None
        self.centre = (0.0, 0.0)
        self.last_unwalkable = None  # the unwalkable cells of the last plan, for waypoint()

    # ---------- cells ----------
    def cell_of(self, x, y):
        return int(math.floor(x / self.cell)), int(math.floor(y / self.cell))

    def centre_of(self, c):
        return (c[0] + 0.5) * self.cell, (c[1] + 0.5) * self.cell

    def in_window(self, c):
        x, y = self.centre_of(c)
        return abs(x - self.centre[0]) <= self.half and abs(y - self.centre[1]) <= self.half

    # ---------- scoring ----------
    def update(self, points, now, centre, exclude=None, exclude_r=0.0):
        """Score one scan. points: returns (x, y) in the grid frame; centre: the robot (x, y) the window rolls
        with; returns within exclude_r of exclude (the target being followed) are not scored."""
        if self.time is not None:
            dec = self.decay * min(5.0, max(0.0, now - self.time))
            self.scores = {c: s - dec for c, s in self.scores.items() if s - dec > 0.0}
        self.time = now
        self.centre = (float(centre[0]), float(centre[1]))
        hits = set()
        for x, y in points:
            if exclude is not None and math.hypot(x - exclude[0], y - exclude[1]) <= exclude_r:
                continue
            c = self.cell_of(x, y)
            if self.in_window(c):
                hits.add(c)
        for c in hits:
            self.scores[c] = min(self.max_score, self.scores.get(c, 0.0) + self.hit)
        self.scores = {c: s for c, s in self.scores.items() if self.in_window(c)}

    def blocked(self):
        """Cells whose score has reached the threshold."""
        return {c for c, s in self.scores.items() if s >= self.threshold}

    def distance_field(self, reach_m):
        """Distance (m) from each cell within reach_m of a blocked cell to the nearest blocked cell's centre."""
        r = int(math.ceil(reach_m / self.cell))
        offsets = [(dx, dy, math.hypot(dx, dy) * self.cell) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                   if math.hypot(dx, dy) * self.cell <= reach_m + 1e-9]
        field = {}
        for bx, by in self.blocked():
            for dx, dy, d in offsets:
                c = (bx + dx, by + dy)
                if d < field.get(c, math.inf):
                    field[c] = d
        return field

    def inflated(self):
        """Cells within inflate_m of a blocked cell (the blocked cells included): not walkable."""
        return {c for c, d in self.distance_field(self.inflate).items() if d <= self.inflate + 1e-9}

    # ---------- planning ----------
    def line_clear(self, a, b, unwalkable):
        """True if the straight segment a -> b (grid frame) crosses no unwalkable cell (sampled every cell / 2)."""
        n = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / (0.5 * self.cell))))
        start = self.cell_of(*a)
        for k in range(1, n + 1):
            c = self.cell_of(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
            if c != start and c in unwalkable:
                return False
        return True

    def plan(self, start, goal, goal_r=0.0, max_expand=20000):
        """A* from start to goal (both (x, y) in the grid frame) through walkable cells, 8-connected.

        Returns the path as cell centres, start first, or None when no walkable cell within goal_r of the goal
        can be reached. The start cell is always walkable (the robot is there). A goal outside the window is
        pulled in along the line from the robot to it. Steps near blocked cells cost extra (clearance_cost)."""
        gx, gy = goal
        cx, cy = self.centre
        lim = self.half - self.cell
        if abs(gx - cx) > lim or abs(gy - cy) > lim:
            k = lim / max(abs(gx - cx), abs(gy - cy))
            gx, gy = cx + (gx - cx) * k, cy + (gy - cy) * k
        field = self.distance_field(self.inflate + self.clearance)
        bad = {c for c, d in field.items() if d <= self.inflate + 1e-9}
        self.last_unwalkable = bad
        s = self.cell_of(*start)
        g = self.cell_of(gx, gy)
        gr = max(goal_r, 0.75 * self.cell)  # the cell holding the goal is always within this

        def at_goal(c):
            x, y = self.centre_of(c)
            return math.hypot(x - gx, y - gy) <= gr + 1e-9

        def h(c):
            x, y = self.centre_of(c)
            return max(0.0, math.hypot(x - gx, y - gy) - gr)

        def extra(c):
            d = field.get(c)
            if d is None or self.clearance <= 0.0:
                return 0.0
            return self.clearance_cost * max(0.0, 1.0 - (d - self.inflate) / self.clearance)

        steps = [(dx, dy, math.hypot(dx, dy) * self.cell) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        best = {s: 0.0}
        came = {}
        heap = [(h(s), 0.0, s)]
        expanded = 0
        while heap and expanded < max_expand:
            _, cost, c = heapq.heappop(heap)
            if cost > best.get(c, math.inf):
                continue
            expanded += 1
            if at_goal(c) and (c == s or c not in bad):
                path = [c]
                while path[-1] in came:
                    path.append(came[path[-1]])
                return [self.centre_of(p) for p in reversed(path)]
            for dx, dy, step in steps:
                n = (c[0] + dx, c[1] + dy)
                if n in bad or not self.in_window(n):
                    continue
                if dx and dy and ((c[0] + dx, c[1]) in bad or (c[0], c[1] + dy) in bad):
                    continue  # no squeezing diagonally between two unwalkable cells
                nc = cost + step * (1.0 + extra(n))
                if nc < best.get(n, math.inf):
                    best[n] = nc
                    came[n] = c
                    heapq.heappush(heap, (nc + h(n), nc, n))
        return None

    def waypoint(self, start, path, lookahead_m=1.0):
        """The first waypoint to steer at: the farthest point of path, no more than lookahead_m along it, that
        start reaches in a straight line crossing no unwalkable cell. None for a path of one cell."""
        if not path or len(path) < 2:
            return None
        bad = self.last_unwalkable if self.last_unwalkable is not None else self.inflated()
        along, pick = 0.0, path[1]
        prev = path[0]
        for p in path[1:]:
            along += math.hypot(p[0] - prev[0], p[1] - prev[1])
            prev = p
            if along > lookahead_m + 1e-9:
                break
            if self.line_clear(start, p, bad):
                pick = p
        return pick


def path_length(start, path):
    """Length (m) from start along path."""
    total, prev = 0.0, start
    for p in path[1:]:
        total += math.hypot(p[0] - prev[0], p[1] - prev[1])
        prev = p
    return total
