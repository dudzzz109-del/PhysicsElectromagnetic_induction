"""
main.py — Main Application Entry Point  (desktop VPython app  +  web host for Vercel)
=======================================================================================
Virtual Physics Laboratory: Electromagnetic Induction
School Physics Project | CCE105

Demonstrates:
  MOVING BAR MAGNET
        ↓
  CHANGING MAGNETIC FIELD
        ↓
  CHANGING MAGNETIC FLUX
        ↓
  INDUCED EMF (Faraday's Law: EMF = -N dΦ/dt)
        ↓
  INDUCED CURRENT (Lenz's Law: I = EMF / R)
        ↓
  GALVANOMETER NEEDLE DEFLECTION

How to run
----------
  Desktop (VPython, opens your browser on localhost):
      pip install -r requirements-desktop.txt
      python main.py

  Website host (same simulation, as a browser app from the web/ folder):
      pip install -r requirements.txt
      python main.py --web                 # http://localhost:8000
      python main.py --web --host 0.0.0.0 --port 8080

  Vercel: Vercel finds the `app` object below automatically (Flask).  It serves the page at
  the root URL ("/"), so nobody has to type index.html.  See README -> "Deploy on Vercel".
  (VPython itself cannot run on Vercel: it needs a long-running Python process and open
  websocket ports, which serverless hosting does not provide.  The web/ version has the same
  physics, controls, 3D scene and live graphs.)
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure local module directory is in sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

WEB_DIR = Path(_HERE) / "web"

# ---------------------------------------------------------------------------------------
# WEB HOST  (WSGI app named `app` — this is what Vercel / gunicorn / `flask run` look for)
# Flask is optional: the desktop app below works without it.
# ---------------------------------------------------------------------------------------
try:
    from flask import Flask, abort, send_from_directory
except ImportError:          # desktop-only install
    Flask = None

if Flask is not None:
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def home():
        """The simulation page is served at the root URL — no /index.html needed."""
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/<path:filename>")
    def assets(filename):
        """JS modules, bundled three.js, etc. from web/ (tests are not published)."""
        if filename.startswith("tests/") or filename.startswith("."):
            abort(404)
        # send_from_directory refuses paths that escape WEB_DIR (no directory traversal)
        return send_from_directory(WEB_DIR, filename)
else:
    app = None


def main():
    print("=" * 75)
    print("  VIRTUAL PHYSICS LABORATORY: ELECTROMAGNETIC INDUCTION")
    print("  Interactive 3D Simulation — Moving Magnet, Solenoid, and Galvanometer")
    print("  Faraday's Law of Induction & Lenz's Law")
    print("=" * 75)
    print()
    print("  Apparatus Components in 3D Scene:")
    print("    • MULTI-TURN COIL   : Realistic copper solenoid on left horizontal axis")
    print("    • BAR MAGNET        : Rectangular magnet (Red N facing coil, Blue S)")
    print("    • MAGNETIC FIELD    : Curved field lines (B) arching between poles")
    print("    • GALVANOMETER      : Analog benchtop meter with center zero & ± scale")
    print("    • CONNECTING WIRES  : Two visible 3D wires completing the circuit")
    print("    • CURRENT ARROWS    : Real-time direction indicators (Lenz's Law)")
    print()
    print("  Interactive Controls:")
    print("    ▶ [ PLAY ]               : Starts the magnet oscillation")
    print("    ⏸ [ PAUSE ]              : Pauses the simulation at any point")
    print("    ⟳ [ RESET ]              : Restores initial stationary position")
    print("    ⇄ [ REVERSE DIRECTION ]  : Flips the magnet motion direction")
    print("    ⇆ [ MODE ]               : PASS THROUGH (magnet goes through the coil) / BOUNCE")
    print("    📊 LIVE GRAPHS            : Φ, EMF and I vs time, drawn inside the scene (right side)")
    print("    • Magnet Speed slider    : Observe that faster motion -> larger EMF")
    print("    • Coil Turns (N) slider  : Observe EMF proportional to N")
    print("    • Magnet Strength slider : Scales magnetic field and flux amplitude")
    print()
    print("  Physical Observations:")
    print("    1. Magnet approaching coil -> Flux increases -> Needle deflects to one side")
    print("    2. Magnet stationary       -> dΦ/dt = 0     -> Needle returns to zero (center)")
    print("    3. Magnet moving away      -> Flux decreases -> Needle deflects to opposite side")
    print("    4. Faster motion           -> Larger dΦ/dt  -> Greater needle deflection")
    print("=" * 75)
    print()

    # Launch simulation (imported here so the web host never loads VPython)
    from simulation import SimulationScene
    sim = SimulationScene(coil_turns=20)
    sim.run()


def run_web(host, port):
    if app is None:
        sys.exit("Flask is not installed.  Run:  pip install -r requirements.txt")
    print(f"Serving the simulation on http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Electromagnetic induction simulation")
    parser.add_argument("--web", action="store_true",
                        help="serve the browser version (web/ folder) instead of opening the VPython app")
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    args = parser.parse_args()
    if args.web:
        run_web(args.host, args.port)
    else:
        main()
