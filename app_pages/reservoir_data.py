import pandas as pd
import plotly.express as px
import streamlit as st
from data_utils import AREA_TYPE_LABELS, DATA_COLUMNS, area_label, column_display_names, load_reservoir_interval
from ui_utils import month_name, page_header, selected_area, selected_period, selection_line

page_header("Reservoir data", "explore", "Weekly reservoir statistics from NVE for all areas of the chosen type.")

# The type of area and the period are global choices from the Overview page (st.session_state).
# The column is a local choice, since it only matters on this page.
area_type, _ = selected_area()
start_month, end_month = selected_period()

selection_line(area_text=AREA_TYPE_LABELS[area_type])
choice, _ = st.columns([2, 3])
column = choice.selectbox("Column", options=DATA_COLUMNS, format_func=lambda c: column_display_names[c])

# The NVE API has no date parameters, so the full data set is downloaded once (cached for a day)
# and only the chosen period and type of area are kept (cached per choice in data_utils)
data = load_reservoir_interval(area_type, start_month, end_month)
if data.empty:
    st.warning("No data for this choice.")
    st.stop()

name = column_display_names[column]
table_tab, plot_tab = st.tabs(["Table", "Plot"])

# ---------------------------------------------------------------- table with LineChartColumn
with table_tab:
    # One row per area. The "Development" cell holds the list of values in the period,
    # which LineChartColumn draws as a small line chart inside the table.
    rows = []
    for number, area_data in data.groupby("area_number"):
        values = area_data[column].tolist()
        rows.append({"Area": area_label(area_type, number), "Development": values, "First": values[0],
                     "Last": values[-1], "Min": min(values), "Max": max(values)})
    st.dataframe(
        pd.DataFrame(rows),
        column_config={
            "Development": st.column_config.LineChartColumn(
                f"{name}, {month_name(start_month)} – {month_name(end_month)}", width="large",
                # Same scale in every row, so the areas can be compared
                y_min=float(data[column].min()), y_max=float(data[column].max()),
            ),
            "First": st.column_config.NumberColumn(format="%.3f"),
            "Last": st.column_config.NumberColumn(format="%.3f"),
            "Min": st.column_config.NumberColumn(format="%.3f"),
            "Max": st.column_config.NumberColumn(format="%.3f"),
        },
        hide_index=True,
        width="stretch",
    )

# ---------------------------------------------------------------- plot (Plotly: zoom, hover, click legend to hide areas)
with plot_tab:
    plot_data = data.assign(Area=[area_label(area_type, n) for n in data["area_number"]])
    fig = px.line(plot_data, x="date", y=column, color="Area",
                  labels={"date": "", column: name},
                  title=f"{name}, {AREA_TYPE_LABELS[area_type].lower()}, {month_name(start_month)} – {month_name(end_month)}")
    fig.update_layout(hovermode="x unified", height=480)
    st.plotly_chart(fig, theme=None)
