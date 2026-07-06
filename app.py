import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go


# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="World Happiness Dashboard",
    layout="wide"
)

# -----------------------------
# Load data
# -----------------------------
df = pd.read_csv("happiness_report_standardized.csv")

# Use standardized country names, but keep original names for rare duplicate cases
df["Country_Key"] = df["Country_Standardized"]
duplicates = df.duplicated(["Country_Standardized", "Year"], keep=False)
df.loc[duplicates, "Country_Key"] = df.loc[duplicates, "Country"]

# -----------------------------
# Columns used in dashboard
# -----------------------------
factors = [
    "GDP per capita",
    "Social support",
    "Healthy life expectancy",
    "Freedom to make life choices",
    "Generosity",
    "Perceptions of corruption"
]

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
regions = ["All regions"] + sorted(df["Region_Standardized"].dropna().unique())

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

start_year = st.sidebar.selectbox("Start year", years, index=0)
end_year = st.sidebar.selectbox("End year", years, index=len(years) - 1)
region = st.sidebar.selectbox("Region", regions)
factor = st.sidebar.selectbox("Compare happiness change with", factors)
n_countries = st.sidebar.slider("Countries to show", 5, 20, 10)

# -----------------------------
# Section 1: Happiness shifts
# -----------------------------
st.header("1. Where Did Happiness Change the Most?")

st.markdown(
    "This section compares countries between two selected years. "
    "The bar chart shows the largest happiness increases and decreases, while the "
    "scatterplot compares happiness change with change in the selected factor."
)

if start_year >= end_year:
    st.warning("Choose an end year that comes after the start year.")
    st.stop()

filtered = df.copy()

if region != "All regions":
    filtered = filtered[filtered["Region_Standardized"] == region]

start_data = filtered[filtered["Year"] == start_year][
    ["Country_Key", "Region_Standardized", "Happiness score", factor]
]

end_data = filtered[filtered["Year"] == end_year][
    ["Country_Key", "Region_Standardized", "Happiness score", factor]
]

start_data = start_data.rename(
    columns={
        "Happiness score": "Happiness_Start",
        factor: "Factor_Start"
    }
)

end_data = end_data.rename(
    columns={
        "Happiness score": "Happiness_End",
        factor: "Factor_End"
    }
)

change_data = start_data.merge(
    end_data,
    on=["Country_Key", "Region_Standardized"],
    how="inner"
)

if change_data.empty:
    st.error("No matching countries found for this selection.")
    st.stop()

change_data["Happiness Change"] = (
    change_data["Happiness_End"] - change_data["Happiness_Start"]
)

change_data["Factor Change"] = (
    change_data["Factor_End"] - change_data["Factor_Start"]
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

left, right = st.columns(2)

with left:
    st.subheader("Largest Happiness Changes")

    biggest_drops = change_data.nsmallest(n_countries, "Happiness Change")
    biggest_gains = change_data.nlargest(n_countries, "Happiness Change")
    bar_data = pd.concat([biggest_drops, biggest_gains])
    bar_data = bar_data.sort_values("Happiness Change")

    bar_chart = px.bar(
        bar_data,
        x="Happiness Change",
        y="Country_Key",
        color="Change Direction",
        orientation="h",
        hover_name="Country_Key",
        hover_data={
            "Region_Standardized": True,
            "Happiness_Start": ":.2f",
            "Happiness_End": ":.2f",
            "Happiness Change": ":.2f",
            "Change Direction": False
        },
        title="Countries with the Biggest Happiness Increases and Decreases",
        labels={
            "Country_Key": "Country",
            "Happiness Change": "Change in happiness score",
            "Region_Standardized": "Region"
        },
        template="plotly_white"
    )

    bar_chart.update_layout(height=600, yaxis_title="")
    st.plotly_chart(bar_chart, use_container_width=True)

with right:
    st.subheader("Happiness Change vs. Factor Change")

    change_scatter = px.scatter(
        change_data,
        x="Factor Change",
        y="Happiness Change",
        color="Region_Standardized",
        hover_name="Country_Key",
        hover_data={
            "Region_Standardized": True,
            "Happiness_Start": ":.2f",
            "Happiness_End": ":.2f",
            "Factor_Start": ":.2f",
            "Factor_End": ":.2f",
            "Factor Change": ":.2f",
            "Happiness Change": ":.2f"
        },
        title=f"Change in {factor} vs. Change in Happiness",
        labels={
            "Factor Change": f"Change in {factor}",
            "Happiness Change": "Change in happiness score",
            "Region_Standardized": "Region"
        },
        template="plotly_white"
    )

    change_scatter.add_hline(y=0, line_dash="dash")
    change_scatter.add_vline(x=0, line_dash="dash")
    change_scatter.update_layout(height=600)

    st.plotly_chart(change_scatter, use_container_width=True)

st.subheader("Country-Level Data")

table = change_data[
    [
        "Country_Key",
        "Region_Standardized",
        "Happiness_Start",
        "Happiness_End",
        "Happiness Change",
        "Factor_Start",
        "Factor_End",
        "Factor Change"
    ]
].rename(
    columns={
        "Country_Key": "Country",
        "Region_Standardized": "Region",
        "Happiness_Start": f"Happiness {start_year}",
        "Happiness_End": f"Happiness {end_year}",
        "Factor_Start": f"{factor} {start_year}",
        "Factor_End": f"{factor} {end_year}",
        "Factor Change": f"{factor} Change"
    }
)

st.dataframe(
    table.sort_values("Happiness Change", ascending=False),
    use_container_width=True,
    hide_index=True
)

# -----------------------------
# Section 2: Correlation explorer
# -----------------------------
st.divider()

st.header("2. Correlation Explorer")

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

if region != "All regions":
    correlation_data = correlation_data[
        correlation_data["Region_Standardized"] == region
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

    heatmap = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=[short_labels[v] for v in correlation_variables],
            y=[short_labels[v] for v in correlation_variables],
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            hovertemplate=(
                "<b>%{y}</b> and <b>%{x}</b><br>"
                "Correlation: %{z:.2f}<extra></extra>"
            )
        )
    )

    heatmap.update_layout(
        height=600,
        template="plotly_white",
        title="Correlation Between Happiness and Related Factors",
        margin=dict(l=90, r=40, t=70, b=90),
        xaxis=dict(side="bottom"),
        yaxis=dict(autorange="reversed")
    )

    st.plotly_chart(heatmap, use_container_width=True)

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

    relationship_scatter = px.scatter(
        relationship_data,
        x=x_variable,
        y=y_variable,
        color="Region_Standardized",
        hover_name="Country_Key",
        hover_data={
            "Year": True,
            "Region_Standardized": True,
            x_variable: ":.2f",
            y_variable: ":.2f"
        },
        title=f"{y_variable} vs. {x_variable}",
        labels={
            "Region_Standardized": "Region"
        },
        template="plotly_white"
    )

    # Add trend line
    if len(relationship_data) >= 2 and relationship_data[x_variable].nunique() > 1:
        x_values = relationship_data[x_variable].astype(float)
        y_values = relationship_data[y_variable].astype(float)

        slope, intercept = np.polyfit(x_values, y_values, 1)

        x_line = np.linspace(x_values.min(), x_values.max(), 100)
        y_line = slope * x_line + intercept

        relationship_scatter.add_trace(
            go.Scatter(
                x=x_line,
                y=y_line,
                mode="lines",
                name="Trend line"
            )
        )

    relationship_scatter.update_layout(height=600)

    st.plotly_chart(relationship_scatter, use_container_width=True)

st.info(
    "The first section compares happiness changes over time. "
    "The second section shows the overall correlation structure and lets users choose "
    "a relationship to explore with a scatterplot and trend line."
)