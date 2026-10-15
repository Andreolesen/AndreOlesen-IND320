import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from data_utils import (
    AREA_TYPE_LABELS,
    DATA_COLUMNS,
    area_label,
    column_display_names,
    load_month_labels,
    load_reservoir_interval,
)

st.title("Reservoir data (NVE)")
st.write("Weekly reservoir statistics from NVE. The choices at the top apply to both the table and the plot.")

# ---------------------------------------------------------------- shared controls
# The controls are placed above the tabs, so the table and the plot always show the same data.
# (In part 1 the table and the plot were on separate pages with their own controls.)
month_labels = load_month_labels()

left, right = st.columns([1, 2])
with left:
    # Radio buttons for the type of area. The value is the code used in the data (NO/EL/VASS)
    area_type = st.radio(
        "Type of area",
        options=list(AREA_TYPE_LABELS),
        format_func=lambda code: AREA_TYPE_LABELS[code],
    )
    # Which column to show in both the table and the plot
    column = st.selectbox(
        "Column",
        options=DATA_COLUMNS,
        format_func=lambda c: column_display_names[c],
    )
with right:
    # Interval slider over months (the slider from page three in part 1). A tuple as value gives
    # a range slider. Default is the last two years, so the seasonal pattern is visible.
    start_month, end_month = st.select_slider(
        "Download interval (months)",
        options=month_labels,
        value=(month_labels[max(0, len(month_labels) - 24)], month_labels[-1]),
    )
    st.caption(
        "The NVE API has no date parameters, so the full data set is downloaded once (cached for a day) "
        "and the slider decides which interval is kept and used on this page."
    )

# "Download" the chosen interval for the chosen area type (cached per choice in data_utils)
data = load_reservoir_interval(area_type, start_month, end_month)

if data.empty:
    st.warning("No data for this choice.")
    st.stop()

name = column_display_names[column]
table_tab, plot_tab = st.tabs(["Table", "Plot"])

# ---------------------------------------------------------------- table with LineChartColumn
with table_tab:
    # One row per area number. The "Development" cell holds the list of values in the interval,
    # which LineChartColumn draws as a small line chart inside the table.
    rows = []
    for area_number, area_data in data.groupby("area_number"):
        values = area_data[column].tolist()
        rows.append({
            "Area": area_label(area_type, area_number),
            "Development": values,
            "First": values[0],
            "Last": values[-1],
            "Min": min(values),
            "Max": max(values),
        })

    st.dataframe(
        pd.DataFrame(rows),
        column_config={
            "Development": st.column_config.LineChartColumn(
                f"{name}, {start_month} to {end_month}",
                width="large",
                # Same scale in every row, so the areas can be compared
                y_min=float(data[column].min()),
                y_max=float(data[column].max()),
            ),
            "First": st.column_config.NumberColumn(format="%.3f"),
            "Last": st.column_config.NumberColumn(format="%.3f"),
            "Min": st.column_config.NumberColumn(format="%.3f"),
            "Max": st.column_config.NumberColumn(format="%.3f"),
        },
        hide_index=True,
        width="stretch",
    )

# ---------------------------------------------------------------- plot
with plot_tab:
    fig, ax = plt.subplots(figsize=(10, 5))

    # One line per area number
    for area_number, area_data in data.groupby("area_number"):
        ax.plot(area_data["date"], area_data[column], linewidth=1.6, label=area_label(area_type, area_number))

    ax.set_title(f"{name}, {AREA_TYPE_LABELS[area_type].lower()}, {start_month} to {end_month}")
    ax.set_xlabel("Date")
    ax.set_ylabel(name)
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    fig.autofmt_xdate()  # tilted date labels so they don't overlap
    fig.tight_layout()
    st.pyplot(fig)

    # Close the figure after drawing it. Streamlit reruns the whole script on every
    # widget change, so open figures would otherwise pile up in memory.
    plt.close(fig)
