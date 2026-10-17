import numpy as np

def generate_360_crater_rim():
    """
    Generates an array of 360 elevation data points (one for each degree of the compass).
    Simulates a jagged crater: highest peak is 3.0° at East (90°), lowest is 0.0° at West (270°).
    """
    azimuths = np.arange(360)
    rim_heights = 1.5 + 1.5 * np.cos(np.radians(azimuths - 90))
    return rim_heights

def analyze_shadows_and_comms(sun_elevations, sun_azimuths, earth_elevations, crater_rim_360):
    """
    Directional Raycasting: Checks if the sun clears the mountain at its specific compass direction.
    """
    sun_visible = []
    
    # Loop through each hour's elevation and direction
    for elev, az in zip(sun_elevations, sun_azimuths):
        az_index = int(az) % 360              # Convert compass degree to array index
        blocking_height = crater_rim_360[az_index] # Get mountain height in that exact direction
        sun_visible.append(elev > blocking_height)
        
    earth_visible = earth_elevations > 2.0
    
    return np.array(sun_visible), earth_visible

def calculate_rover_battery(sun_visible_array, max_capacity=100.0, drain_rate=5.0, charge_rate=8.0):
    battery_levels = []
    current_battery = max_capacity
    
    for is_sun_visible in sun_visible_array:
        if is_sun_visible:
            current_battery += charge_rate  
        else:
            current_battery -= drain_rate   
            
        current_battery = max(0.0, min(max_capacity, current_battery))
        battery_levels.append(current_battery)
        
    return np.array(battery_levels)

if __name__ == "__main__":
    # Terminal Diagnostic Test
    from physics_engine import get_orbital_vectors_local, load_site_coordinates
    from datetime import date
    
    print("--- CLPS Raycasting Engine: 360-Degree Topography Test ---")
    sites = load_site_coordinates()
    target = sites[0]
    
    time_steps = np.arange(0, 24*14) # 14 day test
    test_date = date(2026, 10, 8)
    
    # Engine now returns 3 variables (including azimuth)
    sun_elev, sun_az, earth_elev = get_orbital_vectors_local(
        target['latitude'], target['longitude'], time_steps, test_date
    )
    
    crater_rim = generate_360_crater_rim()
    sun_vis, earth_vis = analyze_shadows_and_comms(sun_elev, sun_az, earth_elev, crater_rim)
    
    print("\n✅ 360° Raycasting Pipeline Executed Successfully.")
    print(f"Sample Hour 100 - Sun Elev: {sun_elev[100]:.2f}°, Sun Azimuth: {sun_az[100]:.0f}°")
    print(f"Mountain Height at Azimuth {sun_az[100]:.0f}°: {crater_rim[int(sun_az[100])]:.2f}°")
    print(f"Is Sun Blocked? {not sun_vis[100]}")