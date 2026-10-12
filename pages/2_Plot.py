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

fig, ax = plt.subplots(figsize=(9, 4.5))

if selected_column == "All columns":
    # Two y-axes instead of normalising: in part 1 the normalised lines overlapped, because
    # fill_TWh is just fill_ratio x a constant capacity (the two lines became identical).
    # Left axis: fill ratio and fill ratio previous week (same unit, 0-1).
    # Right axis: weekly change, which can be negative and has a much smaller scale.
    ax.plot(filtered_df["date"], filtered_df["fill_ratio"], color="tab:blue", linewidth=1.8,
            label=column_display_names["fill_ratio"])
    ax.plot(filtered_df["date"], filtered_df["fill_ratio_previous_week"], color="tab:blue", linewidth=1.2,
            linestyle="--", alpha=0.7, label=column_display_names["fill_ratio_previous_week"])
    ax.set_ylabel("Fill ratio (0-1)", color="tab:blue")

    ax_right = ax.twinx()
    ax_right.plot(filtered_df["date"], filtered_df["fill_ratio_change"], color="tab:red", linewidth=1.2,
                  label=column_display_names["fill_ratio_change"])
    ax_right.axhline(0, color="tab:red", linewidth=0.5, linestyle=":")  # above 0 = filling, below = emptying
    ax_right.set_ylabel("Weekly change", color="tab:red")

    # Collect the legend entries from both axes into one legend
    lines = ax.get_lines() + ax_right.get_lines()[:1]
    ax.legend(lines, [line.get_label() for line in lines], loc="upper left", bbox_to_anchor=(1.12, 1.0))
    ax.set_title(f"All columns, {start_month} to {end_month}")
    st.caption(
        "Fill ratio and the previous week are on the left axis, the weekly change on the right axis. "
        "Fill (TWh) is not shown here since it is the fill ratio times the constant capacity (the same curve), "
        "and capacity is constant. Both can be chosen as single columns in the menu above."
    )
else:
    ax.plot(filtered_df["date"], filtered_df[selected_column], linewidth=1.8)
    ax.set_ylabel(column_display_names[selected_column])
    ax.set_title(f"{column_display_names[selected_column]}, {start_month} to {end_month}")

ax.set_xlabel("Date")
ax.grid(alpha=0.3)
fig.autofmt_xdate()  # tilted date labels so they don't overlap
fig.tight_layout()
st.pyplot(fig)

st.caption("Tip: drag the slider to see a longer period, for example a whole year to see the seasonal pattern.")

# Close the figure after drawing it. Streamlit reruns the whole script on every
# widget change, so open figures would otherwise pile up in memory.
plt.close(fig)