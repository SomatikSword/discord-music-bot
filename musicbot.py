import discord
import os
import random
import asyncio
import threading
from flask import Flask
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from googleapiclient.discovery import build

load_dotenv()

# ================= ENV =================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not DISCORD_TOKEN or not CHANNEL_ID or not YOUTUBE_API_KEY:
    raise ValueError("Missing ENV variables")

CHANNEL_ID = int(CHANNEL_ID)

# ================= MODE =================

TEST_MODE = True  # True = 1 min, False = 10:00 MSK

# ================= STATE =================

sent_videos = set()
loop_started = False

# ================= FILTER =================

REQUIRED_WORDS = [
    "swtor",
    "old republic",
    "knights of the old republic",
    "kotor"
]

BANNED_WORDS = [
    "remix",
    "cover",
    "fan made",
    "trailer"
]

# ================= YOUTUBE =================

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def get_youtube_video(query: str):
    global sent_videos

    try:
        request = youtube.search().list(
            q=query,
            part="snippet",
            type="video",
            maxResults=30
        )

        response = request.execute()
        items = response.get("items", [])

        if not items:
            return None

        random.shuffle(items)

        for v in items:
            title = v["snippet"]["title"].lower()

            if not any(w in title for w in REQUIRED_WORDS):
                continue

            if any(w in title for w in BANNED_WORDS):
                continue

            video_id = v["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={video_id}"

            if url not in sent_videos:
                return url

        sent_videos.clear()
        return None

    except Exception as e:
        print("YT ERROR:", e)
        return None


# ================= FLASK =================

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


# ================= CORE LOGIC =================

async def send_ost():
    try:
        channel = await client.fetch_channel(CHANNEL_ID)

        queries = [
            "SWTOR soundtrack",
            "Star Wars Old Republic music",
            "KOTOR soundtrack",
            "Knights of the Old Republic OST"
        ]

        random.shuffle(queries)

        for q in queries:
            print("SEARCH:", q)

            video = get_youtube_video(q)

            if video:
                sent_videos.add(video)
                await channel.send(f"🎧 OST:\n{video}")
                return

        await channel.send("⚠️ No valid SWTOR/KOTOR OST found")

    except Exception as e:
        print("SEND ERROR:", e)


# ================= LOOP (ROBUST) =================

async def music_loop():
    await client.wait_until_ready()

    while True:
        print("🔥 LOOP TICK")

        try:
            await send_ost()

        except Exception as e:
            print("LOOP ERROR:", e)

        if TEST_MODE:
            await asyncio.sleep(60)
        else:
            await sleep_until_10am()


async def sleep_until_10am():
    msk = pytz.timezone("Europe/Moscow")

    now = datetime.now(msk)
    target = now.replace(hour=10, minute=0, second=0, microsecond=0)

    if now > target:
        target += timedelta(days=1)

    await asyncio.sleep((target - now).total_seconds())


# ================= WATCHDOG =================

async def watchdog():
    while True:
        print("🧠 watchdog alive")
        await asyncio.sleep(300)


# ================= EVENTS =================

@client.event
async def on_ready():
    global loop_started

    print("Bot ready:", client.user)

    if not loop_started:
        loop_started = True

        asyncio.create_task(music_loop())
        asyncio.create_task(watchdog())

        print("LOOPS STARTED")

    await send_ost()


# ================= START =================

threading.Thread(target=run_web, daemon=True).start()

client.run(DISCORD_TOKEN)