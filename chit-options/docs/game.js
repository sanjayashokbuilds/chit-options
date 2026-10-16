// "Play a chit": you against nine rivals who bid the model's equilibrium.
// Everything random (who needs cash when, lottery draws) is drawn up front from
// a seed, so at the end the same chit can be replayed with the model's own rule
// in your seat and the two results compared fairly.
(function () {
  const STEP = 0.005;
  const NS = "http://www.w3.org/2000/svg";
  const NAMES = ["Organiser", "Priya", "Arjun", "You", "Meena", "Karthik", "Divya", "Ravi", "Lakshmi", "Suresh"];
  const YOU = 3;
  const EVENTS = [
    "Your scooter has broken down and the repair can't wait.",
    "School fees are due next week.",
    "A cousin's wedding is coming up and you're expected to help.",
    "A hospital bill has arrived.",
    "Your landlord wants a bigger deposit.",
    "A supplier wants paying up front for your shop.",
  ];
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pct = (v, d = 1) => (100 * v).toFixed(d) + "%";
  const rupees = v => (v < -0.5 ? "−" : "") + "₹" + Math.round(Math.abs(v)).toLocaleString("en-IN");

  let G = null;     // game settings and the equilibrium table
  let S = null;     // the current game
  let timer = null;
  const ui = {};

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------- the chit engine (shared by your game and the model's replay) ----------
  function freshState(seed) {
    const N = G.members, rnd = mulberry32(seed);
    const grid = () => Array.from({ length: N }, () => Array.from({ length: N }, () => rnd()));
    return {
      seed, uNeed: grid(), uLot: Array.from({ length: N }, () => rnd()),
      events: Array.from({ length: N }, () => Math.floor(rnd() * EVENTS.length)),
      won: Array(N).fill(false), need: Array(N).fill(false), history: [], t: -1,
    };
  }
  function cloneDraws(st) {
    return { seed: st.seed, uNeed: st.uNeed, uLot: st.uLot, events: st.events,
             won: Array(G.members).fill(false), need: Array(G.members).fill(false), history: [], t: -1 };
  }
  const waiting = st => st.won.map((w, i) => (w ? -1 : i)).filter(i => i >= 0);

  function updateNeeds(st, t) {
    const fresh = [];
    for (const i of waiting(st)) {
      if (!st.need[i] && st.uNeed[i][t] < G.p_need) { st.need[i] = true; fresh.push(i); }
    }
    return fresh;
  }
  // k = how many OTHER waiting members are in need (the model's state)
  function othersInNeed(st, i) { return waiting(st).filter(j => j !== i && st.need[j]).length; }
  function modelLimit(st, t, i) {
    const v = G.table[t][st.need[i] ? 1 : 0][othersInNeed(st, i)];
    return Math.min(G.cap, Math.max(G.commission, v));
  }

  // English auction: highest limit wins, pays the second-highest; ties drawn by lot
  function resolve(bids, u) {
    const sorted = [...bids].sort((a, b) => b.will - a.will);
    const top = sorted[0].will;
    const tied = sorted.filter(b => b.will >= top - 1e-9);
    let winner, price;
    if (bids.length === 1) { winner = bids[0].i; price = G.commission; }
    else if (tied.length >= 2) { winner = tied[Math.floor(u * tied.length)].i; price = top; }
    else { winner = sorted[0].i; price = sorted[1].will; }
    return { winner, price: Math.min(G.cap, Math.max(G.commission, price)) };
  }

  function settle(st, t, winner, price) {
    const N = G.members, pot = N * G.instalment;
    let payout, payment, commission;
    if (t === 0) { payout = pot; payment = G.instalment; commission = 0; price = 0; }
    else {
      commission = G.commission * pot;
      payout = pot * (1 - price);
      payment = G.instalment - (price * pot - commission) / N;
    }
    st.won[winner] = true;
    st.need[winner] = false;
    st.history.push({ t, winner, price, payout, payment, commission,
                      youFlow: -payment + (winner === YOU ? payout : 0), youNeedAfter: st.need[YOU] });
  }

  function replay(st0, policy) {
    const st = cloneDraws(st0), N = G.members;
    for (let t = 0; t < N; t++) {
      updateNeeds(st, t);
      if (t === 0) { settle(st, 0, 0, 0); continue; }
      const bids = waiting(st).map(i => ({ i, will: i === YOU ? policy(st, t) : modelLimit(st, t, i) }));
      const r = resolve(bids, st.uLot[t]);
      settle(st, t, r.winner, r.price);
    }
    return st;
  }

  // Present value today of your cash flows, valuing money at the borrowing rate
  // while you need cash and at the saving rate otherwise (as in the model).
  function presentValue(st) {
    let pv = 0, df = 1;
    for (const h of st.history) {
      pv += h.youFlow * df;
      df /= 1 + (h.youNeedAfter ? G.r_borrow : G.r_save);
    }
    return pv;
  }

  // ---------- drawing ----------
  function buildBoard() {
    const svg = ui.ring, N = G.members, cx = 220, cy = 220, R = 168;
    const add = (name, attrs, parent = svg) => {
      const n = document.createElementNS(NS, name);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
      parent.appendChild(n); return n;
    };
    ui.flow = add("line", { class: "flow", x1: cx, y1: cy, x2: cx, y2: cy, opacity: 0 });
    ui.seats = [];
    for (let i = 0; i < N; i++) {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / N;
      const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
      const g = add("g", { class: "seat" });
      const halo = add("circle", { cx: x, cy: y, r: 34, fill: "none", stroke: "#ffffff", "stroke-width": 2, "stroke-dasharray": "4 5", opacity: i === YOU ? 0.9 : 0 }, g);
      const c = add("circle", { cx: x, cy: y, r: 28 }, g);
      const label = add("text", { class: "seat-num", x, y }, g);
      label.textContent = i === 0 ? "Org." : NAMES[i];
      label.style.fontSize = i === YOU ? "14px" : "11.5px";
      ui.seats.push({ g, c, label, halo, x, y });
    }
    ui.c1 = add("text", { class: "center-a", x: cx, y: cy - 40 });
    ui.c2 = add("text", { class: "center-b", x: cx, y: cy + 14 });
    ui.c3 = add("text", { class: "center-c", x: cx, y: cy + 42 });
  }

  function drawSeats(opts = {}) {
    const { active = null, dropped = new Set(), winner = null } = opts;
    S.won.forEach((w, i) => {
      const s = ui.seats[i];
      let fill = "#20245a", stroke = "#8d92c4", sw = 2, text = "#c9ccf0", op = 1;
      if (w && i !== winner) { fill = "#2c3170"; stroke = "#2c3170"; text = "#7f84b8"; }
      if (!w && S.need[i]) { stroke = "#f2a900"; sw = 4; }
      if (active && active.has(i)) { stroke = S.need[i] ? "#f2a900" : "#ffffff"; sw = S.need[i] ? 4 : 2.5; }
      if (dropped.has(i)) op = 0.32;
      if (i === winner) { fill = "#f2a900"; stroke = "#f2a900"; text = "#1b1f4b"; op = 1; }
      s.c.style.fill = fill; s.c.style.stroke = stroke; s.c.style.strokeWidth = sw;
      s.c.style.opacity = op; s.label.style.fill = text; s.label.style.opacity = op;
    });
    if (winner != null) {
      const w = ui.seats[winner];
      ui.flow.setAttribute("x1", 220 + (w.x - 220) * 0.42); ui.flow.setAttribute("y1", 220 + (w.y - 220) * 0.42);
      ui.flow.setAttribute("x2", 220 + (w.x - 220) * 0.78); ui.flow.setAttribute("y2", 220 + (w.y - 220) * 0.78);
      ui.flow.setAttribute("opacity", 1);
    } else ui.flow.setAttribute("opacity", 0);
  }

  function center(a, b, c) { ui.c1.textContent = a; ui.c2.textContent = b; ui.c3.textContent = c; }
  function ladder(p) {
    ui.fill.style.width = `${(100 * (p - G.commission)) / (G.cap - G.commission)}%`;
  }
  function coachMarker(limit) {
    const on = ui.coach.checked && limit != null;
    ui.coachMark.hidden = !on;
    ui.coachNote.hidden = !on;
    if (on) {
      ui.coachMark.style.left = `${(100 * (limit - G.commission)) / (G.cap - G.commission)}%`;
      const k = othersInNeed(S, YOU);
      ui.coachNote.textContent = `The model would stay in up to ${pct(limit)} here (you ${S.need[YOU] ? "need cash" : "don't need cash"}, ${k === 0 ? "no one else does" : k === 1 ? "1 other member does" : k + " others do"}).`;
    }
  }

  function youCard() {
    const N = G.members, t = Math.max(S.t, 0);
    const cash = S.history.reduce((a, h) => a + h.youFlow, 0);
    const wonAt = S.history.find(h => h.winner === YOU);
    const status = wonAt ? `Had the pot (month ${wonAt.t + 1})` : S.need[YOU] ? "Waiting, needs cash" : "Waiting";
    ui.you.innerHTML = `
      <div><dt>Month</dt><dd>${S.t < 0 ? "–" : `${t + 1} of ${N}`}</dd></div>
      <div><dt>You</dt><dd class="${!wonAt && S.need[YOU] ? "need" : ""}" style="font-size:1rem;line-height:1.3">${status}</dd></div>
      <div><dt>Your cash so far</dt><dd>${rupees(cash)}</dd></div>`;
  }

  function setEvent(html) { ui.event.innerHTML = html; }
  function primary(label, fn) {
    ui.primary.hidden = !label; ui.primary.textContent = label || ""; ui.primary.onclick = fn;
  }

  // ---------- game flow ----------
  function intro() {
    stop();
    S = freshState((Date.now() ^ Math.floor(Math.random() * 1e9)) >>> 0);
    ui.after.hidden = true;
    drawSeats();
    center("10 members", `₹${(G.members * G.instalment).toLocaleString("en-IN")}`, "in the pot each month");
    ladder(G.commission); coachMarker(null);
    youCard();
    setEvent(`<h3>You're in a 10-member chit</h3>
      <p>Everyone pays ₹${G.instalment.toLocaleString("en-IN")} a month. Each month you can bid to take the pot by giving some of it up. Your rivals bid the way the model says is best.</p>
      <p>Money matters more when you need it: every month you need cash but don't have the pot, you're paying ${pct(G.r_borrow)} a month on an outside loan.</p>`);
    primary("Start the chit", () => monthStart(0));
    ui.drop.hidden = true;
  }

  function monthStart(t) {
    stop();
    S.t = t;
    const fresh = updateNeeds(S, t);
    const N = G.members, pot = N * G.instalment;
    youCard(); ladder(G.commission);
    if (t === 0) {
      settle(S, 0, 0, 0);
      drawSeats({ winner: 0 });
      center(`Month 1 of ${N}`, `₹${pot.toLocaleString("en-IN")}`, "to the organiser");
      setEvent(`<h3>Month 1: the organiser's month</h3><p>By custom the organiser takes the first pot, with no auction. Everyone, you included, pays the full ₹${G.instalment.toLocaleString("en-IN")}.</p>`);
      youCard(); coachMarker(null);
      primary("Next month", () => monthStart(1));
      return;
    }
    const ws = waiting(S);
    if (t === N - 1) {
      const last = ws[0];
      settle(S, t, last, G.commission);
      drawSeats({ winner: last });
      const h = S.history[S.history.length - 1];
      center(`Month ${N} of ${N}`, `₹${Math.round(h.payout).toLocaleString("en-IN")}`, `to ${last === YOU ? "you" : NAMES[last]}`);
      setEvent(`<h3>Month ${N}: the last pot</h3><p>Only ${last === YOU ? "you are" : NAMES[last] + " is"} left, so there's no auction: the pot goes ${last === YOU ? "to you" : "to " + NAMES[last]}, less the organiser's commission.</p>`);
      youCard(); coachMarker(null);
      primary("See how you did", finish);
      return;
    }
    drawSeats({ active: new Set(ws) });
    center(`Month ${t + 1} of ${N}`, `₹${pot.toLocaleString("en-IN")}`, `${ws.length} members can bid`);
    const k = othersInNeed(S, YOU);
    let msg = "";
    if (fresh.includes(YOU)) msg += `<p class="alert">${EVENTS[S.events[t]]} You need cash now: until you take a pot, it's costing you ${pct(G.r_borrow)} a month.</p>`;
    else if (!S.won[YOU] && S.need[YOU]) msg += `<p class="alert">You still need cash.</p>`;
    const others = ws.filter(i => i !== YOU && S.need[i]).length;
    msg += `<p>${others === 0 ? "No one else" : others === 1 ? "One other member" : `${others} other members`} ${others === 1 ? "needs" : "need"} cash right now${others ? ", so expect keener bidding" : ""}.</p>`;
    if (S.won[YOU]) msg += `<p>You've had your pot, so you just watch and collect your share of the discount.</p>`;
    setEvent(`<h3>Month ${t + 1}</h3>${msg}`);
    coachMarker(S.won[YOU] ? null : modelLimit(S, t, YOU));
    primary(S.won[YOU] ? "Watch the auction" : "Start bidding", () => auction(t));
  }

  function auction(t) {
    const ws = waiting(S);
    const youIn = ws.includes(YOU);
    const limits = new Map(ws.filter(i => i !== YOU).map(i => [i, modelLimit(S, t, i)]));
    const coachLim = youIn ? modelLimit(S, t, YOU) : null;
    const active = new Set(ws), dropped = new Set();
    let p = G.commission, youDrop = null;
    const pot = G.members * G.instalment;
    primary(null);
    ui.drop.hidden = !youIn;
    ui.drop.disabled = false;
    ui.drop.onclick = () => { youDrop = p; ui.drop.disabled = true; };

    const show = () => {
      ladder(p);
      center(`Month ${t + 1}: bidding`, pct(p), `give up ${"₹" + Math.round(p * pot).toLocaleString("en-IN")}`);
      drawSeats({ active, dropped });
      const still = [...active].map(i => (i === YOU ? "you" : NAMES[i])).join(", ");
      setEvent(`<h3>Bidding at ${pct(p)}</h3><p>Still in: ${still}.</p>${youIn && youDrop == null ? `<p>Stay in to keep bidding. Drop out when ${pct(p)} of the pot is more than it's worth to you.</p>` : ""}`);
      coachMarker(coachLim);
    };
    const finishAuction = () => {
      stop();
      const bids = ws.map(i => ({ i, will: i === YOU ? (youDrop == null ? G.cap : youDrop - 1e-6) : limits.get(i) }));
      const r = resolve(bids, S.uLot[t]);
      settle(S, t, r.winner, r.price);
      result(t, r);
    };
    show();
    const speed = youIn && youDrop == null ? (reduced ? 450 : 320) : 70;
    const tick = () => {
      if (youDrop != null && active.has(YOU)) { active.delete(YOU); dropped.add(YOU); ui.drop.hidden = true; }
      if (active.size <= 1 || p >= G.cap - 1e-9) return finishAuction();
      const next = Math.min(G.cap, p + STEP);
      // rivals leave once the price passes their limit; if everyone left would
      // leave at once they are tied, and resolve() settles it by lot
      const leaving = [...active].filter(i => i !== YOU && limits.get(i) < next - 1e-9);
      if (leaving.length === active.size) return finishAuction();
      leaving.forEach(i => { active.delete(i); dropped.add(i); });
      p = next;
      show();
      const fast = !active.has(YOU);
      timer = setTimeout(tick, fast ? 70 : speed);
    };
    timer = setTimeout(tick, speed);
  }

  function result(t, r) {
    ui.drop.hidden = true;
    const h = S.history[S.history.length - 1];
    const N = G.members, pot = N * G.instalment;
    drawSeats({ winner: r.winner });
    ladder(r.price);
    youCard(); coachMarker(null);
    const who = r.winner === YOU ? "You" : NAMES[r.winner];
    center(`Month ${t + 1}`, rupees(h.payout), `to ${r.winner === YOU ? "you" : NAMES[r.winner]}`);
    const shared = r.price * pot - h.commission;
    let body = `<h3>${who} ${r.winner === YOU ? "take" : "takes"} the pot</h3>
      <p>${r.winner === YOU ? "You gave" : who + " gave"} up ${pct(r.price)} (${rupees(r.price * pot)}) and ${r.winner === YOU ? "take" : "takes"} ${rupees(h.payout)}. After the organiser's ${rupees(h.commission)}, ${rupees(shared)} is shared out, so everyone pays ${rupees(h.payment)} this month instead of ${rupees(G.instalment)}.</p>`;
    if (r.winner === YOU) body += `<p class="alert">You can't bid again, but you keep paying each month.</p>`;
    setEvent(body);
    primary(t + 1 < N ? "Next month" : "See how you did", () => monthStart(t + 1));
  }

  function finish() {
    stop();
    const N = G.members, pot = N * G.instalment;
    const you = presentValue(S);
    const model = replay(S, (st, t) => modelLimit(st, t, YOU));
    const mv = presentValue(model);
    const myWin = S.history.find(h => h.winner === YOU);
    const modelWin = model.history.find(h => h.winner === YOU);
    const diff = you - mv;
    let rateLine;
    if (myWin.t < N - 1) {
      const y = Math.pow((1 - G.commission) / (1 - myWin.price), 1 / (N - 1 - myWin.t)) - 1;
      rateLine = `You took the pot in month ${myWin.t + 1} at ${pct(myWin.price)}: like borrowing at about ${pct(Math.pow(1 + y, 12) - 1, 0)} a year until the end.`;
    } else {
      rateLine = `You took the last pot: you were saving, and the shared-out discounts were your return.`;
    }
    const verdict = Math.abs(diff) < 1 ? "You matched the model." :
      diff > 0 ? `You beat the model by ${rupees(diff)}.` : `The model did ${rupees(-diff)} better.`;
    const modelLine = modelWin.t === myWin.t ? `The model would also have taken the pot in month ${modelWin.t + 1}.` :
      `The model would have taken the pot in month ${modelWin.t + 1}${modelWin.t < N - 1 ? ` at ${pct(modelWin.price)}` : ""}.`;
    ui.after.hidden = false;
    ui.after.innerHTML = `
      <div class="score">
        <h3>${verdict}</h3>
        <p>${rateLine} ${modelLine}</p>
        <dl class="vs">
          <div><dt>Your seat, in today's money</dt><dd>${rupees(you)}</dd></div>
          <div><dt>The model's play, same chit</dt><dd>${rupees(mv)}</dd></div>
        </dl>
        <p>"Today's money" counts each rupee by when it arrived: while you needed cash, money arriving later was worth ${pct(G.r_borrow)} a month less. Chits usually cost a little overall because the organiser takes a commission.</p>
        <button class="btn btn-gold" type="button" id="play-again">Play again</button>
      </div>
      <div>
        <table class="ledger">
          <caption>Your month-by-month cash</caption>
          <thead><tr><th scope="col">Month</th><th scope="col">Pot went to</th><th scope="col">Winning bid</th><th scope="col">Your cash</th></tr></thead>
          <tbody>${S.history.map(h => `<tr class="${h.winner === YOU ? "you-won" : ""}"><td>${h.t + 1}</td><td>${h.winner === YOU ? "You" : h.winner === 0 ? "Organiser" : NAMES[h.winner]}</td><td>${h.t === 0 ? "–" : pct(h.price)}</td><td>${rupees(h.youFlow)}</td></tr>`).join("")}</tbody>
        </table>
      </div>`;
    document.getElementById("play-again").onclick = () => { intro(); ui.ring.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "center" }); };
    setEvent(`<h3>The chit is over</h3><p>${verdict} Scroll down for the breakdown.</p>`);
    primary("Play again", intro);
    ui.after.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "nearest" });
  }

  function stop() { clearTimeout(timer); timer = null; }

  async function init() {
    G = await fetch("data/game.json").then(r => r.json());
    Object.assign(ui, {
      ring: document.getElementById("game-ring"), fill: document.getElementById("ladder-fill"),
      coachMark: document.getElementById("ladder-coach"), coachNote: document.getElementById("coach-note"),
      coach: document.getElementById("game-coach"), you: document.getElementById("you-card"),
      event: document.getElementById("game-event"), primary: document.getElementById("game-primary"),
      drop: document.getElementById("game-drop"), after: document.getElementById("game-after"),
    });
    buildBoard();
    ui.coach.addEventListener("change", () => {
      if (S && S.t > 0 && !S.won[YOU] && S.t < G.members - 1) coachMarker(modelLimit(S, S.t, YOU));
      else coachMarker(null);
    });
    intro();
  }
  // _engine is used by the tests (tests/game_engine_check.js) to compare with the Python model
  window.ChitGame = { init, _engine: { setGame: g => (G = g), freshState, replay, resolve, presentValue, modelLimit } };
})();
