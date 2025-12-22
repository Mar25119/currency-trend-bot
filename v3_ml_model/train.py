import joblib
import numpy as np
import logging
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import classification_report, accuracy_score, brier_score_loss
from sklearn.utils.class_weight import compute_class_weight
from data_loader import get_all_currencies, get_rates_range
from feature_engineer import compute_features

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def collect_data_for_currency(currency: str, days_back: int = 1000):
    end = datetime.now()
    start = end - timedelta(days=days_back)
    return get_rates_range(start, end, currency)


def main():
    currencies = list(get_all_currencies().keys())
    logger.info(f"Начало сбора данных для {len(currencies)} валют")

    X_all, y_all = [], []
    stats = {}

    for curr in currencies:
        logger.info(f"→ {curr}...")
        data = collect_data_for_currency(curr)
        if len(data) < 10:
            stats[curr] = 0
            continue

        X, y = compute_features(data, window=5)
        if len(X) == 0:
            stats[curr] = 0
            continue

        X_all.extend(X)
        y_all.extend(y)
        stats[curr] = len(X)
        logger.info(f"   +{len(X)} примеров")

    X_all = np.array(X_all)
    y_all = np.array(y_all)
    total = len(X_all)
    logger.info(f"\n📊 Всего собрано: {total} примеров")

    if total < 50:
        logger.error("❌ Недостаточно данных. Соберите минимум 50 записей.")
        return

    # Разделение без перемешивания
    split_idx = int(0.8 * total)
    X_train, X_test = X_all[:split_idx], X_all[split_idx:]
    y_train, y_test = y_all[:split_idx], y_all[split_idx:]

    # 1. Базовая модель с балансировкой классов
    logger.info("Обучение RandomForest с class_weight='balanced'...")
    base_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_split=5,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    base_model.fit(X_train, y_train)

    # 2. Калибровка вероятностей (Isotonic — лучше для небольших данных)
    logger.info("Калибровка вероятностей (Isotonic Regression)...")
    calibrated_model = CalibratedClassifierCV(
        base_model, method="isotonic", cv=3  # 3-fold кросс-валидация внутри калибровки
    )
    calibrated_model.fit(X_train, y_train)

    # Оценка
    y_pred = calibrated_model.predict(X_test)
    y_proba = calibrated_model.predict_proba(X_test)[:, 1]
    acc = accuracy_score(y_test, y_pred)
    brier = brier_score_loss(y_test, y_proba)
    logger.info(f"\n✅ Точность: {acc:.2%} | Brier score: {brier:.4f}")
    print(
        classification_report(y_test, y_pred, target_names=["вниз", "вверх"], digits=3)
    )

    # Сохранение
    joblib.dump(calibrated_model, "model_all.pkl")
    logger.info("💾 Сохранено: model_all.pkl (RandomForest + balanced + isotonic)")

    # Важность признаков (на основе базовой модели)
    feat_names = ["delta_prev", "delta_ma", "volatility", "RSI"]
    importances = base_model.feature_importances_
    for name, imp in zip(feat_names, importances):
        logger.info(f"   {name}: {imp:.3f}")


if __name__ == "__main__":
    main()
