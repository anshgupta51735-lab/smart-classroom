# dashboard/smartedu_pulse_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

API_BASE_URL = "http://localhost:8000"  # change to your backend host:port

st.set_page_config(page_title="SmartEdu Pulse", page_icon="📊", layout="wide")
st.title("SmartEdu Pulse - IoT Smart Classroom")
st.caption("Live data from Raspberry Pi + FastAPI backend")

page = st.sidebar.radio("Screens", [
    "Dashboard",
    "Attendance Logs",
    "Bunk Analytics",
    "Energy Digital Twin"
])


def fetch_json(path: str, params=None):
    try:
        r = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API request failed: {e}")
        return []


if page == "Dashboard":
    st_autorefresh_sec = st.sidebar.slider("Auto-refresh (sec)", 5, 60, 10)
    if hasattr(st, "experimental_set_query_params"):
        st.experimental_set_query_params()

    # no explicit rerun to avoid infinite loops in older/newer Streamlit versions
    latest = fetch_json("/api/attendance/latest", params={"limit": 200})
    df = pd.DataFrame(latest)
    st.subheader("Latest Attendance")
    if df.empty:
        st.write("No data yet.")
    else:
        st.dataframe(df, use_container_width=True)

elif page == "Attendance Logs":
    latest = fetch_json("/api/attendance/latest", params={"limit": 500})
    df = pd.DataFrame(latest)
    st.subheader("Attendance Logs from API")
    if df.empty:
        st.write("No logs.")
    else:
        st.dataframe(df, use_container_width=True)

elif page == "Energy Digital Twin":
    rooms = fetch_json("/api/rooms/status")
    df = pd.DataFrame(rooms)
    st.subheader("Room Status (Digital Twin)")
    if df.empty:
        st.write("No room data.")
    else:
        for _, r in df.iterrows():
            icon = "🟢" if r["occupied"] else "🔴"
            st.markdown(f"### {icon} Room {r['room_id']}")
            st.write(f"Power: {r['power_kw']} kW, Capacity: {r['capacity']}")
            st.write(f"Waste Score (rough): {r['waste_score']:.2f}")
# Current Lecture Detection
st.subheader("Current Lecture")

try:
    data = requests.get("http://127.0.0.1:8000/api/current_lecture").json()
    st.metric("Current Lecture", data["current_lecture"])
except:
    st.warning("Backend not responding")
