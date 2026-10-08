import streamlit as st
# Page settings for the home page: browser tab title, icon and wide layout.
st.set_page_config(page_title="IND320 - Data to Decision", page_icon=":bar_chart:", layout="wide")
# Home page of the app. Streamlit automatically adds every .py file in the
# pages/ folder to the sidebar menu (ordered by the number prefix), so the
# navigation to the other pages comes from the folder structure.

st.title("IND320 - Data to Decision")
st.write("This is a Streamlit app for the IND320 course.")
st.write("Use the menu in the sidebar to open the data table and the plot page.")

