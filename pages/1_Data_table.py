import streamlit as st
import pandas as pd
from data_utils import load_reservoir_data

st.title("Data table")

df, data_columns = load_reservoir_data()

# Determine which rows fall within the first month of data
# (from the earliest date up to, but not including, one month later).
first_date = df["date"].min()
first_month_df = df[df["date"] < first_date + pd.DateOffset(months=1)]

# Build a table with one row PER COLUMN (as the assignment asks for),
# where each row's "First month" cell holds that column's values for the
# first month as a list - st.column_config.LineChartColumn renders a list
# of numbers as a small sparkline chart inside the table cell.
table_data = pd.DataFrame({
    "Column": data_columns,
    "First month": [first_month_df[col].tolist() for col in data_columns],
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
    use_container_width=True,
)