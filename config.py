import os
from dotenv import load_dotenv

load_dotenv()

# 🔐 TELEGRAM
TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID", "")

# 🌐 ЦЕЛЕВОЙ САЙТ
TARGET_URL = "https://tickets.hclokomotiv.ru"

# 🎯 СПИСОК СОБЫТИЙ ДЛЯ МОНИТОРИНГА
TARGET_EVENTS = [
    {
        "id": "apr_24",
        "opponent": "авангард",
        "date": "24.04",
        "year": 2026,
        "label": "24 апреля"
    },
    {
        "id": "may_02",
        "opponent": "авангард",
        "date": "02.05",
        "year": 2026,
        "label": "2 мая"
    }
]

# ⏱ НАСТРОЙКИ
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "120"))  # секунд между проверками
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true" # true для облака, false для локального теста
TIMEOUT = 30000
BLOCK_RESOURCES = True

# 🔔 ШАБЛОН УВЕДОМЛЕНИЯ
NOTIFY_TEMPLATE = """
🚨 <b>БИЛЕТЫ В ПРОДАЖЕ!</b>
🏒 Локомотив — {opponent}
📅 {label}
🏟️ Арена 2000, Ярославль

🎫 <a href="{url}">Открыть сайт покупки</a>

⏰ Обнаружено: {timestamp}
"""

# 🧩 СЕЛЕКТОРЫ (платформа "Лента-Спорт")
SELECTORS = {
    "event_cards": [".event-card", ".match-item", ".schedule-row", "[data-event]", ".card", ".match-card"],
    "buy_buttons": [
        "button.btn-buy:not([disabled])", "a.btn-buy:not([disabled])", 
        ".buy-btn:not([disabled])", "button[data-action='buy']:not([disabled])", 
        "a[href*='/buy/']:not([disabled])"
    ],
    "sold_out_indicators": ["распродано", "нет билетов", "уведомить", "архив", "sold-out", "disabled"]
}