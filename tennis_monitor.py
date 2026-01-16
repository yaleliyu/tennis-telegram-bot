import asyncio
import hashlib
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from telegram import Bot
from bs4 import BeautifulSoup
import re

# ================== 配置区 ==================
BOT_TOKEN = "8234906468:AAF4uOVGEcgOTMID9mV4hy7GSR31p3OiDGA"
CHAT_ID = 7627468013

URL = "https://bookings.better.org.uk/location/islington-tennis-centre/tennis-court-indoor/"

CHECK_INTERVAL = 300  # 秒

# ===========================================

bot = Bot(token=BOT_TOKEN)
last_hash = None


def next_weekend_dates():
    """返回下一个周六和周日的日期列表"""
    today = datetime.today()
    week_day = today.weekday()

    saturday = None
    result = [(today + timedelta((6 - week_day) % 7)).strftime("%Y-%m-%d")]
    if week_day <= 5:
        saturday = (today + timedelta((5 - week_day) % 7)).strftime("%Y-%m-%d")
        result.append(saturday)

    return sorted(result)


async def fetch_slots(date_str: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        await context.add_cookies([
            {
                "name": "OptanonAlertBoxClosed",
                "value": "true",
                "domain": ".better.org.uk",
                "path": "/"
            },
            {
                "name": "OptanonConsent",
                "value": "isIABGlobal=false",
                "domain": ".better.org.uk",
                "path": "/"
            }
        ])

        page = await context.new_page()
        await page.goto(URL + date_str + "/by-time", timeout=60000)
        await page.wait_for_timeout(9000)
        content = await page.content()

        #
        # await page.goto(URL + date_str + "/by-time", timeout=60000)
        # await page.wait_for_timeout(5000)
        #
        # content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        slots_for_book = soup.select('span[class*="ContextualComponent"][class*="BookWrap"]')

        available = []

        for slot in slots_for_book:
            m = re.search(r'(\d+)\s+spaces?\s+available', slot.text)
            spaces_n = int(m.group(1))

            book_info = slot.select('a')
            if len(book_info) == 1:
                url = book_info[0]['href']

                pattern = r'/(\d{4}-\d{2}-\d{2})/by-time/slot/(\d{2}:\d{2})-(\d{2}:\d{2})/'
                m = re.search(pattern, url)
                date, start_time, end_time = m.groups()

                if spaces_n > 0 and start_time > "12:00":
                    available.append((spaces_n, date, start_time, end_time))
                    print(f"found available slot [{date_str}]: {start_time} - {end_time}")

        await browser.close()
        return sorted(set([a[-2] + " - " + a[-1] for a in available]))


async def notify(date, slots):
    msg = (
            "🎾 网球场可预定提醒\n\n"
            "📍 Islington Tennis Centre\n"
            f"📅 {date}\n"
            "⏰ 可用时间：\n"
            + "\n".join(f"• {s}" for s in slots)
            + f"\n\n🔗 立即预定：\n{URL}"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg, disable_web_page_preview=True)


async def main():
    global last_hash

    while True:
        try:
            for d in next_weekend_dates():
                slots = await fetch_slots(d)
                if len(slots) > 0:
                    h = hashlib.md5(",".join(slots).encode()).hexdigest()
                    if h != last_hash:
                        await notify(d, slots)
                        last_hash = h
                print(datetime.now(), f"checked for [{d}]")
                await asyncio.sleep(30)
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
