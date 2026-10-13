// app.js — wires the page together: WebGL renderer, controls, animation loop, readouts.
import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { createApparatus } from './scene.js';
import { LiveGraphs } from './graphs.js';
import { Simulation, DT } from './sim.js';

const $ = (id) => document.getElementById(id);

// ---------- simulation + graphs + apparatus --------------------------------
const graphs = new LiveGraphs($('gFlux'), $('gEmf'), $('gCurr'));
const sim = new Simulation({ graphs, turns: 20 });
const apparatus = createApparatus();

// ---------- renderer / camera ----------------------------------------------
const stage = $('stage');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
stage.prepend(renderer.domElement);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
const TARGET = new THREE.Vector3(-0.35, -0.65, 0);
const VIEW_DIR = new THREE.Vector3(0, 0.10, 1).normalize();
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.copy(TARGET);

function fitCamera(keepDirection) {
  const w = stage.clientWidth, h = stage.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  // distance so the whole bench (about 6.9 wide x 4.6 tall scene units) is visible
  const t = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
  const dist = Math.max(3.45 / (t * camera.aspect), 2.3 / t) * 1.04;
  const dir = keepDirection ? camera.position.clone().sub(controls.target).normalize() : VIEW_DIR;
  camera.position.copy(controls.target).addScaledVector(dir, dist);
  controls.update();
}
fitCamera(false);
new ResizeObserver(() => fitCamera(true)).observe(stage);
$('btnView').onclick = () => { controls.target.copy(TARGET); fitCamera(false); };

// ---------- buttons & sliders -----------------------------------------------
const modeText = () => (sim.passThrough ? 'MODE: PASS THROUGH (click for bounce)' : 'MODE: BOUNCE (click for pass through)');
$('btnMode').textContent = modeText();

$('btnPlay').onclick = () => { sim.running = true; };
$('btnPause').onclick = () => { sim.running = false; };
$('btnReset').onclick = () => { sim.reset(); };
$('btnReverse').onclick = () => sim.reverse();
$('btnMode').onclick = () => { sim.setMode(!sim.passThrough); $('btnMode').textContent = modeText(); };

$('slSpeed').oninput = (e) => { sim.setSpeed(+e.target.value); $('outSpeed').textContent = (+e.target.value).toFixed(1) + 'x'; };
$('slTurns').oninput = (e) => { sim.setTurns(+e.target.value); apparatus.setTurns(+e.target.value); $('outTurns').textContent = e.target.value; };
$('slStrength').oninput = (e) => { sim.setStrength(+e.target.value); $('outStrength').textContent = (+e.target.value).toFixed(1) + 'x'; };

window.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.code === 'Space') { e.preventDefault(); sim.running = !sim.running; }
  else if (e.key === 'r' || e.key === 'R') sim.reset();
});

// ---------- readouts ---------------------------------------------------------
const sci = (v, unit, d = 4) => `${v.toFixed(d)} ${unit}`;
function updateReadouts() {
  const p = sim.physics;
  const [title, sub] = sim.banner();
  $('banTitle').textContent = title;
  $('banSub').textContent = sub;
  $('rPos').textContent = sci(sim.magX * 0.2, 'm', 3);
  $('rVel').textContent = sci(sim.magVel, 'm/s', 3);
  $('rB').textContent = sci(sim.B, 'T', 4);
  $('rA').textContent = sci(p.coilArea, 'm\u00b2', 4);
  $('rN').textContent = String(p.turns);
  $('rFlux').textContent = sci(sim.flux, 'Wb', 5);
  $('rDphi').textContent = sci(sim.dphi, 'Wb/s', 4);
  $('rEmf').textContent = sci(sim.emf, 'V', 3);
  $('rCurr').textContent = sci(sim.curr, 'A', 4);
  $('rNeedle').textContent = sci(sim.needle, '\u00b0', 1);
  $('rDir').textContent = p.directionText(sim.curr);
  $('rLamp').textContent = sim.lamp > 0.04
    ? `${Math.round(sim.lamp * 100)}%  (${(sim.lampPower * 1000).toFixed(0)} mW)` : 'OFF';
}

// ---------- main loop ----------------------------------------------------------
let last = performance.now(), acc = 0, readoutClock = 0;
function frame(now) {
  acc += Math.min((now - last) / 1000, 0.1);
  last = now;
  let n = 0;
  while (acc >= DT && n < 10) { sim.step(); acc -= DT; n++; }
  if (n === 10) acc = 0;

  apparatus.update({ magX: sim.magX, needleDeg: sim.needle, current: sim.curr, lampLevel: sim.lamp });
  controls.update();
  renderer.render(apparatus.scene, camera);
  graphs.draw();

  readoutClock += 1;
  if (readoutClock % 4 === 0) updateReadouts();
  requestAnimationFrame(frame);
}
updateReadouts();
requestAnimationFrame(frame);
