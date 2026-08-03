import json
import html
from pathlib import Path
from importlib import resources
import streamlit as st
import pandas as pd
import altair as alt
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
DATA_FILE = Path(__file__).with_name("happiness_report_standardized1.csv")

# @st.cache_data prevents re-loading the CSV on every interaction
@st.cache_data
def load_data(csv_path, last_modified):
    df = pd.read_csv(csv_path)
    return df

df = load_data(str(DATA_FILE), DATA_FILE.stat().st_mtime)

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


@st.cache_data(show_spinner=False)
def load_country_numeric_codes():
    with resources.files("pycountry").joinpath("databases/iso3166-1.json").open(
        "r",
        encoding="utf-8"
    ) as file_handle:
        country_data = json.load(file_handle)["3166-1"]

    country_codes = {}
    for country in country_data:
        numeric_code = f"{int(country['numeric']):03d}"
        country_codes[country["name"]] = numeric_code
        if "common_name" in country:
            country_codes[country["common_name"]] = numeric_code
        if "official_name" in country:
            country_codes[country["official_name"]] = numeric_code
    return country_codes


COUNTRY_NUMERIC_CODES = load_country_numeric_codes()

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
        return f"{int(lookup_value):03d}"

    numeric_code = COUNTRY_NUMERIC_CODES.get(str(lookup_value))
    if numeric_code is None:
        return pd.NA

    return numeric_code

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
    if hasattr(selection_payload, "selection"):
        return extract_selected_country(getattr(selection_payload, "selection"))
    if isinstance(selection_payload, str):
        return selection_payload or None
    if isinstance(selection_payload, dict):
        if "Country_Key" in selection_payload:
            return extract_selected_country(selection_payload.get("Country_Key"))
        if "Country" in selection_payload:
            return extract_selected_country(selection_payload.get("Country"))
        if "points" in selection_payload:
            return extract_selected_country(selection_payload.get("points"))
        if "selection" in selection_payload:
            return extract_selected_country(selection_payload.get("selection"))
        if "country_select" in selection_payload:
            return extract_selected_country(selection_payload.get("country_select"))
        if "map_country_select" in selection_payload:
            return extract_selected_country(selection_payload.get("map_country_select"))
    if isinstance(selection_payload, list):
        for item in selection_payload:
            if isinstance(item, dict) and "Country_Key" in item:
                selected_value = extract_selected_country(item.get("Country_Key"))
                if selected_value:
                    return selected_value
            if isinstance(item, dict) and "Country" in item:
                selected_value = extract_selected_country(item.get("Country"))
                if selected_value:
                    return selected_value
            if isinstance(item, str) and item:
                return item
    return None


def extract_selected_countries(selection_payload):
    if selection_payload is None:
        return []

    if isinstance(selection_payload, str):
        return [selection_payload] if selection_payload else []

    selected_values = []

    if isinstance(selection_payload, dict):
        for key in ("Country_Key", "Country", "points", "selection", "country_select", "map_country_select"):
            if key in selection_payload:
                selected_values.extend(extract_selected_countries(selection_payload.get(key)))
        return list(dict.fromkeys(value for value in selected_values if value))

    if isinstance(selection_payload, list):
        for item in selection_payload:
            selected_values.extend(extract_selected_countries(item))
        return list(dict.fromkeys(value for value in selected_values if value))

    return []


def resolve_country_key(selected_country_value):
    if not selected_country_value:
        return None

    if selected_country_value in set(df["Country_Key"].dropna()):
        return selected_country_value

    matching_country_keys = (
        df.loc[df["Country_Standardized"] == selected_country_value, "Country_Key"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    if matching_country_keys:
        return matching_country_keys[0]

    return selected_country_value


def highlight_dynamic_text(value):
    return f'<span style="color: #7B2D8B; font-weight: 700;">{html.escape(str(value))}</span>'


def extract_brushed_years(selection_payload):
    if selection_payload is None:
        return []

    if hasattr(selection_payload, "selection"):
        return extract_brushed_years(getattr(selection_payload, "selection"))

    if isinstance(selection_payload, (int, float)):
        return [int(round(selection_payload))]

    if isinstance(selection_payload, str):
        try:
            return [int(round(float(selection_payload)))]
        except ValueError:
            return []

    if isinstance(selection_payload, dict):
        selected_values = []
        for key in ("year_brush", "brush", "selection", "x", "Year", "year"):
            if key in selection_payload:
                selected_values.extend(extract_brushed_years(selection_payload.get(key)))
        return list(dict.fromkeys(value for value in selected_values if value is not None))

    if isinstance(selection_payload, (list, tuple, set)):
        selected_values = []
        for item in selection_payload:
            selected_values.extend(extract_brushed_years(item))
        return list(dict.fromkeys(value for value in selected_values if value is not None))

    return []


years = sorted(df["Year"].dropna().unique())
geographic_groups = sorted(df["Geographic_Group"].dropna().unique())
group_domain = sorted(df["Geographic_Group"].dropna().unique())
group_range = [COLOR_PALETTE.get(group, "#999999") for group in group_domain]
TREND_START_YEAR = 2015
TREND_END_YEAR = 2024

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

    [data-testid="stSidebarContent"] {
        padding-top: clamp(0.5rem, 7vh, 3.5rem);
        padding-bottom: clamp(1rem, 8vh, 4rem);
    }

    @media (max-height: 850px) {
        [data-testid="stSidebarContent"] {
            padding-top: 0.5rem;
            padding-bottom: 1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# Sidebar controls
# -----------------------------
st.sidebar.header("World Explorer")
st.sidebar.markdown("<div style='height: 1.25rem;'></div>", unsafe_allow_html=True)
geographic_group = st.sidebar.selectbox(
    "World Region",
    geographic_groups,
    index=None,
    placeholder="All world regions"
)
st.sidebar.markdown("<div style='height: 0.45rem;'></div>", unsafe_allow_html=True)
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
st.sidebar.markdown("<div style='height: 0.45rem;'></div>", unsafe_allow_html=True)
current_country_filter_signature = (geographic_group, subregion)
previous_country_filter_signature = st.session_state.get("country_filter_signature")
if previous_country_filter_signature != current_country_filter_signature:
    st.session_state["selected_countries_manual"] = []
    st.session_state["country_filter_signature"] = current_country_filter_signature
    st.session_state["map_last_selection_signature"] = None
    st.session_state["map_last_clicked_country"] = None
    st.session_state["map_ignore_next_selection"] = True

map_selection_result = st.session_state.get("map_chart")
map_selection_signature = repr(map_selection_result)
last_map_selection_signature = st.session_state.get("map_last_selection_signature")
ignore_next_selection = st.session_state.get("map_ignore_next_selection", False)

current_selected_countries = list(st.session_state.get("selected_countries_manual", []) or [])
if ignore_next_selection:
    st.session_state["map_last_selection_signature"] = map_selection_signature
    st.session_state["map_ignore_next_selection"] = False
elif map_selection_signature != last_map_selection_signature:
    map_selected_country = resolve_country_key(extract_selected_country(map_selection_result))

    if map_selected_country:
        if map_selected_country in current_selected_countries:
            current_selected_countries = [
                country_key
                for country_key in current_selected_countries
                if country_key != map_selected_country
            ]
        else:
            current_selected_countries.append(map_selected_country)

        st.session_state["map_last_clicked_country"] = map_selected_country
    else:
        current_selected_countries = []
        st.session_state["map_last_clicked_country"] = None

    st.session_state["selected_countries_manual"] = list(dict.fromkeys(current_selected_countries))
    st.session_state["map_last_selection_signature"] = map_selection_signature

map_selected_countries = st.session_state["selected_countries_manual"]

country_pool = df.copy()
if geographic_group:
    country_pool = country_pool[country_pool["Geographic_Group"] == geographic_group]
if subregion:
    country_pool = country_pool[country_pool["Region_Standardized"] == subregion]

country_options = sorted(country_pool["Country_Key"].dropna().unique().tolist())
selected_countries_manual = st.sidebar.multiselect(
    "Country",
    options=country_options,
    key="selected_countries_manual",
    placeholder="All countries"
)

selected_countries = list(dict.fromkeys(st.session_state.get("selected_countries_manual", []) or []))
selected_country_codes = set(
    df.loc[df["Country_Key"].isin(selected_countries), "Country_Standardized"]
    .dropna()
    .map(country_name_to_numeric_code)
    .dropna()
    .tolist()
)

# -----------------------------
# Section 1: World choropleth
# -----------------------------
st.header("1. Which countries are happiest?")

st.markdown(
    "Hover over the map to explore each country's most recent happiness score, or use the **World Explorer** in the sidebar to narrow your view."
)

map_data = df.copy()

if geographic_group:
    map_data = map_data[
        map_data["Geographic_Group"] == geographic_group
    ]

if subregion:
    map_data = map_data[
        map_data["Region_Standardized"] == subregion
    ]

if not map_data.empty:
    map_data = (
        map_data
        .sort_values(["Country_Standardized", "Year"])
        .groupby("Country_Standardized", as_index=False)
        .tail(1)
        .copy()
    )

country_map_data = (
    map_data[
        [
            "Country_Standardized",
            "Happiness score",
            "Geographic_Group",
            "Region_Standardized",
            "Year",
        ]
    ]
    .rename(
        columns={
            "Country_Standardized": "Country",
            "Happiness score": "avg_happiness",
            "Geographic_Group": "world_region",
            "Region_Standardized": "subregion"
        }
    )
)

country_map_data["country_code"] = (
    country_map_data["Country"]
    .apply(country_name_to_numeric_code)
)

country_map_data = (
    country_map_data
    .dropna(subset=["country_code"])
    .copy()
)

if country_map_data.empty:
    st.info("No country data available for the selected filters.")

else:
    country_map_data["country_code"] = country_map_data["country_code"].astype(str)
    country_map_data["is_selected_country"] = country_map_data["country_code"].isin(selected_country_codes)

    world = alt.topo_feature(
        "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json",
        "countries"
    )

    # Most selections use Altair's automatic fit.
    # These Europe views need manual framing because:
    # - Russia pulls Eastern Europe far to the right.
    # - France's overseas geometry pulls Western Europe far off-center.
    if subregion == "Eastern Europe":
        projection_settings = {
            "type": "naturalEarth1",
            "rotate": [-55, 0, 0],
            "center": [0, 53],
            "scale": 455
        }
        clip_map = True

    elif subregion == "Western Europe":
        projection_settings = {
            "type": "naturalEarth1",
            "center": [5, 49],
            "scale": 650
        }
        clip_map = True

    elif geographic_group == "Europe" and not subregion:
        projection_settings = {
            "type": "naturalEarth1",
            "rotate": [-42, 0, 0],
            "center": [0, 53],
            "scale": 355
        }
        clip_map = True

    else:
        projection_settings = {
            "type": "naturalEarth1"
        }
        clip_map = False

    map_country_select = alt.selection_point(
        name="map_country_select",
        fields=["Country"],
        on="click",
        clear="dblclick",
        toggle=True
    )

    map_base_chart = (
        alt.Chart(world)
        .mark_geoshape(
            stroke="white",
            strokeWidth=0.65,
            clip=clip_map
        )
        .transform_lookup(
            lookup="id",
            from_=alt.LookupData(
                country_map_data,
                "country_code",
                [
                    "Country",
                    "avg_happiness",
                    "Year",
                    "world_region",
                    "subregion",
                    "is_selected_country"
                ]
            )
        )
        .transform_filter(
            "isValid(datum.avg_happiness)"
        )
        .encode(
            opacity=alt.value(1.0) if not selected_country_codes else alt.condition(
                "datum.is_selected_country",
                alt.value(0.95),
                alt.value(0.32)
            ),
            color=alt.Color(
                "avg_happiness:Q",
                scale=alt.Scale(
                    domain=[3, 8],
                    clamp=True,
                    range=[
                        "#F4ECF7",
                        "#E2C7EA",
                        "#C89ED8",
                        "#A96CBF",
                        "#7B2D8B"
                    ]
                ),
                legend=None
            ),
            tooltip=[
                alt.Tooltip(
                    "Country:N",
                    title="Country"
                ),
                alt.Tooltip(
                    "avg_happiness:Q",
                    title="Happiness score",
                    format=".2f"
                ),
                alt.Tooltip(
                    "Year:O",
                    title="Year"
                ),
                alt.Tooltip(
                    "world_region:N",
                    title="World region"
                ),
                alt.Tooltip(
                    "subregion:N",
                    title="Subregion"
                )
            ]
        )
        .project(
            **projection_settings
        )
        .properties(
            height=560
        )
    )

    if selected_country_codes:
        selected_border_chart = (
            alt.Chart(world)
            .mark_geoshape(
                fillOpacity=0,
                stroke="#7B2D8B",
                strokeWidth=2.2,
                clip=clip_map
            )
            .transform_lookup(
                lookup="id",
                from_=alt.LookupData(
                    country_map_data,
                    "country_code",
                    [
                        "Country",
                        "avg_happiness",
                        "Year",
                        "world_region",
                        "subregion",
                        "is_selected_country"
                    ]
                )
            )
            .transform_filter(
                "isValid(datum.avg_happiness) && datum.is_selected_country"
            )
            .encode(
                tooltip=[
                    alt.Tooltip(
                        "Country:N",
                        title="Country"
                    ),
                    alt.Tooltip(
                        "avg_happiness:Q",
                        title="Happiness score",
                        format=".2f"
                    ),
                    alt.Tooltip(
                        "Year:O",
                        title="Year"
                    ),
                    alt.Tooltip(
                        "world_region:N",
                        title="World region"
                    ),
                    alt.Tooltip(
                        "subregion:N",
                        title="Subregion"
                    )
                ]
            )
            .project(
                **projection_settings
            )
            .properties(
                height=560
            )
        )
        map_chart = alt.layer(map_base_chart, selected_border_chart)
    else:
        map_chart = map_base_chart

    map_chart = map_chart.add_params(map_country_select).configure_view(strokeWidth=0)

    map_column, explainer_column = st.columns([5, 2])

    with map_column:
        st.markdown(
            """
            <div style="
                width: 560px;
                max-width: 72%;
                margin: 0 auto 18px auto;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 5px;
                    font-size: 0.80rem;
                    font-weight: 600;
                    color: #4b5563;
                ">
                    <span>Lower happiness</span>
                    <span>Higher happiness</span>
                </div>
                <div style="
                    width: 100%;
                    height: 14px;
                    border-radius: 999px;
                    background: linear-gradient(
                        to right,
                        #F4ECF7 0%,
                        #E2C7EA 25%,
                        #C89ED8 50%,
                        #A96CBF 75%,
                        #7B2D8B 100%
                    );
                    border: 1px solid rgba(0, 0, 0, 0.08);
                "></div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.altair_chart(
            map_chart,
            key="map_chart",
            use_container_width=True
            ,
            on_select="rerun",
            selection_mode=["map_country_select"]
        )

    with explainer_column:
        st.info(
            "**How is happiness measured?**\n"
            "- **Score out of 10** for life satisfaction and well-being.\n"
            "- It is **self-reported** by respondents using the **Cantril Ladder**: **0** is worst, **10** is best.\n"
            "- It avoids the word happiness, so it translates more easily.\n"
            "- Collected by the **Gallup World Poll** since 2005 and analyzed by independent experts.\n"
            "Learn more at [worldhappiness.report/faq](https://www.worldhappiness.report/faq/)"
        )

# -----------------------------
# Section 2: Happiness trends
# -----------------------------
st.header("2. How has happiness changed over time?")

st.markdown(
    "Compare happiness trends with the global average from 2015 to 2024. Select countries from the map or the **World Explorer** to compare their trends."
)

trend_data = df[df["Year"].between(TREND_START_YEAR, TREND_END_YEAR)].copy()

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
year_brush = alt.selection_interval(encodings=["x"], name="year_brush", clear="dblclick")

overview_chart = (
    alt.layer(*trend_layers)
    .add_params(year_brush)
    .properties(height=420, title="Happiness Trajectories")
    .resolve_scale(color="independent")
    .configure_legend(
        orient="bottom",
        columns=3,
        labelFontSize=11,
        titleFontSize=12
    )
)

overview_selection_state = st.altair_chart(
    overview_chart,
    use_container_width=True,
    key="trajectories_chart",
    on_select="rerun",
    selection_mode=["year_brush"]
)

brushed_years = extract_brushed_years(overview_selection_state)
if len(brushed_years) >= 2:
    start_year = min(brushed_years)
    end_year = max(brushed_years)
else:
    start_year = TREND_START_YEAR
    end_year = TREND_END_YEAR

# -----------------------------
# Section 2: Happiness shifts
# -----------------------------
st.markdown("#### Where has happiness improved or declined the most?")

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

if subregion:
    comparison_scope = highlight_dynamic_text(subregion)
elif geographic_group:
    comparison_scope = highlight_dynamic_text(geographic_group)
# elif selected_countries:
#     comparison_scope = "selected countries"
else:
    comparison_scope = "countries worldwide"

changes_heading = (
    f"Comparing {comparison_scope} from {highlight_dynamic_text(start_year)} "
    f"to {highlight_dynamic_text(end_year)}"
)

st.markdown(f"##### {changes_heading}", unsafe_allow_html=True)

st.info("**💡 Try a different time period.** Drag across the **Happiness Trajectories** chart above to compare another year range.")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Countries compared", len(change_data))
with col2:
    st.metric("Average happiness change", round(change_data["Happiness Change"].mean(), 2))
with col3:
    if (change_data["Happiness Change"] > 0).any():
        best_country = change_data.loc[change_data["Happiness Change"].idxmax(), "Country_Key"]
        best_change = change_data["Happiness Change"].max()
        best_label = "Largest increase"
    else:
        best_country = change_data.loc[change_data["Happiness Change"].idxmin(), "Country_Key"]
        best_change = change_data["Happiness Change"].min()
        best_label = "Largest decrease"

    st.metric(best_label, best_country, round(best_change, 2))

changes_title = "Country-level happiness changes"

st.caption("Each bar shows a country's change in happiness over the selected time range, highlighting the largest gains and declines.")

if "n_countries" not in st.session_state:
    st.session_state.n_countries = 10

biggest_drops = change_data.nsmallest(st.session_state.n_countries, "Happiness Change")
biggest_gains = change_data.nlargest(st.session_state.n_countries, "Happiness Change")
bar_data = pd.concat([biggest_gains, biggest_drops]).sort_values("Happiness Change", ascending=False)

bar_chart = (
    alt.Chart(bar_data)
    .mark_bar()
    .encode(
        x=alt.X("Happiness Change:Q", title="Happiness change"),
        y=alt.Y(
            "Country_Key:N", title="",
            sort=alt.EncodingSortField(field="Happiness Change", op="sum", order="descending")
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
        ]
    )
    .properties(height=600, title=changes_title)
)

st.altair_chart(bar_chart, use_container_width=True)


# -----------------------------
# Section 3: Correlation explorer
# -----------------------------
st.divider()

st.header("3. What predicts a country's happiness?")

st.markdown(
    "This section shows how happiness and related factors are correlated. "
    "By examining these relationships, we can better understand what influences a country's overall happiness."
)

correlation_year = "All years"

correlation_data = df.copy()

if geographic_group:
    correlation_data = correlation_data[
        correlation_data["Geographic_Group"] == geographic_group
    ]

if subregion:
    correlation_data = correlation_data[
        correlation_data["Region_Standardized"] == subregion
    ]

correlation_data = correlation_data.dropna(subset=correlation_variables)

if correlation_data.empty:
    st.error("No data available for the selected correlation filters.")
    st.stop()

global_correlation_data = df.copy()
global_correlation_data = global_correlation_data.dropna(subset=correlation_variables)

def build_correlation_heatmap(correlation_frame, title_text):
    correlation_matrix = correlation_frame[correlation_variables].corr()

    corr_happiness = (
        correlation_matrix[["Happiness score"]]
        .drop(index="Happiness score")
        .reset_index()
        .rename(columns={"index": "Variable", "Happiness score": "Correlation"})
        .sort_values("Correlation", ascending=False)
    )

    corr_happiness["Short Label"] = corr_happiness["Variable"].map(short_labels)
    sorted_labels = corr_happiness["Short Label"].tolist()
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
            ),
            tooltip=alt.value(None)
        )
    )

    heatmap_chart = (
        alt.layer(heatmap_row, heatmap_text)
        .properties(
            width="container",
            height=200,
        )
        .configure_axisX(
            labelAngle=45,
            labelFontSize=12
        )
    )

    if title_text:
        heatmap_chart = heatmap_chart.properties(title=title_text)

    return heatmap_chart

global_correlation_title = "How do happiness predictors correlate globally?"
global_corr_heatmap = build_correlation_heatmap(global_correlation_data, None)

heatmap_column, explainer_column = st.columns([4, 2])

with heatmap_column:
    st.markdown(f"##### {global_correlation_title}")
    st.altair_chart(global_corr_heatmap, use_container_width=True)

    if geographic_group or subregion:
        regional_correlation_data = correlation_data
        if regional_correlation_data.empty:
            st.info("No region-specific correlation data is available for the current selection.")
        else:
            regional_selection = subregion if subregion else geographic_group
            st.markdown(
                f"##### How do happiness predictors correlate in {highlight_dynamic_text(regional_selection)}?",
                unsafe_allow_html=True
            )

            regional_corr_heatmap = build_correlation_heatmap(regional_correlation_data, None)
            st.altair_chart(regional_corr_heatmap, use_container_width=True)
            st.info(
                "**💡 Different regions tell different stories.** Try changing the **World Explorer** to see which predictors rise to the top."
            )
    else:
        st.info(
            "**💡 Predictors aren't equally important everywhere.** Use the **World Explorer** to compare regions."
        )

with explainer_column:
    st.info(
        "**What do these scores mean?**\n"
        "- **1**: the factor and happiness usually **rise together**.\n"
        "- **-1**: as one goes up, the other tends to **fall**.\n"
        "- **0**: there is **little clear relationship** in this data."
    )

st.subheader("A Closer Look at One Relationship")

st.markdown(
    "Pick one factor from the heatmap above to see how it relates to happiness score in more detail. "
    "The scatterplot keeps happiness score on the y-axis so you can focus on the pattern for the selected factor."
)

x_variable = st.selectbox(
    "Choose a factor to explore",
    [v for v in correlation_variables if v != "Happiness score"],
    index=None,
    placeholder="Select a factor from the heatmap"
)

if x_variable is None:
    st.info("Select a factor above to explore how it relates to happiness score.")
else:
    y_variable = "Happiness score"
    selected_corr = correlation_data[correlation_variables].corr().loc[y_variable, x_variable]

    st.markdown(
        f"Showing **{x_variable}** against **{y_variable}** "
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

    scatter_heading = f"{y_variable} vs. {x_variable}"
    if subregion or geographic_group:
        selected_region = subregion if subregion else geographic_group
        scatter_heading = f"{scatter_heading} in {highlight_dynamic_text(selected_region)}"
        st.markdown(f"##### {scatter_heading}", unsafe_allow_html=True)
    else:
        st.markdown(f"##### {scatter_heading}")

    relationship_scatter = relationship_scatter.properties(
        width="container",
        height=500,
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