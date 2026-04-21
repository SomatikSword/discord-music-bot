import discord
import os
import random
import asyncio
import threading
import yt_dlp
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN не задан в env")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан в env")

CHANNEL_ID = int(CHANNEL_ID)

# ================= Flask (Render keep-alive) =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ================= Discord =================

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ================= YouTube search (NO API) =================

def get_youtube_video(query):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "default_search": "ytsearch10"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(query, download=False)

        entries = result.get("entries", [])
        if not entries:
            print("Пустой результат:", query)
            return None

        video = random.choice(entries)
        return f"https://www.youtube.com/watch?v={video['id']}"

    except Exception as e:
        print("YT-DLP ERROR:", e)
        return None


# ================= Core send function =================

async def send_ost():
    print("▶ send_ost вызвана")

    try:
        channel = await client.fetch_channel(CHANNEL_ID)

        queries = [
            "Star Wars The Old Republic OST",
            "Knights of the Old Republic soundtrack",
            "Star Wars ambient music 1 hour",
            "SWTOR OST compilation",
            "Star Wars cinematic music"
        ]

        random.shuffle(queries)

        video_url = None

        for q in queries:
            video_url = get_youtube_video(q)
            if video_url:
                break

        if not video_url:
            await channel.send("❌ Не удалось найти OST видео")
            return

        await channel.send(f"🎧 Daily OST:\n{video_url}")

    except Exception as e:
        print("SEND ERROR:", e)


# ================= Scheduler =================

scheduler = AsyncIOScheduler()

TEST_MODE = True   # 🔥 ВКЛЮЧИ ДЛЯ ТЕСТА

async def job():
    await send_ost()


def start_scheduler():
    if TEST_MODE:
        print("🧪 TEST MODE: каждые 1 минуту")
        scheduler.add_job(lambda: asyncio.create_task(job()), "interval", minutes=1)
    else:
        print("⏰ PROD MODE: 10:00 МСК (07:00 UTC)")
        scheduler.add_job(
            lambda: asyncio.create_task(job()),
            "cron",
            hour=7,
            minute=0
        )

    scheduler.start()


# ================= Discord events =================

@client.event
async def on_ready():
    print("Bot ready:", client.user)

    start_scheduler()

    # ⚠️ убираем автоспам при старте (важно)
    print("Scheduler started")


# ================= Start Flask =================

threading.Thread(target=run_web, daemon=True).start()

# ================= Run bot =================

client.run(DISCORD_TOKEN)