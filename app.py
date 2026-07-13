
import json
import streamlit as st
import pandas as pd
import altair as alt
import pycountry
import streamlit.components.v1 as components


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="World Happiness Dashboard",
    page_icon="😊",
    layout="wide"
)

# -----------------------------
# Load data
# -----------------------------
# @st.cache_data prevents re-loading the CSV on every interaction
@st.cache_data
def load_data():
    df = pd.read_csv("happiness_report_standardized.csv")
    return df

df = load_data()

# Use standardized country names, but keep original names for rare duplicate cases
df["Country_Key"] = df["Country_Standardized"]
duplicates = df.duplicated(["Country_Standardized", "Year"], keep=False)
df.loc[duplicates, "Country_Key"] = df.loc[duplicates, "Country"]

region_groups = {
    "Europe": [
        "Northern Europe", "Western Europe",
        "Southern Europe", "Eastern Europe"
    ],
    "Asia": [
        "Central Asia", "Eastern Asia", "South-eastern Asia",
        "Southern Asia", "Western Asia"
    ],
    "Africa": [
        "Northern Africa", "Eastern Africa", "Western Africa",
        "Southern Africa", "Middle Africa"
    ],
    "Latin America & Caribbean": [
        "Central America", "South America", "Caribbean"
    ],
    "North America": ["Northern America"],
    "Oceania": ["Australia and New Zealand"]
}


def assign_group(region):
    for group, regions in region_groups.items():
        if region in regions:
            return group
    return "Other"


df["Geographic_Group"] = df["Region_Standardized"].apply(assign_group)

COUNTRY_NAME_ALIASES = {
    "Congo Republic": "Congo",
    "DR Congo": "Congo, The Democratic Republic of the",
    "Kosovo": "383",
    "Palestine": "Palestine, State of",
    "Russia": "Russian Federation",
}


def country_name_to_numeric_code(country_name):
    if pd.isna(country_name) or not str(country_name).strip():
        return pd.NA

    lookup_value = COUNTRY_NAME_ALIASES.get(country_name, country_name)
    if str(lookup_value).isdigit():
        return int(lookup_value)

    try:
        return int(pycountry.countries.lookup(lookup_value).numeric)
    except LookupError:
        return pd.NA

COLOR_PALETTE = {
    "Africa": "#E15759",
    "Asia": "#F28E2B",
    "Europe": "#4E79A7",
    "Latin America & Caribbean": "#59A14F",
    "North America": "#76B7B2",
    "Oceania": "#B07AA1",
    "Global Average": "#1F3A8A",
    "Other": "#9D9D9D",
}

# -----------------------------
# Columns used in dashboard
# -----------------------------
correlation_variables = [
    "Happiness score",
    "GDP per capita",
    "Social support",
    "Healthy life expectancy",
    "Freedom to make life choices",
    "Generosity",
    "Perceptions of corruption"
]

short_labels = {
    "Happiness score": "Happiness",
    "GDP per capita": "GDP",
    "Social support": "Support",
    "Healthy life expectancy": "Life Exp.",
    "Freedom to make life choices": "Freedom",
    "Generosity": "Generosity",
    "Perceptions of corruption": "Corruption"
}

# Trend variables list (reused across section 3)
TREND_VARIABLES = [*correlation_variables]

# Cache repeated aggregates so charts can reuse summary tables on every rerun
@st.cache_data(show_spinner=False)
def build_trend_tables(start_year, end_year):
    trend_data = df[df["Year"].between(start_year, end_year)].copy()
    country_trends = trend_data.groupby(["Country_Key", "Year"], as_index=False)[TREND_VARIABLES].mean()
    region_trends = trend_data.groupby(["Geographic_Group", "Year"], as_index=False)[TREND_VARIABLES].mean()
    global_trends = trend_data.groupby("Year", as_index=False)[TREND_VARIABLES].mean()
    return country_trends, region_trends, global_trends


# Flatten the various nested selection shapes Streamlit can emit to one country key
def extract_selected_country(selection_payload):
    if selection_payload is None:
        return None
    if isinstance(selection_payload, str):
        return selection_payload or None
    if isinstance(selection_payload, dict):
        if "Country_Key" in selection_payload:
            return extract_selected_country(selection_payload.get("Country_Key"))
        if "points" in selection_payload:
            return extract_selected_country(selection_payload.get("points"))
        if "selection" in selection_payload:
            return extract_selected_country(selection_payload.get("selection"))
        if "country_select" in selection_payload:
            return extract_selected_country(selection_payload.get("country_select"))
    if isinstance(selection_payload, list):
        for item in selection_payload:
            if isinstance(item, dict) and "Country_Key" in item:
                selected_value = extract_selected_country(item.get("Country_Key"))
                if selected_value:
                    return selected_value
            if isinstance(item, str) and item:
                return item
    return None

years = sorted(df["Year"].dropna().unique())
geographic_groups = sorted(df["Geographic_Group"].dropna().unique())
group_domain = sorted(df["Geographic_Group"].dropna().unique())
group_range = [COLOR_PALETTE.get(group, "#999999") for group in group_domain]

# -----------------------------
# Title
# -----------------------------
st.title("World Happiness Dashboard")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-image: url("https://em-content.zobj.net/source/apple/354/smiling-face_263a-fe0f.png");
        background-repeat: no-repeat;
        background-position: bottom 20px center;
        background-size: 80px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("Controls")

year_range = st.sidebar.slider(
    "Year range",
    min_value=int(min(years)),
    max_value=int(max(years)),
    value=(int(min(years)), int(max(years))),
    step=1
)
start_year, end_year = year_range
geographic_group = st.sidebar.selectbox(
    "World Region",
    geographic_groups,
    index=None,
    placeholder="All world regions"
)

subregion_options = sorted(df["Region_Standardized"].dropna().unique().tolist())
if geographic_group:
    subregion_options = sorted(
        df.loc[df["Geographic_Group"] == geographic_group, "Region_Standardized"]
        .dropna()
        .unique()
        .tolist()
    )

subregion = st.sidebar.selectbox(
    "Subregion",
    subregion_options,
    index=None,
    placeholder="All subregions"
)

# -----------------------------
# Section 1: World choropleth
# -----------------------------
st.header("1. Global Happiness Map")

st.markdown(
    "See how the average happiness score changes across countries for the selected year range. "
    "The map averages each country's score over all years in the current selection."
)

map_data = df[df["Year"].between(start_year, end_year)].copy()
if geographic_group:
    map_data = map_data[map_data["Geographic_Group"] == geographic_group]
if subregion:
    map_data = map_data[map_data["Region_Standardized"] == subregion]

country_map_data = (
    map_data.groupby("Country_Standardized", as_index=False)
    .agg(
        {
            "Happiness score": "mean",
            "Geographic_Group": "first",
            "Region_Standardized": "first"
        }
    )
    .rename(columns={
        "Country_Standardized": "Country",
        "Happiness score": "avg_happiness",
        "Geographic_Group": "world_region",
        "Region_Standardized": "subregion"
    })
)
country_map_data["country_code"] = country_map_data["Country"].apply(country_name_to_numeric_code)
country_map_data = country_map_data.dropna(subset=["country_code"]).copy()
if not country_map_data.empty:
    country_map_data["country_code"] = country_map_data["country_code"].astype(int)
    map_happiness_min = float(country_map_data["avg_happiness"].min())
    map_happiness_max = float(country_map_data["avg_happiness"].max())
    if map_happiness_min == map_happiness_max:
        map_happiness_min -= 0.01
        map_happiness_max += 0.01

world_countries_url = alt.datasets.url("world_110m")

if country_map_data.empty:
    st.info("No country data available for the selected filters.")
else:
    world_data = country_map_data.to_dict(orient="records")
    map_spec = {
        "$schema": "https://vega.github.io/schema/vega/v6.json",
        "description": "Interactive world happiness choropleth with pan and zoom.",
        "width": 900,
        "height": 500,
        "autosize": "none",
        "signals": [
            {"name": "tx", "update": "width / 2 - 160"},
            {"name": "ty", "update": "height / 2 + 20"},
            {
                "name": "scale",
                "value": 100,
                "on": [
                    {
                        "events": {"type": "wheel", "filter": "event.ctrlKey || event.metaKey", "consume": True},
                        "update": "clamp(scale * pow(1.0005, -event.deltaY * pow(16, event.deltaMode)), 40, 3000)"
                    }
                ]
            },
            {"name": "angles", "value": [0, 0], "on": [{"events": "pointerdown", "update": "[rotateX, centerY]"}]},
            {"name": "cloned", "value": None, "on": [{"events": "pointerdown", "update": "copy('projection')"}]},
            {"name": "start", "value": None, "on": [{"events": "pointerdown", "update": "invert(cloned, xy())"}]},
            {"name": "drag", "value": None, "on": [{"events": "[pointerdown, window:pointerup] > window:pointermove", "update": "invert(cloned, xy())"}]},
            {"name": "delta", "value": None, "on": [{"events": {"signal": "drag"}, "update": "[drag[0] - start[0], start[1] - drag[1]]"}]},
            {"name": "rotateX", "value": 0, "on": [{"events": {"signal": "delta"}, "update": "angles[0] + delta[0]"}]},
            {"name": "centerY", "value": 0, "on": [{"events": {"signal": "delta"}, "update": "clamp(angles[1] + delta[1], -60, 60)"}]},
        ],
        "projections": [
            {
                "name": "projection",
                "type": "mercator",
                "scale": {"signal": "scale"},
                "rotate": [{"signal": "rotateX"}, 0, 0],
                "center": [0, {"signal": "centerY"}],
                "translate": [{"signal": "tx"}, {"signal": "ty + 58"}],
            }
        ],
        "data": [
            {"name": "country_data", "values": world_data},
            {
                "name": "world",
                "url": world_countries_url,
                "format": {"type": "topojson", "feature": "countries"},
                "transform": [
                    {
                        "type": "lookup",
                        "from": "country_data",
                        "key": "country_code",
                        "fields": ["id"],
                        "values": ["Country", "avg_happiness", "world_region", "subregion"],
                        "as": ["Country", "avg_happiness", "world_region", "subregion"],
                    }
                ],
            },
        ],
        "marks": [
            {
                "type": "shape",
                "from": {"data": "world"},
                "encode": {
                    "enter": {
                        "strokeWidth": {"value": 0.5},
                        "stroke": {"value": "white"},
                        "fill": {
                            "signal": "datum.avg_happiness == null ? '#EFEFEF' : scale('color', datum.avg_happiness)"
                        },
                        "tooltip": {
                            "signal": "datum.avg_happiness == null ? null : {'Country': datum.Country, 'Avg happiness': format(datum.avg_happiness, '.2f'), 'World region': datum.world_region, 'Subregion': datum.subregion}"
                        },
                    }
                },
                "transform": [{"type": "geoshape", "projection": "projection"}],
            }
        ],
        "scales": [
            {
                "name": "color",
                "type": "linear",
                "domain": [map_happiness_min, map_happiness_max],
                "range": ["#F4ECF7", "#E2C7EA", "#C89ED8", "#A96CBF", "#7B2D8B"],
            }
        ],
    }

    map_html = f"""
        <style>
            .world-happiness-map-shell {{
                font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                position: relative;
                display: flex;
                align-items: flex-start;
                gap: 18px;
            }}
            .world-happiness-map-shell #world-happiness-map {{
                flex: 1 1 auto;
                margin-top: 0;
                min-width: 0;
            }}
            .world-happiness-legend {{
                display: flex;
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
                margin-top: 6px;
                flex: 0 0 110px;
                font-size: 12px;
                color: #4b5563;
            }}
            .world-happiness-legend-row {{
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 10px;
                width: 100%;
            }}
            .world-happiness-legend-bar {{
                width: 14px;
                height: 240px;
                border-radius: 999px;
                background: linear-gradient(to bottom, #7B2D8B 0%, #A96CBF 25%, #C89ED8 50%, #E2C7EA 75%, #F4ECF7 100%);
                border: 1px solid rgba(0, 0, 0, 0.08);
            }}
            .world-happiness-legend-label {{
                white-space: nowrap;
                font-weight: 600;
                color: #374151;
            }}
            .world-happiness-legend-note {{
                color: #6b7280;
                text-align: center;
            }}
            .world-happiness-tooltip {{
                position: absolute;
                pointer-events: none;
                z-index: 20;
                display: none;
                max-width: 260px;
                background: rgba(255, 255, 255, 0.92);
                color: #111827;
                border: 1px solid rgba(17, 24, 39, 0.12);
                border-radius: 6px;
                padding: 8px 10px;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.14);
                font-size: 12px;
                line-height: 1.3;
                backdrop-filter: blur(4px);
                -webkit-backdrop-filter: blur(4px);
            }}
            .world-happiness-tooltip-title {{
                display: block;
                margin-bottom: 6px;
                font-size: 13px;
                font-weight: 600;
                color: #111827;
            }}
            .world-happiness-tooltip-row {{
                display: flex;
                justify-content: space-between;
                gap: 12px;
                margin-top: 2px;
            }}
            .world-happiness-tooltip-label {{
                color: #6b7280;
                white-space: nowrap;
            }}
            .world-happiness-tooltip-value {{
                color: #111827;
                text-align: right;
                font-weight: 500;
            }}
        </style>
        <div class="world-happiness-map-shell">
            <div id="world-happiness-map"></div>
            <div class="world-happiness-legend" aria-label="Happiness score legend">
                <div class="world-happiness-legend-row">
                    <div class="world-happiness-legend-label">Higher happiness</div>
                    <div class="world-happiness-legend-bar"></div>
                    <div class="world-happiness-legend-label">Lower happiness</div>
                </div>
            </div>
            <div id="world-happiness-tooltip" class="world-happiness-tooltip"></div>
        </div>
    <script src=\"https://cdn.jsdelivr.net/npm/vega@6\"></script>
    <script>
            const mount = document.getElementById('world-happiness-map');
                        const tooltip = document.getElementById('world-happiness-tooltip');
                        const formatTooltip = (value) => {{
                                if (value == null) {{
                                        tooltip.style.display = 'none';
                                        return;
                                }}

                                const rows = [];
                                if (value['Avg happiness'] != null) rows.push(['Avg happiness', value['Avg happiness']]);
                                if (value['World region']) rows.push(['World region', value['World region']]);
                                if (value.Subregion) rows.push(['Subregion', value.Subregion]);
                                tooltip.innerHTML = '<div class="world-happiness-tooltip-title">' + value.Country + '</div>' + rows.map(([label, rowValue]) => '<div class="world-happiness-tooltip-row"><span class="world-happiness-tooltip-label">' + label + '</span><span class="world-happiness-tooltip-value">' + rowValue + '</span></div>').join('');
                        }};
            try {{
                const spec = {json.dumps(map_spec)};
                const runtime = vega.parse(spec);
                                const view = new vega.View(runtime, {{
                                        renderer: 'canvas',
                                        container: '#world-happiness-map',
                                        hover: true,
                                        tooltip: function(handler, event, item, value) {{
                                                if (!value) {{
                                                        tooltip.style.display = 'none';
                                                        return;
                                                }}

                                                formatTooltip(value);
                                                tooltip.style.display = 'block';
                                                const rect = mount.getBoundingClientRect();
                                                const x = event.clientX - rect.left + 14;
                                                const y = event.clientY - rect.top + 14;
                                                tooltip.style.left = x + 'px';
                                                tooltip.style.top = y + 'px';
                                        }}
                                }});
                view.runAsync().catch((error) => {{
                    mount.innerHTML = '<pre style="color:#b00020; white-space:pre-wrap;">' + String(error && error.stack ? error.stack : error) + '</pre>';
                }});
                                mount.addEventListener('mouseleave', () => {{
                                        tooltip.style.display = 'none';
                                }});
            }} catch (error) {{
                mount.innerHTML = '<pre style="color:#b00020; white-space:pre-wrap;">' + String(error && error.stack ? error.stack : error) + '</pre>';
            }}
    </script>
    """

    components.html(map_html, height=560, scrolling=False)
    st.caption("Tip: hold Ctrl on Windows/Linux or Cmd on Mac while scrolling to zoom; drag to pan.")

# -----------------------------
# Section 2: Happiness trends
# -----------------------------
st.header("2. Happiness Trends Over Time")

st.markdown(
    "Track average happiness over the selected year range. "
    "Use the World Region and Subregion filters and optionally highlight countries."
)

country_pool = df.copy()
if geographic_group:
    country_pool = country_pool[country_pool["Geographic_Group"] == geographic_group]
if subregion:
    country_pool = country_pool[country_pool["Region_Standardized"] == subregion]

country_options = sorted(country_pool["Country_Key"].dropna().unique().tolist())
selected_countries = st.multiselect(
    "Country",
    options=country_options,
    placeholder="All countries"
)

trend_data = df[df["Year"].between(start_year, end_year)].copy()

# ── Global average baseline (always shown) ──────────────────────
global_avg = (
    trend_data
    .groupby("Year", as_index=False)["Happiness score"]
    .mean()
    .rename(columns={"Happiness score": "Avg Score"})
)

global_line = (
    alt.Chart(global_avg)
    .mark_line(
        strokeWidth=1.5,
        color=COLOR_PALETTE["Global Average"],
        strokeDash=[4, 4],
        opacity=0.4
    )
    .encode(
        x=alt.X("Year:O", title="Year"),
        y=alt.Y(
            "Avg Score:Q",
            title="Happiness score",
            scale=alt.Scale(domain=[0, 10])
        ),
        tooltip=[
            alt.Tooltip("Year:O", title="Year"),
            alt.Tooltip("Avg Score:Q", title="Global Avg.", format=".2f")
        ]
    )
)

global_label = (
    alt.Chart(global_avg.tail(1))
    .mark_text(
        align="left", dx=8, fontSize=11,
        color=COLOR_PALETTE["Global Average"], opacity=0.5
    )
    .encode(
        x=alt.X("Year:O"),
        y=alt.Y("Avg Score:Q"),
        text=alt.value("Global Avg.")
    )
)

trend_layers = [global_line, global_label]

# ── World Region line (dashed, continent color) ─────────────────
if geographic_group:
    region_avg = (
        trend_data[trend_data["Geographic_Group"] == geographic_group]
        .groupby("Year", as_index=False)["Happiness score"]
        .mean()
        .rename(columns={"Happiness score": "Avg Score"})
    )
    if not region_avg.empty:
        region_color = COLOR_PALETTE.get(geographic_group, "#999999")
        region_avg["World Region"] = geographic_group

        region_line_chart = (
            alt.Chart(region_avg)
            .mark_line(
                strokeWidth=2.5,
                strokeDash=[6, 3],
                point=alt.OverlayMarkDef(filled=True, size=50)
            )
            .encode(
                x=alt.X("Year:O", title="Year"),
                y=alt.Y("Avg Score:Q", scale=alt.Scale(domain=[0, 10])),
                color=alt.Color(
                    "World Region:N",
                    title="World Region",
                    scale=alt.Scale(
                        domain=[geographic_group],
                        range=[region_color]
                    )
                ),
                tooltip=[
                    alt.Tooltip("Year:O", title="Year"),
                    alt.Tooltip("World Region:N", title="World Region"),
                    alt.Tooltip("Avg Score:Q", title="Avg Score", format=".2f")
                ]
            )
        )
        trend_layers.append(region_line_chart)

# ── Subregion line (solid, lighter shade) ───────────────────────
if subregion:
    subregion_avg = (
        trend_data[trend_data["Region_Standardized"] == subregion]
        .groupby("Year", as_index=False)["Happiness score"]
        .mean()
        .rename(columns={"Happiness score": "Avg Score"})
    )
    if not subregion_avg.empty:
        # Use a fixed lighter color per continent family
        subregion_color_map = {
            "Europe": "#A8C8E8",
            "Asia": "#FFCC88",
            "Africa": "#F4A0A0",
            "Latin America & Caribbean": "#A8D8A0",
            "North America": "#B8E0DE",
            "Oceania": "#D8C0D8",
        }
        subregion_color = subregion_color_map.get(geographic_group, "#BBBBBB")
        subregion_avg["Subregion"] = subregion

        subregion_line_chart = (
            alt.Chart(subregion_avg)
            .mark_line(
                strokeWidth=2,
                strokeDash=[3, 2],
                point=alt.OverlayMarkDef(filled=True, size=50)
            )
            .encode(
                x=alt.X("Year:O", title="Year"),
                y=alt.Y("Avg Score:Q", scale=alt.Scale(domain=[0, 10])),
                color=alt.Color(
                    "Subregion:N",
                    title="Subregion",
                    scale=alt.Scale(
                        domain=[subregion],
                        range=[subregion_color]
                    )
                ),
                tooltip=[
                    alt.Tooltip("Year:O", title="Year"),
                    alt.Tooltip("Subregion:N", title="Subregion"),
                    alt.Tooltip("Avg Score:Q", title="Avg Score", format=".2f")
                ]
            )
        )
        trend_layers.append(subregion_line_chart)

# ── Country lines (solid, distinct colors) ──────────────────────
if selected_countries:
    country_lines_data = (
        trend_data[trend_data["Country_Key"].isin(selected_countries)]
        .loc[:, ["Year", "Country_Key", "Happiness score"]]
        .rename(columns={"Country_Key": "Label", "Happiness score": "Avg Score"})
    )
    if not country_lines_data.empty:
        country_colors = [
            "#7B2D8B", "#E15759", "#59A14F", "#B07AA1",
            "#76B7B2", "#F28E2B", "#FF9DA7", "#9C755F",
            "#BAB0AC", "#4E79A7"
        ]
        country_line_chart = (
            alt.Chart(country_lines_data)
            .mark_line(
                strokeWidth=2.5,
                point=alt.OverlayMarkDef(filled=True, size=60)
            )
            .encode(
                x=alt.X("Year:O", title="Year"),
                y=alt.Y(
                    "Avg Score:Q",
                    title="Happiness score",
                    scale=alt.Scale(domain=[0, 10])
                ),
                color=alt.Color(
                    "Label:N",
                    title="Country",
                    scale=alt.Scale(
                        domain=selected_countries,
                        range=country_colors[:len(selected_countries)]
                    )
                ),
                tooltip=[
                    alt.Tooltip("Year:O", title="Year"),
                    alt.Tooltip("Label:N", title="Country"),
                    alt.Tooltip("Avg Score:Q", title="Avg Score", format=".2f")
                ]
            )
        )
        trend_layers.append(country_line_chart)

# ── Render ───────────────────────────────────────────────────────
overview_chart = (
    alt.layer(*trend_layers)
    .properties(height=420, title="Happiness Trajectories")
    .resolve_scale(color="independent")
    .configure_legend(
        orient="bottom",
        columns=3,
        labelFontSize=11,
        titleFontSize=12
    )
)

st.altair_chart(overview_chart, use_container_width=True)

st.divider()





# -----------------------------
# Section 3: Happiness shifts (Melissa's version)
# -----------------------------
st.header("3. Where Happiness Changed Most")

st.markdown(
    "Compare countries between two selected years. "
    "The bar chart highlights the largest gains and losses."
)

if start_year >= end_year:
    st.warning(f"Select a different end year to compare with {start_year}.")

else:
    filtered = df.copy()
    if geographic_group:
        filtered = filtered[filtered["Geographic_Group"] == geographic_group]
    if subregion:
        filtered = filtered[filtered["Region_Standardized"] == subregion]
    start_data = filtered[filtered["Year"] == start_year][
        ["Country_Key", "Geographic_Group", "Region_Standardized", "Happiness score"]
    ].rename(columns={"Happiness score": "Happiness_Start"})

    end_data = filtered[filtered["Year"] == end_year][
        ["Country_Key", "Geographic_Group", "Region_Standardized", "Happiness score"]
    ].rename(columns={"Happiness score": "Happiness_End"})

    change_data = start_data.merge(
        end_data,
        on=["Country_Key", "Geographic_Group", "Region_Standardized"],
        how="inner"
    )
    if change_data.empty:
        st.error("No matching countries found for this selection.")
        st.stop()

    change_data["Happiness Change"] = (
        change_data["Happiness_End"] - change_data["Happiness_Start"]
    )
    change_data["Change Direction"] = change_data["Happiness Change"].apply(
        lambda value: "Increase" if value >= 0 else "Decrease"
    )

    st.subheader(f"Changes from {start_year} to {end_year}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Countries compared", len(change_data))
    with col2:
        st.metric("Average happiness change", round(change_data["Happiness Change"].mean(), 2))
    with col3:
        best_country = change_data.loc[change_data["Happiness Change"].idxmax(), "Country_Key"]
        best_change = change_data["Happiness Change"].max()
        st.metric("Largest increase", best_country, round(best_change, 2))

    top_left, top_right = st.columns(2)

    if "selected_country" not in st.session_state:
        st.session_state.selected_country = None

    with top_left:
        st.subheader("Largest Happiness Changes")
        st.caption("Click a bar to select a country. Double-click empty space to clear the selection.")

        if "n_countries" not in st.session_state:
            st.session_state.n_countries = 10

        biggest_drops = change_data.nsmallest(st.session_state.n_countries, "Happiness Change")
        biggest_gains = change_data.nlargest(st.session_state.n_countries, "Happiness Change")
        bar_data = pd.concat([biggest_drops, biggest_gains]).sort_values("Happiness Change")

        country_select = alt.selection_point(
            name="country_select",
            fields=["Country_Key"],
            on="click",
            clear="dblclick",
            toggle=False
        )

        bar_chart = (
            alt.Chart(bar_data)
            .mark_bar()
            .encode(
                x=alt.X("Happiness Change:Q", title="Happiness change"),
                y=alt.Y(
                    "Country_Key:N", title="",
                    sort=alt.EncodingSortField(field="Happiness Change", op="sum", order="ascending")
                ),
                color=alt.Color(
                    "Change Direction:N",
                    scale=alt.Scale(domain=["Increase", "Decrease"], range=["#2E8B57", "#C0392B"])
                ),
                tooltip=[
                    alt.Tooltip("Country_Key:N", title="Country"),
                    alt.Tooltip("Geographic_Group:N", title="World Region"),
                    alt.Tooltip("Region_Standardized:N", title="Subregion"),
                    alt.Tooltip("Happiness_Start:Q", title=f"Happiness {start_year}", format=".2f"),
                    alt.Tooltip("Happiness_End:Q", title=f"Happiness {end_year}", format=".2f"),
                    alt.Tooltip("Happiness Change:Q", title="Happiness Change", format=".2f")
                ],
                opacity=alt.condition(country_select, alt.value(1.0), alt.value(0.35))
            )
            .add_params(country_select)
            .properties(height=600, title="Countries with the Largest Happiness Changes")
        )

        selection_state = st.altair_chart(
            bar_chart, use_container_width=True,
            on_select="rerun", selection_mode=["country_select"]
        )

        st.slider("Countries to show", 5, 20, key="n_countries")

        if isinstance(selection_state, dict):
            selected_payload = selection_state.get("selection", {}).get("country_select")
            if selected_payload is None and "country_select" in selection_state:
                selected_payload = selection_state.get("country_select")
            if selected_payload in (None, [], {}):
                st.session_state.selected_country = None
            else:
                selected_country_candidate = extract_selected_country(selected_payload)
                if selected_country_candidate in set(change_data["Country_Key"]):
                    st.session_state.selected_country = selected_country_candidate

    selected_country = st.session_state.selected_country

    with top_right:
        st.subheader("Indexed Factor Trends")
        st.caption("Click legend items to show or hide metrics; the chart rescales automatically.")

        full_years = list(range(start_year, end_year + 1))
        country_trends, region_trends, global_trends = build_trend_tables(start_year, end_year)

        if selected_country:
            trend_data_s2 = country_trends[country_trends["Country_Key"] == selected_country].copy()
            trend_title = f"Selected country: {selected_country}"
        elif subregion:
            raw = df[df["Year"].between(start_year, end_year)].copy()
            trend_data_s2 = (
                raw[raw["Region_Standardized"] == subregion]
                .groupby("Year", as_index=False)[TREND_VARIABLES]
                .mean()
            )
            trend_title = f"Subregion average: {subregion}"
        elif geographic_group:
            trend_data_s2 = region_trends[region_trends["Geographic_Group"] == geographic_group].copy()
            trend_title = f"World Region average: {geographic_group}"
        else:
            trend_data_s2 = global_trends.copy()
            trend_title = "Global average"

        trend_data_s2 = (
            trend_data_s2
            .set_index("Year")
            .reindex(full_years)
            .rename_axis("Year")
            .reset_index()
        )

        trend_long = (
            trend_data_s2[["Year"] + TREND_VARIABLES]
            .melt(id_vars="Year", var_name="Metric", value_name="Value")
            .sort_values(["Metric", "Year"])
        )

        if trend_long.empty:
            st.warning("No trend data available for this selection.")
        else:
            trend_long["Baseline"] = trend_long.groupby("Metric")["Value"].transform(
                lambda series: series.dropna().iloc[0] if not series.dropna().empty else pd.NA
            )
            trend_long["Indexed Change"] = trend_long["Value"] - trend_long["Baseline"]
            trend_long["Metric Short"] = trend_long["Metric"].map(short_labels)

            factor_order = TREND_VARIABLES[1:]
            factor_short_order = [short_labels[m] for m in factor_order]
            metric_short_order = [short_labels["Happiness score"]] + factor_short_order
            metric_colors = ["#7B2D8B", "#4E79A7", "#59A14F", "#F28E2B", "#E15759", "#76B7B2", "#B07AA1"]

            factor_select = alt.selection_point(
                fields=["Metric Short"], bind="legend", empty="all", toggle="true",
                value=[{"Metric Short": m} for m in metric_short_order]
            )

            trend_base = alt.Chart(trend_long).encode(
                x=alt.X("Year:O", title="Year"),
                y=alt.Y("Indexed Change:Q", title=f"Change since {start_year}"),
                color=alt.Color(
                    "Metric Short:N", sort=metric_short_order,
                    scale=alt.Scale(domain=metric_short_order, range=metric_colors),
                    title="Metric", legend=alt.Legend(symbolOpacity=1, labelOpacity=1)
                )
            )

            zero_rule = (
                alt.Chart(pd.DataFrame({"y": [0]}))
                .mark_rule(strokeDash=[6, 6], color="#666666")
                .encode(y="y:Q")
            )

            trend_lines = (
                trend_base
                .mark_line(strokeWidth=2, point=True)
                .add_params(factor_select)
                .transform_filter(factor_select)
                .encode(
                    strokeDash=alt.condition(
                        alt.datum["Metric Short"] == "Happiness",
                        alt.value([6, 3]),
                        alt.value([1, 0])
                    ),
                    tooltip=[
                        alt.Tooltip("Year:O", title="Year"),
                        alt.Tooltip("Metric:N", title="Metric"),
                        alt.Tooltip("Value:Q", title="Value", format=".2f"),
                        alt.Tooltip("Indexed Change:Q", title="Change from baseline", format=".2f"),
                    ]
                )
            )

            indexed_trend_chart = (
                alt.layer(zero_rule, trend_lines)
                .properties(height=600, title=trend_title)
            )

            st.altair_chart(indexed_trend_chart, use_container_width=True)



# -----------------------------
# Section 4: Correlation explorer
# -----------------------------
st.divider()

st.header("4. Correlation Explorer")

st.markdown(
    "This section shows how happiness and related factors are correlated. "
    "Use the dropdowns to choose a relationship, then inspect the scatterplot and trend line."
)

correlation_year_options = ["All years"] + years

correlation_year = st.selectbox(
    "Correlation year",
    correlation_year_options,
    index=0
)

correlation_data = df.copy()

if geographic_group:
    correlation_data = correlation_data[
        correlation_data["Geographic_Group"] == geographic_group
    ]

if subregion:
    correlation_data = correlation_data[
        correlation_data["Region_Standardized"] == subregion
    ]

if correlation_year != "All years":
    correlation_data = correlation_data[
        correlation_data["Year"] == correlation_year
    ]

correlation_data = correlation_data.dropna(subset=correlation_variables)

if correlation_data.empty:
    st.error("No data available for the selected correlation filters.")
    st.stop()

corr = correlation_data[correlation_variables].corr()

# Correlation heatmap — single row, happiness score vs all variables
corr_happiness = (
    corr[["Happiness score"]]
    .drop(index="Happiness score")
    .reset_index()
    .rename(columns={"index": "Variable", "Happiness score": "Correlation"})
    .sort_values("Correlation", ascending=False)
)

corr_happiness["Short Label"] = corr_happiness["Variable"].map(short_labels)

# Variable order sorted by correlation value
sorted_labels = corr_happiness["Short Label"].tolist()

# Add a dummy column to create a single-row heatmap
corr_happiness["Row"] = "Correlation"

heatmap_row = (
    alt.Chart(corr_happiness)
    .mark_rect()
    .encode(
        x=alt.X(
            "Short Label:N",
            sort=sorted_labels,
            title=None
        ),
        y=alt.Y(
            "Row:N",
            title=None,
            axis=alt.Axis(labels=False, ticks=False)
        ),
        color=alt.Color(
            "Correlation:Q",
            scale=alt.Scale(domain=[-1, 1], scheme="redblue"),
            title="Correlation"
        ),
        tooltip=[
            alt.Tooltip("Variable:N", title="Variable"),
            alt.Tooltip("Correlation:Q", format=".2f", title="Correlation with Happiness")
        ]
    )
)

heatmap_text = (
    alt.Chart(corr_happiness)
    .mark_text(fontSize=12)
    .encode(
        x=alt.X("Short Label:N", sort=sorted_labels),
        y=alt.Y("Row:N"),
        text=alt.Text("Correlation:Q", format=".2f"),
        color=alt.condition(
            "abs(datum.Correlation) > 0.5",
            alt.value("white"),
            alt.value("black")
        )
    )
)

corr_heatmap = (
    alt.layer(heatmap_row, heatmap_text)
    .properties(
        width="container",
        height=200,
        title="Correlation with Happiness Score"
    ).configure_axisX(
        labelAngle = 45,
        labelFontSize = 12
    )
)

st.altair_chart(corr_heatmap, use_container_width=True)

# Scatter plot — full width
# Scatter plot — full width
st.subheader("Selected Relationship")

x_variable = st.selectbox(
    "X-axis variable",
    [v for v in correlation_variables if v != "Happiness score"],
    index=None,
    placeholder="Select a variable to compare with Happiness score"
)

y_variable = st.selectbox(
    "Y-axis variable",
    correlation_variables,
    index=correlation_variables.index("Happiness score")
)

if x_variable is None:
    st.info("Select an X-axis variable above to explore the relationship with Happiness score.")
else:
    selected_corr = corr.loc[y_variable, x_variable]

    st.markdown(
        f"Showing **{y_variable}** by **{x_variable}** "
        f"with correlation **{selected_corr:.2f}**."
    )

    relationship_data = correlation_data.dropna(subset=[x_variable, y_variable])

    relationship_points = (
        alt.Chart(relationship_data)
        .mark_point(size=80, filled=True)
        .encode(
            x=alt.X(f"{x_variable}:Q", title=x_variable),
            y=alt.Y(f"{y_variable}:Q", title=y_variable),
            color=alt.Color(
                "Geographic_Group:N",
                title="World Region",
                scale=alt.Scale(
                    domain=[geographic_group] if geographic_group else group_domain,
                    range=[COLOR_PALETTE.get(geographic_group, "#999999")] if geographic_group else group_range
                )
            ),
            shape=alt.Shape(
                "Region_Standardized:N",
                title="Subregion"
            ),
            tooltip=[
                alt.Tooltip("Country_Key:N", title="Country"),
                alt.Tooltip("Year:O", title="Year"),
                alt.Tooltip("Geographic_Group:N", title="World Region"),
                alt.Tooltip("Region_Standardized:N", title="Subregion"),
                alt.Tooltip(f"{x_variable}:Q", title=x_variable, format=".2f"),
                alt.Tooltip(f"{y_variable}:Q", title=y_variable, format=".2f")
            ]
        )
    )

    if len(relationship_data) >= 2 and relationship_data[x_variable].nunique() > 1:
        trend_line = (
            alt.Chart(relationship_data)
            .transform_regression(x_variable, y_variable)
            .mark_line(color="black")
            .encode(
                x=alt.X(f"{x_variable}:Q"),
                y=alt.Y(f"{y_variable}:Q")
            )
        )

        if subregion and geographic_group:
            continent_data = df[df["Geographic_Group"] == geographic_group].copy()

            if correlation_year != "All years":
                continent_data = continent_data[
                    continent_data["Year"] == correlation_year
                ]

            continent_data = continent_data.dropna(subset=[x_variable, y_variable])

            continent_trend = (
                alt.Chart(continent_data)
                .transform_regression(x_variable, y_variable)
                .mark_line(
                    strokeDash=[6, 3],
                    opacity=0.4,
                    color=COLOR_PALETTE.get(geographic_group, "#999999")
                )
                .encode(
                    x=alt.X(f"{x_variable}:Q"),
                    y=alt.Y(f"{y_variable}:Q")
                )
            )

            relationship_scatter = alt.layer(
                relationship_points, continent_trend, trend_line
            )
        else:
            relationship_scatter = alt.layer(relationship_points, trend_line)
    else:
        relationship_scatter = relationship_points

    relationship_scatter = relationship_scatter.properties(
        width="container",
        height=500,
        title=f"{y_variable} vs. {x_variable}"
    )

    st.altair_chart(relationship_scatter, use_container_width=True)

st.write("")

st.caption(
    "Source: raw dataset from Kaggle, World Happiness 2015-2024 by Yadira Espinoza "
    "(https://www.kaggle.com/datasets/yadiraespinoza/world-happiness-2015-2024)."
)

st.caption(
    "The World Happiness Report is published by the Wellbeing Research Centre at the University of Oxford "
    "in partnership with Gallup, the UN Sustainable Development Solutions Network, and an independent editorial board."
)