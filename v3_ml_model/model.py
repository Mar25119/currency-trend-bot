import joblib
import numpy as np
from datetime import datetime, timedelta
from data_loader import get_rates_range
from feature_engineer import compute_features

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

    # Прогноз
    proba = model.predict_proba([X[-1]])[0]
    pred = model.predict([X[-1]])[0]
    raw_conf = float(proba[pred])
    trend = "вверх" if pred == 1 else "вниз"

    # КАЛИБРОВКА + ИНТЕРПРЕТАЦИЯ
    if raw_conf < 0.40:
        # Низкая уверенность → "вниз" с пониженной степенью
        display_conf = round((0.5 - raw_conf) * 200, 1)  # 0.35 → 30.0%
        trend = "вниз"
        reason_base = "слабый нисходящий сигнал"
    elif raw_conf > 0.60:
        # Чёткий сигнал
        display_conf = round(raw_conf * 100, 1)
        reason_base = "чёткий сигнал"
    else:
        # 0.40–0.60 → неопределённость
        return {
            "trend": "неопределённо",
            "confidence": round((0.5 - abs(raw_conf - 0.5)) * 200, 1),
            "reason": "противоречивые факторы: тренд и волатильность"
        }

    # Уточнение причины
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