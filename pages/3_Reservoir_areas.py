import matplotlib.pyplot as plt
import streamlit as st
from data_utils import load_all_reservoir_data

st.title("Reservoir fill ratio by area")

# All areas from the NVE API (cached in data_utils)
df = load_all_reservoir_data()

# Radio buttons: choose the type of area. The keys are the codes used in the data,
# format_func shows a readable label instead of the code.
area_labels = {
    "NO": "Norway (whole country)",
    "EL": "Price areas (EL, NO1-NO5)",
    "VASS": "Watercourse areas (VASS)",
}
area_type = st.radio(
    "Type of area",
    options=list(area_labels),
    format_func=lambda code: area_labels[code],
    horizontal=True,
)

# Interval slider: a (start, end) tuple as default value gives a range slider.
# Default is the last five years, so the seasonal pattern is readable.
first_year = int(df["date"].dt.year.min())
last_year = int(df["date"].dt.year.max())
start_year, end_year = st.slider(
    "Interval (years)",
    min_value=first_year,
    max_value=last_year,
    value=(last_year - 4, last_year),
)

# Keep only the chosen area type and years
selected = df[
    (df["area_type"] == area_type)
    & (df["date"].dt.year.between(start_year, end_year))
]

# One line per area number (e.g. EL 1-5), each with its own label in the legend
fig, ax = plt.subplots(figsize=(10, 5))
for area_number, area_df in selected.groupby("area_number"):
    label = "Norway" if area_type == "NO" else f"{area_type} {area_number}"
    ax.plot(area_df["date"], area_df["fill_ratio"], label=label)

ax.set_title(f"Fill ratio, {area_labels[area_type].lower()}, {start_year}-{end_year}")
ax.set_xlabel("Date")
ax.set_ylabel("Fill ratio (0-1)")
ax.grid(alpha=0.3)
ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
fig.tight_layout()
st.pyplot(fig)
plt.close(fig)  # Free memory, since Streamlit reruns the script on every widget change

st.caption(
    "Data: NVE Magasinstatistikk API. The API has no date parameters, so all data is "
    "downloaded once (cached for a day) and the slider selects the interval shown."
)