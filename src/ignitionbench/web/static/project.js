import { lineChart } from "./charts.js";
import { MotorViewer } from "./viewer3d.js";

const $ = (id) => document.getElementById(id);
const fmt = (x, d = 1) =>
  Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const debounce = (fn, ms) => {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

const GRAIN_IDS = [
  "segments", "outer_d_mm", "core_d_mm", "length_mm",
  "slit_count", "slit_depth_mm", "slit_width_mm", "slit_length_mm", "slit_taper_pct",
];
const NOZZLE_IDS = ["throat_d_mm", "half_angle_deg"];
const CUSTOM_IDS = ["name", "a_mm_mpa", "n", "density", "gamma", "temp_k", "molar_g", "min_mpa", "max_mpa"];

let project = null;
let library = {};
let viewer = null;
let lastDesign = null;
let sim = null;
let simStale = true;
let charts = { thrust: null, pressure: null };

// ---------- state <-> DOM ----------

function stateToForms() {
  const p = project.propellant;
  document.querySelectorAll("#propMode .seg").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === p.mode));
  $("libraryForm").hidden = p.mode !== "library";
  $("customForm").hidden = p.mode !== "custom";
  $("propellant").value = p.key;
  for (const f of CUSTOM_IDS) $(`c_${f}`).value = p.custom[f];
  for (const f of GRAIN_IDS) $(f).value = project.grain[f];
  for (const f of NOZZLE_IDS) $(f).value = project.nozzle[f];
  $("projectName").textContent = project.name;
}

function formsToState() {
  const mode = document.querySelector("#propMode .seg.active").dataset.mode;
  project.propellant.mode = mode;
  project.propellant.key = $("propellant").value || project.propellant.key;
  for (const f of CUSTOM_IDS) {
    const v = $(`c_${f}`).value;
    project.propellant.custom[f] = f === "name" ? v : parseFloat(v);
  }
  for (const f of GRAIN_IDS) project.grain[f] = parseFloat($(f).value);
  for (const f of NOZZLE_IDS) project.nozzle[f] = parseFloat($(f).value);
}

const save = debounce(async () => {
  $("saveState").textContent = "Saving…";
  $("saveState").classList.add("saving");
  await fetch(`/api/projects/${window.PROJECT_ID}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: project.name,
      propellant: project.propellant,
      grain: project.grain,
      nozzle: project.nozzle,
      summary: project.summary,
    }),
  });
  $("saveState").textContent = "Saved";
  $("saveState").classList.remove("saving");
}, 400);

// ---------- propellant tab ----------

function designPayload() {
  return { propellant: project.propellant, grain: project.grain, nozzle: project.nozzle };
}

function burnRateSamples() {
  // returns {p: psi[], r: mm/s[]} for the active propellant
  const ps = [], rs = [];
  const sample = (pMin, pMax, a, n) => {
    for (let i = 0; i <= 30; i++) {
      const p = pMin + (i / 30) * (pMax - pMin);
      ps.push(p / 6895);
      rs.push(a * Math.pow(p, n) * 1000);
    }
  };
  if (project.propellant.mode === "library") {
    const lib = library[project.propellant.key];
    if (!lib) return null;
    for (const s of lib.segments) sample(s.min, s.max, s.a, s.n);
  } else {
    const c = project.propellant.custom;
    if (!(c.a_mm_mpa > 0) || !(c.n > 0) || !(c.min_mpa < c.max_mpa)) return null;
    const aSI = (c.a_mm_mpa * 1e-3) / Math.pow(1e6, c.n);
    sample(c.min_mpa * 1e6, c.max_mpa * 1e6, aSI, c.n);
  }
  return { p: ps, r: rs };
}

function renderPropellantTab() {
  const meta = $("libMeta");
  if (project.propellant.mode === "library") {
    const lib = library[project.propellant.key];
    if (lib) {
      meta.innerHTML = `
        <tr><td>Density</td><td>${fmt(lib.density, 0)} kg/m³</td></tr>
        <tr><td>c* characteristic velocity</td><td>${fmt(lib.c_star, 0)} m/s</td></tr>
        <tr><td>γ exhaust</td><td>${fmt(lib.gamma, 3)}</td></tr>
        <tr><td>Flame temperature</td><td>${fmt(lib.temp_k, 0)} K</td></tr>
        <tr><td>Validated range</td><td>${fmt(lib.min_pressure / 6895, 0)}–${fmt(lib.max_pressure / 6895, 0)} psi</td></tr>
        <tr><td>Burn-rate segments</td><td>${lib.segments.length}</td></tr>`;
    }
  }
  const samples = burnRateSamples();
  if (samples) {
    lineChart($("burnRateChart"), {
      x: samples.p, y: samples.r,
      xLabel: "chamber pressure (psi)", yLabel: "mm/s",
      yFmt: (v) => fmt(v, 1),
    });
    $("propSummary").textContent =
      project.propellant.mode === "library"
        ? "Piecewise Vieille's-law fit from published strand-burner measurements."
        : "Single-segment Vieille's law from your a and n values.";
  }
}

// ---------- motor tab ----------

async function refreshDesign() {
  formsToState();
  save();
  renderPropellantTab();
  simStale = true;

  const res = await fetch("/api/design", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(designPayload()),
  });
  const d = await res.json();
  const banner = $("designError");

  if (!res.ok) {
    banner.textContent = "⚠ " + d.error;
    banner.hidden = false;
    $("classBadge").textContent = "—";
    $("certChip").hidden = true;
    lastDesign = null;
    return;
  }
  banner.hidden = true;
  lastDesign = d;

  $("v_kn").textContent = fmt(d.kn, 0);
  $("v_pc").textContent = fmt(d.chamber_pressure_psi, 0) + " psi";
  $("s_pc").textContent = fmt(d.chamber_pressure_mpa, 2) + " MPa";
  $("v_thrust").textContent = fmt(d.thrust_n, 0) + " N";
  $("v_class").textContent = d.motor_class;
  $("s_cert").textContent = d.certification.level === "none" ? "no cert needed" : d.certification.level + " cert";

  $("n_eps").textContent = fmt(d.expansion_ratio, 2) + " : 1";
  $("n_exit").textContent = fmt(d.exit_d_mm, 1) + " mm";
  $("n_div").textContent = fmt(d.divergent_length_mm, 1) + " mm";
  $("n_mass").textContent = fmt(d.propellant_mass_g, 0) + " g";
  $("n_p2t").textContent = fmt(d.port_to_throat, 2);

  $("classBadge").textContent = d.motor_class;
  const chip = $("certChip");
  chip.hidden = false;
  chip.className = `cert-chip ${d.certification.level}`;
  chip.textContent = d.certification.text;

  const list = $("warnings");
  list.innerHTML = "";
  if (d.warnings.length === 0) {
    list.innerHTML = `<li class="ok">✓ No warnings — design is inside validated data and geometry guidelines.</li>`;
  } else {
    for (const w of d.warnings) {
      const li = document.createElement("li");
      li.className = w.level;
      li.textContent = (w.level === "serious" ? "▲ " : "△ ") + w.text;
      list.appendChild(li);
    }
  }

  project.summary = {
    motor_class: d.motor_class,
    total_impulse_ns: d.total_impulse_ns,
    thrust_n: d.thrust_n,
  };

  try {
    viewer.rebuild(d.geometry);
  } catch (err) {
    console.error("3D viewer rebuild failed", err);
  }
  drawNozzleSection(d.geometry);
}

// ---------- nozzle section drawing ----------

function drawNozzleSection(geo) {
  const W = 640, H = 300, yc = 132, wall = 3;
  const Rin = geo.outer_d_mm / 2;
  const rt = geo.throat_d_mm / 2;
  const re = geo.exit_d_mm / 2;
  const conv = Rin - rt; // 45° convergent
  const div = geo.divergent_length_mm;
  const total = conv + div;
  const maxR = Math.max(Rin, re) + wall;
  const s = Math.min((yc - 46) / maxR, 340 / total);
  const x0 = (W - total * s) / 2 + 10;
  const xt = x0 + conv * s;
  const xe = x0 + total * s;
  const yBot = yc + maxR * s;

  const C = window.ibColor;
  const DIM = C("nz-dim"), INK = C("nz-ink"), PROFILE = C("nz-profile");
  const mono = `font-family="ui-monospace,Menlo,monospace" font-size="10.5" fill="${INK}"`;
  const el = [];

  el.push(`<defs>
    <marker id="dimArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M0,1.5L10,5L0,8.5Z" fill="${DIM}"/>
    </marker>
    <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="${C("nz-hatch")}" stroke-width="1.1"/>
    </pattern>
  </defs>`);

  // centerline (dash-dot)
  el.push(`<line x1="${x0 - 34}" y1="${yc}" x2="${xe + 34}" y2="${yc}" stroke="${C("nz-center")}" stroke-width="1" stroke-dasharray="13 4 3 4"/>`);

  // hatched section solids, top and bottom
  for (const m of [1, -1]) {
    const pts = [
      [x0, yc - m * (Rin + wall) * s],
      [xe, yc - m * (re + wall) * s],
      [xe, yc - m * re * s],
      [xt, yc - m * rt * s],
      [x0, yc - m * Rin * s],
    ].map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ");
    el.push(`<polygon points="${pts}" fill="url(#hatch)" stroke="${PROFILE}" stroke-width="1.5" stroke-linejoin="round"/>`);
  }

  const dimLine = (x1, y1, x2, y2) =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${DIM}" stroke-width="1" marker-start="url(#dimArrow)" marker-end="url(#dimArrow)"/>`;
  const extLine = (x1, y1, x2, y2) =>
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${DIM}" stroke-width="0.75"/>`;

  // Ø inlet — vertical dimension left of the inlet face
  const xd0 = x0 - 26;
  el.push(extLine(x0 - 4, yc - Rin * s, xd0 - 4, yc - Rin * s));
  el.push(extLine(x0 - 4, yc + Rin * s, xd0 - 4, yc + Rin * s));
  el.push(dimLine(xd0, yc - Rin * s, xd0, yc + Rin * s));
  el.push(`<text x="${xd0 - 6}" y="${yc + 3.5}" text-anchor="end" ${mono}>⌀${fmt(geo.outer_d_mm, 1)}</text>`);

  // Ø exit — vertical dimension right of the exit face
  const xd1 = xe + 26;
  el.push(extLine(xe + 4, yc - re * s, xd1 + 4, yc - re * s));
  el.push(extLine(xe + 4, yc + re * s, xd1 + 4, yc + re * s));
  el.push(dimLine(xd1, yc - re * s, xd1, yc + re * s));
  el.push(`<text x="${xd1 + 6}" y="${yc + 3.5}" ${mono}>⌀${fmt(geo.exit_d_mm, 1)}</text>`);

  // Ø throat — arrows across the gap plus a leader to a label above
  el.push(dimLine(xt, yc - rt * s, xt, yc + rt * s));
  el.push(extLine(xt, yc - rt * s, xt + 26, yc - maxR * s - 12));
  el.push(`<text x="${xt + 29}" y="${yc - maxR * s - 9}" ${mono}>⌀${fmt(geo.throat_d_mm, 1)} throat</text>`);

  // lengths below: convergent + divergent, then overall
  const y1 = yBot + 24, y2 = y1 + 24;
  el.push(extLine(x0, yBot + 4, x0, y2 + 4));
  el.push(extLine(xt, yc + rt * s + 4, xt, y1 + 4));
  el.push(extLine(xe, yBot + 4, xe, y2 + 4));
  el.push(dimLine(x0, y1, xt, y1));
  el.push(`<text x="${(x0 + xt) / 2}" y="${y1 - 4}" text-anchor="middle" ${mono}>${fmt(conv, 1)}</text>`);
  el.push(dimLine(xt, y1, xe, y1));
  el.push(`<text x="${(xt + xe) / 2}" y="${y1 - 4}" text-anchor="middle" ${mono}>${fmt(div, 1)}</text>`);
  el.push(dimLine(x0, y2, xe, y2));
  el.push(`<text x="${(x0 + xe) / 2}" y="${y2 - 4}" text-anchor="middle" ${mono}>${fmt(total, 1)}</text>`);

  // angle callouts on the top wall of each cone
  el.push(`<text x="${x0 + conv * s * 0.35}" y="${yc - (Rin - conv * 0.35) * s - 8}" ${mono} fill="${C("ink-2")}">45°</text>`);
  el.push(`<text x="${xt + div * s * 0.5}" y="${yc - (rt + (re - rt) * 0.5) * s - 10}" ${mono} fill="${C("ink-2")}">α ${fmt(geo.half_angle_deg, 0)}°</text>`);

  el.push(`<text x="${W - 8}" y="${H - 8}" text-anchor="end" font-size="10" fill="${C("ink-3")}">SECTION A-A · conical de Laval · ε ${fmt((re * re) / (rt * rt), 2)}:1</text>`);

  $("nozzleSection").innerHTML = el.join("");
}

// ---------- simulation tab ----------

async function runSimulation() {
  const res = await fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(designPayload()),
  });
  const d = await res.json();
  const banner = $("simError");
  if (!res.ok) {
    banner.textContent = "⚠ " + d.error;
    banner.hidden = false;
    sim = null;
    return;
  }
  banner.hidden = true;
  sim = d;
  simStale = false;

  $("m_maxF").textContent = fmt(d.max_thrust, 0) + " N";
  $("s_avgF").textContent = "avg " + fmt(d.avg_thrust, 0) + " N";
  $("m_maxP").textContent = fmt(d.max_pressure / 6895, 0) + " psi";
  $("s_maxP").textContent = fmt(d.max_pressure / 1e6, 2) + " MPa";
  $("m_tb").textContent = fmt(d.burn_time, 2) + " s";
  $("m_It").textContent = fmt(d.total_impulse, 0) + " N·s";
  $("s_class").textContent = `class ${d.motor_class} · ${d.certification.text}`;
  $("m_isp").textContent = fmt(d.isp_delivered, 0) + " s";
  $("m_kn").textContent = fmt(d.peak_kn, 0);

  renderSimCharts(d);

  $("scrubber").max = d.time.length - 1;
  setFrame(0);
}

function renderSimCharts(d) {
  charts.thrust = lineChart($("thrustChart"), {
    x: d.time, y: d.thrust, xLabel: "time (s)", yLabel: "N", yFmt: (v) => fmt(v, 0),
  });
  charts.pressure = lineChart($("pressureChart"), {
    x: d.time, y: d.pressure.map((p) => p / 6895), xLabel: "time (s)", yLabel: "psi", yFmt: (v) => fmt(v, 0),
  });
}

// the AI mentor can edit the design through its tool; refresh everything
// when it does
window.addEventListener("ai-project-updated", (e) => {
  if (!project) return;
  project = e.detail;
  stateToForms();
  refreshDesign();
});

// every JS-drawn surface picks its colours at draw time, so a theme
// switch just means drawing everything again
window.addEventListener("themechange", () => {
  if (!project) return;
  renderPropellantTab();
  if (lastDesign) drawNozzleSection(lastDesign.geometry);
  if (sim) {
    renderSimCharts(sim);
    setFrame(parseInt($("scrubber").value, 10) || 0);
  }
});

// ----- grain animation -----

let playing = false;
let playhead = 0;
let lastTick = 0;
let playTimer = null;

function frameIndex(t) {
  const times = sim.time;
  let lo = 0, hi = times.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (times[mid] <= t) lo = mid; else hi = mid;
  }
  return lo;
}

function setFrame(i) {
  if (!sim) return;
  const g = project.grain;
  const webMm = sim.web[i] * 1000;
  $("scrubber").value = i;
  $("animTime").textContent = `t = ${fmt(sim.time[i], 2)} s`;
  drawFace(g, webMm);
  drawSection(g, webMm);
  $("animReadout").innerHTML =
    `Kn <b>${fmt(sim.kn[i], 0)}</b> · ` +
    `Pc <b>${fmt(sim.pressure[i] / 6895, 0)} psi</b> · ` +
    `thrust <b>${fmt(sim.thrust[i], 0)} N</b> · ` +
    `propellant <b>${fmt(sim.mass[i] * 1000, 0)} g</b> · ` +
    `web burned <b>${fmt(webMm, 1)} mm</b>`;
  charts.thrust?.setCursor(sim.time[i]);
  charts.pressure?.setCursor(sim.time[i]);
}

// Straight-sided kerf outline of slit k at the face, in mm coordinates
// centred on the motor axis. Starts slightly inside the core so the polygon
// fuses with the core circle.
function slitPolygon(g, k) {
  const rc = g.core_d_mm / 2;
  const tip = rc + g.slit_depth_mm;
  const half = g.slit_width_mm / 2;
  const th = (2 * Math.PI * k) / g.slit_count - Math.PI / 2;
  const ux = Math.cos(th), uy = Math.sin(th);
  const vx = -uy, vy = ux;
  const r0 = rc * 0.9;
  return [
    [r0 * ux - half * vx, r0 * uy - half * vy],
    [tip * ux - half * vx, tip * uy - half * vy],
    [tip * ux + half * vx, tip * uy + half * vy],
    [r0 * ux + half * vx, r0 * uy + half * vy],
  ];
}

function drawFace(g, webMm) {
  const S = 220, c = S / 2, pad = 14;
  const rCaseMm = g.outer_d_mm / 2 + 3;
  const k = (S / 2 - pad) / rCaseMm;
  const rCase = rCaseMm * k;
  const rGrain = (g.outer_d_mm / 2) * k;
  const rCore = Math.min(g.core_d_mm / 2 + webMm, g.outer_d_mm / 2) * k;
  const slits = g.slit_count > 0
    ? Array.from({ length: g.slit_count }, (_, i) => slitPolygon(g, i))
    : [];
  const toPath = (poly) =>
    poly.map(([x, y], i) => `${i ? "L" : "M"}${(c + x * k).toFixed(2)},${(c + y * k).toFixed(2)}`).join("") + "Z";

  const C = window.ibColor;
  const VOID = C("draw-void"), OUTLINE = C("draw-outline");
  // burned region = initial void dilated by the web distance; a round-joined
  // stroke of width 2·web on the slit wedge is exactly that dilation
  const burnedSlits = slits.map((poly) =>
    `<path d="${toPath(poly)}" fill="${VOID}" stroke="${VOID}" stroke-width="${2 * webMm * k}" stroke-linejoin="round" stroke-linecap="round"/>`).join("");
  const originalSlits = slits.map((poly) =>
    `<path d="${toPath(poly)}" fill="none" stroke="${OUTLINE}" stroke-dasharray="3 4"/>`).join("");

  $("faceView").innerHTML = `
    <defs><clipPath id="grainClip"><circle cx="${c}" cy="${c}" r="${rGrain}"/></clipPath></defs>
    <circle cx="${c}" cy="${c}" r="${rCase}" fill="${C("draw-case")}" stroke="${OUTLINE}" stroke-width="2"/>
    <circle cx="${c}" cy="${c}" r="${rGrain}" fill="rgba(57,135,229,0.25)" stroke="rgba(57,135,229,0.9)"/>
    <g clip-path="url(#grainClip)">
      <circle cx="${c}" cy="${c}" r="${rCore}" fill="${VOID}"/>
      ${burnedSlits}
      <circle cx="${c}" cy="${c}" r="${(g.core_d_mm / 2) * k}" fill="none" stroke="${OUTLINE}" stroke-dasharray="3 4"/>
      ${originalSlits}
    </g>
    <circle cx="${c}" cy="${c}" r="${rGrain}" fill="none" stroke="rgba(57,135,229,0.9)"/>
    <text x="${c}" y="${S - 3}" fill="${C("ink-3")}" font-size="10" text-anchor="middle">face view</text>`;
}

// Analytic distance field for a plain BATES stack: per segment the nearest
// of core wall and the two faces, inter-segment gaps as void. Same payload
// shape as the server's slit section: rows span the full bore diameter,
// top row at +R, bottom row at -R.
function batesSection(g) {
  const R = g.outer_d_mm / 2, rc = g.core_d_mm / 2, L = g.length_mm;
  const half = 80, nu = 2 * half, du = R / half;
  const dz = 0.5, gapCols = Math.round(3 / dz);
  const nzSeg = Math.max(Math.ceil(L / dz), 8);
  const nz = g.segments * nzSeg + (g.segments - 1) * gapCols;
  const dist = new Float64Array(nu * nz);
  for (let iu = 0; iu < nu; iu++) {
    const u = Math.abs((iu + 0.5) * du - R); // radial distance from the axis
    for (let s = 0; s < g.segments; s++) {
      const col0 = s * (nzSeg + gapCols);
      for (let iz = 0; iz < nzSeg; iz++) {
        const z = (iz + 0.5) * (L / nzSeg);
        dist[iu * nz + col0 + iz] = u <= rc ? 0 : Math.min(u - rc, z, L - z);
      }
    }
  }
  return {
    nu, nz, du_mm: du, dz_mm: dz, cell_mm: du,
    web_mm: Math.min(R - rc, L / 2), dist_mm: dist,
  };
}

// Axial section of the whole stack at true proportions, openMotor style:
// colour encodes when each point burns, dark = already consumed, white =
// the front. Rows span the bore diameter — for a slitted grain the top
// half is the ray between slits, the bottom half the ray through a slit.
function drawSection(g, webMm) {
  const cv = $("sectionView");
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, padX = 34, padT = 14, padB = 30;
  const C = window.ibColor;
  const [brR, brG, brB] = window.ibColorRGB("draw-burned");
  const [frR, frG, frB] = window.ibColorRGB("draw-front");
  ctx.fillStyle = C("draw-void");
  ctx.fillRect(0, 0, W, H);

  const sec = (sim && sim.slit_section) || batesSection(g);
  const { nu, nz, web_mm } = sec;
  const front = Math.max(sec.cell_mm * 1.4, web_mm / 90);

  const img = new ImageData(nz, nu);
  for (let iu = 0; iu < nu; iu++) {
    const row = iu * nz; // rows already run top (+R) to bottom (-R)
    for (let iz = 0; iz < nz; iz++) {
      const d = sec.dist_mm[row + iz];
      const o = (row + iz) * 4;
      if (d <= 0) {
        img.data[o + 3] = 0; // void from the start — panel background
      } else if (Math.abs(d - webMm) <= front) {
        img.data[o] = frR; img.data[o + 1] = frG; img.data[o + 2] = frB;
        img.data[o + 3] = 255;
      } else if (d < webMm) {
        img.data[o] = brR; img.data[o + 1] = brG; img.data[o + 2] = brB;
        img.data[o + 3] = 255; // burned
      } else {
        const t = Math.min(d / web_mm, 1); // late-burning = darker blue
        img.data[o] = Math.round(127 - 97 * t);
        img.data[o + 1] = Math.round(181 - 123 * t);
        img.data[o + 2] = Math.round(240 - 148 * t);
        img.data[o + 3] = 255;
      }
    }
  }

  // scale mm → px uniformly so the motor keeps its real proportions
  const wMm = nz * sec.dz_mm, hMm = nu * sec.du_mm;
  const s = Math.min((W - 2 * padX) / wMm, (H - padT - padB) / hMm);
  const dw = wMm * s, dh = hMm * s;
  const x0 = padX + (W - 2 * padX - dw) / 2;
  const y0 = padT + (H - padT - padB - dh) / 2;

  const off = new OffscreenCanvas(nz, nu);
  off.getContext("2d").putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(off, x0, y0, dw, dh);

  // casing walls above and below, motor axis dashed through the middle
  ctx.fillStyle = C("draw-outline-2");
  ctx.fillRect(x0, y0 - 2, dw, 2);
  ctx.fillRect(x0, y0 + dh, dw, 2);
  ctx.strokeStyle = C("draw-outline");
  ctx.setLineDash([7, 5]);
  ctx.beginPath();
  ctx.moveTo(x0 - 12, y0 + dh / 2);
  ctx.lineTo(x0 + dw + 12, y0 + dh / 2);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = C("ink-3");
  ctx.font = "10px ui-monospace, Menlo, monospace";
  ctx.textAlign = "center";
  const halves = g.slit_count > 0 ? "top: between slits · bottom: through a slit" : "axial section";
  ctx.fillText(`${halves} · colour: burn order · line: burn front`, W / 2, H - 8);
  ctx.textAlign = "left";
  ctx.fillText("fwd face", x0, y0 - 6);
  ctx.textAlign = "right";
  ctx.fillText("nozzle end", x0 + dw, y0 - 6);
}

function stopPlayback(label) {
  playing = false;
  clearInterval(playTimer);
  playTimer = null;
  $("playBtn").textContent = label;
}

function tick() {
  if (!playing || !sim) return;
  const now = performance.now();
  const dt = (now - lastTick) / 1000;
  lastTick = now;
  playhead += dt * parseFloat($("speed").value);
  if (playhead >= sim.burn_time) {
    playhead = sim.burn_time;
    stopPlayback("▶ Replay");
  }
  setFrame(frameIndex(playhead));
}

$("playBtn").addEventListener("click", () => {
  if (!sim) return;
  if (playing) {
    stopPlayback("▶ Play");
  } else {
    if (playhead >= sim.burn_time) playhead = 0;
    playing = true;
    $("playBtn").textContent = "⏸ Pause";
    lastTick = performance.now();
    playTimer = setInterval(tick, 33);
  }
});

$("scrubber").addEventListener("input", () => {
  if (!sim) return;
  stopPlayback("▶ Play");
  const i = parseInt($("scrubber").value, 10);
  playhead = sim.time[i];
  setFrame(i);
});

// ---------- tabs ----------

document.querySelectorAll(".steps .step").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".steps .step").forEach((b) => b.classList.toggle("active", b === btn));
    for (const name of ["propellant", "motor", "simulation", "review"]) {
      $(`tab-${name}`).hidden = name !== btn.dataset.tab;
    }
    if (btn.dataset.tab === "simulation" && (simStale || !sim)) runSimulation();
    if (btn.dataset.tab === "motor" && lastDesign) viewer.rebuild(lastDesign.geometry);
    if (btn.dataset.tab === "review") window.dispatchEvent(new CustomEvent("review-tab-opened"));
  });
});

// ---------- wiring ----------

document.querySelectorAll("#propMode .seg").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#propMode .seg").forEach((b) => b.classList.toggle("active", b === btn));
    $("libraryForm").hidden = btn.dataset.mode !== "library";
    $("customForm").hidden = btn.dataset.mode !== "custom";
    refreshDesign();
  });
});

for (const id of [...GRAIN_IDS, ...NOZZLE_IDS, "propellant", ...CUSTOM_IDS.map((f) => `c_${f}`)]) {
  $(id).addEventListener("input", debounce(refreshDesign, 200));
}

$("projectName").addEventListener("blur", () => {
  project.name = $("projectName").textContent.trim() || project.name;
  $("projectName").textContent = project.name;
  save();
});
$("projectName").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); $("projectName").blur(); }
});

$("cutaway").addEventListener("change", (e) => viewer.setCutaway(e.target.checked));
document.querySelectorAll(".view-group [data-view]").forEach((btn) =>
  btn.addEventListener("click", () => viewer.setView(btn.dataset.view)));
$("stlBtn").addEventListener("click", () => {
  const g = project.grain;
  const params = new URLSearchParams({
    outer_d_mm: g.outer_d_mm, core_d_mm: g.core_d_mm, length_mm: g.length_mm,
    slit_count: g.slit_count || 0, slit_depth_mm: g.slit_depth_mm,
    slit_width_mm: g.slit_width_mm, slit_length_mm: g.slit_length_mm,
    slit_taper_pct: g.slit_taper_pct,
    // the cut differs per segment, so slitted grains export the whole stack
    segments: g.slit_count > 0 ? g.segments : 1,
  });
  location.href = `/api/stl?${params}`;
});

// ---------- boot ----------

async function boot() {
  const [projRes, libRes] = await Promise.all([
    fetch(`/api/projects/${window.PROJECT_ID}`),
    fetch("/api/propellants"),
  ]);
  project = await projRes.json();
  library = await libRes.json();
  // projects saved before slits existed get the defaults
  project.grain = {
    slit_count: 0, slit_depth_mm: 8, slit_width_mm: 3, slit_length_mm: 30,
    slit_taper_pct: 30,
    ...project.grain,
  };
  if (!project.grain.slit_length_mm) {
    project.grain.slit_length_mm = Math.round(project.grain.length_mm / 3);
  }

  const select = $("propellant");
  for (const [key, p] of Object.entries(library)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = p.name;
    select.appendChild(opt);
  }

  viewer = new MotorViewer($("viewer3d"));
  stateToForms();
  renderPropellantTab();
  await refreshDesign();
}

boot();
