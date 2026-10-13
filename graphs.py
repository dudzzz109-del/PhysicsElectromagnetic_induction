"""
graphs.py — LIVE GRAPHS DRAWN INSIDE THE 3D SIMULATION (right-hand side)
=========================================================================
Three real-time plots sit on a dark panel to the RIGHT of the apparatus, in the
same VPython scene as the coil, magnet and galvanometer (no pop-up window, no
Matplotlib, no Tkinter):

    1. Magnetic flux   Phi_B   [Wb]   = B * A * cos(theta)
    2. Induced EMF             [V]    = -N * dPhi/dt          (Faraday)
    3. Induced current I       [A]    = EMF / R               (Lenz / Ohm)

HOW IT DRAWS (oscilloscope "sweep" style)
-----------------------------------------
* The trace is written left -> right across the plot as time passes; a bright dot
  marks the newest sample.  When it reaches the right edge (WINDOW seconds) the
  plots are cleared and a new sweep starts from the left.
* WINDOW = 12 s is longer than one full pass-through cycle (10.5 s), so you see the
  magnet go in, straight out the other side, and back - all on one screen.
* Every plot uses the SAME vertical scale on both sides of zero, so a flux or EMF
  that reverses sign (magnet passing through the coil) is obvious.  The scale only
  grows during a sweep (1-2-5 steps) and is re-fitted at the start of the next one.
* Only ONE new point per plot is sent to the browser per sample (every STRIDE
  frames), so it stays smooth.

The data come straight from the NumPy physics values (zero fake data):
SimulationScene.step() calls  push(t, flux, emf, current)  every frame.
"""

import math
from vpython import vector, curve, label, box, sphere


def _v(x, y=0.0, z=0.0):
    """Safe builder for vpython.vector ensuring standard Python floats."""
    return vector(float(x), float(y), float(z))


def _nice_ceil(value):
    """Smallest 'nice' number (1, 2 or 5 times a power of ten) that is >= value."""
    if value <= 0.0:
        return 1.0
    e = math.floor(math.log10(value))
    m = value / (10.0 ** e)
    for step in (1.0, 2.0, 5.0, 10.0):
        if m <= step * 1.000001:
            return step * (10.0 ** e)
    return 10.0 ** (e + 1)


def _fmt(value):
    """Short tick-label text, e.g. 0.002, 0.5, 2."""
    return f"{value:.2g}"


class SceneGraphs:
    """Three stacked live plots rendered inside the VPython scene."""

    # key, title, colour (r, g, b), minimum half-range (floor of the scale)
    PLOTS = [
        ("flux", "1. Magnetic flux  \u03a6 = B\u00b7A   [Wb]",            (0.22, 0.74, 0.97), 0.0005),
        ("emf",  "2. Induced EMF = \u2212N\u00b7d\u03a6/dt   [V]",         (0.96, 0.25, 0.37), 0.05),
        ("curr", "3. Induced current  I = EMF / R   [A]",                 (0.29, 0.87, 0.50), 0.025),
    ]

    def __init__(self, x_left=3.30, x_right=6.55, y_top=3.05,
                 window=12.0, stride=4):
        self.window = float(window)      # seconds shown across one sweep
        self.stride = int(stride)        # draw one point every `stride` frames

        # ---- geometry (world units) -----------------------------------------
        plot_h   = 1.00
        spacing  = 0.50                  # room for each plot's title
        self.px0 = x_left + 0.58         # plot area left edge
        self.px1 = x_right - 0.12        # plot area right edge
        self.plot_h = plot_h

        first_top = y_top - 0.75
        tops = [first_top - i * (plot_h + spacing) for i in range(3)]
        y_bot = tops[-1] - plot_h - 0.62
        self.tops = tops

        # ---- backing panel ---------------------------------------------------
        box(pos=_v((x_left + x_right) / 2.0, (y_top + y_bot) / 2.0, -0.04),
            size=_v(x_right - x_left, y_top - y_bot, 0.02),
            color=_v(0.07, 0.09, 0.14), opacity=0.92)
        label(pos=_v((x_left + x_right) / 2.0, y_top - 0.20, 0.06),
              text="LIVE GRAPHS  (update in real time)",
              color=_v(0.22, 0.74, 0.97), height=11, box=False)

        # ---- per-plot objects ------------------------------------------------
        self.curves, self.dots = {}, {}
        self.lbl_top, self.lbl_bot = {}, {}
        self.mids = {}
        self._scale = {}
        for (key, title, rgb, floor), top in zip(self.PLOTS, tops):
            mid = top - plot_h / 2.0
            self.mids[key] = mid
            col = _v(*rgb)
            # frame
            curve(pos=[_v(self.px0, top, 0.01), _v(self.px1, top, 0.01), _v(self.px1, top - plot_h, 0.01),
                       _v(self.px0, top - plot_h, 0.01), _v(self.px0, top, 0.01)],
                  color=_v(0.30, 0.36, 0.48), radius=0.006)
            # zero line
            curve(pos=[_v(self.px0, mid, 0.012), _v(self.px1, mid, 0.012)],
                  color=_v(0.55, 0.60, 0.70), radius=0.005)
            # title and tick labels
            label(pos=_v((self.px0 + self.px1) / 2.0, top + 0.17, 0.06), text=title,
                  color=col, height=10, box=False)
            tick_x = x_left + 0.29
            self.lbl_top[key] = label(pos=_v(tick_x, top - 0.02, 0.06), text="", height=9,
                                      color=_v(0.80, 0.85, 0.95), box=False)
            label(pos=_v(tick_x, mid, 0.06), text="0", height=9,
                  color=_v(0.80, 0.85, 0.95), box=False)
            self.lbl_bot[key] = label(pos=_v(tick_x, top - plot_h + 0.02, 0.06), text="", height=9,
                                      color=_v(0.80, 0.85, 0.95), box=False)
            # trace + "newest sample" dot
            self.curves[key] = curve(color=col, radius=0.014)
            self.dots[key]   = sphere(pos=_v(self.px0, mid, 0.03), radius=0.04, color=col)
            self._scale[key] = floor
            self._write_scale_labels(key)

        # ---- time axis labels (under the last plot) --------------------------
        y_t = tops[-1] - plot_h - 0.17
        self.lbl_t0 = label(pos=_v(self.px0,                       y_t, 0.06), text="0", height=9,
                            color=_v(0.80, 0.85, 0.95), box=False)
        self.lbl_t1 = label(pos=_v((self.px0 + self.px1) / 2.0,    y_t, 0.06), text="", height=9,
                            color=_v(0.80, 0.85, 0.95), box=False)
        self.lbl_t2 = label(pos=_v(self.px1,                       y_t, 0.06), text="", height=9,
                            color=_v(0.80, 0.85, 0.95), box=False)
        label(pos=_v((self.px0 + self.px1) / 2.0, y_t - 0.22, 0.06),
              text="time  t  (s)   -   trace sweeps left \u2192 right, dot = now",
              height=9, color=_v(0.60, 0.66, 0.78), box=False)

        # ---- data buffers ----------------------------------------------------
        self._sweep = 0
        self._frame = 0
        self._ts = []                                   # time inside the sweep [s]
        self._vals = {k: [] for k, *_ in self.PLOTS}    # sampled values
        self._peak = {k: 0.0 for k, *_ in self.PLOTS}   # peak |value| in this sweep
        self._write_time_labels()

    # -------------------------------------------------------------------------
    # helpers
    # -------------------------------------------------------------------------
    def _write_scale_labels(self, key):
        s = self._scale[key]
        self.lbl_top[key].text = "+" + _fmt(s)
        self.lbl_bot[key].text = "\u2212" + _fmt(s)

    def _write_time_labels(self):
        t0 = self._sweep * self.window
        self.lbl_t0.text = f"{t0:.0f}"
        self.lbl_t1.text = f"{t0 + self.window / 2.0:.0f}"
        self.lbl_t2.text = f"{t0 + self.window:.0f}"

    def _point(self, key, ts, val):
        """World position of one sample on plot `key` (clipped to the frame)."""
        x = self.px0 + (ts / self.window) * (self.px1 - self.px0)
        frac = max(-1.0, min(1.0, val / self._scale[key]))
        y = self.mids[key] + frac * (self.plot_h / 2.0) * 0.96
        return _v(x, y, 0.02)

    def _redraw(self, key):
        """Rebuild one trace from the stored samples (only when its scale changed)."""
        c = self.curves[key]
        c.clear()
        for ts, val in zip(self._ts, self._vals[key]):
            c.append(self._point(key, ts, val))

    # -------------------------------------------------------------------------
    # public API
    # -------------------------------------------------------------------------
    def clear(self):
        """Wipe everything (RESET button / mode change): back to sweep 0, default scales."""
        self._sweep = 0
        self._frame = 0
        self._ts = []
        for key, _, _, floor in self.PLOTS:
            self._vals[key] = []
            self._peak[key] = 0.0
            self._scale[key] = floor
            self.curves[key].clear()
            self.dots[key].pos = _v(self.px0, self.mids[key], 0.03)
            self._write_scale_labels(key)
        self._write_time_labels()

    def _start_new_sweep(self, sweep):
        """Window is full: clear the traces, re-fit the scale to the last sweep's peak."""
        self._sweep = sweep
        self._ts = []
        for key, _, _, floor in self.PLOTS:
            self._vals[key] = []
            self._scale[key] = max(floor, _nice_ceil(self._peak[key] * 1.05))
            self._peak[key] = 0.0
            self.curves[key].clear()
            self._write_scale_labels(key)
        self._write_time_labels()

    def push(self, t, flux, emf, current):
        """
        Feed one frame of physics results (called every frame from the main loop).
        `t` is the simulation's real time [s].
        """
        sweep = int(t // self.window)
        if sweep != self._sweep:
            self._start_new_sweep(sweep)

        values = {"flux": flux, "emf": emf, "curr": current}
        # Track the peak every frame (cheap) so the scale never misses a spike
        scale_changed = []
        for key, val in values.items():
            a = abs(val)
            if a > self._peak[key]:
                self._peak[key] = a
            if a > self._scale[key]:
                self._scale[key] = _nice_ceil(a * 1.05)
                scale_changed.append(key)

        self._frame += 1
        if self._frame % self.stride:
            # not a drawing frame: store nothing, but if the scale grew we must redraw
            for key in scale_changed:
                self._write_scale_labels(key)
                self._redraw(key)
            return

        ts = t - self._sweep * self.window
        self._ts.append(ts)
        for key, val in values.items():
            self._vals[key].append(float(val))
        for key in scale_changed:
            self._write_scale_labels(key)
            self._redraw(key)                       # includes the sample we just stored
        for key, val in values.items():
            p = self._point(key, ts, val)
            if key not in scale_changed:
                self.curves[key].append(p)
            self.dots[key].pos = _v(p.x, p.y, 0.03)


# Backward-compatible names (older code imported these)
LiveGraphManager = SceneGraphs
GraphManager = SceneGraphs
