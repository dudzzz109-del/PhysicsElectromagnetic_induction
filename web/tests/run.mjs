// Headless checks (no browser needed):  node --import ./web/tests/register.mjs web/tests/run.mjs
import assert from 'node:assert/strict';

// --- minimal DOM stubs so Three.js CanvasTexture / our canvas code can run in Node ---
const ctxStub = new Proxy(function () {}, { get: () => ctxStub, apply: () => ctxStub, set: () => true });
const fakeCanvas = () => ({ width: 0, height: 0, clientWidth: 400, clientHeight: 140, getContext: () => ctxStub });
globalThis.document = { createElement: () => fakeCanvas() };
globalThis.window = { devicePixelRatio: 1 };

const { Simulation, DT } = await import('../sim.js');
const { LiveGraphs, WINDOW } = await import('../graphs.js');
const { createApparatus } = await import('../scene.js');

let pass = 0;
const ok = (name, cond, extra = '') => { assert.ok(cond, name + ' ' + extra); pass++; console.log('  ok  ' + name + (extra ? '  (' + extra + ')' : '')); };

function run(sim, seconds) {
  const rows = [];
  sim.running = true;
  for (let i = 0; i < Math.round(seconds / DT); i++) { sim.step(); rows.push({ x: sim.magX, B: sim.B, flux: sim.flux, emf: sim.emf, curr: sim.curr, st: sim.state, needle: sim.needle }); }
  return rows;
}
const peak = (rows, k) => Math.max(...rows.map((r) => Math.abs(r[k])));

// ---- PASS-THROUGH ----
{
  const sim = new Simulation();
  const rows = run(sim, 11);
  const xmin = Math.min(...rows.map((r) => r.x));
  ok('pass-through: magnet leaves the coil completely on the far side', xmin + 0.48 < -1.85, `S end at ${(xmin + 0.48).toFixed(2)} < coil end -1.85`);
  ok('pass-through: peak EMF ~0.40 V', Math.abs(peak(rows, 'emf') - 0.40) < 0.03, peak(rows, 'emf').toFixed(3) + ' V');
  ok('pass-through: flux changes sign', Math.min(...rows.map((r) => r.flux)) < -0.001 && Math.max(...rows.map((r) => r.flux)) > 0.0008);
  // EMF sign sequence while going through (first leg)
  const imin = rows.findIndex((r) => r.x === Math.min(...rows.map((q) => q.x)));
  const seq = [];
  for (const r of rows.slice(0, imin)) { const s = Math.abs(r.emf) > 0.03 ? Math.sign(r.emf) : 0; if (s && seq[seq.length - 1] !== s) seq.push(s); }
  ok('pass-through: needle sequence LEFT, RIGHT, LEFT', seq[0] === -1 && seq[1] === 1 && seq[2] === -1, JSON.stringify(seq));
}

// ---- BOUNCE (original calibration) ----
{
  const sim = new Simulation(); sim.setMode(false);
  const rows = run(sim, 6);
  ok('bounce: peak EMF ~0.40 V (original calibration)', Math.abs(peak(rows, 'emf') - 0.399) < 0.02, peak(rows, 'emf').toFixed(3) + ' V');
  ok('bounce: |B| max ~0.37 T', Math.abs(peak(rows, 'B') - 0.374) < 0.02, peak(rows, 'B').toFixed(3) + ' T');
  const s2 = new Simulation(); s2.setMode(false); s2.setSpeed(2); const r2 = run(s2, 6);
  ok('bounce: 2x speed doubles EMF', Math.abs(peak(r2, 'emf') / peak(rows, 'emf') - 2) < 0.1, (peak(r2, 'emf') / peak(rows, 'emf')).toFixed(2));
  const s3 = new Simulation(); s3.setMode(false); s3.setTurns(40); const r3 = run(s3, 6);
  ok('bounce: N=40 doubles EMF', Math.abs(peak(r3, 'emf') / peak(rows, 'emf') - 2) < 0.1);
}

// ---- REVERSE ----
{
  const sim = new Simulation(); run(sim, 3);
  const x0 = sim.magX, v0 = sim.magVel; sim.reverse(); sim.step();
  ok('reverse: position continuous, velocity flips', Math.abs(sim.magX - x0) < 0.03 && Math.sign(sim.magVel) === -Math.sign(v0));
}

// ---- graphs: sweep, wrap, reset ----
{
  const g = new LiveGraphs(fakeCanvas(), fakeCanvas(), fakeCanvas());
  const sim = new Simulation({ graphs: g });
  run(sim, 11);
  const n1 = g.graphs.emf.ts.length;
  ok('graphs: samples collected in sweep 0', n1 > 150 && g.graphs.emf.scale >= 0.5, `${n1} pts, scale ±${g.graphs.emf.scale}`);
  run(sim, 3);
  ok('graphs: sweep wraps after ' + WINDOW + ' s', g.graphs.emf.sweep === 1 && g.graphs.emf.ts.length < n1);
  g.draw();
  sim.reset();
  ok('graphs: RESET clears', g.graphs.emf.ts.length === 0 && g.graphs.emf.sweep === 0);
}

// ---- 3D apparatus builds and updates ----
{
  const app = createApparatus();
  app.setTurns(5); app.setTurns(60);
  for (const [x, d, i, l] of [[1.85, 0, 0, 0], [-0.3, -30, -0.2, 0.9], [-2.9, 40, 0.15, 0.3], [0, 60, 0, 1]]) app.update({ magX: x, needleDeg: d, current: i, lampLevel: l });
  ok('apparatus: builds and updates', app.scene.children.length > 10, app.scene.children.length + ' scene objects');
}

console.log(`\n${pass} checks passed`);
