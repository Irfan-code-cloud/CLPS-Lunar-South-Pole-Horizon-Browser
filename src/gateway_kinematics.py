import numpy as np
from datetime import date
from typing import Tuple

class GatewayRelayEngine:
    """
    Module C (Phase 1): Orbital Mechanics Engine for Lunar Gateway NRHO Relay.
    Calculates the 3D kinematics of the Gateway space station and validates 
    three-body line-of-sight signal clearance (Rover -> Gateway -> Earth).
    """
    def __init__(self):
        # Gateway NRHO Orbital Parameters
        self.orbit_period_hours = 156.0  # ~6.5 Earth days
        self.eccentricity = 0.6          # Highly elliptical orbit
        self.moon_radius_macro = 1.2     # Matched to orbital_graphics.py

    def calculate_gateway_orbit(
        self, 
        time_array_hours: np.ndarray, 
        start_date: date, 
        moon_x: np.ndarray, 
        moon_y: np.ndarray, 
        moon_z: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculates the 3D Cartesian coordinates of Gateway and evaluates signal clearance.
        
        Parameters:
            time_array_hours: 1D array of elapsed mission hours.
            start_date: Mission landing date (to align orbital phase).
            moon_x, moon_y, moon_z: 1D arrays of the Moon's absolute coordinates.
            
        Returns:
            gateway_x, gateway_y, gateway_z (Absolute 3D positions)
            rover_to_gateway_vis (Boolean array: Can the South Pole rover see Gateway?)
            gateway_to_earth_vis (Boolean array: Can Gateway see Earth?)
        """
        # Align Gateway's phase with the existing ephemeris timeline
        reference_date = date(2026, 9, 11)
        days_since_ref = (start_date - reference_date).days
        phase_offset_hours = (days_since_ref % 6.5) * 24

        g_x, g_y, g_z = [], [], []
        rover_vis, earth_vis = [], []

        for i, t in enumerate(time_array_hours):
            absolute_t = t + phase_offset_hours
            
            # 1. Keplerian Eccentric Anomaly Approximation
            # Mean Anomaly (M): 0 = Apoapsis (South Pole), Pi = Periapsis (North Pole)
            M = 2 * np.pi * (absolute_t % self.orbit_period_hours) / self.orbit_period_hours
            
            # Eccentric Anomaly (E) approximation: E = M - e*sin(M)
            # This mathematically enforces Kepler's Second Law: 
            # Gateway moves slowly over the South Pole (Apoapsis Hang) and fast over the North (Periapsis Whip)
            E = M - self.eccentricity * np.sin(M)
            
            # 2. Parametric NRHO generation relative to Moon center
            # X/Y generate the "Halo", Z generates the extreme polar elongation
            rel_x = 1.5 * np.cos(E)
            rel_y = 1.5 * np.sin(E)
            rel_z = -3.5 * np.cos(E) - 1.0  
            
            # Convert to absolute solar system coordinates
            abs_gx = moon_x[i] + rel_x
            abs_gy = moon_y[i] + rel_y
            abs_gz = moon_z[i] + rel_z
            
            g_x.append(abs_gx)
            g_y.append(abs_gy)
            g_z.append(abs_gz)
            
            # --- 3. RELAY SIGNAL CLEARANCE CHECKS ---
            
            # Check A: Rover -> Gateway Visibility
            # The CLPS rover is at the Lunar South Pole (-Z). 
            # Gateway is visible when it is in the southern hemisphere (rel_z < 0.5)
            is_r_vis = rel_z < 0.5
            rover_vis.append(is_r_vis)
            
            # Check B: Gateway -> Earth Visibility
            # Earth is fixed at (0,0,0). We check if the Moon blocks the line-of-sight.
            G = np.array([abs_gx, abs_gy, abs_gz])
            M_pos = np.array([moon_x[i], moon_y[i], moon_z[i]])
            
            # Calculate shortest distance from Moon center to the Earth-Gateway signal line
            cross_prod = np.cross(M_pos, G)
            dist_to_line = np.linalg.norm(cross_prod) / (np.linalg.norm(G) + 1e-6)
            
            # Determine if the Moon is physically between Earth and Gateway
            is_between = np.dot(M_pos, G) > 0 and np.linalg.norm(M_pos) < np.linalg.norm(G)
            
            # If the line passes through the Moon's 1.2 radius body, the Earth link is dead
            if dist_to_line < self.moon_radius_macro and is_between:
                is_e_vis = False
            else:
                is_e_vis = True
                
            earth_vis.append(is_e_vis)

        return np.array(g_x), np.array(g_y), np.array(g_z), np.array(rover_vis), np.array(earth_vis)

# --- STANDALONE UNIT TEST BLOCK ---
if __name__ == "__main__":
    from physics_engine import get_macro_kinematics
    
    print("--- Running Gateway NRHO Kinematics Test ---")
    engine = GatewayRelayEngine()
    test_date = date(2026, 10, 8)
    time_steps = np.arange(0, 156) # Exactly one 6.5 day orbit
    
    # Extract Moon coordinates
    earth_c, moon_arrays, sun_c = get_macro_kinematics(time_steps, test_date)
    m_x, m_y, m_z = moon_arrays
    
    # Calculate Gateway Orbit
    gx, gy, gz, r_vis, e_vis = engine.calculate_gateway_orbit(time_steps, test_date, m_x, m_y, m_z)
    
    print("\n=== NRHO RELAY TELEMETRY LOG ===")
    print(f"Total Orbit Duration: {len(time_steps)} hours")
    print(f"Rover-to-Gateway Link Active: {np.sum(r_vis)} hours ({(np.sum(r_vis)/156)*100:.1f}%)")
    print(f"Gateway-to-Earth Link Active: {np.sum(e_vis)} hours ({(np.sum(e_vis)/156)*100:.1f}%)")
    print("\nPeriapsis Whip Check (Fast North Pole pass):")
    print(f"Max Z Altitude (North): {max(gz - m_z):.2f} | Rover Link: {r_vis[np.argmax(gz - m_z)]}")
    print("\nApoapsis Hang Check (Slow South Pole pass):")
    print(f"Min Z Altitude (South): {min(gz - m_z):.2f} | Rover Link: {r_vis[np.argmin(gz - m_z)]}")