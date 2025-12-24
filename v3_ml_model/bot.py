# v3_ml_model/bot.py
import io
import logging
import numpy as np
from datetime import datetime, timedelta
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from model import predict_trend, get_advice
from plotter import plot_trend
from data_loader import get_all_currencies, get_rates_range
from feature_engineer import compute_rsi

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "token"  # ← замените при необходимости


def get_kb():
    return ReplyKeyboardMarkup(
        [["/predict USD 7", "/advice USD"], ["/how", "/clear", "/help"]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📈 Бот прогнозирования тренда валют (v3.0)\n"
        "• Единая ML-модель для всех валют\n"
        "• Аналитика: курс, RSI, волатильность\n"
        "• Советы и объяснимость\n\n"
        "Доступные команды:\n"
        "• /predict USD 7 — прогноз + график\n"
        "• /advice USD — аналитический совет\n"
        "• /how — как считается?\n"
        "• /clear — очистить сообщения",
        reply_markup=get_kb(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📘 Справка (v3.0):\n"
        "🔹 /predict <код> [N]\n"
        "   Примеры:\n"
        "   /predict USD        → 7 дней + ML + график\n"
        "   /predict GBP 10     → график за 10 дней\n"
        "   /predict CHF 01.12–18.12 → период\n\n"
        "🔹 /advice USD — совет по валюте\n"
        "🔹 /how — как работает расчёт?\n"
        "🔹 /clear — очистить последние сообщения бота\n\n"
        "ℹ️ Все данные — от ЦБ РФ. Прогнозы — аналитические."
    )
    await update.message.reply_text(text, reply_markup=get_kb())


async def how_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "ℹ️ *Как работает прогноз?*\n\n"
        "🔹 *Данные*: курсы ЦБ РФ (только будние дни), кэшируются локально.\n"
        "🔹 *Признаки* (4):\n"
        "   • Δ вчера vs позавчера,\n"
        "   • Среднее изменение за 5 дней,\n"
        "   • Волатильность (std изменений),\n"
        "   • RSI(5) — индекс силы тренда.\n"
        "🔹 *Модель*: Random Forest + калибровка вероятностей.\n"
        "🔹 *Уверенность*:\n"
        "   • >60% → «чёткий сигнал»,\n"
        "   • 40–60% → «неопределённо»,\n"
        "   • <40% → «слабый сигнал».\n"
        "🔹 *Прогноз*: направление (вверх/вниз) на завтра.\n\n"
        "⚠️ Это аналитический инструмент, а не финансовый совет."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_kb())


async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        n = int(context.args[0]) if context.args else 3
        n = min(max(n, 1), 10)
    except:
        n = 3

    deleted = 0
    msg_id = update.message.message_id

    for i in range(1, n + 1):
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id, message_id=msg_id - i
            )
            deleted += 1
        except Exception:
            continue

    confirm = await update.message.reply_text(f"🗑️ Удалено {deleted} сообщений.")
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=update.message.message_id
    )
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=confirm.message_id, timeout=2.0
    )


async def list_currencies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    currencies = get_all_currencies()
    items = [f"`{code}` — {name}" for code, name in sorted(currencies.items())]
    mid = (len(items) + 1) // 2
    col1 = items[:mid]
    col2 = items[mid:]
    max_len = max(len(line) for line in col1) if col1 else 0
    lines = []
    for i in range(max(len(col1), len(col2))):
        left = col1[i] if i < len(col1) else ""
        right = col2[i] if i < len(col2) else ""
        lines.append(f"{left.ljust(max_len)}   {right}")
    text = "💰 Доступные валюты (ЦБ РФ):\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=get_kb())


async def advice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text("📌 Укажите валюту: /advice USD")
        return

    curr = args[0].upper()
    currencies = get_all_currencies()
    if curr not in currencies:
        await update.message.reply_text(
            f"❌ Валюта `{curr}` не найдена. См. /list.", parse_mode="Markdown"
        )
        return

    advice = get_advice(curr)
    if not advice:
        await update.message.reply_text(f"⚠️ Не удалось сформировать совет для {curr}.")
        return

    text = (
        f"💡 *Аналитический совет по {curr}*:\n\n"
        f"{advice}\n\n"
        "⚠️ Это не финансовый совет. Информация носит ознакомительный характер."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "📌 Укажите валюту и (опционально) период:\n"
            "/predict USD 7\n/predict EUR 01.12–18.12",
            reply_markup=get_kb(),
        )
        return

    curr = args[0].upper()
    date_arg = args[1] if len(args) > 1 else "7"

    currencies = get_all_currencies()
    if curr not in currencies:
        await update.message.reply_text(
            f"❌ Валюта `{curr}` не найдена.\nСм. /list — полный список.",
            parse_mode="Markdown",
            reply_markup=get_kb(),
        )
        return

    # === 📊 Расширенная аналитика ===
    try:
        end = datetime.now()
        start = end - timedelta(days=20)
        full_data = get_rates_range(start, end, curr)
        if len(full_data) >= 3:
            rates = [r for _, r in full_data]
            dates = [d for d, _ in full_data]

            d1 = (rates[-1] - rates[-2]) / rates[-2] * 100 if len(rates) >= 2 else 0.0
            d3 = (rates[-1] - rates[-3]) / rates[-3] * 100 if len(rates) >= 3 else 0.0
            d7 = (rates[-1] - rates[-7]) / rates[-7] * 100 if len(rates) >= 7 else 0.0

            changes_7 = [
                (rates[i] - rates[i - 1]) / rates[i - 1]
                for i in range(max(1, len(rates) - 7), len(rates))
            ]
            vol_7 = np.std(changes_7) * 100 if len(changes_7) > 1 else 0.0
            vol_level = (
                "низкая" if vol_7 < 0.5 else "средняя" if vol_7 < 1.2 else "высокая"
            )

            rsi = compute_rsi(rates[-6:], period=5)
            rsi_status = (
                "перекупленность"
                if rsi > 70
                else "перепроданность" if rsi < 30 else "нейтрально"
            )

            stats_text = (
                f"📊 *{curr}/RUB* (на {dates[-1].strftime('%d.%m')}):\n"
                f"• Курс: {rates[-1]:.4f} ₽\n"
                f"• Δ (1 дн.): {d1:+.2f}%\n"
                f"• Δ (3 дн.): {d3:+.2f}%\n"
                f"• Δ (7 дн.): {d7:+.2f}%\n"
                f"• Волатильность (7 дн.): {vol_7:.2f}% ({vol_level})\n"
                f"• RSI(5): {rsi:.1f} ({rsi_status})"
            )
            await update.message.reply_text(stats_text, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Не удалось собрать статистику для {curr}: {e}")

    # === ✅ ML-прогноз (единая модель) ===
    res = predict_trend(curr)
    if res:
        if res["trend"] == "неопределённо":
            arrow = "❓"
        else:
            arrow = "📈" if res["trend"] == "вверх" else "📉"
        text = (
            f"{arrow} *Прогноз ML для {curr}*:\n"
            f"→ **{res['trend']}**\n"
            f"→ Уверенность: {res['confidence']}%\n"
            f"→ Основание: {res['reason']}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ Не удалось получить ML-прогноз для {curr}.")

    # === 📈 График ===
    img_bytes = plot_trend(curr, date_arg)
    if img_bytes:
        caption = f"📊 {curr}/RUB"
        if date_arg.isdigit():
            caption += f" за {date_arg} дн."
        else:
            caption += f" ({date_arg})"
        await update.message.reply_photo(io.BytesIO(img_bytes), caption=caption)
    else:
        await update.message.reply_text(
            "⚠️ Не удалось построить график. Проверьте дату."
        )


# === Запуск ===
def main():
    if not TOKEN or len(TOKEN) < 10:
        raise ValueError("❗ Укажите корректный токен")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("how", how_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("list", list_currencies))
    app.add_handler(CommandHandler("advice", advice_cmd))
    app.add_handler(CommandHandler("predict", predict))
    logger.info("✅ v3.0 запущен: аналитика + ML + советы + очистка")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
