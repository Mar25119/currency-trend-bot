import logging
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    filters
)

# === Настройка логгера ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Константы ===
CURRENCY_CODES = {
    "USD": "R01235",  # USD → код в XML ЦБ
    "EUR": "R01239",
    "CNY": "R01375"
}
BASE_URL = "бот"
TOKEN = "8418519970:AAGt8FPMij2SVKUGwikoI4he3VgcKnwJ76U" 

# === Функции получения данных ===

def get_exchange_rate(date: datetime, currency: str) -> float | None:
    """Получает курс валюты на дату из API ЦБ РФ."""
    date_str = date.strftime("%d/%m/%Y")
    url = f"{BASE_URL}?date_req={date_str}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        # Ищем нужную валюту по ID
        for valute in root.findall("Valute"):
            if valute.find("CharCode").text == currency:
                nominal = int(valute.find("Nominal").text)
                value_str = valute.find("Value").text.replace(",", ".")
                value = float(value_str)
                return value / nominal  # Приводим к 1 единице валюты
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении курса {currency} на {date_str}: {e}")
        return None

def get_trend_prediction(currency: str) -> dict | None:
    """Возвращает прогноз на основе разницы курсов за два дня."""
    today = datetime.now().date()
    # Пытаемся взять вчерашний и позавчерашний день (если сегодня — выходной, ЦБ не публикует)
    date1 = today - timedelta(days=1)  # вчера
    date0 = today - timedelta(days=2)  # позавчера

    rate1 = get_exchange_rate(datetime.combine(date1, datetime.min.time()), currency)
    rate0 = get_exchange_rate(datetime.combine(date0, datetime.min.time()), currency)

    if rate1 is None or rate0 is None:
        return None

    delta = rate1 - rate0
    delta_pct = (delta / rate0) * 100
    trend = "вверх" if delta > 0 else "вниз" if delta < 0 else "без изменений"

    return {
        "currency": currency,
        "date_ref": date1.strftime("%d.%m.%Y"),
        "rate_ref": rate1,
        "rate_prev": rate0,
        "delta": delta,
        "delta_pct": delta_pct,
        "trend": trend
    }

# === Обработчики команд ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я — бот прогнозирования тренда валют (v2.0).\n"
        "Теперь я использую реальные курсы ЦБ РФ.\n\n"
        "Выберите валюту:",
        reply_markup=get_main_keyboard()
    )

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    currency = "USD"  # по умолчанию
    if context.args:
        currency = context.args[0].upper()

    if currency not in CURRENCY_CODES:
        await update.message.reply_text(
            f"Валюта '{currency}' не поддерживается.\n"
            f"Доступные: {', '.join(CURRENCY_CODES.keys())}"
        )
        return

    pred = get_trend_prediction(currency)

    if pred is None:
        await update.message.reply_text(
            "❌ Не удалось получить курсы за последние дни.\n"
            "Возможно, сегодня выходной или ЦБ ещё не обновил данные."
        )
        return

    # Форматирование
    rate_ref = f"{pred['rate_ref']:.4f}"
    delta_pct = f"{pred['delta_pct']:+.2f}"
    trend = pred["trend"]
    arrow = "📈" if trend == "вверх" else "📉" if trend == "вниз" else "➡️"

    response = (
        f"{arrow} Прогноз для {currency} (данные ЦБ РФ):\n"
        f"Дата: {pred['date_ref']}\n"
        f"Курс: {rate_ref} RUB\n"
        f"Изменение: {delta_pct}%\n"
        f"Направление: **{trend}**\n\n"
        "ℹ️ Прогноз основан на сравнении курса за два дня подряд."
    )
    await update.message.reply_text(response, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — приветствие\n"
        "/predict USD — прогноз для доллара (можно EUR, CNY)\n"
        "/help — эта справка\n\n"
        "v2.0: использует реальные курсы ЦБ РФ."
    )

# === Вспомогательные функции ===

def get_main_keyboard():
    buttons = [
        [KeyboardButton("/predict USD"), KeyboardButton("/predict EUR")],
        [KeyboardButton("/predict CNY"), KeyboardButton("/help")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

# === Запуск ===

def main() -> None:
    if TOKEN == "ВАШ_ТОКЕН_ОТ_BOTFATHER":
        raise ValueError("❗ Замените TOKEN на ваш реальный токен от @BotFather")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("predict", predict))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("✅ Бот v2.0 запущен. Использует API ЦБ РФ.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()