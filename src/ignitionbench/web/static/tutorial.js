// Guided tours: interactive, re-openable coach-mark walkthroughs. Each step
// rings a real control on the actual page, explains it, and (for action steps)
// advances when the user clicks it. Three tours: the home → project designer
// "first motor" tour, and a Propellant Engine tour. Works offline; only the
// Review / AutoCast steps need an API key.
(() => {
  const FLAG = "ib-tour"; // "home" | "project" while the first-motor tour spans pages
  const SEEN = "ib-tour-seen";
  const path = location.pathname;
  const onProject = /^\/project\//.test(path) || !!window.PROJECT_ID;
  const onEngine = path === "/engine";
  const onHome = path === "/" || path === "";
  const $ = (s, r = document) => r.querySelector(s);

  // ---------- step lists ----------

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
      sel: "#projectName",
      title: "Name your motor", body: "This is the name field — type a name for your motor here (for example “My first KNSB J”).",
    },
    {
      sel: "#modalCreate", click: "#modalCreate", commit: "project",
      title: "Create it", body: "Now click <b>Create</b> to open the designer.",
    },
  ];

  const PROJECT_STEPS = [
    // --- Propellant tab ---
    {
      sel: "#propMode",
      title: "Propellant source",
      body: "<b>Library</b> uses a published, characterized propellant; <b>Custom batch</b> lets you type your own measured burn data.",
    },
    {
      sel: "#propellant",
      title: "The propellant",
      body: "KNSB is selected — a forgiving, well-documented first propellant. Its burn data is real published data, never invented.",
    },
    {
      sel: "#libMeta",
      title: "Its properties",
      body: "The measured physics of this propellant: <b>density</b>, <b>c*</b> (how much exhaust velocity the chemistry gives), <b>γ</b>, <b>flame temperature</b>, and the <b>pressure range</b> the data is valid for.",
    },
    {
      sel: "#burnRateChart",
      title: "Burn-rate curve",
      body: "How fast the propellant burns at each chamber pressure — the heart of every calculation here.",
    },
    {
      sel: '.steps .step[data-tab="motor"]', click: '.steps .step[data-tab="motor"]',
      title: "Shape the motor", body: "Click <b>Motor design</b> to build the grain and nozzle.",
    },
    // --- Motor design tab ---
    {
      sel: "#core_d_mm", tab: "motor",
      title: "The grain",
      body: "A BATES grain: <b>Segments</b> (how many), <b>Outer Ø</b> (fits your casing), <b>Core Ø</b> (the hole — your biggest lever on burning area), and <b>Length</b>.",
    },
    {
      sel: "#slit_count", tab: "motor",
      title: "Face slits (optional)",
      body: "Advanced: cuts that add burning area early in the burn. Leave <b>Slits</b> at 0 for a plain BATES motor.",
    },
    {
      sel: "#throat_d_mm", tab: "motor",
      title: "The nozzle",
      body: "<b>Throat Ø</b> is your main tuning knob — shrink it and pressure and thrust climb; open it and they fall. <b>Half-angle</b> is the divergent cone.",
    },
    {
      sel: "#tab-motor .spec", tab: "motor",
      title: "Nozzle spec",
      body: "Computed geometry: <b>expansion ratio ε</b>, <b>exit diameter</b>, <b>divergent length</b>, <b>propellant mass</b>, and <b>port/throat</b> (keep it above ~2 to avoid erosive burning).",
    },
    {
      sel: "#stlBtn", tab: "motor",
      title: "Export the grain",
      body: "Download one grain segment as an <b>STL</b> file for CAD or 3D printing.",
    },
    {
      sel: "#tab-motor .tiles .tile:nth-child(1)", tab: "motor",
      title: "Kn",
      body: "The burning area divided by the throat area. Higher Kn → higher chamber pressure.",
    },
    {
      sel: "#tab-motor .tiles .tile:nth-child(2)", tab: "motor",
      title: "Chamber pressure",
      body: "The steady-state pressure inside the motor (psi, with MPa below). This drives burn rate and thrust — and the structural limits.",
    },
    {
      sel: "#tab-motor .tiles .tile:nth-child(3)", tab: "motor",
      title: "Thrust",
      body: "The force the motor produces at this operating point, in newtons.",
    },
    {
      sel: "#tab-motor .tiles .tile:nth-child(4)", tab: "motor",
      title: "Motor class",
      body: "The NAR/TRA impulse class letter (A, B, C … J, K). Each letter is roughly double the total impulse of the one before.",
    },
    {
      sel: "#viewer3d", tab: "motor",
      title: "3D model",
      body: "A live cutaway of your grain — drag to orbit, scroll to zoom. It updates as you change the numbers.",
    },
    {
      sel: "#warnings", tab: "motor",
      title: "Safety warnings",
      body: "Anything risky about this design — overpressure, a tight port, data-range limits — shows up here.",
    },
    {
      sel: '.steps .step[data-tab="simulation"]', click: '.steps .step[data-tab="simulation"]',
      title: "Simulate the burn", body: "Click <b>Simulation</b> to see how the motor behaves over time.",
    },
    // --- Simulation tab ---
    {
      sel: "#simTiles", tab: "simulation",
      title: "Simulated performance",
      body: "Delivered numbers from the burn regression: <b>max thrust</b>, <b>max pressure</b>, <b>burn time</b>, <b>total impulse</b>, <b>delivered Isp</b>, and <b>peak Kn</b>.",
    },
    {
      sel: "#playBtn", tab: "simulation",
      title: "Play the burn",
      body: "Press <b>▶ Play</b> to animate the grain regressing. Use the speed selector and the slider below to scrub to any instant.",
    },
    {
      sel: "#thrustChart", tab: "simulation",
      title: "Thrust curve",
      body: "Thrust versus time — the shape of the motor's push. A flat curve is neutral; a rising one is progressive.",
    },
    {
      sel: "#pressureChart", tab: "simulation",
      title: "Pressure curve",
      body: "Chamber pressure versus time, synced to the thrust curve.",
    },
    {
      sel: '.steps .step[data-tab="review"]', click: '.steps .step[data-tab="review"]',
      title: "Get a safety review", body: "Finally, click <b>Review</b>.",
    },
    // --- Review tab ---
    {
      sel: "#reviewBtn", tab: "review",
      title: "Delta's safety review",
      body: "Run a full plain-language safety review of the whole design (needs an API key). Delta never signs off a design — that's a human's call.",
    },
    {
      title: "You did it! 🎉",
      body: "You designed, simulated, and reviewed your first motor. Before any real hardware: work under a certified mentor or RSO, use published data, validate against BurnSim, and static-test before you fly. Reopen this tour anytime from the <b>🎓 Guided tutorial</b> button on the home screen.",
      next: "Finish", finish: true,
    },
  ];

  const ENGINE_STEPS = [
    {
      title: "The Propellant Engine",
      body: "This is where you develop your own propellant and its grain casting. Let's make one together.",
      next: "Start",
    },
    {
      sel: "#newPropTop", click: "#newPropTop",
      title: "New propellant", body: "Click <b>+ New propellant</b>.",
    },
    {
      sel: "#newPropName",
      title: "Name your batch", body: "Type a name for your propellant here.",
    },
    {
      sel: "#newModalCreate", click: "#newModalCreate",
      title: "Create it", body: "Click <b>Create</b> — it starts from a published KNSB baseline you can adjust.",
    },
    {
      sel: ".steps", tab: "plan",
      title: "Four steps",
      body: "Every propellant moves through <b>Plan</b> → <b>Prepare</b> → <b>Cast</b> → <b>Characterization</b>.",
    },
    {
      sel: "#ingredientRows", tab: "plan",
      title: "Ingredients",
      body: "Document your recipe's ingredients here — this is your <b>notebook</b>. IgnitionBench never invents formulations, ratios, or mixing steps.",
    },
    {
      sel: "#sourceMode", tab: "plan",
      title: "Burn-rate source",
      body: "<b>Start from published</b> data (relabeled with your batch name), or switch to <b>your own a/n</b> from strand-burner tests.",
    },
    {
      sel: "#baseMeta", tab: "plan",
      title: "Baseline properties",
      body: "The published baseline's real measured properties — density, c*, γ, flame temp, and validated pressure range.",
    },
    {
      sel: "#saveProp", tab: "plan",
      title: "Save it",
      body: "Save changes to this propellant. Once saved, it appears in <b>every project's</b> propellant menu.",
    },
    {
      sel: '.steps .step[data-tab="prepare"]', click: '.steps .step[data-tab="prepare"]',
      title: "Prepare", body: "Click <b>Prepare</b>.",
    },
    {
      sel: "#safetyCheck", tab: "prepare",
      title: "Safety checklist",
      body: "A checklist for making propellant safely. This is the dangerous step — Delta will <b>not</b> give you a mixing or casting procedure; that's done under a certified mentor or RSO.",
    },
    {
      sel: "#prepNotes", tab: "prepare",
      title: "Your notes",
      body: "Record your own preparation process, cure times, tooling, and safety measures.",
    },
    {
      sel: '.steps .step[data-tab="cast"]', click: '.steps .step[data-tab="cast"]',
      title: "Cast", body: "Click <b>Cast</b> to shape the grain from this propellant.",
    },
    {
      sel: "#g_core_d_mm", tab: "cast",
      title: "Cast the grain",
      body: "BATES grain and nozzle inputs — the same physics as the full designer, using this propellant.",
    },
    {
      sel: "#tab-cast .tiles", tab: "cast",
      title: "Live results",
      body: "<b>Kn</b>, <b>chamber pressure</b>, <b>thrust</b>, and <b>class</b> for this propellant, updating as you design.",
    },
    {
      sel: "#ambient_preset", tab: "cast",
      title: "Ambient pressure",
      body: "Set where the motor fires — sea level, altitude, or vacuum — and watch thrust and Isp change.",
    },
    {
      sel: "#autocastBtn", tab: "cast",
      title: "AutoCast",
      body: "Describe how you want it to fly and Delta proposes grain geometry (needs an API key). You approve it before anything is applied.",
    },
    {
      sel: "#createProject", tab: "cast",
      title: "Make a project",
      body: "Turn this propellant and grain into a full motor project.",
    },
    {
      sel: '.steps .step[data-tab="char"]', click: '.steps .step[data-tab="char"]',
      title: "Characterization", body: "Click <b>Characterization</b>.",
    },
    {
      sel: "#charRows", tab: "char",
      title: "Test burns",
      body: "Making your own propellant means measuring it. Log real test-firing data here — pressure versus measured burn rate.",
    },
    {
      sel: "#charChart", tab: "char",
      title: "Fit a and n",
      body: "It fits the burn-rate law r = a·Pⁿ from your points, shows the quality of the fit, and <b>Use in Plan</b> sends a and n back to the Plan tab.",
    },
    {
      title: "That's the Propellant Engine! 🎉",
      body: "You can develop, characterize, and cast your own propellants here — and everything you save shows up in every project. Remember: real propellant work happens under a certified mentor, never from an app. Reopen this tour anytime from the <b>🎓 Tutorial</b> button.",
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
    list = null;
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

  const visible = (el) => el && el.offsetWidth > 0 && el.offsetHeight > 0;

  function place(el) {
    const r = el.getBoundingClientRect();
    const pad = 6;
    spot.hidden = false;
    veil.hidden = true;
    spot.style.top = `${r.top - pad}px`;
    spot.style.left = `${r.left - pad}px`;
    spot.style.width = `${r.width + pad * 2}px`;
    spot.style.height = `${r.height + pad * 2}px`;

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
    else if (!curTarget && callout && !callout.hidden) placeCenter();
  }

  function renderCallout(s) {
    const isClick = !!s.click;
    callout.innerHTML = `
      <div class="tour-title">${s.title}</div>
      <div class="tour-body">${s.body}</div>
      <div class="tour-foot">
        <button class="tour-skip" type="button">Skip tour</button>
        <div class="tour-nav">
          <span class="tour-count">${idx + 1} / ${list.length}</span>
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
    if (s.sel && !visible(el)) {
      if (retries < 30) return void setTimeout(() => showStep(retries + 1), 100);
      return advance(); // don't trap the user on a target that never appears
    }
    curTarget = el;
    renderCallout(s);

    if (el) {
      // Instant (not smooth) so the ringed control is guaranteed on-screen and
      // clickable the moment the callout appears, with no mid-scroll lag.
      el.scrollIntoView({ block: "center", behavior: "auto" });
      requestAnimationFrame(() => place(el));
    } else {
      placeCenter();
    }

    if (s.click) {
      clickEl = $(s.click);
      if (clickEl) {
        clickFn = () => setTimeout(advance, 140); // let the app's own handler run first
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
  function startEngine() { run(ENGINE_STEPS); }

  // ---------- launch wiring ----------

  window.IB_startTutorial = startHome;
  window.IB_startEngineTour = startEngine;
  const wire = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };

  if (onHome) { wire("tutorialBtn", startHome); wire("emptyTutorialBtn", startHome); }
  if (onEngine) wire("engineTutorialBtn", startEngine);

  const flag = localStorage.getItem(FLAG);
  if (onProject && flag === "project") {
    run(PROJECT_STEPS);
  } else if (onHome && flag === "home") {
    run(HOME_STEPS);
  } else if (onHome && !localStorage.getItem(SEEN)) {
    fetch("/api/projects")
      .then((r) => r.json())
      .then((p) => { if (Array.isArray(p) && p.length === 0) startHome(); })
      .catch(() => {});
  }
})();
