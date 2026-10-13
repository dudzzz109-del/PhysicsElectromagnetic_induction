# Virtual Physics Laboratory: Electromagnetic Induction
### Interactive 3D Simulation using VPython and NumPy
**School Physics Project — Faraday's Law & Lenz's Law**

---

## 🔬 Project Overview

This project is a realistic virtual laboratory apparatus recreating the classic **electromagnetic induction** experiment. It visually and mathematically demonstrates how a moving bar magnet produces a changing magnetic flux through a conducting solenoid coil, inducing an electromotive force (EMF) and driving an electrical current that deflects an analog galvanometer.

```
       MULTI-TURN COIL                  BAR MAGNET
        ((((((((((((                  ┌──────────────┐
        ((((((((((((  ← B Field line  │ N          S │  ⇄ [MAGNET MOTION]
        ((((((((((((                  └──────────────┘
           │      │
           │      └─────────────────┐
           │                        │ (Connecting Wires)
           └────────────────┐       │
                            │       │
                         ┌──┴───────┴──┐
                         │   −  0  +   │
                         │      ↖      │ (Red Needle)
                         │GALVANOMETER │
                         └─────────────┘
```

---

## ⚛️ Physical Principles & Mathematical Model

### 1. The Core Induction Chain

$$\text{Moving Magnet} \implies \text{Changing } B \implies \text{Changing Flux } \Phi_B \implies \text{Induced EMF } \mathcal{E} \implies \text{Current } I \implies \text{Galvanometer Deflection } \theta$$

### 2. Finite Bar Magnet Field Model (Educational Approximation)
A bar magnet of length $2L_m$ is modeled as two effective magnetic poles: North ($+q_m$) and South ($-q_m$). Along the axis of symmetry, the magnetic field at distance $x$ from the magnet center is:

$$B(x) = \frac{\mu_0 q_m}{4\pi} \left[ \frac{1}{(x - x_N)^2 + R_m^2} - \frac{1}{(x - x_S)^2 + R_m^2} \right]$$

- Follows the physical $\sim 1/r^3$ dipole decay at large distances.
- $R_m$ provides a physical softening radius representing the cross-sectional size of the magnet, ensuring smooth, non-singular behavior even when the magnet enters the hollow coil.

### 3. Magnetic Flux
Magnetic flux through the coil of cross-sectional area $A = \pi r_{\text{coil}}^2$:

$$\Phi_B = B \cdot A \cdot \cos(\theta)$$

For axial alignment ($\theta = 0^\circ$), $\cos(\theta) = 1$ (maximum coupling).

### 4. Faraday's Law of Induction
The induced electromotive force (EMF) is proportional to the time rate of change of magnetic flux:

$$\mathcal{E} = -N \frac{d\Phi_B}{dt}$$

where:
- $\mathcal{E}$ = Induced EMF ($\text{Volts, V}$)
- $N$ = Number of coil turns
- $\frac{d\Phi_B}{dt}$ = Rate of change of magnetic flux ($\text{Wb/s}$) calculated via numerical finite difference.

### 5. Lenz's Law & Circuit Current
According to Ohm's Law for the closed circuit:

$$I = \frac{\mathcal{E}}{R_{\text{circuit}}}$$

The negative sign in Faraday's Law represents **Lenz's Law**:
- **Magnet Moving Toward Coil** ($\Phi_B$ increasing): $\frac{d\Phi_B}{dt} > 0 \implies \mathcal{E} < 0 \implies I < 0$. The needle deflects left.
- **Magnet Stopped** ($\Phi_B$ constant): $\frac{d\Phi_B}{dt} = 0 \implies \mathcal{E} = 0 \implies I = 0$. The needle rests at center ($0^\circ$).
- **Magnet Moving Away** ($\Phi_B$ decreasing): $\frac{d\Phi_B}{dt} < 0 \implies \mathcal{E} > 0 \implies I > 0$. The needle deflects right.
- **Faster Motion**: Higher $\left|\frac{d\Phi_B}{dt}\right| \implies$ larger $|\mathcal{E}| \implies$ greater needle deflection.

### 6. Galvanometer Deflection
The angular deflection of the meter pointer is proportional to the calculated current:

$$\theta_{\text{deg}} = k_{\text{meter}} \cdot I$$

---

## 🧲 Pass-Through Mode (magnet goes straight through the coil)

In **PASS THROUGH** mode the magnet starts on the right, enters the coil with its North pole, travels all the way through and leaves the other (left) side completely (centre swings from $x = +0.37\,\text{m}$ to $-0.59\,\text{m}$), then returns.

**Why a different field model is needed.** Outside the magnet the field along the axis points one way; *inside* the magnet it points the opposite way. So when the magnet passes through the coil the flux changes **sign**. The bounce model returns only $|B|$ at the coil centre, which cannot do that. In pass-through mode the flux through the coil opening is computed from the same two-pole magnet, integrated over the coil disc (radius $r$). For each pole of strength $\pm q_m$ at axial distance $d$ from the coil plane ($s^2 = d^2 + R_m^2$):

$$\Phi_{\text{pole}} = \frac{\mu_0 q_m}{4\pi}\; 2\pi d \left[\frac{1}{s} - \frac{1}{\sqrt{r^2 + s^2}}\right], \qquad \Phi_B = \Phi_N - \Phi_S, \qquad B_{\text{avg}} = \frac{\Phi_B}{A}$$

$d$ changes sign when a pole crosses the coil plane, which is what reverses the flux. The readout still obeys $\Phi = B_{\text{avg}} \cdot A$, and Faraday's law, Ohm's law and the needle are unchanged. The pole strength is calibrated so the peak EMF is about 0.40 V at 1x speed with $N = 20$.

**What you see on one pass (needle):**

| Magnet position | Flux $\Phi$ | EMF | Needle |
|---|---|---|---|
| N pole approaching the coil | rising | negative | LEFT |
| N pole crossing the coil | falls through zero and **reverses** | large positive | RIGHT |
| Middle of the magnet inside the coil | steady (large, but not changing) | ≈ 0 | CENTRE |
| S end leaving the coil | rises back toward zero | negative | LEFT |
| Magnet far away | ≈ 0 | ≈ 0 | CENTRE |

The current direction is reported as seen from the **right** (the magnet's starting side). N pole approaching → counterclockwise from the right → the coil's right face becomes a North pole and repels the magnet (Lenz).

---

## 🌐 Run it online (GitHub Pages — automatic publishing)

GitHub can only host *static* websites, and the VPython version (`main.py`) needs a running Python process, so it cannot be published as is. The `web/` folder is a **browser version of the same simulation** (JavaScript + Three.js, same physics constants and equations, same pass-through / bounce modes, live graphs on the right). It needs no installation: it is just HTML/JS files.

**One-time setup**

1. Create a GitHub repository and push this project (the `.gitignore` keeps `.venv/` out):
   ```bash
   git init
   git add .
   git commit -m "Electromagnetic induction simulation"
   git branch -M main
   git remote add origin https://github.com/<your-user>/<your-repo>.git
   git push -u origin main
   ```
2. On GitHub open **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.

**After that, every `git push` to `main` publishes automatically.** The workflow `.github/workflows/pages.yml` first runs the headless physics/graph/scene checks (`web/tests/run.mjs`), then deploys the `web/` folder. The site appears at `https://<your-user>.github.io/<your-repo>/` (the address is also shown in the **Actions** tab).

**Try it on your own computer first** (browsers block ES modules from `file://`, so use a tiny local server):

```bash
cd web
python -m http.server 8000      # then open http://localhost:8000
```

Run the automated checks locally (needs Node 18+): `node --import ./web/tests/register.mjs web/tests/run.mjs`

---

## ▲ Deploy on Vercel

`main.py` now has two jobs: `python main.py` still opens the desktop VPython simulation, and it also exposes a Flask web host named `app`, which Vercel finds automatically. The host serves the browser version of the simulation (the `web/` folder) at the **root URL**, so nobody has to type `index.html`.

> **Why not the VPython version itself?** VPython needs a long-running Python process and open websocket ports. Vercel is serverless, so that cannot run there. The `web/` version has the same physics constants, 3D scene, controls, pass-through mode and live graphs.

**Deploy**

1. Push the project to GitHub (repository root = the folder that contains `main.py`, `web/`, `vercel.json`).
2. Go to [vercel.com](https://vercel.com) → **Add New… → Project** → import your repository.
3. Leave **Framework Preset** as detected (Flask) or choose *Other*. Leave **Build Command** and **Output Directory** empty. Click **Deploy**.
4. Open the URL Vercel shows (`https://<project>.vercel.app`). Every later `git push` redeploys automatically.

**Test the same host locally**

```bash
pip install -r requirements.txt
python main.py --web                      # http://localhost:8000
python main.py --web --host 0.0.0.0 --port 8080
```

---

## 🛠️ Technologies Used

| Library | Role in Project |
|---|---|
| **VPython** | 3D apparatus rendering, coil, magnet, curved field lines, analog meter, needle animation, wires, and controls. *(Constructed without `torus` for universal compatibility).* |
| **NumPy** | High-performance numerical calculations: field evaluation, flux integration, finite-difference numerical derivative $\frac{d\Phi_B}{dt}$, Ohm's Law, and meter kinematics. |
| **VPython (in-scene graphs)** | Real-time synchronized graphs of $\Phi_B(t)$, $\mathcal{E}(t)$ and $I(t)$ drawn inside the 3D scene, on the right-hand side. |

---

## 🎮 Virtual Laboratory Features & Controls

| Control | Action |
|---|---|
| **▶ PLAY** | Starts the real-time simulation and magnet motion. |
| **⏸ PAUSE** | Freezes the animation to inspect instantaneous physical quantities. |
| **⟳ RESET** | Restores initial conditions and clears graphing history. |
| **⇄ REVERSE DIRECTION** | Inverts the magnet's motion direction mid-flight (the magnet turns round smoothly). |
| **MODE: PASS THROUGH / BOUNCE** | Toggles the motion. *Pass through*: the magnet enters the coil, travels through it and exits the other side. *Bounce*: the original swing in and back out the same side. |
| **📊 LIVE GRAPHS (right side)** | Always on: three plots of $\Phi$, $\mathcal{E}$ and $I$ vs. time sit to the right of the apparatus and update every frame as the magnet moves. The trace sweeps left to right over 12 s (one full pass-through cycle); the dot marks "now". All three share a symmetric vertical scale so sign reversals are obvious. |
| **Magnet Speed Slider** | Adjusts velocity; directly verifies that higher speed produces larger EMF. |
| **Coil Turns ($N$) Slider** | Adjusts turn count; verifies $\mathcal{E} \propto N$. |
| **Magnet Strength Slider** | Scales magnetic field strength $B_0$. |

---

## 📊 Live Numerical Readout Panel

Updated continuously in the 3D scene:
- **Magnet Position** ($\text{m}$)
- **Magnet Velocity** ($\text{m/s}$)
- **Magnetic Field** ($\text{T}$)
- **Coil Area** ($\text{m}^2$)
- **Number of Turns** ($N$)
- **Magnetic Flux** ($\text{Wb}$)
- **$d\Phi/dt$** ($\text{Wb/s}$)
- **Induced EMF** ($\text{V}$)
- **Current** ($\text{A}$)
- **Galvanometer Deflection** ($\text{deg}$)
- **Current Direction** (*Clockwise / Counterclockwise / None*)

---

## 🚀 How to Install and Run

### 1. Install Dependencies
```bash
pip install -r requirements-desktop.txt
```

### 2. Launch the Virtual Laboratory
```bash
python main.py
```

*An interactive 3D WebGL scene will automatically open in your web browser. Click **▶ PLAY** to begin the experiment.*

---

## 📁 Project Structure

```
Electromagnetic_induction/
│
├── main.py          # Application entry point & welcome banner
├── simulation.py    # VPython 3D laboratory scene & UI controls
├── physics.py       # NumPy mathematical calculations & physical laws
├── graphs.py        # Live graphs drawn inside the 3D scene (right side)
├── graph.py         # Compatibility forwarder
├── web/             # Browser version (published to GitHub Pages)
│   ├── index.html, app.js, sim.js, physics.js, scene.js, graphs.js
│   ├── vendor/      # three.js (bundled, no CDN needed)
│   └── tests/       # headless checks run by the workflow
├── .github/workflows/pages.yml   # auto-deploy on every push
├── requirements.txt # Web host dependency (Flask) — what Vercel installs
├── requirements-desktop.txt # Desktop VPython app dependencies
├── vercel.json      # Vercel config (bundles web/ with the function)
└── README.md        # Comprehensive documentation
```
