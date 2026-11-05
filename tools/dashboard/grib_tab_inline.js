const gribDraw = (() => {
  let built = false;
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
    const P = GRIB.paths.filter((p) => p.run === ids[0] || p.run === ids[1]);
    const tmax = d3.max(P, (p) => p.t) || 40;
    const slider = document.getElementById('tb-gribtime'); slider.max = String(tmax);
    if (GB.t > tmax) { GB.t = tmax; slider.value = String(tmax); }
    const xs = P.flatMap((p) => [p.rx, p.tx, ...(p.ox != null ? [p.ox] : [])]), ys = P.flatMap((p) => [p.ry, p.ty, ...(p.oy != null ? [p.oy] : [])]);
    if (!xs.length) return;
    const [x0, x1] = d3.extent(xs), [y0, y1] = d3.extent(ys);
    ['off', 'on'].forEach((v, i) => {
      const el = document.getElementById(`tb-gribmap-${v}`); ready(el);
      const sum = GRIB.runs.find((r) => r.run_id === ids[i]);
      const res = document.getElementById(`tb-gribmap-${v}-res`);
      res.textContent = sum ? `${sum.pass ? 'ผ่าน' : 'ตก'} · ${sum.contact ? 'ชน' : 'ไม่ชน'} · เห็นเป้า ${Math.round(100 * sum.vis)}% · ห่างตอนจบ ${f2(sum.final_gap_m)} m` : 'ไม่มีข้อมูล';
      res.className = 'tb-pill ' + (sum ? (sum.contact ? 'tb-bad' : sum.pass ? 'tb-ok' : 'tb-warn') : '');
      const rows = P.filter((p) => p.run === ids[i] && p.t <= GB.t + 1e-6);
      const W = Math.max(240, el.clientWidth), pad = 16, span = 0.8;
      const k0 = (W - 2 * pad) / ((x1 - x0) + span);
      const H = Math.round(Math.min(380, Math.max(200, ((y1 - y0) + span) * k0 + 2 * pad)));
      const k = Math.min(k0, (H - 2 * pad) / ((y1 - y0) + span));
      const X = (q) => pad + (q - x0 + span / 2) * k, Y = (q) => H - pad - (q - y0 + span / 2) * k;
      const svg = d3.create('svg').attr('width', W).attr('height', H).attr('viewBox', `0 0 ${W} ${H}`);
      d3.range(Math.ceil(x0), Math.floor(x1) + 1).forEach((g) => svg.append('line').attr('x1', X(g)).attr('x2', X(g)).attr('y1', 0).attr('y2', H).attr('stroke', 'var(--cds-chart-grid)'));
      d3.range(Math.ceil(y0), Math.floor(y1) + 1).forEach((g) => svg.append('line').attr('y1', Y(g)).attr('y2', Y(g)).attr('x1', 0).attr('x2', W).attr('stroke', 'var(--cds-chart-grid)'));
      const now = rows[rows.length - 1], c = gribColor(v);
      if (now && now.ox != null) {
        svg.append('circle').attr('cx', X(now.ox)).attr('cy', Y(now.oy)).attr('r', 0.2 * k).attr('fill', 'var(--color-fg-muted)').attr('opacity', 0.35).attr('stroke', 'var(--color-fg-muted)');
      }
      const line = (a, b) => d3.line().x((p) => X(p[a])).y((p) => Y(p[b]));
      svg.append('path').attr('d', line('tx', 'ty')(rows) || '').attr('fill', 'none').attr('stroke', 'var(--color-fg-muted)').attr('stroke-dasharray', '4 4').attr('stroke-width', 1.5);
      svg.append('path').attr('d', line('rx', 'ry')(rows) || '').attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2.5).attr('stroke-linecap', 'round').attr('stroke-linejoin', 'round');
      if (now) {
        svg.append('rect').attr('x', -0.26 * k).attr('y', -0.235 * k).attr('width', 0.52 * k).attr('height', 0.47 * k)
          .attr('fill', 'none').attr('stroke', c).attr('stroke-width', 2).attr('transform', `translate(${X(now.rx)},${Y(now.ry)}) rotate(${-now.ryaw})`);
        svg.append('circle').attr('cx', X(now.tx)).attr('cy', Y(now.ty)).attr('r', 5).attr('fill', 'var(--color-fg-muted)');
      }
      el.replaceChildren(svg.node());
    });
  }

  function build(html) {
    document.getElementById('panel-grib').innerHTML = html;
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
  return () => {
    const tx = dash.data('grib_text');
    if (tx.status === 'error' || tx.status === 'connect') { const m = document.getElementById('tb-gribload'); if (m) m.textContent = 'Failed to load'; return; }
    if (tx.status !== 'ok' || !tx.data.length) return;
    if (!built) build(tx.data[0].html);
    drawGrib();
  };
})();
