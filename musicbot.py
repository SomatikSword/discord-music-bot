import discord
import os
import feedparser
import random
import asyncio
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import threading

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# ---------- Flask (Render keep alive) ----------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ---------- Discord ----------

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ---------- safer youtube RSS search ----------

def get_youtube_video(query: str):
    try:
        url = f"https://www.youtube.com/feeds/videos.xml?search_query={query.replace(' ', '+')}"
        feed = feedparser.parse(url)

        entries = getattr(feed, "entries", None)

        if not entries:
            print("RSS пустой для:", query)
            return None

        video = random.choice(entries)
        return video.link

    except Exception as e:
        print("RSS error:", e)
        return None


# ---------- Discord sending ----------

async def send_ost():
    print("▶ send_ost")

    try:
        channel = await client.fetch_channel(CHANNEL_ID)

        queries = [
            "Star Wars The Old Republic OST",
            "Knights of the Old Republic soundtrack",
            "Star Wars movie soundtrack",
            "SWTOR ambient music"
        ]

        # пробуем несколько запросов, а не один
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


# ---------- Scheduler ----------

scheduler = AsyncIOScheduler()

async def job_wrapper():
    await send_ost()

@scheduler.scheduled_job("cron", hour=7, minute=0)  # UTC
def scheduled_job():
    asyncio.create_task(job_wrapper())


# ---------- Bot ----------

@client.event
async def on_ready():
    print("Bot ready:", client.user)

    if not scheduler.running:
        scheduler.start()
        print("Scheduler started")

    # первое сообщение при запуске
    await send_ost()


# ---------- Start Flask ----------

threading.Thread(target=run_web, daemon=True).start()

# ---------- Run bot ----------

client.run(DISCORD_TOKEN)