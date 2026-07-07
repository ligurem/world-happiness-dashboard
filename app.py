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


def assign_group(region):
    for group, regions in region_groups.items():
        if region in regions:
            return group
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

years = sorted(df["Year"].dropna().unique())
geographic_groups = sorted(df["Geographic_Group"].dropna().unique())
group_domain = sorted(df["Geographic_Group"].dropna().unique())
group_range = [COLOR_PALETTE.get(group, "#999999") for group in group_domain]

# -----------------------------
# Title
# -----------------------------
st.title("World Happiness Dashboard")

st.markdown(
    "Explore how happiness scores changed across countries and how happiness relates "
    "to social and economic indicators in the World Happiness Report dataset."
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
# Section 1: Happiness trends
# -----------------------------
st.header("1. Happiness Trends Over Time")

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
            alt.Tooltip("Avg Score:Q", title="Global Avg.", format=".2f")
        ]
    )
)

global_label = (
    alt.Chart(global_avg.tail(1))
    .mark_text(align="left", dx=8, fontSize=11, color=COLOR_PALETTE["Global Average"], opacity=0.5)
    .encode(
        x=alt.X("Year:O"),
        y=alt.Y("Avg Score:Q"),
        text=alt.value("Global Avg.")
    )
)

trend_layers = [global_line, global_label]

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
    overlay_title = "World Region / Country"

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
                alt.Tooltip("Label:N", title="World Region / Country"),
                alt.Tooltip("Avg Score:Q", title="Avg Score", format=".2f")
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
st.header("2. Where Did Happiness Change the Most?")

st.markdown(
    "This section compares countries between two selected years. "
    "The bar chart shows the largest happiness increases and decreases."
)

if start_year >= end_year:
    st.warning("Choose an end year that comes after the start year.")
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
    st.metric("Biggest increase", best_country, round(best_change, 2))

top_left, top_right = st.columns(2)

selected_country = None

with top_left:
    st.subheader("Largest Happiness Changes")
    st.caption("Click a bar to select a country. Double-click empty chart space to clear selection.")

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
        clear="dblclick"
    )

    bar_chart = (
        alt.Chart(bar_data)
        .mark_bar()
        .encode(
            x=alt.X("Happiness Change:Q", title="Change in happiness score"),
            y=alt.Y(
                "Country_Key:N",
                title="",
                sort=alt.EncodingSortField(
                    field="Happiness Change",
                    op="sum",
                    order="ascending"
                )
            ),
            color=alt.condition(
                country_select,
                alt.Color(
                    "Change Direction:N",
                    scale=alt.Scale(
                        domain=["Increase", "Decrease"],
                        range=["#2E8B57", "#C0392B"]
                    )
                ),
                alt.value("#BDBDBD")
            ),
            tooltip=[
                alt.Tooltip("Country_Key:N", title="Country"),
                alt.Tooltip("Geographic_Group:N", title="World Region"),
                alt.Tooltip("Region_Standardized:N", title="Subregion"),
                alt.Tooltip("Happiness_Start:Q", title=f"Happiness {start_year}", format=".2f"),
                alt.Tooltip("Happiness_End:Q", title=f"Happiness {end_year}", format=".2f"),
                alt.Tooltip("Happiness Change:Q", title="Happiness Change", format=".2f")
            ],
            opacity=alt.condition(country_select, alt.value(1.0), alt.value(0.7))
        )
        .add_params(country_select)
        .properties(
            height=600,
            title="Countries with the Biggest Happiness Increases and Decreases"
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
        if isinstance(selected_payload, list) and selected_payload:
            first_item = selected_payload[0]
            if isinstance(first_item, dict):
                selected_country = first_item.get("Country_Key")
        elif isinstance(selected_payload, dict):
            selected_value = selected_payload.get("Country_Key")
            if isinstance(selected_value, list):
                selected_country = selected_value[0] if selected_value else None
            else:
                selected_country = selected_value

with top_right:
    st.subheader("Indexed Factor Trends")
    st.caption("Click legend items to hide or show metrics and automatically rescale the y-axis.")

    trend_variables = [
        "Happiness score",
        "GDP per capita",
        "Social support",
        "Healthy life expectancy",
        "Freedom to make life choices",
        "Generosity",
        "Perceptions of corruption"
    ]
    full_years = list(range(start_year, end_year + 1))
    trend_data = df[df["Year"].between(start_year, end_year)].copy()

    if selected_country:
        trend_data = (
            trend_data[trend_data["Country_Key"] == selected_country]
            .groupby("Year", as_index=False)[trend_variables]
            .mean()
        )
        trend_title = f"Selected country: {selected_country}"
    elif geographic_group:
        trend_data = (
            trend_data[trend_data["Geographic_Group"] == geographic_group]
            .groupby("Year", as_index=False)[trend_variables]
            .mean()
        )
        trend_title = f"World Region average: {geographic_group}"
    else:
        trend_data = trend_data.groupby("Year", as_index=False)[trend_variables].mean()
        trend_title = "Global average"

    trend_data = (
        trend_data
        .set_index("Year")
        .reindex(full_years)
        .rename_axis("Year")
        .reset_index()
    )

    trend_long = (
        trend_data[["Year"] + trend_variables]
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

        factor_order = trend_variables[1:]
        factor_short_order = [short_labels[metric] for metric in factor_order]
        metric_colors = [
            "#1F3A8A",
            "#4E79A7",
            "#59A14F",
            "#F28E2B",
            "#E15759",
            "#76B7B2"
        ]

        factor_select = alt.selection_point(
            fields=["Metric Short"],
            bind="legend",
            empty="all"
        )

        happiness_long = trend_long[trend_long["Metric"] == "Happiness score"].copy()
        factor_long = trend_long[trend_long["Metric"] != "Happiness score"].copy()

        happiness_line = (
            alt.Chart(happiness_long)
            .mark_line(strokeWidth=3, point=True, color=COLOR_PALETTE["Global Average"])
            .encode(
                x=alt.X("Year:O", title="Year"),
                y=alt.Y("Indexed Change:Q", title=f"Change since {start_year}", scale=alt.Scale(zero=True)),
                tooltip=[
                    alt.Tooltip("Year:O", title="Year"),
                    alt.Tooltip("Value:Q", title="Happiness score", format=".2f"),
                    alt.Tooltip("Indexed Change:Q", title="Change from baseline", format=".2f")
                ]
            )
        )

        trend_base = alt.Chart(factor_long).encode(
            x=alt.X("Year:O", title="Year"),
            y=alt.Y("Indexed Change:Q", title=f"Change since {start_year}"),
            color=alt.Color(
                "Metric Short:N",
                sort=factor_short_order,
                scale=alt.Scale(domain=factor_short_order, range=metric_colors),
                title="Metric"
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
            .encode(tooltip=[
                alt.Tooltip("Year:O", title="Year"),
                alt.Tooltip("Metric Short:N", title="Metric"),
                alt.Tooltip("Value:Q", title="Value", format=".2f"),
                alt.Tooltip("Indexed Change:Q", title="Change from baseline", format=".2f")
            ])
        )

        indexed_trend_chart = (
            alt.layer(zero_rule, happiness_line, trend_lines)
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
    "The first section compares happiness changes over time. "
    "The second section shows the overall correlation structure and lets users choose "
    "a relationship to explore with a scatterplot and trend line."
)