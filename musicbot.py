import discord
import os
import random
import asyncio
import threading
import re
from flask import Flask
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

# ================= FILTER CONFIG =================

THEME_KEYWORDS = [
    "swtor",
    "star wars the old republic",
    "old republic",
    "kotor",
    "knights of the old republic",
]

MUSIC_KEYWORDS = [
    "ost",
    "soundtrack",
    "original soundtrack",
    "official soundtrack",
    "music",
    "theme",
]

BANNED_WORDS = [
    "remix",
    "cover",
    "fan made",
    "fanmade",
    "fan edit",
    "extended remix",
    "nightcore",
    "slowed",
    "reverb",
    "8d",
    "bass boosted",
    "trailer",
    "teaser",
    "reaction",
    "edit",
    "mashup",
    "karaoke",
]

# ================= YOUTUBE =================

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_valid_ost_video(title: str, description: str, channel_title: str) -> bool:
    blob = normalize_text(f"{title} {description} {channel_title}")

    has_theme = any(k in blob for k in THEME_KEYWORDS)
    has_music = any(k in blob for k in MUSIC_KEYWORDS)
    has_banned = any(k in blob for k in BANNED_WORDS)

    return has_theme and has_music and not has_banned


def fetch_search_items(query: str, max_results: int = 50):
    request = youtube.search().list(
        q=query,
        part="snippet",
        type="video",
        maxResults=max_results,
        relevanceLanguage="en",
        safeSearch="none",
    )
    response = request.execute()
    return response.get("items", [])


def pick_video_from_items(items):
    global sent_videos

    random.shuffle(items)

    # Первый проход: ищем неотправленные
    for v in items:
        snippet = v.get("snippet", {})
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        channel_title = snippet.get("channelTitle", "")

        if not is_valid_ost_video(title, description, channel_title):
            continue

        video_id = v.get("id", {}).get("videoId")
        if not video_id:
            continue

        url = f"https://www.youtube.com/watch?v={video_id}"

        if url not in sent_videos:
            return url

    # Если все подходящие уже отправлялись — сбрасываем и выбираем заново
    sent_videos.clear()

    for v in items:
        snippet = v.get("snippet", {})
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        channel_title = snippet.get("channelTitle", "")

        if not is_valid_ost_video(title, description, channel_title):
            continue

        video_id = v.get("id", {}).get("videoId")
        if not video_id:
            continue

        return f"https://www.youtube.com/watch?v={video_id}"

    return None


def get_youtube_video(query: str):
    try:
        items = fetch_search_items(query=query, max_results=50)
        if not items:
            return None
        return pick_video_from_items(items)

    except HttpError as e:
        print("YT HTTP ERROR:", e)
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
            "SWTOR original soundtrack",
            "Star Wars The Old Republic OST",
            "KOTOR original soundtrack",
            "Knights of the Old Republic OST",
            "Star Wars Old Republic official soundtrack",
            "KOTOR music theme",
        ]

        random.shuffle(queries)

        for q in queries:
            print("SEARCH:", q)
            video = get_youtube_video(q)

            if video:
                sent_videos.add(video)
                await channel.send(f"OST:\n{video}")
                return

        await channel.send("No valid SWTOR/KOTOR OST found")

    except Exception as e:
        print("SEND ERROR:", e)


# ================= LOOP (ROBUST) =================

async def music_loop():
    await client.wait_until_ready()

    while True:
        print("LOOP TICK")

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
        print("watchdog alive")
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

    # Одно стартовое сообщение для проверки после запуска
    await send_ost()


# ================= START =================

threading.Thread(target=run_web, daemon=True).start()
client.run(DISCORD_TOKEN)