const $ = (id) => document.getElementById(id);
const INPUT_IDS = ["propellant", "segments", "outer_d_mm", "core_d_mm", "length_mm", "throat_d_mm", "half_angle_deg"];

let propellants = {};

const fmt = (x, digits = 1) =>
  Number(x).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

async function loadPropellants() {
  propellants = await (await fetch("/api/propellants")).json();
  const select = $("propellant");
  for (const [key, p] of Object.entries(propellants)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = p.name;
    select.appendChild(opt);
  }
  select.value = "knsb";
  updatePropMeta();
}

function updatePropMeta() {
  const p = propellants[$("propellant").value];
  if (!p) return;
  $("propMeta").textContent =
    `ρ ${fmt(p.density, 0)} kg/m³ · c* ${fmt(p.c_star, 0)} m/s · ` +
    `data valid ${fmt(p.min_pressure / 1e6, 2)}–${fmt(p.max_pressure / 1e6, 1)} MPa`;
}

function payload() {
  const v = {};
  for (const id of INPUT_IDS) v[id] = $(id).value;
  return v;
}

async function update() {
  updatePropMeta();
  const res = await fetch("/api/design", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload()),
  });
  const data = await res.json();
  const banner = $("errorBanner");
  const results = document.querySelector(".results");

  if (!res.ok) {
    banner.textContent = "⚠ " + data.error;
    banner.hidden = false;
    results.classList.add("stale");
    $("classBadge").textContent = "—";
    return;
  }
  banner.hidden = true;
  results.classList.remove("stale");
  render(data);
}

function render(d) {
  $("classBadge").textContent = d.motor_class;

  $("v_kn").textContent = fmt(d.kn, 0);
  $("s_kn").textContent = `burning area / throat area`;
  $("v_pc").textContent = fmt(d.chamber_pressure_mpa, 2) + " MPa";
  $("s_pc").textContent = fmt(d.chamber_pressure_psi, 0) + " psi";
  $("v_thrust").textContent = fmt(d.thrust_n, 0) + " N";
  $("s_thrust").textContent = fmt(d.thrust_n / 9.80665, 1) + " kgf";
  $("v_impulse").textContent = fmt(d.total_impulse_ns, 0) + " N·s";
  $("s_impulse").textContent = `class ${d.motor_class}`;
  $("v_isp").textContent = fmt(d.isp_s, 0) + " s";
  $("v_burn").textContent = "~" + fmt(d.burn_time_s, 2) + " s";
  $("s_burn").textContent = fmt(d.mass_flow_kg_s, 3) + " kg/s";

  $("n_eps").textContent = fmt(d.expansion_ratio, 2) + " : 1";
  $("n_cf").textContent = fmt(d.cf, 3);
  $("n_exit").textContent = fmt(d.exit_d_mm, 1) + " mm";
  $("n_div").textContent = fmt(d.divergent_length_mm, 1) + " mm";
  $("n_mdot").textContent = fmt(d.mass_flow_kg_s, 3) + " kg/s";
  $("n_mass").textContent = fmt(d.propellant_mass_g, 0) + " g";
  $("n_p2t").textContent = fmt(d.port_to_throat, 2);

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

  drawMotor(d.geometry);
}

function drawMotor(g) {
  const W = 720, H = 260, pad = 40, cy = H / 2;
  const gap = 3, bulk = 10, fwd = 6, aft = 5, wall = 3;
  const grainLen = g.segments * g.length_mm + (g.segments - 1) * gap;
  const conv = (g.outer_d_mm - g.throat_d_mm) / 2; // 45° convergent
  const chamberLen = bulk + fwd + grainLen + aft;
  const totalLen = chamberLen + conv + g.divergent_length_mm;
  const maxDia = Math.max(g.outer_d_mm + 2 * wall, g.exit_d_mm + 2 * wall);
  const s = Math.min((W - 2 * pad) / totalLen, (H - 2 * pad) / maxDia);
  const x0 = (W - totalLen * s) / 2;

  const caseR = (g.outer_d_mm / 2 + wall) * s;
  const grainR = (g.outer_d_mm / 2) * s;
  const coreR = (g.core_d_mm / 2) * s;
  const rt = (g.throat_d_mm / 2) * s;
  const re = (g.exit_d_mm / 2) * s;
  const xn = x0 + chamberLen * s; // nozzle entrance
  const xt = xn + conv * s; // throat
  const xe = xt + g.divergent_length_mm * s; // exit

  const el = [];
  // centerline
  el.push(`<line x1="${x0 - 14}" y1="${cy}" x2="${xe + 14}" y2="${cy}" stroke="#3a3937" stroke-dasharray="7 5"/>`);
  // casing
  el.push(`<rect x="${x0}" y="${cy - caseR}" width="${chamberLen * s}" height="${2 * caseR}" rx="4" fill="#201f1e" stroke="#55534d" stroke-width="1.5"/>`);
  // forward bulkhead
  el.push(`<rect x="${x0 + 2}" y="${cy - grainR}" width="${bulk * s}" height="${2 * grainR}" fill="#3a3937"/>`);
  // grain segments (top and bottom halves of the annulus)
  for (let i = 0; i < g.segments; i++) {
    const gx = x0 + (bulk + fwd + i * (g.length_mm + gap)) * s;
    const gw = g.length_mm * s;
    for (const [y, h] of [[cy - grainR, grainR - coreR], [cy + coreR, grainR - coreR]]) {
      el.push(`<rect x="${gx}" y="${y}" width="${gw}" height="${h}" fill="rgba(57,135,229,0.22)" stroke="rgba(57,135,229,0.85)" stroke-width="1"/>`);
    }
  }
  // nozzle solid (top and mirrored bottom)
  for (const m of [1, -1]) {
    const pts = [
      [xn, cy - m * caseR],
      [xe, cy - m * (re + wall * s)],
      [xe, cy - m * re],
      [xt, cy - m * rt],
      [xn, cy - m * grainR],
    ].map((p) => p.join(",")).join(" ");
    el.push(`<polygon points="${pts}" fill="#33322f" stroke="#6b6a61" stroke-width="1.2"/>`);
  }
  // throat + exit annotations
  el.push(`<line x1="${xt}" y1="${cy - rt}" x2="${xt}" y2="${cy + rt}" stroke="#3987e5" stroke-width="1.5"/>`);
  el.push(`<text x="${xt}" y="${cy + rt + 16}" fill="#c3c2b7" font-size="11" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">⌀${fmt(g.throat_d_mm, 1)}</text>`);
  el.push(`<line x1="${xe}" y1="${cy - re}" x2="${xe}" y2="${cy + re}" stroke="#3987e5" stroke-width="1.5"/>`);
  el.push(`<text x="${xe}" y="${cy + re + 16}" fill="#c3c2b7" font-size="11" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">⌀${fmt(g.exit_d_mm, 1)}</text>`);
  // grain length annotation
  el.push(`<text x="${x0 + (bulk + fwd) * s + (grainLen * s) / 2}" y="${cy - caseR - 10}" fill="#8f8e84" font-size="11" text-anchor="middle" font-family="ui-monospace,Menlo,monospace">${g.segments} × ${fmt(g.length_mm, 0)} mm grain</text>`);

  $("motorSvg").innerHTML = el.join("");
}

const debouncedUpdate = debounce(update, 150);
for (const id of INPUT_IDS) $(id).addEventListener("input", debouncedUpdate);

loadPropellants().then(update);
