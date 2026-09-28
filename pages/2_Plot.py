import streamlit as st
import matplotlib.pyplot as plt
from data_utils import load_reservoir_data, column_display_names

st.title("Plot")

df, data_columns = load_reservoir_data()


#  A sorted list of unique "YYYY-MM" labels to use as slider options
month_labels = sorted(df["date"].dt.strftime("%Y-%m").unique())


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
    # Min-max normalise so columns with very different scales can be compared.
    # capacity_TWh is left out because it is constant (see the notebook).
    columns_to_plot = [c for c in data_columns if c != "capacity_TWh"]
    # Use min/max from the full dataset, not just the selected months, so the
    # scale stays the same when the slider is moved.
    normalized = (filtered_df[columns_to_plot] - df[columns_to_plot].min()) / (
        df[columns_to_plot].max() - df[columns_to_plot].min()
    )
    for column in columns_to_plot:
        ax.plot(filtered_df["date"], normalized[column], label=column_display_names[column])
    ax.set_ylabel("Normalised value (0-1)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.set_title(f"All columns (normalised), {start_month} to {end_month}")
    st.caption("All columns are min-max normalised to 0-1 so they can be compared on one axis. "
               "Capacity is left out because it is constant.")
else:
    ax.plot(filtered_df["date"], filtered_df[selected_column])
    ax.set_ylabel(column_display_names[selected_column])
    ax.set_title(f"{column_display_names[selected_column]}, {start_month} to {end_month}")

ax.set_xlabel("Date")
ax.grid(alpha=0.3)
fig.tight_layout()
st.pyplot(fig)

# Close the figure after drawing it. Streamlit reruns the whole script on every
# widget change, so open figures would otherwise pile up in memory.
plt.close(fig)