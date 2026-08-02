// AI mentor: slide-out chat drawer (every page) + the project Review tab.
// Plain script — runs on both home and project pages; project features
// activate only when window.PROJECT_ID is set.

(() => {
  const $ = (id) => document.getElementById(id);
  const projectId = window.PROJECT_ID || null;
  const history = []; // [{role, content}] for this page visit
  let aiStatus = null;
  let busy = false;

  // ---------- tiny markdown renderer (headings, lists, bold/italic/code) ----------

  const escapeHtml = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function inline(s) {
    return escapeHtml(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }

  function renderMarkdown(md) {
    const out = [];
    let list = null; // "ul" | "ol"
    const closeList = () => {
      if (list) { out.push(`</${list}>`); list = null; }
    };
    for (const raw of md.split("\n")) {
      const line = raw.trimEnd();
      const h = line.match(/^(#{1,4})\s+(.*)/);
      const ul = line.match(/^[-*]\s+(.*)/);
      const ol = line.match(/^\d+[.)]\s+(.*)/);
      if (h) {
        closeList();
        const level = Math.min(h[1].length + 2, 5); // # → h3 inside the panel
        out.push(`<h${level}>${inline(h[2])}</h${level}>`);
      } else if (ul) {
        if (list !== "ul") { closeList(); out.push("<ul>"); list = "ul"; }
        out.push(`<li>${inline(ul[1])}</li>`);
      } else if (ol) {
        if (list !== "ol") { closeList(); out.push("<ol>"); list = "ol"; }
        out.push(`<li>${inline(ol[1])}</li>`);
      } else if (line.trim() === "") {
        closeList();
      } else {
        closeList();
        out.push(`<p>${inline(line)}</p>`);
      }
    }
    closeList();
    return out.join("");
  }

  // ---------- drawer ----------

  function addMessage(role, html, cls = "") {
    const div = document.createElement("div");
    div.className = `ai-msg ${role} ${cls}`;
    div.innerHTML = html;
    $("aiMessages").appendChild(div);
    $("aiMessages").scrollTop = $("aiMessages").scrollHeight;
    return div;
  }

  const NOT_CONFIGURED = "Delta needs your Anthropic API key — open the ✦ Delta panel to add it.";

  async function ensureStatus() {
    if (aiStatus) return aiStatus;
    try {
      aiStatus = await (await fetch("/api/ai/status")).json();
    } catch {
      aiStatus = { configured: false, source: "none", editable: true };
    }
    return aiStatus;
  }

  // ---------- API key panel (lives at the top of the drawer) ----------

  const keyPanel = document.createElement("div");
  keyPanel.className = "ai-keypanel";
  keyPanel.hidden = true;
  $("aiMessages").before(keyPanel);

  function renderKeyPanel() {
    const s = aiStatus || {};
    if (s.source === "env" || s.source === "credentials") {
      // A key is supplied outside the app; nothing to manage here.
      keyPanel.hidden = true;
      keyPanel.innerHTML = "";
      return;
    }
    keyPanel.hidden = false;
    if (s.source === "stored") {
      keyPanel.innerHTML =
        `<div class="ai-keynote">API key added ` +
        `<span class="ai-keyhint">${escapeHtml(s.key_hint || "")}</span>` +
        `<button type="button" class="link-btn" id="aiKeyRemove">Remove</button></div>`;
      $("aiKeyRemove").addEventListener("click", removeKey);
      return;
    }
    // No key yet: show the entry form.
    keyPanel.innerHTML =
      `<form class="ai-keyform" id="aiKeyForm">
         <p>Delta needs your Anthropic API key. It's stored only on this computer
         and never leaves it.</p>
         <input id="aiKeyInput" type="password" placeholder="sk-ant-…"
                autocomplete="off" spellcheck="false">
         <div class="ai-keyrow">
           <button class="btn primary" type="submit">Save key</button>
           <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noopener">Get a key ↗</a>
         </div>
         <div class="ai-keymsg" id="aiKeyMsg"></div>
       </form>`;
    $("aiKeyForm").addEventListener("submit", (e) => {
      e.preventDefault();
      const k = $("aiKeyInput").value.trim();
      if (k) saveKey(k);
    });
  }

  async function saveKey(key) {
    const msg = $("aiKeyMsg");
    if (msg) msg.textContent = "Checking your key…";
    try {
      const res = await fetch("/api/ai/key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
      aiStatus = d;
      renderKeyPanel();
      if (aiStatus.configured) greet(true);
    } catch (err) {
      if ($("aiKeyMsg")) $("aiKeyMsg").textContent = `⚠ ${err.message}`;
    }
  }

  async function removeKey() {
    try {
      aiStatus = await (await fetch("/api/ai/key", { method: "DELETE" })).json();
    } catch {
      aiStatus = { configured: false, source: "none", editable: true };
    }
    renderKeyPanel();
  }

  function greet(force = false) {
    if ($("aiMessages").dataset.greeted && !force) return;
    $("aiMessages").dataset.greeted = "1";
    addMessage(
      "assistant",
      projectId
        ? "I can see your current design. Ask me anything — or ask me to change it, and I'll explain what I did and why."
        : "Ask me about rocketry, safety practice, or the design process. Open a project and I can review or edit the design itself.",
      "notice",
    );
  }

  async function openDrawer() {
    $("aiDrawer").hidden = false;
    $("aiTab").hidden = true;
    const status = await ensureStatus();
    renderKeyPanel();
    if (status.configured) greet();
    $("aiText").focus();
  }

  function closeDrawer() {
    $("aiDrawer").hidden = true;
    $("aiTab").hidden = false;
  }

  async function send() {
    const text = $("aiText").value.trim();
    if (!text || busy) return;
    const status = await ensureStatus();
    if (!status.configured) {
      renderKeyPanel();
      if ($("aiKeyInput")) $("aiKeyInput").focus();
      return;
    }
    busy = true;
    $("aiSend").disabled = true;
    $("aiText").value = "";
    history.push({ role: "user", content: text });
    addMessage("user", escapeHtml(text));
    const pending = addMessage("assistant", "Thinking…", "pending");
    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, messages: history }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
      history.push({ role: "assistant", content: d.reply });
      pending.classList.remove("pending");
      pending.innerHTML = renderMarkdown(d.reply);
      if (d.updated && d.project) {
        addMessage("assistant", "✏️ Delta updated your design — the forms and results have refreshed.", "notice");
        window.dispatchEvent(new CustomEvent("ai-project-updated", { detail: d.project }));
      }
    } catch (err) {
      history.pop(); // let the user retry the same question
      pending.classList.remove("pending");
      pending.classList.add("notice");
      pending.innerHTML = `⚠ ${escapeHtml(err.message)}`;
    } finally {
      busy = false;
      $("aiSend").disabled = false;
      $("aiMessages").scrollTop = $("aiMessages").scrollHeight;
    }
  }

  $("aiTab").addEventListener("click", openDrawer);
  $("aiClose").addEventListener("click", closeDrawer);
  $("aiForm").addEventListener("submit", (e) => { e.preventDefault(); send(); });
  $("aiText").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });

  // ---------- Review tab (project pages only) ----------

  if (!projectId || !$("reviewBtn")) return;

  let reviewRan = false;
  let reviewBusy = false;

  async function runReview() {
    if (reviewBusy) return;
    const status = await ensureStatus();
    const note = $("reviewStatus");
    if (!status.configured) {
      note.hidden = false;
      note.innerHTML = NOT_CONFIGURED;
      return;
    }
    reviewBusy = true;
    reviewRan = true;
    $("reviewBtn").disabled = true;
    note.hidden = false;
    note.textContent = "Delta is reviewing your project — this takes a moment…";
    try {
      const res = await fetch("/api/ai/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || `HTTP ${res.status}`);
      note.hidden = true;
      $("reviewBody").innerHTML = renderMarkdown(d.review);
    } catch (err) {
      note.textContent = `⚠ Review failed: ${err.message}`;
      reviewRan = false; // allow the auto-run to retry next time
    } finally {
      reviewBusy = false;
      $("reviewBtn").disabled = false;
    }
  }

  $("reviewBtn").addEventListener("click", runReview);
  window.addEventListener("review-tab-opened", () => {
    if (!reviewRan) runReview();
  });
})();
