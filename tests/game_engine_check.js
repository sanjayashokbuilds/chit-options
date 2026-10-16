// Checks the browser game's chit engine against the Python model:
// average winning discount by month when every seat follows the equilibrium.
// Run: node tests/game_engine_check.js   (prints JSON; test_web.py compares it)
const fs = require("fs");
const path = require("path");
global.window = { matchMedia: () => ({ matches: true }) };
eval(fs.readFileSync(path.join(__dirname, "../docs/game.js"), "utf8"));
const G = JSON.parse(fs.readFileSync(path.join(__dirname, "../docs/data/game.json"), "utf8"));
const E = window.ChitGame._engine;
E.setGame(G);
const N = G.members, sims = +(process.argv[2] || 20000);
const sum = Array(N).fill(0), sq = Array(N).fill(0);
for (let s = 0; s < sims; s++) {
  const st = E.freshState(1000 + s);
  const out = E.replay(st, (st2, t) => E.modelLimit(st2, t, 3));
  out.history.forEach(h => { sum[h.t] += h.price; sq[h.t] += h.price * h.price; });
}
const mean = sum.map(v => v / sims);
const se = sq.map((v, i) => Math.sqrt(Math.max(v / sims - mean[i] ** 2, 0) / sims));
console.log(JSON.stringify({ mean, se }));
