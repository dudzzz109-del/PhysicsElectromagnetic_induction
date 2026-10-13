// graphs.js — three live "oscilloscope sweep" graphs (flux, EMF, current), drawn on <canvas>.
// The trace is written left -> right over WINDOW seconds, then clears and starts again.
// All plots use a symmetric vertical scale (so sign reversals are obvious) that grows in
// 1-2-5 steps during a sweep and is re-fitted at the start of the next one.

export const WINDOW = 12.0;   // seconds per sweep (> one pass-through cycle of 10.5 s)

function niceCeil(v) {
  if (v <= 0) return 1;
  const e = Math.floor(Math.log10(v));
  const m = v / 10 ** e;
  for (const s of [1, 2, 5, 10]) if (m <= s * 1.000001) return s * 10 ** e;
  return 10 ** (e + 1);
}
const fmt = (v) => Number(v.toPrecision(2)).toString();

class SweepGraph {
  constructor(canvas, title, color, floor) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.title = title;
    this.color = color;
    this.floor = floor;
    this.clear();
  }

  clear() {
    this.sweep = 0;
    this.ts = [];
    this.vs = [];
    this.scale = this.floor;
    this.peak = 0;
    this.lastValue = 0;
  }

  startSweep(sweep) {
    this.sweep = sweep;
    this.ts = [];
    this.vs = [];
    this.scale = Math.max(this.floor, niceCeil(this.peak * 1.05));
    this.peak = 0;
  }

  /** Called every physics step (cheap); only stores every `stride`-th sample. */
  push(t, v, store) {
    const sweep = Math.floor(t / WINDOW);
    if (sweep !== this.sweep) this.startSweep(sweep);
    const a = Math.abs(v);
    if (a > this.peak) this.peak = a;
    if (a > this.scale) this.scale = niceCeil(a * 1.05);
    this.lastValue = v;
    if (store) { this.ts.push(t - this.sweep * WINDOW); this.vs.push(v); }
  }

  draw() {
    const c = this.canvas, g = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
      c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
    }
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.fillStyle = '#0b1220'; g.fillRect(0, 0, w, h);

    const L = 46, R = 10, T = 22, B = 18;
    const pw = w - L - R, ph = h - T - B, mid = T + ph / 2;

    g.fillStyle = this.color; g.font = '600 12px system-ui, sans-serif';
    g.textAlign = 'left'; g.fillText(this.title, L, 14);

    g.strokeStyle = '#33415c'; g.lineWidth = 1; g.strokeRect(L, T, pw, ph);
    g.strokeStyle = '#6b7a99'; g.beginPath(); g.moveTo(L, mid); g.lineTo(L + pw, mid); g.stroke();

    g.fillStyle = '#cbd5e1'; g.font = '10px system-ui, sans-serif'; g.textAlign = 'right';
    g.fillText('+' + fmt(this.scale), L - 4, T + 8);
    g.fillText('0', L - 4, mid + 3);
    g.fillText('\u2212' + fmt(this.scale), L - 4, T + ph);

    g.textAlign = 'center';
    const t0 = this.sweep * WINDOW;
    g.fillText(String(Math.round(t0)), L, h - 5);
    g.fillText(String(Math.round(t0 + WINDOW / 2)), L + pw / 2, h - 5);
    g.fillText(String(Math.round(t0 + WINDOW)) + ' s', L + pw, h - 5);

    const X = (t) => L + (t / WINDOW) * pw;
    const Y = (v) => mid - Math.max(-1, Math.min(1, v / this.scale)) * (ph / 2) * 0.96;
    if (this.ts.length) {
      g.strokeStyle = this.color; g.lineWidth = 2; g.lineJoin = 'round';
      g.beginPath();
      this.ts.forEach((t, i) => (i ? g.lineTo(X(t), Y(this.vs[i])) : g.moveTo(X(t), Y(this.vs[i]))));
      g.stroke();
      const i = this.ts.length - 1;
      g.fillStyle = '#ffffff';
      g.beginPath(); g.arc(X(this.ts[i]), Y(this.vs[i]), 3.5, 0, 2 * Math.PI); g.fill();
    }
  }
}

export class LiveGraphs {
  constructor(canvasFlux, canvasEmf, canvasCurr, stride = 4) {
    this.stride = stride;
    this.n = 0;
    this.graphs = {
      flux: new SweepGraph(canvasFlux, '1. Magnetic flux  \u03a6 = B\u00b7A   [Wb]', '#38bdf8', 0.0005),
      emf:  new SweepGraph(canvasEmf,  '2. Induced EMF = \u2212N\u00b7d\u03a6/dt   [V]', '#f43f5e', 0.05),
      curr: new SweepGraph(canvasCurr, '3. Induced current  I = EMF / R   [A]', '#4ade80', 0.025),
    };
  }
  clear() { this.n = 0; Object.values(this.graphs).forEach((g) => g.clear()); }
  push(t, flux, emf, curr) {
    this.n++;
    const store = this.n % this.stride === 0;
    this.graphs.flux.push(t, flux, store);
    this.graphs.emf.push(t, emf, store);
    this.graphs.curr.push(t, curr, store);
  }
  draw() { Object.values(this.graphs).forEach((g) => g.draw()); }
}
