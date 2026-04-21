import discord
import os
import random
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from googleapiclient.discovery import build

load_dotenv()

# ================= ENV =================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN не задан")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан")

if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY не задан")

CHANNEL_ID = int(CHANNEL_ID)

# ================= YOUTUBE API =================

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def get_youtube_video(query: str):
    try:
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=10
        )

        response = request.execute()
        items = response.get("items", [])

        if not items:
            print("⚠️ EMPTY:", query)
            return None

        video = random.choice(items)
        video_id = video["id"]["videoId"]

        return f"https://www.youtube.com/watch?v={video_id}"

    except Exception as e:
        print("YT API ERROR:", e)
        return None


# ================= FLASK (Render keep alive) =================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# ================= DISCORD =================

intents = discord.Intents.default()
client = discord.Client(intents=intents)


# ================= SEND FUNCTION =================

async def send_ost():
    print("▶ send_ost")

    try:
        channel = await client.fetch_channel(CHANNEL_ID)

        queries = [
            "Star Wars The Old Republic OST full",
            "Knights of the Old Republic soundtrack",
            "SWTOR ambient music compilation",
        ]

        random.shuffle(queries)

        video_url = None

        for q in queries:
            print("SEARCH:", q)
            video_url = get_youtube_video(q)
            if video_url:
                break

        if not video_url:
            await channel.send("❌ OST не найден (API error)")
            return

        await channel.send(f"🎧 Daily OST:\n{video_url}")

    except Exception as e:
        print("SEND ERROR:", e)


# ================= SCHEDULER =================

scheduler = AsyncIOScheduler()

TEST_MODE = True   # 🔥 True = 1 минута / False = 10:00 МСК

def start_scheduler():
    if scheduler.running:
        return

    if TEST_MODE:
        print("🧪 TEST MODE: каждые 1 минуту")
        scheduler.add_job(lambda: asyncio.create_task(send_ost()), "interval", minutes=1)
    else:
        print("⏰ PROD MODE: 10:00 МСК (07:00 UTC)")
        scheduler.add_job(lambda: asyncio.create_task(send_ost()), "cron", hour=7, minute=0)

    scheduler.start()
    print("Scheduler started")


# ================= EVENTS =================

@client.event
async def on_ready():
    print("Bot ready:", client.user)

    start_scheduler()

    # тест при старте (можно убрать позже)
    await send_ost()


# ================= START =================

threading.Thread(target=run_web, daemon=True).start()

client.run(DISCORD_TOKEN)