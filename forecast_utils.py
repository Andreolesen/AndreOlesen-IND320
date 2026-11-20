"""
Forecast of the weekly fill ratio with River (moved here from the part 4 notebook, where the models are tested).

Two River models and a benchmark:
- "lags": a regression on the last weeks' fill ratios, the change in the same week last year, the time of year
  and the exogenous variables. It predicts the change to next week and is run step by step (dynamic forecast):
  each prediction becomes the newest lag. Learner: Bayesian linear regression.
- "snarimax": River's seasonal ARIMA with exogenous variables (period 52 weeks). The default, since it had the
  lowest error in the notebook's backtest (22 forecasts in 2021-2026).
- "naive": last year's development, shifted to start at today's level.
"""
import time

import numpy as np
import pandas as pd
from river import linear_model, optim, preprocessing, time_series

WEEKS_PER_YEAR = 52


def exog_features(row, exog_columns):
    """The exogenous variables of one week as a dict (River's input format)."""
    return {column: float(row[column]) for column in exog_columns}


def lag_features(fills, i, n_lags, date, row, exog_columns):
    """Input of the lag-based model for week i: the last n_lags fill ratios, the change in the same week last
    year, the time of year (sine and cosine of the week number) and the exogenous variables."""
    week = date.isocalendar().week
    x = {f"lag{k}": fills[i - k] for k in range(1, n_lags + 1)}  # lag1 = last week
    x["change_last_year"] = fills[i - WEEKS_PER_YEAR] - fills[i - WEEKS_PER_YEAR - 1]
    x["sin_week"] = np.sin(2 * np.pi * week / WEEKS_PER_YEAR)
    x["cos_week"] = np.cos(2 * np.pi * week / WEEKS_PER_YEAR)
    x.update(exog_features(row, exog_columns))
    return x


def exog_for_horizon(history, future_index, exog_columns):
    """Exogenous values for the forecast weeks: the mean of the same week in the training history (a "normal" year).
    The real future values are not used, not even when the forecast starts in the past: a real forecast of the
    coming months does not know the future weather, and the notebook showed that using it makes the forecast
    look better than it is."""
    normal = history[exog_columns].groupby(history.index.isocalendar().week.values).mean()
    fallback = normal.reindex(future_index.isocalendar().week.values).ffill().bfill()
    fallback.index = future_index
    return fallback


def forecast_filling(data, model="snarimax", history_weeks=520, horizon_weeks=26, cutoff=None,
                     p=2, d=0, q=1, sp=1, sd=1, sq=0, lr=0.01, n_lags=2):
    """
    Forecast the weekly fill ratio (0-1).

    data:          weekly DataFrame with the column "fill" and the exogenous columns to use.
    model:         "lags", "snarimax" or "naive".
    history_weeks: number of weeks before the cutoff used for training.
    horizon_weeks: number of weeks to forecast.
    cutoff:        last week of the training data (default: the last week with data).
    p, d, q, sp, sd, sq: SNARIMAX orders (seasonal period 52 weeks); lr: its learning rate.
    n_lags:        number of past weeks in the lag-based model.
    Returns (forecast Series, the cutoff that was used, seconds used).
    """
    exog_columns = [column for column in data.columns if column != "fill"]
    # Weeks without an exogenous value (e.g. the newest weeks, after the weather was last stored) get the mean of
    # the same week number in the other years, a "normal" value, instead of being dropped
    data = data.copy()
    week_numbers = data.index.isocalendar().week.values
    for column in exog_columns:
        normal = data[column].groupby(week_numbers).transform("mean")
        data[column] = data[column].fillna(normal)
    cutoff = data["fill"].dropna().index[-1] if cutoff is None else pd.Timestamp(cutoff)
    history = data.loc[:cutoff].dropna().iloc[-history_weeks:]
    cutoff = history.index[-1]  # the last complete week (the weather of the newest week may be missing)
    future_index = pd.date_range(cutoff, periods=horizon_weeks + 1, freq="W-SUN")[1:]
    future_exog = exog_for_horizon(history, future_index, exog_columns)
    fills = history["fill"].tolist()
    start = time.perf_counter()

    if model == "naive":
        last_year = data["fill"].reindex(future_index - pd.Timedelta(weeks=WEEKS_PER_YEAR)).to_numpy()
        values = fills[-1] + (last_year - data["fill"].loc[cutoff - pd.Timedelta(weeks=WEEKS_PER_YEAR)])

    elif model == "snarimax":
        regressor = preprocessing.StandardScaler() | linear_model.LinearRegression(optimizer=optim.SGD(lr),
                                                                                    intercept_lr=lr)
        arima = time_series.SNARIMAX(p=p, d=d, q=q, m=WEEKS_PER_YEAR, sp=sp, sd=sd, sq=sq, regressor=regressor)
        for _, row in history.iterrows():
            arima.learn_one(row["fill"], exog_features(row, exog_columns))
        xs = [exog_features(row, exog_columns) for _, row in future_exog.iterrows()]
        values = arima.forecast(horizon=horizon_weeks, xs=xs)

    elif model == "lags":
        # Bayesian linear regression has a closed-form update, so one pass over the history fits it exactly
        regressor = preprocessing.StandardScaler() | linear_model.BayesianLinearRegression()
        first = max(n_lags, WEEKS_PER_YEAR) + 1  # the features need a year of history
        for i in range(first, len(history)):
            x = lag_features(fills, i, n_lags, history.index[i], history.iloc[i], exog_columns)
            regressor.learn_one(x, fills[i] - fills[i - 1])  # target: the change since last week
        values = []
        for date, row in future_exog.iterrows():
            x = lag_features(fills, len(fills), n_lags, date, row, exog_columns)
            fills.append(fills[-1] + regressor.predict_one(x))  # the prediction becomes the newest lag
            values.append(fills[-1])
    else:
        raise ValueError(f"Unknown model: {model}")

    seconds = time.perf_counter() - start
    forecast = pd.Series(np.clip(np.asarray(values, dtype=float), 0, 1), index=future_index, name="forecast")
    return forecast, cutoff, seconds
