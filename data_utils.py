import pandas as pd
import streamlit as st


@st.cache_data
def load_reservoir_data():
    """
    Load and clean the reservoir data:
    - Filter to the national total series (omrType == "NO", omrnr == 0),
      since the raw file mixes several regions on the same dates.
    - Sort chronologically (raw rows are not sorted by date).
    - Rename columns to clear English names.
    - Keep only the date and the genuine data columns (drop region/ISO
      metadata columns that become redundant or constant after filtering).
    Cached so the CSV is only read and processed once per app session.
    """
    df = pd.read_csv("data/reservoirs.csv")

    df_national = df[(df["omrType"] == "NO") & (df["omrnr"] == 0)].copy()
    df_national["dato_Id"] = pd.to_datetime(df_national["dato_Id"])
    df_national = df_national.sort_values("dato_Id").reset_index(drop=True)

    df_national = df_national.rename(columns={
        "dato_Id": "date",
        "fyllingsgrad": "fill_ratio",
        "kapasitet_TWh": "capacity_TWh",
        "fylling_TWh": "fill_TWh",
        "fyllingsgrad_forrige_uke": "fill_ratio_previous_week",
        "endring_fyllingsgrad": "fill_ratio_change",
    })

    data_columns = [
        "fill_ratio",
        "capacity_TWh",
        "fill_TWh",
        "fill_ratio_previous_week",
        "fill_ratio_change",
    ]
    return df_national[["date"] + data_columns], data_columns