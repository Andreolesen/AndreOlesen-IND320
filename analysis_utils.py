"""
Analysis functions for the Streamlit app (part 3).
The same functions are written and tested in Notebooks/IND320_part3.ipynb,
here they are collected in one module so the pages can import them.
Every function returns matplotlib figures, which the pages show with st.pyplot.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.fft import dct, idct
from scipy.signal import spectrogram
from scipy.stats import median_abs_deviation
from sklearn.neighbors import LocalOutlierFactor
from statsmodels.tsa.seasonal import STL


def precipitation_outliers(series, freq_cutoff=50, n_std=3.0):
    """
    Find outliers in a precipitation series with DCT high-pass filtering and robust SPC limits.

    series: precipitation as a pandas Series with a time index
    freq_cutoff: number of the lowest DCT frequencies that are removed (higher = more is seen as "slow" variation)
    n_std: how many robust standard deviations from the median the limits are

    Returns (figure, table of outliers, summary dictionary).
    """
    values = series.to_numpy(dtype=float)

    # DCT of the whole series. type 2 + norm="ortho" makes idct the exact inverse
    coefficients = dct(values, type=2, norm="ortho")

    # High-pass: remove the lowest frequencies -> seasonally adjusted variations (SATV)
    high_pass = coefficients.copy()
    high_pass[:freq_cutoff] = 0
    satv = idct(high_pass, type=2, norm="ortho")
    slow = values - satv  # the season and slow weather changes

    # Robust statistics for the SATV, estimated from the whole year
    center = np.median(satv)
    sigma = 1.4826 * median_abs_deviation(satv)
    upper = slow + center + n_std * sigma
    lower = slow + center - n_std * sigma
    is_outlier = (satv > center + n_std * sigma) | (satv < center - n_std * sigma)

    # Plot: precipitation, the SPC limits and the outliers in a contrasting colour
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(series.index, values, color="tab:blue", linewidth=0.6, label="Average precipitation")
    ax.plot(series.index, upper, color="black", linewidth=0.8, linestyle="--", label=f"SPC limits (±{n_std} σ)")
    ax.plot(series.index, lower, color="black", linewidth=0.8, linestyle="--")
    ax.scatter(series.index[is_outlier], values[is_outlier], color="tab:red", s=10, zorder=3, label="Outliers")
    ax.set_title(f"Precipitation with SPC outliers (DCT cut-off {freq_cutoff}, {n_std} σ)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Precipitation (mm/h)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    plt.close(fig)  # the figure is returned and shown by the caller

    outliers = pd.DataFrame({
        "precipitation": values[is_outlier],
        "satv": satv[is_outlier],
        "lower_limit": lower[is_outlier],
        "upper_limit": upper[is_outlier],
    }, index=series.index[is_outlier])

    summary = {
        "n_outliers": int(is_outlier.sum()),
        "share_outliers": round(float(is_outlier.mean()), 4),
        "n_above": int((satv > center + n_std * sigma).sum()),
        "n_below": int((satv < center - n_std * sigma).sum()),
        "robust_sigma": round(float(sigma), 4),
    }
    return fig, outliers, summary


def temperature_anomalies(series, contamination=0.01, n_neighbors=20):
    """
    Find anomalies in a temperature series with Local Outlier Factor on (time, temperature).

    series: temperature as a pandas Series with a time index
    contamination: proportion of points marked as anomalies
    n_neighbors: number of neighbours LOF uses

    Returns (figure, table of anomalies, summary dictionary).
    """
    # Features: hours since start and temperature, standardised to mean 0 and std 1
    hours = ((series.index - series.index[0]) / pd.Timedelta(hours=1)).to_numpy(dtype=float)
    features = np.column_stack([hours, series.to_numpy(dtype=float)])
    features = (features - features.mean(axis=0)) / features.std(axis=0)

    lof = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    is_anomaly = lof.fit_predict(features) == -1          # -1 = anomaly, 1 = normal
    score = -lof.negative_outlier_factor_                  # higher = more unusual

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(series.index, series.values, color="tab:blue", linewidth=0.6, label="Average temperature")
    ax.scatter(series.index[is_anomaly], series.values[is_anomaly], color="tab:red", s=12, zorder=3,
               label=f"LOF anomalies ({contamination:.0%})")
    ax.set_title(f"Temperature with LOF anomalies (contamination {contamination}, {n_neighbors} neighbours)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Temperature (°C)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()
    plt.close(fig)

    anomalies = pd.DataFrame({"temperature": series.values[is_anomaly], "lof_score": score[is_anomaly]},
                             index=series.index[is_anomaly]).sort_values("lof_score", ascending=False)

    summary = {
        "n_anomalies": int(is_anomaly.sum()),
        "share_anomalies": round(float(is_anomaly.mean()), 4),
        "coldest_anomaly": round(float(anomalies["temperature"].min()), 1),
        "warmest_anomaly": round(float(anomalies["temperature"].max()), 1),
        "months_with_most_anomalies": anomalies.index.month.value_counts().head(3).to_dict(),
    }
    return fig, anomalies, summary


def stl_decomposition(series, period=52, seasonal=13, trend=105, robust=True):
    """
    STL decomposition of a time series, plotted as four panels (original, trend, seasonal, remainder).

    series: pandas Series with a time index (here weekly filling degree)
    period: length of one season in number of observations (52 weeks)
    seasonal, trend: lengths of the seasonal and trend smoothers (odd numbers)
    robust: use robust fitting that reduces the weight of extreme values

    Returns the figure.
    """
    result = STL(series, period=period, seasonal=seasonal, trend=trend, robust=robust).fit()

    parts = [
        ("Original", series),
        ("Trend", result.trend),
        ("Seasonal", result.seasonal),
        ("Remainder", result.resid),
    ]
    fig, axes = plt.subplots(4, 1, figsize=(14, 9), sharex=True)
    for ax, (name, values) in zip(axes, parts):
        if name == "Remainder":
            ax.scatter(values.index, values, s=3)       # points make single weeks easier to see
            ax.axhline(0, color="black", linewidth=0.5)
        else:
            ax.plot(values.index, values, linewidth=0.9)
        ax.set_ylabel(name)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Date")
    fig.suptitle(f"STL of filling degree (period={period}, seasonal={seasonal}, trend={trend}, robust={robust})")
    fig.tight_layout()
    plt.close(fig)
    return fig


def filling_spectrogram(series, window_length=104, overlap=78, max_frequency=6):
    """
    Spectrogram of a weekly time series.

    series: pandas Series with a weekly time index
    window_length: weeks per window
    overlap: weeks shared by two neighbouring windows (must be smaller than window_length)
    max_frequency: highest frequency (cycles per year) shown in the plot

    Returns the figure.
    """
    weeks_per_year = 365.25 / 7
    frequencies, times, power = spectrogram(
        series.to_numpy(dtype=float),
        fs=weeks_per_year,        # samples per year -> frequencies in cycles per year
        nperseg=window_length,
        noverlap=overlap,
        detrend="constant",       # remove the mean in each window, so frequency 0 doesn't dominate
        scaling="spectrum",
    )
    # times are in years after the first week -> convert to dates for the x-axis
    dates = series.index[0] + pd.to_timedelta(times * 365.25, unit="D")

    fig, ax = plt.subplots(figsize=(14, 5))
    mesh = ax.pcolormesh(dates, frequencies, 10 * np.log10(power + 1e-12), shading="auto", cmap="viridis")
    ax.set_ylim(0, max_frequency)
    ax.set_title(f"Spectrogram of filling degree (window {window_length} weeks, overlap {overlap} weeks)")
    ax.set_xlabel("Date (centre of window)")
    ax.set_ylabel("Frequency (cycles per year)")
    fig.colorbar(mesh, ax=ax, label="Power (dB)")
    fig.tight_layout()
    plt.close(fig)
    return fig
