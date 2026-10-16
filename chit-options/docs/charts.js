// Small SVG charts with hover tooltips. No dependencies.
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tooltip");

  function el(name, attrs = {}, parent) {
    const node = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  function niceMax(v) {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }

  function showTip(html, clientX, clientY) {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    const r = t.getBoundingClientRect();
    let x = clientX + 14, y = clientY - r.height - 12;
    if (x + r.width > window.innerWidth - 8) x = clientX - r.width - 14;
    if (y < 8) y = clientY + 16;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  function hideTip() { tip().hidden = true; }

  function legend(container, series) {
    const row = document.createElement("div");
    row.className = "chart-legend";
    row.style.cssText = "display:flex;gap:1.1rem;flex-wrap:wrap;font-family:var(--sans);font-size:.92rem;color:var(--ink-2);margin-bottom:.4rem";
    for (const s of series) {
      const item = document.createElement("span");
      item.innerHTML = `<span style="display:inline-block;width:16px;height:3px;border-radius:2px;background:${s.color};vertical-align:middle;margin-right:6px"></span>${s.name}`;
      row.appendChild(item);
    }
    container.appendChild(row);
  }

  // opts: { x: [..], series: [{name, color, values}], xLabel, yLabel,
  //         yFormat(v), xFormat(v), band: {x0, x1, label} }
  function lineChart(container, opts) {
    container.innerHTML = "";
    legend(container, opts.series);
    const W = Math.max(300, container.clientWidth);
    const H = Math.round(Math.min(380, Math.max(250, W * 0.52)));
    const m = { l: 46, r: W < 480 ? 16 : 92, t: 18, b: 44 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.label || "" }, container);
    const xs = opts.x, n = xs.length;
    const all = opts.series.flatMap(s => s.values.filter(v => v != null));
    const yMax = niceMax(Math.max(...all) * 1.08);
    const xMin = xs[0], xMax = xs[n - 1];
    const X = v => m.l + (v - xMin) / (xMax - xMin || 1) * (W - m.l - m.r);
    const Y = v => H - m.b - (v / yMax) * (H - m.t - m.b);

    if (opts.band) {
      const x0 = X(Math.max(opts.band.x0, xMin)), x1 = X(Math.min(opts.band.x1, xMax));
      el("rect", { class: "range-band", x: x0, y: m.t, width: Math.max(0, x1 - x0), height: H - m.t - m.b }, svg);
      const lab = el("text", { class: "band-label", x: x0 + 6, y: m.t + 14 }, svg);
      lab.textContent = opts.band.label;
    }
    const ticks = 5;
    const ax = el("g", { class: "axis" }, svg);
    for (let i = 0; i <= ticks; i++) {
      const v = yMax * i / ticks, y = Y(v);
      el("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y, y2: y }, ax);
      const t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end" }, ax);
      t.textContent = opts.yFormat(v);
    }
    const maxTicks = W < 480 ? 5 : 9;
    const xStep = [1, 2, 5, 10, 20].find(st => (xMax - xMin) / st <= maxTicks) || 50;
    for (let v = Math.ceil(xMin / xStep) * xStep; v <= xMax; v += xStep) {
      const t = el("text", { x: X(v), y: H - m.b + 18, "text-anchor": "middle" }, ax);
      t.textContent = opts.xFormat ? opts.xFormat(v) : v;
    }
    const xl = el("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle" }, ax);
    xl.textContent = opts.xLabel;

    const ends = [];
    for (const s of opts.series) {
      let d = "";
      s.values.forEach((v, i) => { if (v != null) d += (d ? "L" : "M") + X(xs[i]).toFixed(1) + "," + Y(v).toFixed(1); });
      el("path", { class: "series", d, style: `stroke:${s.color}` }, svg);
      let last = s.values.length - 1;
      while (last > 0 && s.values[last] == null) last--;
      ends.push({ s, x: X(xs[last]), y: Y(s.values[last]) });
    }
    if (W >= 480) {   // direct labels at line ends, nudged apart
      ends.sort((a, b) => a.y - b.y);
      for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 16) ends[i].y = ends[i - 1].y + 16;
      for (const e of ends) {
        const t = el("text", { class: "direct-label", x: e.x + 8, y: e.y + 4 }, svg);
        t.textContent = e.s.short || e.s.name;
      }
    }

    const hover = el("g", { style: "display:none" }, svg);
    const cross = el("line", { class: "crosshair", y1: m.t, y2: H - m.b }, hover);
    const dots = opts.series.map(s => el("circle", { class: "hover-dot", r: 5, style: `fill:${s.color}` }, hover));
    const hit = el("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" }, svg);
    hit.style.cursor = "crosshair";
    const move = ev => {
      const box = svg.getBoundingClientRect();
      const px = (ev.clientX - box.left) * (W / box.width);
      let i = Math.round((px - m.l) / (W - m.l - m.r) * (n - 1));
      i = Math.max(0, Math.min(n - 1, i));
      const x = X(xs[i]);
      hover.style.display = "";
      cross.setAttribute("x1", x); cross.setAttribute("x2", x);
      let rows = `<strong>${opts.tipTitle ? opts.tipTitle(xs[i]) : xs[i]}</strong>`;
      opts.series.forEach((s, j) => {
        const v = s.values[i];
        dots[j].style.display = v == null ? "none" : "";
        if (v != null) { dots[j].setAttribute("cx", x); dots[j].setAttribute("cy", Y(v)); }
        rows += `<br><span class="sw" style="background:${s.color}"></span>${s.name}: ${v == null ? "n/a" : opts.yFormat(v, true)}`;
      });
      showTip(rows, ev.clientX, ev.clientY);
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", () => { hover.style.display = "none"; hideTip(); });
  }

  // opts: { labels: [..], values: [..], color, xLabel, yFormat(v), tipTitle(label) }
  function barChart(container, opts) {
    container.innerHTML = "";
    const W = Math.max(280, container.clientWidth);
    const H = Math.round(Math.min(220, Math.max(170, W * 0.36)));
    const m = { l: 40, r: 8, t: 10, b: 40 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.label || "" }, container);
    const n = opts.values.length;
    const yMax = niceMax(Math.max(...opts.values) * 1.05);
    const bw = (W - m.l - m.r) / n;
    const Y = v => H - m.b - (v / yMax) * (H - m.t - m.b);
    const ax = el("g", { class: "axis" }, svg);
    for (let i = 0; i <= 4; i++) {
      const v = yMax * i / 4, y = Y(v);
      el("line", { class: "gridline", x1: m.l, x2: W - m.r, y1: y, y2: y }, ax);
      const t = el("text", { x: m.l - 6, y: y + 4, "text-anchor": "end" }, ax);
      t.textContent = opts.yFormat(v);
    }
    const step = Math.max(1, Math.ceil(n / 12));
    opts.values.forEach((v, i) => {
      const x = m.l + i * bw + 1, w = Math.max(1, bw - 2), y = Y(v), h = H - m.b - y;
      const r = Math.min(4, w / 2, h);
      const d = h <= 0 ? "" : `M${x},${H - m.b}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${H - m.b}Z`;
      const bar = el("path", { class: "bar", d, style: `fill:${opts.color}` }, svg);
      const hit = el("rect", { x: m.l + i * bw, y: m.t, width: bw, height: H - m.t - m.b, fill: "transparent" }, svg);
      const show = ev => showTip(`<strong>${opts.tipTitle(opts.labels[i])}</strong><br>${opts.yFormat(v, true)}`, ev.clientX, ev.clientY);
      hit.addEventListener("pointermove", show);
      hit.addEventListener("pointerdown", show);
      hit.addEventListener("pointerleave", hideTip);
      if (i % step === 0) {
        const t = el("text", { x: m.l + i * bw + bw / 2, y: H - m.b + 16, "text-anchor": "middle" }, ax);
        t.textContent = opts.labels[i];
      }
    });
    const xl = el("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle" }, ax);
    xl.textContent = opts.xLabel;
  }

  window.Charts = { lineChart, barChart, hideTip };
})();
