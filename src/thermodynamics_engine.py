import numpy as np

class LunarThermodynamics:
    """
    Module A (Phase 1): Standalone Thermodynamics Engine for CLPS Rover Survival.
    Calculates dynamic solar heat absorption and radiative cooling in a vacuum environment
    based on Stefan-Boltzmann principles and LRO Diviner thermal baselines.
    """
    def __init__(
        self,
        starting_temp: float = 10.0,
        solar_heat_rate: float = 1.2,
        radiative_cool_rate: float = 3.5
    ):
        # --- CLPS HARDWARE THERMAL LIMITS (°C) ---
        self.OPTIMAL_BASELINE_TEMP = 0.0     # Ideal operational baseline
        self.HIGH_TEMP_WARNING = 40.0        # High temperature alert (requires mitigation)
        self.CRITICAL_OVERHEAT = 50.0        # Thermal failure threshold (hardware burnout)
        self.LOW_TEMP_WARNING = -20.0        # Low temperature alert (heaters required)
        self.CRITICAL_FREEZE = -30.0         # Freezing failure threshold (battery death)
        
        # --- PHYSICAL EQUILIBRIUM LIMITS (°C) ---
        # Extreme surface temperature ranges observed at the Lunar South Pole
        self.MAX_SURFACE_EQUILIBRIUM = 120.0
        self.MIN_SURFACE_EQUILIBRIUM = -150.0
        
        # --- THERMODYNAMIC STATE VARIABLES ---
        self.starting_temp = float(starting_temp)
        # Base °C accumulation per hour at maximum direct overhead solar irradiance (90° elevation)
        self.solar_heat_rate = float(solar_heat_rate)        
        # Base °C loss per hour in absolute shadow (vacuum radiation cooling)
        self.radiative_cool_rate = float(radiative_cool_rate)  

    def _calculate_solar_flux_factor(self, sun_elevation: float) -> float:
        """
        Calculates normalized solar radiation flux incidence based on solar elevation angle.
        At 0° elevation (horizon), flux factor is 0. At 90° elevation (zenith), flux factor is 1.0.
        """
        if sun_elevation <= 0.0:
            return 0.0
        # The intensity of incoming radiation is proportional to the sine of the elevation angle
        return float(np.sin(np.radians(sun_elevation)))

    def calculate_thermal_array(self, sun_elevations: np.ndarray, sun_visible_array: np.ndarray) -> np.ndarray:
        """
        Stateful Thermodynamics Loop:
        Calculates the hour-by-hour core temperature array based on physical exposure limits.
        
        Parameters:
            sun_elevations (np.ndarray): 1D array of solar elevation angles in degrees.
            sun_visible_array (np.ndarray): 1D boolean array indicating solar line-of-sight clearance.
            
        Returns:
            np.ndarray: 1D float array of core temperature values (°C) across elapsed mission time.
        """
        temperature_levels = []
        current_temp = self.starting_temp

        for elev, is_sun_visible in zip(sun_elevations, sun_visible_array):
            
            # --- 1. SOLAR HEATING ALGORITHM ---
            if is_sun_visible and elev > 0.0:
                flux_factor = self._calculate_solar_flux_factor(elev)
                delta_t = self.solar_heat_rate * flux_factor
                current_temp += delta_t
                
            # --- 2. RADIATIVE COOLING ALGORITHM ---
            else:
                # If behind a mountain or the moon's horizon, rapid heat loss to deep space occurs
                delta_t = -self.radiative_cool_rate
                current_temp += delta_t

            # --- 3. CLAMP TO PHYSICAL EXTREMES ---
            # Prevents mathematical runaway beyond physical lunar bounds
            current_temp = max(self.MIN_SURFACE_EQUILIBRIUM, min(self.MAX_SURFACE_EQUILIBRIUM, current_temp))
            temperature_levels.append(round(current_temp, 4))

        return np.array(temperature_levels, dtype=float)


# Diagnostic execution block for standalone testing
if __name__ == "__main__":
    engine = LunarThermodynamics()
    test_elevations = np.array([10.0, 30.0, 45.0, 10.0, -5.0, -5.0])
    test_sun_vis = np.array([True, True, True, False, False, False]) 
    
    print("--- Thermodynamic Engine Unit Test ---")
    temps = engine.calculate_thermal_array(test_elevations, test_sun_vis)
    for h, (e, vis, t) in enumerate(zip(test_elevations, test_sun_vis, temps)):
        print(f"Hour {h}: Elev={e:5.1f}°, SunVisible={str(vis):5s} -> Core Temp={t:6.2f}°C")