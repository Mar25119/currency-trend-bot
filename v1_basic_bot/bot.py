import logging
from datetime import datetime
from random import choice

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# === Настройка логгера ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Глобальные настройки ===
CURRENCIES = ["USD", "EUR", "CNY"]  
TOKEN = "нельзя такое на гит"  #Актуальный токен 

# === Обработчики команд ===


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n\n"
        "Я — бот прогнозирования тренда валют.\n"
        "Напишите /predict USD, /predict EUR или выберите в меню.",
        reply_markup=get_main_keyboard(),
    )


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Укажите валюту: /predict USD, /predict EUR и т.д."
        )
        return

    currency = context.args[0].upper()
    if currency not in CURRENCIES:
        await update.message.reply_text(
            f"Валюта '{currency}' не поддерживается.\n"
            f"Доступные: {', '.join(CURRENCIES)}"
        )
        return

    # === v1: Простой детерминированный прогноз ===
    minute = datetime.now().minute
    trend = "вверх" if minute % 2 == 0 else "вниз"
    confidence = 65 + (minute % 10)  # 65–74% — показывает "уверенность"

    response = (
        f"📈 Прогноз на {currency} на сегодня:\n"
        f"→ Направление: **{trend}**\n"
        f"→ Уверенность модели: {confidence}%\n\n"
        "Это v1 — без анализа данных. Во v2 будет реальная статистика."
    )
    await update.message.reply_text(response, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — приветствие\n"
        "/predict USD — прогноз для доллара\n"
        "/predict EUR — для евро\n"
        "/help — эта справка"
    )


# === Вспомогательные функции ===


def get_main_keyboard():
    buttons = [
        [KeyboardButton("/predict USD"), KeyboardButton("/predict EUR")],
        [KeyboardButton("/predict CNY"), KeyboardButton("/help")],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)


# === Основная функция запуска ===


def main() -> None:
    if TOKEN == "ТОКЕН_ОТ_BOTFATHER":
        raise ValueError("Замените TOKEN на реальный токен")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("predict", predict))
    application.add_handler(CommandHandler("help", help_command))

    # Запуск бота
    logger.info("✅ Бот v1.0 запущен. Ожидание сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
