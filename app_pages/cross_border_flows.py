import calendar

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_utils import CONNECTION_NAMES, load_flow_options, load_month_flows, load_yearly_totals
from ui_utils import page_header

page_header("Cross-border flows", "explore", "Physical electricity flows between Norway and neighbouring countries (ENTSO-E).")

# Connections and years that exist in MongoDB (cached in data_utils)
connections, years = load_flow_options()

# Labels for the two directions, used by both columns
DIRECTION_LABELS = {"export": "Export (out of Norway)", "import": "Import (into Norway)"}
DIRECTION_COLOURS = {"export": "#1F5F7A", "import": "#C9810A"}

# st.columns splits the page into two columns side by side
left, right = st.columns([2, 3])  # right side wider, so all 12 month pills fit

# ---------------------------------------------------------------- left column: pie chart
with left:
    st.subheader("Yearly balance")

    # Radio buttons for the connection, with readable names instead of the codes
    connection = st.radio(
        "Connection",
        options=connections,
        format_func=lambda c: CONNECTION_NAMES.get(c, c),
    )
    # Selectbox for the year, default is the latest year
    year = st.selectbox("Year", options=years, index=len(years) - 1)

    totals = load_yearly_totals(connection, year)

    if not totals:
        st.warning("No data for this connection and year.")
    else:
        directions = [d for d in ["export", "import"] if d in totals]
        values = [totals[d] for d in directions]

        fig = go.Figure(go.Pie(
            labels=[DIRECTION_LABELS[d] for d in directions], values=values, hole=0.5, sort=False,
            marker=dict(colors=[DIRECTION_COLOURS[d] for d in directions]),
            texttemplate="%{percent:.0%}", hovertemplate="%{label}<br>%{value:.2f} TWh<extra></extra>",
        ))
        fig.update_layout(title=f"{CONNECTION_NAMES.get(connection, connection)}, {year}", height=380,
                          legend=dict(orientation="h", y=-0.1),
                          annotations=[dict(text=f"{sum(values):.1f} TWh", showarrow=False, font=dict(size=16))])
        st.plotly_chart(fig, theme=None)

# ---------------------------------------------------------------- right column: line plot
with right:
    st.subheader("Flow in chosen months")

    # Pills: choose which months to include (several can be chosen). January is the default,
    # like the plot in the notebook.
    chosen_months = st.pills(
        "Months",
        options=list(range(1, 13)),
        selection_mode="multi",
        default=[1],
        format_func=lambda m: calendar.month_abbr[m],
    )

    if not chosen_months:
        st.info("Choose at least one month.")
    else:
        fig = go.Figure()
        labelled = set()  # so each direction only gets one entry in the legend

        # One part of the line per chosen month, so months that are not next to each
        # other are not joined by a straight line across the gap
        for month in sorted(chosen_months):
            # The times in MongoDB are UTC, and the months there are UTC months. A Norwegian day starts at 22:00 or
            # 23:00 UTC the day before (summer/winter), so the last hours of the previous UTC month are loaded too,
            # the times are converted to Norwegian time, and only the days of the chosen month are kept.
            previous = load_month_flows(connection, year, month - 1) if month > 1 else load_month_flows(connection, year - 1, 12)
            month_data = pd.concat([previous, load_month_flows(connection, year, month)], ignore_index=True)
            if month_data.empty:
                continue
            times = pd.to_datetime(month_data["time"])
            times = times.dt.tz_localize("UTC") if times.dt.tz is None else times
            month_data["local_time"] = times.dt.tz_convert("Europe/Oslo")
            month_data = month_data[month_data["local_time"].dt.month == month]

            # Sum the hourly values per Norwegian day (GWh)
            daily = (
                month_data.groupby(["direction", month_data["local_time"].dt.date.rename("time")])["mwh"]
                .sum()
                .div(1000)
                .reset_index()
            )
            for direction in ["export", "import"]:
                line = daily[daily["direction"] == direction]
                fig.add_trace(go.Scatter(
                    x=line["time"], y=line["mwh"], mode="lines+markers", name=DIRECTION_LABELS[direction],
                    legendgroup=direction, showlegend=direction not in labelled,
                    line=dict(color=DIRECTION_COLOURS[direction], width=1.8), marker=dict(size=4),
                ))
                labelled.add(direction)

        month_names = ", ".join(calendar.month_abbr[m] for m in sorted(chosen_months))
        fig.update_layout(title=f"Daily flow, {month_names} {year}", yaxis_title="Energy per day (GWh)",
                          height=460, hovermode="x unified",
                          legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))
        st.plotly_chart(fig, theme=None)

# ---------------------------------------------------------------- data source
with st.expander("About the data"):
        st.markdown(
        """
        - **Source:** ENTSO-E Transparency Platform, physical cross-border flows (A11), 2024-2025.
        - **Processing:** Downloaded in the notebook, stored in Cassandra, summed to hourly energy with Spark
          and saved in MongoDB, which this page reads from. Export = out of Norway, import = into Norway.
        - **Time zone:** the hours are stored in UTC. They are converted to Norwegian time before they are summed
          per day, so a day on the plot is a Norwegian day (part 4; in part 3 the days were UTC days).
        """
    )
    
