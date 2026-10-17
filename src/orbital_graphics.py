import numpy as np
import plotly.graph_objects as go

def create_celestial_sphere(radius, color, center_coords, name):
    """Generates 3D spherical meshes for planets with adjusted lighting."""
    cx, cy, cz = center_coords
    
    u = np.linspace(0, 2 * np.pi, 40)
    v = np.linspace(0, np.pi, 40)
    x = radius * np.outer(np.cos(u), np.sin(v)) + cx
    y = radius * np.outer(np.sin(u), np.sin(v)) + cy
    z = radius * np.outer(np.ones(np.size(u)), np.cos(v)) + cz
    
    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, color], [1, color]],
        showscale=False,
        name=name,
        hoverinfo="name",
        opacity=1.0,
        lighting=dict(ambient=0.1, diffuse=0.9, roughness=0.5, specular=0.1)
    )

def create_shadow_cone(base_radius, length, center_coords, name):
    """Generates a volumetric shadow cone (umbra) pointing away from the sun."""
    cx, cy, cz = center_coords
    
    u = np.linspace(0, 2 * np.pi, 30)
    v = np.linspace(0, 1, 15)
    u, v = np.meshgrid(u, v)
    
    x = cx - (length * v)
    r = base_radius * (1 - v)
    y = cy + (r * np.cos(u))
    z = cz + (r * np.sin(u))
    
    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, 'black'], [1, 'black']],
        showscale=False,
        name=name,
        hoverinfo="none",
        opacity=0.35
    )

def create_solar_radiation_wash(sun_x, end_x, radius):
    """Generates a highly transparent glowing cylinder to represent traveling light rays."""
    u = np.linspace(0, 2 * np.pi, 20)
    v = np.linspace(0, 1, 2)
    u, v = np.meshgrid(u, v)
    
    x = sun_x - ((sun_x - end_x) * v)
    y = radius * np.cos(u)
    z = radius * np.sin(u)
    
    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, 'yellow'], [1, 'yellow']],
        showscale=False,
        name="Solar Radiation Wash",
        hoverinfo="none",
        opacity=0.08  # Extremely faint, just enough to catch the eye
    )

def generate_macro_orbital_view(
    earth_coords, current_moon_coords, sun_coords, moon_path_arrays,
    current_gateway_coords=None, gateway_path_arrays=None, relay_active=False
):
    """
    Renders the Earth, Moon, Sun, and Gateway Relay in a 3D Deep Space Plotly canvas.
    Features directional lighting, a procedural Milky Way, dynamic eclipses, and active signal bounces.
    """
    fig = go.Figure()
    
    # --- 1. DYNAMIC ECLIPSE MATHEMATICS ---
    mx, my, mz = current_moon_coords
    is_lunar_eclipse = mx < 0 and np.sqrt(my**2 + mz**2) < 3.0
    moon_color = "darkred" if is_lunar_eclipse else "silver"
    
    # --- 2. PROCEDURAL MILKY WAY ---
    np.random.seed(42)
    num_stars = 1500
    star_x = np.random.uniform(-40, 120, num_stars)
    star_y = np.random.uniform(-80, 80, num_stars)
    star_z = np.random.uniform(-80, 80, num_stars)
    star_colors = np.random.choice(['#B3C5FF', '#FFFFFF', '#FFDFB3'], num_stars, p=[0.2, 0.6, 0.2])
    star_sizes = np.random.uniform(0.5, 2.5, num_stars)
    
    fig.add_trace(go.Scatter3d(
        x=star_x, y=star_y, z=star_z, mode='markers',
        marker=dict(size=star_sizes, color=star_colors, opacity=0.7),
        name="Procedural Starfield", hoverinfo='none'
    ))
    
    # --- 3. SOLAR RADIATION & CORONA ---
    fig.add_trace(create_solar_radiation_wash(sun_coords[0], -20, 18))
    fig.add_trace(create_celestial_sphere(13.5, "orange", sun_coords, "Solar Corona"))
    fig.update_traces(opacity=0.15, selector=dict(name="Solar Corona"))
    
    # --- 4. CELESTIAL BODIES (Scale Emphasis Applied) ---
    fig.add_trace(create_celestial_sphere(3, "royalblue", earth_coords, "Earth"))
    fig.add_trace(create_celestial_sphere(12, "gold", sun_coords, "Sun"))
    # Increased Moon radius from 1.2 to 1.8 to establish it as the primary operational theater
    fig.add_trace(create_celestial_sphere(1.8, moon_color, current_moon_coords, "Moon"))
    
    # --- 5. VOLUMETRIC SHADOW CONES ---
    fig.add_trace(create_shadow_cone(3, 40, earth_coords, "Earth Umbra"))
    # Matched Moon umbra base radius to the new 1.8 scale
    fig.add_trace(create_shadow_cone(1.8, 15, current_moon_coords, "Moon Umbra"))
    
    # --- 6. MACRO ORBITAL PATHS ---
    path_x, path_y, path_z = moon_path_arrays
    fig.add_trace(go.Scatter3d(
        x=path_x, y=path_y, z=path_z, mode='lines',
        line=dict(color='rgba(255, 255, 255, 0.3)', width=2, dash='dot'),
        name="5.14° Lunar Orbit Path"
    ))
    
    # --- 7. PHASE 3: GATEWAY NRHO & ACTIVE RELAY SIGNAL (Contrast Boost Applied) ---
    if gateway_path_arrays is not None:
        gx, gy, gz = gateway_path_arrays
        # Increased line width to 4 and opacity to 0.8 for distinct separation from the starfield
        fig.add_trace(go.Scatter3d(
            x=gx, y=gy, z=gz, mode='lines',
            line=dict(color='rgba(255, 165, 0, 0.8)', width=4, dash='dot'),
            name="Gateway NRHO Path"
        ))
        
    if current_gateway_coords is not None:
        cgx, cgy, cgz = current_gateway_coords
        fig.add_trace(go.Scatter3d(
            x=[cgx], y=[cgy], z=[cgz], mode='markers',
            marker=dict(size=5, color='orange', symbol='diamond'),
            name="Gateway Space Station"
        ))
        
        # Render the physical cyan laser bounce if the relay is active
        if relay_active:
            ex, ey, ez = earth_coords
            fig.add_trace(go.Scatter3d(
                x=[ex, cgx, mx], y=[ey, cgy, my], z=[ez, cgz, mz],
                mode='lines', line=dict(color='cyan', width=4),
                name="Active Telemetry Relay"
            ))

    # --- 8. HD LAYOUT & DIRECTIONAL SHADING ---
    directional_light = dict(ambient=0.05, diffuse=0.95, roughness=0.5, specular=0.1)
    fig.update_traces(lighting=directional_light, selector=dict(type='surface'))
    fig.update_traces(lighting=dict(ambient=1.0, diffuse=0.0), selector=dict(name="Sun"))
    
    fig.update_layout(
        scene=dict(
            xaxis=dict(visible=False, showbackground=False),
            yaxis=dict(visible=False, showbackground=False),
            zaxis=dict(visible=False, showbackground=False),
            bgcolor='black', aspectmode='data', 
            camera=dict(up=dict(x=0, y=0, z=1), center=dict(x=0.2, y=0, z=0), eye=dict(x=0.2, y=-1.5, z=0.5))
        ),
        margin=dict(l=0, r=0, b=0, t=0), height=750,
        paper_bgcolor="black", plot_bgcolor="black" 
    )
    
    return fig