# v3_ml_model/model.py
import joblib
import numpy as np
from datetime import datetime, timedelta
from data_loader import get_rates_range
from feature_engineer import compute_features, compute_rsi

def predict_trend(currency: str) -> dict | None:
    try:
        model = joblib.load("model_all.pkl")
    except FileNotFoundError:
        return None

    end = datetime.now()
    start = end - timedelta(days=20)
    data = get_rates_range(start, end, currency)
    if len(data) < 7:
        return None

    recent = data[-7:]
    X, _ = compute_features(recent, window=5)
    if not X:
        return None

    proba = model.predict_proba([X[-1]])[0]
    pred = model.predict([X[-1]])[0]
    raw_conf = float(proba[pred])
    trend = "вверх" if pred == 1 else "вниз"

    # Калибровка уверенности
    if raw_conf < 0.40:
        display_conf = round((0.5 - raw_conf) * 200, 1)
        trend = "вниз"
        reason_base = "слабый нисходящий сигнал"
    elif raw_conf > 0.60:
        display_conf = round(raw_conf * 100, 1)
        reason_base = "чёткий сигнал"
    else:
        return {
            "trend": "неопределённо",
            "confidence": round((0.5 - abs(raw_conf - 0.5)) * 200, 1),
            "reason": "противоречивые факторы: тренд и волатильность"
        }

    delta_prev, delta_ma, volatility, rsi = X[-1]
    details = []
    if delta_prev > 0:
        details.append("рост вчера")
    elif delta_prev < 0:
        details.append("падение вчера")
    if rsi > 70:
        details.append("RSI >70 → перекупленность")
    elif rsi < 30:
        details.append("RSI <30 → перепроданность")
    if volatility < 0.004:
        details.append("низкая волатильность")
    elif volatility > 0.012:
        details.append("высокая волатильность")

    reason = f"{reason_base} ({', '.join(details) if details else 'нейтральные факторы'})"

    return {
        "trend": trend,
        "confidence": display_conf,
        "reason": reason
    }


def get_advice(currency: str) -> str | None:
    end = datetime.now()
    start = end - timedelta(days=15)
    data = get_rates_range(start, end, currency)
    if len(data) < 5:
        return None

    rates = [r for _, r in data]
    changes = [(rates[i] - rates[i-1]) / rates[i-1] for i in range(1, len(rates))]
    vol = (sum(x**2 for x in changes[-5:]) / 5) ** 0.5 * 100
    delta_1d = (rates[-1] - rates[-2]) / rates[-2] * 100 if len(rates) >= 2 else 0.0
    delta_7d = (rates[-1] - rates[-7]) / rates[-7] * 100 if len(rates) >= 7 else 0.0

    lines = []

    if vol > 1.5:
        lines.append("❗ Высокая волатильность — возможны резкие движения.")
    elif vol < 0.4:
        lines.append("ℹ️ Низкая волатильность — рынок в диапазоне.")

    if delta_1d > 1.0:
        lines.append("📈 Резкий рост за день — возможна коррекция.")
    elif delta_1d < -1.0:
        lines.append("📉 Резкое падение за день — возможен отскок.")

    if delta_7d > 3.0:
        lines.append("📈 Устойчивый рост за неделю — тренд сильный.")
    elif delta_7d < -3.0:
        lines.append("📉 Устойчивое падение за неделю — тренд слабый.")

    if not lines:
        lines.append("📊 Рынок в нейтральной фазе. Следите за RSI и волатильностью.")

    return "\n".join(lines)