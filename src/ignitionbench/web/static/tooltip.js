// Global hover tooltips: any element carrying [data-tip] shows a description
// bubble after the pointer rests on it for ~1 second, and hides on leave.
(() => {
  const DELAY = 1000;
  let bubble = null;
  let timer = null;
  let current = null;

  function ensureBubble() {
    if (!bubble) {
      bubble = document.createElement("div");
      bubble.className = "tooltip-bubble";
      bubble.hidden = true;
      document.body.appendChild(bubble);
    }
    return bubble;
  }

  function show(el) {
    const tip = el.getAttribute("data-tip");
    if (!tip) return;
    const b = ensureBubble();
    b.textContent = tip;
    b.style.visibility = "hidden"; // measure without a flash at (0,0)
    b.hidden = false;
    const r = el.getBoundingClientRect();
    const bw = b.offsetWidth;
    const bh = b.offsetHeight;
    const left = Math.max(8, Math.min(r.left + r.width / 2 - bw / 2, innerWidth - bw - 8));
    let top = r.top - bh - 8;
    if (top < 8) top = r.bottom + 8; // flip below when there's no room above
    b.style.left = `${left}px`;
    b.style.top = `${top}px`;
    b.style.visibility = "visible";
  }

  function hide() {
    clearTimeout(timer);
    timer = null;
    current = null;
    if (bubble) bubble.hidden = true;
  }

  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("[data-tip]");
    if (!el || el === current) return;
    hide();
    current = el;
    timer = setTimeout(() => show(el), DELAY);
  });
  document.addEventListener("mouseout", (e) => {
    if (current && e.target.closest("[data-tip]") === current) hide();
  });
  // never strand a bubble
  addEventListener("scroll", hide, true);
  document.addEventListener("click", hide, true);
})();
