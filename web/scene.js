// scene.js — builds the 3D apparatus with Three.js and updates it every frame.
// No renderer here (so it can be unit-tested in Node): app.js owns the WebGL renderer.
import * as THREE from 'three';
import { COIL_X } from './physics.js';

export { COIL_X };               // coil centre (scene units); the coil axis is the x axis
export const COIL_LEN = 1.10;
export const COIL_R = 0.48;
export const MAG_POLE_LEN = 0.48;   // each pole block; the whole magnet is 0.96 long
export const MAG_H = 0.22;

// ---------- small helpers --------------------------------------------------
function makeCanvas(w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

function labelSprite(text, { color = '#e2e8f0', border = null, width = 1.6, font = 34 } = {}) {
  const c = makeCanvas(512, 96);
  const g = c.getContext('2d');
  g.fillStyle = 'rgba(8,13,26,0.82)'; g.fillRect(2, 2, 508, 92);
  if (border) { g.strokeStyle = border; g.lineWidth = 4; g.strokeRect(4, 4, 504, 88); }
  g.fillStyle = color; g.font = `600 ${font}px system-ui, sans-serif`;
  g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillText(text, 256, 50);
  const tex = new THREE.CanvasTexture(c);
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false }));
  sp.scale.set(width, width * 96 / 512, 1);
  sp.renderOrder = 10;
  return sp;
}

function wire(points, color = 0x38bdf8, radius = 0.018) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)), false, 'catmullrom', 0.02);
  return new THREE.Mesh(
    new THREE.TubeGeometry(curve, points.length * 12, radius, 8, false),
    new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.1 }),
  );
}

function dialTexture() {
  const W = 440, H = 240;
  const c = makeCanvas(W, H);
  const g = c.getContext('2d');
  g.fillStyle = '#f8fafc'; g.fillRect(0, 0, W, H);
  const cx = 220, cy = 200, R = 165;
  g.strokeStyle = '#111827'; g.fillStyle = '#111827';
  g.lineWidth = 3;
  g.beginPath(); g.arc(cx, cy, R, (-90 - 50) * Math.PI / 180, (-90 + 50) * Math.PI / 180); g.stroke();
  for (let d = -50; d <= 50; d += 10) {
    const a = (d - 90) * Math.PI / 180;
    const len = d % 50 === 0 || d === 0 ? 24 : 14;
    g.lineWidth = d === 0 ? 4 : 2;
    g.beginPath();
    g.moveTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
    g.lineTo(cx + Math.cos(a) * (R - len), cy + Math.sin(a) * (R - len));
    g.stroke();
  }
  g.font = '700 34px system-ui, sans-serif'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.fillStyle = '#b91c1c'; g.fillText('\u2212', 60, 70);
  g.fillStyle = '#15803d'; g.fillText('+', W - 60, 70);
  g.fillStyle = '#111827'; g.fillText('0', cx, 58);
  g.font = '700 28px system-ui, sans-serif'; g.fillText('G', cx, 150);
  return new THREE.CanvasTexture(c);
}

// ---------- the apparatus --------------------------------------------------
export function createApparatus() {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b1020);

  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 1.1);
  sun.position.set(2, 4, 6);
  scene.add(sun);

  // ----- coil ---------------------------------------------------------------
  const coil = new THREE.Group();
  coil.position.set(COIL_X, 0, 0);
  scene.add(coil);

  const copper = new THREE.MeshStandardMaterial({ color: 0xe0902f, roughness: 0.35, metalness: 0.35 });
  const ringGeo = new THREE.TorusGeometry(COIL_R, 0.03, 12, 48);
  ringGeo.rotateY(Math.PI / 2);                         // ring plane perpendicular to the x axis
  const rings = new THREE.Group();
  coil.add(rings);

  const bobbin = new THREE.Mesh(
    new THREE.CylinderGeometry(COIL_R - 0.03, COIL_R - 0.03, COIL_LEN, 32, 1, true),
    new THREE.MeshStandardMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.10, side: THREE.DoubleSide }),
  );
  bobbin.rotation.z = Math.PI / 2;
  coil.add(bobbin);

  function setTurns(n) {
    while (rings.children.length) rings.remove(rings.children[0]);
    const k = Math.max(1, Math.min(36, Math.round(n)));   // draw at most 36 rings
    for (let i = 0; i < k; i++) {
      const m = new THREE.Mesh(ringGeo, copper);
      m.position.x = k === 1 ? 0 : -COIL_LEN / 2 + (COIL_LEN * i) / (k - 1);
      rings.add(m);
    }
  }
  setTurns(20);

  const coilLabel = labelSprite('CONDUCTING COIL', { color: '#fbbf24', border: '#b45309', width: 1.7, font: 32 });
  coilLabel.position.set(COIL_X, 0.95, 0);
  scene.add(coilLabel);

  // ----- Lenz arrows (direction of the induced current) --------------------
  const arrows = new THREE.Group();
  arrows.position.set(COIL_X, 0, 0);
  scene.add(arrows);
  const arrowMat = new THREE.MeshStandardMaterial({ color: 0xf0abfc, emissive: 0x6b21a8, emissiveIntensity: 0.6 });
  const arrowMeshes = [];
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * 2 * Math.PI;
    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.18, 12), arrowMat);
    cone.position.set(0, 0.64 * Math.sin(a), 0.64 * Math.cos(a));
    cone.userData.angle = a;
    arrows.add(cone);
    arrowMeshes.push(cone);
  }
  arrows.visible = false;
  const up = new THREE.Vector3(0, 1, 0);

  // ----- bar magnet -----------------------------------------------------------
  const magnet = new THREE.Group();
  scene.add(magnet);
  const north = new THREE.Mesh(new THREE.BoxGeometry(MAG_POLE_LEN, MAG_H, MAG_H),
    new THREE.MeshStandardMaterial({ color: 0xe11d2e, roughness: 0.45 }));
  north.position.x = -MAG_POLE_LEN / 2;
  const south = new THREE.Mesh(new THREE.BoxGeometry(MAG_POLE_LEN, MAG_H, MAG_H),
    new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.45 }));
  south.position.x = MAG_POLE_LEN / 2;
  magnet.add(north, south);
  const nTag = labelSprite('N', { color: '#fff', width: 0.22, font: 60 });
  nTag.position.set(-MAG_POLE_LEN / 2, 0, MAG_H / 2 + 0.02);
  const sTag = labelSprite('S', { color: '#fff', width: 0.22, font: 60 });
  sTag.position.set(MAG_POLE_LEN / 2, 0, MAG_H / 2 + 0.02);
  magnet.add(nTag, sTag);

  // a few field-line loops that travel with the magnet
  const loops = new THREE.Group();
  for (let k = 0; k < 3; k++) {
    const e = new THREE.EllipseCurve(0, 0, 0.78 + 0.32 * k, 0.30 + 0.28 * k, 0, 2 * Math.PI);
    const geo = new THREE.BufferGeometry().setFromPoints(e.getPoints(80).map((p) => new THREE.Vector3(p.x, p.y, 0)));
    const line = new THREE.LineLoop(geo, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.45 }));
    const line2 = line.clone();
    line2.rotation.x = Math.PI / 2;
    loops.add(line, line2);
  }
  magnet.add(loops);
  const magLabel = labelSprite('BAR MAGNET', { color: '#e2e8f0', border: '#94a3b8', width: 1.3, font: 34 });
  magLabel.position.set(0, 1.12, 0);
  magnet.add(magLabel);

  // ----- galvanometer ---------------------------------------------------------
  const galv = new THREE.Group();
  galv.position.set(-0.20, -1.95, 0);
  scene.add(galv);
  galv.add(new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.9, 0.5),
    new THREE.MeshStandardMaterial({ color: 0x2b3547, roughness: 0.6 })));
  const dial = new THREE.Mesh(new THREE.PlaneGeometry(1.1, 0.6), new THREE.MeshBasicMaterial({ map: dialTexture() }));
  dial.position.set(0, 0.08, 0.26);
  galv.add(dial);
  const pivot = new THREE.Group();
  pivot.position.set(0, 0.08 - 0.2, 0.28);               // matches the dial's arc centre
  galv.add(pivot);
  const needle = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.42, 0.01),
    new THREE.MeshBasicMaterial({ color: 0xdc2626 }));
  needle.position.y = 0.21;
  pivot.add(needle);
  const termL = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 12), new THREE.MeshStandardMaterial({ color: 0xdc2626 }));
  termL.position.set(-0.35, -0.25, 0.27);
  const termR = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 12), new THREE.MeshStandardMaterial({ color: 0x111827 }));
  termR.position.set(0.35, -0.25, 0.27);
  galv.add(termL, termR);
  const galvLabel = labelSprite('GALVANOMETER', { color: '#e2e8f0', border: '#94a3b8', width: 1.3, font: 34 });
  galvLabel.position.set(-0.20, -2.62, 0.2);
  scene.add(galvLabel);

  // ----- lamp -----------------------------------------------------------------
  const lamp = new THREE.Group();
  lamp.position.set(1.40, -1.70, 0);
  scene.add(lamp);
  const glassMat = new THREE.MeshStandardMaterial({
    color: 0xcfe8ff, transparent: true, opacity: 0.30, roughness: 0.15,
    emissive: 0xffc94a, emissiveIntensity: 0,
  });
  const glass = new THREE.Mesh(new THREE.SphereGeometry(0.30, 24, 24), glassMat);
  glass.position.y = 0.30;
  const lampBase = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.15, 0.26, 16),
    new THREE.MeshStandardMaterial({ color: 0x6b7280, metalness: 0.5, roughness: 0.4 }));
  lampBase.position.y = -0.12;
  const filMat = new THREE.MeshBasicMaterial({ color: 0x6b6b6b });
  const filament = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.012, 8, 16), filMat);
  filament.position.y = 0.30;
  lamp.add(glass, lampBase, filament);
  const lampLight = new THREE.PointLight(0xffc94a, 0, 4);
  lampLight.position.set(0, 0.3, 0.2);
  lamp.add(lampLight);
  const lampLabel = labelSprite('LAMP (in series with the coil)', { color: '#fde68a', border: '#b45309', width: 1.9, font: 30 });
  lampLabel.position.set(1.40, -2.62, 0.2);
  scene.add(lampLabel);

  // ----- wires (one series circuit: coil -> galvanometer -> lamp -> coil) -----
  scene.add(wire([[COIL_X - COIL_LEN / 2, -COIL_R, 0], [-1.85, -1.3, 0], [-1.85, -2.2, 0.2], [-0.55, -2.2, 0.27]]));
  scene.add(wire([[0.15, -2.2, 0.27], [0.6, -2.3, 0.2], [1.28, -2.2, 0.1], [1.28, -1.95, 0]]));
  scene.add(wire([[1.52, -1.95, 0], [1.95, -1.95, 0], [1.95, -0.9, 0], [-0.75, -0.9, 0], [-0.75, -COIL_R, 0]]));

  // ----- per-frame update -----------------------------------------------------
  function update({ magX, needleDeg, current, lampLevel }) {
    magnet.position.x = magX;
    pivot.rotation.z = -needleDeg * Math.PI / 180;       // + current -> needle to the RIGHT

    // lamp
    const b = Math.max(0, Math.min(1, lampLevel));
    glassMat.emissiveIntensity = 1.6 * b;
    glassMat.opacity = 0.30 + 0.40 * b;
    filMat.color.setRGB(0.42 + 0.58 * b, 0.42 + 0.50 * b, 0.42 + 0.10 * b);
    lampLight.intensity = 2.5 * b;

    // Lenz arrows: I < 0 (N pole approaching) circulates counterclockwise seen from the right
    const mag = Math.abs(current);
    arrows.visible = mag > 0.005;
    if (arrows.visible) {
      const s = current < 0 ? 1 : -1;
      arrowMat.color.set(current < 0 ? 0xf0abfc : 0x86efac);
      arrowMat.emissive.set(current < 0 ? 0x6b21a8 : 0x166534);
      for (const cone of arrowMeshes) {
        const a = cone.userData.angle;
        const y = Math.sin(a), z = Math.cos(a);
        // positive circulation about +x: direction = x_hat × (0, y, z) = (0, -z, y)
        const dir = new THREE.Vector3(0, -z * s, y * s).normalize();
        cone.quaternion.setFromUnitVectors(up, dir);
      }
    }
  }

  return { scene, update, setTurns };
}
