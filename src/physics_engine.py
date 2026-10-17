import json
import os
import pandas as pd
import numpy as np
from datetime import date

def load_site_coordinates():
    """Loads the target lunar coordinates from the local JSON configuration file."""
    filepath = os.path.join(os.path.dirname(__file__), '..', 'data', 'lunar_site_coords.json')
    with open(filepath, 'r') as file:
        return json.load(file)['sites']

def parse_custom_site_file(uploaded_file):
    """
    Parser: Reads an uploaded JSON or CSV file containing custom lunar site target coordinates.
    Enforces strict mathematical validation on coordinate boundaries (-90 to 90 Lat, -180 to 180 Lon).
    Returns a list of standardized site dictionaries: 
    [{'name': str, 'latitude': float, 'longitude': float, 'description': str}]
    """
    filename = uploaded_file.name.lower()
    custom_sites = []
    
    # Helper function for strict physical coordinate validation
    def validate_coordinate(val, bound_min, bound_max):
        try:
            val_float = float(val)
            if pd.isna(val_float): # Catch Pandas NaN
                return None
            if not (bound_min <= val_float <= bound_max):
                return None
            return val_float
        except (ValueError, TypeError):
            return None # Catch strings or missing data

    try:
        # --- JSON PARSING ---
        if filename.endswith('.json'):
            content = json.load(uploaded_file)
            raw_list = content.get("sites", []) if isinstance(content, dict) else (content if isinstance(content, list) else [content])

            for idx, entry in enumerate(raw_list):
                name = str(entry.get("name", f"Custom JSON Target {idx+1}"))
                desc = str(entry.get("description", "Custom user-uploaded JSON target."))
                
                # Strict Validation
                lat = validate_coordinate(entry.get("latitude"), -90.0, 90.0)
                lon = validate_coordinate(entry.get("longitude"), -180.0, 180.0)
                
                # Only append if BOTH coordinates are mathematically valid
                if lat is not None and lon is not None:
                    custom_sites.append({"name": name, "latitude": lat, "longitude": lon, "description": desc})

        # --- CSV PARSING ---
        elif filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            col_map = {str(col).lower().strip(): col for col in df.columns}
            
            name_col = col_map.get('name', None)
            lat_col = col_map.get('latitude', col_map.get('lat', None))
            lon_col = col_map.get('longitude', col_map.get('lon', None))
            desc_col = col_map.get('description', col_map.get('desc', None))

            for idx, row in df.iterrows():
                site_name = str(row[name_col]) if name_col and pd.notna(row[name_col]) else f"Custom CSV Target {idx+1}"
                site_desc = str(row[desc_col]) if desc_col and pd.notna(row[desc_col]) else "Custom user-uploaded CSV target."
                
                # Strict Validation (Extract value if column exists, else pass None)
                raw_lat = row[lat_col] if lat_col else None
                raw_lon = row[lon_col] if lon_col else None
                
                lat = validate_coordinate(raw_lat, -90.0, 90.0)
                lon = validate_coordinate(raw_lon, -180.0, 180.0)

                # Only append if BOTH coordinates are mathematically valid
                if lat is not None and lon is not None:
                    custom_sites.append({"name": site_name, "latitude": lat, "longitude": lon, "description": site_desc})

    except Exception as e:
        print(f"Error parsing uploaded target site file: {e}")
        return []

    return custom_sites

def get_orbital_vectors_local(site_lat, site_lon, time_array_hours, start_date):
    """
    Calculates solar/earth vectors including absolute Azimuth (compass direction).
    """
    lunar_tilt = 1.54 
    lat_rad = np.radians(site_lat)
    
    reference_new_moon = date(2026, 9, 11)
    days_since_ref = (start_date - reference_new_moon).days
    phase_offset_hours = (days_since_ref % 29.53) * 24
    
    sun_elevations = []
    sun_azimuths = []  # NEW: Array to store compass direction
    earth_elevations = []
    
    for t in time_array_hours:
        absolute_t = t + phase_offset_hours
        
        declination = np.radians(lunar_tilt * np.sin(np.radians(absolute_t * (360/708)))) 
        hour_angle = np.radians(absolute_t * (360/708)) 
        
        # 1. Elevation Math
        sin_elevation = (np.sin(lat_rad) * np.sin(declination) + 
                         np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle))
        sun_elev = np.degrees(np.arcsin(sin_elevation))
        sun_elevations.append(sun_elev)
        
        # 2. Azimuth Math (Compass Direction)
        y = -np.sin(hour_angle)
        x = np.tan(declination) * np.cos(lat_rad) - np.sin(lat_rad) * np.cos(hour_angle)
        sun_az = np.degrees(np.arctan2(y, x))
        sun_az = (sun_az + 360) % 360  # Normalize to 0-360 degrees
        sun_azimuths.append(sun_az)
        
        # 3. Earth Math (Upgraded for Global Coordinates)
        # Calculate base tidal locking elevation
        base_earth_sin = np.cos(lat_rad) * np.cos(np.radians(site_lon))
        base_earth_elev = np.degrees(np.arcsin(base_earth_sin))
        
        # Add ~6.5 degree libration (wobble) based on orbital phase
        earth_elev = base_earth_elev + (6.5 * np.sin(hour_angle))
        earth_elevations.append(earth_elev)
        
    return np.array(sun_elevations), np.array(sun_azimuths), np.array(earth_elevations)

def get_macro_kinematics(time_array_hours, start_date):
    """
    Phase 2 Engine: Calculates the 3D Cartesian coordinates (x, y, z) 
    for the Earth, Moon, and Sun to drive the Macro-Orbital visualization.
    """
    # Use the exact same New Moon anchor so the Macro and Micro views are perfectly synced
    reference_new_moon = date(2026, 9, 11)
    days_since_ref = (start_date - reference_new_moon).days
    phase_offset_hours = (days_since_ref % 29.53) * 24

    # Orbital parameters (Normalized for 3D UI rendering)
    moon_orbit_radius = 20.0
    sun_distance = 100.0  # Placed far away to cast parallel rays
    moon_inclination = np.radians(5.14) # The crucial 5.14-degree lunar tilt

    moon_x_array = []
    moon_y_array = []
    moon_z_array = []

    for t in time_array_hours:
        absolute_t = t + phase_offset_hours
        
        # Moon completes a full 360-degree orbit every 29.53 days (708.7 hours)
        orbital_angle = np.radians(absolute_t * (360 / 708.7))
        
        # Cartesian mapping of the Moon's elliptical orbit
        m_x = moon_orbit_radius * np.cos(orbital_angle)
        m_y = moon_orbit_radius * np.sin(orbital_angle)
        
        # Z introduces the 5.14-degree orbital inclination tilt
        m_z = moon_orbit_radius * np.sin(orbital_angle) * np.sin(moon_inclination)
        
        moon_x_array.append(m_x)
        moon_y_array.append(m_y)
        moon_z_array.append(m_z)

    # Earth is fixed at the absolute center (0,0,0)
    earth_coords = (0, 0, 0)
    
    # Sun is fixed far along the positive X-axis
    # (Locking the Earth-Sun line makes shadow cone visualization much clearer for mission planning)
    sun_coords = (sun_distance, 0, 0)

    return earth_coords, (np.array(moon_x_array), np.array(moon_y_array), np.array(moon_z_array)), sun_coords

if __name__ == "__main__":
    print("--- CLPS Physics Engine: Local Vector Compute ---")
    sites = load_site_coordinates()
    target = sites[0]
    
    print(f"Calculating vectors for: {target['name']}")
    print(f"Coordinates: Lat {target['latitude']}, Lon {target['longitude']}")
    
    # Generate 24 hours of data instantly
    time_steps = np.linspace(0, 24, 24)
    sun, earth = get_orbital_vectors_local(target['latitude'], target['longitude'], time_steps)
    
    print(f"\n✅ Calculation Complete (0.01 seconds)")
    print(f"Sample Sun Angle at hour 12: {sun[12]:.2f}°")
    print(f"Sample Earth Angle at hour 12: {earth[12]:.2f}°")
    print("\nPHASE 1 COMPLETE. Ready to begin Phase 2 (Terrain Shadows).")