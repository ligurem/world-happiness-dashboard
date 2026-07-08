import streamlit as st
import pandas as pd
import altair as alt


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


# Collapse the dataset's finer subregions into the broader world regions used throughout the dashboard.
def assign_group(region):
    for group, regions in region_groups.items():
        if region in regions:
            return group
    # Preserve unmapped rows instead of dropping them from the charts.
    return "Other"


df["Geographic_Group"] = df["Region_Standardized"].apply(assign_group)

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

TREND_VARIABLES = [
    *correlation_variables
]


@st.cache_data(show_spinner=False)
def build_trend_tables(start_year, end_year):
    # Cache the repeated aggregates so the charts can reuse the same summary tables on every rerun.
    trend_data = df[df["Year"].between(start_year, end_year)].copy()

    country_trends = trend_data.groupby(["Country_Key", "Year"], as_index=False)[TREND_VARIABLES].mean()
    region_trends = trend_data.groupby(["Geographic_Group", "Year"], as_index=False)[TREND_VARIABLES].mean()
    global_trends = trend_data.groupby("Year", as_index=False)[TREND_VARIABLES].mean()

    return country_trends, region_trends, global_trends

years = sorted(df["Year"].dropna().unique())
geographic_groups = sorted(df["Geographic_Group"].dropna().unique())
group_domain = geographic_groups
group_range = [COLOR_PALETTE.get(group, "#999999") for group in group_domain]

# -----------------------------
# Title
# -----------------------------
st.title("World Happiness Dashboard")

st.markdown(
    "Explore how happiness changes across countries and how it relates to social and economic factors "
    "in the World Happiness Report dataset."
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
    # Narrow the subregion choices so the filters stay aligned.
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
# Section 1: Happiness trends
# -----------------------------
st.header("1. Happiness Trends Over Time")

st.markdown(
    "Track average happiness over the selected year range. "
    "Use the World Region and Subregion filters to narrow the view, then highlight countries if needed."
)

country_pool = df.copy()
if geographic_group:
    country_pool = country_pool[country_pool["Geographic_Group"] == geographic_group]
if subregion:
    country_pool = country_pool[country_pool["Region_Standardized"] == subregion]

# Keep the country picker scoped to the active filters so it only offers relevant options.
country_options = sorted(country_pool["Country_Key"].dropna().unique().tolist())
selected_countries = st.multiselect(
    "Countries",
    options=country_options,
    placeholder="All countries"
)

trend_data = df[df["Year"].between(start_year, end_year)].copy()

# Show the global average first so every trend chart has a stable reference line.
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
        point=True,
        opacity=0.5
    )
    .encode(
        x=alt.X("Year:O", title="Year"),
        y=alt.Y("Avg Score:Q", title="Happiness score", scale=alt.Scale(domain=[0, 10])),
        tooltip=[
            alt.Tooltip("Year:O", title="Year"),
            alt.Tooltip("Avg Score:Q", title="Global average", format=".2f")
        ]
    )
)

global_label = (
    alt.Chart(global_avg.tail(1))
    .mark_text(align="left", dx=8, fontSize=11, color=COLOR_PALETTE["Global Average"], opacity=0.5)
    .encode(
        x=alt.X("Year:O"),
        y=alt.Y("Avg Score:Q"),
        text=alt.value("Global average")
    )
)

trend_layers = [global_line, global_label]

# Layer any selected region average and country series on top of the global baseline.
overlay_frames = []
overlay_labels = []
overlay_colors = []

if geographic_group:
    region_avg = (
        trend_data[trend_data["Geographic_Group"] == geographic_group]
        .groupby("Year", as_index=False)["Happiness score"]
        .mean()
        .rename(columns={"Happiness score": "Avg Score"})
    )
    if not region_avg.empty:
        region_avg["Label"] = geographic_group
        overlay_frames.append(region_avg)
        overlay_labels.append(geographic_group)
        overlay_colors.append(COLOR_PALETTE.get(geographic_group, "#999999"))

if selected_countries:
    country_lines_data = (
        trend_data[trend_data["Country_Key"].isin(selected_countries)]
        .loc[:, ["Year", "Country_Key", "Geographic_Group", "Region_Standardized", "Happiness score"]]
        .rename(columns={"Country_Key": "Label", "Happiness score": "Avg Score"})
    )
    if not country_lines_data.empty:
        overlay_frames.append(country_lines_data)
        overlay_labels.extend(selected_countries)
        default_country_colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
            "#bcbd22", "#17becf"
        ]
        overlay_colors.extend(default_country_colors[:len(selected_countries)])

if overlay_frames:
    overlay_data = pd.concat(overlay_frames, ignore_index=True)
    overlay_title = "World region / country"

    overlay_line = (
        alt.Chart(overlay_data)
        .mark_line(strokeWidth=2, point=True)
        .encode(
            x=alt.X("Year:O", title="Year"),
            y=alt.Y("Avg Score:Q", title="Happiness score", scale=alt.Scale(domain=[0, 10])),
            strokeDash=alt.condition(
                alt.datum.Label == geographic_group,
                alt.value([6, 3]),
                alt.value([1, 0])
            ),
            color=alt.Color(
                "Label:N",
                title=overlay_title,
                scale=alt.Scale(domain=overlay_labels, range=overlay_colors)
            ),
            tooltip=[
                alt.Tooltip("Year:O", title="Year"),
                alt.Tooltip("Label:N", title=overlay_title),
                alt.Tooltip("Avg Score:Q", title="Average score", format=".2f")
            ]
        )
    )
    trend_layers.append(overlay_line)

overview_chart = (
    alt.layer(*trend_layers)
    .properties(height=420, title="Happiness Trajectories")
)

st.altair_chart(overview_chart, use_container_width=True)

st.divider()

# -----------------------------
# Section 2: Happiness shifts
# -----------------------------
st.header("2. Where Happiness Changed Most")

st.markdown(
    "Compare countries between two selected years. "
    "The bar chart highlights the largest gains and losses."
)

if start_year >= end_year:
    st.warning("Choose an end year after the start year.")
    st.stop()

filtered = df.copy()

if geographic_group:
    filtered = filtered[filtered["Geographic_Group"] == geographic_group]
if subregion:
    filtered = filtered[filtered["Region_Standardized"] == subregion]

start_data = filtered[filtered["Year"] == start_year][
    ["Country_Key", "Geographic_Group", "Region_Standardized", "Happiness score"]
]

end_data = filtered[filtered["Year"] == end_year][
    ["Country_Key", "Geographic_Group", "Region_Standardized", "Happiness score"]
]

start_data = start_data.rename(
    columns={
        "Happiness score": "Happiness_Start"
    }
)

end_data = end_data.rename(
    columns={
        "Happiness score": "Happiness_End"
    }
)

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

# Split the change values into direction buckets so the bar chart can color increases and decreases differently.
change_data["Change Direction"] = change_data["Happiness Change"].apply(
    lambda value: "Increase" if value >= 0 else "Decrease"
)

st.subheader(f"Changes from {start_year} to {end_year}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Countries compared", len(change_data))

with col2:
    st.metric(
        "Average happiness change",
        round(change_data["Happiness Change"].mean(), 2)
    )

with col3:
    best_country = change_data.loc[
        change_data["Happiness Change"].idxmax(),
        "Country_Key"
    ]
    best_change = change_data["Happiness Change"].max()
    st.metric("Largest increase", best_country, round(best_change, 2))

top_left, top_right = st.columns(2)

if "selected_country" not in st.session_state:
    st.session_state.selected_country = None


def extract_selected_country(selection_payload):
    # Streamlit can emit a few nested selection shapes, so flatten them to one country key.
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

with top_left:
    st.subheader("Largest Happiness Changes")
    st.caption("Click a bar to select a country. Double-click empty space to clear the selection.")

    if "n_countries" not in st.session_state:
        st.session_state.n_countries = 10

    biggest_drops = change_data.nsmallest(st.session_state.n_countries, "Happiness Change")
    biggest_gains = change_data.nlargest(st.session_state.n_countries, "Happiness Change")
    bar_data = pd.concat([biggest_drops, biggest_gains])
    bar_data = bar_data.sort_values("Happiness Change")

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
                "Country_Key:N",
                title="",
                sort=alt.EncodingSortField(
                    field="Happiness Change",
                    op="sum",
                    order="ascending"
                )
            ),
            color=alt.Color(
                "Change Direction:N",
                scale=alt.Scale(
                    domain=["Increase", "Decrease"],
                    range=["#2E8B57", "#C0392B"]
                )
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
        .properties(
            height=600,
            title="Countries with the Largest Happiness Changes"
        )
    )

    selection_state = st.altair_chart(
        bar_chart,
        use_container_width=True,
        on_select="rerun",
        selection_mode=["country_select"]
    )

    st.slider(
        "Countries to show",
        5,
        20,
        key="n_countries"
    )

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
        trend_data = country_trends[country_trends["Country_Key"] == selected_country].copy()
        trend_title = f"Selected country: {selected_country}"
    elif subregion:
        subregion_trends = (
            trend_data[trend_data["Region_Standardized"] == subregion]
            .groupby("Year", as_index=False)[TREND_VARIABLES]
            .mean()
        )
        trend_data = subregion_trends.copy()
        trend_title = f"Subregion average: {subregion}"
    elif geographic_group:
        trend_data = region_trends[region_trends["Geographic_Group"] == geographic_group].copy()
        trend_title = f"World Region average: {geographic_group}"
    else:
        trend_data = global_trends.copy()
        trend_title = "Global average"

    trend_data = (
        trend_data
        .set_index("Year")
        .reindex(full_years)
        .rename_axis("Year")
        .reset_index()
    )

    trend_long = (
        trend_data[["Year"] + TREND_VARIABLES]
        .melt(id_vars="Year", var_name="Metric", value_name="Value")
        .sort_values(["Metric", "Year"])
    )

    if trend_long.empty:
        st.warning("No trend data available for this selection.")
    else:
        # Keep missing years blank and anchor each metric to its first observed year.
        trend_long["Baseline"] = trend_long.groupby("Metric")["Value"].transform(
            lambda series: series.dropna().iloc[0] if not series.dropna().empty else pd.NA
        )
        trend_long["Indexed Change"] = trend_long["Value"] - trend_long["Baseline"]
        trend_long["Metric Short"] = trend_long["Metric"].map(short_labels)

        factor_order = TREND_VARIABLES[1:]
        factor_short_order = [short_labels[metric] for metric in factor_order]
        metric_short_order = [short_labels["Happiness score"]] + factor_short_order
        metric_colors = [
            COLOR_PALETTE["Global Average"],
            "#59A14F",
            "#F28E2B",
            "#E15759",
            "#76B7B2",
            "#B07AA1",
            "#9D9D9D"
        ]

        # Start with every metric selected; legend clicks remove individual series from the view.
        factor_select = alt.selection_point(
            fields=["Metric Short"],
            bind="legend",
            empty="all",
            toggle="true",
            value=[{"Metric Short": metric} for metric in metric_short_order]
        )

        trend_base = alt.Chart(trend_long).encode(
            x=alt.X("Year:O", title="Year"),
            y=alt.Y("Indexed Change:Q", title=f"Change since {start_year}"),
            color=alt.Color(
                "Metric Short:N",
                sort=metric_short_order,
                scale=alt.Scale(domain=metric_short_order, range=metric_colors),
                title="Metric",
                legend=alt.Legend(symbolOpacity=1, labelOpacity=1)
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
                # Keep Happiness visually distinct with a dashed stroke while leaving the legend behavior shared.
                strokeDash=alt.condition(
                    alt.datum["Metric Short"] == "Happiness",
                    alt.value([4, 4]),
                    alt.value([1, 0])
                ),
                tooltip=[
                alt.Tooltip("Year:O", title="Year"),
                alt.Tooltip("Metric Short:N", title="Metric"),
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
# Section 3: Correlation explorer
# -----------------------------
st.divider()

st.header("3. Correlation Explorer")

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

# Reapply the same geographic filters so the matrix and scatterplot stay in sync with the rest of the dashboard.
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

matrix_col, scatter_col = st.columns([1, 1])

with matrix_col:
    st.subheader("Correlation Matrix")

    corr_long = (
        corr.rename_axis("Y Variable")
        .reset_index()
        .melt(id_vars="Y Variable", var_name="X Variable", value_name="Correlation")
    )

    corr_long["X Label"] = corr_long["X Variable"].map(short_labels)
    corr_long["Y Label"] = corr_long["Y Variable"].map(short_labels)

    ordered_labels = [short_labels[v] for v in correlation_variables]

    heatmap_base = alt.Chart(corr_long).encode(
        x=alt.X("X Label:N", sort=ordered_labels, title=None),
        y=alt.Y("Y Label:N", sort=ordered_labels, title=None),
        tooltip=[
            alt.Tooltip("Y Variable:N", title="Variable 1"),
            alt.Tooltip("X Variable:N", title="Variable 2"),
            alt.Tooltip("Correlation:Q", format=".2f")
        ]
    )

    heatmap_cells = heatmap_base.mark_rect().encode(
        color=alt.Color(
            "Correlation:Q",
            scale=alt.Scale(domain=[1, -1], scheme="redblue"),
            title="Correlation"
        )
    )

    heatmap_text = heatmap_base.mark_text(size=11).encode(
        text=alt.Text("Correlation:Q", format=".2f"),
        color=alt.condition(
            "abs(datum.Correlation) >= 0.6",
            alt.value("white"),
            alt.value("black")
        )
    )

    heatmap = (
        alt.layer(heatmap_cells, heatmap_text)
        .properties(
            height=600,
            title="Correlation Between Happiness and Related Factors"
        )
    )

    st.altair_chart(heatmap, use_container_width=True)

with scatter_col:
    st.subheader("Selected Relationship")

    x_variable = st.selectbox(
        "X-axis variable",
        correlation_variables,
        index=correlation_variables.index("Social support")
    )

    y_variable = st.selectbox(
        "Y-axis variable",
        correlation_variables,
        index=correlation_variables.index("Happiness score")
    )

    selected_corr = corr.loc[y_variable, x_variable]

    st.markdown(
        f"Showing **{y_variable}** by **{x_variable}** "
        f"with correlation **{selected_corr:.2f}**."
    )

    relationship_data = correlation_data.dropna(subset=[x_variable, y_variable])

    relationship_points = (
        alt.Chart(relationship_data)
        .mark_circle(size=70)
        .encode(
            x=alt.X(f"{x_variable}:Q", title=x_variable),
            y=alt.Y(f"{y_variable}:Q", title=y_variable),
            color=alt.Color(
                "Geographic_Group:N",
                title="World Region",
                scale=alt.Scale(domain=group_domain, range=group_range)
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

    relationship_scatter = relationship_points

    # Add trend line
    # Only add the regression line when there are enough unique x-values to fit something meaningful.
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
        relationship_scatter = alt.layer(relationship_points, trend_line)

    relationship_scatter = relationship_scatter.properties(
        height=600,
        title=f"{y_variable} vs. {x_variable}"
    )

    st.altair_chart(relationship_scatter, use_container_width=True)

st.info(
    "The first section shows happiness trajectories over time. "
    "The second highlights the largest changes between two years. "
    "The third lets you explore correlations with a scatterplot and trend line."
)

st.write("")

st.caption(
    "Source: raw dataset from Kaggle, World Happiness 2015-2024 by Yadira Espinoza "
    "(https://www.kaggle.com/datasets/yadiraespinoza/world-happiness-2015-2024)."
)

st.caption(
    "The World Happiness Report is published by the Wellbeing Research Centre at the University of Oxford "
    "in partnership with Gallup, the UN Sustainable Development Solutions Network, and an independent editorial board."
)