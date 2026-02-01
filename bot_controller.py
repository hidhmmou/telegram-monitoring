#!/usr/bin/env python3
import os
import json
import asyncio
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment
load_dotenv("/opt/study-monitor/.env")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", 60))
STATE_FILE = "/opt/study-monitor/state.json"

# ---------- State Helpers ----------
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

# ---------- Command Handlers ----------
async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    reset_daily_limit_if_needed(state)
    # If daily time is already up, cannot pause
    if state.get("consumed_minutes", 0) >= DAILY_LIMIT:
        await update.message.reply_text("⛔ Can't pause — daily time is already up!")
        return

    # If already paused, inform the user instead of changing state
    if state.get("paused", False):
        await update.message.reply_text("⏸️ Bot Already paused!")
        return
    now = datetime.now().timestamp()
    state["paused"] = True
    state["pause_until"] = None
    # Mark pause start and last accounted time so we can track realtime paused minutes
    state["pause_started_at"] = now
    state["pause_last_accounted_at"] = now
    save_state(state)
    await update.message.reply_text("⏸️ Bot paused!")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    reset_daily_limit_if_needed(state)
    # If already running (not paused), inform the user instead of changing state
    if not state.get("paused", False):
        await update.message.reply_text("▶️ Bot Already running!")
        return
    # Account for realtime paused duration up to resume time
    now = datetime.now().timestamp()
    last_accounted = state.get("pause_last_accounted_at") or state.get("pause_started_at") or now
    elapsed_seconds = max(0, now - last_accounted)
    # Convert to minutes, round up to 1-minute granularity
    import math
    minutes = math.ceil(elapsed_seconds / 60)
    if minutes > 0:
        state["consumed_minutes"] = state.get("consumed_minutes", 0) + minutes

    # Clear pause markers and update paused state
    state["paused"] = False
    state["pause_until"] = None
    state.pop("pause_started_at", None)
    state.pop("pause_last_accounted_at", None)

    # If we've reached the daily limit during pause handling, mark as up
    if state["consumed_minutes"] >= DAILY_LIMIT:
        state["consumed_minutes"] = min(state["consumed_minutes"], DAILY_LIMIT)
        state["paused"] = True
        # keep pause markers cleared

    save_state(state)

    if state.get("consumed_minutes", 0) >= DAILY_LIMIT:
        await update.message.reply_text(f"⛔ Time's up — daily limit of {DAILY_LIMIT} minutes reached!")
    else:
        await update.message.reply_text("▶️ Bot resumed!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = load_state()
    reset_daily_limit_if_needed(state)
    used = state.get("consumed_minutes", 0)
    # Calculate realtime pending paused minutes (do not persist)
    pending = 0
    if state.get("paused", False):
        now = datetime.now().timestamp()
        last_accounted = state.get("pause_last_accounted_at") or state.get("pause_started_at") or now
        elapsed = max(0, now - last_accounted)
        import math
        pending = math.ceil(elapsed / 60)

    # If there's pending paused minutes, persist them so /status updates the stored state
    if pending > 0:
        now = datetime.now().timestamp()
        last_accounted = state.get("pause_last_accounted_at") or state.get("pause_started_at") or now
        state["consumed_minutes"] = state.get("consumed_minutes", 0) + pending
        # advance the last accounted marker by the number of whole minutes we just accounted
        state["pause_last_accounted_at"] = last_accounted + pending * 60

        # If we hit the daily limit, cap and stop tracking pause markers
        if state["consumed_minutes"] >= DAILY_LIMIT:
            state["consumed_minutes"] = min(state["consumed_minutes"], DAILY_LIMIT)
            state["paused"] = True
            state.pop("pause_started_at", None)
            state.pop("pause_last_accounted_at", None)

        save_state(state)
        # If limit reached, notify the requester immediately
        if state["consumed_minutes"] >= DAILY_LIMIT:
            await update.message.reply_text(f"⛔ Time's up — daily limit of {DAILY_LIMIT} minutes reached!")

    used_now = min(state.get("consumed_minutes", 0), DAILY_LIMIT)
    print("used:", state.get("consumed_minutes", 0), "pending:", pending, "used_now:", used_now)
    left = max(DAILY_LIMIT - used_now, 0)
    is_paused = state.get("paused", False)
    if used_now >= DAILY_LIMIT:
        status_emoji = "⛔ Time's up"
    else:
        status_emoji = "⏸️ Paused" if is_paused else "▶️ Active"
    # Use 1-minute granularity for the progress bar so each block = 1 minute
    # Cap the bar length to avoid extremely long messages for large DAILY_LIMIT
    bar_length = 10
    filled = int(min(used_now, DAILY_LIMIT) * (bar_length / DAILY_LIMIT)) if DAILY_LIMIT else 0
    bar = "🟩" * filled + "⬜" * (bar_length - filled)

    msg = (
        f"📊 Bot Status 📊\n"
        f"🔹 Status: {status_emoji}\n"
        f"🕒 Paused Time: {used_now} / {DAILY_LIMIT} min\n"
        f"⏳ Time Left: {left} min\n"
        f"\n"
        f"{bar}"
    )
    
    await update.message.reply_text(msg)

async def screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Take and send a screenshot immediately"""
    try:
        filename = "/tmp/instant_screenshot.png"
        
        # Take screenshot using scrot
        os.environ['DISPLAY'] = ':0'
        subprocess.run(["scrot", filename], check=True)
        
        # Send screenshot
        with open(filename, "rb") as photo:
            await update.message.reply_photo(photo=photo, caption="📸 HATID MAYSKAR")
        
        # Clean up
        if os.path.exists(filename):
            os.remove(filename)
            
    except subprocess.CalledProcessError as e:
        await update.message.reply_text(f"❌ Failed to take screenshot: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# ---------- Startup Message ----------
async def send_startup_message(bot: Bot):
    # Compose a startup status message similar to /status output
    try:
        state = load_state()
        reset_daily_limit_if_needed(state)
        used = state.get("consumed_minutes", 0)
        left = max(DAILY_LIMIT - used, 0)
        is_paused = state.get("paused", False)
        status_emoji = "⏸️ Paused" if is_paused else "▶️ Active"
        bar_length = 10
        filled = int(min(used, DAILY_LIMIT) * (bar_length / DAILY_LIMIT)) if DAILY_LIMIT else 0
        bar = "🟩" * filled + "⬜" * (bar_length - filled)

        msg = (
            f"PC Study Monitor Bot Started!\n"
        )

        await bot.send_message(chat_id=CHAT_ID, text=msg)
    except Exception as e:
        print("Failed to send startup message:", e)

# ---------- Main ----------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register commands
    app.add_handler(CommandHandler("pause", pause))
    app.add_handler(CommandHandler("resume", resume))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("screenshot", screenshot))

    bot = Bot(token=BOT_TOKEN)
    await app.initialize()
    await app.start()

    # Send startup notification
    await send_startup_message(bot)

    # Start polling (ignore old messages)
    await app.updater.start_polling(allowed_updates=["message"])
    await asyncio.Event().wait()  # keep alive

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "event loop is already running" in str(e):
            loop = asyncio.get_event_loop()
            loop.create_task(main())
        else:
            raise

