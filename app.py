import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import our custom backend modules
from src.physics_engine import load_site_coordinates, get_orbital_vectors_local, get_macro_kinematics, parse_custom_site_file
from src.terrain_analyzer import analyze_shadows_and_comms, calculate_rover_battery, generate_360_crater_rim
from src.telemetry_graphs import generate_realistic_3d_terrain
from src.orbital_graphics import generate_macro_orbital_view
from src.optimization_engine import find_optimal_launch_windows
from src.thermodynamics_engine import LunarThermodynamics
from src.spatial_pathfinder import generate_dynamic_pathfinding_mesh, render_3d_navigation_mesh
from src.gateway_kinematics import GatewayRelayEngine
from src.report_generator import generate_executive_briefing
from src.mission_copilot import MissionCopilot

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="CLPS Lunar Horizon Browser", layout="wide", page_icon="🌙", initial_sidebar_state="expanded")

st.title("CLPS Lunar South Pole Horizon Browser", icon=":material/dark_mode:")
st.caption("A Next-Gen 3D Telemetry and Shadow Mapping Tool for Mission Planners")
# --- GLOBAL UI OVERRIDES (External CSS Loader) ---
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("assets/style.css")

# --- DATA INGESTION & CUSTOM TARGET UPLOADER ---
@st.cache_data
def get_default_sites():
    return load_site_coordinates()

sites = get_default_sites()

# --- SIDEBAR: MISSION CONTROLS ---
st.sidebar.header("Mission Controls")

# Uploader: Bring Your Own Crater / Custom Coordinates
uploaded_site_file = st.sidebar.file_uploader(
    "Ingest Custom Landing Target (JSON/CSV)",
    type=["json", "csv"],
    help="Upload a JSON or CSV file containing custom coordinates ('name', 'latitude', 'longitude', and optional 'description')."
)

if uploaded_site_file is not None:
    custom_sites = parse_custom_site_file(uploaded_site_file)
    if custom_sites:
        # Prepend custom uploaded sites so they immediately appear at the top of the target dropdown
        sites = custom_sites + sites
        st.sidebar.success(f"Ingested {len(custom_sites)} Custom Target(s)", icon=":material/check_circle:")
    else:
        st.sidebar.error("Could not parse file. Check JSON/CSV formatting.", icon=":material/error:")

site_names = [site['name'] for site in sites]
selected_site_name = st.sidebar.selectbox("Select Landing Site Target", site_names)

# Match selected name to coordinate data
target_site = next(site for site in sites if site['name'] == selected_site_name)

st.sidebar.markdown(f"**Lat:** {target_site['latitude']} | **Lon:** {target_site['longitude']}")
st.sidebar.info(target_site['description'])

# Absolute temporal scale inputs
st.sidebar.subheader("Temporal Parameters", icon=":material/calendar_month:")
landing_date = st.sidebar.date_input("Mission Landing Date")
mission_duration_days = st.sidebar.slider("Mission Duration (Earth Days)", 1, 28, 14)
time_slider = st.sidebar.slider("Elapsed Mission Hours", 0, (mission_duration_days * 24) - 1, 0)

st.sidebar.subheader("Rover Specifications", icon=":material/battery_charging_full:")
max_batt = st.sidebar.number_input("Max Battery Capacity (Wh)", value=100.0)
drain_rate = st.sidebar.slider("Shadow Drain Rate", 1.0, 10.0, 5.0)
# --- ROUTE NAVIGATION CONTROLS ---
st.sidebar.subheader("Rover Route Targets", icon=":material/navigation:")
start_col, goal_col = st.sidebar.columns(2)
with start_col:
    start_r = st.sidebar.number_input("Landing Row", 0, 99, 15)
    start_c = st.sidebar.number_input("Landing Col", 0, 99, 15)
with goal_col:
    goal_r = st.sidebar.number_input("Target Row", 0, 99, 85)
    goal_c = st.sidebar.number_input("Target Col", 0, 99, 85)

# --- BACKEND CALCULATION TRIGGER ---
time_steps = np.arange(0, mission_duration_days * 24)

# Unpack the 3 variables (now including sun_azimuths)
sun_angles, sun_azimuths, earth_angles = get_orbital_vectors_local(
    target_site['latitude'], 
    target_site['longitude'], 
    time_steps,
    landing_date
)

# Generate the jagged 360-degree crater rim array
crater_rim_360 = generate_360_crater_rim()

# Pass azimuth and 360 terrain into the analyzer
sun_vis, earth_vis = analyze_shadows_and_comms(sun_angles, sun_azimuths, earth_angles, crater_rim_360)
battery_levels = calculate_rover_battery(sun_vis, max_capacity=max_batt, drain_rate=drain_rate)

# --- THERMAL INTEGRATION ---
thermo_engine = LunarThermodynamics()
temperature_levels = thermo_engine.calculate_thermal_array(sun_angles, sun_vis)
current_temp = temperature_levels[time_slider]

# Extract current instant data based on slider
current_sun = sun_angles[time_slider]
current_azimuth = sun_azimuths[time_slider]
current_earth = earth_angles[time_slider]
is_sun_blocked = not sun_vis[time_slider]
is_earth_blocked = not earth_vis[time_slider]
current_batt = battery_levels[time_slider]

# Find the exact height of the mountain blocking the sun right now
current_mountain_height = crater_rim_360[int(current_azimuth) % 360]

# --- PATHFINDING PIPELINE HANDSHAKE ---
path_telemetry = generate_dynamic_pathfinding_mesh(
    sun_elevation=current_sun,
    sun_azimuth=current_azimuth,
    crater_rim_360=crater_rim_360,
    start_coords=(int(start_r), int(start_c)),
    goal_coords=(int(goal_r), int(goal_c)),
    grid_size=100,
    cell_size_m=10.0
)

# --- MACRO KINEMATICS (Phase 2) ---
# Calculate the entire orbital path for the mission duration
earth_c, moon_c_arrays, sun_c = get_macro_kinematics(time_steps, landing_date)

# Extract the Moon's exact X, Y, Z coordinates for the currently selected hour on the slider
current_moon_x = moon_c_arrays[0][time_slider]
current_moon_y = moon_c_arrays[1][time_slider]
current_moon_z = moon_c_arrays[2][time_slider]

# --- GATEWAY RELAY PIPELINE (Phase 2 Handshake) ---
gateway_engine = GatewayRelayEngine()
g_x_arr, g_y_arr, g_z_arr, r_vis_arr, e_vis_arr = gateway_engine.calculate_gateway_orbit(
    time_steps, landing_date, moon_c_arrays[0], moon_c_arrays[1], moon_c_arrays[2]
)

# Extract instant vectors for the current time slider hour
current_gx = g_x_arr[time_slider]
current_gy = g_y_arr[time_slider]
current_gz = g_z_arr[time_slider]
is_rover_to_gateway_clear = r_vis_arr[time_slider]
is_gateway_to_earth_clear = e_vis_arr[time_slider]

# --- THE HANDSHAKE DECISION TREE ---
# If Earth is blocked, but both legs of the Gateway relay are clear, activate the backup link
relay_active = is_earth_blocked and is_rover_to_gateway_clear and is_gateway_to_earth_clear

# Total blackout only occurs if Earth is blocked AND the Gateway relay is unavailable
total_comms_blackout = is_earth_blocked and not relay_active

# --- CENTER WINDOW: MAIN VISUALIZATION ---
# UX Decision: Wrap only the visual canvas and metrics within tabs. 
# The sidebar controls and bottom timeline remain global to drive both views simultaneously.
tab1, tab2, tab3 = st.tabs([
    ":material/satellite_alt: Surface Topography (Micro View)", 
    ":material/public: Orbital Mechanics (Macro View)",
    ":material/smart_toy: AI Mission Copilot"
])

with tab1:
    # ----------------- MICRO VIEW (Rover Perspective) -----------------
    with st.expander("Mission Primer: How to read this surface map", expanded=True, icon=":material/menu_book:"):
        st.markdown("""
        **The Micro Survival Problem:** Even if the Moon is in direct sunlight, a local mountain can block the lander's solar panels.
        * **The Grey Mesh:** A 3D mathematical representation of the localized crater topography around the landing site.
        * **The White Diamond:** The stationary CLPS lander on the lunar surface.
        * **The Yellow/Red Vector:** The exact physical path of the Sun. If the line turns red and points through the mountain, the lander is in shadow and draining battery.
        * **The Cyan Vector:** The radio signal path to Earth.
        """)

    # ----------------- MICRO VIEW (Rover Perspective - HUD Layout) -----------------
    st.subheader("System Vital Status")
    
    # ROW 1: Top-Level Alerts
    alert_col1, alert_col2, alert_col3 = st.columns(3)
    with alert_col1:
        if is_sun_blocked:
            st.error("CRATER SHADOW: Power Offline", icon=":material/battery_alert:")
        else:
            st.success("SOLAR ARRAY: Charging", icon=":material/solar_power:")
            
    with alert_col2:
        if not is_earth_blocked:
            st.info("DIRECT LINK: Earth-Line Clear", icon=":material/satellite_alt:")
        elif relay_active:
            st.warning("RELAY ACTIVE: Gateway Link Established", icon=":material/settings_input_antenna:")
        else:
            st.error("COMMS BLACKOUT: Total Signal Loss", icon=":material/wifi_off:")
            
    with alert_col3:
        # Dynamic HUD Alerts based on hardware limits mapped in the physics engine
        if current_temp >= thermo_engine.CRITICAL_OVERHEAT:
            st.error("THERMAL FAILURE: Hardware Overheat", icon=":material/local_fire_department:")
        elif current_temp >= thermo_engine.HIGH_TEMP_WARNING:
            st.warning("THERMAL WARNING: Approaching Max Temp", icon=":material/warning:")
        elif current_temp <= thermo_engine.CRITICAL_FREEZE:
            st.error("THERMAL FAILURE: Hardware Frozen", icon=":material/ac_unit:")
        elif current_temp <= thermo_engine.LOW_TEMP_WARNING:
            st.warning("THERMAL WARNING: Approaching Min Temp", icon=":material/warning:")
        else:
            st.success("THERMALS: Nominal", icon=":material/thermostat:")
            
    # ROW 2: Symmetrical 5-Column KPI Grid
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    with kpi1:
        with st.container(border=False):
            st.metric(label="Solar Angle", value=f"{current_sun:.2f}°", delta=f"{current_sun - current_mountain_height:.2f}° clearance")
    with kpi2:
        with st.container(border=False):
            st.metric(label="Earth Elevation", value=f"{current_earth:.2f}°", delta=f"{current_earth - 2.0:.2f}° clearance")
    with kpi3:
        with st.container(border=False):
            st.metric(label="Solar Azimuth", value=f"{current_azimuth:.0f}°")
    with kpi4:
        with st.container(border=False):
            st.metric(label="Current Battery", value=f"{current_batt:.1f}%")
    with kpi5:
        with st.container(border=False):
            # Calculate live heating/cooling rate vs the previous hour
            temp_delta = current_temp - temperature_levels[max(0, time_slider - 1)]
            st.metric(label="Core Temp", value=f"{current_temp:.1f}°C", delta=f"{temp_delta:+.2f}°C / hr", delta_color="off")

    # ROW 3: Full-Width 3D Visualization
    with st.container(border=True):
        st.subheader("Interactive 3D Orbit & Vector Space", icon=":material/3d_rotation:")
        fig_3d = generate_realistic_3d_terrain(current_sun, current_azimuth, current_earth, is_sun_blocked, is_earth_blocked)
        st.plotly_chart(fig_3d, use_container_width=True)

    # --- ROW 4: Autonomous Navigation System & KPIs ---
    st.subheader("Autonomous Navigation System", icon=":material/route:")
    
    # 1. Mission Primer (Educational Onboarding)
    with st.expander("Mission Primer: How to read this navigation mesh", expanded=True, icon=":material/menu_book:"):
        st.markdown("""
        **The Surface Routing Problem:** The rover must navigate from the landing zone to the target destination without flipping over on steep crater walls or freezing in permanent shadows.
        * **The Green Vector:** The optimal A* traversal route mapping the path of least topographical resistance.
        * **The Blue Marker:** The Rover Landing Zone (Start).
        * **The Red Marker:** The Target Destination (Goal).
        * **Safety Overrides:** If the requested route forces the rover into a slope exceeding 25° or a pitch-black freezing shadow, the system will trigger a mandatory safety scrub and abort the path.
        """)
    
    # 2. Top-Level Dynamic Warning HUD (Full Width Status)
    if not path_telemetry["path_viable"]:
        st.error("ROUTE UNVIABLE: Topographical Hazard or Shadow Blockage", icon=":material/block:")
    else:
        st.success("ROUTE NOMINAL: Safe Traverse Plotted", icon=":material/check_circle:")
            
    # 3. Symmetrical 3-Column KPI Grid
    nav_kpi1, nav_kpi2, nav_kpi3 = st.columns(3)
    
    with nav_kpi1:
        with st.container(border=False):
            dist_km = path_telemetry["total_distance_m"] / 1000.0
            st.metric("Total Traverse", f"{dist_km:.2f} km")
            
    with nav_kpi2:
        with st.container(border=False):
            max_slp = path_telemetry["max_slope_deg"]
            st.metric("Max Slope", f"{max_slp:.1f}°")
            
    with nav_kpi3:
        with st.container(border=False):
            # Drive time based on realistic extreme terrain rover speed (0.1 km/h)
            drive_time = dist_km / 0.1 if dist_km > 0 else 0
            st.metric("Est. Drive Time", f"{drive_time:.1f} hrs")

    # --- ROW 5: Full-Width 3D Pathfinding Mesh ---
    with st.container(border=True):
        st.subheader("Interactive 3D Navigation Mesh", icon=":material/3d_rotation:")
        fig_3d_nav = render_3d_navigation_mesh(path_telemetry)
        st.plotly_chart(fig_3d_nav, use_container_width=True)



    # --- AI OPTIMIZATION ENGINE (Main UI Placement) ---
    # 1. Initialize the dataframe in session memory so it survives chat reruns
    if "optimal_df" not in st.session_state:
        st.session_state.optimal_df = None

    with st.container(border=True):
        st.subheader("AI Optimization Engine", icon=":material/model_training:")
        st.caption("Brute-force the next 365 days of orbital mechanics to find the absolute best future launch windows for the selected target.")

        if st.button("Calculate Optimal Launch Windows", icon=":material/memory:"):
            with st.status("Running 365-day orbital simulation...", expanded=True) as status:
                st.write("Initializing target physics vectors from today's date...")
                st.write("Raycasting terrain topographies...")
                
                # Trigger the engine and save directly to session state
                st.session_state.optimal_df = find_optimal_launch_windows(
                    target_site['latitude'], 
                    target_site['longitude'], 
                    mission_duration_days=mission_duration_days
                )
                
                st.write("Sorting optimal future survival windows...")
                status.update(label="Analysis Complete!", state="complete", expanded=False)
                
            if st.session_state.optimal_df is None:
                st.error("MISSION SCRUBBED: Target coordinates are in permanent topographic shadow. No viable launch windows exist.", icon=":material/block:")
            else:
                st.success("Top 3 Future Mission Windows Identified:")
                st.dataframe(st.session_state.optimal_df, use_container_width=True)

    # --- BOTTOM TIMELINE PANEL ---

    # 1. Create a figure with a secondary y-axis
    fig_timeline = make_subplots(specs=[[{"secondary_y": True}]])

    # 2. Add Battery Trace to the PRIMARY axis (Left)
    fig_timeline.add_trace(
        go.Scatter(
            x=time_steps, 
            y=battery_levels,
            mode='lines',
            name='Battery Level',
            line=dict(color='#00FF00', width=2),
            fill='tozeroy', # Adds a faint green glow under the battery line for quick visual weight
            fillcolor='rgba(0, 255, 0, 0.1)',
            hovertemplate='<b>Battery:</b> %{y:.1f}%<extra></extra>'
        ),
        secondary_y=False,
    )

    # 3. Add Sun Angle Trace to the SECONDARY axis (Right)
    fig_timeline.add_trace(
        go.Scatter(
            x=time_steps, 
            y=sun_angles,
            mode='lines',
            name='Sun Angle',
            line=dict(color='#FFD700', width=2),
            hovertemplate='<b>Sun Angle:</b> %{y:.2f}°<extra></extra>'
        ),
        secondary_y=True,
    )

    # 4. Add the Horizon Threshold Line
    fig_timeline.add_hline(
        y=0, 
        line_dash="dot", 
        secondary_y=True, 
        line_color="rgba(255, 255, 255, 0.5)", 
        annotation_text="Lunar Horizon (0°)", 
        annotation_position="bottom right",
        annotation_font=dict(color="rgba(255, 255, 255, 0.5)")
    )

    # 5. Configure layout, dual axis labels, and a unified hover tooltip
    fig_timeline.update_layout(
        xaxis_title="Elapsed Mission Time (Hours)",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Lock the Battery axis from 0 to 105 so it doesn't bounce around, but let the Sun axis scale dynamically
    fig_timeline.update_yaxes(title_text="Battery Level (%)", range=[0, 105], secondary_y=False)
    fig_timeline.update_yaxes(title_text="Sun Elevation Angle (°)", secondary_y=True)

    with st.container(border=True):
        st.subheader("Mission Telemetry Timeline", icon=":material/timeline:")
        st.plotly_chart(fig_timeline, use_container_width=True)

    # --- DEDICATED THERMAL TIMELINE ---

    fig_thermal = go.Figure()

    # Core Temperature Curve (Red)
    fig_thermal.add_trace(
        go.Scatter(
            x=time_steps, 
            y=temperature_levels,
            mode='lines',
            name='Core Temp',
            line=dict(color='#FF4B4B', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 75, 75, 0.1)',
            hovertemplate='<b>Temp:</b> %{y:.2f}°C<extra></extra>'
        )
    )

    # Render hardcoded Failure Threshold Lines from the backend engine
    fig_thermal.add_hline(
        y=thermo_engine.CRITICAL_OVERHEAT, line_dash="dash", line_color="#FF0000",
        annotation_text="CRITICAL OVERHEAT LIMIT", annotation_position="top left",
        annotation_font=dict(color="#FF0000")
    )
    fig_thermal.add_hline(
        y=thermo_engine.CRITICAL_FREEZE, line_dash="dash", line_color="#00FFFF",
        annotation_text="CRITICAL FREEZE LIMIT", annotation_position="bottom left",
        annotation_font=dict(color="#00FFFF")
    )

    fig_thermal.update_layout(
        xaxis_title="Elapsed Mission Time (Hours)",
        yaxis_title="Core Temperature (°C)",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    with st.container(border=True):
        st.subheader("Thermodynamic Profile", icon=":material/thermostat:")
        st.plotly_chart(fig_thermal, use_container_width=True)

    # --- MISSION TELEMETRY EXPORT & DATA TABLE ---

    # 1. Package the arrays into the DataFrame (keeping them as pure math for the CSV)
    df_telemetry = pd.DataFrame({
        "Elapsed Mission Hour": time_steps,
        "Battery Level (%)": battery_levels,
        "Core Temperature (°C)": temperature_levels,
        "Sun Elevation Angle (°)": sun_angles,
        "Solar Azimuth (°)": sun_azimuths,
        "Earth Elevation (°)": earth_angles,
        "Moon Orbit X": moon_c_arrays[0],
        "Moon Orbit Y": moon_c_arrays[1],
        "Moon Orbit Z": moon_c_arrays[2]
    })

    csv_export = df_telemetry.to_csv(index=False).encode('utf-8')

    # --- UI OVERRIDES (Square Corners) ---
    st.markdown("""
        <style>
        [data-testid="stDataFrame"] > div {
            border-radius: 0px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # 2. Create the Layout
    header_col, csv_col, pdf_col = st.columns([2, 1, 1])

    with header_col:
        st.subheader("Raw Telemetry Data", icon=":material/table_chart:")
        st.markdown(f"**Target Site:** {selected_site_name} | **Total Rows:** {len(df_telemetry)} | **Data Columns:** {len(df_telemetry.columns)}")
        st.caption("This dataset contains the hour-by-hour local physical vectors, global orbital kinematics, and power state for advanced mission analysis.")
        
    with csv_col:
        st.write("") 
        st.download_button(
            label="Export Raw Data (CSV)",
            data=csv_export,
            file_name=f"CLPS_Telemetry_{selected_site_name.replace(' ', '_')}_{landing_date}.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True 
        )

    with pdf_col:
        st.write("")
        # Generate the PDF in memory only when the user clicks the button
        pdf_bytes = generate_executive_briefing(
            site_name=selected_site_name,
            lat=target_site['latitude'],
            lon=target_site['longitude'],
            launch_date=landing_date,
            duration=mission_duration_days,
            battery_array=battery_levels,
            temp_array=temperature_levels,
            sun_vis_array=sun_vis,
            timeline_fig=fig_timeline,
            thermal_fig=fig_thermal,
            optimal_df=st.session_state.optimal_df # Updated to use memory
        )
        
        # FIX: Cast the fpdf2 bytearray into strict immutable bytes for Streamlit
        st.download_button(
            label="Executive Briefing (PDF)",
            data=bytes(pdf_bytes),
            file_name=f"Flight_Readiness_{selected_site_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            use_container_width=True
        )

    # 3. Render the interactive table with Native Streamlit Column Formatting
    st.dataframe(
        df_telemetry, 
        height=400, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            # Casting Hour as a TextColumn forces it to the left side
            "Elapsed Mission Hour": st.column_config.TextColumn("Elapsed Mission Hour"),
            # Formatting the rest to clean 1 or 2 decimal places to remove the zeros
            "Battery Level (%)": st.column_config.NumberColumn(format="%.1f"),
            "Core Temperature (°C)": st.column_config.NumberColumn(format="%.2f"),
            "Sun Elevation Angle (°)": st.column_config.NumberColumn(format="%.2f"),
            "Solar Azimuth (°)": st.column_config.NumberColumn(format="%.2f"),
            "Earth Elevation (°)": st.column_config.NumberColumn(format="%.2f"),
            "Moon Orbit X": st.column_config.NumberColumn(format="%.2f"),
            "Moon Orbit Y": st.column_config.NumberColumn(format="%.2f"),
            "Moon Orbit Z": st.column_config.NumberColumn(format="%.2f"),
        }
    )

with tab2:
    # ----------------- MACRO VIEW (Solar System Perspective) -----------------
    st.subheader("Solar System Kinematics (Macro View)", icon=":material/explore:")
    
    # 1. Educational Legend Update
    with st.expander("Mission Primer: How to read this orbital map", expanded=True, icon=":material/menu_book:"):
        st.markdown("""
        **Bridging the Macro to the Micro:** The survival of our CLPS lander on the surface is entirely dictated by these macro-orbital mechanics.
        * **The Black Cones (Umbra):** The physical shadows cast by the Earth and Moon. 
        * **The Red Moon (Eclipse):** If the Moon's 5.14° tilted orbit drags it through the Earth's black shadow cone, a Lunar Eclipse occurs, causing a total power blackout.
        * **Gateway NRHO Relay:** The orange dotted line represents the highly elliptical orbit of the Lunar Gateway. If the direct Earth signal is blocked by local terrain, the rover will automatically bounce its telemetry off the station (rendered as a cyan beam).
        """)
        
    # Package the current coordinates for Phase 3 rendering
    current_moon_coords = (current_moon_x, current_moon_y, current_moon_z)
    current_gateway_coords = (current_gx, current_gy, current_gz)
    gateway_path_arrays = (g_x_arr, g_y_arr, g_z_arr)
    
    # 2. Dynamic Real-Time Alerts
    if current_moon_x < 0 and np.sqrt(current_moon_y**2 + current_moon_z**2) < 3.0:
        st.error("LUNAR ECLIPSE DETECTED: The Moon has entered the Earth's shadow cone. The CLPS lander is experiencing a total power blackout.", icon=":material/emergency:")
    else:
        st.success("ORBITAL CLEARANCE: The Moon is receiving unobstructed solar radiation.", icon=":material/light_mode:")

    # 3. Generate and display the enlarged deep space figure (Now with Gateway!)
    fig_macro = generate_macro_orbital_view(
        earth_c, current_moon_coords, sun_c, moon_c_arrays,
        current_gateway_coords, gateway_path_arrays, relay_active
    )
    st.plotly_chart(fig_macro, use_container_width=True)

    # --- DEEP SPACE NETWORK (DSN) HUD ---
    st.markdown("---")
    st.subheader("Deep Space Network (DSN) Telemetry", icon=":material/cell_tower:")
    
    # 1. Aggregate the full mission duration into network uptime percentages
    direct_earth_array = np.array(earth_vis)
    relay_array = (~direct_earth_array) & np.array(r_vis_arr) & np.array(e_vis_arr)
    blackout_array = (~direct_earth_array) & (~relay_array)
    
    total_hours = len(time_steps)
    pct_direct = (np.sum(direct_earth_array) / total_hours) * 100
    pct_relay = (np.sum(relay_array) / total_hours) * 100
    pct_blackout = (np.sum(blackout_array) / total_hours) * 100
    
    # 2. Calculate instantaneous real-time distances for the current slider hour
    # The visual vectors are scaled down for the 3D plot. Multiply by ~3000 to convert back to realistic NRHO kilometers.
    ORBITAL_SCALE_FACTOR = 3000  
    gateway_altitude = np.sqrt(current_gx**2 + current_gy**2 + current_gz**2) * ORBITAL_SCALE_FACTOR
    
    # 3. Render the 4-Column Metric HUD with Uniform Heights
    dsn_col1, dsn_col2, dsn_col3, dsn_col4 = st.columns(4)
    
    with dsn_col1:
        with st.container(border=False):
            st.metric("Direct-to-Earth Link", f"{pct_direct:.1f}%")
            
    with dsn_col2:
        with st.container(border=False):
            st.metric("Gateway NRHO Relay", f"{pct_relay:.1f}%")
            
    with dsn_col3:
        with st.container(border=False):
            # Dynamic color alert for blackouts formatted as a metric
            if pct_blackout > 0:
                st.metric("Total Comms Blackout", f"{pct_blackout:.1f}%", delta="CRITICAL SIGNAL LOSS", delta_color="inverse")
            else:
                st.metric("Total Comms localized", f"{pct_blackout:.1f}%")
                
    with dsn_col4:
        with st.container(border=False):
            prev_gx = g_x_arr[max(0, time_slider - 1)]
            prev_gy = g_y_arr[max(0, time_slider - 1)]
            prev_gz = g_z_arr[max(0, time_slider - 1)]
            prev_alt = np.sqrt(prev_gx**2 + prev_gy**2 + prev_gz**2) * ORBITAL_SCALE_FACTOR
            alt_delta = 0 if time_slider == 0 else gateway_altitude - prev_alt
            st.metric("Gateway Altitude", f"{gateway_altitude:,.0f} km", delta=f"{alt_delta:+,.0f} km/h", delta_color="inverse")

    # 4. Educational Tooltips/Explanations
    st.info("""
    **Understanding DSN Telemetry Metrics:**
    * **Direct-to-Earth Link:** The percentage of the mission duration where the rover has an unobstructed, direct line-of-sight to Earth for maximum data downlink bandwidth.
    * **Gateway NRHO Relay:** The percentage of the mission where the direct Earth signal is blocked by local crater walls, forcing the rover to bounce its telemetry off the Lunar Gateway space station passing overhead.
    * **Total Comms Blackout:** The percentage of time where the rover is deep inside a crater *and* the Lunar Gateway is on the far side of its orbit, resulting in zero communication capability.
    """, icon=":material/info:")

with tab3:
    st.subheader("AI Mission Copilot", icon=":material/smart_toy:")
    st.caption("Ask questions about the current telemetry payload, power states, and orbital relays.")

    # 1. Package the live dashboard state and predictive arrays into a dictionary
    live_telemetry = {
        "site": selected_site_name,
        "current_hour": time_slider,
        "current_battery": current_batt,
        "current_temp": current_temp,
        "gateway_alt": gateway_altitude,
        "blackout": pct_blackout,
        "contingencies": st.session_state.optimal_df, # Updated to use memory
        # INJECT FULL ARRAYS FOR PREDICTIVE FORECASTING
        "time_steps": time_steps.tolist(),
        "battery_array": battery_levels.tolist(),
        "temp_array": temperature_levels.tolist()
    }

    # 2. Initialize chat session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 3. Create a dedicated scrollable terminal container
    chat_container = st.container(height=450, border=True)

    # 4. Render Welcome State OR Active Conversation Log
    with chat_container:
        if len(st.session_state.messages) == 0:
            # --- WELCOME BANNER (Only visible before the first message) ---
            st.markdown("<br>", unsafe_allow_html=True)
            st.info("""
            **DSN Link Established: AI Mission Copilot Online**
            
            I am your deterministic flight controller. I am continuously monitoring the live surface topography, macro-orbital kinematics, and 14-day telemetry forecasting arrays.
            
            **Suggested commands to begin:**
            * *"Scan the 14-day array. At what exact hour does the battery reach 0.0%?"*
            * *"If we scrub today's launch, what is our #1 ranked backup date?"*
            * *"Confirm our current mission hour, core temperature, and gateway altitude."*
            
            *Awaiting telemetry query...*
            """, icon=":material/radar:")
        else:
            # --- ACTIVE CONVERSATION LOG (Welcome banner vanishes permanently) ---
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # 5. Chat Input Field (Anchored directly below the terminal window)
    if prompt := st.chat_input("Please start your conversation here..."):
        # Append user query to state
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Render live visual feedback in the terminal container
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Analyzing telemetry payload..."):
                    copilot = MissionCopilot()
                    response_text = copilot.generate_response(prompt, live_telemetry)
                    st.markdown(response_text)
                    
        # Append response and force an instant UI refresh to remove the welcome banner
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.rerun()