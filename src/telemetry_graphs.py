import numpy as np
import plotly.graph_objects as go

def generate_realistic_3d_terrain(current_sun, current_azimuth, current_earth, is_sun_blocked, is_earth_blocked):
    """
    Builds a high-fidelity, rugged lunar terrain model and renders the telemetry vectors.
    """
    fig_3d = go.Figure()
    
    grid_size = 5
    resolution = 50
    u = np.linspace(-grid_size, grid_size, resolution)
    v = np.linspace(-grid_size, grid_size, resolution)
    u, v = np.meshgrid(u, v)
    
    # 1. Generate Rugged Lunar Topography
    # Base bowl shape
    distance_from_center = np.sqrt(u**2 + v**2)
    base_bowl = (distance_from_center**2 * 0.15)
    
    # Add high-frequency "noise" to simulate boulders, craters, and jagged rims
    np.random.seed(42) 
    noise = np.random.normal(0, 0.15, (resolution, resolution))
    
    # Combine bowl with jagged noise
    w = base_bowl + noise
    
    # Ensure the exact center (rover landing spot) is relatively flat and clear
    center_mask = distance_from_center < 1.0
    w[center_mask] = w[center_mask] * 0.1 
    
    fig_3d.add_trace(go.Surface(
        x=u, y=v, z=w, 
        colorscale="Greys", # Realistic lunar regolith colors
        opacity=0.9, 
        showscale=False,
        name="Lunar Topography",
        hoverinfo='skip', # Hides the raw X/Y/Z array coordinates from the user
        lighting=dict(ambient=0.4, diffuse=0.8, roughness=0.9, specular=0.1) 
    ))
    
    # 2. Glowing Vectors (Elevated slightly to avoid clipping the floor)
    rover_z_offset = 0.5
    sun_x = np.cos(np.radians(current_azimuth)) * grid_size
    sun_y = np.sin(np.radians(current_azimuth)) * grid_size
    sun_z = np.sin(np.radians(current_sun)) * grid_size * 2
    
    fig_3d.add_trace(go.Scatter3d(
        x=[0, sun_x], y=[0, sun_y], z=[rover_z_offset, max(sun_z, rover_z_offset)], 
        mode='lines+markers',
        line=dict(color='yellow' if not is_sun_blocked else 'red', width=6),
        marker=dict(size=[0, 6], color='yellow' if not is_sun_blocked else 'red'),
        name="Solar Vector",
        hovertemplate='<b>Solar Path</b><extra></extra>' # Forces a clean HTML label
    ))
    
    earth_x = np.cos(np.radians(180)) * grid_size 
    earth_y = np.sin(np.radians(180)) * grid_size
    earth_z = np.sin(np.radians(current_earth)) * grid_size * 2
    
    fig_3d.add_trace(go.Scatter3d(
        x=[0, earth_x], y=[0, earth_y], z=[rover_z_offset, earth_z],
        mode='lines+markers',
        line=dict(color='cyan' if not is_earth_blocked else 'red', width=6),
        marker=dict(size=[0, 6], color='cyan' if not is_earth_blocked else 'red'),
        name="Earth Signal",
        hovertemplate='<b>Earth Radio Link</b><extra></extra>' # Forces a clean HTML label
    ))
    
    # 3. Rover Indicator
    fig_3d.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[rover_z_offset], 
        mode='markers',
        marker=dict(size=6, color='white', symbol='diamond'),
        name="CLPS Lander",
        hovertemplate='<b>CLPS Lander (Origin)</b><extra></extra>' # Forces a clean HTML label
    ))
    
    fig_3d.update_layout(
        scene=dict(
            xaxis=dict(visible=False, range=[-grid_size, grid_size]), 
            yaxis=dict(visible=False, range=[-grid_size, grid_size]), 
            zaxis=dict(visible=False, range=[-1, grid_size*1.5]),
            camera=dict(up=dict(x=0, y=0, z=1), center=dict(x=0, y=0, z=0), eye=dict(x=1.5, y=1.5, z=0.5))
        ),
        margin=dict(l=0, r=0, b=0, t=0), height=450,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"
    )
    
    return fig_3d