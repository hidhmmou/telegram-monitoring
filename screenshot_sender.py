#!/usr/bin/env python3
import asyncio
import subprocess
import os
import json
from datetime import datetime
from telegram import Bot
from dotenv import load_dotenv

# Load environment variables
load_dotenv("/opt/study-monitor/.env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 60))
INTERVAL = 5
STATE_FILE = "/opt/study-monitor/state.json"
os.environ['DISPLAY'] = ':0'

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"paused": False, "consumed_minutes": 0, "pause_until": None, "last_reset": datetime.now().strftime("%Y-%m-%d")}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def reset_daily_limit_if_needed(state):
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_reset") != today:
        state["consumed_minutes"] = 0
        state["paused"] = False
        state["pause_until"] = None
        state["last_reset"] = today
        save_state(state)

async def send_screenshot():
    bot = Bot(token=BOT_TOKEN)
    filename = "/tmp/screenshot.png"

    # Take screenshot
    subprocess.run(["scrot", filename], check=True)

    # Send screenshot
    try:
        with open(filename, "rb") as photo:
            await bot.send_photo(chat_id=CHAT_ID, photo=photo)
    except Exception as e:
        print("Failed to send screenshot:", e)
    finally:
        if os.path.exists(filename):
            os.remove(filename)

async def send_screenshot_stateful():
    state = load_state()
    reset_daily_limit_if_needed(state)

    # Auto-resume if pause_until has passed
    if state.get("pause_until"):
        if datetime.now().timestamp() > state["pause_until"]:
            state["paused"] = False
            state["pause_until"] = None
            save_state(state)

    if state.get("paused"):
        # Account for realtime paused duration since last accounting
        now = datetime.now().timestamp()
        last_accounted = state.get("pause_last_accounted_at") or state.get("pause_started_at") or now
        elapsed = min(INTERVAL, now - last_accounted)
        import math
        minutes = math.ceil(elapsed / 60)

        prev = state.get("consumed_minutes", 0)
        if minutes > 0:
            state["consumed_minutes"] = prev + minutes
            # advance the last accounted marker by the number of minutes we've accounted
            last_accounted = state.get("pause_last_accounted_at") or state.get("pause_started_at") or now
            state["pause_last_accounted_at"] = last_accounted + minutes * 60

        hit_limit = False
        if state["consumed_minutes"] >= DAILY_LIMIT:
            state["consumed_minutes"] = min(state["consumed_minutes"], DAILY_LIMIT)
            state["paused"] = True
            state["pause_until"] = None
            if prev < DAILY_LIMIT:
                hit_limit = True

        save_state(state)

        # Send notifications if we updated consumed time or hit the limit
        try:
            bot = Bot(token=BOT_TOKEN)
            if minutes > 0 and hit_limit:
                await bot.send_message(chat_id=CHAT_ID, text=f"⛔ Time's up — daily limit of {DAILY_LIMIT} minutes reached!")

            if minutes > 0:
                used = state.get("consumed_minutes", 0)
                left = max(DAILY_LIMIT - used, 0)
                bar_length = 10
                filled = int(min(used, DAILY_LIMIT) * (bar_length / DAILY_LIMIT)) if DAILY_LIMIT else 0
                bar = "🟩" * filled + "⬜" * (bar_length - filled)
                status_msg = (
                    f"📊 Bot Status 📊\n"
                    f"🔹 Status: ⏸️ Paused\n"
                    f"🕒 Paused Time: {used} / {DAILY_LIMIT} min\n"
                    f"⏳ Time Left: {left} min\n"
                    f"📈 Progress:\n"
                    f"{bar}"
                )
                await bot.send_message(chat_id=CHAT_ID, text=status_msg)
        except Exception as e:
            print("Failed to send paused status message:", e)

        return  # skip sending

    bot = Bot(token=BOT_TOKEN)
    filename = "/tmp/screenshot.png"

    # Take screenshot
    subprocess.run(["scrot", filename], check=True)

    # Send screenshot
    try:
        with open(filename, "rb") as photo:
            await bot.send_photo(chat_id=CHAT_ID, photo=photo)
    except Exception as e:
        print("Failed to send screenshot:", e)
    finally:
        if os.path.exists(filename):
            os.remove(filename)

    # No change to consumed_minutes while active (we track paused minutes only)
    save_state(state)

if __name__ == "__main__":
    asyncio.run(send_screenshot())

