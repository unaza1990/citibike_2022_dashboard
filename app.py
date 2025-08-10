# ================================
# Citi Bikes Strategy Dashboard
# ================================
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ---------- Page config & CSS ----------
st.set_page_config(page_title="Citi Bikes Strategy Dashboard", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1400px; }
h1, h2, h3 { font-weight: 800; }
.big-title { font-size: 44px; font-weight: 800; line-height: 1.15; margin: 6px 0 8px 0; }
.sub-title { font-size: 28px; font-weight: 700; margin: 10px 0 18px 0; }
.body-lg   { font-size: 18px; line-height: 1.6; }
.caption   { text-align:center; color:#666; font-size:14px; margin-top:6px; }
hr { margin: 1.2rem 0; }
/* NEW: Make iframes (like maps) fill width & height */
.stApp iframe {
    width: 100% !important;
    min-height: 80vh !important;
    border: none;
</style>
""", unsafe_allow_html=True)

# ---------- Paths (we’ll auto-find common ones) ----------
DATA_PATH      = "reduced_data_to_plot_7.csv"
MAP_HTML       = "citibike_trip_routes.html"
TRIPS_CSV_OPT  = "citibike_trip_sample.csv"      # for stacked weekday chart

INTRO_IMG_CANDIDATES = [
    "ghtp-superJumbo.jpg.webp",                  # your download name
    "intro_citibike.webp", "intro_citibike.jpg", "intro_citibike.png"
]
RECS_IMG_CANDIDATES = [
    "recs_citibike.jpg", "recs_citibike.png"
]
# if not found locally, we’ll fallback to these URLs
RECS_IMG_FALLBACK = "https://images.unsplash.com/photo-1551836022-d5d88e9218df?q=80&w=1600&auto=format&fit=crop"

def find_first_existing(candidates):
    """Return first existing file among candidates; also check Downloads folder."""
    here = Path.cwd()
    downloads = Path.home() / "Downloads"
    for name in candidates:
        p1 = here / name
        p2 = downloads / name
        if p1.exists():
            return str(p1)
        if p2.exists():
            return str(p2)
    return None

INTRO_IMG = find_first_existing(INTRO_IMG_CANDIDATES)
RECS_IMG  = find_first_existing(RECS_IMG_CANDIDATES)

# ---------- Helpers ----------
def page_h1():
    st.markdown('<div class="big-title">Citi Bikes Strategy Dashboard</div>', unsafe_allow_html=True)

def fmt_int(n):
    try:
        return f"{int(float(n)):,}"
    except:
        return str(n)

@st.cache_data
def load_main(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        # add season for filtering
        season_map = {12:"Winter",1:"Winter",2:"Winter",3:"Spring",4:"Spring",5:"Spring",
                      6:"Summer",7:"Summer",8:"Summer",9:"Fall",10:"Fall",11:"Fall"}
        df["season"] = df["date"].dt.month.map(season_map)
    return df

@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

# ---------- Sidebar ----------
st.sidebar.header("Aspect Selector")
page = st.sidebar.selectbox(
    "Select an aspect of the analysis",
    [
        "Intro page",
        "Weather component and bike usage",
        "Most popular stations",
        "Interactive map with aggregated bike trips",
        "Average duration by weekday & rider (stacked)",
        "Recommendations",
    ],
)

# ---------- Data ----------
if not Path(DATA_PATH).exists():
    st.error(f"Missing data file: {DATA_PATH}")
    st.stop()
df = load_main(DATA_PATH)

# ---------- Pages ----------
if page == "Intro page":
    page_h1()
    st.markdown(
        '<div class="sub-title">This dashboard provides insight into Citi Bike availability and usage patterns in NYC.</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        """
We investigate why customers sometimes can’t find bikes and highlight patterns in:
- Most popular stations  
- Weather component and bike usage  
- Interactive map with aggregated trips  
- Recommendations  

Use the left **Aspect Selector** to navigate.
        """
    )
    if INTRO_IMG:
        st.image(INTRO_IMG, use_container_width=True, caption="Citi Bike Image")
    else:
        st.info("Add **ghtp-superJumbo.jpg.webp** (or intro_citibike.*) next to app.py — or leave it in Downloads; I’ll find it automatically next run.")

elif page == "Weather component and bike usage":
    page_h1()
    st.subheader("Daily Bike Rides vs. Average Temperature (2022)")
    need = {"date","bike_rides_daily","avgTemp"}
    if not need.issubset(df.columns):
        st.error(f"Expected columns missing: {need - set(df.columns)}")
    else:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        # ORANGE rides (solid), BLUE temp (dotted) — your theme
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["bike_rides_daily"],
                       name="Number of Trips", line=dict(color="#F59E0B", width=2)),
            secondary_y=False
        )
        fig.add_trace(
            go.Scatter(x=df["date"], y=df["avgTemp"],
                       name="Avg Temperature (°F)", line=dict(color="#1f77b4", width=2, dash="dot")),
            secondary_y=True
        )
        fig.update_layout(
            height=520, margin=dict(l=20,r=20,t=10,b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_white"
        )
        fig.update_yaxes(title_text="Daily Bike Rides", secondary_y=False)
        fig.update_yaxes(title_text="Avg Temperature (°F)", secondary_y=True)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Key insights")
        st.markdown(
            """
1. **Weather-driven demand** — rides climb with warmer temps (May–Oct), fall in winter.  
2. **Peaks cluster** in late spring and summer; expect stockouts unless ops ramp up.  
3. **Plan rebalancing** windows around weekday AM/PM peaks; watch summer weekends.  
4. **Use forecasts** to pre-position bikes before heat waves and events.  
            """
        )

elif page == "Most popular stations":
    page_h1()
    st.subheader("Top 20 Most Popular Start Stations in NYC (2022)")

    # Season filter & KPI
    with st.sidebar:
        seasons = sorted(df["season"].dropna().unique().tolist()) if "season" in df.columns else []
        season_filter = st.multiselect("Season filter", options=seasons, default=seasons)

    df1 = df.query("season in @season_filter") if season_filter else df.copy()

    if "bike_rides_daily" in df1.columns:
        st.markdown("#### Total Bike Rides")
        st.markdown(f"### {fmt_int(df1['bike_rides_daily'].sum())}")

    # Build top20 by start_station_name using your aggregated daily counts
    if "start_station_name" not in df1.columns:
        st.warning("Column `start_station_name` not found — showing a placeholder ranking by trip totals if available.")
    grp = (df1.groupby("start_station_name", as_index=False)
              .agg(trip_count=("bike_rides_daily","sum"))
              .sort_values("trip_count", ascending=True)
           ).tail(20)

    # Horizontal bar with 'Sunset' colors (your original theme)
    fig = go.Figure(go.Bar(
        x=grp["trip_count"],
        y=grp["start_station_name"],
        orientation="h",
        marker=dict(color=grp["trip_count"], colorscale="Sunset", showscale=False)
    ))
    fig.update_layout(
        height=640, margin=dict(l=180, r=40, t=10, b=40),
        xaxis_title="Sum of trips",
        yaxis_title="Start stations",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Key insights")
    st.markdown(
        """
1. **A few hubs dominate** usage — the top stations account for a large share of trips.  
2. These hubs align with **dense commuter & tourist corridors** (mid/low Manhattan).  
3. **Capacity & rebalancing** should prioritize the top 5–8 stations in warm months.  
4. **Edge stations** (upper Manhattan, outer areas) show opportunity for smarter growth.  
5. Track **seasonality**: strong summer uplift means pre-summer dock expansions pay off.  
        """
    )

# ───────────────  Interactive map with aggregated bike trips  ───────────────

elif page == "Interactive map with aggregated bike trips":
    page_h1()
    st.subheader("Interactive map showing aggregated bike trips over New York")
    st.markdown("### Aggregated Bike Trips in New York")

    from pathlib import Path
    path_to_html = "citibike_trip_routes.html"   # keep this file next to app.py

    try:
        with open(path_to_html, "r", encoding="utf-8") as f:
            html_data = f.read()

        # IMPORTANT: use components.html (not st.iframe)
        st.components.v1.html(html_data, height=900, scrolling=True)

        # Optional insights
        st.markdown("### Key Observations:")
        st.markdown(
            """
            1. **Manhattan core is the densest** (Midtown–Downtown corridors).  
            2. **Cross-river links** to Brooklyn/Jersey City are visible but thinner.  
            3. **Hotspots** align with commuter & tourist areas (Central Park, waterfront).  
            4. **Ops**: larger docks & faster rebalancing needed during peaks.
            """
        )
    except FileNotFoundError:
        st.error(f"HTML file not found: {Path(path_to_html).resolve()}")


# ─────────────────── Duration by weekday & rider (stacked) ───────────────────
elif page == "Average duration by weekday & rider (stacked)":
    page_h1()
    st.subheader("Average Trip Duration by Day and Rider Type (stacked)")

    TRIPS_CSV_OPT = "citibike_trip_sample.csv"   # put this next to app.py
    if Path(TRIPS_CSV_OPT).exists():
        tdf = load_csv(TRIPS_CSV_OPT)

        # detect common columns
        ts_start = next((c for c in ["started_at","starttime","start_time"] if c in tdf.columns), None)
        ts_end   = next((c for c in ["ended_at","stoptime","end_time"] if c in tdf.columns), None)
        rider_col= next((c for c in ["member_casual","usertype","user_type"] if c in tdf.columns), None)

        if not (ts_start and ts_end and rider_col):
            st.warning("Trip file is missing expected columns (started_at, ended_at, member_casual/usertype).")
        else:
            tdf[ts_start] = pd.to_datetime(tdf[ts_start], errors="coerce")
            tdf[ts_end]   = pd.to_datetime(tdf[ts_end], errors="coerce")
            tdf = tdf.dropna(subset=[ts_start, ts_end])

            tdf["trip_duration"] = (tdf[ts_end] - tdf[ts_start]).dt.total_seconds()/60
            tdf["day_of_week"] = tdf[ts_start].dt.day_name()

            avg_duration_day = (
                tdf.groupby(["day_of_week", rider_col])["trip_duration"]
                   .mean()
                   .reset_index()
            )
            order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
            avg_duration_day["day_of_week"] = pd.Categorical(avg_duration_day["day_of_week"], categories=order, ordered=True)
            avg_duration_day = avg_duration_day.sort_values("day_of_week")

            CUSTOM_COLORS = {'casual':'#FBBF24', 'member':'#F59E0B', 'Customer':'#FBBF24', 'Subscriber':'#F59E0B'}  # sunset vibes
            fig6 = px.bar(
                avg_duration_day,
                x='day_of_week',
                y='trip_duration',
                color=rider_col,
                labels={'day_of_week':'Day of Week','trip_duration':'Average Duration (min)'},
                color_discrete_map=CUSTOM_COLORS,
                title=''
            )
            fig6.update_layout(
                height=520, template='plotly_white',
                xaxis=dict(title_font=dict(color='black'), tickfont=dict(color='black')),
                yaxis=dict(title_font=dict(color='black'), tickfont=dict(color='black')),
                margin=dict(l=20,r=20,t=10,b=20),
                legend_title_text="Rider Type"
            )
            st.plotly_chart(fig6, use_container_width=True)

            st.markdown("### Key insights")
            st.markdown(
                """
                - **Weekends run longer**, especially for casual riders (leisure trips).  
                - **Members are steadier** on weekdays (commutes, errands).  
                - **Ops**: focus rebalancing Sat–Sun afternoons for casual surges.  
                """
            )
    else:
        st.info(f"Place a trip-level CSV named **{TRIPS_CSV_OPT}** next to app.py to enable this page.")

# ───────────────────────────── Recommendations ─────────────────────────────
elif page == "Recommendations":
    page_h1()
    st.subheader("Conclusions and recommendations")

    # Optional hero image (put a file next to app.py, or comment these two lines)
    RECS_IMG = "recs_citibike.jpg"
    if Path(RECS_IMG).exists():
        st.image(RECS_IMG, use_container_width=True, caption="Citi Bike Recommendations")

    st.markdown("### Our analysis highlights key factors")
    st.markdown(
        """
        1. **Seasonal variability** — usage peaks May–Oct; winter is lowest.  
        2. **High-demand hubs** — a handful of stations dominate volumes.  
        3. **Uneven regional activity** — outer areas remain under-served.  
        4. **Connectivity corridors** — waterfront & cross-river spines are persistent flows.  
        5. **Redistribution gaps** — peaks need faster, data-driven rebalancing.  
        """
    )

    st.markdown("### Recommendations")
    st.markdown(
        """
        - **Seasonal scaling**: ramp inventory May–Oct; scale down Nov–Apr using warm/cold ratio.  
        - **Expand hubs**: add docks at top 5–8 stations; pilot **dynamic rebalancing windows**.  
        - **Proactive positioning**: trigger crews off **weather & event alerts**; pre-position before spikes.  
        - **Grow edges smartly**: seed capacity in **outer areas** near transit & parks.  
        - **Next data**: add **station capacity + real-time availability** to set SLA windows.  
        """
    )
