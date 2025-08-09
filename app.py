# app.py — fresh, simple, and robust ✨

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# -----------------------------
# Page config & theme
# -----------------------------
st.set_page_config(page_title="CitiBike 2022 Dashboard", layout="wide")
st.title("🚲 CitiBike 2022 Dashboard")

# Colors (member = orange, casual = gold)
COLORS = {"member": "orange", "casual": "gold"}
WEEKDAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

# -----------------------------
# Sidebar: file inputs
# -----------------------------
st.sidebar.header("Data")
default_trip = "citibike_trip_sample.csv" if Path("citibike_trip_sample.csv").exists() else ""
csv_path = st.sidebar.text_input("Trips CSV path", value=default_trip, key="trip_csv_key")

weather_default = "citibike_weather_merged_2022.csv" if Path("citibike_weather_merged_2022.csv").exists() else ""
weather_path = st.sidebar.text_input("Weather CSV path (optional)", value=weather_default, key="weather_csv_key")

kepler_default = "citibike_trip_routes.html" if Path("citibike_trip_routes.html").exists() else ""
kepler_path = st.sidebar.text_input("Kepler map HTML (optional)", value=kepler_default, key="kepler_html_key")


# -----------------------------
# Helpers
# -----------------------------
@st.cache_data
def load_trips(path: str) -> pd.DataFrame:
    if not path or not Path(path).exists():
        # Tiny demo fallback so app still runs
        n = 400
        rng = pd.date_range("2022-01-01", periods=n, freq="6H")
        demo = pd.DataFrame({
            "ride_id": np.arange(n),
            "started_at": rng,
            "ended_at": rng + pd.to_timedelta(np.random.gamma(2, 8, size=n), unit="m"),
            "start_station_name": np.random.choice(
                ["W 21 St & 6 Ave","W 31 St & 7 Ave","E 40 St & Park Ave",
                 "Central Park West & W 72 St","West St & Liberty St"], size=n
            ),
            "member_casual": np.random.choice(["member","casual"], size=n, p=[0.78, 0.22])
        })
        demo["trip_duration_min"] = (demo["ended_at"] - demo["started_at"]).dt.total_seconds()/60
        return demo

    df = pd.read_csv(path, low_memory=False)
    return df


def normalize_trips(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    # --- standardize rider type to "member_casual"
    if "member_casual" not in d.columns:
        for alt in ["rider_type","member.casual","memberCasual"]:
            if alt in d.columns:
                d = d.rename(columns={alt: "member_casual"})
                break

    # --- ensure datetime columns and a date column
    date_col = None
    for c in ["date", "started_at", "start_time", "start_datetime"]:
        if c in d.columns:
            date_col = c
            break
    if date_col is None:
        st.error("Could not find a date column. Expected one of: date, started_at, start_time, start_datetime.")
        return d

    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    if date_col != "date":
        d["date"] = d[date_col]
    d["date"] = d["date"].dt.date
    d["date"] = pd.to_datetime(d["date"])

    # --- trip duration in minutes
    if "trip_duration_min" not in d.columns:
        # try a few possibilities
        guesses = ["trip_duration","duration_min","ride_length_min","ride_duration_min","tripduration_min"]
        made = False
        for g in guesses:
            if g in d.columns:
                d["trip_duration_min"] = d[g]
                made = True
                break
        if not made and "started_at" in d.columns and "ended_at" in d.columns:
            d["started_at"] = pd.to_datetime(d["started_at"], errors="coerce")
            d["ended_at"] = pd.to_datetime(d["ended_at"], errors="coerce")
            d["trip_duration_min"] = (d["ended_at"] - d["started_at"]).dt.total_seconds()/60

    # --- day of week (ordered for charts)
    d["day_of_week"] = d["date"].dt.day_name()
    d["day_of_week"] = pd.Categorical(d["day_of_week"], categories=WEEKDAY_ORDER, ordered=True)

    # --- month label for monthly trend
    d["month"] = d["date"].dt.to_period("M").astype(str)

    return d


@st.cache_data
def load_weather(path: str) -> pd.DataFrame | None:
    if not path or not Path(path).exists():
        return None
    w = pd.read_csv(path, parse_dates=["date"])
    w["date"] = w["date"].dt.date
    w["date"] = pd.to_datetime(w["date"])
    # find a usable average temperature column
    temp_col = next((c for c in ["avg_temp_f", "tavg_f", "tavg", "temp_avg_f", "avg_temp_f_tenths"] if c in w.columns), None)
    if temp_col == "avg_temp_f_tenths":
        w["avg_temp_f"] = w[temp_col] / 10.0
        temp_col = "avg_temp_f"
    return w[[c for c in w.columns if c in ["date", temp_col]]]


# -----------------------------
# Figure builders
# -----------------------------
def fig_distribution(df: pd.DataFrame) -> go.Figure:
    return px.box(
        df, x="member_casual", y="trip_duration_min",
        color="member_casual", color_discrete_map=COLORS,
        labels={"member_casual":"Rider Type", "trip_duration_min":"Trip Duration (min)"},
        title="Trip Duration Distribution by Rider Type"
    )


def fig_monthly_trend(df: pd.DataFrame) -> go.Figure:
    g = df.groupby(["month","member_casual"]).size().reset_index(name="rides")
    return px.bar(
        g, x="month", y="rides", color="member_casual",
        color_discrete_map=COLORS, barmode="stack",
        labels={"month":"Month", "rides":"Number of Rides", "member_casual":"Rider Type"},
        title="Monthly Ride Counts by Rider Type"
    )


def fig_totals(df: pd.DataFrame) -> go.Figure:
    g = df["member_casual"].value_counts().rename_axis("member_casual").reset_index(name="count")
    return px.bar(
        g, x="member_casual", y="count", color="member_casual",
        color_discrete_map=COLORS,
        labels={"member_casual":"Rider Type", "count":"Count"},
        title="Total Number of Rides by Rider Type",
        text_auto=True
    )


def fig_top_start_stations(df: pd.DataFrame, topn: int = 20) -> go.Figure:
    station_col = next((c for c in ["start_station_name","start_station","from_station_name"] if c in df.columns), None)
    if not station_col:
        return go.Figure()
    top = df[station_col].value_counts().head(topn).reset_index()
    top.columns = [station_col, "rides"]
    fig = px.bar(
        top, x="rides", y=station_col, orientation="h",
        color_discrete_sequence=["orange"],
        labels={"rides":"Number of Trips", station_col:"Start Station"},
        title=f"Top {topn} Most Popular Start Stations"
    )
    fig.update_layout(yaxis={"categoryorder":"total ascending"})
    return fig


def fig_rides_vs_temp(df: pd.DataFrame, weather: pd.DataFrame | None) -> go.Figure:
    # daily rides
    daily = df.groupby("date").size().reset_index(name="rides")

    if weather is None:
        # show rides only
        fig = px.line(daily, x="date", y="rides", labels={"date":"Date","rides":"Daily Bike Rides"},
                      title="Daily Bike Rides (2022)")
        return fig

    # merge with weather
    m = daily.merge(weather, on="date", how="inner")
    temp_col = next((c for c in ["avg_temp_f","tavg_f","tavg","temp_avg_f"] if c in m.columns), None)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=m["date"], y=m["rides"], name="Daily Bike Rides",
        mode="lines", line=dict(width=2, color="#FF8A00")   # warm orange
    ))
    fig.add_trace(go.Scatter(
        x=m["date"], y=m[temp_col], name="Avg Temp (°F)",
        mode="lines", line=dict(width=2, color="#1f77b4", dash="dot"),
        yaxis="y2"
    ))
    fig.update_layout(
        template="plotly_dark",
        title="Daily Bike Rides vs. Average Temperature (2022)",
        xaxis_title="Date",
        yaxis=dict(title="Daily Bike Rides"),
        yaxis2=dict(title="Average Temperature (°F)", overlaying="y", side="right"),
        legend=dict(orientation="h"),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    return fig


def fig_hour_weekday_heatmap(df: pd.DataFrame) -> go.Figure:
    if "started_at" in df.columns:
        dt = pd.to_datetime(df["started_at"], errors="coerce")
    else:
        dt = pd.to_datetime(df["date"], errors="coerce")
    hours = dt.dt.hour
    weekday = dt.dt.day_name()
    weekday = pd.Categorical(weekday, categories=WEEKDAY_ORDER, ordered=True)

    hm = pd.DataFrame({"hour": hours, "weekday": weekday}).dropna()
    hm = hm.groupby(["weekday","hour"]).size().reset_index(name="rides")

    fig = px.density_heatmap(
        hm, x="hour", y="weekday", z="rides",
        color_continuous_scale=["#FFF380","#FFD700","#FFB000","#FF7F0E"], # warm theme
        labels={"hour":"Hour of Day","weekday":"Day of Week","rides":"Rides"},
        title="Rides by Hour and Day of Week"
    )
    fig.update_layout(plot_bgcolor="white")
    return fig
    # --- WEEKDAY STACKED BAR: Avg trip duration by day & rider type ---
import pandas as pd
import plotly.express as px

def plot_avg_trip_duration_by_day(df):
    """Stacked bar: average trip duration by weekday split by rider type."""
    if df is None or df.empty:
        return None

    # Must have these columns
    need = {"started_at", "member_casual"}
    # duration column could be trip_duration or trip_duration_min — use what you have
    duration_col = "trip_duration" if "trip_duration" in df.columns else (
        "trip_duration_min" if "trip_duration_min" in df.columns else None
    )
    if not need.issubset(df.columns) or duration_col is None:
        return None

    d = df.copy()
    d["started_at"] = pd.to_datetime(d["started_at"], errors="coerce")
    d["day_of_week"] = d["started_at"].dt.day_name()

    avg = (
        d.groupby(["day_of_week", "member_casual"], observed=False)[duration_col]
         .mean()
         .reset_index()
    )

    # Order weekdays
    order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    avg["day_of_week"] = pd.Categorical(avg["day_of_week"], order, ordered=True)

    # Theme colors you’re using everywhere else
    COLORS = {"casual": "#FFD700", "member": "#FFA500"}  # gold = casual, orange = member

    fig = px.bar(
        avg,
        x="day_of_week",
        y=duration_col,
        color="member_casual",
        barmode="stack",
        color_discrete_map=COLORS,
        labels={
            "day_of_week": "Day of the Week",
            duration_col: "Average Duration (min)",
            "member_casual": "Rider Type",
        },
        title="Average Trip Duration by Day and Rider Type",
    )

    fig.update_layout(
        xaxis=dict(title_font=dict(color="black"), tickfont=dict(color="black")),
        yaxis=dict(title_font=dict(color="black"), tickfont=dict(color="black")),
        legend_title_font=dict(color="black"),
        legend_font=dict(color="black"),
        title_font=dict(color="black"),
        plot_bgcolor="white",
    )
    return fig



# -----------------------------
# Load & normalize data
# -----------------------------
df_raw = load_trips(csv_path)
df = normalize_trips(df_raw)

# Metrics
total_rides = len(df)
avg_duration = df["trip_duration_min"].dropna().mean() if "trip_duration_min" in df.columns else np.nan

m1, m2 = st.columns(2)
m1.metric("Total Rides", f"{total_rides:,}")
m2.metric("Avg Duration (min)", f"{avg_duration:.1f}" if pd.notnull(avg_duration) else "—")

st.divider()
# --- Weekday charts pack ---
import pandas as pd
import plotly.express as px

WEEKDAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
COLORS = {"member": "orange", "casual": "gold"}  # keep your theme

def make_weekday_charts(d: pd.DataFrame):
    d = d.copy()
    # ensure date & weekday
    d["date"] = pd.to_datetime(d["date"], errors="coerce")
    d = d.dropna(subset=["date"])
    d["weekday"] = d["date"].dt.day_name()

    # pick duration column (be flexible with names)
    minute_col = next((c for c in ["trip_duration_min","trip_duration","duration_min","ride_duration_min"]
                       if c in d.columns), None)

    # 1) counts by weekday & rider type
    counts = (d.groupby(["weekday","member_casual"])
                .size()
                .reset_index(name="rides"))
    fig_counts = px.bar(
        counts, x="weekday", y="rides", color="member_casual",
        category_orders={"weekday": WEEKDAY_ORDER},
        color_discrete_map=COLORS,
        labels={"weekday":"Day of the Week","rides":"Number of Rides","member_casual":"Rider Type"},
        title="Ride Counts by Day of Week and Rider Type"
    )

    # 2) average duration by weekday & rider type (only if we have a duration column)
    fig_avg = None
    if minute_col:
        avg = (d.groupby(["weekday","member_casual"], observed=True)[minute_col]
                 .mean()
                 .reset_index(name="avg_duration_min"))
        fig_avg = px.bar(
            avg, x="weekday", y="avg_duration_min", color="member_casual",
            category_orders={"weekday": WEEKDAY_ORDER},
            color_discrete_map=COLORS,
            labels={"weekday":"Day of the Week","avg_duration_min":"Average Duration (min)","member_casual":"Rider Type"},
            title="Average Trip Duration by Day of Week and Rider Type"
        )

    return fig_counts, fig_avg


# -----------------------------
# Tabs layout
# -----------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
    ["Distribution", "Monthly Trend", "Totals", "Top Stations", "Rides vs Temp", "Heatmap"]
)

with tab1:
    st.plotly_chart(fig_distribution(df), use_container_width=True)

with tab2:
    st.plotly_chart(fig_monthly_trend(df), use_container_width=True)

with tab3:
    st.plotly_chart(fig_totals(df), use_container_width=True)
    

with tab4:
    st.plotly_chart(fig_top_start_stations(df, topn=20), use_container_width=True)

with tab5:
    weather = load_weather(weather_path)
    st.plotly_chart(fig_rides_vs_temp(df, weather), use_container_width=True)

with tab6:
    st.plotly_chart(fig_hour_weekday_heatmap(df), use_container_width=True)

# -----------------------------
# Optional Kepler map
# -----------------------------
# --- Kepler map (NYC) embed via Streamlit ---

import streamlit as st
from pathlib import Path

# 1) Name of your saved Kepler map HTML (must be in the same folder as app.py)
path_to_html = "citibike_trip_routes.html"   # <-- your file

# 2) Read the HTML (safely) and embed it
MAP_PATH = Path(path_to_html)

st.subheader("Aggregated Bike Trips in NYC (Kepler.gl)")

if MAP_PATH.exists():
    # Read as text and embed
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        html_data = f.read()
    # Big, scrollable embed
    st.components.v1.html(html_data, height=1000, scrolling=True)
else:
    st.warning(f"Map file not found: {MAP_PATH.resolve()}\n"
               "Make sure the HTML is in the same folder as app.py or update 'path_to_html'.")
