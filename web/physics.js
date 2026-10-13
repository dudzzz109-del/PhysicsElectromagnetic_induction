// physics.js — Electromagnetic induction physics engine (JavaScript port of physics.py)
// Same constants, same equations, same two motion models:
//   BOUNCE       : |B| at the coil centre from a two-pole magnet (original model)
//   PASS-THROUGH : signed flux through the coil opening (field reverses inside the magnet)
//
// Units: metres, tesla, webers, volts, amperes, degrees.

export const MU_0 = 4.0 * Math.PI * 1e-7;
export const WORLD_TO_METERS = 0.20;        // 1 scene unit = 0.20 m
export const COIL_X = -1.30;                // coil centre on the x axis (scene units)
export const BASE_POLE_STRENGTH = 8500.0;   // A·m  (BOUNCE mode)
export const PASS_POLE_STRENGTH = 5000.0;   // A·m  (PASS-THROUGH mode, peak EMF ~0.40 V at 1x, N=20)

export class Physics {
  constructor({ coilRadiusM = 0.096, turns = 20, resistance = 2.0, strength = 1.0 } = {}) {
    this.coilRadiusM = coilRadiusM;
    this.coilArea = Math.PI * coilRadiusM * coilRadiusM;
    this.turns = turns;
    this.resistance = resistance;
    this.strength = strength;
    this.passThrough = false;
    this.magnetHalfLenM = 0.48 * WORLD_TO_METERS;   // 0.096 m
    this.softeningM = 0.032;
    this.galvSensitivity = 180.0;                   // deg / A
    this._prevFlux = null;
    this._prevTime = null;
  }

  reset() { this._prevFlux = null; this._prevTime = null; }

  /** Axial field seen by the coil [T]. Positions are scene units. */
  computeB(magnetX, coilX) {
    const xm = magnetX * WORLD_TO_METERS;
    const xc = coilX * WORLD_TO_METERS;
    const xN = xm - this.magnetHalfLenM;      // North pole faces the coil
    const xS = xm + this.magnetHalfLenM;
    if (this.passThrough) return this._discAverageField(xc, xN, xS);

    const q = BASE_POLE_STRENGTH * this.strength;
    const coeff = (MU_0 * q) / (4 * Math.PI);
    const R2 = this.softeningM ** 2;
    const dN2 = (xc - xN) ** 2 + R2;
    const dS2 = (xc - xS) ** 2 + R2;
    return Math.abs(coeff * (1 / dN2 - 1 / dS2));
  }

  /** Signed average axial field over the coil opening; normal = -x (approach => positive). */
  _discAverageField(xc, xN, xS) {
    const q = PASS_POLE_STRENGTH * this.strength;
    const coeff = (MU_0 * q) / (4 * Math.PI);
    const r2 = this.coilRadiusM ** 2;
    const R2 = this.softeningM ** 2;
    const poleFlux = (xp) => {
      const d = xc - xp;
      const s2 = d * d + R2;
      const s = Math.sqrt(s2);
      return 2 * Math.PI * d * (1 / s - 1 / Math.sqrt(r2 + s2));
    };
    const fluxPlusX = coeff * (poleFlux(xN) - poleFlux(xS));
    return -fluxPlusX / this.coilArea;
  }

  computeFlux(B) { return B * this.coilArea; }            // cos(0) = 1

  /** Faraday: EMF = -N dPhi/dt (finite difference). Returns [emf, dphi_dt]. */
  computeEmf(flux, t) {
    if (this._prevFlux === null) { this._prevFlux = flux; this._prevTime = t; return [0, 0]; }
    const dt = t - this._prevTime;
    if (Math.abs(dt) < 1e-12) return [0, 0];
    const dphi = (flux - this._prevFlux) / dt;
    this._prevFlux = flux; this._prevTime = t;
    return [-this.turns * dphi, dphi];
  }

  computeCurrent(emf) { return emf / Math.max(this.resistance, 1e-6); }   // Ohm

  needleDeg(current) {
    return Math.max(-50, Math.min(50, current * this.galvSensitivity));
  }

  /** Direction seen from the RIGHT (magnet's starting side). EMF>0 => clockwise. */
  directionText(current) {
    if (Math.abs(current) < 1e-4) return 'None (0 A)';
    return current > 0 ? 'Clockwise (from right)' : 'Counterclockwise (from right)';
  }
}
