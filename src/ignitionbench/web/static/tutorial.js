// Guided "first motor" tour: an interactive, re-openable coach-mark walkthrough.
// It rings a real control on the actual page, tells the user what to click, and
// advances when they click it — spanning the home screen (create a project) and
// the project designer (propellant → motor → simulation → review). Works fully
// offline; only the optional Review step needs an API key.
(() => {
  const FLAG = "ib-tour"; // "home" | "project" while a tour is running
  const SEEN = "ib-tour-seen";
  const path = location.pathname;
  const onProject = /^\/project\//.test(path) || !!window.PROJECT_ID;
  const onHome = path === "/" || path === "";
  const $ = (s, r = document) => r.querySelector(s);

  // ---------- steps ----------

  const HOME_STEPS = [
    {
      title: "Design your first motor",
      body: "I'll walk you through the real app. Whenever you need to click something, I'll ring it in blue — just click it to move on.",
      next: "Start",
    },
    {
      sel: "#newProjectBtn", click: "#newProjectBtn",
      title: "Start a project", body: "Click <b>+ New project</b> to begin.",
    },
    {
      sel: ".modal", click: "#modalCreate", commit: "project",
      title: "Name your motor", body: "Type a name, then click <b>Create</b> to open the designer.",
    },
  ];

  const PROJECT_STEPS = [
    {
      sel: "#propellant",
      title: "Pick a propellant",
      body: "KNSB is already selected — a forgiving, well-documented first propellant. Its burn data is real published data, never invented.",
    },
    {
      sel: '.steps .step[data-tab="motor"]', click: '.steps .step[data-tab="motor"]',
      title: "Shape the motor", body: "Click <b>Motor design</b> to shape the grain and nozzle.",
    },
    {
      sel: "#core_d_mm", tab: "motor",
      title: "The grain core",
      body: "The core diameter sets how much surface burns at once. Change any number here and the results update instantly.",
    },
    {
      sel: "#tab-motor .tiles", tab: "motor",
      title: "Live results",
      body: "Kn, chamber pressure, thrust, and your motor class — all computed live as you design.",
    },
    {
      sel: '.steps .step[data-tab="simulation"]', click: '.steps .step[data-tab="simulation"]',
      title: "Watch it burn", body: "Click <b>Simulation</b> to see the burn play out over time.",
    },
    {
      sel: "#playBtn", tab: "simulation",
      title: "Press play", body: "Hit <b>▶ Play</b> anytime to animate the grain burning back.",
    },
    {
      sel: '.steps .step[data-tab="review"]', click: '.steps .step[data-tab="review"]',
      title: "Safety review", body: "Click <b>Review</b> — Delta reads your whole design for hazards (needs an API key).",
    },
    {
      title: "You did it! 🎉",
      body: "You designed, simulated, and reviewed your first motor. Before any real hardware: work under a certified mentor or RSO, use published data, validate against BurnSim, and static-test before you fly. Reopen this tour anytime from the <b>🎓 Guided tutorial</b> button on the home screen.",
      next: "Finish", finish: true,
    },
  ];

  // ---------- engine ----------

  let list = null;
  let idx = 0;
  let veil, spot, callout;
  let clickEl = null, clickFn = null;
  let curTarget = null;

  function buildDom() {
    veil = document.createElement("div");
    veil.className = "tour-veil";
    spot = document.createElement("div");
    spot.className = "tour-spot";
    callout = document.createElement("div");
    callout.className = "tour-callout";
    for (const el of [veil, spot, callout]) { el.hidden = true; document.body.appendChild(el); }
    window.addEventListener("resize", reposition, { passive: true });
    window.addEventListener("scroll", reposition, { passive: true, capture: true });
  }

  function teardown() {
    clearClick();
    for (const el of [veil, spot, callout]) if (el) el.hidden = true;
    document.body.style.overflow = "";
    curTarget = null;
  }

  function clearClick() {
    if (clickEl && clickFn) clickEl.removeEventListener("click", clickFn);
    clickEl = null; clickFn = null;
  }

  function finish() {
    localStorage.removeItem(FLAG);
    localStorage.setItem(SEEN, "1");
    teardown();
  }

  function ensureTab(tab) {
    if (!tab) return;
    const section = $(`#tab-${tab}`);
    if (section && section.hidden) {
      const btn = $(`.steps .step[data-tab="${tab}"]`);
      if (btn) btn.click();
    }
  }

  function place(el) {
    const r = el.getBoundingClientRect();
    const pad = 6;
    spot.hidden = false;
    veil.hidden = true;
    spot.style.top = `${r.top - pad}px`;
    spot.style.left = `${r.left - pad}px`;
    spot.style.width = `${r.width + pad * 2}px`;
    spot.style.height = `${r.height + pad * 2}px`;

    // callout below the target if there's room, otherwise above
    callout.hidden = false;
    const cw = Math.min(340, window.innerWidth - 24);
    callout.style.width = `${cw}px`;
    const ch = callout.offsetHeight || 160;
    let top = r.bottom + 12;
    if (top + ch > window.innerHeight - 12) top = Math.max(12, r.top - ch - 12);
    let left = r.left + r.width / 2 - cw / 2;
    left = Math.max(12, Math.min(left, window.innerWidth - cw - 12));
    callout.style.top = `${top}px`;
    callout.style.left = `${left}px`;
  }

  function placeCenter() {
    spot.hidden = true;
    veil.hidden = false;
    callout.hidden = false;
    const cw = Math.min(380, window.innerWidth - 24);
    callout.style.width = `${cw}px`;
    const ch = callout.offsetHeight || 160;
    callout.style.top = `${Math.max(12, window.innerHeight / 2 - ch / 2)}px`;
    callout.style.left = `${window.innerWidth / 2 - cw / 2}px`;
  }

  function reposition() {
    if (!list) return;
    if (curTarget && document.body.contains(curTarget)) place(curTarget);
    else if (!curTarget && !callout.hidden) placeCenter();
  }

  function renderCallout(s) {
    const total = list.length;
    const isClick = !!s.click;
    callout.innerHTML = `
      <div class="tour-title">${s.title}</div>
      <div class="tour-body">${s.body}</div>
      <div class="tour-foot">
        <button class="tour-skip" type="button">Skip tour</button>
        <div class="tour-nav">
          <span class="tour-count">${idx + 1} / ${total}</span>
          ${isClick ? `<span class="tour-hint">click the highlighted control ↑</span>`
                    : `<button class="btn primary tour-next" type="button">${s.next || "Next ›"}</button>`}
        </div>
      </div>`;
    callout.querySelector(".tour-skip").addEventListener("click", finish);
    const nextBtn = callout.querySelector(".tour-next");
    if (nextBtn) nextBtn.addEventListener("click", () => (s.finish ? finish() : advance()));
  }

  function showStep(retries = 0) {
    clearClick();
    const s = list[idx];
    if (s.commit) localStorage.setItem(FLAG, s.commit);
    ensureTab(s.tab);

    const el = s.sel ? $(s.sel) : null;
    if (s.sel && !el) {
      if (retries < 20) return void setTimeout(() => showStep(retries + 1), 80);
      return advance(); // give up on a missing target rather than trapping the user
    }
    curTarget = el;
    renderCallout(s);

    if (el) {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      requestAnimationFrame(() => setTimeout(() => place(el), 60));
    } else {
      placeCenter();
    }

    if (s.click) {
      clickEl = $(s.click);
      if (clickEl) {
        clickFn = () => setTimeout(advance, 120); // let the app's own handler run first
        clickEl.addEventListener("click", clickFn);
      }
    }
  }

  function advance() {
    clearClick();
    idx += 1;
    if (idx >= list.length) return finish();
    showStep();
  }

  function run(steps) {
    if (!veil) buildDom();
    list = steps;
    idx = 0;
    document.body.style.overflow = "";
    showStep();
  }

  function startHome() {
    localStorage.setItem(FLAG, "home");
    localStorage.setItem(SEEN, "1");
    run(HOME_STEPS);
  }

  // ---------- launch wiring ----------

  window.IB_startTutorial = startHome;
  const wire = (id) => { const el = document.getElementById(id); if (el) el.addEventListener("click", startHome); };
  if (onHome) { wire("tutorialBtn"); wire("emptyTutorialBtn"); }

  const flag = localStorage.getItem(FLAG);
  if (onProject && flag === "project") {
    run(PROJECT_STEPS);
  } else if (onHome && flag === "home") {
    run(HOME_STEPS);
  } else if (onHome && !localStorage.getItem(SEEN)) {
    // First-ever visit with no projects: offer the tour once.
    fetch("/api/projects")
      .then((r) => r.json())
      .then((p) => { if (Array.isArray(p) && p.length === 0) startHome(); })
      .catch(() => {});
  }
})();
