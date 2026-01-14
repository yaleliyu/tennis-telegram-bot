import asyncio
import hashlib
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from telegram import Bot
from bs4 import BeautifulSoup


# ================== 配置区 ==================
BOT_TOKEN = "8234906468:AAF4uOVGEcgOTMID9mV4hy7GSR31p3OiDGA"
CHAT_ID = 7627468013

URL = "https://bookings.better.org.uk/location/islington-tennis-centre/tennis-court-indoor/"


CHECK_INTERVAL = 600  # 秒（10分钟）

TIME_START = "13:00"
TIME_END = "17:00"
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

    return result


def time_in_range(t):
    return TIME_START <= t <= TIME_END

async def fetch_slots(date_str:str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(URL+date_str+"/by-time", timeout=60000)
        await page.wait_for_timeout(5000)

        slots = []

        cards = await page.query_selector_all("button")
        content =  await page.content()
        soup = BeautifulSoup(content, "html.parser")

        slots = soup.select('div[class*="ClassTime"]')
        spaces = soup.select('span[class*="BookWrap"]')

        if len(slots) == len(spaces) and len(slots) > 0:
            for i in range(len(slots)):
                print(slots[i] + ": " + spaces[i])


        for c in cards:
            text = (await c.inner_text()).strip()
            print(text)
            if "Book" in text or "Available" in text:
                # 简单时间提取（Better 页面一般包含时间）
                for part in text.split():
                    if ":" in part:
                        t = part[:5]
                        if time_in_range(t):
                            slots.append(t)

        await browser.close()
        return sorted(set(slots))


async def notify(slots):
    msg = (
        "🎾 网球场可预定提醒\n\n"
        "📍 Islington Tennis Centre\n"
        "📅 2026-01-17\n"
        "⏰ 可用时间：\n"
        + "\n".join(f"• {s}" for s in slots)
        + f"\n\n🔗 立即预定：\n{URL}"
    )
    await bot.send_message(chat_id=CHAT_ID, text=msg, disable_web_page_preview=True)


async def main():
    global last_hash
    await notify(['test_head', '1'])

    while True:
        try:
            for d in next_weekend_dates():
                slots = await fetch_slots(d)
                if slots:
                    h = hashlib.md5(",".join(slots).encode()).hexdigest()
                    if h != last_hash:
                        await notify(slots)
                        last_hash = h
                print(datetime.now(), "checked")
        except Exception as e:
            print("Error:", e)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())


