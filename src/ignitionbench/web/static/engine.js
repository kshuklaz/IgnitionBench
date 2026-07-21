// Propellant Engine: Plan (ingredients + characterize/save), Prepare (safety +
// notes), Cast (grain geometry + AutoCast). Custom propellants saved here show
// up in every project's propellant menu.

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

document.querySelectorAll(".steps .step").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".steps .step").forEach((b) => b.classList.toggle("active", b === btn));
    for (const name of ["plan", "prepare", "cast"]) {
      $(`tab-${name}`).hidden = name !== btn.dataset.tab;
    }
    if (btn.dataset.tab === "cast") runCastDesign();
  });
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
loadCatalog();
