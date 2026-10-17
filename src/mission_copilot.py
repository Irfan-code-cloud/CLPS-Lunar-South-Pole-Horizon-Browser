import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

class MissionCopilot:
    """
    Production-ready AI Agent for NASA Space Apps.
    Ingests live dashboard telemetry and 14-day arrays to predict mission failure states.
    """
    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file.")
            
        genai.configure(api_key=api_key)
        self.model_name = "gemini-3.5-flash"

    def _build_system_instruction(self, telemetry: dict) -> str:
        """
        Constructs the strict boundary prompt using real-time physics data and predictive arrays.
        """
        contingency_text = "None available."
        if telemetry.get('contingencies') is not None and not telemetry['contingencies'].empty:
            contingency_text = telemetry['contingencies'].to_string(index=False)

        # Compress the 14-day arrays into a dense, parseable JSON dictionary
        timeline_forecast = {}
        if 'time_steps' in telemetry and 'battery_array' in telemetry and 'temp_array' in telemetry:
            for h, b, t in zip(telemetry['time_steps'], telemetry['battery_array'], telemetry['temp_array']):
                timeline_forecast[f"H{int(h)}"] = {"Batt_%": round(b, 1), "Temp_C": round(t, 1)}

        return f"""
        You are a NASA Flight Copilot and Senior Astrophysicist. You operate strictly as a deterministic Decision Support System.
        You must ONLY answer based on the following live telemetry payload and 14-day forecast arrays.
        Do not hallucinate, invent, or assume any physics data outside this payload.

        --- LIVE TELEMETRY PAYLOAD (CURRENT SNAPSHOT) ---
        Target Site: {telemetry.get('site', 'Unknown')}
        Current Mission Hour: {telemetry.get('current_hour', 0)}
        Rover Battery Level: {telemetry.get('current_battery', 0):.1f}%
        Rover Core Temperature: {telemetry.get('current_temp', 0):.2f}°C
        Gateway Station Altitude: {telemetry.get('gateway_alt', 0):,.0f} km
        Total Comms Blackout: {telemetry.get('blackout', 0):.1f}%

        --- 14-DAY PREDICTIVE FORECAST ARRAYS ---
        The following JSON maps Elapsed Mission Hour (e.g., "H0") to the predicted Battery % and Core Temperature (°C).
        Use this to forecast failures, predict exactly when temperatures drop to -30°C (CRITICAL FREEZE), or when batteries hit 0.0%.
        {json.dumps(timeline_forecast)}

        --- AI OPTIMIZED LAUNCH CONTINGENCIES ---
        {contingency_text}

        RULES:
        1. If asked about the future, parse the '14-DAY PREDICTIVE FORECAST ARRAYS' to find the exact hour a threshold is crossed.
        2. If the user asks a question that cannot be answered using the metrics above, reply strictly with: "Data unavailable in current telemetry payload."
        3. Keep your answers highly concise, professional, and formatted for a mission control environment.
        4. Never invent new contingency dates.
        """

    def generate_response(self, user_prompt: str, telemetry: dict) -> str:
        dynamic_system_instruction = self._build_system_instruction(telemetry)
        
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=dynamic_system_instruction
        )
        
        try:
            response = model.generate_content(user_prompt)
            return response.text
        except Exception as e:
            error_msg = str(e).lower()
            # Intercept API quota and rate-limit errors
            if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                return "⚠️ **DSN BANDWIDTH EXCEEDED:** The Deep Space Network relay has reached its maximum telemetry quota. Please standby for the satellite link to reset before transmitting additional queries."
            
            # Fallback for all other errors (like no internet connection)
            return f"⚠️ **CRITICAL DSN UPLINK ERROR:** Unable to reach AI core. {e}"