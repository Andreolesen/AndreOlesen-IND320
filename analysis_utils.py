"""
Analysis functions for the Streamlit app (written and tested in the part 3 notebook).
Part 4: the plots are Plotly figures (zoom, hover), styled by the "fjord" template in ui_utils.py, and the
outlier functions work on any weather property, not only precipitation and temperature.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.fft import dct, idct
from scipy.signal import spectrogram
from scipy.stats import median_abs_deviation
from sklearn.neighbors import LocalOutlierFactor
from statsmodels.tsa.seasonal import STL

from ui_utils import FJORD, GREY, OUTLIER

HOURS_PER_YEAR = 365.25 * 24


def spc_outliers(series, cutoff_per_year=25, n_std=3.0, label="Value", unit=""):
    """
    Outliers with DCT high-pass filtering and robust SPC limits, for any hourly weather series.

    series: hourly values as a pandas Series with a time index
    cutoff_per_year: variations slower than this many cycles per year are removed as "slow" (season and weather
                     systems). DCT coefficient k is k/2 cycles over the series, so k = 2 * cutoff * years.
    n_std: how many robust standard deviations from the median the limits are

    Returns (figure, table of outliers, summary dictionary).
    """
    values = series.to_numpy(dtype=float)
    years = len(values) / HOURS_PER_YEAR
    n_removed = max(1, int(round(2 * cutoff_per_year * years)))

    # DCT of the whole series. type 2 + norm="ortho" makes idct the exact inverse
    coefficients = dct(values, type=2, norm="ortho")
    high_pass = coefficients.copy()
    high_pass[:n_removed] = 0
    satv = idct(high_pass, type=2, norm="ortho")  # seasonally adjusted variations
    slow = values - satv

    # Robust statistics of the SATV
    center = np.median(satv)
    sigma = 1.4826 * median_abs_deviation(satv)
    upper = slow + center + n_std * sigma
    lower = slow + center - n_std * sigma
    above, below = satv > center + n_std * sigma, satv < center - n_std * sigma
    is_outlier = above | below

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=values, name=label, line=dict(color=FJORD, width=1)))
    fig.add_trace(go.Scatter(x=series.index, y=upper, name=f"SPC limits (±{n_std} σ)",
                             line=dict(color=GREY, width=1, dash="dash")))
    fig.add_trace(go.Scatter(x=series.index, y=lower, showlegend=False, hoverinfo="skip",
                             line=dict(color=GREY, width=1, dash="dash")))
    fig.add_trace(go.Scatter(x=series.index[is_outlier], y=values[is_outlier], name="Outliers", mode="markers",
                             marker=dict(color=OUTLIER, size=5)))
    fig.update_layout(title=f"{label} with SPC outliers (DCT cut-off {cutoff_per_year} cycles/year, {n_std} σ)",
                      yaxis_title=f"{label} ({unit})", xaxis_title="Time (UTC)", height=460, hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))

    outliers = pd.DataFrame({label: values[is_outlier], "SATV": satv[is_outlier], "lower limit": lower[is_outlier],
                             "upper limit": upper[is_outlier]}, index=series.index[is_outlier])
    summary = {
        "n_outliers": int(is_outlier.sum()),
        "share_outliers": float(is_outlier.mean()),
        "n_above": int(above.sum()),
        "n_below": int(below.sum()),
        "robust_sigma": float(sigma),
    }
    return fig, outliers, summary


def lof_anomalies(series, contamination=0.01, n_neighbors=20, label="Value", unit=""):
    """
    Anomalies with Local Outlier Factor on (time, value), for any hourly weather series.

    contamination: proportion of points marked as anomalies; n_neighbors: number of neighbours LOF uses.
    Returns (figure, table of anomalies, summary dictionary).
    """
    # Features: hours since start and the value, standardised to mean 0 and std 1
    hours = ((series.index - series.index[0]) / pd.Timedelta(hours=1)).to_numpy(dtype=float)
    features = np.column_stack([hours, series.to_numpy(dtype=float)])
    spread = features.std(axis=0)
    spread[spread == 0] = 1  # a constant series (e.g. no snow at all) cannot be scaled
    features = (features - features.mean(axis=0)) / spread

    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    is_anomaly = lof.fit_predict(features) == -1  # -1 = anomaly, 1 = normal
    score = -lof.negative_outlier_factor_          # higher = more unusual

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series.index, y=series.values, name=label, line=dict(color=FJORD, width=1)))
    fig.add_trace(go.Scatter(x=series.index[is_anomaly], y=series.values[is_anomaly], mode="markers",
                             name=f"LOF anomalies ({contamination:.1%})", marker=dict(color=OUTLIER, size=6)))
    fig.update_layout(title=f"{label} with LOF anomalies ({n_neighbors} neighbours)", yaxis_title=f"{label} ({unit})",
                      xaxis_title="Time (UTC)", height=460, hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"))

    anomalies = pd.DataFrame({label: series.values[is_anomaly], "LOF score": score[is_anomaly]},
                             index=series.index[is_anomaly]).sort_values("LOF score", ascending=False)
    summary = {
        "n_anomalies": int(is_anomaly.sum()),
        "share_anomalies": float(is_anomaly.mean()),
        "lowest": float(anomalies[label].min()) if len(anomalies) else float("nan"),
        "highest": float(anomalies[label].max()) if len(anomalies) else float("nan"),
        "months_with_most_anomalies": anomalies.index.month.value_counts().head(3).to_dict(),
    }
    return fig, anomalies, summary


def stl_decomposition(series, period=52, seasonal=13, trend=105, robust=True):
    """
    STL decomposition of the weekly fill ratio, plotted as four panels (original, trend, seasonal, remainder).
    seasonal, trend: lengths of the smoothers (odd numbers); robust: less weight to extreme weeks.
    Returns the figure.
    """
    result = STL(series, period=period, seasonal=seasonal, trend=trend, robust=robust).fit()
    parts = [("Original", series), ("Trend", result.trend), ("Seasonal", result.seasonal), ("Remainder", result.resid)]

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=[p[0] for p in parts])
    for row, (name, values) in enumerate(parts, start=1):
        if name == "Remainder":  # points make single weeks easier to see
            fig.add_trace(go.Scatter(x=values.index, y=values * 100, mode="markers", name=name,
                                     marker=dict(color=FJORD, size=3)), row=row, col=1)
            fig.add_hline(y=0, line=dict(color=GREY, width=1), row=row, col=1)
        else:
            fig.add_trace(go.Scatter(x=values.index, y=values * 100, name=name, line=dict(color=FJORD, width=1.2)),
                          row=row, col=1)
        fig.update_yaxes(title_text="%" if name in ("Original", "Trend") else "pp", row=row, col=1)
    fig.update_layout(title=f"STL of the fill ratio (period={period}, seasonal={seasonal}, trend={trend}, robust={robust})",
                      height=820, showlegend=False)
    return fig


def filling_spectrogram(series, window_length=104, overlap=78, max_frequency=6):
    """
    Spectrogram of a weekly series: frequency (cycles per year) over time, power as colour.
    window_length: weeks per window; overlap: weeks shared by two neighbouring windows.
    Returns the figure.
    """
    weeks_per_year = 365.25 / 7
    frequencies, times, power = spectrogram(
        series.to_numpy(dtype=float),
        fs=weeks_per_year,        # samples per year -> frequencies in cycles per year
        nperseg=window_length,
        noverlap=overlap,
        detrend="constant",       # remove the mean in each window, so frequency 0 does not dominate
        scaling="spectrum",
    )
    dates = series.index[0] + pd.to_timedelta(times * 365.25, unit="D")  # window centres as dates
    keep = frequencies <= max_frequency

    fig = go.Figure(go.Heatmap(
        x=dates, y=frequencies[keep], z=10 * np.log10(power[keep] + 1e-12),
        colorscale=[[0, "#F2F6F8"], [0.35, "#B5CCD6"], [0.65, "#5F8EA3"], [0.85, FJORD], [1, "#0E2F40"]],
        colorbar=dict(title=dict(text="Power (dB)", side="right"), thickness=12, outlinewidth=0),
        hovertemplate="%{x|%b %Y}<br>%{y:.2f} cycles/year<br>%{z:.1f} dB<extra></extra>",
    ))
    fig.update_layout(title=f"Spectrogram of the fill ratio (window {window_length} weeks, overlap {overlap} weeks)",
                      xaxis_title="Date (centre of window)", yaxis_title="Frequency (cycles per year)", height=480)
    return fig
