"""
physics.py — Electromagnetic Induction Physics Engine (NumPy-Powered)
======================================================================
Performs all numerical physics calculations using NumPy:
  • Two-pole bar magnet magnetic field B(x) model
  • Magnetic flux Φ_B = B · A · cos(θ)
  • Numerical derivative dΦ_B/dt using finite differences
  • Faraday's Law of Induction: EMF = -N · (dΦ_B/dt)
  • Ohm's Law for circuit current: I = EMF / R
  • Lenz's Law directional logic and galvanometer angular deflection

Physical Quantities & Units:
----------------------------
  • Position: meters [m]
  • Velocity: meters per second [m/s]
  • Magnetic Field: Tesla [T]
  • Coil Area: square meters [m²]
  • Magnetic Flux: Webers [Wb]
  • dΦ/dt: Webers per second [Wb/s]
  • Induced EMF: Volts [V]
  • Induced Current: Amperes [A]
  • Galvanometer Deflection: degrees [°]
"""

import numpy as np

# Physical constants
MU_0 = 4.0 * np.pi * 1e-7          # Permeability of free space [T·m/A]
WORLD_TO_METERS = 0.20             # 1 VPython world unit = 0.20 meters
BASE_POLE_STRENGTH = 8500.0        # Calibrated magnetic pole strength [A·m]  (BOUNCE mode)
PASS_POLE_STRENGTH = 5000.0        # Calibrated pole strength [A·m]            (PASS-THROUGH mode)
                                   # (lower because the coil-disc average is used there, see below;
                                   #  tuned so the peak EMF is ~0.40 V at 1x speed with N = 20)


class PhysicsEngine:
    """
    NumPy-based physical calculation engine for electromagnetic induction.
    """

    def __init__(self,
                 coil_radius_m: float = 0.096,     # physical radius (r ≈ 9.6 cm)
                 coil_turns: int = 20,              # initial turns N = 20
                 coil_resistance: float = 2.0,      # circuit resistance R = 2.0 Ω
                 magnet_strength_scale: float = 1.0):

        # Coil geometry & circuit parameters
        self.coil_radius_m   = float(coil_radius_m)
        self.coil_area       = float(np.pi * (self.coil_radius_m ** 2))
        self.coil_turns      = int(coil_turns)
        self.coil_resistance = float(coil_resistance)
        self.strength_scale  = float(magnet_strength_scale)

        # Motion mode.  False = magnet bounces in front of the coil (original model).
        #               True  = magnet passes straight THROUGH the coil and out the other side.
        self.pass_through    = False

        # Bar magnet geometry (physical meters)
        self.magnet_half_len_m = 0.48 * WORLD_TO_METERS    # half-length L_m = 0.096 m
        self.softening_radius_m = 0.032                    # cross-section softening radius R_m

        # Dynamic state tracking for numerical derivative dΦ/dt
        self._prev_flux = None
        self._prev_time = None

        # Galvanometer deflection calibration factor (deg/A)
        # Calibrated so that current of ~0.20 A gives ~36 degrees deflection
        self.galv_sensitivity = 180.0

        # Simulation history stored as NumPy float64 arrays
        self.time_history = np.zeros(0, dtype=np.float64)
        self.pos_history  = np.zeros(0, dtype=np.float64)
        self.vel_history  = np.zeros(0, dtype=np.float64)
        self.B_history    = np.zeros(0, dtype=np.float64)
        self.flux_history = np.zeros(0, dtype=np.float64)
        self.emf_history  = np.zeros(0, dtype=np.float64)
        self.curr_history = np.zeros(0, dtype=np.float64)

    # -------------------------------------------------------------------------
    # Parameter Setters
    # -------------------------------------------------------------------------
    def set_coil_turns(self, turns: int):
        """Update number of coil turns N."""
        self.coil_turns = max(1, int(turns))

    def set_magnet_strength(self, scale: float):
        """Update magnetic field strength multiplier."""
        self.strength_scale = max(0.1, float(scale))

    # -------------------------------------------------------------------------
    # Core Physics Calculations (NumPy-accelerated)
    # -------------------------------------------------------------------------
    def compute_B_field(self, magnet_center_x: float, coil_center_x: float) -> float:
        """
        Axial magnetic field B seen by the coil [Tesla].

        BOUNCE mode (original model)
            B at the coil CENTRE from the two-pole magnet.  Only valid while the
            coil stays on one side of the magnet, so the result is |B| (no sign).

        PASS-THROUGH mode
            Once the magnet goes through the coil the field at the coil changes
            DIRECTION (outside the magnet it points one way, inside it points the
            other way), so a signed value is needed.  We return the AVERAGE axial
            field over the coil opening,  B_avg = Phi / A,  so that
            Phi = B_avg * A  still holds.  Sign convention: positive = pointing
            away from the side the magnet starts on (so approaching gives B > 0).

        Parameters
        ----------
        magnet_center_x : float - World x position of magnet center
        coil_center_x   : float - World x position of coil center
        """
        x_m = magnet_center_x * WORLD_TO_METERS
        x_c = coil_center_x * WORLD_TO_METERS

        # North pole (+q_m) faces left toward coil; South pole (-q_m) is on right
        x_N = x_m - self.magnet_half_len_m
        x_S = x_m + self.magnet_half_len_m

        if self.pass_through:
            return self._disc_average_field(x_c, x_N, x_S)

        q_m = BASE_POLE_STRENGTH * self.strength_scale
        coeff = (MU_0 * q_m) / (4.0 * np.pi)

        # Distances with softening radius to prevent unphysical singularities
        dist_N_sq = (x_c - x_N)**2 + self.softening_radius_m**2
        dist_S_sq = (x_c - x_S)**2 + self.softening_radius_m**2

        # B field at coil center (axial component)
        B = coeff * (1.0 / dist_N_sq - 1.0 / dist_S_sq)
        return float(np.abs(B))

    def _disc_average_field(self, x_c: float, x_N: float, x_S: float) -> float:
        """
        Signed average axial field over the coil opening (radius r) for the
        two-pole magnet.  Each (softened) pole of strength q at axial distance d
        from the coil plane sends through the disc a flux

            Phi_pole = (mu0 q / 4 pi) * 2 pi d * [ 1/s - 1/sqrt(r^2 + s^2) ],
            s^2 = d^2 + R_m^2

        (exact integral of the pole's field over the disc).  d changes sign when
        the pole crosses the coil plane, which is what reverses the flux.
        """
        q_m   = PASS_POLE_STRENGTH * self.strength_scale
        coeff = (MU_0 * q_m) / (4.0 * np.pi)
        r2    = self.coil_radius_m ** 2

        def pole_flux(x_pole):
            d  = x_c - x_pole                       # + if the coil is to the right of the pole
            s2 = d * d + self.softening_radius_m ** 2
            s  = np.sqrt(s2)
            return 2.0 * np.pi * d * (1.0 / s - 1.0 / np.sqrt(r2 + s2))

        flux_along_plus_x = coeff * (pole_flux(x_N) - pole_flux(x_S))   # N is +q, S is -q
        # Normal chosen along -x (away from the magnet's starting side)
        return float(-flux_along_plus_x / self.coil_area)

    def compute_flux(self, B: float, theta_deg: float = 0.0) -> float:
        """
        Calculates magnetic flux through the coil:
            Φ_B = B · A · cos(θ)   [Weber, Wb]
        """
        theta_rad = np.deg2rad(theta_deg)
        return float(B * self.coil_area * np.cos(theta_rad))

    def compute_emf(self, flux: float, current_time: float):
        """
        Calculates the rate of change of magnetic flux dΦ/dt and
        the induced EMF using Faraday's Law:
            EMF = -N · (dΦ_B / dt)   [Volts, V]

        Returns
        -------
        (emf, dphi_dt) : (float, float)
        """
        if self._prev_flux is None or self._prev_time is None:
            self._prev_flux = flux
            self._prev_time = current_time
            return 0.0, 0.0

        dt = current_time - self._prev_time
        if abs(dt) < 1e-12:
            return 0.0, 0.0

        # Numerical finite difference: dΦ/dt
        dphi_dt = (flux - self._prev_flux) / dt

        # Faraday's Law (with Lenz's Law negative sign)
        emf = -float(self.coil_turns) * dphi_dt

        self._prev_flux = flux
        self._prev_time = current_time

        return float(emf), float(dphi_dt)

    def compute_current(self, emf: float) -> float:
        """
        Calculates induced current using Ohm's Law:
            I = EMF / R   [Amperes, A]
        """
        return float(emf / max(self.coil_resistance, 1e-6))

    def compute_galvanometer_deflection(self, current: float) -> float:
        """
        Calculates physical needle deflection in degrees:
          • Negative current (magnet approaching) -> deflects LEFT (-)
          • Current = 0 (magnet stopped)          -> returns to CENTER (0)
          • Positive current (magnet retreating)   -> deflects RIGHT (+)
        Clamped to ±50.0 degrees maximum scale.
        """
        deg = current * self.galv_sensitivity
        return float(np.clip(deg, -50.0, 50.0))

    def get_current_direction_text(self, current: float) -> str:
        """
        Direction of the induced current, seen from the RIGHT (the side the magnet
        starts on, looking toward the coil).  Flux normal = -x, so EMF > 0 drives
        the current counterclockwise about -x, i.e. CLOCKWISE seen from the right.
        Check (Lenz): N pole approaching -> I < 0 -> counterclockwise from the
        right -> the coil's right face becomes a North pole and REPELS the magnet.
        """
        if abs(current) < 1e-4:
            return "None (0 A)"
        elif current > 0:
            return "Clockwise (from right)"
        else:
            return "Counterclockwise (from right)"

    # -------------------------------------------------------------------------
    # NumPy History Recording
    # -------------------------------------------------------------------------
    def record(self, t: float, pos_m: float, vel_ms: float, B: float, flux: float, emf: float, curr: float):
        """Append data using NumPy array concatenation."""
        self.time_history = np.append(self.time_history, t)
        self.pos_history  = np.append(self.pos_history,  pos_m)
        self.vel_history  = np.append(self.vel_history,  vel_ms)
        self.B_history    = np.append(self.B_history,    B)
        self.flux_history = np.append(self.flux_history, flux)
        self.emf_history  = np.append(self.emf_history,  emf)
        self.curr_history = np.append(self.curr_history, curr)

    def reset(self):
        """Reset historical data arrays and derivative tracking."""
        self._prev_flux = None
        self._prev_time = None
        self.time_history = np.zeros(0, dtype=np.float64)
        self.pos_history  = np.zeros(0, dtype=np.float64)
        self.vel_history  = np.zeros(0, dtype=np.float64)
        self.B_history    = np.zeros(0, dtype=np.float64)
        self.flux_history = np.zeros(0, dtype=np.float64)
        self.emf_history  = np.zeros(0, dtype=np.float64)
        self.curr_history = np.zeros(0, dtype=np.float64)
