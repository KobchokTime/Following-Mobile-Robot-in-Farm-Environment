/* Follower Test Bench: grib experiment tab (2026-11-05, branch claude/robot/grib-local-grid 2125e8b).
   Loaded by index.html; draws into #panel-grib from datasets grib_runs and grib_paths. */
(function () {
  let dash, failed, ready, f2, built = false;
  const PANEL_HTML = "\n    <p class=\"tb-history\">การทดลองเล่น ๆ (5 พ.ย.): แผนที่ตารางรอบตัวหุ่นจาก LiDAR + หาทางด้วย A* (แนวคิด grib จากเกม Godot) · branch <code>claude/robot/grib-local-grid</code> <code>2125e8b</code> · ปิดไว้เป็นค่าเริ่มต้น ไม่เข้า hub ไม่ใช้วันลงพื้นที่ · ผลจาก twin เท่านั้น Codex ยังไม่ review</p>\n    <div class=\"tb-kpis\" id=\"tb-gribkpis\" data-source=\"grib_runs\"></div>\n    <div class=\"tb-grid\">\n      <section class=\"tb-card\" id=\"grib-pass\">\n        <h2>ผ่านกี่รอบ ต่อฉาก (จาก 5)</h2>\n        <p class=\"tb-note\">\"ปิด\" = ค่าวันลงพื้นที่ · \"เปิด\" = <code>grib:=true</code> · กฎผ่านเดิม: เห็นเป้าตอนจบ, ห่าง ≤ 1.5 m, ไม่ชน, เห็นเป้า ≥ 90% ของเวลา</p>\n        <div class=\"tb-chart dash-skeleton\" id=\"tb-gribpass\" data-source=\"grib_runs\"></div>\n      </section>\n      <section class=\"tb-card\" id=\"grib-vis\">\n        <h2>สัดส่วนเวลาที่เห็นเป้า รายรอบ</h2>\n        <p class=\"tb-note\">จุดละ 1 รอบ (seed 0–4) · เส้นประคือเกณฑ์ 0.9 · จุดกลวง = ตก</p>\n        <div class=\"tb-chart dash-skeleton\" id=\"tb-gribvis\" data-source=\"grib_runs\"></div>\n      </section>\n    </div>\n    <section class=\"tb-card\" id=\"grib-map\">\n      <h2>เล่นซ้ำ ปิด vs เปิด (มองจากด้านบน)</h2>\n      <div class=\"tb-controls\">\n        <label class=\"tb-note\" for=\"tb-gribscen\">ฉาก</label>\n        <select class=\"tb-select\" id=\"tb-gribscen\">\n          <option value=\"blind_corner\">blind_corner · คนยืนมุมด้านใน</option>\n          <option value=\"zigzag\">zigzag · เดินส่ายซ้ายขวา</option>\n          <option value=\"pass_by\">pass_by · คนนั่งยองข้างทาง</option>\n          <option value=\"turn_90\">turn_90 · เลี้ยวหักมุม</option>\n          <option value=\"side_step\">side_step · ก้าวออกข้าง</option>\n        </select>\n        <label class=\"tb-note\" for=\"tb-gribseed\">seed</label>\n        <select class=\"tb-select\" id=\"tb-gribseed\"><option>0</option><option>1</option><option>2</option><option>3</option><option>4</option></select>\n      </div>\n      <div class=\"tb-sfgrid\">\n        <div class=\"tb-sfpane\"><h3>ปิด grib <span class=\"tb-pill\" id=\"tb-gribmap-off-res\"></span></h3><div class=\"tb-chart dash-skeleton\" id=\"tb-gribmap-off\" data-source=\"grib_paths\"></div></div>\n        <div class=\"tb-sfpane\"><h3>เปิด grib <span class=\"tb-pill\" id=\"tb-gribmap-on-res\"></span></h3><div class=\"tb-chart dash-skeleton\" id=\"tb-gribmap-on\" data-source=\"grib_paths\"></div></div>\n      </div>\n      <div class=\"tb-controls\">\n        <button type=\"button\" class=\"tb-play\" id=\"tb-gribplay\">▶ เล่น</button>\n        <input type=\"range\" class=\"tb-time\" id=\"tb-gribtime\" min=\"0\" max=\"40\" step=\"0.4\" value=\"40\" aria-label=\"เวลาในฉาก (วินาที)\">\n        <span class=\"tb-clock\" id=\"tb-gribclock\">t = 40.0 s</span>\n      </div>\n      <div class=\"tb-legend\"><span><i style=\"background:var(--cds-chart-status-critical)\"></i>หุ่น (ปิด)</span><span><i id=\"tb-gribleg-on\"></i>หุ่น (เปิด)</span><span><i style=\"border-top:2px dashed var(--color-fg-muted);height:0\"></i>คนเป้าหมาย</span><span>วงเทา = คนที่กล้องไม่เห็น</span></div>\n    </section>\n    <section class=\"tb-card\" id=\"grib-take\">\n      <h2>สรุป</h2>\n      <ul class=\"tb-note\">\n        <li><strong>รวม:</strong> ปิด 21/25 · เปิด 20/25 · ไม่ชนเลยทั้ง 50 รอบ</li>\n        <li><strong>blind_corner:</strong> 1/5 → 2/5 และไม่หลุดตามเลย (ตอนปิดหลุด 2 รอบ ห่างเกือบ 3 m) แต่ 2 รอบที่ผ่านเฉียดเกณฑ์ (0.900, 0.904) อยู่ในช่วงผลแกว่งระหว่างรอบ ข้อจำกัดเดิมยังอยู่: คนอยู่ในวงหมุน 0.40 m</li>\n        <li><strong>zigzag:</strong> 5/5 → 3/5 แย่ลงจริง grib ทำงานตอนเป้าไปขอบภาพทั้งที่ไม่มีอะไรขวาง และเลี้ยวช้ากว่าตัวตามปกติ (~0.3 vs 0.8 rad/s)</li>\n        <li><strong>ความปลอดภัย:</strong> ตัวหยุดหน้าสิ่งกีดขวาง วงหมุน และกฎความเร็วเดิมยังเป็นตัวตัดสินสุดท้าย</li>\n        <li><strong>ข้อจำกัด:</strong> grid ใช้ตำแหน่งจากคำสั่งความเร็ว ยังไม่เทียบล้อจริง · twin เท่านั้น · ไม่ได้รันชุดเต็ม 110 · เพิ่มกฎ 2 ข้อหลังดู blind_corner (ก่อนรันเปรียบเทียบ)</li>\n      </ul>\n    </section>\n  ";
  // ---------- grib experiment (2026-11-05, branch claude/robot/grib-local-grid, datasets grib_runs, grib_paths) ----------
  let GRIB = null;
  const GB = { t: 40, timer: null };
  const GRIBSC = ['blind_corner', 'zigzag', 'pass_by', 'turn_90', 'side_step'];
  function gribColor(v) { return v === 'off' ? 'var(--cds-chart-status-critical)' : dash.colors[2]; }
  function drawGrib() {
    const els = ['tb-gribpass', 'tb-gribvis', 'tb-gribmap-off', 'tb-gribmap-on'].map((id) => document.getElementById(id));
    const rd = dash.data('grib_runs'), pd = dash.data('grib_paths');
    if ([rd, pd].some((x) => x.status === 'error' || x.status === 'connect')) { els.forEach(failed); return; }
    if (rd.status !== 'ok' || pd.status !== 'ok') return;
    GRIB = { runs: rd.data, paths: pd.data };
    document.getElementById('tb-gribleg-on').style.background = dash.colors[2];
    const R = GRIB.runs;
    // KPIs
    const k = document.getElementById('tb-gribkpis');
    const tot = (v) => R.filter((r) => r.variant === v);
    const kpi = (label, value, note) => { const d = document.createElement('div'); d.className = 'tb-kpi';
      d.innerHTML = `<span class="tb-kpi-label"></span><span class="tb-kpi-value"></span><span class="tb-kpi-note"></span>`;
      d.children[0].textContent = label; d.children[1].textContent = value; d.children[2].textContent = note; return d; };
    k.replaceChildren(
      kpi('ปิด grib (ค่าวันลงพื้นที่)', `${tot('off').filter((r) => r.pass).length}/${tot('off').length}`, `ชน ${tot('off').filter((r) => r.contact).length} ครั้ง`),
      kpi('เปิด grib', `${tot('on').filter((r) => r.pass).length}/${tot('on').length}`, `ชน ${tot('on').filter((r) => r.contact).length} ครั้ง`),
      kpi('ข้อสรุป', 'ไม่คุ้ม', 'blind_corner ดีขึ้นนิดเดียว แต่ zigzag แย่ลง'));
    // pass bars
    {
      const el = els[0]; ready(el);
      const W = Math.max(280, el.clientWidth), m = { t: 8, r: 40, b: 8, l: 110 }, bh = 12, gap = 14;
      const H = m.t + GRIBSC.length * (2 * bh + gap) + m.b;
      const svg = d3.create('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
      const x = d3.scaleLinear([0, 5], [m.l, W - m.r]);
      GRIBSC.forEach((s, i) => {
        const y = m.t + i * (2 * bh + gap);
        svg.append('text').attr('x', m.l - 8).attr('y', y + bh + 4).attr('text-anchor', 'end').attr('class', 'tb-strong').text(s);
        ['off', 'on'].forEach((v, j) => {
          const rs = R.filter((r) => r.scenario === s && r.variant === v), p = rs.filter((r) => r.pass).length;
          svg.append('rect').attr('x', m.l).attr('y', y + j * bh).attr('width', x(5) - m.l).attr('height', bh - 2).attr('fill', 'var(--cds-chart-grid)');
          svg.append('rect').attr('x', m.l).attr('y', y + j * bh).attr('width', x(p) - m.l).attr('height', bh - 2).attr('fill', gribColor(v));
          svg.append('text').attr('x', x(5) + 6).attr('y', y + j * bh + bh - 3).attr('font-size', 11).text(`${p}/${rs.length}`);
        });
      });
      el.replaceChildren(svg.node());
    }
    // in-view dots
    {
      const el = els[1]; ready(el);
      const W = Math.max(280, el.clientWidth), m = { t: 8, r: 16, b: 26, l: 110 }, row = 30;
      const H = m.t + GRIBSC.length * row + m.b;
      const svg = d3.create('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`);
      const x = d3.scaleLinear([0.3, 1], [m.l, W - m.r]);
      svg.append('line').attr('x1', x(0.9)).attr('x2', x(0.9)).attr('y1', m.t).attr('y2', H - m.b).attr('stroke', 'var(--color-fg-muted)').attr('stroke-dasharray', '4 4');
      svg.append('g').attr('transform', `translate(0,${H - m.b})`).call(d3.axisBottom(x).ticks(7).tickFormat(d3.format('.1f')));
      GRIBSC.forEach((s, i) => {
        const y = m.t + i * row + row / 2;
        svg.append('text').attr('x', m.l - 8).attr('y', y + 4).attr('text-anchor', 'end').attr('class', 'tb-strong').text(s);
        R.filter((r) => r.scenario === s).forEach((r) => {
          const dy = r.variant === 'off' ? -6 : 6;
          svg.append('circle').attr('cx', x(Math.max(0.3, r.vis))).attr('cy', y + dy).attr('r', 4.5)
            .attr('fill', r.pass ? gribColor(r.variant) : 'none').attr('stroke', gribColor(r.variant)).attr('stroke-width', 1.5)
            .append('title').text(`${r.variant} s${r.seed}: เห็นเป้า ${r.vis} · ห่างตอนจบ ${r.final_gap_m} m · ${r.pass ? 'ผ่าน' : 'ตก'}`);
        });
      });
      el.replaceChildren(svg.node());
    }
    drawGribMap();
  }
  function drawGribMap() {
    if (!GRIB) return;
    const scen = document.getElementById('tb-gribscen').value, seed = document.getElementById('tb-gribseed').value;
    document.getElementById('tb-gribclock').textContent = `t = ${GB.t.toFixed(1)} s`;
    const ids = ['off', 'on'].map((v) => `${scen}-${v}-${seed}`);
    const P = GRIB.paths.filter((p) => p[0] === ids[0] || p[0] === ids[1]);
    const tmax = d3.max(P, (p) => p[1]) || 40;
    const slider = document.getElementById('tb-gribtime'); slider.max = String(tmax);
    if (GB.t > tmax) { GB.t = tmax; slider.value = String(tmax); }
    const xs = P.flatMap((p) => [p[2], p[5], ...(p.length > 7 ? [p[7]] : [])]), ys = P.flatMap((p) => [p[3], p[6], ...(p.length > 7 ? [p[8]] : [])]);
    if (!xs.length) return;
    const [x0, x1] = d3.extent(xs), [y0, y1] = d3.extent(ys);
    ['off', 'on'].forEach((v, i) => {
      const el = document.getElementById(`tb-gribmap-${v}`); ready(el);
      const sum = GRIB.runs.find((r) => r.run_id === ids[i]);
      const res = document.getElementById(`tb-gribmap-${v}-res`);
      res.textContent = sum ? `${sum.pass ? 'ผ่าน' : 'ตก'} · ${sum.contact ? 'ชน' : 'ไม่ชน'} · เห็นเป้า ${Math.round(100 * sum.vis)}% · ห่างตอนจบ ${f2(sum.final_gap_m)} m` : 'ไม่มีข้อมูล';
      res.className = 'tb-pill ' + (sum ? (sum.contact ? 'tb-bad' : sum.pass ? 'tb-ok' : 'tb-warn') : '');
      const rows = P.filter((p) => p[0] === ids[i] && p[1] <= GB.t + 1e-6);
      const W = Math.max(240, el.clientWidth), pad = 16, span = 0.8;
      const k0 = (W - 2 * pad) / ((x1 - x0) + span);
      const H = Math.round(Math.min(380, Math.max(200, ((y1 - y0) + span) * k0 + 2 * pad)));
      const k = Math.min(k0, (H - 2 * pad) / ((y1 - y0) + span));
      const X = (q) => pad + (q - x0 + span / 2) * k, Y = (q) => H - pad - (q - y0 + span / 2) * k;
      const svg = d3.create('svg').attr('width', W).attr('height', H).attr('viewBox', `0 0 ${W} ${H}`);
      d3.range(Math.ceil(x0), Math.floor(x1) + 1).forEach((g) => svg.append('line').attr('x1', X(g)).attr('x2', X(g)).attr('y1', 0).attr('y2', H).attr('stroke', 'var(--cds-chart-grid)'));
      d3.range(Math.ceil(y0), Math.floor(y1) + 1).forEach((g) => svg.append('line').attr('y1', Y(g)).attr('y2', Y(g)).attr('x1', 0).attr('x2', W).attr('stroke', 'var(--cds-chart-grid)'));
      const now = rows[rows.length - 1], c = gribColor(v);
      if (now && now.length > 7) {
        svg.append('circle').attr('cx', X(now[7])).attr('cy', Y(now[8])).attr('r', 0.2 * k).attr('fill', 'var(--color-fg-muted)').attr('opacity', 0.35).attr('stroke', 'var(--color-fg-muted)');
      }
      const line = (a, b) => d3.line().x((p) => X(p[a])).y((p) => Y(p[b]));
      svg.append('path').attr('d', line(5, 6)(rows) || '').attr('fill', 'none').attr('stroke', 'var(--color-fg-muted)').attr('stroke-dasharray', '4 4').attr('stroke-width', 1.5);
      svg.append('path').attr('d', line(2, 3)(rows) || '').attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2.5).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');
      if (now) {
        svg.append('rect').attr('x', -0.26 * k).attr('y', -0.235 * k).attr('width', 0.52 * k).attr('height', 0.47 * k)
          .attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2).attr('transform', `translate(${X(now[2])},${Y(now[3])}) rotate(${-now[4]})`);
        svg.append('circle').attr('cx', X(now[5])).attr('cy', Y(now[6])).attr('r', 5).attr('fill', 'var(--color-fg-muted)');
      }
      el.replaceChildren(svg.node());
    });
  }

  function build() {
    document.getElementById('panel-grib').innerHTML = PANEL_HTML;
  ['tb-gribscen', 'tb-gribseed'].forEach((id) => document.getElementById(id).addEventListener('change', () => { GB.t = 99; drawGribMap(); }));
  document.getElementById('tb-gribtime').addEventListener('input', (e) => { GB.t = +e.target.value; drawGribMap(); });
  document.getElementById('tb-gribplay').addEventListener('click', (e) => {
    if (GB.timer) { clearInterval(GB.timer); GB.timer = null; e.target.textContent = '▶ เล่น'; return; }
    const s = document.getElementById('tb-gribtime');
    if (GB.t >= +s.max - 1e-6) GB.t = 0;
    e.target.textContent = '❚❚ หยุด';
    GB.timer = setInterval(() => {
      GB.t = Math.min(+s.max, GB.t + 0.4); s.value = String(GB.t); drawGribMap();
      if (GB.t >= +s.max - 1e-6) { clearInterval(GB.timer); GB.timer = null; e.target.textContent = '▶ เล่น'; }
    }, 100);
  });


    built = true;
  }
  window.GribTab = { draw(ctx) { ({ dash, failed, ready, f2 } = ctx); if (!built) build(); drawGrib(); } };
})();
