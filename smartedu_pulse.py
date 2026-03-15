<<<<<<< HEAD
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime
import os

# =========================================================
# SMARTEDU PULSE - STREAMLIT APP
# Attendance + Bunk + Energy + Digital Twin + Free Rooms
# Hindi-English comments inside code
# =========================================================

DB_PATH = "smartedu_pulse.db"

# ---------- DB Helpers ----------

def get_conn():
    # SQLite connection - simple local DB (suppress Python 3.12 deprecation)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DB tables create + demo seed data (agar empty ho)."""
    conn = get_conn()
    cur = conn.cursor()

    # students(id,name,batch)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            batch TEXT NOT NULL
        )
    """)

    # timetable(lecture_id,day,time,subject,room)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetable(
            lecture_id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT NOT NULL
        )
    """)

    # attendance(student_id,lecture_id,action,time)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            lecture_id TEXT NOT NULL,
            action TEXT NOT NULL,           -- 'IN' / 'OUT'
            time TIMESTAMP NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(lecture_id) REFERENCES timetable(lecture_id)
        )
    """)

    # rooms(room_id,power_kw,capacity)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms(
            room_id TEXT PRIMARY KEY,
            power_kw REAL NOT NULL,
            capacity INTEGER NOT NULL
        )
    """)

    # Seed students agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM students")
    if cur.fetchone()["c"] == 0:
        demo_students = [
            ("Ansh", "CSE-A"),
            ("Priya", "CSE-A"),
            ("Rohan", "CSE-A"),
            ("Simran", "CSE-A"),
            ("Kabir", "CSE-A"),
            ("Aisha", "CSE-A"),
            ("Vikram", "CSE-A"),
            ("Neha", "CSE-A"),
            ("Arjun", "CSE-A"),
            ("Isha", "CSE-A"),
        ]
        cur.executemany(
            "INSERT INTO students(name,batch) VALUES(?,?)",
            demo_students
        )

    # Seed rooms agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM rooms")
    if cur.fetchone()["c"] == 0:
        demo_rooms = [
            ("R101", 1.2, 60),
            ("R102", 1.5, 80),
            ("R103", 1.0, 50),
            ("Lab1", 2.0, 40),
        ]
        cur.executemany(
            "INSERT INTO rooms(room_id,power_kw,capacity) VALUES(?,?,?)",
            demo_rooms
        )

    # Seed timetable agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM timetable")
    if cur.fetchone()["c"] == 0:
        # NOTE: time format "HH:MM-HH:MM" taaki duration nikal saken
        demo_tt = [
            ("L1", "Mon", "09:00-10:00", "DSA", "R101"),
            ("L2", "Mon", "10:00-11:00", "WCC", "R101"),
            ("L3", "Mon", "11:00-12:00", "OS", "R102"),
            ("L4", "Tue", "09:00-10:00", "DBMS", "R101"),
            ("L5", "Tue", "10:00-11:00", "WCC", "R102"),
            ("L6", "Wed", "09:00-10:00", "DSA", "R103"),
        ]
        cur.executemany(
            "INSERT INTO timetable(lecture_id,day,time,subject,room) VALUES(?,?,?,?,?)",
            demo_tt
        )

    conn.commit()
    conn.close()


def parse_time_range(time_str):
    """
    Timetable ke time column ka format:
    - "09:00-10:00" → start, end
    - Agar sirf "09:00" ho, to 1 hour assume.
    """
    try:
        if "-" in time_str:
            start_s, end_s = time_str.split("-")
            start = datetime.strptime(start_s.strip(), "%H:%M")
            end = datetime.strptime(end_s.strip(), "%H:%M")
        else:
            start = datetime.strptime(time_str.strip(), "%H:%M")
            end = start.replace(hour=(start.hour + 1) % 24)
        return start, end
    except Exception:
        # Koi parsing error ho to default 1 hour
        now = datetime.now()
        start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end = now.replace(hour=10, minute=0, second=0, microsecond=0)
        return start, end


# ---------- Data Load Helpers ----------

def load_students_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM students ORDER BY id", conn)
    conn.close()
    return df


def load_rooms_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM rooms ORDER BY room_id", conn)
    conn.close()
    return df


def load_timetable_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM timetable ORDER BY day, time", conn)
    conn.close()
    return df


def load_attendance_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM attendance", conn, parse_dates=["time"])
    conn.close()
    return df


# ---------- Attendance Logic ----------

def record_attendance(student_id, lecture_id, action):
    """Attendance scan IN/OUT record kare (current time ke saath)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO attendance(student_id,lecture_id,action,time) VALUES(?,?,?,?)",
        (int(student_id), lecture_id, action, datetime.now())
    )
    conn.commit()
    conn.close()


def build_attendance_summary():
    """
    Attendance summary:
    - Har (student, lecture) ke liye duration (minutes) nikalna (OUT - IN).
    - Present tab manenge jab duration >= 30 min (configurable).
    """
    students = load_students_df()
    timetable = load_timetable_df()
    att = load_attendance_df()

    if att.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0

    # IN/OUT ko group karke earliest IN & latest OUT nikalna
    grouped = (
        att.groupby(["student_id", "lecture_id", "action"])["time"]
        .agg(["min", "max"])
        .reset_index()
    )

    # Pivot: IN / OUT alag columns
    pivot = grouped.pivot_table(
        index=["student_id", "lecture_id"],
        columns="action",
        values="min",  # 'min' hi sufficient hai (per action)
        aggfunc="first"
    ).reset_index()

    # Column names flatten
    pivot.columns.name = None

    # Duration minutes
    def calc_duration(row):
        t_in = row.get("IN")
        t_out = row.get("OUT")
        if pd.isna(t_in) or pd.isna(t_out):
            return 0.0
        return (t_out - t_in).total_seconds() / 60.0

    pivot["duration_min"] = pivot.apply(calc_duration, axis=1)

    # Present flag (>= 30 min)
    MIN_PRESENT_MIN = 30
    pivot["present"] = pivot["duration_min"] >= MIN_PRESENT_MIN

    # Join students + timetable for readable info
    pivot = pivot.merge(students, left_on="student_id", right_on="id", how="left")
    pivot = pivot.merge(timetable, on="lecture_id", how="left")

    # Lecture-wise summary
    lecture_summary = (
        pivot.groupby(["lecture_id", "day", "time", "subject", "room"])
        .agg(
            total_students=("student_id", "nunique"),
            present_students=("present", "sum"),
            avg_duration_min=("duration_min", "mean"),
        )
        .reset_index()
    )
    lecture_summary["attendance_pct"] = (
        lecture_summary["present_students"] * 100.0 / lecture_summary["total_students"].clip(lower=1)
    )

    # Overall avg attendance
    overall_attendance = lecture_summary["attendance_pct"].mean() if not lecture_summary.empty else 0.0

    return pivot, lecture_summary, overall_attendance


# ---------- Bunk Analysis ----------

def compute_bunk_triggers(att_summary_df, lecture_summary_df, students_df):
    """
    Bunk trigger detector:
    - Consecutive lectures ke pairs (same day + batch approximate).
    - Pair (A->B) ke liye:
        % bunk = students who were present in A but absent in B.
    """
    if att_summary_df.empty or lecture_summary_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Timetable with ordered index
    tt = load_timetable_df().copy()
    # Time ko sortable banane ke liye start time parse
    tt["start_time_obj"] = tt["time"].apply(lambda x: parse_time_range(x)[0])
    tt = tt.sort_values(["day", "start_time_obj"]).reset_index(drop=True)

    # consecutive pairs
    pairs = []
    for idx in range(len(tt) - 1):
        row_a = tt.iloc[idx]
        row_b = tt.iloc[idx + 1]
        # Same room/batch approx - yaha simple rule: same day & same batch (all CSE-A demo)
        if row_a["day"] == row_b["day"]:
            pairs.append((row_a["lecture_id"], row_b["lecture_id"]))

    if not pairs:
        return pd.DataFrame(), pd.DataFrame()

    pair_stats = []
    for l1, l2 in pairs:
        a1 = att_summary_df[att_summary_df["lecture_id"] == l1]
        a2 = att_summary_df[att_summary_df["lecture_id"] == l2]

        # Students set - currently all same batch, to be safe use intersection
        students_present_l1 = set(a1.loc[a1["present"], "student_id"].tolist())
        students_present_l2 = set(a2.loc[a2["present"], "student_id"].tolist())

        if not students_present_l1:
            continue

        bunkers = students_present_l1 - students_present_l2
        bunk_pct = len(bunkers) * 100.0 / len(students_present_l1)

        subj1 = tt.loc[tt["lecture_id"] == l1, "subject"].values[0]
        subj2 = tt.loc[tt["lecture_id"] == l2, "subject"].values[0]

        pair_stats.append({
            "from_lecture": l1,
            "to_lecture": l2,
            "from_subject": subj1,
            "to_subject": subj2,
            "bunk_pct": bunk_pct,
            "bunk_count": len(bunkers),
            "base_present_count": len(students_present_l1),
        })

    if not pair_stats:
        return pd.DataFrame(), pd.DataFrame()

    pair_df = pd.DataFrame(pair_stats).sort_values("bunk_pct", ascending=False)

    # Heatmap ke liye pivot (subject-wise)
    heatmap_df = pair_df.pivot_table(
        index="from_subject",
        columns="to_subject",
        values="bunk_pct",
        aggfunc="mean"
    ).fillna(0.0)

    return pair_df, heatmap_df


# ---------- Energy Analytics ----------

def compute_energy_waste(lecture_summary_df, rooms_df, cost_per_kwh=8.0):
    """
    Energy calculator:
    - Har lecture ke liye:
        occupancy = present / capacity
        duration_hours from timetable time
        energy_used = power_kw * duration_hours
        waste_factor = (1 - occupancy)
        wasted_energy = energy_used * waste_factor
    """
    tt = load_timetable_df()
    if lecture_summary_df.empty or tt.empty or rooms_df.empty:
        return pd.DataFrame(), 0.0, 0.0

    # Merge timetable + rooms + attendance summary
    df = lecture_summary_df.merge(tt, on=["lecture_id", "day", "time", "subject", "room"], how="left")
    df = df.merge(rooms_df, left_on="room", right_on="room_id", how="left")

    # Duration hours
    def duration_hrs(row):
        start, end = parse_time_range(row["time"])
        return (end - start).total_seconds() / 3600.0

    df["duration_h"] = df.apply(duration_hrs, axis=1)
    # Occupancy
    df["occupancy"] = df["present_students"] / df["capacity"].clip(lower=1)

    # Energy used (ideal full utilisation) & waste
    df["energy_kwh"] = df["power_kw"] * df["duration_h"]
    df["waste_factor"] = (1.0 - df["occupancy"]).clip(lower=0.0, upper=1.0)
    df["wasted_kwh"] = df["energy_kwh"] * df["waste_factor"]
    df["wasted_inr"] = df["wasted_kwh"] * cost_per_kwh

    total_waste_inr = df["wasted_inr"].sum()
    total_energy_inr = (df["energy_kwh"] * cost_per_kwh).sum()
    waste_pct = (total_waste_inr * 100.0 / total_energy_inr) if total_energy_inr > 0 else 0.0

    return df, total_waste_inr, waste_pct


# ---------- Free Rooms Finder ----------

def get_free_rooms(selected_day, selected_time):
    """
    Free rooms finder:
    - Selected day + time slot ke liye timetable check karo.
    - Jis room me us slot ka lecture nahi hai → free.
    """
    rooms = load_rooms_df()
    tt = load_timetable_df()

    if rooms.empty:
        return []

    # Filter timetable on same day and exact time string
    busy = tt[(tt["day"] == selected_day) & (tt["time"] == selected_time)]
    busy_rooms = set(busy["room"].tolist())

    all_rooms = set(rooms["room_id"].tolist())
    free_rooms = sorted(list(all_rooms - busy_rooms))
    return free_rooms


# =========================================================
# STREAMLIT UI
# =========================================================

def main():
    init_db()

    st.set_page_config(
        page_title="SmartEdu Pulse",
        page_icon="📊",
        layout="wide"
    )

    st.title("🎓 SmartEdu Pulse - Smart Classroom Analytics")
    st.caption("Smart Attendance + Bunk Detector + Energy Waste + Digital Twin + Free Rooms (Software Only)")

    # Sidebar navigation - 7 screens
    pages = {
        "1️⃣ Dashboard": "dashboard",
        "2️⃣ Attendance + Stay Graph": "attendance",
        "3️⃣ Timetable CSV Upload": "timetable",
        "4️⃣ Bunk Heatmap + Triggers": "bunk",
        "5️⃣ Energy Digital Twin": "energy",
        "6️⃣ Free Rooms Finder": "free_rooms",
        "7️⃣ Reports / CSV Export": "reports"
    }

    choice = st.sidebar.radio("Screens", list(pages.keys()))
    page = pages[choice]

    # Load base data
    students_df = load_students_df()
    rooms_df = load_rooms_df()
    timetable_df = load_timetable_df()
    att_df = load_attendance_df()
    att_detail_df, lecture_summary_df, overall_attendance = build_attendance_summary()
    bunk_pairs_df, bunk_heatmap_df = compute_bunk_triggers(
        att_detail_df, lecture_summary_df, students_df
    )
    energy_df, total_waste_inr, waste_pct = compute_energy_waste(
        lecture_summary_df, rooms_df
    )

    if page == "dashboard":
        render_dashboard(
            students_df,
            timetable_df,
            att_detail_df,
            lecture_summary_df,
            bunk_pairs_df,
            energy_df,
            total_waste_inr,
            waste_pct,
            overall_attendance
        )
    elif page == "attendance":
        render_attendance_page(
            students_df,
            timetable_df,
            att_detail_df,
            lecture_summary_df
        )
    elif page == "timetable":
        render_timetable_page(timetable_df)
    elif page == "bunk":
        render_bunk_page(bunk_pairs_df, bunk_heatmap_df)
    elif page == "energy":
        render_energy_page(energy_df, rooms_df)
    elif page == "free_rooms":
        render_free_rooms_page(timetable_df, rooms_df)
    elif page == "reports":
        render_reports_page(att_detail_df, lecture_summary_df, bunk_pairs_df, energy_df)


# ---------- Page 1: Dashboard ----------

def render_dashboard(
    students_df,
    timetable_df,
    att_detail_df,
    lecture_summary_df,
    bunk_pairs_df,
    energy_df,
    total_waste_inr,
    waste_pct,
    overall_attendance
):
    st.subheader("📊 Overall Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_students = len(students_df)
        st.metric("Total Students", total_students)

    with col2:
        total_lectures = len(timetable_df)
        st.metric("Timetable Lectures", total_lectures)

    with col3:
        st.metric("Avg Attendance %", f"{overall_attendance:.1f}%")

    with col4:
        monthly_est_waste = total_waste_inr * 22  # approx 22 working days
        st.metric("Est. Monthly Waste (₹)", f"{monthly_est_waste:,.0f}")

    # Insights cards - Hindi-English copy (pitch ke hisaab se)
    st.markdown("---")
    st.markdown("#### 🔍 Insight Cards")

    c1, c2, c3 = st.columns(3)

    # Top bunk pair
    bunk_text = "Data kam hai - bunk pattern abhi clear nahi."
    if not bunk_pairs_df.empty:
        top = bunk_pairs_df.iloc[0]
        bunk_text = f"Top bunk: **{top['from_subject']} → {top['to_subject']}** ({top['bunk_pct']:.0f}% students missing)"

    with c1:
        st.info(f"🔍 {bunk_text}")

    # Energy waste card
    energy_text = "Energy data pending - timetable/attendance aur add karein."
    if not energy_df.empty:
        worst_room = (
            energy_df.groupby("room")["wasted_inr"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .iloc[0]
        )
        st.info(
            f"⚡ Room **{worst_room['room']}** me high waste (₹{worst_room['wasted_inr']:.0f} approx)."
        )
    else:
        with c2:
            st.info(f"⚡ {energy_text}")
        energy_text = None  # already used

    if energy_text is None:
        with c2:
            # Attendance suggestion
            st.info("📈 3 peak bunk slots fix karo → attendance +25% & energy -18% (estimate).")
    else:
        # energy already printed as generic
        pass

    with c3:
        st.info("💡 1-click SmartEdu Pulse: no hardware, sirf software – scalable 1000+ colleges.")

    # Simple attendance vs waste plot
    st.markdown("---")
    st.markdown("#### 📉 Attendance vs Energy Waste (Demo Overview)")

    if not lecture_summary_df.empty and not energy_df.empty:
        merged = lecture_summary_df.merge(
            energy_df[["lecture_id", "wasted_inr"]],
            on="lecture_id",
            how="left"
        ).fillna(0.0)

        fig = px.scatter(
            merged,
            x="attendance_pct",
            y="wasted_inr",
            hover_data=["subject", "room", "day", "time"],
            labels={
                "attendance_pct": "Attendance (%)",
                "wasted_inr": "Wasted Energy (₹)"
            },
            title="Low Attendance → High Energy Waste Spots"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Attendance ya energy data sufficient nahi – thoda demo attendance mark karein.")


# ---------- Page 2: Attendance + Stay Graph ----------

def render_attendance_page(students_df, timetable_df, att_detail_df, lecture_summary_df):
    st.subheader("📋 Smart Attendance (IN/OUT + Stay Duration)")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### 🎟️ Quick Scan IN/OUT")

        if students_df.empty or timetable_df.empty:
            st.warning("Students / Timetable data nahi mila. Pehle CSV upload karein ya default seed use karein.")
            return

        student_sel = st.selectbox(
            "Student select karein",
            options=students_df["id"],
            format_func=lambda i: f"{i} - {students_df.loc[students_df['id'] == i, 'name'].values[0]}"
        )

        lecture_sel = st.selectbox(
            "Current Lecture select karein",
            options=timetable_df["lecture_id"],
            format_func=lambda lid: f"{lid} - {timetable_df.loc[timetable_df['lecture_id'] == lid, 'subject'].values[0]} ({timetable_df.loc[timetable_df['lecture_id'] == lid, 'day'].values[0]} {timetable_df.loc[timetable_df['lecture_id'] == lid, 'time'].values[0]})"
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Scan IN"):
                record_attendance(student_sel, lecture_sel, "IN")
                st.success("IN scan recorded ✅ (entry DB me save ho gayi).")

        with c2:
            if st.button("Scan OUT"):
                record_attendance(student_sel, lecture_sel, "OUT")
                st.success("OUT scan recorded ✅ (exit DB me save ho gayi).")

        st.caption("Yeh simple fingerprint/button simulation hai – real hardware ke bina pure software demo.")

    with col_right:
        st.markdown("#####  Raw Attendance Logs (Latest)")

        att_df = load_attendance_df()
        if att_df.empty:
            st.write("Abhi tak koi attendance record nahi hai.")
        else:
            # Join for readability - include time column
            df = att_df.merge(students_df, left_on="student_id", right_on="id", how="left")
            df = df.merge(timetable_df, on="lecture_id", how="left")
            df = df[["time", "action", "name", "batch", "subject", "day", "time_y", "room"]]
            df = df.rename(columns={"time_y": "slot"})
            df = df.sort_values("time", ascending=False)
            st.dataframe(df.head(50), use_container_width=True)

    st.markdown("---")
    st.markdown("##### ⏱️ Stay Duration per Lecture")

    if lecture_summary_df.empty:
        st.write("Stay duration nikalne ke liye IN/OUT data chahiye – thoda scans run karein.")
        return

    st.dataframe(lecture_summary_df, use_container_width=True)

    fig = px.bar(
        lecture_summary_df,
        x="subject",
        y="avg_duration_min",
        color="room",
        hover_data=["day", "time", "attendance_pct"],
        labels={"avg_duration_min": "Average Stay (min)"},
        title="Average Stay Time per Subject"
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------- Page 3: Timetable CSV Upload ----------

def render_timetable_page(timetable_df):
    st.subheader("📂 Timetable CSV Upload + View")

    st.markdown("""
**CSV Format (exact columns):**  
`lecture_id,day,time,subject,room`  
Example row: `L10,Mon,09:00-10:00,DSA,R101`
    """)

    uploaded = st.file_uploader("Timetable CSV choose karein", type=["csv"])
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
            required_cols = {"lecture_id", "day", "time", "subject", "room"}
            if not required_cols.issubset(df.columns):
                st.error(f"CSV me yeh columns honi chahiye: {required_cols}")
            else:
                conn = get_conn()
                cur = conn.cursor()
                # Purani timetable clear karke fresh upload
                cur.execute("DELETE FROM timetable")
                conn.commit()

                df.to_sql("timetable", conn, if_exists="append", index=False)
                conn.close()
                st.success("Timetable CSV successfully import ho gaya ✅")
                timetable_df = df
        except Exception as e:
            st.error(f"CSV read error: {e}")

    st.markdown("##### Current Timetable")
    if timetable_df.empty:
        st.write("Abhi timetable empty hai.")
    else:
        st.dataframe(timetable_df, use_container_width=True)


# ---------- Page 4: Bunk Heatmap + Triggers ----------

def render_bunk_page(bunk_pairs_df, bunk_heatmap_df):
    st.subheader("🚫 Bunk Heatmap + Top Triggers")

    if bunk_pairs_df.empty:
        st.info("Bunk analysis ke liye attendance data kam hai. Thoda IN/OUT run karke wapas aayen.")
        return

    # Top triggers table
    st.markdown("##### 🔝 Top Bunk Triggers (Lecture → Lecture)")
    top_n = st.slider("Top N pairs dikhayein", 3, 10, 5)
    st.dataframe(
        bunk_pairs_df.head(top_n)[
            ["from_subject", "to_subject", "bunk_pct", "bunk_count", "base_present_count"]
        ],
        use_container_width=True
    )

    # Specific DSA→WCC highlight
    dsa_wcc = bunk_pairs_df[
        (bunk_pairs_df["from_subject"].str.upper() == "DSA") &
        (bunk_pairs_df["to_subject"].str.upper().str.contains("WCC"))
    ]
    if not dsa_wcc.empty:
        val = dsa_wcc.iloc[0]["bunk_pct"]
        st.success(f"🔍 Highlight: **DSA → WCC** bunk ≈ **{val:.0f}%** (sheet example jaisa pattern).")
    else:
        st.warning("DSA → WCC pair abhi data me strong nahi dikha – demo ke liye kuch scans add karein.")

    st.markdown("##### 🌡️ Subject-to-Subject Bunk Heatmap")
    if bunk_heatmap_df.empty:
        st.write("Heatmap ke liye sufficient pairs nahi mile.")
    else:
        fig = px.imshow(
            bunk_heatmap_df,
            labels=dict(x="Next Subject", y="Previous Subject", color="% Bunk"),
            color_continuous_scale="Reds",
            text_auto=True
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)


# ---------- Page 5: Energy Digital Twin ----------

def render_energy_page(energy_df, rooms_df):
    st.subheader("⚡ Energy Digital Twin - Room Status")

    if rooms_df.empty:
        st.warning("Rooms table empty hai.")
        return

    st.markdown("Digital twin: har room ka **occupancy vs energy waste** status (🟢, 🟡, 🔴).")

    # Room-wise aggregation
    if energy_df.empty:
        # Koi attendance nahi to assumption: low occupancy → yellow
        room_status = []
        for _, r in rooms_df.iterrows():
            room_status.append({
                "room": r["room_id"],
                "status": "🟡 Low Utilisation (no data)",
                "waste_inr": 0.0,
                "occupancy": 0.0
            })
        status_df = pd.DataFrame(room_status)
    else:
        grouped = (
            energy_df.groupby("room")
            .agg(
                total_waste_inr=("wasted_inr", "sum"),
                avg_occupancy=("occupancy", "mean")
            )
            .reset_index()
        )
        status = []
        for _, row in grouped.iterrows():
            occ = row["avg_occupancy"]
            waste = row["total_waste_inr"]
            if occ >= 0.7:
                icon = "🟢"
                text = "Good Utilisation"
            elif occ > 0:
                icon = "🟡"
                text = "Low Occupancy"
            else:
                icon = "🔴"
                text = "No Attendance (Pure Waste)"
            status.append({
                "room": row["room"],
                "icon": icon,
                "status_text": text,
                "waste_inr": waste,
                "occupancy": occ
            })
        status_df = pd.DataFrame(status)

    # Grid layout - 2 per row
    cols = st.columns(2)
    for idx, row in status_df.iterrows():
        col = cols[idx % 2]
        with col:
            icon = row.get("icon", "🟡")
            occ = row.get("occupancy", 0.0)
            waste = row.get("waste_inr", 0.0)
            text = row.get("status_text", row.get("status", "Status Unknown"))
            st.markdown(f"### {icon} Room {row['room']}")
            st.write(f"Status: **{text}**")
            st.write(f"Avg Occupancy: **{occ*100:.1f}%**")
            st.write(f"Estimated Waste: **₹{waste:,.0f}**")

    st.markdown("---")
    st.markdown("##### 🔴 Example: R102 High Waste Story")
    st.write("Pitch ke liye aap yeh bol sakte ho: *“R102 me sirf 18% occupancy, lekin pura 1.5kW fan+light chal rahe – pure waste.”*")


# ---------- Page 6: Free Rooms Finder ----------

def render_free_rooms_page(timetable_df, rooms_df):
    st.subheader("🏫 Free Rooms Finder")

    if rooms_df.empty or timetable_df.empty:
        st.warning("Rooms / Timetable data missing hai.")
        return

    unique_days = sorted(timetable_df["day"].unique().tolist())
    unique_times = sorted(timetable_df["time"].unique().tolist())

    c1, c2 = st.columns(2)
    with c1:
        day_sel = st.selectbox("Day select karein", unique_days)
    with c2:
        time_sel = st.selectbox("Time slot select karein", unique_times)

    free_rooms = get_free_rooms(day_sel, time_sel)

    st.markdown("##### Results")
    if not free_rooms:
        st.error("Is slot me koi free room nahi mila.")
    else:
        st.success(f"Free rooms for **{day_sel} {time_sel}**: {', '.join(free_rooms)}")

    st.caption("Yeh feature timetable par based hai, attendance ke bagair bhi kaam karega.")


# ---------- Page 7: Reports / CSV Export ----------

def render_reports_page(att_detail_df, lecture_summary_df, bunk_pairs_df, energy_df):
    st.subheader("📦 Reports / CSV Export")

    st.markdown("Yahan se aap **CSV export** kar sakte hain for hackathon demo / PPT.")

    if att_detail_df.empty and lecture_summary_df.empty and bunk_pairs_df.empty and energy_df.empty:
        st.info("Abhi tak analysis tables empty hain. Attendance & timetable data add karke wapas aayen.")
        return

    def download_section(label, df):
        st.markdown(f"##### {label}")
        if df.empty:
            st.write("No data.")
            return
        st.dataframe(df.head(100), use_container_width=True)
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Download {label} CSV",
            csv_data,
            file_name=f"{label.lower().replace(' ', '_')}.csv",
            mime="text/csv"
        )
        st.markdown("---")

    download_section("Attendance Detail", att_detail_df)
    download_section("Lecture-wise Attendance Summary", lecture_summary_df)
    download_section("Bunk Trigger Pairs", bunk_pairs_df)
    download_section("Energy Waste per Lecture", energy_df)


# ---------- Run App ----------

if __name__ == "__main__":
=======
import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from datetime import datetime
import os

# =========================================================
# SMARTEDU PULSE - STREAMLIT APP
# Attendance + Bunk + Energy + Digital Twin + Free Rooms
# Hindi-English comments inside code
# =========================================================

DB_PATH = "smartedu_pulse.db"

# ---------- DB Helpers ----------

def get_conn():
    # SQLite connection - simple local DB (suppress Python 3.12 deprecation)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DB tables create + demo seed data (agar empty ho)."""
    conn = get_conn()
    cur = conn.cursor()

    # students(id,name,batch)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            batch TEXT NOT NULL
        )
    """)

    # timetable(lecture_id,day,time,subject,room)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS timetable(
            lecture_id TEXT PRIMARY KEY,
            day TEXT NOT NULL,
            time TEXT NOT NULL,
            subject TEXT NOT NULL,
            room TEXT NOT NULL
        )
    """)

    # attendance(student_id,lecture_id,action,time)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            lecture_id TEXT NOT NULL,
            action TEXT NOT NULL,           -- 'IN' / 'OUT'
            time TIMESTAMP NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(lecture_id) REFERENCES timetable(lecture_id)
        )
    """)

    # rooms(room_id,power_kw,capacity)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms(
            room_id TEXT PRIMARY KEY,
            power_kw REAL NOT NULL,
            capacity INTEGER NOT NULL
        )
    """)

    # Seed students agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM students")
    if cur.fetchone()["c"] == 0:
        demo_students = [
            ("Ansh", "CSE-A"),
            ("Priya", "CSE-A"),
            ("Rohan", "CSE-A"),
            ("Simran", "CSE-A"),
            ("Kabir", "CSE-A"),
            ("Aisha", "CSE-A"),
            ("Vikram", "CSE-A"),
            ("Neha", "CSE-A"),
            ("Arjun", "CSE-A"),
            ("Isha", "CSE-A"),
        ]
        cur.executemany(
            "INSERT INTO students(name,batch) VALUES(?,?)",
            demo_students
        )

    # Seed rooms agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM rooms")
    if cur.fetchone()["c"] == 0:
        demo_rooms = [
            ("R101", 1.2, 60),
            ("R102", 1.5, 80),
            ("R103", 1.0, 50),
            ("Lab1", 2.0, 40),
        ]
        cur.executemany(
            "INSERT INTO rooms(room_id,power_kw,capacity) VALUES(?,?,?)",
            demo_rooms
        )

    # Seed timetable agar khali hai
    cur.execute("SELECT COUNT(*) AS c FROM timetable")
    if cur.fetchone()["c"] == 0:
        # NOTE: time format "HH:MM-HH:MM" taaki duration nikal saken
        demo_tt = [
            ("L1", "Mon", "09:00-10:00", "DSA", "R101"),
            ("L2", "Mon", "10:00-11:00", "WCC", "R101"),
            ("L3", "Mon", "11:00-12:00", "OS", "R102"),
            ("L4", "Tue", "09:00-10:00", "DBMS", "R101"),
            ("L5", "Tue", "10:00-11:00", "WCC", "R102"),
            ("L6", "Wed", "09:00-10:00", "DSA", "R103"),
        ]
        cur.executemany(
            "INSERT INTO timetable(lecture_id,day,time,subject,room) VALUES(?,?,?,?,?)",
            demo_tt
        )

    conn.commit()
    conn.close()


def parse_time_range(time_str):
    """
    Timetable ke time column ka format:
    - "09:00-10:00" → start, end
    - Agar sirf "09:00" ho, to 1 hour assume.
    """
    try:
        if "-" in time_str:
            start_s, end_s = time_str.split("-")
            start = datetime.strptime(start_s.strip(), "%H:%M")
            end = datetime.strptime(end_s.strip(), "%H:%M")
        else:
            start = datetime.strptime(time_str.strip(), "%H:%M")
            end = start.replace(hour=(start.hour + 1) % 24)
        return start, end
    except Exception:
        # Koi parsing error ho to default 1 hour
        now = datetime.now()
        start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end = now.replace(hour=10, minute=0, second=0, microsecond=0)
        return start, end


# ---------- Data Load Helpers ----------

def load_students_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM students ORDER BY id", conn)
    conn.close()
    return df


def load_rooms_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM rooms ORDER BY room_id", conn)
    conn.close()
    return df


def load_timetable_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM timetable ORDER BY day, time", conn)
    conn.close()
    return df


def load_attendance_df():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM attendance", conn, parse_dates=["time"])
    conn.close()
    return df


# ---------- Attendance Logic ----------

def record_attendance(student_id, lecture_id, action):
    """Attendance scan IN/OUT record kare (current time ke saath)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO attendance(student_id,lecture_id,action,time) VALUES(?,?,?,?)",
        (int(student_id), lecture_id, action, datetime.now())
    )
    conn.commit()
    conn.close()


def build_attendance_summary():
    """
    Attendance summary:
    - Har (student, lecture) ke liye duration (minutes) nikalna (OUT - IN).
    - Present tab manenge jab duration >= 30 min (configurable).
    """
    students = load_students_df()
    timetable = load_timetable_df()
    att = load_attendance_df()

    if att.empty:
        return pd.DataFrame(), pd.DataFrame(), 0.0

    # IN/OUT ko group karke earliest IN & latest OUT nikalna
    grouped = (
        att.groupby(["student_id", "lecture_id", "action"])["time"]
        .agg(["min", "max"])
        .reset_index()
    )

    # Pivot: IN / OUT alag columns
    pivot = grouped.pivot_table(
        index=["student_id", "lecture_id"],
        columns="action",
        values="min",  # 'min' hi sufficient hai (per action)
        aggfunc="first"
    ).reset_index()

    # Column names flatten
    pivot.columns.name = None

    # Duration minutes
    def calc_duration(row):
        t_in = row.get("IN")
        t_out = row.get("OUT")
        if pd.isna(t_in) or pd.isna(t_out):
            return 0.0
        return (t_out - t_in).total_seconds() / 60.0

    pivot["duration_min"] = pivot.apply(calc_duration, axis=1)

    # Present flag (>= 30 min)
    MIN_PRESENT_MIN = 30
    pivot["present"] = pivot["duration_min"] >= MIN_PRESENT_MIN

    # Join students + timetable for readable info
    pivot = pivot.merge(students, left_on="student_id", right_on="id", how="left")
    pivot = pivot.merge(timetable, on="lecture_id", how="left")

    # Lecture-wise summary
    lecture_summary = (
        pivot.groupby(["lecture_id", "day", "time", "subject", "room"])
        .agg(
            total_students=("student_id", "nunique"),
            present_students=("present", "sum"),
            avg_duration_min=("duration_min", "mean"),
        )
        .reset_index()
    )
    lecture_summary["attendance_pct"] = (
        lecture_summary["present_students"] * 100.0 / lecture_summary["total_students"].clip(lower=1)
    )

    # Overall avg attendance
    overall_attendance = lecture_summary["attendance_pct"].mean() if not lecture_summary.empty else 0.0

    return pivot, lecture_summary, overall_attendance


# ---------- Bunk Analysis ----------

def compute_bunk_triggers(att_summary_df, lecture_summary_df, students_df):
    """
    Bunk trigger detector:
    - Consecutive lectures ke pairs (same day + batch approximate).
    - Pair (A->B) ke liye:
        % bunk = students who were present in A but absent in B.
    """
    if att_summary_df.empty or lecture_summary_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Timetable with ordered index
    tt = load_timetable_df().copy()
    # Time ko sortable banane ke liye start time parse
    tt["start_time_obj"] = tt["time"].apply(lambda x: parse_time_range(x)[0])
    tt = tt.sort_values(["day", "start_time_obj"]).reset_index(drop=True)

    # consecutive pairs
    pairs = []
    for idx in range(len(tt) - 1):
        row_a = tt.iloc[idx]
        row_b = tt.iloc[idx + 1]
        # Same room/batch approx - yaha simple rule: same day & same batch (all CSE-A demo)
        if row_a["day"] == row_b["day"]:
            pairs.append((row_a["lecture_id"], row_b["lecture_id"]))

    if not pairs:
        return pd.DataFrame(), pd.DataFrame()

    pair_stats = []
    for l1, l2 in pairs:
        a1 = att_summary_df[att_summary_df["lecture_id"] == l1]
        a2 = att_summary_df[att_summary_df["lecture_id"] == l2]

        # Students set - currently all same batch, to be safe use intersection
        students_present_l1 = set(a1.loc[a1["present"], "student_id"].tolist())
        students_present_l2 = set(a2.loc[a2["present"], "student_id"].tolist())

        if not students_present_l1:
            continue

        bunkers = students_present_l1 - students_present_l2
        bunk_pct = len(bunkers) * 100.0 / len(students_present_l1)

        subj1 = tt.loc[tt["lecture_id"] == l1, "subject"].values[0]
        subj2 = tt.loc[tt["lecture_id"] == l2, "subject"].values[0]

        pair_stats.append({
            "from_lecture": l1,
            "to_lecture": l2,
            "from_subject": subj1,
            "to_subject": subj2,
            "bunk_pct": bunk_pct,
            "bunk_count": len(bunkers),
            "base_present_count": len(students_present_l1),
        })

    if not pair_stats:
        return pd.DataFrame(), pd.DataFrame()

    pair_df = pd.DataFrame(pair_stats).sort_values("bunk_pct", ascending=False)

    # Heatmap ke liye pivot (subject-wise)
    heatmap_df = pair_df.pivot_table(
        index="from_subject",
        columns="to_subject",
        values="bunk_pct",
        aggfunc="mean"
    ).fillna(0.0)

    return pair_df, heatmap_df


# ---------- Energy Analytics ----------

def compute_energy_waste(lecture_summary_df, rooms_df, cost_per_kwh=8.0):
    """
    Energy calculator:
    - Har lecture ke liye:
        occupancy = present / capacity
        duration_hours from timetable time
        energy_used = power_kw * duration_hours
        waste_factor = (1 - occupancy)
        wasted_energy = energy_used * waste_factor
    """
    tt = load_timetable_df()
    if lecture_summary_df.empty or tt.empty or rooms_df.empty:
        return pd.DataFrame(), 0.0, 0.0

    # Merge timetable + rooms + attendance summary
    df = lecture_summary_df.merge(tt, on=["lecture_id", "day", "time", "subject", "room"], how="left")
    df = df.merge(rooms_df, left_on="room", right_on="room_id", how="left")

    # Duration hours
    def duration_hrs(row):
        start, end = parse_time_range(row["time"])
        return (end - start).total_seconds() / 3600.0

    df["duration_h"] = df.apply(duration_hrs, axis=1)
    # Occupancy
    df["occupancy"] = df["present_students"] / df["capacity"].clip(lower=1)

    # Energy used (ideal full utilisation) & waste
    df["energy_kwh"] = df["power_kw"] * df["duration_h"]
    df["waste_factor"] = (1.0 - df["occupancy"]).clip(lower=0.0, upper=1.0)
    df["wasted_kwh"] = df["energy_kwh"] * df["waste_factor"]
    df["wasted_inr"] = df["wasted_kwh"] * cost_per_kwh

    total_waste_inr = df["wasted_inr"].sum()
    total_energy_inr = (df["energy_kwh"] * cost_per_kwh).sum()
    waste_pct = (total_waste_inr * 100.0 / total_energy_inr) if total_energy_inr > 0 else 0.0

    return df, total_waste_inr, waste_pct


# ---------- Free Rooms Finder ----------

def get_free_rooms(selected_day, selected_time):
    """
    Free rooms finder:
    - Selected day + time slot ke liye timetable check karo.
    - Jis room me us slot ka lecture nahi hai → free.
    """
    rooms = load_rooms_df()
    tt = load_timetable_df()

    if rooms.empty:
        return []

    # Filter timetable on same day and exact time string
    busy = tt[(tt["day"] == selected_day) & (tt["time"] == selected_time)]
    busy_rooms = set(busy["room"].tolist())

    all_rooms = set(rooms["room_id"].tolist())
    free_rooms = sorted(list(all_rooms - busy_rooms))
    return free_rooms


# =========================================================
# STREAMLIT UI
# =========================================================

def main():
    init_db()

    st.set_page_config(
        page_title="SmartEdu Pulse",
        page_icon="📊",
        layout="wide"
    )

    st.title("🎓 SmartEdu Pulse - Smart Classroom Analytics")
    st.caption("Smart Attendance + Bunk Detector + Energy Waste + Digital Twin + Free Rooms (Software Only)")

    # Sidebar navigation - 7 screens
    pages = {
        "1️⃣ Dashboard": "dashboard",
        "2️⃣ Attendance + Stay Graph": "attendance",
        "3️⃣ Timetable CSV Upload": "timetable",
        "4️⃣ Bunk Heatmap + Triggers": "bunk",
        "5️⃣ Energy Digital Twin": "energy",
        "6️⃣ Free Rooms Finder": "free_rooms",
        "7️⃣ Reports / CSV Export": "reports"
    }

    choice = st.sidebar.radio("Screens", list(pages.keys()))
    page = pages[choice]

    # Load base data
    students_df = load_students_df()
    rooms_df = load_rooms_df()
    timetable_df = load_timetable_df()
    att_df = load_attendance_df()
    att_detail_df, lecture_summary_df, overall_attendance = build_attendance_summary()
    bunk_pairs_df, bunk_heatmap_df = compute_bunk_triggers(
        att_detail_df, lecture_summary_df, students_df
    )
    energy_df, total_waste_inr, waste_pct = compute_energy_waste(
        lecture_summary_df, rooms_df
    )

    if page == "dashboard":
        render_dashboard(
            students_df,
            timetable_df,
            att_detail_df,
            lecture_summary_df,
            bunk_pairs_df,
            energy_df,
            total_waste_inr,
            waste_pct,
            overall_attendance
        )
    elif page == "attendance":
        render_attendance_page(
            students_df,
            timetable_df,
            att_detail_df,
            lecture_summary_df
        )
    elif page == "timetable":
        render_timetable_page(timetable_df)
    elif page == "bunk":
        render_bunk_page(bunk_pairs_df, bunk_heatmap_df)
    elif page == "energy":
        render_energy_page(energy_df, rooms_df)
    elif page == "free_rooms":
        render_free_rooms_page(timetable_df, rooms_df)
    elif page == "reports":
        render_reports_page(att_detail_df, lecture_summary_df, bunk_pairs_df, energy_df)


# ---------- Page 1: Dashboard ----------

def render_dashboard(
    students_df,
    timetable_df,
    att_detail_df,
    lecture_summary_df,
    bunk_pairs_df,
    energy_df,
    total_waste_inr,
    waste_pct,
    overall_attendance
):
    st.subheader("📊 Overall Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_students = len(students_df)
        st.metric("Total Students", total_students)

    with col2:
        total_lectures = len(timetable_df)
        st.metric("Timetable Lectures", total_lectures)

    with col3:
        st.metric("Avg Attendance %", f"{overall_attendance:.1f}%")

    with col4:
        monthly_est_waste = total_waste_inr * 22  # approx 22 working days
        st.metric("Est. Monthly Waste (₹)", f"{monthly_est_waste:,.0f}")

    # Insights cards - Hindi-English copy (pitch ke hisaab se)
    st.markdown("---")
    st.markdown("#### 🔍 Insight Cards")

    c1, c2, c3 = st.columns(3)

    # Top bunk pair
    bunk_text = "Data kam hai - bunk pattern abhi clear nahi."
    if not bunk_pairs_df.empty:
        top = bunk_pairs_df.iloc[0]
        bunk_text = f"Top bunk: **{top['from_subject']} → {top['to_subject']}** ({top['bunk_pct']:.0f}% students missing)"

    with c1:
        st.info(f"🔍 {bunk_text}")

    # Energy waste card
    energy_text = "Energy data pending - timetable/attendance aur add karein."
    if not energy_df.empty:
        worst_room = (
            energy_df.groupby("room")["wasted_inr"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .iloc[0]
        )
        st.info(
            f"⚡ Room **{worst_room['room']}** me high waste (₹{worst_room['wasted_inr']:.0f} approx)."
        )
    else:
        with c2:
            st.info(f"⚡ {energy_text}")
        energy_text = None  # already used

    if energy_text is None:
        with c2:
            # Attendance suggestion
            st.info("📈 3 peak bunk slots fix karo → attendance +25% & energy -18% (estimate).")
    else:
        # energy already printed as generic
        pass

    with c3:
        st.info("💡 1-click SmartEdu Pulse: no hardware, sirf software – scalable 1000+ colleges.")

    # Simple attendance vs waste plot
    st.markdown("---")
    st.markdown("#### 📉 Attendance vs Energy Waste (Demo Overview)")

    if not lecture_summary_df.empty and not energy_df.empty:
        merged = lecture_summary_df.merge(
            energy_df[["lecture_id", "wasted_inr"]],
            on="lecture_id",
            how="left"
        ).fillna(0.0)

        fig = px.scatter(
            merged,
            x="attendance_pct",
            y="wasted_inr",
            hover_data=["subject", "room", "day", "time"],
            labels={
                "attendance_pct": "Attendance (%)",
                "wasted_inr": "Wasted Energy (₹)"
            },
            title="Low Attendance → High Energy Waste Spots"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("Attendance ya energy data sufficient nahi – thoda demo attendance mark karein.")


# ---------- Page 2: Attendance + Stay Graph ----------

def render_attendance_page(students_df, timetable_df, att_detail_df, lecture_summary_df):
    st.subheader("📋 Smart Attendance (IN/OUT + Stay Duration)")

    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### 🎟️ Quick Scan IN/OUT")

        if students_df.empty or timetable_df.empty:
            st.warning("Students / Timetable data nahi mila. Pehle CSV upload karein ya default seed use karein.")
            return

        student_sel = st.selectbox(
            "Student select karein",
            options=students_df["id"],
            format_func=lambda i: f"{i} - {students_df.loc[students_df['id'] == i, 'name'].values[0]}"
        )

        lecture_sel = st.selectbox(
            "Current Lecture select karein",
            options=timetable_df["lecture_id"],
            format_func=lambda lid: f"{lid} - {timetable_df.loc[timetable_df['lecture_id'] == lid, 'subject'].values[0]} ({timetable_df.loc[timetable_df['lecture_id'] == lid, 'day'].values[0]} {timetable_df.loc[timetable_df['lecture_id'] == lid, 'time'].values[0]})"
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Scan IN"):
                record_attendance(student_sel, lecture_sel, "IN")
                st.success("IN scan recorded ✅ (entry DB me save ho gayi).")

        with c2:
            if st.button("Scan OUT"):
                record_attendance(student_sel, lecture_sel, "OUT")
                st.success("OUT scan recorded ✅ (exit DB me save ho gayi).")

        st.caption("Yeh simple fingerprint/button simulation hai – real hardware ke bina pure software demo.")

    with col_right:
        st.markdown("#####  Raw Attendance Logs (Latest)")

        att_df = load_attendance_df()
        if att_df.empty:
            st.write("Abhi tak koi attendance record nahi hai.")
        else:
            # Join for readability - include time column
            df = att_df.merge(students_df, left_on="student_id", right_on="id", how="left")
            df = df.merge(timetable_df, on="lecture_id", how="left")
            df = df[["time", "action", "name", "batch", "subject", "day", "time_y", "room"]]
            df = df.rename(columns={"time_y": "slot"})
            df = df.sort_values("time", ascending=False)
            st.dataframe(df.head(50), use_container_width=True)

    st.markdown("---")
    st.markdown("##### ⏱️ Stay Duration per Lecture")

    if lecture_summary_df.empty:
        st.write("Stay duration nikalne ke liye IN/OUT data chahiye – thoda scans run karein.")
        return

    st.dataframe(lecture_summary_df, use_container_width=True)

    fig = px.bar(
        lecture_summary_df,
        x="subject",
        y="avg_duration_min",
        color="room",
        hover_data=["day", "time", "attendance_pct"],
        labels={"avg_duration_min": "Average Stay (min)"},
        title="Average Stay Time per Subject"
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------- Page 3: Timetable CSV Upload ----------

def render_timetable_page(timetable_df):
    st.subheader("📂 Timetable CSV Upload + View")

    st.markdown("""
**CSV Format (exact columns):**  
`lecture_id,day,time,subject,room`  
Example row: `L10,Mon,09:00-10:00,DSA,R101`
    """)

    uploaded = st.file_uploader("Timetable CSV choose karein", type=["csv"])
    if uploaded is not None:
        try:
            df = pd.read_csv(uploaded)
            required_cols = {"lecture_id", "day", "time", "subject", "room"}
            if not required_cols.issubset(df.columns):
                st.error(f"CSV me yeh columns honi chahiye: {required_cols}")
            else:
                conn = get_conn()
                cur = conn.cursor()
                # Purani timetable clear karke fresh upload
                cur.execute("DELETE FROM timetable")
                conn.commit()

                df.to_sql("timetable", conn, if_exists="append", index=False)
                conn.close()
                st.success("Timetable CSV successfully import ho gaya ✅")
                timetable_df = df
        except Exception as e:
            st.error(f"CSV read error: {e}")

    st.markdown("##### Current Timetable")
    if timetable_df.empty:
        st.write("Abhi timetable empty hai.")
    else:
        st.dataframe(timetable_df, use_container_width=True)


# ---------- Page 4: Bunk Heatmap + Triggers ----------

def render_bunk_page(bunk_pairs_df, bunk_heatmap_df):
    st.subheader("🚫 Bunk Heatmap + Top Triggers")

    if bunk_pairs_df.empty:
        st.info("Bunk analysis ke liye attendance data kam hai. Thoda IN/OUT run karke wapas aayen.")
        return

    # Top triggers table
    st.markdown("##### 🔝 Top Bunk Triggers (Lecture → Lecture)")
    top_n = st.slider("Top N pairs dikhayein", 3, 10, 5)
    st.dataframe(
        bunk_pairs_df.head(top_n)[
            ["from_subject", "to_subject", "bunk_pct", "bunk_count", "base_present_count"]
        ],
        use_container_width=True
    )

    # Specific DSA→WCC highlight
    dsa_wcc = bunk_pairs_df[
        (bunk_pairs_df["from_subject"].str.upper() == "DSA") &
        (bunk_pairs_df["to_subject"].str.upper().str.contains("WCC"))
    ]
    if not dsa_wcc.empty:
        val = dsa_wcc.iloc[0]["bunk_pct"]
        st.success(f"🔍 Highlight: **DSA → WCC** bunk ≈ **{val:.0f}%** (sheet example jaisa pattern).")
    else:
        st.warning("DSA → WCC pair abhi data me strong nahi dikha – demo ke liye kuch scans add karein.")

    st.markdown("##### 🌡️ Subject-to-Subject Bunk Heatmap")
    if bunk_heatmap_df.empty:
        st.write("Heatmap ke liye sufficient pairs nahi mile.")
    else:
        fig = px.imshow(
            bunk_heatmap_df,
            labels=dict(x="Next Subject", y="Previous Subject", color="% Bunk"),
            color_continuous_scale="Reds",
            text_auto=True
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)


# ---------- Page 5: Energy Digital Twin ----------

def render_energy_page(energy_df, rooms_df):
    st.subheader("⚡ Energy Digital Twin - Room Status")

    if rooms_df.empty:
        st.warning("Rooms table empty hai.")
        return

    st.markdown("Digital twin: har room ka **occupancy vs energy waste** status (🟢, 🟡, 🔴).")

    # Room-wise aggregation
    if energy_df.empty:
        # Koi attendance nahi to assumption: low occupancy → yellow
        room_status = []
        for _, r in rooms_df.iterrows():
            room_status.append({
                "room": r["room_id"],
                "status": "🟡 Low Utilisation (no data)",
                "waste_inr": 0.0,
                "occupancy": 0.0
            })
        status_df = pd.DataFrame(room_status)
    else:
        grouped = (
            energy_df.groupby("room")
            .agg(
                total_waste_inr=("wasted_inr", "sum"),
                avg_occupancy=("occupancy", "mean")
            )
            .reset_index()
        )
        status = []
        for _, row in grouped.iterrows():
            occ = row["avg_occupancy"]
            waste = row["total_waste_inr"]
            if occ >= 0.7:
                icon = "🟢"
                text = "Good Utilisation"
            elif occ > 0:
                icon = "🟡"
                text = "Low Occupancy"
            else:
                icon = "🔴"
                text = "No Attendance (Pure Waste)"
            status.append({
                "room": row["room"],
                "icon": icon,
                "status_text": text,
                "waste_inr": waste,
                "occupancy": occ
            })
        status_df = pd.DataFrame(status)

    # Grid layout - 2 per row
    cols = st.columns(2)
    for idx, row in status_df.iterrows():
        col = cols[idx % 2]
        with col:
            icon = row.get("icon", "🟡")
            occ = row.get("occupancy", 0.0)
            waste = row.get("waste_inr", 0.0)
            text = row.get("status_text", row.get("status", "Status Unknown"))
            st.markdown(f"### {icon} Room {row['room']}")
            st.write(f"Status: **{text}**")
            st.write(f"Avg Occupancy: **{occ*100:.1f}%**")
            st.write(f"Estimated Waste: **₹{waste:,.0f}**")

    st.markdown("---")
    st.markdown("##### 🔴 Example: R102 High Waste Story")
    st.write("Pitch ke liye aap yeh bol sakte ho: *“R102 me sirf 18% occupancy, lekin pura 1.5kW fan+light chal rahe – pure waste.”*")


# ---------- Page 6: Free Rooms Finder ----------

def render_free_rooms_page(timetable_df, rooms_df):
    st.subheader("🏫 Free Rooms Finder")

    if rooms_df.empty or timetable_df.empty:
        st.warning("Rooms / Timetable data missing hai.")
        return

    unique_days = sorted(timetable_df["day"].unique().tolist())
    unique_times = sorted(timetable_df["time"].unique().tolist())

    c1, c2 = st.columns(2)
    with c1:
        day_sel = st.selectbox("Day select karein", unique_days)
    with c2:
        time_sel = st.selectbox("Time slot select karein", unique_times)

    free_rooms = get_free_rooms(day_sel, time_sel)

    st.markdown("##### Results")
    if not free_rooms:
        st.error("Is slot me koi free room nahi mila.")
    else:
        st.success(f"Free rooms for **{day_sel} {time_sel}**: {', '.join(free_rooms)}")

    st.caption("Yeh feature timetable par based hai, attendance ke bagair bhi kaam karega.")


# ---------- Page 7: Reports / CSV Export ----------

def render_reports_page(att_detail_df, lecture_summary_df, bunk_pairs_df, energy_df):
    st.subheader("📦 Reports / CSV Export")

    st.markdown("Yahan se aap **CSV export** kar sakte hain for hackathon demo / PPT.")

    if att_detail_df.empty and lecture_summary_df.empty and bunk_pairs_df.empty and energy_df.empty:
        st.info("Abhi tak analysis tables empty hain. Attendance & timetable data add karke wapas aayen.")
        return

    def download_section(label, df):
        st.markdown(f"##### {label}")
        if df.empty:
            st.write("No data.")
            return
        st.dataframe(df.head(100), use_container_width=True)
        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Download {label} CSV",
            csv_data,
            file_name=f"{label.lower().replace(' ', '_')}.csv",
            mime="text/csv"
        )
        st.markdown("---")

    download_section("Attendance Detail", att_detail_df)
    download_section("Lecture-wise Attendance Summary", lecture_summary_df)
    download_section("Bunk Trigger Pairs", bunk_pairs_df)
    download_section("Energy Waste per Lecture", energy_df)


# ---------- Run App ----------

if __name__ == "__main__":
>>>>>>> 81bf992d76a815cbb279ad7749e4cf614edd9542
    main()