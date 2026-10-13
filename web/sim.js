// sim.js — simulation state (motion + physics + classification). No DOM, so it is testable in Node.
import { Physics, WORLD_TO_METERS, COIL_X } from './physics.js';

export const DT = 0.012;             // fixed physics step [s]  (same as the Python version)
export const MAG_X_FAR = 1.85;       // start position (right of the coil)
export const MAG_X_NEAR = -0.65;     // BOUNCE: turnaround point (N end inside the coil)
export const MAG_X_PASS_END = -2.95; // PASS-THROUGH: far end (magnet completely out of the left side)
export const BOUNCE_OMEGA = 1.15;    // rad/s
export const PASS_OMEGA = 0.60;      // rad/s   (same ~0.29 m/s peak speed in both modes)
export const LAMP_P_REF = 0.06;      // W that gives full brightness

const BANNERS_PASS = {
  READY:      ['READY \u2014 press PLAY: the magnet will pass THROUGH the coil', ''],
  APPROACH:   ['FLUX INCREASING \u2192 EMF negative \u2192 needle LEFT', "Lenz's Law: the induced current opposes the change in flux"],
  TURNAROUND: ['FLUX STEADY \u2192 EMF = 0 (magnet body is inside the coil)', 'Strong field, but it is not CHANGING, so there is no induced EMF'],
  RETREAT:    ['FLUX DECREASING \u2192 EMF positive \u2192 needle RIGHT', 'The current REVERSES \u2014 includes the N pole crossing the coil, where B through the coil flips direction'],
  REST:       ['MAGNET FAR AWAY \u2192 field at the coil is tiny \u2192 EMF \u2248 0', 'No (or very little) change in flux = no (or very little) induced current'],
};
const BANNERS_BOUNCE = {
  READY:      ['READY \u2014 press PLAY', 'The magnet swings toward the coil and back'],
  APPROACH:   ['MAGNET APPROACHING \u2192 flux increasing \u2192 EMF negative \u2192 needle LEFT', "Lenz's Law: the coil opposes the increase in flux (it repels the N pole)"],
  TURNAROUND: ['MAGNET AT ITS CLOSEST POINT \u2192 flux at maximum but not changing \u2192 EMF = 0', 'Strong field, zero rate of change: no induced current'],
  RETREAT:    ['MAGNET MOVING AWAY \u2192 flux decreasing \u2192 EMF positive \u2192 needle RIGHT', 'Lenz: the coil now tries to keep the flux from falling (it attracts the N pole)'],
  REST:       ['MAGNET FAR AWAY \u2192 field at the coil is tiny \u2192 EMF \u2248 0', 'No (or very little) change in flux = no (or very little) induced current'],
};

export class Simulation {
  constructor({ graphs = null, turns = 20 } = {}) {
    this.physics = new Physics({ turns });
    this.graphs = graphs;
    this.speed = 1.0;
    this.running = false;
    this.setMode(true);            // default: PASS THROUGH
  }

  // ---- mode / reset -------------------------------------------------------
  setMode(passThrough) {
    this.passThrough = !!passThrough;
    this.physics.passThrough = this.passThrough;
    const end = this.passThrough ? MAG_X_PASS_END : MAG_X_NEAR;
    this.amp = (MAG_X_FAR - end) / 2;
    this.mid = (MAG_X_FAR + end) / 2;
    this.omega = this.passThrough ? PASS_OMEGA : BOUNCE_OMEGA;
    this.reset();
  }

  reset() {
    this.running = false;
    this.phase = 0;            // x = mid + amp*cos(phase); phase is accumulated so REVERSE works
    this.dir = 1;
    this.realTime = 0;
    this.magX = MAG_X_FAR;
    this.magVel = 0;           // m/s
    this.B = 0; this.flux = 0; this.dphi = 0; this.emf = 0; this.curr = 0;
    this.needle = 0; this.lamp = 0; this.lampPower = 0;
    this.state = 'READY';
    this.physics.reset();
    if (this.graphs) this.graphs.clear();
  }

  reverse() { this.dir = -this.dir; }
  setSpeed(v) { this.speed = v; }
  setTurns(n) { this.physics.turns = Math.round(n); }
  setStrength(s) { this.physics.strength = s; }

  // ---- one fixed physics step ----------------------------------------------
  step() {
    if (!this.running) return;
    const p = this.physics;
    this.realTime += DT;
    this.phase += this.omega * DT * this.speed * this.dir;
    this.magX = this.mid + this.amp * Math.cos(this.phase);
    this.magVel = -this.amp * this.omega * this.dir * Math.sin(this.phase) * this.speed * WORLD_TO_METERS;

    this.B = p.computeB(this.magX, COIL_X);
    this.flux = p.computeFlux(this.B);
    [this.emf, this.dphi] = p.computeEmf(this.flux, this.realTime);
    this.curr = p.computeCurrent(this.emf);
    this.needle += (p.needleDeg(this.curr) - this.needle) * 0.35;

    this.lampPower = this.curr * this.curr * p.resistance;             // P = I^2 R
    const target = Math.min(1, this.lampPower / LAMP_P_REF);
    this.lamp = Math.max(target, this.lamp * 0.93);                    // filament inertia

    this.state = this.classify();
    if (this.graphs) this.graphs.push(this.realTime, this.flux, this.emf, this.curr);
  }

  classify() {
    if (this.realTime === 0) return 'READY';
    const thr = 0.002;                                    // |dPhi/dt| below this counts as "steady"
    const strong = this.passThrough ? 0.02 : 0.15;        // tesla
    if (Math.abs(this.dphi) < thr) return Math.abs(this.B) > strong ? 'TURNAROUND' : 'REST';
    return this.dphi > 0 ? 'APPROACH' : 'RETREAT';
  }

  banner() { return (this.passThrough ? BANNERS_PASS : BANNERS_BOUNCE)[this.state]; }
}
