import streamlit as st
import pandas as pd
from data_utils import load_reservoir_data, column_display_names

st.title("Data table")

df, data_columns = load_reservoir_data()

# Rows in the first calendar month of the data. Uses the same "YYYY-MM" logic
# as the month slider on the plot page, so "first month" means the same thing.
first_month = df["date"].dt.strftime("%Y-%m").min()
first_month_df = df[df["date"].dt.strftime("%Y-%m") == first_month]

# Building a table with one row per column,
# where each row's "First month" cell holds that column's values for the
# first month as a list - st.column_config.LineChartColumn renders a list
# of numbers as a small sparkline chart inside the table cell.
table_data = pd.DataFrame({
    "Column": [column_display_names[c] for c in data_columns],
    "First month": [first_month_df[c].tolist() for c in data_columns],
})
    

st.subheader("Overview of the imported data")
st.dataframe(
    table_data,
    column_config={
        "First month": st.column_config.LineChartColumn(
            "First month (sparkline)",
            width="medium",
        ),
    },
    hide_index=True,
    width="stretch",
)