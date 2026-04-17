#!/usr/bin/env python3
"""
🎫 Монитор билетов ХК Локомотив
Отслеживает появление билетов на заданные матчи и отправляет уведомления в Telegram.
"""
import asyncio
import logging
import re
import sys
import ssl
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TARGET_URL, TARGET_EVENTS,
    CHECK_INTERVAL, HEADLESS, TIMEOUT, BLOCK_RESOURCES, NOTIFY_TEMPLATE, SELECTORS
)

# 🔧 Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# 🔒 Автоматический SSL-фикс ТОЛЬКО для локального запуска на macOS
# В облаке (Linux) он не применяется и не мешает работе.
if sys.platform == "darwin" and not HEADLESS:
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
        logger.warning("⚠️ Применён локальный SSL-фикс для macOS (для тестов)")
    except:
        pass

def parse_russian_date(text: str, target_year: int) -> str | None:
    """Извлекает дату в формате ДД.ММ из текста"""
    if not text: return None
    months = {
        'янв':'01','фев':'02','мар':'03','апр':'04','май':'05','июн':'06','июл':'07','авг':'08','сен':'09','окт':'10','ноя':'11','дек':'12',
        'мая':'05','июня':'06','июля':'07','августа':'08','сентября':'09','октября':'10','ноября':'11','декабря':'12'
    }
    text_clean = re.sub(r'\s+', ' ', text.strip().lower())
    # "2 мая"
    m = re.search(r'(\d{1,2})\s+([а-яё]+)', text_clean)
    if m:
        d, mon = m.groups()
        mc = months.get(mon[:3]) or months.get(mon)
        if mc: return f"{d.zfill(2)}.{mc}"
    # "02.05"
    m = re.search(r'(\d{1,2})\.(\d{2})', text_clean)
    if m: return f"{m.group(1).zfill(2)}.{m.group(2)}"
    return None

def is_sold_out(text: str) -> bool:
    return any(ind.lower() in text.lower() for ind in SELECTORS["sold_out_indicators"])

async def send_telegram(text: str) -> bool:
    """Отправка уведомления в Telegram с повторными попытками"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("❌ Не заданы TG_BOT_TOKEN или TG_CHAT_ID")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    
    # Для локального теста на macOS отключаем проверку SSL, в облаке работает стандартно
    ssl_val = False if (sys.platform == "darwin" and not HEADLESS) else True
    
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=15, ssl=ssl_val) as resp:
                    if resp.status == 200:
                        logger.info("✅ Уведомление отправлено")
                        return True
                    logger.warning(f"⚠️ Telegram API error {resp.status}")
        except Exception as e:
            logger.warning(f"⚠️ Попытка {attempt+1} не удалась: {e}")
            await asyncio.sleep(2 * (attempt + 1))
    return False

async def check_event_via_html(page, event: dict) -> bool:
    """Проверка наличия конкретного матча на странице"""
    try:
        body_text = await page.text_content("body")
        if not body_text: return False
        if any(phrase in body_text for phrase in ["Мероприятий нет", "Список пуст", "нет данных"]):
            return False

        for card_sel in SELECTORS["event_cards"]:
            cards = await page.query_selector_all(card_sel)
            for card in cards:
                card_text = await card.text_content() or ""
                if not card_text.strip(): continue
                
                if event["opponent"].lower() not in card_text.lower(): continue
                if parse_russian_date(card_text, event["year"]) != event["date"]: continue
                if is_sold_out(card_text): continue

                for btn_sel in SELECTORS["buy_buttons"]:
                    try:
                        btn = await card.query_selector(btn_sel)
                        if btn and await btn.is_visible() and not await btn.is_disabled():
                            logger.info(f"🎯 НАЙДЕН МАТЧ [{event['label']}]: {card_text.strip()[:100]}")
                            return True
                    except: continue

                if any(k in card_text.lower() for k in ["купить", "выбрать места", "в корзину"]) and not is_sold_out(card_text):
                    logger.info(f"🎯 НАЙДЕН МАТЧ [{event['label']}] (косвенный признак)")
                    return True
        return False
    except Exception as e:
        logger.error(f"⚠️ Ошибка проверки {event['label']}: {e}")
        return False

async def main():
    logger.info(f"🚀 Запуск монитора | Событий: {len(TARGET_EVENTS)} | Интервал: {CHECK_INTERVAL}с")
    for ev in TARGET_EVENTS:
        logger.info(f"   • {ev['label']}: {ev['opponent'].title()}, {ev['date']}.{ev['year']}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        if BLOCK_RESOURCES:
            await page.route("**/*.{png,jpg,jpeg,svg,webp,woff,woff2,ttf,eot,css}", lambda route: route.abort())

        # Отслеживаем, по каким событиям уже отправили уведомление
        notified = {ev["id"]: False for ev in TARGET_EVENTS}
        logger.info("✅ Мониторинг активен. Ожидание появления билетов...")

        while True:
            try:
                logger.info(f"🔄 Проверка {datetime.now().strftime('%H:%M:%S')}")
                await page.goto(TARGET_URL, wait_until="networkidle", timeout=TIMEOUT)
                await page.wait_for_timeout(1500)  # Доп. ожидание рендера

                for ev in TARGET_EVENTS:
                    if notified[ev["id"]]: continue  # Уже уведомили об этом матче
                    
                    if await check_event_via_html(page, ev):
                        msg = NOTIFY_TEMPLATE.format(
                            opponent=ev["opponent"].title(),
                            label=ev["label"],
                            url=TARGET_URL,
                            timestamp=datetime.now().strftime("%d.%m %H:%M:%S")
                        ).strip()
                        
                        if await send_telegram(msg):
                            notified[ev["id"]] = True
                            logger.warning(f"✅✅✅ УВЕДОМЛЕНИЕ ОТПРАВЛЕНО: {ev['label']} ✅✅✅")
                            # Если нужно останавливать скрипт после первого найденного матча, раскомментируй:
                            # break 

            except KeyboardInterrupt:
                logger.info("🛑 Остановлено пользователем")
                break
            except Exception as e:
                logger.error(f"💥 Ошибка цикла: {e}")
                await asyncio.sleep(30)  # Пауза при ошибке, чтобы не спамить

            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Завершение работы")