import os
from fpdf import FPDF
import tempfile

class FlightReadinessReport(FPDF):
    def header(self):
        # Professional Aerospace Title Block
        self.set_fill_color(14, 17, 23) # Deep Space Black/Blue
        self.rect(0, 0, 210, 22, 'F')
        self.set_y(6)
        self.set_font('helvetica', 'B', 16)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'NASA CLPS: FLIGHT READINESS REVIEW', border=False, ln=1, align='C')
        self.set_text_color(0, 0, 0) # Reset text color to black for body
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_executive_briefing(
    site_name, lat, lon, launch_date, duration, 
    battery_array, temp_array, sun_vis_array, 
    timeline_fig, thermal_fig, optimal_df
):
    pdf = FlightReadinessReport()
    pdf.add_page()
    
    min_temp = min(temp_array)
    max_temp = max(temp_array)
    lowest_batt = min(battery_array)
    is_nogo = lowest_batt <= 0 or min_temp <= -150 or max_temp >= 120
    
    # --- 1. TOP-LEVEL VERDICT BANNER ---
    pdf.set_font('helvetica', 'B', 14)
    if is_nogo:
        pdf.set_fill_color(255, 235, 235) # Alert Red Fill
        pdf.set_text_color(200, 0, 0)
        verdict_text = "VERDICT: NO-GO (CATASTROPHIC HARDWARE FAILURE DETECTED)"
    else:
        pdf.set_fill_color(235, 255, 235) # Nominal Green Fill
        pdf.set_text_color(0, 150, 0)
        verdict_text = "VERDICT: GO FOR LAUNCH (NOMINAL PARAMETERS)"
        
    pdf.cell(0, 12, verdict_text, border=1, ln=1, align='C', fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(8)

    # --- 2. COMPACT TWO-COLUMN DATA GRID ---
    y_before_grid = pdf.get_y()
    
    # Left Column: Mission Parameters
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(92, 8, 'MISSION PARAMETERS', border=1, ln=1, fill=True)
    pdf.set_font('helvetica', '', 10)
    pdf.cell(92, 7, f"Target Site: {site_name}", border='LR', ln=1)
    pdf.cell(92, 7, f"Coordinates: Lat {lat}, Lon {lon}", border='LR', ln=1)
    pdf.cell(92, 7, f"Proposed Date: {launch_date}", border='LR', ln=1)
    pdf.cell(92, 7, f"Duration: {duration} Earth Days", border='LRB', ln=1)
    
    # Right Column: Extreme Telemetry
    pdf.set_xy(108, y_before_grid)
    pdf.set_font('helvetica', 'B', 11)
    pdf.cell(92, 8, 'EXTREME TELEMETRY', border=1, ln=1, fill=True)
    pdf.set_font('helvetica', '', 10)
    pdf.set_x(108)
    pdf.cell(92, 7, f"Lowest Battery State: {lowest_batt:.1f}%", border='LR', ln=1)
    pdf.set_x(108)
    pdf.cell(92, 7, f"Minimum Core Temp: {min_temp:.1f} C", border='LR', ln=1)
    pdf.set_x(108)
    pdf.cell(92, 7, f"Maximum Core Temp: {max_temp:.1f} C", border='LR', ln=1)
    pdf.set_x(108)
    pdf.cell(92, 7, "", border='LRB', ln=1) # Spacer for symmetry

    pdf.ln(8)

    # --- 3. SIDE-BY-SIDE CHART VISUALIZATIONS ---
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, 'TELEMETRY VISUALIZATIONS', ln=1)
    
    dark_layout = dict(
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117", 
        font=dict(color="white"), margin=dict(l=10, r=10, t=30, b=10)
    )
    timeline_fig.update_layout(**dark_layout)
    thermal_fig.update_layout(**dark_layout)
    
    y_chart = pdf.get_y()
    
    # Render charts at 4:3 aspect ratio and place them horizontally
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_time:
        timeline_fig.write_image(tmp_time.name, format="png", width=800, height=600, scale=2)
        pdf.image(tmp_time.name, x=10, y=y_chart, w=92)
        
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_therm:
        thermal_fig.write_image(tmp_therm.name, format="png", width=800, height=600, scale=2)
        pdf.image(tmp_therm.name, x=108, y=y_chart, w=92)

    pdf.set_y(y_chart + 72) # Push cursor clear of the 92mm-wide images
    os.remove(tmp_time.name)
    os.remove(tmp_therm.name)

    # --- 4. AI CONTINGENCY TABLE ---
    pdf.ln(5)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, 'AI OPTIMIZED LAUNCH CONTINGENCIES', ln=1)
    
    if optimal_df is not None and not optimal_df.empty:
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(30, 8, 'Rank', border=1, fill=True, align='C')
        pdf.cell(80, 8, 'Launch Date', border=1, fill=True, align='C')
        pdf.cell(80, 8, 'Continuous Sunlight', border=1, ln=1, fill=True, align='C')
        
        pdf.set_font('helvetica', '', 10)
        # Use enumerate(..., start=1) to guarantee perfect 1, 2, 3 ranking
        for rank, (index, row) in enumerate(optimal_df.head(3).iterrows(), start=1):
            pdf.cell(30, 8, f"#{rank}", border=1, align='C')
            pdf.cell(80, 8, f"{row['Optimal Launch Date']}", border=1, align='C')
            pdf.cell(80, 8, f"{row['Longest Sun Window (Hrs)']} hrs", border=1, ln=1, align='C')
    else:
        pdf.set_font('helvetica', 'I', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, "No viable alternate launch windows detected in the next 365 days.", ln=1)

    return pdf.output(dest='S')