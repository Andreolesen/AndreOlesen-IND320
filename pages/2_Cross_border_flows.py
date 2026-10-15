import calendar

import matplotlib.pyplot as plt
import streamlit as st
from data_utils import CONNECTION_NAMES, load_flow_options, load_month_flows, load_yearly_totals

st.title("Cross-border electricity flows")
st.write(
    "Physical flows between the Norwegian price areas and the neighbouring countries. "
    "Choose a connection and a year on the left, and directions and a month on the right."
)

# Connections and years that exist in MongoDB (cached in data_utils)
connections, years = load_flow_options()

# Labels for the two directions, used by both columns
DIRECTION_LABELS = {"export": "Export (out of Norway)", "import": "Import (into Norway)"}
DIRECTION_COLOURS = {"export": "tab:blue", "import": "tab:orange"}

# st.columns splits the page into two columns side by side
left, right = st.columns(2)

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

        fig, ax = plt.subplots(figsize=(5, 5))
        ax.pie(
            values,
            labels=[f"{DIRECTION_LABELS[d]}\n{totals[d]:.2f} TWh" for d in directions],
            colors=[DIRECTION_COLOURS[d] for d in directions],
            autopct="%1.0f%%",
            startangle=90,
        )
        ax.set_title(f"{CONNECTION_NAMES.get(connection, connection)}, {year}")
        st.pyplot(fig)
        plt.close(fig)  # free memory, Streamlit reruns the script on every widget change

# ---------------------------------------------------------------- right column: line plot
with right:
    st.subheader("Flow in one month")

    # Pills: choose which directions to show (both by default). This replaces the
    # "production groups" in the task text, since the flow data has directions instead.
    chosen_directions = st.pills(
        "Directions",
        options=["export", "import"],
        selection_mode="multi",
        default=["export", "import"],
        format_func=lambda d: DIRECTION_LABELS[d],
    )
    # Month selector with month names instead of numbers
    month = st.selectbox("Month", options=list(range(1, 13)), format_func=lambda m: calendar.month_name[m])

    month_data = load_month_flows(connection, year, month)

    if not chosen_directions:
        st.info("Choose at least one direction.")
    elif month_data.empty:
        st.warning("No data for this month.")
    else:
        # Sum the hourly values per day (GWh), same as the plot in the notebook
        daily = (
            month_data.groupby(["direction", month_data["time"].dt.date])["mwh"]
            .sum()
            .div(1000)
            .reset_index()
        )

        fig, ax = plt.subplots(figsize=(7, 5))
        for direction in chosen_directions:
            line = daily[daily["direction"] == direction]
            ax.plot(line["time"], line["mwh"], color=DIRECTION_COLOURS[direction],
                    linewidth=1.8, marker="o", markersize=3, label=DIRECTION_LABELS[direction])

        ax.set_title(f"Daily flow, {calendar.month_name[month]} {year}")
        ax.set_xlabel("Date")
        ax.set_ylabel("Energy per day (GWh)")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.autofmt_xdate()  # tilted date labels so they don't overlap
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

# ---------------------------------------------------------------- data source
with st.expander("About the data"):
        st.markdown(
        """
        - **Source:** ENTSO-E Transparency Platform, physical cross-border flows (A11), 2024-2025.
        - **Processing:** Downloaded in the notebook, stored in Cassandra, summed to hourly energy with Spark
          and saved in MongoDB, which this page reads from. Export = out of Norway, import = into Norway.
        """
    )
    
