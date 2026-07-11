// Minimal dark line chart: single series, recessive grid, hover crosshair
// with tooltip, and an external time cursor for animation sync.

const NS = "http://www.w3.org/2000/svg";

function niceTicks(min, max, count = 4) {
  const span = max - min || 1;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(v);
  return ticks;
}

function el(name, attrs) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

export function lineChart(container, { x, y, xLabel, yLabel, color = "#3987e5", yFmt = (v) => v.toFixed(1) }) {
  container.innerHTML = "";
  const W = 520, H = 240, padL = 52, padR = 14, padT = 12, padB = 34;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
  container.appendChild(svg);

  const xMin = Math.min(...x), xMax = Math.max(...x);
  const yMin = 0, yMax = Math.max(...y) * 1.06 || 1;
  const sx = (v) => padL + ((v - xMin) / (xMax - xMin || 1)) * (W - padL - padR);
  const sy = (v) => H - padB - ((v - yMin) / (yMax - yMin)) * (H - padT - padB);

  for (const t of niceTicks(yMin, yMax)) {
    svg.appendChild(el("line", { x1: padL, y1: sy(t), x2: W - padR, y2: sy(t), stroke: "#26251f", "stroke-width": 1 }));
    const label = el("text", { x: padL - 8, y: sy(t) + 4, fill: "#8f8e84", "font-size": 11, "text-anchor": "end", "font-family": "ui-monospace,Menlo,monospace" });
    label.textContent = yFmt(t);
    svg.appendChild(label);
  }
  for (const t of niceTicks(xMin, xMax, 5)) {
    const label = el("text", { x: sx(t), y: H - padB + 18, fill: "#8f8e84", "font-size": 11, "text-anchor": "middle", "font-family": "ui-monospace,Menlo,monospace" });
    label.textContent = t.toFixed(1);
    svg.appendChild(label);
  }
  svg.appendChild(el("line", { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB, stroke: "#3a3937", "stroke-width": 1 }));

  const xl = el("text", { x: (padL + W - padR) / 2, y: H - 4, fill: "#8f8e84", "font-size": 11, "text-anchor": "middle" });
  xl.textContent = xLabel;
  svg.appendChild(xl);
  const yl = el("text", { x: 12, y: (padT + H - padB) / 2, fill: "#8f8e84", "font-size": 11, "text-anchor": "middle", transform: `rotate(-90 12 ${(padT + H - padB) / 2})` });
  yl.textContent = yLabel;
  svg.appendChild(yl);

  const path = x.map((v, i) => `${i ? "L" : "M"}${sx(v).toFixed(1)},${sy(y[i]).toFixed(1)}`).join("");
  svg.appendChild(el("path", { d: path, fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));

  // animation cursor
  const cursor = el("line", { x1: 0, y1: padT, x2: 0, y2: H - padB, stroke: "#c3c2b7", "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" });
  const cursorDot = el("circle", { r: 4, fill: color, stroke: "#1a1a19", "stroke-width": 2, visibility: "hidden" });
  svg.appendChild(cursor);
  svg.appendChild(cursorDot);

  // hover layer
  const hoverLine = el("line", { x1: 0, y1: padT, x2: 0, y2: H - padB, stroke: "#55534d", "stroke-width": 1, visibility: "hidden" });
  const hoverDot = el("circle", { r: 4.5, fill: color, stroke: "#1a1a19", "stroke-width": 2, visibility: "hidden" });
  svg.appendChild(hoverLine);
  svg.appendChild(hoverDot);
  const tip = document.createElement("div");
  tip.className = "chart-tip";
  tip.hidden = true;
  container.appendChild(tip);

  function nearestIndex(xVal) {
    let lo = 0, hi = x.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (x[mid] < xVal) lo = mid; else hi = mid;
    }
    return xVal - x[lo] < x[hi] - xVal ? lo : hi;
  }

  svg.addEventListener("mousemove", (e) => {
    const rect = svg.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    if (px < padL || px > W - padR) return;
    const i = nearestIndex(xMin + ((px - padL) / (W - padL - padR)) * (xMax - xMin));
    const cx = sx(x[i]), cy = sy(y[i]);
    hoverLine.setAttribute("x1", cx); hoverLine.setAttribute("x2", cx);
    hoverLine.setAttribute("visibility", "visible");
    hoverDot.setAttribute("cx", cx); hoverDot.setAttribute("cy", cy);
    hoverDot.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.style.left = `${(cx / W) * rect.width}px`;
    tip.style.top = `${(cy / H) * rect.height}px`;
    tip.textContent = `${x[i].toFixed(2)} s · ${yFmt(y[i])} ${yLabel}`;
  });
  svg.addEventListener("mouseleave", () => {
    hoverLine.setAttribute("visibility", "hidden");
    hoverDot.setAttribute("visibility", "hidden");
    tip.hidden = true;
  });

  return {
    setCursor(xVal) {
      if (xVal == null) {
        cursor.setAttribute("visibility", "hidden");
        cursorDot.setAttribute("visibility", "hidden");
        return;
      }
      const i = nearestIndex(xVal);
      const cx = sx(x[i]);
      cursor.setAttribute("x1", cx); cursor.setAttribute("x2", cx);
      cursor.setAttribute("visibility", "visible");
      cursorDot.setAttribute("cx", cx); cursorDot.setAttribute("cy", sy(y[i]));
      cursorDot.setAttribute("visibility", "visible");
    },
  };
}
