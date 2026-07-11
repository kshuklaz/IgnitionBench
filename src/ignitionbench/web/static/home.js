const $ = (id) => document.getElementById(id);

function relTime(ts) {
  const s = Date.now() / 1000 - ts;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

async function loadProjects() {
  const projects = await (await fetch("/api/projects")).json();
  const grid = $("projectGrid");
  grid.innerHTML = "";
  $("emptyState").hidden = projects.length > 0;

  for (const p of projects) {
    const card = document.createElement("div");
    card.className = "project-card";
    const cls = p.summary?.motor_class || "—";
    const impulse = p.summary?.total_impulse_ns
      ? `${Math.round(p.summary.total_impulse_ns).toLocaleString()} N·s · `
      : "";
    const propName = (p.propellant?.mode === "custom"
      ? p.propellant?.custom?.name
      : p.propellant?.key?.toUpperCase()) || "—";
    card.innerHTML = `
      <div class="card-top">
        <h3></h3>
        <span class="card-class">${cls}</span>
      </div>
      <div class="card-meta">${propName} · ${impulse}updated ${relTime(p.updated)}</div>
      <div class="card-actions">
        <button class="icon-btn rename" title="Rename">✎ rename</button>
        <button class="icon-btn delete" title="Delete">✕ delete</button>
      </div>`;
    card.querySelector("h3").textContent = p.name;
    card.addEventListener("click", () => (location.href = `/project/${p.id}`));
    card.querySelector(".rename").addEventListener("click", async (e) => {
      e.stopPropagation();
      const name = prompt("Rename project:", p.name);
      if (name && name.trim()) {
        await fetch(`/api/projects/${p.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        });
        loadProjects();
      }
    });
    card.querySelector(".delete").addEventListener("click", async (e) => {
      e.stopPropagation();
      if (confirm(`Delete "${p.name}"? This cannot be undone.`)) {
        await fetch(`/api/projects/${p.id}`, { method: "DELETE" });
        loadProjects();
      }
    });
    grid.appendChild(card);
  }
}

function openModal() {
  $("modal").hidden = false;
  $("projectName").value = "";
  $("projectName").focus();
}

async function createProject() {
  const name = $("projectName").value.trim();
  if (!name) return;
  const res = await fetch("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const project = await res.json();
  location.href = `/project/${project.id}`;
}

$("newProjectBtn").addEventListener("click", openModal);
$("emptyNewBtn").addEventListener("click", openModal);
$("modalCancel").addEventListener("click", () => ($("modal").hidden = true));
$("modalCreate").addEventListener("click", createProject);
$("projectName").addEventListener("keydown", (e) => {
  if (e.key === "Enter") createProject();
  if (e.key === "Escape") $("modal").hidden = true;
});
$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) $("modal").hidden = true;
});

loadProjects();
