import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from data_utils import load_reservoir_data

st.title("Plot")

df, data_columns = load_reservoir_data()


#  A sorted list of unique "YYYY-MM" labels to use as slider options
month_labels = sorted(df["date"].dt.strftime("%Y-%m").unique())

# Readable labels for the dropdown, the actual column names stay the same internally
column_display_names = {
    "fill_ratio": "Fill ratio",
    "capacity_TWh": "Capacity (TWh)",
    "fill_TWh": "Fill (TWh)",
    "fill_ratio_previous_week": "Fill ratio, previous week",
    "fill_ratio_change": "Fill ratio, week-over-week change",
}

# Dropdown: choose a single column, or "All columns".
selected_label = st.selectbox(
    "Choose a column to plot",
    options=["All columns"] + [column_display_names[c] for c in data_columns],
)

# Translate the friendly label back to the real column name.
label_to_column = {v: k for k, v in column_display_names.items()}
selected_column = label_to_column.get(selected_label, "All columns")

# Range slider over months, defaulting to just the first month (start == end).
start_month, end_month = st.select_slider(
    "Choose a range of months",
    options=month_labels,
    value=(month_labels[0], month_labels[0]),
)

# Filter the data down to rows whose year-month falls within the selected range.
row_month = df["date"].dt.strftime("%Y-%m")
filtered_df = df[(row_month >= start_month) & (row_month <= end_month)]

fig, ax = plt.subplots(figsize=(10, 5))

if selected_column == "All columns":
    # normalise so columns with very
    # different scales can be compared, excluding the near-constant capacity_TWh.
    columns_to_plot = [c for c in data_columns if c != "capacity_TWh"]
    # Normalise using min/max from the full dataset 
    normalized = (filtered_df[columns_to_plot] - df[columns_to_plot].min()) / (
        df[columns_to_plot].max() - df[columns_to_plot].min()
    )
    for column in columns_to_plot:
        ax.plot(filtered_df["date"], normalized[column], label=column)
    ax.set_ylabel("Normalised value (0-1)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.set_title(f"All columns (normalised), {start_month} to {end_month}")
else:
    ax.plot(filtered_df["date"], filtered_df[selected_column])
    ax.set_ylabel(selected_column)
    ax.set_title(f"{selected_column}, {start_month} to {end_month}")

ax.set_xlabel("Date")
ax.grid(alpha=0.3)
fig.tight_layout()
st.pyplot(fig)