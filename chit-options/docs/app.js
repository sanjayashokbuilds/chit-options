(function () {
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
  const css = name => `var(${name})`;
  const pct = (v, d = 1) => (100 * v).toFixed(d) + "%";
  const rupees = v => "₹" + Math.round(v).toLocaleString("en-IN");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const state = { example: null, explore: null, tables: null, py: null };

  // ---------- segmented controls ----------
  function seg(group, value) {
    group.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.value === String(value))));
  }
  function segValue(group) {
    const b = group.querySelector('button[aria-pressed="true"]');
    return b ? b.dataset.value : null;
  }
  document.addEventListener("click", ev => {
    const b = ev.target.closest(".seg button");
    if (!b) return;
    const group = b.parentElement;
    seg(group, b.dataset.value);
    group.dispatchEvent(new CustomEvent("segchange", { bubbles: true }));
  });

  // ---------- the seat ring ----------
  const NS = "http://www.w3.org/2000/svg";
  const ring = { seats: [], t: 0, timer: null };

  function buildRing() {
    const ex = state.example, svg = document.getElementById("ring"), n = ex.members;
    const cx = 220, cy = 220, R = 176;
    const add = (name, attrs, parent = svg) => {
      const node = document.createElementNS(NS, name);
      for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
      parent.appendChild(node);
      return node;
    };
    ring.flow = add("line", { class: "flow", x1: cx, y1: cy, x2: cx, y2: cy });
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
      const g = add("g", { class: "seat" });
      const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
      const c = add("circle", { cx: x, cy: y, r: 18 }, g);
      const t = add("text", { class: "seat-num", x, y }, g);
      t.textContent = i === 0 ? "F" : i + 1;
      ring.seats.push({ c, t, x, y });
    }
    const ta = add("text", { class: "center-a", x: cx, y: cy - 40, lang: "ta" });
    ta.textContent = "சீட்டு";
    ring.month = add("text", { class: "center-b", x: cx, y: cy + 14 });
    ring.pot = add("text", { class: "center-c", x: cx, y: cy + 42 });

    const slider = document.getElementById("ring-month");
    slider.max = n;
    slider.addEventListener("input", () => { stopPlay(); showMonth(+slider.value - 1); });
    document.getElementById("ring-play").addEventListener("click", () => ring.timer ? stopPlay() : startPlay());
    showMonth(0);
    if (!reducedMotion) startPlay();
  }

  function showMonth(t) {
    const ex = state.example, n = ex.members, mo = ex.months[t];
    ring.t = t;
    const wonBefore = new Set(ex.months.slice(0, t).map(m => m.winner));
    const needy = new Set(mo.in_need);
    ring.seats.forEach((s, i) => {
      // the hero sits on the dark "night" band, so it uses fixed night colours
      let fill = "#20245a", stroke = "#8d92c4", sw = 2, text = "#c9ccf0";
      if (i === mo.winner) { fill = "#f2a900"; stroke = "#f2a900"; text = "#1b1f4b"; }
      else if (wonBefore.has(i)) { fill = "#2c3170"; stroke = "#2c3170"; text = "#7f84b8"; }
      else if (needy.has(i)) { stroke = "#f2a900"; sw = 4; }
      s.c.style.fill = fill; s.c.style.stroke = stroke; s.c.style.strokeWidth = sw;
      s.t.style.fill = text;
    });
    const w = ring.seats[mo.winner];
    // a line from just outside the centre text to the winning seat
    ring.flow.setAttribute("x1", 220 + (w.x - 220) * 0.5);
    ring.flow.setAttribute("y1", 220 + (w.y - 220) * 0.5);
    ring.flow.setAttribute("x2", 220 + (w.x - 220) * 0.8);
    ring.flow.setAttribute("y2", 220 + (w.y - 220) * 0.8);
    ring.month.textContent = `Month ${t + 1}`;
    ring.pot.textContent = `Pot ${rupees(ex.pot)}`;
    document.getElementById("ring-month").value = t + 1;
    document.getElementById("ring-month-label").textContent = `Month ${t + 1} of ${n}`;
    document.getElementById("ring-story").textContent = story(t);
  }

  function story(t) {
    const ex = state.example, n = ex.members, mo = ex.months[t];
    if (t === 0) return `The organiser (F) takes the first pot of ${rupees(ex.pot)} with no auction. Every member pays the full ${rupees(ex.instalment)}. Gold rings mark members who need cash.`;
    if (t === n - 1) return `Only seat ${mo.winner + 1} is left, so there is no auction. They take ${rupees(mo.payout)}: the pot less the organiser's commission.`;
    const waiting = mo.waiting.length, needy = mo.in_need.length;
    const needText = needy === 0 ? "none of whom need cash right now" : needy === 1 ? "one of whom needs cash now" : `${needy} of whom need cash now`;
    const shared = mo.discount * ex.pot - mo.commission;
    return `${waiting} members are still waiting, ${needText}. Seat ${mo.winner + 1} wins by giving up ${pct(mo.discount)} of the pot and takes ${rupees(mo.payout)}. ` +
      `The organiser keeps ${rupees(mo.commission)} and ${rupees(shared)} is shared out, so everyone pays ${rupees(mo.payment)} this month instead of ${rupees(ex.instalment)}.`;
  }

  function startPlay() {
    const btn = document.getElementById("ring-play");
    if (ring.t >= state.example.members - 1) showMonth(0);
    btn.textContent = "Pause"; btn.setAttribute("aria-pressed", "true");
    ring.timer = setInterval(() => {
      if (ring.t >= state.example.members - 1) return stopPlay();
      showMonth(ring.t + 1);
    }, 1600);
  }
  function stopPlay() {
    clearInterval(ring.timer); ring.timer = null;
    const btn = document.getElementById("ring-play");
    btn.textContent = "Play"; btn.setAttribute("aria-pressed", "false");
  }

  // ---------- rates explorer ----------
  const LABELS = {
    members: v => v,
    p_need: v => (+v === 0.0425 ? "4.25% (fitted)" : pct(+v, 0)),
    r_borrow: v => (+v === 0.033 ? "3.3% a month (fitted)" : pct(+v, 0) + " a month"),
    cap: v => (+v >= 0.6 ? "No cap" : pct(+v, 0)),
  };
  const DEFAULTS = { members: 40, p_need: 0.0425, r_borrow: 0.033, cap: 0.6 };

  function buildExplorer() {
    const grid = state.explore.grid;
    document.querySelectorAll("#explore-form .seg").forEach(group => {
      const name = group.dataset.name;
      for (const v of grid[name]) {
        const b = document.createElement("button");
        b.type = "button"; b.dataset.value = String(v); b.textContent = LABELS[name](v);
        group.appendChild(b);
      }
      seg(group, String(DEFAULTS[name]));
    });
    document.getElementById("explore-form").addEventListener("segchange", drawRates);
    drawRates();
    drawCap();
  }

  function scenario(n, p, rb, cap) { return state.explore.scenarios[`${n}|${p}|${rb}|${cap}`]; }

  function drawRates() {
    const v = {};
    document.querySelectorAll("#explore-form .seg").forEach(g => (v[g.dataset.name] = segValue(g)));
    const n = +v.members, s = scenario(v.members, v.p_need, v.r_borrow, v.cap);
    const months = s.yield.map((_, i) => i + 2);         // auctions run in months 2..N-1
    Charts.lineChart(document.getElementById("rates-chart"), {
      label: "Implied interest rate by month",
      x: months,
      series: [
        { name: "Yield to end", short: "Yield", color: css("--s-yield"), values: s.yield },
        { name: "Forward rate", short: "Forward", color: css("--s-forward"), values: s.forward },
      ],
      band: { x0: n / 4, x1: n / 3, label: "Practitioners' peak" },
      xLabel: "Month of the chit",
      yFormat: (y, exact) => (100 * y).toFixed(exact ? 1 : 0) + "%",
      tipTitle: m => `Month ${m} of ${n}`,
    });
    const peak = s.yield_peak_month + 1;              // our month index t -> calendar month t+1
    const where = peak / n, lo = 0.25 - 1e-9, hi = 1 / 3 + 1e-9;
    const verdict = where < lo ? "earlier than practitioners say" : where <= hi ? "where practitioners say" : "later than practitioners say";
    document.getElementById("rates-readout").innerHTML = `
      <div><dt>Average implied rate</dt><dd>${pct(s.mean_yield)}<small>a year</small></dd></div>
      <div><dt>Rates peak in</dt><dd>Month ${peak} of ${n}<small>${Math.round(100 * where)}% of the way in, ${verdict}</small></dd></div>
      <div><dt>First winning bid</dt><dd>${pct(s.discount[0])}<small>of the pot</small></dd></div>`;
  }

  function drawCap() {
    const before = scenario(40, 0.0425, 0.033, 0.6), after = scenario(40, 0.0425, 0.033, 0.3);
    Charts.lineChart(document.getElementById("cap-chart"), {
      label: "Yield to end before and after a 30% cap, calibrated model",
      x: before.yield.map((_, i) => i + 2),
      series: [
        { name: "No cap (before 1993)", short: "No cap", color: css("--s-yield"), values: before.yield },
        { name: "30% cap (after 1993)", short: "30% cap", color: css("--s-forward"), values: after.yield },
      ],
      band: { x0: 10, x1: 40 / 3, label: "Practitioners' peak" },
      xLabel: "Month of a 40-member chit",
      yFormat: (y, exact) => (100 * y).toFixed(exact ? 1 : 0) + "%",
      tipTitle: m => `Month ${m} of 40, yield to end`,
    });
  }

  // ---------- the model in the browser ----------
  async function loadModel() {
    const status = document.getElementById("model-status"), go = document.getElementById("advice-go");
    try {
      await new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = PYODIDE + "pyodide.js"; s.onload = res; s.onerror = () => rej(new Error("couldn't download Pyodide"));
        document.head.appendChild(s);
      });
      const py = await loadPyodide({ indexURL: PYODIDE });
      await py.loadPackage("numpy");
      const files = await (await fetch("py/files.json")).json();
      py.FS.mkdirTree("/home/pyodide/chit");
      for (const f of files) py.FS.writeFile(`/home/pyodide/chit/${f}`, await (await fetch(`py/chit/${f}`)).text());
      py.runPython("import sys; sys.path.insert(0, '/home/pyodide'); from chit.web import advise_json");
      state.py = py;
      status.textContent = "The model is running in your browser.";
      go.disabled = false; go.textContent = "Get advice";
    } catch (err) {
      status.textContent = `The model didn't load (${err.message}). Check your connection and reload the page.`;
      status.classList.add("error");
      go.textContent = "Model unavailable";
    }
  }

  function readAdviceForm() {
    const f = document.getElementById("advice-form");
    const n = +f.members.value, cap = +segValue(f.querySelector('[data-name="advice_cap"]'));
    const instalment = +f.instalment.value;
    const history = f.history.value.split(/[,\s]+/).filter(Boolean).map(Number);
    const myR = f.my_r.value.trim();
    if (!(instalment > 0)) throw new Error("Enter a monthly instalment above zero.");
    if (history.some(x => !Number.isFinite(x))) throw new Error("Winning bids should be numbers, like 38, 37, 37.");
    const low = 100 * state.tables.market.commission, high = 100 * cap;
    const bad = history.find(x => x < low - 1e-9 || x > high + 1e-9);
    if (bad !== undefined) throw new Error(`Each winning bid must be between ${low}% (the commission) and ${high}% (the cap). ${bad}% isn't.`);
    if (history.length + 2 > n - 1) throw new Error(`A ${n}-member chit has ${n - 2} auctions after the foreman's month; you entered ${history.length} bids already.`);
    return { n, cap, instalment, history: history.map(x => x / 100), in_need: segValue(f.querySelector('[data-name="in_need"]')) === "1",
             myR: myR === "" ? null : +myR / 100 };
  }

  function advise(ev) {
    ev.preventDefault();
    const out = document.getElementById("advice-out");
    let inp;
    try { inp = readAdviceForm(); } catch (err) { out.innerHTML = `<p class="status error">${err.message}</p>`; return; }
    const mk = state.tables.market;
    const req = {
      members: inp.n, instalment: inp.instalment, commission: mk.commission, cap: inp.cap,
      r_borrow: mk.r_borrow, r_save: mk.r_save, p_need: mk.p_need,
      in_need: inp.in_need, history: inp.history, my_r_borrow: inp.myR,
      table: state.tables.tables[`${inp.n}|${inp.cap}`],
    };
    const a = JSON.parse(state.py.globals.get("advise_json")(JSON.stringify(req)));
    const pot = inp.n * inp.instalment, month = a.month + 1;
    const wait = a.p_win < 0.05;
    out.innerHTML = `
      <p class="verdict">${wait ? "Wait this month" : `Bid up to ${pct(a.limit)} of the pot`}</p>
      <p class="verdict-sub">${wait
        ? `Your limit is ${pct(a.limit)}, but others are likely to outbid you in month ${month}. Waiting costs you little.`
        : `In month ${month}, give up at most ${rupees(a.limit_amount)} of the ${rupees(pot)} pot.`}</p>
      <dl class="figures">
        <div><dt>Chance you win this month</dt><dd>${pct(a.p_win, 0)}</dd></div>
        <div><dt>Likely winning bid if you do</dt><dd>${a.expected_price == null ? "n/a" : pct(a.expected_price)}</dd></div>
        <div><dt>Members still waiting</dt><dd>${inp.n - a.month}</dd></div>
      </dl>
      <h3>How many waiting members probably need cash now</h3>
      <div class="chart" id="belief-chart"></div>
      <p class="caveat">Inferred from the bids so far, assuming members need cash in about ${pct(mk.p_need, 2)} of months and outside loans cost ${pct(mk.r_borrow)} a month, as fitted to real chits. A guide, not financial advice.</p>`;
    let last = a.belief.length - 1, tail = 0;
    while (last > 3 && tail + a.belief[last] < 0.005) { tail += a.belief[last]; last--; }
    const vals = a.belief.slice(0, last + 1);
    Charts.barChart(document.getElementById("belief-chart"), {
      label: "Probability of each number of members in need",
      labels: vals.map((_, i) => i), values: vals, color: css("--s-yield"),
      xLabel: "Members in need", yFormat: (v, exact) => (100 * v).toFixed(exact ? 1 : 0) + "%",
      tipTitle: k => `${k} in need`,
    });
  }

  // ---------- start ----------
  async function start() {
    const get = p => fetch(p).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
    [state.example, state.explore, state.tables] = await Promise.all([
      get("data/example.json"), get("data/explore.json"), get("data/tables.json")]);
    buildRing();
    if (window.ChitGame) window.ChitGame.init();
    buildExplorer();
    document.getElementById("advice-form").addEventListener("submit", advise);
    let resizeTimer;
    window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { drawRates(); drawCap(); }, 150); });
    loadModel();
  }
  start();
})();
