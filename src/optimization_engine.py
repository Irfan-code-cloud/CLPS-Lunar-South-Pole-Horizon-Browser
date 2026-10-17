import numpy as np
import pandas as pd
from datetime import date, timedelta
from src.physics_engine import get_orbital_vectors_local
from src.terrain_analyzer import analyze_shadows_and_comms, generate_360_crater_rim
from src.thermodynamics_engine import LunarThermodynamics

def get_max_continuous_hours(boolean_array):
    """Helper to find the longest streak of True values (sunlight) in an array."""
    padded = np.pad(boolean_array, (1, 1), 'constant', constant_values=False)
    diff = np.diff(padded.astype(int))
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]
    if len(starts) == 0:
        return 0
    return np.max(ends - starts)

def find_optimal_launch_windows(lat, lon, mission_duration_days=14):
    """
    Brute-forces the next 365 days from TODAY to find the launch dates 
    yielding the maximum continuous hours of solar clearance, Earth visibility,
    and survivable hardware thermodynamics.
    """
    start_date = date.today()
    time_steps = np.arange(0, mission_duration_days * 24)
    crater_rim = generate_360_crater_rim()
    
    # Init Phase 1 Thermal Engine
    thermo_engine = LunarThermodynamics()
    
    results = []
    
    # Loop through the next 365 days sequentially
    for day_offset in range(365):
        test_date = start_date + timedelta(days=day_offset)
        
        # 1. Generate local vectors for this specific date
        sun_elev, sun_az, earth_elev = get_orbital_vectors_local(
            lat, lon, time_steps, test_date
        )
        
        # 2. Run the 360-degree raycasting terrain analyzer
        sun_vis, earth_vis = analyze_shadows_and_comms(sun_elev, sun_az, earth_elev, crater_rim)
        
        # 3. PHASE 2 THERMAL CALCULATION: Run the stateful thermodynamic array
        thermal_array = thermo_engine.calculate_thermal_array(sun_elev, sun_vis)
        
        # 4. Calculate Power (Sun) and Telemetry (Earth) metrics
        max_continuous_sun = get_max_continuous_hours(sun_vis)
        total_sun = np.sum(sun_vis)
        max_continuous_earth = get_max_continuous_hours(earth_vis)
        total_earth = np.sum(earth_vis)
        
        results.append({
            "Optimal Launch Date": test_date.strftime("%Y-%m-%d"),
            "Longest Sun Window (Hrs)": int(max_continuous_sun),
            "Total Sunlight (Hrs)": int(total_sun),
            "Longest Earth Comm (Hrs)": int(max_continuous_earth),
            "Total Earth Vis (Hrs)": int(total_earth),
            "Peak Temp (°C)": round(np.max(thermal_array), 2),
            "Min Temp (°C)": round(np.min(thermal_array), 2)
        })
        
    df_results = pd.DataFrame(results)
    
    # --- ENGINEERING: THERMAL OVERHAUL NO-GO STATE ---
    # Filter out any launch dates that trigger thermal failure
    survivable_windows = df_results[
        (df_results["Peak Temp (°C)"] < thermo_engine.CRITICAL_OVERHEAT) &
        (df_results["Min Temp (°C)"] > thermo_engine.CRITICAL_FREEZE)
    ]
    
    # Abort if the target is in permanent topographic shadow OR has no survivable thermal windows
    if survivable_windows.empty or df_results["Longest Sun Window (Hrs)"].max() == 0:
        return None
        
    # Otherwise, sort valid windows by the longest continuous sun streak, then Earth comms
    top_windows = survivable_windows.sort_values(
        by=["Longest Sun Window (Hrs)", "Longest Earth Comm (Hrs)"], 
        ascending=False
    ).head(3)
    
    # Reset index to 1, 2, 3 for a clean dashboard display
    top_windows.index = np.arange(1, len(top_windows) + 1)
    
    return top_windows