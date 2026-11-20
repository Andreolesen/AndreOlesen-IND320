"""
Shared look and global choices for all pages.

- Colours of the "Fjord" theme (the same as in .streamlit/config.toml and the sketch in the notebook).
- A Plotly template, so every Plotly figure gets the same font, colours and transparent background.
- The page header with the colour of the page's group, and a line with the global choices the page uses.
- The global choices (area type, area and period). They are chosen on the Overview page and kept in
  st.session_state, so every page uses the same area and period.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from data_utils import AREA_TYPE_LABELS, DEFAULT_AREA, area_label, load_area_numbers, load_month_labels

# ---------------------------------------------------------------- colours
FJORD = "#1F5F7A"     # main colour: data lines, selected area, buttons
TEXT = "#1B2631"
GREY = "#6B7B8C"
GRID = "#E1E7EC"
OUTLIER = "#C0392B"   # only for outliers and anomalies
GROUPS = {
    "overview": ("Overview", FJORD),
    "explore": ("Explore the data", "#1A7F8E"),
    "patterns": ("Patterns and anomalies", "#C9810A"),
    "forecast": ("Forecast", "#3C8D2F"),
}

# ---------------------------------------------------------------- Plotly template
# Registered once when the module is imported. Pages pass theme=None to st.plotly_chart, so Streamlit
# does not replace these settings with its own theme.
pio.templates["fjord"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", color=TEXT, size=13),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    colorway=[FJORD, "#1A7F8E", "#C9810A", "#3C8D2F", GREY, "#8E5A9B"],
    xaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(font=dict(family="Inter, sans-serif")),
    margin=dict(l=10, r=10, t=50, b=10),
))
pio.templates.default = "plotly_white+fjord"

# ---------------------------------------------------------------- global choices
DEFAULT_YEARS = 2  # default period: the last two years, so the yearly pattern is visible


def init_state():
    """Set the global choices the first time the app is opened (called from streamlit_app.py on every run)."""
    st.session_state.setdefault("area_type", DEFAULT_AREA[0])
    st.session_state.setdefault("area_number", DEFAULT_AREA[1])
    if "period" not in st.session_state:
        months = load_month_labels()
        st.session_state["period"] = (months[-12 * DEFAULT_YEARS], months[-1])


def selected_area():
    """The chosen (area_type, area_number)."""
    return st.session_state["area_type"], st.session_state["area_number"]


def selected_period():
    """The chosen period as two month labels ("YYYY-MM", "YYYY-MM")."""
    return st.session_state["period"]


def month_name(label):
    """ "2024-01" -> "Jan 2024" """
    return pd.Timestamp(label).strftime("%b %Y")


# ---------------------------------------------------------------- page elements
# The theme in config.toml cannot style the menu bar, so a little CSS is added on every page: the menu is
# centred and the text is larger, so the menu is easier to see. The selectors are Streamlit's own test ids.
MENU_CSS = """
<style>
div:has(> div > [data-testid="stTopNavSection"]) { justify-content: center; gap: 1.2rem; }
@media (min-width: 900px) {  /* on wide screens the menu sits in the middle of the page */
  div:has(> div > [data-testid="stTopNavSection"]) { position: absolute; left: 50%; transform: translateX(-50%); }
}
[data-testid="stTopNavLink"] p, [data-testid="stTopNavSection"] p { font-size: 1.05rem; font-weight: 500; }
[data-testid="stTopNavLink"], [data-testid="stTopNavSection"] { padding: 0.35rem 0.8rem; height: auto; }
[data-testid="stTopNavLink"] [data-testid="stIconMaterial"],
[data-testid="stTopNavSection"] [data-testid="stIconMaterial"] { font-size: 1.25rem; }
</style>
"""


def menu_style():
    """Add the CSS for the menu bar (called from streamlit_app.py on every run)."""
    st.html(MENU_CSS)


def page_header(title, group, text=None):
    """Title with the group name above it and a short bar in the group's colour below it."""
    name, colour = GROUPS[group]
    st.markdown(
        f'<p style="color:{colour}; font-weight:600; letter-spacing:0.08em; font-size:0.8rem; '
        f'margin-bottom:-0.8rem">{name.upper()}</p>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.markdown(
        f'<div style="width:64px; height:4px; border-radius:2px; background:{colour}; margin:-0.6rem 0 1rem 0"></div>',
        unsafe_allow_html=True,
    )
    if text:
        st.write(text)


def _set_area_type():
    """Callback for the area type in the popover: new type, and an area number that exists for it."""
    area_type = st.session_state["popover_area_type"]
    if area_type is None:  # the user clicked the chosen option again
        return
    numbers = load_area_numbers(area_type)
    st.session_state["area_type"] = area_type
    if st.session_state["area_number"] not in numbers:  # keep e.g. area 3 if the new type has it
        st.session_state["area_number"] = numbers[0]


def _set_area_number():
    st.session_state["area_number"] = st.session_state["popover_area_number"]


def _set_period():
    st.session_state["period"] = st.session_state["popover_period"]


def selection_line(area_text=None, show_period=True):
    """
    One line under the page header with the global choices this page uses (area and/or period), and a button
    that opens a small popover where they can be changed without going back to the Overview page.
    area_text: text for the area (default: the chosen area, e.g. "NO3", and the popover lets you choose the area).
    A text such as "Price areas" means the page only uses the area type; "" means the page does not use the area.

    The global choices are kept under their own keys ("area_type", "area_number", "period"), since Streamlit
    forgets a widget's state when you go to another page. The popover widgets get the global value before they
    are drawn, and their callbacks write the new value back, so the Overview page and all other pages follow.
    """
    use_type = area_text != ""
    use_number = area_text is None
    parts = [area_text if area_text is not None else area_label(*selected_area())]
    if show_period:
        start, end = selected_period()
        parts.append(f"{month_name(start)} – {month_name(end)}")
    text, change = st.columns([3, 1], vertical_alignment="center")
    text.markdown(":material/location_on: " + " · ".join(f"**{p}**" if i == 0 else p for i, p in enumerate(parts) if p))

    label = "Change area and period" if use_type and show_period else "Change area" if use_type else "Change period"
    with change.popover(label, icon=":material/tune:", width="stretch"):
        if use_type:
            st.session_state["popover_area_type"] = st.session_state["area_type"]
            st.segmented_control("Type of area", options=list(AREA_TYPE_LABELS), format_func=AREA_TYPE_LABELS.get,
                                 key="popover_area_type", on_change=_set_area_type)
        if use_number:
            area_type = st.session_state["area_type"]
            numbers = load_area_numbers(area_type)
            if len(numbers) > 1:  # Norway has only one "area"
                st.session_state["popover_area_number"] = st.session_state["area_number"]
                st.selectbox("Area", options=numbers, format_func=lambda n: area_label(area_type, n),
                             key="popover_area_number", on_change=_set_area_number)
        if show_period:
            # A range slider needs a tuple as value (otherwise it becomes a single slider), so the global value is
            # passed as value, and an old widget state that no longer matches the global period is removed first.
            period = tuple(st.session_state["period"])
            if st.session_state.get("popover_period", period) != period:
                del st.session_state["popover_period"]
            st.select_slider("Period", options=load_month_labels(), value=period, format_func=month_name,
                             key="popover_period", on_change=_set_period)
        st.page_link("app_pages/overview.py", label="Choose on the map instead", icon=":material/map:")
