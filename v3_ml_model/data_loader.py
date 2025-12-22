import os
import json
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Кэш списка валют (загружается один раз)
_ALL_CURRENCIES = None


def get_all_currencies(refresh: bool = False) -> dict[str, str]:
    """Возвращает {CharCode: Name} для всех валют из XML ЦБ РФ."""
    global _ALL_CURRENCIES
    if _ALL_CURRENCIES and not refresh:
        return _ALL_CURRENCIES

    try:
        url = "https://cbr.ru/scripts/XML_daily.asp"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        _ALL_CURRENCIES = {
            valute.find("CharCode").text: valute.find("Name").text
            for valute in root.findall("Valute")
        }
        logger.info(f"✅ Загружено {len(_ALL_CURRENCIES)} валют из ЦБ РФ")
        return _ALL_CURRENCIES
    except Exception as e:
        logger.error(f"❌ Не удалось загрузить список валют: {e}")
        # fallback
        return {
            "USD": "Доллар США",
            "EUR": "Евро",
            "CNY": "Юань",
            "GBP": "Фунт стерлингов",
            "JPY": "Японская иена",
            "CHF": "Швейцарский франк",
        }


def _get_cache_path(date: datetime) -> Path:
    return CACHE_DIR / f"{date.strftime('%Y-%m-%d')}.json"


def _load_from_cache(date: datetime) -> dict | None:
    path = _get_cache_path(date)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Кэш повреждён {path}: {e}")
    return None


def _save_to_cache(date: datetime, data: dict) -> None:
    path = _get_cache_path(date)
    path.parent.mkdir(parents=True, exist_ok=True)  
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_exchange_rate(date: datetime, currency: str) -> float | None:
    cached = _load_from_cache(date)
    if cached and currency in cached:
        return cached[currency]

    date_str = date.strftime("%d/%m/%Y")
    url = f"https://cbr.ru/scripts/XML_daily.asp?date_req={date_str}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        rates = {}
        for valute in root.findall("Valute"):
            char_code = valute.find("CharCode").text
            nominal = int(valute.find("Nominal").text)
            value_str = valute.find("Value").text.replace(",", ".")
            value = float(value_str)
            rates[char_code] = value / nominal

        _save_to_cache(date, rates)
        return rates.get(currency)
    except Exception as e:
        logger.error(f"Ошибка при получении курса {currency} на {date_str}: {e}")
        return None


def get_rates_range(
    start_date: datetime, end_date: datetime, currency: str
) -> list[tuple[datetime, float]]:
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5: 
            rate = get_exchange_rate(current, currency)
            if rate is not None:
                dates.append((current, rate))
        current += timedelta(days=1)
    return dates
