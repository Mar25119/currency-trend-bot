import numpy as np
from datetime import datetime


def compute_rsi(prices: list[float], period: int = 5) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-(period + 1) :])
    gains = deltas[deltas > 0].sum() / period
    losses = -deltas[deltas < 0].sum() / period
    if losses == 0:
        return 100.0
    if gains == 0:
        return 0.0
    rs = gains / losses
    return 100.0 - (100.0 / (1.0 + rs))


def compute_features(dates_rates: list[tuple[datetime, float]], window=5):
    if len(dates_rates) < window + 1:
        return [], []
    X, y = [], []
    rates = [r for _, r in dates_rates]
    for i in range(window, len(rates)):
        window_rates = rates[i - window : i]
        today_rate = rates[i]
        prev_rate = rates[i - 1]

        delta_prev = (prev_rate - rates[i - 2]) / rates[i - 2] if i >= 2 else 0.0

        rel_changes = (
            [
                (window_rates[j] - window_rates[j - 1]) / window_rates[j - 1]
                for j in range(1, len(window_rates))
            ]
            if len(window_rates) > 1
            else [0.0]
        )
        delta_ma = float(np.mean(rel_changes))
        volatility = float(np.std(rel_changes)) if len(rel_changes) > 1 else 0.0

        rsi = compute_rsi(rates[:i], period=5)

        y_val = 1 if today_rate > prev_rate else 0
        X.append([delta_prev, delta_ma, volatility, rsi])
        y.append(y_val)
    return X, y
