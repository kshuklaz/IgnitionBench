// Propellant Engine: Plan (ingredients + characterize/save), Prepare (safety +
// notes), Characterization (fit a/n from measured test burns), Cast (grain
// geometry + AutoCast). Custom propellants saved here show up in every
// project's propellant menu.

const $ = (id) => document.getElementById(id);
const fmt = (x, d = 1) =>
  Number(x).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const debounce = (fn, ms) => {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};
const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const ROLES = ["oxidizer", "fuel", "binder", "additive", "catalyst"];
const GRAIN_IDS = [
  "segments", "outer_d_mm", "core_d_mm", "length_mm",
  "slit_count", "slit_depth_mm", "slit_width_mm", "slit_length_mm", "slit_taper_pct",
];
const NOZZLE_IDS = ["throat_d_mm", "half_angle_deg"];
const OWN_IDS = ["a_mm_mpa", "n", "density", "gamma", "temp_k", "molar_g", "min_mpa", "max_mpa"];

const SAFETY_ITEMS = [
  "A certified mentor or RSO is supervising — you are not doing this alone.",
  "Full PPE: safety glasses/face shield, gloves, non-synthetic clothing, hearing protection.",
  "No ignition sources — no flame, sparks, static, or hot surfaces anywhere nearby.",
  "Working outdoors or with strong ventilation, away from people and structures.",
  "Smallest practical batch size; never scale up an untested formulation.",
  "Non-sparking, dedicated tools; containers and surfaces grounded against static.",
  "A charged fire extinguisher and water are within reach.",
  "You know your local laws and have any permits required to make or store propellant.",
  "A labeled, cool, dry storage plan away from living spaces.",
];

let catalog = {};

// ---------- tiny markdown (shared shape with ai.js, kept local) ----------

function renderMarkdown(md) {
  const inline = (s) =>
    escapeHtml(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  const out = [];
  let list = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of md.split("\n")) {
    const line = raw.trimEnd();
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const ul = line.match(/^[-*]\s+(.*)/);
    const ol = line.match(/^\d+[.)]\s+(.*)/);
    if (h) { close(); out.push(`<h${Math.min(h[1].length + 2, 5)}>${inline(h[2])}</h${Math.min(h[1].length + 2, 5)}>`); }
    else if (ul) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(ul[1])}</li>`); }
    else if (ol) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(ol[1])}</li>`); }
    else if (line.trim() === "") { close(); }
    else { close(); out.push(`<p>${inline(line)}</p>`); }
  }
  close();
  return out.join("");
}

// ---------- tabs ----------

const TAB_NAMES = ["plan", "prepare", "char", "cast"];

function showTab(name) {
  document.querySelectorAll(".steps .step").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === name));
  for (const t of TAB_NAMES) $(`tab-${t}`).hidden = t !== name;
  if (name === "cast") runCastDesign();
  if (name === "char") updateCharSkip();
}

document.querySelectorAll(".steps .step").forEach((btn) => {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
});

// ---------- Plan: ingredients ----------

function addIngredientRow(item = {}) {
  const row = document.createElement("div");
  row.className = "ingredient-row";
  const roleOpts = ROLES.map(
    (r) => `<option value="${r}"${r === item.role ? " selected" : ""}>${r}</option>`
  ).join("");
  row.innerHTML = `
    <input class="ing-name" type="text" maxlength="60" placeholder="ingredient" value="${item.name ? escapeHtml(item.name) : ""}">
    <select class="ing-role">${roleOpts}</select>
    <input class="ing-pct" type="number" min="0" max="100" step="0.5" value="${item.percent ?? ""}">
    <button class="icon-btn ing-del" title="Remove" data-tip="Remove this ingredient">✕</button>`;
  row.querySelector(".ing-del").addEventListener("click", () => { row.remove(); updatePctTotal(); });
  row.querySelector(".ing-pct").addEventListener("input", updatePctTotal);
  $("ingredientRows").appendChild(row);
}

function collectIngredients() {
  return [...document.querySelectorAll(".ingredient-row")]
    .map((r) => ({
      name: r.querySelector(".ing-name").value.trim(),
      role: r.querySelector(".ing-role").value,
      percent: parseFloat(r.querySelector(".ing-pct").value) || 0,
    }))
    .filter((i) => i.name);
}

function updatePctTotal() {
  const total = collectIngredients().reduce((s, i) => s + i.percent, 0);
  const el = $("pctTotal");
  el.textContent = `${fmt(total, total % 1 ? 1 : 0)}%`;
  el.classList.toggle("off", collectIngredients().length > 0 && Math.abs(total - 100) > 0.5);
}

// ---------- Plan: characterize + save ----------

function sourceMode() {
  return document.querySelector("#sourceMode .seg.active").dataset.src;
}

function fillBaseMeta() {
  const p = catalog[$("p_base").value];
  if (!p) return;
  $("baseMeta").innerHTML = `
    <tr><td>Density</td><td>${fmt(p.density, 0)} kg/m³</td></tr>
    <tr><td>c*</td><td>${fmt(p.c_star, 0)} m/s</td></tr>
    <tr><td>γ exhaust</td><td>${fmt(p.gamma, 3)}</td></tr>
    <tr><td>Flame temp</td><td>${fmt(p.temp_k, 0)} K</td></tr>
    <tr><td>Validated range</td><td>${fmt(p.min_pressure / 6895, 0)}–${fmt(p.max_pressure / 6895, 0)} psi</td></tr>`;
}

function savePayload() {
  const base = {
    name: $("p_name").value.trim(),
    ingredients: collectIngredients(),
    source: $("p_source").value.trim(),
  };
  if (sourceMode() === "base") return { ...base, base_key: $("p_base").value };
  const ballistics = {};
  for (const f of OWN_IDS) ballistics[f] = parseFloat($(`p_${f}`).value);
  return { ...base, ballistics };
}

async function saveProp() {
  const msg = $("saveMsg");
  const payload = savePayload();
  if (!payload.name) { msg.textContent = "Give it a name first."; return; }
  $("saveProp").disabled = true;
  msg.textContent = "Saving…";
  try {
    const res = await fetch("/api/propellants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
    msg.textContent = `Saved “${d.name}” — it's now in every propellant menu.`;
    $("p_name").value = "";
    await loadCatalog();
  } catch (err) {
    msg.textContent = `⚠ ${err.message}`;
  } finally {
    $("saveProp").disabled = false;
  }
}

function renderMyProps() {
  const box = $("myProps");
  const mine = Object.entries(catalog).filter(([, p]) => p.custom);
  if (!mine.length) {
    box.innerHTML = `<p class="footnote">Nothing saved yet. Characterize a propellant above and it lands here.</p>`;
    return;
  }
  box.innerHTML = "";
  for (const [key, p] of mine) {
    const ing = (p.ingredients || []).map((i) => i.name).join(", ");
    const card = document.createElement("div");
    card.className = "prop-item";
    card.innerHTML = `
      <div>
        <div class="prop-item-name"></div>
        <div class="footnote">${p.base_key ? `based on ${escapeHtml(catalog[p.base_key]?.name || p.base_key)}` : "custom a/n"}${ing ? ` · ${escapeHtml(ing)}` : ""}</div>
      </div>
      <button class="icon-btn prop-del" data-tip="Delete this saved propellant">✕ delete</button>`;
    card.querySelector(".prop-item-name").textContent = p.name;
    const del = card.querySelector(".prop-del");
    del.addEventListener("click", async () => {
      if (!del.dataset.armed) {
        del.dataset.armed = "1";
        del.textContent = "✕ click again";
        del.style.color = "var(--critical)";
        setTimeout(() => { delete del.dataset.armed; del.textContent = "✕ delete"; del.style.color = ""; }, 3000);
        return;
      }
      await fetch(`/api/propellants/${p.id}`, { method: "DELETE" });
      await loadCatalog();
    });
    box.appendChild(card);
  }
}

// ---------- Prepare ----------

function renderSafetyCheck() {
  $("safetyCheck").innerHTML = SAFETY_ITEMS
    .map((t, i) => `<li><label><input type="checkbox" id="safe_${i}"> <span>${escapeHtml(t)}</span></label></li>`)
    .join("");
}

function customOptions() {
  return Object.entries(catalog).filter(([, p]) => p.custom);
}

function fillPrepProp() {
  const sel = $("prepProp");
  const prev = sel.value;
  const mine = customOptions();
  sel.innerHTML = mine.length
    ? mine.map(([k, p]) => `<option value="${k}">${escapeHtml(p.name)}</option>`).join("")
    : `<option value="">— save a propellant first —</option>`;
  if (mine.some(([k]) => k === prev)) sel.value = prev;
  loadPrepNotes();
}

function loadPrepNotes() {
  const p = catalog[$("prepProp").value];
  $("prepNotes").value = p ? p.prepare_notes || "" : "";
  $("prepNotes").disabled = !p;
  $("savePrep").disabled = !p;
}

async function savePrep() {
  const key = $("prepProp").value;
  const p = catalog[key];
  if (!p) return;
  $("prepMsg").textContent = "Saving…";
  await fetch(`/api/propellants/${p.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prepare_notes: $("prepNotes").value }),
  });
  $("prepMsg").textContent = "Notes saved.";
  await loadCatalog();
}

// ---------- Characterization: fit a/n from measured test burns ----------

const CHAR_STORE = "ib-char-points";

function addCharRow(pt = {}) {
  const row = document.createElement("div");
  row.className = "char-row";
  row.innerHTML = `
    <input class="char-p" type="number" min="0.01" step="0.05" placeholder="e.g. 3.5" value="${pt.p ?? ""}">
    <input class="char-r" type="number" min="0.01" step="0.1" placeholder="e.g. 9.2" value="${pt.r ?? ""}">
    <button class="icon-btn ing-del" title="Remove" data-tip="Remove this test burn">✕</button>`;
  row.querySelector(".ing-del").addEventListener("click", () => { row.remove(); refitChar(); });
  row.querySelectorAll("input").forEach((i) => i.addEventListener("input", debounce(refitChar, 250)));
  $("charRows").appendChild(row);
}

function collectCharPoints() {
  return [...document.querySelectorAll(".char-row")]
    .map((row) => ({
      p: parseFloat(row.querySelector(".char-p").value),
      r: parseFloat(row.querySelector(".char-r").value),
    }))
    .filter((pt) => pt.p > 0 && pt.r > 0);
}

// least-squares fit of ln r = ln a + n·ln P
function fitChar(points) {
  if (points.length < 3) return null;
  const lx = points.map((pt) => Math.log(pt.p));
  const ly = points.map((pt) => Math.log(pt.r));
  const N = points.length;
  const mx = lx.reduce((s, v) => s + v, 0) / N;
  const my = ly.reduce((s, v) => s + v, 0) / N;
  let sxy = 0, sxx = 0, syy = 0;
  for (let i = 0; i < N; i++) {
    sxy += (lx[i] - mx) * (ly[i] - my);
    sxx += (lx[i] - mx) ** 2;
    syy += (ly[i] - my) ** 2;
  }
  if (sxx === 0) return null; // all burns at the same pressure
  const n = sxy / sxx;
  const a = Math.exp(my - n * mx);
  const r2 = syy === 0 ? 1 : (sxy * sxy) / (sxx * syy);
  const ps = points.map((pt) => pt.p);
  return { a, n, r2, pmin: Math.min(...ps), pmax: Math.max(...ps) };
}

let charFitResult = null;

function refitChar() {
  const points = collectCharPoints();
  localStorage.setItem(CHAR_STORE, JSON.stringify(points));
  const fit = fitChar(points);
  charFitResult = null;
  const table = $("charFit");
  const msg = $("charMsg");
  drawCharChart(points, fit);
  if (!fit) {
    table.innerHTML = "";
    msg.textContent = points.length
      ? "Add at least 3 burns at different pressures to fit a and n."
      : "";
    $("charToPlan").disabled = true;
    return;
  }
  table.innerHTML = `
    <tr><td>a — burn coeff</td><td>${fmt(fit.a, 3)} mm/s at MPa</td></tr>
    <tr><td>n — exponent</td><td>${fmt(fit.n, 3)}</td></tr>
    <tr><td>R² of fit</td><td>${fmt(fit.r2, 3)}</td></tr>
    <tr><td>Validated range</td><td>${fmt(fit.pmin, 2)}–${fmt(fit.pmax, 2)} MPa (${fmt(fit.pmin * 145, 0)}–${fmt(fit.pmax * 145, 0)} psi)</td></tr>`;
  const problems = [];
  if (!(fit.n > 0 && fit.n < 1)) {
    problems.push(`n = ${fmt(fit.n, 3)} is outside 0–1 — solid propellants don't behave like this; re-check your pressure and rate measurements.`);
  }
  if (fit.r2 < 0.9) {
    problems.push("R² is low — the points scatter badly. Repeat the outliers before trusting this fit.");
  }
  if (fit.pmax / fit.pmin < 1.5) {
    problems.push("Your burns cover a narrow pressure range — the fit only holds inside it. Test wider if your motor will run outside.");
  }
  msg.textContent = problems.length ? `⚠ ${problems.join(" ")}` : "Good fit. Send it to Plan to finish characterizing.";
  charFitResult = fit;
  $("charToPlan").disabled = !(fit.n > 0 && fit.n < 1);
}

function drawCharChart(points, fit) {
  const box = $("charChart");
  if (!points.length) {
    box.innerHTML = `<p class="footnote">Your test points plot here as you enter them.</p>`;
    return;
  }
  const W = 340, H = 190, L = 40, R = 12, T = 12, B = 28;
  const ps = points.map((pt) => pt.p), rs = points.map((pt) => pt.r);
  const pad = (lo, hi) => { const d = (hi - lo) || hi * 0.4 || 1; return [Math.max(lo - d * 0.15, 0), hi + d * 0.15]; };
  const [x0, x1] = pad(Math.min(...ps), Math.max(...ps));
  const [y0, y1] = pad(Math.min(...rs), Math.max(...rs));
  const X = (p) => L + ((p - x0) / (x1 - x0)) * (W - L - R);
  const Y = (r) => H - B - ((r - y0) / (y1 - y0)) * (H - T - B);
  let curve = "";
  if (fit) {
    const steps = 40;
    curve = [...Array(steps + 1)]
      .map((_, i) => {
        const p = x0 + ((x1 - x0) * i) / steps;
        return `${X(p).toFixed(1)},${Y(fit.a * Math.pow(Math.max(p, 1e-6), fit.n)).toFixed(1)}`;
      })
      .join(" ");
  }
  box.innerHTML = `
  <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Burn rate vs pressure">
    <line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" stroke="var(--chart-axis)" stroke-width="1"/>
    <line x1="${L}" y1="${T}" x2="${L}" y2="${H - B}" stroke="var(--chart-axis)" stroke-width="1"/>
    ${curve ? `<polyline points="${curve}" fill="none" stroke="var(--accent)" stroke-width="2" opacity="0.85"/>` : ""}
    ${points.map((pt) => `<circle cx="${X(pt.p).toFixed(1)}" cy="${Y(pt.r).toFixed(1)}" r="4" fill="var(--ink)" stroke="var(--surface)" stroke-width="1.5"/>`).join("")}
    <text x="${L - 6}" y="${Y(y1).toFixed(1)}" text-anchor="end" dominant-baseline="middle" font-size="10" fill="var(--ink-3)">${fmt(y1, 1)}</text>
    <text x="${L - 6}" y="${Y(y0).toFixed(1)}" text-anchor="end" dominant-baseline="middle" font-size="10" fill="var(--ink-3)">${fmt(y0, 1)}</text>
    <text x="${X(x0).toFixed(1)}" y="${H - B + 14}" text-anchor="middle" font-size="10" fill="var(--ink-3)">${fmt(x0, 1)}</text>
    <text x="${X(x1).toFixed(1)}" y="${H - B + 14}" text-anchor="middle" font-size="10" fill="var(--ink-3)">${fmt(x1, 1)}</text>
    <text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle" font-size="10" fill="var(--ink-3)">P — MPa</text>
    <text x="12" y="${(T + H - B) / 2}" text-anchor="middle" font-size="10" fill="var(--ink-3)" transform="rotate(-90 12 ${(T + H - B) / 2})">r — mm/s</text>
  </svg>`;
}

function sendCharToPlan() {
  if (!charFitResult) return;
  $("p_a_mm_mpa").value = charFitResult.a.toFixed(3);
  $("p_n").value = charFitResult.n.toFixed(3);
  $("p_min_mpa").value = charFitResult.pmin.toFixed(2);
  $("p_max_mpa").value = charFitResult.pmax.toFixed(2);
  document.querySelector('#sourceMode .seg[data-src="own"]').click();
  showTab("plan");
  $("saveMsg").textContent =
    "Fitted a/n and pressure range loaded — add density, γ, flame temp, and molar mass, then save.";
}

// a/n are already established when the user starts from a published baseline
function updateCharSkip() {
  const skip = $("charSkip");
  if (sourceMode() === "base") {
    const name = catalog[$("p_base").value]?.name || "a published propellant";
    skip.hidden = false;
    skip.textContent =
      `Your Plan tab starts from ${name}, whose a and n are already established ` +
      `from published test data — you can skip this tab. Characterize only when ` +
      `you're entering your own a/n data for your own batch.`;
  } else {
    skip.hidden = true;
  }
}

function loadCharRows() {
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(CHAR_STORE)) || []; } catch { /* fresh start */ }
  if (saved.length) saved.forEach((pt) => addCharRow(pt));
  else for (let i = 0; i < 3; i++) addCharRow();
  refitChar();
}

// ---------- Cast ----------

function castGrain() {
  const g = {};
  for (const f of GRAIN_IDS) g[f] = parseFloat($(`g_${f}`).value);
  return g;
}
function castNozzle() {
  const n = {};
  for (const f of NOZZLE_IDS) n[f] = parseFloat($(`g_${f}`).value);
  return n;
}
function castDesignPayload() {
  return {
    propellant: { mode: "library", key: $("castProp").value },
    grain: castGrain(),
    nozzle: castNozzle(),
  };
}

async function runCastDesign() {
  let d;
  try {
    const res = await fetch("/api/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(castDesignPayload()),
    });
    d = await res.json();
    if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
  } catch (err) {
    $("castError").hidden = false;
    $("castError").textContent = err.message;
    $("castWarnings").innerHTML = "";
    return;
  }
  $("castError").hidden = true;
  $("c_kn").textContent = fmt(d.kn, 0);
  $("c_pc").textContent = fmt(d.chamber_pressure_psi, 0) + " psi";
  $("c_pcsub").textContent = fmt(d.chamber_pressure_mpa, 2) + " MPa";
  $("c_thrust").textContent = fmt(d.thrust_n, 0) + " N";
  $("c_class").textContent = d.motor_class;
  const w = $("castWarnings");
  if (d.warnings.length) {
    w.innerHTML = d.warnings.map((x) => `<li class="${x.level}">${escapeHtml(x.text)}</li>`).join("");
  } else {
    w.innerHTML = `<li class="ok">No warnings at this operating point.</li>`;
  }
}

let castProposal = null;

async function runAutocast() {
  const status = $("autocastStatus");
  const body = $("autocastBody");
  const cfg = await (await fetch("/api/ai/status")).json().catch(() => ({ configured: false }));
  if (!cfg.configured) {
    status.hidden = false;
    status.innerHTML =
      'AutoCast needs a Claude API key. Set <code>ANTHROPIC_API_KEY</code> and restart the server.';
    return;
  }
  $("autocastBtn").disabled = true;
  status.hidden = false;
  status.textContent = "Delta is designing a grain for your goal…";
  body.innerHTML = "";
  $("applyCast").hidden = true;
  castProposal = null;
  try {
    const res = await fetch("/api/ai/autocast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        goal: $("ac_goal").value,
        propellant_key: $("castProp").value,
        grain: castGrain(),
        nozzle: castNozzle(),
      }),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
    status.hidden = true;
    body.innerHTML = renderMarkdown(d.reply || "");
    if (d.proposal) {
      castProposal = d.proposal;
      $("applyCast").hidden = false;
    }
  } catch (err) {
    status.textContent = `⚠ AutoCast failed: ${err.message}`;
  } finally {
    $("autocastBtn").disabled = false;
  }
}

function applyProposal() {
  if (!castProposal) return;
  for (const f of GRAIN_IDS) if (castProposal.grain?.[f] != null) $(`g_${f}`).value = castProposal.grain[f];
  for (const f of NOZZLE_IDS) if (castProposal.nozzle?.[f] != null) $(`g_${f}`).value = castProposal.nozzle[f];
  $("applyCast").hidden = true;
  runCastDesign();
}

async function createProject() {
  const name = prompt("Name this motor project:", `${catalog[$("castProp").value]?.name || "Motor"} build`);
  if (!name || !name.trim()) return;
  const proj = await (await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name.trim() }),
  })).json();
  proj.propellant.mode = "library";
  proj.propellant.key = $("castProp").value;
  proj.grain = { ...proj.grain, ...castGrain() };
  proj.nozzle = castNozzle();
  await fetch(`/api/projects/${proj.id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: proj.name, propellant: proj.propellant, grain: proj.grain, nozzle: proj.nozzle, summary: {} }),
  });
  location.href = `/project/${proj.id}`;
}

// ---------- catalog load / wiring ----------

function fillSelect(sel, entries, { onlyBase = false, prefer = "knsb" } = {}) {
  const prev = sel.value;
  sel.innerHTML = "";
  for (const [key, p] of entries) {
    if (onlyBase && p.custom) continue;
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = p.custom ? `★ ${p.name}` : p.name;
    sel.appendChild(opt);
  }
  const has = (v) => [...sel.options].some((o) => o.value === v);
  if (has(prev)) sel.value = prev;
  else if (has(prefer)) sel.value = prefer; // sensible beginner default
}

async function loadCatalog() {
  catalog = await (await fetch("/api/propellants")).json();
  const entries = Object.entries(catalog);
  fillSelect($("p_base"), entries, { onlyBase: true });
  fillSelect($("castProp"), entries);
  fillBaseMeta();
  renderMyProps();
  fillPrepProp();
  runCastDesign();
}

document.querySelectorAll("#sourceMode .seg").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#sourceMode .seg").forEach((b) => b.classList.toggle("active", b === btn));
    $("baseForm").hidden = btn.dataset.src !== "base";
    $("ownForm").hidden = btn.dataset.src !== "own";
  });
});

$("addIngredient").addEventListener("click", () => addIngredientRow());
$("addCharRow").addEventListener("click", () => addCharRow());
$("charToPlan").addEventListener("click", sendCharToPlan);
$("p_base").addEventListener("change", fillBaseMeta);
$("saveProp").addEventListener("click", saveProp);
$("prepProp").addEventListener("change", loadPrepNotes);
$("savePrep").addEventListener("click", savePrep);
$("castProp").addEventListener("change", runCastDesign);
for (const f of [...GRAIN_IDS, ...NOZZLE_IDS]) {
  $(`g_${f}`).addEventListener("input", debounce(runCastDesign, 250));
}
$("autocastBtn").addEventListener("click", runAutocast);
$("applyCast").addEventListener("click", applyProposal);
$("createProject").addEventListener("click", createProject);

// ---------- boot ----------

addIngredientRow();
addIngredientRow();
updatePctTotal();
renderSafetyCheck();
loadCharRows();
loadCatalog();
