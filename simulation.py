"""
simulation.py — Virtual Physics Laboratory Apparatus
=====================================================
Interactive 3D Simulation of Electromagnetic Induction.
Key Features:
  • Hollow multi-turn conducting coil (solenoid built with ring() objects)
  • Rectangular bar magnet (Red N, Blue S) with velocity arrow
  • Curved magnetic field lines (B) with directional arrows
  • Analog benchtop galvanometer with calibrated scale and dynamic red needle
  • Two visible 3D circuit connecting wires
  • Tangential Lenz's Law induced current arrows around coil
  • Real-time scientific readout panel on the FAR LEFT (leaving coil center clear)
  • LIVE GRAPHS drawn INSIDE the 3D scene on the right (flux, EMF, current vs time)
  • Interactive control console (Play, Pause, Reset, Reverse, Mode, Sliders)
  • Two motion modes: PASS-THROUGH (magnet goes straight through the coil and out the
    other side) and BOUNCE (magnet swings in and back out the same side)

Compatible with Python 3.10+ and VPython 7.6+ (No torus used).

DEFENSE GUIDE TO THIS FILE
--------------------------
This file is the "body": it DRAWS things and handles buttons/sliders. It does
NOT contain the physics equations (those are in physics.py).

  __init__()        -> creates PhysicsEngine + all 3D objects + controls
  _build_*()        -> draw coil, magnet, field lines, galvanometer, wires
  _build_controls() -> Play / Pause / Reset / Reverse / Mode + 3 sliders
  _cb_*()           -> button & slider callbacks (they ONLY set flags/values)
  _update_*()       -> redraw objects each frame from the latest physics values
  step()            -> ONE animation frame: move magnet -> physics -> redraw
  run()             -> endless loop at 80 frames/s that calls step()
  _build_lamp_and_flow()/_update_lamp_and_flow() -> series lamp (brightness = I^2R) + moving charge dots
  _build_presenter()/_update_presenter() -> on-screen banner, live lesson, guided tour, live math

UNITS: the scene uses "world units". Multiply by WORLD_TO_METERS (0.20) to get
meters. Example: magnet travels x = +1.85 .. -0.65 (world) = +0.37 .. -0.13 m.
"""

from vpython import (
    canvas, cylinder, ring, sphere, arrow, box, label,
    curve, vector, color, rate, slider, button, wtext,
    cos, sin, pi, scene
)
import numpy as np
from physics import PhysicsEngine, WORLD_TO_METERS
from graphs import SceneGraphs


def _v(x, y=0.0, z=0.0):
    """Safe builder for vpython.vector ensuring standard Python floats."""
    return vector(float(x), float(y), float(z))


def _screen_size():
    """
    Returns (width, height) of the user's monitor in pixels so the 3D canvas
    can fill the browser window. Tries tkinter, then the Windows API, then a
    safe 1920x1080 default.
    """
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:
        pass
    try:
        import ctypes
        u32 = ctypes.windll.user32
        return int(u32.GetSystemMetrics(0)), int(u32.GetSystemMetrics(1))
    except Exception:
        pass
    return 1920, 1080


class SimulationScene:
    """
    Manages the 3D apparatus, animation loop, in-scene live graphs, and user controls.
    """

    # -------------------------------------------------------------------------
    # Geometric Layout Constants (World Units)
    # -------------------------------------------------------------------------
    # --- WORLD units (x0.20 = meters). Coil center -1.30 world = -0.26 m ---
    COIL_X       = -1.30     # Solenoid center on x-axis
    COIL_Y       =  0.75     # Height of the coil and magnet horizontal axis
    COIL_RADIUS  =  0.48     # Solenoid inner radius (sufficient for magnet entry)
    COIL_SPAN    =  1.10     # Solenoid length along x-axis
    NUM_RINGS    =  12       # Number of physical wound copper turns

    # Bar magnet dimensions (cross-section fits smoothly inside coil)
    MAG_POLE_LEN =  0.48     # Half length of magnet (each pole is 0.48, total = 0.96)
    MAG_HEIGHT   =  0.22     # Height < 2 * COIL_RADIUS so magnet enters coil smoothly
    MAG_DEPTH    =  0.22

    # Magnet oscillation boundaries
    # Magnet swings between FAR (+1.85 = 0.37 m) and NEAR (-0.65 = -0.13 m).
    # NEAR is the "turnaround point": velocity = 0 there, so dPhi/dt = 0, EMF = 0.
    MAG_X_NEAR   = -0.65     # Magnet enters inside the front of the hollow coil!
    MAG_X_FAR    =  1.85     # Retracted away from coil

    # PASS-THROUGH mode: the magnet swings from MAG_X_FAR all the way THROUGH the coil
    # and out the other (left) side.  The coil spans x = -1.85 .. -0.75 and the magnet is
    # 0.96 long, so its centre must get below -1.85 - 0.48 = -2.33 to be completely out.
    # -2.95 leaves a clear gap.  Slower omega keeps the peak speed (~0.3 m/s) about the same
    # as in BOUNCE mode, because the swing is almost twice as long.
    MAG_X_PASS_END = -2.95
    BOUNCE_OMEGA   = 1.15    # rad/s
    PASS_OMEGA     = 0.60    # rad/s

    # Galvanometer benchtop position at bottom
    GALV_X       = -0.45
    GALV_Y       = -1.30
    GALV_Z       =  0.00

    def __init__(self, coil_turns=20):
        # NumPy physics engine
        self.physics = PhysicsEngine(
            coil_radius_m         = self.COIL_RADIUS * WORLD_TO_METERS,
            coil_turns            = coil_turns,
            coil_resistance       = 2.0,
            magnet_strength_scale = 1.0
        )

        # Animation kinematic state
        self.running            = False
        self.sim_time           = 0.0
        self.dt                 = 0.012   # time per frame [s]  (~83 frames/s; loop targets 80)
        self.real_time          = 0.0     # FIX: real time used for dPhi/dt (not scaled by speed)
        self.speed              = 1.0
        self.motion_dir         = 1.0

        self.mag_x       = self.MAG_X_FAR
        self.mag_vel     = 0.0
        # Magnet motion is simple harmonic:  x = mid + amp * cos(phase)
        # The PHASE is accumulated frame by frame (phase += omega*dt*speed*direction).
        # That is what makes REVERSE work: flipping the direction makes the phase run
        # backwards from where it is, so the magnet turns round smoothly.
        # (The old  cos(omega*t*dir)  form could not reverse because cosine is even.)
        # amp / mid / omega are set by _set_mode():
        #   BOUNCE       : x = +1.85 .. -0.65  (0.37 .. -0.13 m), omega 1.15 -> max speed 0.29 m/s
        #   PASS-THROUGH : x = +1.85 .. -2.95  (0.37 .. -0.59 m), omega 0.60 -> max speed 0.29 m/s
        self.phase        = 0.0
        self.pass_through = True
        self.request_mode = None      # thread-safe request set by the MODE button
        self._set_mode(True, reset=False)

        # Physical cached values
        self.B_val       = 0.0
        self.flux_val    = 0.0
        self.emf_val     = 0.0
        self.dphi_val    = 0.0
        self.curr_val    = 0.0
        self.needle_deg  = 0.0

        # Presenter / teaching mode state (see section 11B)
        self.tour_step      = -1      # -1 = "live explain" mode, 0..N = guided tour slide
        self.request_tour   = None    # thread-safe request set by tour buttons
        self.auto_pause     = False   # tour can ask the sim to pause at the turnaround
        self.state          = "READY" # APPROACH / TURNAROUND / RETREAT / REST / READY
        self._pframe        = 0       # frame counter to throttle text updates
        self._lesson_key    = None

        # Lamp + current-flow visuals (see section 7B)
        self.lamp_level     = 0.0     # smoothed lamp brightness 0..1 (filament inertia)
        self.lamp_power     = 0.0     # P = I^2 R  [W]
        self.flow_phase     = 0.0     # position offset of the moving charge dots

        # Construct virtual laboratory
        self._setup_canvas()
        self._build_conducting_coil()
        self._build_bar_magnet()
        self._build_magnetic_field_lines()
        self._build_galvanometer()
        self._build_connecting_wires()
        self._build_lenz_current_arrows()
        self._build_laboratory_labels()
        self.graphs = SceneGraphs()          # live graphs panel on the RIGHT of the scene
        self._build_info_panel()
        self._build_controls()
        self._build_presenter()

        # Initial apparatus alignment
        self._update_all_visuals()

    # =========================================================================
    # 1. 3D CANVAS SETUP
    # =========================================================================
    def _setup_canvas(self):
        scene.title = (
            "<b style='font-size:19px; color:#38bdf8'>"
            "Virtual Physics Laboratory: Electromagnetic Induction</b><br>"
            "<span style='font-size:13px; color:#cbd5e1'>"
            "Faraday's Law: &Epsilon; = &minus;N(d&Phi;/dt) &bull; Lenz's Law: Direction Opposes Flux Change</span>"
        )
        # FULL-SCREEN CANVAS: size the 3D view from the monitor resolution so it
        # fills the browser window. Tune these two margins if it does not fit:
        #   CANVAS_MARGIN_W : pixels kept free at the sides (avoids horizontal scrollbar)
        #   CANVAS_MARGIN_H : pixels kept free for browser tabs/address bar/taskbar + page title
        # For a truly edge-to-edge view also press F11 in the browser (full-screen mode).
        CANVAS_MARGIN_W = 30
        CANVAS_MARGIN_H = 215
        screen_w, screen_h = _screen_size()
        scene.width      = max(900, screen_w - CANVAS_MARGIN_W)
        scene.height     = max(550, screen_h - CANVAS_MARGIN_H)
        scene.background = _v(0.06, 0.07, 0.10)   # Dark studio navy
        scene.ambient    = color.gray(0.42)
        # Shift camera slightly to left and back to comfortably frame the info panel
        # on the far left, the unobstructed coil center, and the benchtop galvanometer
        scene.camera.pos  = _v(-0.6, 0.35, 5.8)
        scene.camera.axis = _v(0.0, -0.12, -5.8)

    # =========================================================================
    # 2. CONDUCTING COIL (SOLENOID)
    # =========================================================================
    def _build_conducting_coil(self):
        """
        Hollow solenoid constructed with individual copper ring() objects.
        The hollow center is completely open and unobstructed so the magnet's
        entry into the coil is fully visible.
        """
        cx = self.COIL_X
        cy = self.COIL_Y
        r  = self.COIL_RADIUS
        L  = self.COIL_SPAN

        # Hollow acrylic bobbin supporting the rings
        self.coil_bobbin = cylinder(
            pos     = _v(cx - L/2 - 0.03, cy, 0),
            axis    = _v(L + 0.06, 0, 0),
            radius  = r * 1.02,
            color   = _v(0.22, 0.28, 0.38),
            opacity = 0.16
        )

        # Multi-turn copper rings
        self.coil_rings = []
        ring_xs = np.linspace(cx - L/2, cx + L/2, self.NUM_RINGS)
        for rx in ring_xs:
            rng = ring(
                pos       = _v(rx, cy, 0),
                axis      = _v(1, 0, 0),
                radius    = r,
                thickness = 0.036,
                color     = _v(0.88, 0.50, 0.18),   # Copper
                opacity   = 0.95
            )
            self.coil_rings.append(rng)

        # Wire leads dropping down from solenoid ends
        self.lead_left = cylinder(
            pos    = _v(cx - L/2, cy - r, 0),
            axis   = _v(0, -0.22, 0),
            radius = 0.022,
            color  = _v(0.88, 0.50, 0.18)
        )
        self.lead_right = cylinder(
            pos    = _v(cx + L/2, cy - r, 0),
            axis   = _v(0, -0.22, 0),
            radius = 0.022,
            color  = _v(0.88, 0.50, 0.18)
        )

    # =========================================================================
    # 3. BAR MAGNET
    # =========================================================================
    def _build_bar_magnet(self):
        """
        Rectangular bar magnet with Red North pole (facing coil), Blue South pole,
        visible N/S labels, and yellow velocity arrow.
        """
        cy = self.COIL_Y
        pl = self.MAG_POLE_LEN
        h  = self.MAG_HEIGHT
        d  = self.MAG_DEPTH

        # North pole (Red) on left — faces coil
        self.mag_N = box(
            pos     = _v(self.mag_x - pl/2, cy, 0),
            size    = _v(pl, h, d),
            color   = _v(0.92, 0.15, 0.15),
            opacity = 0.95
        )
        # South pole (Blue) on right
        self.mag_S = box(
            pos     = _v(self.mag_x + pl/2, cy, 0),
            size    = _v(pl, h, d),
            color   = _v(0.15, 0.48, 0.95),
            opacity = 0.95
        )

        # Labels "N" and "S"
        self.lbl_N = label(
            pos     = _v(self.mag_x - pl/2, cy, d/2 + 0.04),
            text    = "N",
            color   = color.white,
            height  = 16,
            box     = False
        )
        self.lbl_S = label(
            pos     = _v(self.mag_x + pl/2, cy, d/2 + 0.04),
            text    = "S",
            color   = color.white,
            height  = 16,
            box     = False
        )

        # Yellow motion arrow ("MAGNET MOTION")
        self.vel_arrow = arrow(
            pos        = _v(self.mag_x, cy - h/2 - 0.18, 0),
            axis       = _v(0, 0, 0),
            color      = _v(1.0, 0.90, 0.15),
            shaftwidth = 0.034,
            visible    = False
        )
        self.vel_label = label(
            pos     = _v(self.mag_x, cy - h/2 - 0.32, 0),
            text    = "MAGNET MOTION",
            color   = _v(1.0, 0.90, 0.15),
            height  = 10,
            box     = False,
            visible = False
        )

    # =========================================================================
    # 4. MAGNETIC FIELD LINES (AROUND BAR MAGNET)
    # =========================================================================
    def _build_magnetic_field_lines(self):
        """
        Creates curved field lines arching between North and South poles,
        plus axial field arrows extending toward and through the coil.
        """
        cy = self.COIL_Y
        self.field_curves = []
        self.field_templates = []

        loop_radii = [0.45, 0.82]
        for lr in loop_radii:
            for sign_y in [1.0, -1.0]:
                n_pts = 34
                t_vals = np.linspace(0.08, np.pi - 0.08, n_pts)
                xs = -self.MAG_POLE_LEN * np.cos(t_vals)
                ys = sign_y * (self.MAG_HEIGHT/2 + lr * np.sin(t_vals))
                c = curve(color=_v(0.18, 0.70, 0.98), radius=0.012, opacity=0.65)
                self.field_curves.append(c)
                self.field_templates.append((xs, ys, sign_y))

        # Direction arrows on loops
        self.field_arrows = []
        for _, ys, sign_y in self.field_templates:
            mid_y = ys[len(ys)//2]
            a = arrow(
                pos        = _v(self.mag_x, cy + mid_y, 0),
                axis       = _v(0.18, 0, 0),
                color      = _v(0.25, 0.85, 1.0),
                shaftwidth = 0.016,
                opacity    = 0.75
            )
            self.field_arrows.append((a, mid_y))

        # Axial field arrows penetrating the coil
        self.axial_arrows = []
        axial_offsets = np.linspace(-0.85, -0.15, 5)
        for off in axial_offsets:
            a = arrow(
                pos        = _v(self.mag_x - self.MAG_POLE_LEN + off, cy, 0),
                axis       = _v(-0.25, 0, 0),
                color      = _v(0.25, 0.85, 1.0),
                shaftwidth = 0.022,
                opacity    = 0.85
            )
            self.axial_arrows.append((a, off))

    # =========================================================================
    # 5. BENCHTOP ANALOG GALVANOMETER
    # =========================================================================
    def _build_galvanometer(self):
        """
        Benchtop analog galvanometer with:
          • Wooden stand block
          • Dark meter casing
          • White dial face with center zero and ± scale
          • Dynamically controlled red needle
          • Center pivot
          • Red and black binding terminals
        """
        gx = self.GALV_X
        gy = self.GALV_Y
        gz = self.GALV_Z

        # 1. Wooden pedestal block
        box(
            pos   = _v(gx, gy - 0.54, gz),
            size  = _v(1.08, 0.50, 0.78),
            color = _v(0.72, 0.54, 0.34)
        )

        # 2. Main meter body
        box(
            pos   = _v(gx, gy - 0.08, gz),
            size  = _v(0.90, 0.74, 0.52),
            color = _v(0.18, 0.20, 0.24)
        )

        # 3. Dial face (white recessed meter plate)
        box(
            pos   = _v(gx, gy + 0.11, gz + 0.262),
            size  = _v(0.76, 0.44, 0.02),
            color = _v(0.95, 0.95, 0.96)
        )

        # 4. Dial scale markings (-5 to +5 around 0)
        center_y = gy - 0.02
        meter_r  = 0.29
        scale_angles = np.linspace(-45, 45, 11)
        for i, deg in enumerate(scale_angles):
            rad = np.deg2rad(deg)
            is_zero = (i == 5)
            t_len = 0.046 if (i % 2 == 1 or is_zero) else 0.026
            p1 = _v(gx + (meter_r - t_len) * np.sin(rad),
                    center_y + (meter_r - t_len) * np.cos(rad),
                    gz + 0.275)
            p2 = _v(gx + meter_r * np.sin(rad),
                    center_y + meter_r * np.cos(rad),
                    gz + 0.275)
            curve(pos=[p1, p2], radius=0.005, color=_v(0.12, 0.14, 0.18))

        # "0" marking at center
        label(pos=_v(gx, center_y + meter_r + 0.04, gz + 0.28), text="0", color=_v(0.1, 0.1, 0.15), height=10, box=False)
        label(pos=_v(gx - 0.26, center_y + 0.18, gz + 0.28), text="−", color=_v(0.1, 0.1, 0.15), height=14, box=False)
        label(pos=_v(gx + 0.26, center_y + 0.18, gz + 0.28), text="+", color=_v(0.1, 0.1, 0.15), height=14, box=False)
        label(pos=_v(gx, center_y + 0.05, gz + 0.28), text="G", color=_v(0.15, 0.25, 0.6), height=15, box=False)

        cylinder(pos=_v(gx, center_y, gz + 0.265), axis=_v(0, 0, 0.028), radius=0.022, color=_v(0.25, 0.25, 0.3))

        # 5. Dynamically controlled red needle
        self.needle_len   = 0.26
        self.needle_pivot = _v(gx, center_y, gz + 0.285)
        self.galv_needle  = arrow(
            pos        = self.needle_pivot,
            axis       = _v(0, self.needle_len, 0),   # Upright at 0
            color      = _v(0.95, 0.15, 0.15),        # Red needle
            shaftwidth = 0.014,
            headwidth  = 0.032,
            headlength = 0.050
        )

        # 6. Lower panel with yellow badge
        box(pos=_v(gx, gy - 0.26, gz + 0.262), size=_v(0.76, 0.22, 0.02), color=_v(0.40, 0.18, 0.14))
        label(pos=_v(gx, gy - 0.26, gz + 0.28), text="A", color=_v(1.0, 0.85, 0.2), height=13, box=False)

        # 7. Red (left) and Black (right) binding post terminals
        self.term_left_pos  = _v(gx - 0.25, gy - 0.26, gz + 0.26)
        self.term_right_pos = _v(gx + 0.25, gy - 0.26, gz + 0.26)
        cylinder(pos=self.term_left_pos, axis=_v(0, 0, 0.07), radius=0.026, color=_v(0.85, 0.15, 0.15))
        cylinder(pos=self.term_right_pos, axis=_v(0, 0, 0.07), radius=0.026, color=_v(0.14, 0.15, 0.18))

    # =========================================================================
    # 6. CONNECTING WIRES (CLOSED ELECTRICAL CIRCUIT)
    # =========================================================================
    def _build_connecting_wires(self):
        """
        Creates two visible light cyan-blue 3D insulated wires linking coil to meter.
        """
        cx = self.COIL_X
        cy = self.COIL_Y
        r  = self.COIL_RADIUS
        L  = self.COIL_SPAN
        wire_color = _v(0.20, 0.65, 1.0)
        wire_rad   = 0.018

        # Left wire: Left coil lead -> left (red) binding post
        left_pts = [
            _v(cx - L/2, cy - r - 0.22, 0),
            _v(cx - L/2 - 0.05, cy - r - 0.65, 0.1),
            _v(cx - L/2 - 0.18, self.GALV_Y + 0.15, 0.2),
            _v(cx - L/2 - 0.12, self.GALV_Y - 0.26, 0.3),
            _v(self.term_left_pos.x - 0.20, self.GALV_Y - 0.28, 0.3),
            _v(self.term_left_pos.x, self.term_left_pos.y, self.term_left_pos.z + 0.07)
        ]
        self.wire_left = curve(pos=left_pts, radius=wire_rad, color=wire_color)

        # Right wire now goes THROUGH A LAMP (series circuit):
        #   coil right lead -> LAMP -> galvanometer right (black) post
        # Lamp socket position (world units). Placed below/right of the magnet's path.
        BX, BY = 1.20, -1.15
        self.lamp_pos = _v(BX, BY, 0)
        lamp_tl = _v(BX - 0.16, BY + 0.05, 0.05)    # lamp left terminal
        lamp_tr = _v(BX + 0.16, BY + 0.05, 0.05)    # lamp right terminal

        right_pts_1 = [
            _v(cx + L/2, cy - r - 0.22, 0),
            _v(cx + L/2 + 0.16, cy - r - 0.50, 0.1),
            _v(0.50, -0.45, 0.15),
            _v(BX - 0.40, BY + 0.20, 0.10),
            _v(BX - 0.22, BY + 0.05, 0.05),
            lamp_tl
        ]
        self.wire_right = curve(pos=right_pts_1, radius=wire_rad, color=wire_color)

        right_pts_2 = [
            lamp_tr,
            _v(BX + 0.22, BY + 0.05, 0.05),
            _v(BX + 0.40, BY - 0.15, 0.20),
            _v(BX + 0.40, self.GALV_Y - 0.26, 0.30),
            _v(self.term_right_pos.x + 0.18, self.GALV_Y - 0.26, 0.30),
            _v(self.term_right_pos.x, self.term_right_pos.y, self.term_right_pos.z + 0.07)
        ]
        self.wire_right2 = curve(pos=right_pts_2, radius=wire_rad, color=wire_color)

        # Closed loop path used by the moving charge dots (clockwise as seen from the front):
        #   through coil (left->right) -> right wire -> lamp -> galvanometer -> left wire -> back
        loop = []
        loop.append(_v(cx - L/2, cy - r - 0.22, 0))
        loop.append(_v(cx - L/2, cy - r, 0))               # up into the coil winding
        loop.append(_v(cx + L/2, cy - r, 0))               # along the winding
        loop += right_pts_1                                # right wire to lamp
        loop.append(_v(BX, BY + 0.14, 0.05))               # through the lamp filament base
        loop += right_pts_2                                # lamp to galvanometer
        loop.append(_v(self.term_left_pos.x, self.term_left_pos.y, self.term_left_pos.z + 0.07))
        loop += list(reversed(left_pts))                   # left wire back up to the coil
        self._build_lamp_and_flow(loop, BX, BY)

    # =========================================================================
    # 7B. LAMP (series load) + MOVING CHARGE DOTS  -> makes the current visible
    # =========================================================================
    # WHY: the needle shows the current only as an angle. A lamp that glows and
    # dots that flow around the wires let everyone SEE that a current exists.
    #   * Lamp brightness follows POWER  P = I^2 * R  (so it glows for BOTH
    #     directions of current - the needle shows the direction, the lamp does not).
    #   * Dot SPEED is proportional to |I|; dot DIRECTION flips with the sign of I
    #     (Lenz's Law). Dots are hidden when I ~ 0 (magnet stopped / far away).
    LAMP_P_REF   = 0.06       # power [W] that gives full brightness (peak is ~0.08 W)
    FLOW_DOTS    = 26         # number of moving charge dots
    FLOW_GAIN    = 6.0        # path-units per second per ampere

    def _build_lamp_and_flow(self, loop_pts, BX, BY):
        # --- lamp socket / base (metal screw base)
        cylinder(pos=_v(BX, BY, 0), axis=_v(0, 0.16, 0), radius=0.10, color=_v(0.55, 0.55, 0.58))
        cylinder(pos=_v(BX, BY + 0.16, 0), axis=_v(0, 0.06, 0), radius=0.085, color=_v(0.30, 0.30, 0.33))
        cylinder(pos=_v(BX - 0.16, BY + 0.05, 0.05), axis=_v(0.07, 0, 0), radius=0.022, color=_v(0.85, 0.15, 0.15))
        cylinder(pos=_v(BX + 0.09, BY + 0.05, 0.05), axis=_v(0.07, 0, 0), radius=0.022, color=_v(0.14, 0.15, 0.18))

        # --- glass bulb
        self.bulb_center = _v(BX, BY + 0.50, 0)
        self.bulb_glass = sphere(pos=self.bulb_center, radius=0.27,
                                 color=_v(0.80, 0.86, 0.92), opacity=0.28)
        # --- filament (zig-zag wire inside the glass)
        fx, fy = BX, BY + 0.40
        fil = [_v(fx - 0.09, fy, 0), _v(fx - 0.06, fy + 0.12, 0), _v(fx - 0.03, fy, 0),
               _v(fx, fy + 0.12, 0), _v(fx + 0.03, fy, 0), _v(fx + 0.06, fy + 0.12, 0),
               _v(fx + 0.09, fy, 0)]
        self.bulb_filament = curve(pos=fil, radius=0.012, color=_v(0.30, 0.25, 0.20))
        # support posts from base to filament
        cylinder(pos=_v(fx - 0.09, BY + 0.22, 0), axis=_v(0, 0.18, 0), radius=0.008, color=_v(0.6, 0.6, 0.6))
        cylinder(pos=_v(fx + 0.09, BY + 0.22, 0), axis=_v(0, 0.18, 0), radius=0.008, color=_v(0.6, 0.6, 0.6))

        # --- soft glow halo (visible only when lit)
        self.bulb_halo = sphere(pos=self.bulb_center, radius=0.62,
                                color=_v(1.0, 0.85, 0.35), opacity=0.0)
        self.bulb_halo.visible = False

        # --- optional real light source so the lamp lights up nearby objects
        self.lamp_light = None
        try:
            from vpython import local_light
            self.lamp_light = local_light(pos=_v(BX, BY + 0.5, 0.6), color=_v(0, 0, 0))
        except Exception:
            self.lamp_light = None

        # --- labels
        label(pos=_v(BX, BY + 1.12, 0), text="LAMP (in series with the coil)",
              color=_v(1.0, 0.85, 0.35), height=11, border=4, box=True,
              background=_v(0.08, 0.11, 0.18), opacity=0.85, align="center")
        self.lbl_lamp = label(pos=_v(BX, BY - 0.28, 0.1), text="LAMP OFF  (0%)",
                              color=_v(0.80, 0.85, 0.95), height=11, border=4, box=True,
                              background=_v(0.08, 0.11, 0.18), opacity=0.85, align="center")

        # --- moving charge dots along the closed loop
        pts = [(p.x, p.y, p.z) for p in loop_pts]
        arr = np.array(pts, dtype=float)
        seg = np.linalg.norm(np.diff(arr, axis=0), axis=1)
        self._flow_pts = arr
        self._flow_cum = np.concatenate([[0.0], np.cumsum(seg)])
        self._flow_len = float(self._flow_cum[-1])
        self.flow_dots = [sphere(pos=_v(*arr[0]), radius=0.032, color=_v(0.95, 0.95, 0.95))
                          for _ in range(self.FLOW_DOTS)]
        for d in self.flow_dots:
            d.visible = False

    def _flow_position(self, s_pos):
        """Point on the closed loop at arc-length s_pos (wraps around)."""
        s_pos = s_pos % self._flow_len
        i = int(np.searchsorted(self._flow_cum, s_pos, side="right") - 1)
        i = max(0, min(i, len(self._flow_pts) - 2))
        seg_len = self._flow_cum[i + 1] - self._flow_cum[i]
        f = 0.0 if seg_len < 1e-9 else (s_pos - self._flow_cum[i]) / seg_len
        p = self._flow_pts[i] + f * (self._flow_pts[i + 1] - self._flow_pts[i])
        return _v(p[0], p[1], p[2])

    def _update_lamp_and_flow(self):
        """Called every frame: lamp brightness from P = I^2 R, dots speed/direction from I."""
        if not hasattr(self, "flow_dots"):
            return
        I = self.curr_val
        R = self.physics.coil_resistance
        self.lamp_power = I * I * R                       # electrical power  P = I^2 R [W]
        target = min(1.0, self.lamp_power / self.LAMP_P_REF)
        if self.running:
            # filament inertia: brightness rises instantly but fades slowly
            self.lamp_level = max(target, self.lamp_level * 0.93)
        b = self.lamp_level

        # filament + glass + halo + light
        self.bulb_filament.color = _v(0.30 + 0.70 * b, 0.25 + 0.60 * b, 0.20 + 0.20 * b)
        self.bulb_glass.color = _v(0.80 + 0.20 * b, 0.86 + 0.10 * b, 0.92 - 0.45 * b)
        self.bulb_glass.opacity = 0.28 + 0.40 * b
        lit = b > 0.04
        self.bulb_halo.visible = lit
        if lit:
            self.bulb_halo.opacity = 0.10 + 0.30 * b
            self.bulb_halo.radius = 0.45 + 0.35 * b
        if self.lamp_light is not None:
            self.lamp_light.color = _v(1.0 * b, 0.85 * b, 0.4 * b)

        pct = int(round(100 * b))
        txt = (f"LAMP {pct}%   P = I²R = {self.lamp_power * 1000:.0f} mW"
               if lit else "LAMP OFF  (no current)")
        if txt != self.lbl_lamp.text:
            self.lbl_lamp.text = txt
            self.lbl_lamp.color = _v(1.0, 0.9, 0.4) if lit else _v(0.80, 0.85, 0.95)

        # charge dots: speed ~ |I|, direction flips with the sign of I (Lenz)
        active = abs(I) > 0.004
        if self.running:
            # negative I (magnet approaching, "clockwise") moves dots forward along the loop
            self.flow_phase += (-I) * self.FLOW_GAIN * self.dt
        spacing = self._flow_len / len(self.flow_dots)
        col = _v(0.20, 0.95, 0.35) if I > 0 else _v(0.95, 0.30, 0.95)
        for k, d in enumerate(self.flow_dots):
            d.visible = active
            if active:
                d.pos = self._flow_position(self.flow_phase + k * spacing)
                d.color = col

    # (end of lamp section)
    # =========================================================================
    # 7. LENZ'S LAW INDUCED CURRENT ARROWS
    # =========================================================================
    def _build_lenz_current_arrows(self):
        """
        Tangential arrows around coil circumference indicating direction of induced current.
        """
        self.lenz_arrows = []
        angles = [0, np.pi/2, np.pi, 3*np.pi/2]
        r = self.COIL_RADIUS * 1.15
        cx = self.COIL_X
        cy = self.COIL_Y

        for ang in angles:
            y0 = cy + r * np.sin(ang)
            z0 = r * np.cos(ang)
            a = arrow(
                pos        = _v(cx, y0, z0),
                axis       = _v(0, 0.18, 0),
                color      = _v(1.0, 0.95, 0.2),
                shaftwidth = 0.026,
                visible    = False
            )
            self.lenz_arrows.append((a, ang))

    # =========================================================================
    # 8. LABORATORY LABELS
    # =========================================================================
    def _build_laboratory_labels(self):
        # "CONDUCTING COIL" placed safely above coil
        label(
            pos        = _v(self.COIL_X, self.COIL_Y + self.COIL_RADIUS + 0.32, 0),
            text       = "CONDUCTING COIL",
            color      = _v(1.0, 0.75, 0.35),
            height     = 12,
            border     = 6,
            background = _v(0.12, 0.15, 0.22),
            box        = True
        )

        # "GALVANOMETER"
        label(
            pos        = _v(self.GALV_X, self.GALV_Y - 0.88, 0),
            text       = "GALVANOMETER",
            color      = color.white,
            height     = 12,
            border     = 6,
            background = _v(0.12, 0.15, 0.22),
            box        = True
        )

        # "BAR MAGNET"
        self.lbl_bar_mag = label(
            pos        = _v(self.mag_x, self.COIL_Y + self.MAG_HEIGHT/2 + 0.28, 0),
            text       = "BAR MAGNET",
            color      = color.white,
            height     = 11,
            background = _v(0.12, 0.15, 0.22),
            box        = True
        )

        # "MAGNETIC FIELD"
        self.lbl_b_field = label(
            pos        = _v(self.mag_x, self.COIL_Y + self.MAG_HEIGHT/2 + 0.95, 0),
            text       = "MAGNETIC FIELD",
            color      = _v(0.3, 0.85, 1.0),
            height     = 10,
            box        = False
        )

        # "INDUCED CURRENT" indicator
        self.lbl_induced_curr = label(
            pos        = _v(self.COIL_X, self.COIL_Y - self.COIL_RADIUS - 0.32, 0),
            text       = "INDUCED CURRENT: 0 A",
            color      = _v(0.8, 0.85, 0.9),
            height     = 10,
            box        = False
        )

        # "EMF" badge
        self.lbl_emf_badge = label(
            pos        = _v(self.COIL_X + self.COIL_SPAN/2 + 0.35, self.COIL_Y + 0.40, 0),
            text       = "EMF = 0.00 V",
            color      = _v(0.95, 0.4, 0.4),
            height     = 10,
            box        = False
        )

    # =========================================================================
    # 9. REAL-TIME NUMERICAL INFORMATION PANEL (ON FAR LEFT OF COIL)
    # =========================================================================
    def _build_info_panel(self):
        """
        Positioned at far left, BELOW the magnet's path (x = -4.10, y = -0.15) so the
        magnet can travel all the way through the coil and out the left side without
        passing behind the panel.
        """
        self.info_panel = label(
            pos        = _v(-4.10, -0.15, 0),
            text       = self._generate_info_text(),
            color      = color.white,
            height     = 10,
            border     = 8,
            background = _v(0.08, 0.11, 0.18),
            opacity    = 0.92,
            box        = True,
            align      = "left"
        )

    def _generate_info_text(self):
        phys_pos = self.mag_x * WORLD_TO_METERS
        phys_vel = self.mag_vel * WORLD_TO_METERS
        return (
            "ELECTROMAGNETIC INDUCTION\n"
            f"  Magnet Position:        {phys_pos:6.3f} m\n"
            f"  Magnet Velocity:        {phys_vel:6.3f} m/s\n"
            f"  Magnetic Field:         {self.B_val:6.4f} T\n"
            f"  Coil Area:              {self.physics.coil_area:6.4f} m²\n"
            f"  Number of Turns:        {self.physics.coil_turns:4d}\n"
            f"  Magnetic Flux:          {self.flux_val:8.5f} Wb\n"
            f"  dΦ/dt:                  {self.dphi_val:8.4f} Wb/s\n"
            f"  Induced EMF:            {self.emf_val:8.4f} V\n"
            f"  Current:                {self.curr_val:8.4f} A\n"
            f"  Galvanometer Deflection:{self.needle_deg:6.1f} deg\n"
            f"  Current Direction:      {self.physics.get_current_direction_text(self.curr_val)}"
        )

    # =========================================================================
    # 10. INTERACTIVE USER CONTROLS
    # =========================================================================
    def _build_controls(self):
        scene.append_to_caption("\n\n")

        self.btn_play = button(
            text       = "▶ PLAY",
            color      = color.green,
            background = _v(0.14, 0.20, 0.28),
            bind       = self._cb_play
        )
        scene.append_to_caption("   ")
        self.btn_pause = button(
            text       = "⏸ PAUSE",
            color      = color.yellow,
            background = _v(0.14, 0.20, 0.28),
            bind       = lambda b: setattr(self, 'running', False)
        )
        scene.append_to_caption("   ")
        self.btn_reset = button(
            text       = "⟳ RESET",
            color      = color.red,
            background = _v(0.14, 0.20, 0.28),
            bind       = self._cb_reset
        )
        scene.append_to_caption("   ")
        self.btn_reverse = button(
            text       = "⇄ REVERSE DIRECTION",
            color      = _v(1.0, 0.70, 0.2),
            background = _v(0.14, 0.20, 0.28),
            bind       = self._cb_reverse
        )
        scene.append_to_caption("   ")
        self.btn_mode = button(
            text       = self._mode_button_text(),
            color      = _v(0.55, 0.95, 0.55),
            background = _v(0.14, 0.20, 0.28),
            bind       = self._cb_mode
        )
        scene.append_to_caption("\n\n")

        scene.append_to_caption("<b>Magnet Speed:</b> Slow ")
        self.sl_speed = slider(min=0.2, max=3.5, value=1.0, step=0.1, length=200, bind=self._cb_speed)
        scene.append_to_caption(" Fast ")
        self.wt_speed = wtext(text=f"({self.speed:.1f}x)")

        scene.append_to_caption("      ")

        scene.append_to_caption("<b>Coil Turns (N):</b> ")
        self.sl_turns = slider(min=5, max=50, value=self.physics.coil_turns, step=1, length=180, bind=self._cb_turns)
        self.wt_turns = wtext(text=f"({self.physics.coil_turns})")

        scene.append_to_caption("      ")

        scene.append_to_caption("<b>Magnet Strength:</b> ")
        self.sl_field = slider(min=0.2, max=3.0, value=1.0, step=0.1, length=180, bind=self._cb_field)
        self.wt_field = wtext(text="(1.0x)")

        scene.append_to_caption("\n<span style='color:#94a3b8; font-size:12px;'>")
        scene.append_to_caption(
            "<b>Physics Verification:</b> Moving Magnet &rarr; Changing Flux &rarr; "
            "Induced EMF (Faraday: &Epsilon; = &minus;N d&Phi;/dt) &rarr; "
            "Induced Current (Lenz) &rarr; Galvanometer Needle Deflects (live graphs on the right)."
        )
        scene.append_to_caption("</span>\n")

    # -------------------------------------------------------------------------
    # Control Callbacks (Thread-Safe: only set state flags)
    # -------------------------------------------------------------------------
    def _cb_play(self, b):
        # THREAD SAFETY: button callbacks run in another thread, so they only set
        # flags. The main loop (run) does the real work. This fixed the Tkinter crash.
        self.running = True

    def _cb_mode(self, b):
        # Thread-safe: only post a request; run() applies it on the main thread.
        self.request_mode = not self.pass_through

    def _mode_button_text(self):
        return ("MODE: PASS THROUGH  (click for bounce)" if self.pass_through
                else "MODE: BOUNCE  (click for pass through)")

    def _set_mode(self, pass_through, reset=True):
        """
        Switch between the two motion modes.
          PASS-THROUGH : magnet goes in one side of the coil and straight out the other.
          BOUNCE       : magnet goes in and comes back out the same side (original demo).
        The physics engine switches model too, because a magnet that passes through the
        coil makes the field through it REVERSE direction (needs a signed flux).
        """
        self.pass_through         = bool(pass_through)
        self.physics.pass_through = self.pass_through
        x_end = self.MAG_X_PASS_END if self.pass_through else self.MAG_X_NEAR
        self.osc_amp   = (self.MAG_X_FAR - x_end) / 2.0
        self.osc_mid   = (self.MAG_X_FAR + x_end) / 2.0
        self.osc_omega = self.PASS_OMEGA if self.pass_through else self.BOUNCE_OMEGA
        if hasattr(self, "btn_mode"):
            self.btn_mode.text = self._mode_button_text()
        if reset and hasattr(self, "info_panel"):
            self._cb_reset(None)

    def _cb_reset(self, b):
        self.running     = False
        self.sim_time    = 0.0
        self.real_time   = 0.0     # FIX: also reset real time
        self.mag_x       = self.MAG_X_FAR
        self.mag_vel     = 0.0
        self.motion_dir  = 1.0
        self.phase       = 0.0

        self.physics.reset()
        self.B_val      = self.physics.compute_B_field(self.mag_x, self.COIL_X)
        self.flux_val   = self.physics.compute_flux(self.B_val)
        self.emf_val    = 0.0
        self.dphi_val   = 0.0
        self.curr_val   = 0.0
        self.needle_deg = 0.0
        self.lamp_level = 0.0      # lamp off after reset
        if hasattr(self, "graphs"):
            self.graphs.clear()    # wipe the live graphs
        self.flow_phase = 0.0

        self._update_all_visuals()

    def _cb_reverse(self, b):
        # motion_dir = +1 / -1 makes the phase run forwards / backwards, so the
        # magnet reverses -> dPhi/dt changes sign -> EMF & current reverse.
        self.motion_dir *= -1.0

    def _cb_speed(self, s):
        # Speed slider (0.2x-3.5x): scales how fast animation time advances.
        # Faster motion -> larger |dPhi/dt| -> larger EMF (EMF is proportional to speed).
        self.speed = float(s.value)
        self.wt_speed.text = f"({self.speed:.1f}x)"

    def _cb_turns(self, s):
        # Coil Turns slider (5-50): EMF = -N dPhi/dt, so EMF is proportional to N.
        turns = int(s.value)
        self.physics.set_coil_turns(turns)
        self.wt_turns.text = f"({turns})"

    def _cb_field(self, s):
        # Magnet Strength slider: scales pole strength q_m -> scales B, Phi, EMF.
        val = float(s.value)
        self.physics.set_magnet_strength(val)
        self.wt_field.text = f"({val:.1f}x)"

    # =========================================================================
    # 11. VISUAL REFRESH ROUTINES
    # =========================================================================
    def _update_magnet_visuals(self):
        pl, cy, d = self.MAG_POLE_LEN, self.COIL_Y, self.MAG_DEPTH

        self.mag_N.pos = _v(self.mag_x - pl/2, cy, 0)
        self.mag_S.pos = _v(self.mag_x + pl/2, cy, 0)
        self.lbl_N.pos = _v(self.mag_x - pl/2, cy, d/2 + 0.04)
        self.lbl_S.pos = _v(self.mag_x + pl/2, cy, d/2 + 0.04)
        self.lbl_bar_mag.pos = _v(self.mag_x, cy + self.MAG_HEIGHT/2 + 0.28, 0)

        is_moving = abs(self.mag_vel) > 0.015
        self.vel_arrow.visible = is_moving
        self.vel_label.visible = is_moving
        if is_moving:
            v_len = np.clip(self.mag_vel * 0.40, -0.65, 0.65)
            self.vel_arrow.pos  = _v(self.mag_x, cy - self.MAG_HEIGHT/2 - 0.18, 0)
            self.vel_arrow.axis = _v(v_len, 0, 0)
            self.vel_label.pos  = _v(self.mag_x + v_len + (0.16 if v_len >= 0 else -0.16),
                                     cy - self.MAG_HEIGHT/2 - 0.18, 0)

    def _update_field_visuals(self):
        cy = self.COIL_Y

        for c, (xs, ys, sign_y) in zip(self.field_curves, self.field_templates):
            pts = [_v(self.mag_x + x, cy + y, 0) for x, y in zip(xs, ys)]
            c.clear()
            for pt in pts:
                c.append(pt)

        for arr, mid_y in self.field_arrows:
            arr.pos  = _v(self.mag_x, cy + mid_y, 0)
            arr.axis = _v(0.18, 0, 0)

        for a, off in self.axial_arrows:
            a.pos = _v(self.mag_x - self.MAG_POLE_LEN + off, cy, 0)
            b_norm = min(abs(self.B_val) / (0.1 if self.pass_through else 0.4), 1.0)
            a.shaftwidth = float(0.018 + 0.014 * b_norm)

        self.lbl_b_field.pos = _v(self.mag_x, cy + self.MAG_HEIGHT/2 + 0.95, 0)

    def _update_galvanometer_needle(self):
        """
        Dynamically drives the galvanometer needle based on the CALCULATED
        induced current. Strong, clearly visible deflection (±25° to ±45°).
        """
        # needle_deg comes from physics.py (k*I, clamped +-50 deg). Convert to a
        # direction vector: sin -> horizontal swing, cos -> vertical.
        angle_rad = np.deg2rad(self.needle_deg)
        nx = self.needle_len * np.sin(angle_rad)
        ny = self.needle_len * np.cos(angle_rad)
        self.galv_needle.axis = _v(nx, ny, 0)

        # Dynamic needle coloring
        if abs(self.needle_deg) < 1.0:
            self.galv_needle.color = _v(0.95, 0.15, 0.15)
        elif self.needle_deg > 0:
            self.galv_needle.color = _v(0.20, 0.90, 0.35)   # Green for positive deflection (right)
        else:
            self.galv_needle.color = _v(0.95, 0.20, 0.95)   # Magenta for negative deflection (left)

    def _update_lenz_current_visuals(self):
        # LENZ'S LAW VISUAL: arrows around the coil flip direction with the sign
        # of the induced current (approach = counterclockwise seen from the right,
        # retreat = clockwise seen from the right).
        active = abs(self.curr_val) > 1e-4
        sign = 1 if self.curr_val >= 0 else -1
        cy = self.COIL_Y

        for a, ang in self.lenz_arrows:
            a.visible = active
            if active:
                # I < 0 (N pole approaching) must circulate COUNTERCLOCKWISE seen from the
                # right (magnet side) so the coil's right face is a North pole and repels it.
                ay =  sign * np.cos(ang) * 0.18
                az = -sign * np.sin(ang) * 0.18
                a.axis = _v(0, ay, az)
                a.color = _v(0.2, 0.9, 0.3) if sign > 0 else _v(0.95, 0.2, 0.95)

        if active:
            ring_glow = _v(1.0, 0.70, 0.28) if sign > 0 else _v(1.0, 0.45, 0.65)
            for rng in self.coil_rings:
                rng.color = ring_glow
        else:
            for rng in self.coil_rings:
                rng.color = _v(0.88, 0.50, 0.18)

        dir_text = self.physics.get_current_direction_text(self.curr_val)
        self.lbl_induced_curr.text = f"INDUCED CURRENT: {self.curr_val:+.3f} A ({dir_text})"
        self.lbl_emf_badge.text = f"EMF = {self.emf_val:+.3f} V"

    def _update_all_visuals(self):
        self._update_magnet_visuals()
        self._update_field_visuals()
        self._update_galvanometer_needle()
        self._update_lenz_current_visuals()
        self.info_panel.text = self._generate_info_text()
        self._update_lamp_and_flow()
        self._update_presenter()


    # =========================================================================
    # 11B. PRESENTATION / TEACHING MODE  (explanations INSIDE the simulation)
    # =========================================================================
    # Three tools to help the professor follow:
    #   (1) BANNER   - big text above the coil that says, in plain words, what
    #                  is happening right now (approaching / stopped / retreating)
    #   (2) LESSON   - an explanation box under the controls. In LIVE mode it
    #                  explains the current situation; in TOUR mode it shows
    #                  slide-by-slide teaching steps.
    #   (3) LIVE MATH- the equations with the CURRENT numbers plugged in, e.g.
    #                  EMF = -N x dPhi/dt = -20 x (+0.0199) = -0.398 V
    #
    # Banner colors: magenta = approach (negative), green = retreat (positive).

    # Live-mode banner text, keyed by physical state: (title, subtitle, color)
    STATE_BANNER = {
        "READY":      ("READY - press PLAY (or START GUIDED TOUR)", "",
                       (0.80, 0.85, 0.95)),
        "APPROACH":   ("MAGNET APPROACHING  ->  flux increasing  ->  EMF negative  ->  needle LEFT",
                       "Lenz's Law: the coil opposes the increase in flux",
                       (0.95, 0.35, 0.95)),
        "TURNAROUND": ("MAGNET MOMENTARILY STOPPED  ->  flux NOT changing  ->  EMF = 0",
                       "B is at its maximum, but induction needs a CHANGE in flux",
                       (1.00, 0.85, 0.30)),
        "RETREAT":    ("MAGNET MOVING AWAY  ->  flux decreasing  ->  EMF positive  ->  needle RIGHT",
                       "Current REVERSES: the coil now opposes the decrease in flux",
                       (0.30, 0.95, 0.45)),
        "REST":       ("MAGNET FAR AWAY  ->  field at coil is tiny and barely changing  ->  EMF ~ 0",
                       "No (or very little) change in flux = no (or very little) induced current",
                       (0.80, 0.85, 0.95)),
    }

    # Same, for PASS-THROUGH mode.  The states are named by what the FLUX is doing
    # (not by where the magnet is), because with a magnet going through the coil the
    # flux rises, falls, reverses and rises again.
    PT_STATE_BANNER = {
        "READY":      ("READY - press PLAY: the magnet will pass THROUGH the coil", "",
                       (0.80, 0.85, 0.95)),
        "APPROACH":   ("FLUX INCREASING  ->  EMF negative  ->  needle LEFT",
                       "Lenz's Law: the induced current opposes the change in flux",
                       (0.95, 0.35, 0.95)),
        "TURNAROUND": ("FLUX STEADY  ->  EMF = 0  (magnet body is inside the coil)",
                       "Strong field, but it is not CHANGING, so there is no induced EMF",
                       (1.00, 0.85, 0.30)),
        "RETREAT":    ("FLUX DECREASING  ->  EMF positive  ->  needle RIGHT",
                       "Current REVERSES - this includes the N pole crossing the coil, where B through the coil flips direction",
                       (0.30, 0.95, 0.45)),
        "REST":       ("MAGNET FAR AWAY  ->  field at the coil is tiny  ->  EMF ~ 0",
                       "No (or very little) change in flux = no (or very little) induced current",
                       (0.80, 0.85, 0.95)),
    }

    PT_STATE_LESSON = {
        "READY": (
            "<b>What you are looking at:</b> a bar magnet swings straight <b>through</b> the coil and out "
            "the other side, then comes back. Press <b>PLAY</b> and watch the needle. "
            "The big idea: <b>a CHANGING magnetic flux induces a voltage (EMF) and a current.</b>"),
        "APPROACH": (
            "<b>The flux is increasing</b> (d&Phi;/dt &gt; 0), so EMF = &minus;N&middot;d&Phi;/dt is "
            "<b>negative</b> and the needle goes <b>LEFT</b>.<br>"
            "This happens twice per pass: while the <b>N pole is approaching</b> the coil, and again when the "
            "<b>S end is leaving</b> (the flux climbs back from its negative value toward zero).<br>"
            "<b>Lenz:</b> the induced current always opposes whatever the flux is doing."),
        "TURNAROUND": (
            "<b>The middle of the magnet is inside the coil.</b> The field through the coil is strong and "
            "fairly uniform, but it is <b>not changing</b>, so d&Phi;/dt &asymp; 0.<br>"
            "<b>EMF = 0, needle at centre, lamp dark</b> - even though the flux is large.<br>"
            "<b>Key idea:</b> induction depends on the <i>rate of change</i> of flux, <u>not</u> on its size."),
        "RETREAT": (
            "<b>The flux is decreasing</b> (d&Phi;/dt &lt; 0), so the EMF is <b>positive</b> and the needle goes "
            "<b>RIGHT</b>.<br>"
            "The big swing happens as the <b>N pole crosses the coil</b>: outside the magnet the field points one "
            "way, inside it points the other way, so the flux falls through zero and <b>reverses sign</b>.<br>"
            "Same magnet motion, opposite current - that is Lenz's Law."),
        "REST": (
            "<b>The magnet is far from the coil.</b> The field at the coil is very weak and changes very little, "
            "so the induced EMF and current are almost zero."),
    }

    # Live-mode lesson text (HTML), keyed by physical state
    STATE_LESSON = {
        "READY": (
            "<b>What you are looking at:</b> a bar magnet swings back and forth in front of a coil "
            "that is wired to a galvanometer (a current meter). Press <b>PLAY</b> and watch the needle. "
            "The big idea: <b>a CHANGING magnetic flux induces a voltage (EMF) and a current.</b>"),
        "APPROACH": (
            "<b>1. Magnet moves toward the coil</b> - the field through the coil gets stronger, so the "
            "magnetic flux &Phi; <b>increases</b> (d&Phi;/dt &gt; 0).<br>"
            "<b>2. Faraday's Law:</b> EMF = &minus;N&middot;d&Phi;/dt, so the EMF is <b>negative</b>.<br>"
            "<b>3. Lenz's Law:</b> the induced current flows in the direction that <b>opposes</b> the "
            "increase in flux (see the arrows around the coil).<br>"
            "<b>4. Result:</b> the needle deflects <b>LEFT</b>, the <b>lamp lights up</b> and the moving dots show the current flowing around the circuit."),
        "TURNAROUND": (
            "<b>The magnet has momentarily stopped</b> at its closest point. The field B is at its "
            "<b>maximum</b>, but it is <b>not changing</b>, so d&Phi;/dt = 0.<br>"
            "<b>EMF = 0, current = 0, needle returns to center, the lamp goes dark and the dots stop.</b><br>"
            "<b>Key idea:</b> induction depends on the <i>rate of change</i> of flux, "
            "<u>not</u> on how strong the field is."),
        "RETREAT": (
            "<b>1. Magnet moves away</b> - the flux through the coil <b>decreases</b> (d&Phi;/dt &lt; 0).<br>"
            "<b>2. Faraday:</b> EMF = &minus;N&middot;d&Phi;/dt is now <b>positive</b>.<br>"
            "<b>3. Lenz:</b> the current <b>reverses</b> to oppose the decrease (arrows flip).<br>"
            "<b>4. Result:</b> the needle deflects <b>RIGHT</b>, the dots flow the <b>opposite way</b>, and the lamp glows again (its brightness depends on I&sup2;, so it lights for either direction - the needle tells the direction)."),
        "REST": (
            "<b>The magnet is far from the coil.</b> The field at the coil is very weak and changes "
            "very little, so d&Phi;/dt is almost zero and the induced EMF/current are almost zero. "
            "Watch what happens when the magnet comes closer."),
    }

    # Guided tour slides: (title, html text, what-to-say script)
    TOUR = [
        ("Introduction",
         "<b>Goal:</b> show that a <b>moving magnet</b> creates an <b>electric current</b> in a coil "
         "(electromagnetic induction, discovered by Faraday in 1831).<br>"
         "<b>Chain of cause and effect:</b> moving magnet &rarr; changing B &rarr; changing flux &Phi; "
         "&rarr; induced EMF &rarr; current I &rarr; needle deflects.",
         "We simulated Faraday's experiment. Nothing powers the coil except the moving magnet."),
        ("The apparatus",
         "<b>Left:</b> copper coil with N turns (slider: 5-50).<br>"
         "<b>Right:</b> bar magnet - <span style='color:#f87171'>red = North</span>, "
         "<span style='color:#60a5fa'>blue = South</span> - with curved magnetic field lines.<br>"
         "<b>Bottom:</b> galvanometer; the needle shows the current. "
         "The wires complete the circuit. <b>Bottom right:</b> a lamp in series with the coil - it glows when current flows, and small moving dots show the current. <b>Far left:</b> live readout panel.",
         "Point to each part: coil, magnet, field lines, wires, galvanometer, readout panel."),
        ("The equations used",
         "<b>Flux:</b> &Phi; = B &middot; A &middot; cos&theta; (&theta; = 0&deg; here)<br>"
         "<b>Faraday's Law:</b> EMF = &minus;N &middot; d&Phi;/dt<br>"
         "<b>Ohm's Law:</b> I = EMF / R &nbsp; (R = 2.0 &Omega;)<br>"
         "<b>Needle:</b> &theta; = 180&deg;/A &times; I (limited to &plusmn;50&deg;)<br>"
         "The minus sign is <b>Lenz's Law</b>: the induced current opposes the change.",
         "These equations are exactly the functions in physics.py. The green box below shows them with live numbers."),
        ("1. Magnet approaching the coil",
         "The tour is now <b>playing</b>. As the magnet moves toward the coil watch: "
         "flux increases, EMF is <b>negative</b>, the needle goes <b>LEFT</b>, and the arrows around the coil "
         "show the induced current direction. The <b>lamp lights up</b> and dots flow around the wires.",
         "Flux going up means dPhi/dt is positive, so Faraday's minus sign makes the EMF negative."),
        ("2. The turnaround point",
         "The simulation <b>pauses automatically</b> when the magnet reaches its closest point "
         "(press NEXT again if it is already paused). Look: <b>B is at maximum, yet EMF = 0</b> and the "
         "needle is centered, and the <b>lamp is dark</b>.",
         "The field is strongest here but is not changing. Induction depends on the RATE of change, not on B itself."),
        ("3. Magnet moving away",
         "Playing again. The flux now <b>decreases</b>, the EMF becomes <b>positive</b>, the current "
         "<b>reverses</b> and the needle swings <b>RIGHT</b>. This is Lenz's Law in action.",
         "Same magnet, opposite motion, opposite current."),
        ("4. Magnet passes THROUGH the coil",
         "The mode is now <b>PASS THROUGH</b>: the magnet goes into the coil, <b>all the way through</b> and out the "
         "other side. Watch the needle: <b>LEFT</b> as the N pole approaches, a big swing <b>RIGHT</b> as the N pole "
         "crosses the coil (the field through the coil <b>reverses</b>), <b>zero</b> while the middle of the magnet "
         "is inside, then <b>LEFT</b> again as the S end leaves. Peak EMF is again about 0.4 V.",
         "The magnet keeps moving the same way, yet the current reverses - because the flux changes direction of change."),
        ("5. Faster magnet = bigger EMF",
         "Speed is now <b>2.0x</b>. The flux changes twice as fast, so the peak EMF is about "
         "<b>twice as large</b> (about 0.8 V instead of 0.4 V) and the needle reaches its scale limit "
         "(&plusmn;50&deg;). EMF is proportional to speed.",
         "Compare the peak EMF in the green box with the 0.4 V we saw at 1x."),
        ("6. More turns = bigger EMF",
         "Speed is back to 1.0x and the coil now has <b>N = 40</b> turns (was 20). Each turn "
         "contributes the same EMF, so the total EMF is <b>doubled</b> for the same motion. "
         "EMF is proportional to N.",
         "Same motion, twice the turns, twice the EMF."),
        ("7. Graphs",
         "Look at the <b>live graphs on the right</b>: &Phi;(t), EMF(t) and I(t). Notice that the <b>EMF is the negative slope "
         "of the flux curve</b>: where flux peaks (zero slope) the EMF crosses zero; where flux rises "
         "or falls fastest the EMF peaks.",
         "This graph confirms Faraday's Law: EMF is minus N times the derivative of flux."),
        ("Conclusion",
         "<b>A changing magnetic flux induces an EMF and a current (Faraday).</b> The direction "
         "always opposes the change (Lenz). The size grows with <b>speed</b>, <b>number of turns N</b> and "
         "<b>magnet strength</b>. No motion means no change in flux, so no current.<br>"
         "Press <b>EXIT TOUR</b> for live explanations, or play with the sliders.",
         "One sentence: moving magnet, changing flux, induced EMF, current, needle; direction set by Lenz."),
    ]

    def _build_presenter(self):
        """Creates the on-screen banner, tour buttons and explanation boxes."""
        # (1) Banner inside the 3D scene, above the coil
        self.presenter_banner = label(
            pos        = _v(-0.6, 2.55, 0),
            text       = "",
            color      = color.white,
            height     = 14,
            border     = 8,
            background = _v(0.08, 0.11, 0.18),
            opacity    = 0.90,
            box        = True,
            align      = "center"
        )

        # (2) Tour buttons + explanation boxes under the controls
        scene.append_to_caption("\n<hr style='border-color:#334155'>")
        scene.append_to_caption("<b style='color:#38bdf8'>PRESENTATION MODE:</b>&nbsp;")
        self.btn_tour_start = button(text="🎓 START GUIDED TOUR", color=_v(0.0, 0.85, 1.0),
                                     background=_v(0.14, 0.20, 0.28), bind=self._cb_tour_start)
        scene.append_to_caption("  ")
        self.btn_tour_prev = button(text="◀ BACK", color=color.white,
                                    background=_v(0.14, 0.20, 0.28), bind=self._cb_tour_prev)
        scene.append_to_caption("  ")
        self.btn_tour_next = button(text="NEXT ▶", color=color.green,
                                    background=_v(0.14, 0.20, 0.28), bind=self._cb_tour_next)
        scene.append_to_caption("  ")
        self.btn_tour_exit = button(text="■ EXIT TOUR (live explain)", color=_v(1.0, 0.70, 0.2),
                                    background=_v(0.14, 0.20, 0.28), bind=self._cb_tour_exit)
        scene.append_to_caption("\n")
        self.wt_lesson = wtext(text="")
        self.wt_live   = wtext(text="")
        self._update_presenter(force=True)

    # ---- tour button callbacks (thread-safe: they only post a request) -------
    def _cb_tour_start(self, b): self.request_tour = "start"
    def _cb_tour_next(self, b):  self.request_tour = "next"
    def _cb_tour_prev(self, b):  self.request_tour = "prev"
    def _cb_tour_exit(self, b):  self.request_tour = "exit"

    def _apply_tour_request(self, req):
        """Runs on the main thread: change the tour slide and set up the experiment for it."""
        last = len(self.TOUR) - 1
        if req == "start":
            new = 0
        elif req == "next":
            new = 0 if self.tour_step < 0 else min(self.tour_step + 1, last)
        elif req == "prev":
            new = 0 if self.tour_step < 0 else max(self.tour_step - 1, 0)
        else:   # exit
            new = -1
        self.tour_step = new
        self.auto_pause = False
        self._tour_action(new)
        self._update_presenter(force=True)

    def _set_speed(self, value):
        self.speed = float(value)
        self.sl_speed.value = self.speed
        self.wt_speed.text = f"({self.speed:.1f}x)"

    def _set_turns(self, n):
        self.physics.set_coil_turns(int(n))
        self.sl_turns.value = int(n)
        self.wt_turns.text = f"({int(n)})"

    def _tour_action(self, step):
        """Automatically sets up the experiment for each tour slide."""
        # Slide 6 is the only PASS-THROUGH slide; every other slide uses the original
        # BOUNCE motion (the 'turnaround' slides depend on it).  Switching mode resets.
        if step >= 0 and self.pass_through != (step == 6):
            self._set_mode(step == 6)
        if step in (0, 1, 2):          # intro slides: reset and wait
            self._cb_reset(None)
            self._set_speed(1.0)
            self._set_turns(20)
        elif step == 3:                # approach: restart and play
            self._cb_reset(None)
            self._set_speed(1.0)
            self._set_turns(20)
            self.running = True
        elif step == 4:                # turnaround: pause automatically when reached
            self.running = True
            self.auto_pause = True
        elif step == 5:                # retreat
            self.running = True
        elif step == 6:                # pass through the coil
            self._cb_reset(None)
            self._set_speed(1.0)
            self._set_turns(20)
            self.running = True
        elif step == 7:                # speed 2x
            self._cb_reset(None)
            self._set_speed(2.0)
            self.running = True
        elif step == 8:                # N = 40
            self._cb_reset(None)
            self._set_speed(1.0)
            self._set_turns(40)
            self.running = True
        elif step == 9:                # graphs (always visible on the right)
            self.running = True
        # step 10 (conclusion) and -1 (exit): leave things as they are

    def _classify_state(self):
        """Decide what the magnet is doing from the PHYSICS values (not from the animation)."""
        if (not self.running) and self.sim_time == 0.0:
            return "READY"
        d = self.dphi_val                  # dPhi/dt [Wb/s]
        thr = 0.002                        # below this we call the flux "not changing"
        if d > thr:
            return "APPROACH"              # flux increasing -> EMF negative
        if d < -thr:
            return "RETREAT"               # flux decreasing -> EMF positive
        b_strong = 0.02 if self.pass_through else 0.15      # what counts as a 'strong' field
        if abs(self.B_val) > b_strong:
            return "TURNAROUND"            # strong field but flux not changing
        return "REST"

    def _update_presenter(self, force=False):
        """Refresh banner / lesson / live math. Throttled so it never slows the animation."""
        if not hasattr(self, "wt_live"):
            return                          # presenter not built yet (during __init__)

        self._pframe += 1
        self.state = self._classify_state()

        # --- (1) Banner: update whenever the state changes
        banners = self.PT_STATE_BANNER if self.pass_through else self.STATE_BANNER
        title, sub, rgb = banners[self.state]
        banner_text = title if not sub else title + "\n" + sub
        if force or banner_text != self.presenter_banner.text:
            self.presenter_banner.text = banner_text
            self.presenter_banner.color = _v(*rgb)

        # --- (2) Lesson box: only rewrite when state or tour slide changes
        key = (self.state, self.tour_step, self.pass_through)
        if force or key != self._lesson_key:
            self._lesson_key = key
            if self.tour_step >= 0:
                title_t, body, script = self.TOUR[self.tour_step]
                html = (
                    "<div style='background:#0f172a;border-left:5px solid #38bdf8;padding:8px 12px;"
                    "margin:6px 0;font-size:14px;color:#e2e8f0;line-height:1.5'>"
                    f"<b style='color:#38bdf8'>TOUR {self.tour_step + 1}/{len(self.TOUR)} - {title_t}</b><br>"
                    f"{body}<br><i style='color:#fbbf24'>Say: {script}</i></div>"
                )
            else:
                html = (
                    "<div style='background:#0f172a;border-left:5px solid #a78bfa;padding:8px 12px;"
                    "margin:6px 0;font-size:14px;color:#e2e8f0;line-height:1.5'>"
                    "<b style='color:#a78bfa'>LIVE EXPLANATION</b><br>"
                    f"{(self.PT_STATE_LESSON if self.pass_through else self.STATE_LESSON)[self.state]}</div>"
                )
            self.wt_lesson.text = html

        # --- (3) Live math: refresh every 3 frames (or when forced)
        if force or self._pframe % 3 == 0:
            ph = self.physics
            self.wt_live.text = (
                "<div style='background:#111827;border-left:5px solid #34d399;padding:8px 12px;"
                "margin:6px 0;font-size:13px;color:#d1fae5;font-family:monospace;line-height:1.6'>"
                "<b>LIVE MATH (the equations with today's numbers)</b><br>"
                f"&Phi; = B&middot;A = {self.B_val:.4f} T &times; {ph.coil_area:.4f} m&sup2; "
                f"= <b>{self.flux_val:.5f} Wb</b><br>"
                f"d&Phi;/dt = <b>{self.dphi_val:+.4f} Wb/s</b><br>"
                f"EMF = &minus;N&middot;d&Phi;/dt = &minus;{ph.coil_turns} &times; ({self.dphi_val:+.4f}) "
                f"= <b>{self.emf_val:+.3f} V</b><br>"
                f"I = EMF/R = {self.emf_val:+.3f} / {ph.coil_resistance:.1f} "
                f"= <b>{self.curr_val:+.3f} A</b><br>"
                f"Needle = 180 &times; I = <b>{self.needle_deg:+.1f}&deg;</b><br>"
                f"Lamp: P = I&sup2;R = ({self.curr_val:+.3f})&sup2; &times; {ph.coil_resistance:.1f} "
                f"= <b>{self.lamp_power * 1000:.0f} mW</b> &rarr; brightness <b>{100 * self.lamp_level:.0f}%</b></div>"
            )

    # =========================================================================
    # 12. ANIMATION STEP & RUN LOOP (MAIN THREAD SAFE)
    # =========================================================================
    def step(self):
        """
        Advances the virtual physics experiment by one simulation time step
        and updates the live in-scene graphs in real time.
        """
        # ONE FRAME of the experiment. Order of work:
        #   1) advance time  2) move magnet  3) B  4) flux  5) EMF  6) current
        #   7) needle  8) record data  9) redraw 3D  10) update graph
        eff_dt = self.dt * self.speed      # animation time grows faster when speed > 1
        self.sim_time += eff_dt            # drives the magnet's POSITION
        self.real_time += self.dt          # FIX: drives dPhi/dt (see below)

        # Kinematics: Magnet moves along horizontal axis aligned with coil
        self.phase += self.osc_omega * eff_dt * self.motion_dir
        arg = self.phase
        self.mag_x   = float(self.osc_mid + self.osc_amp * np.cos(arg))
        # Velocity = derivative of x(t). Multiply by speed so the HUD shows the
        # true (faster) velocity when the Speed slider is raised.
        self.mag_vel = float(-self.osc_amp * self.osc_omega * self.motion_dir * np.sin(arg)) * self.speed

        # Real-time NumPy Physics Calculations
        # 1. Magnetic Field B at coil
        self.B_val = self.physics.compute_B_field(self.mag_x, self.COIL_X)

        # 2. Magnetic Flux Φ_B
        self.flux_val = self.physics.compute_flux(self.B_val, theta_deg=0.0)

        # 3. Induced EMF (Faraday's Law: EMF = -N dΦ/dt)
        # FIX: use real_time here. With sim_time the speed factor cancelled out
        # (delta-Phi and delta-t both scaled), so EMF did NOT change with speed.
        # With real_time: 2x speed -> same time step but twice the flux change
        # -> dPhi/dt doubles -> EMF doubles (EMF proportional to speed).
        self.emf_val, self.dphi_val = self.physics.compute_emf(self.flux_val, self.real_time)

        # 4. Induced Current (Ohm's Law: I = EMF / R)
        self.curr_val = self.physics.compute_current(self.emf_val)

        # 5. Galvanometer Deflection
        self.needle_deg = self.physics.compute_galvanometer_deflection(self.curr_val)

        # Record simulation trajectory in NumPy arrays
        self.physics.record(
            self.real_time,
            self.mag_x * WORLD_TO_METERS,
            self.mag_vel * WORLD_TO_METERS,
            self.B_val,
            self.flux_val,
            self.emf_val,
            self.curr_val
        )

        # Synchronize 3D VPython instruments
        self._update_all_visuals()

        # Guided tour helper: freeze the animation exactly at the turnaround
        # so the presenter can point at "B is maximum but EMF = 0".
        if self.auto_pause and self.state == "TURNAROUND":
            self.running = False
            self.auto_pause = False
            self._update_presenter(force=True)

        # Feed the live graphs (drawn inside the 3D scene, right-hand side)
        self.graphs.push(self.real_time, self.flux_val, self.emf_val, self.curr_val)

    def run(self):
        """
        Main rendering and event loop running strictly on the main thread.
        Handles button requests (mode, tour) safely on the main thread.
        """
        while True:
            rate(80)   # cap at 80 frames per second (VPython limit)

            # Process MODE button presses on the MAIN THREAD
            if self.request_mode is not None:
                want, self.request_mode = self.request_mode, None
                self._set_mode(want)

            # Process guided-tour button presses on the MAIN THREAD
            if self.request_tour is not None:
                req, self.request_tour = self.request_tour, None
                self._apply_tour_request(req)

            if self.running:
                self.step()