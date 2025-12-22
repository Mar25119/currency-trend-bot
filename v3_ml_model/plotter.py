import io
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from data_loader import get_rates_range

def parse_date_range(arg: str, default_days=7) -> tuple[datetime, datetime] | None:
    arg = arg.strip()
    if arg.isdigit():
        n = max(1, int(arg))
        end = datetime.now()
        # ← Берём запас в 2×N дней, чтобы точно хватило будних
        start = end - timedelta(days=n * 2 + 5)
        return start, end

    # 2. Диапазон: DD.MM–DD.MM или DD.MM-DD.MM
    match = re.match(r"(\d{1,2})\.(\d{1,2})\s*[-–]\s*(\d{1,2})\.(\d{1,2})", arg)
    if match:
        d1, m1, d2, m2 = map(int, match.groups())
        year = datetime.now().year
        start = datetime(year, m1, d1)
        end = datetime(year, m2, d2)
        if start > end:
            start, end = end, start
        return start, end

    return None

def plot_trend(currency: str, date_arg: str = "7") -> bytes | None:
    dr = parse_date_range(date_arg)
    if not dr:
        return None

    start, end = dr
    all_data = get_rates_range(start, end, currency)
    if len(all_data) < 2:
        return None

    # Если запросили N дней — берём последние N точек
    n_requested = None
    if date_arg.isdigit():
        n_requested = int(date_arg)
        if n_requested > 0:
            all_data = all_data[-n_requested:]  # последние N записей

    if len(all_data) < 2:
        return None

    # Ограничиваем максимум
    if len(all_data) > 30:
        step = len(all_data) // 30
        all_data = all_data[::step] or all_data[:30]

    dates = [d.strftime("%d.%m") for d, _ in all_data]
    rates = [r for _, r in all_data]

    # Прогноз — только если запрашивали N дней И ≥2 точки
    show_pred = n_requested is not None and len(rates) >= 2
    pred_rate = None
    if show_pred:
        delta = rates[-1] - rates[-2]
        pred_rate = rates[-1] + delta
        dates.append("→")
        rates.append(pred_rate)

    # Построение
    plt.figure(figsize=(6.4, 3.2), dpi=120)
    plt.plot(dates, rates, marker='o', linewidth=1.1, markersize=3, color='black')

    if pred_rate is not None:
        plt.plot(["→"], [pred_rate], marker='x', color='black', markersize=6)

    plt.title(f"{currency}/RUB", fontsize=10, pad=8)
    plt.xlabel("Дата", fontsize=8, labelpad=4)
    plt.ylabel("Курс, руб.", fontsize=8, labelpad=4)
    plt.xticks(fontsize=7, rotation=35)
    plt.yticks(fontsize=7)
    plt.tight_layout(pad=1.5)
    plt.grid(False)
    for spine in ['top', 'right']:
        plt.gca().spines[spine].set_visible(False)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf.read()