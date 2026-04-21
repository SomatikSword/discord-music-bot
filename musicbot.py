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

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN не задан")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан")

if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY не задан")

CHANNEL_ID = int(CHANNEL_ID)

# ================= MODE =================

TEST_MODE = True
# True  -> каждая минута
# False -> 10:00 МСК

# ================= MEMORY =================

sent_videos = set()

# ================= FILTER =================

REQUIRED_WORDS = [
    "old republic",
    "swtor",
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
            maxResults=40
        )

        response = request.execute()
        items = response.get("items", [])

        if not items:
            print("EMPTY:", query)
            return None

        random.shuffle(items)

        for video in items:

            title = video["snippet"]["title"].lower()

            # проверяем обязательные слова
            if not any(word in title for word in REQUIRED_WORDS):
                continue

            # проверяем запрещённые слова
            if any(word in title for word in BANNED_WORDS):
                continue

            video_id = video["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={video_id}"

            if url not in sent_videos:
                return url

        print("Все подходящие видео уже отправлены")

        # fallback — разрешаем повтор
        video = random.choice(items)

        video_id = video["id"]["videoId"]

        return f"https://www.youtube.com/watch?v={video_id}"

    except Exception as e:
        print("YT API ERROR:", e)
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


# ================= SEND =================

async def send_ost():
    print("send_ost")

    try:
        channel = await client.fetch_channel(CHANNEL_ID)

        queries = [
            "SWTOR soundtrack",
            "Star Wars The Old Republic music",
            "KOTOR soundtrack",
            "Knights of the Old Republic music",
            "SWTOR ambient music"
        ]

        random.shuffle(queries)

        video_url = None

        for q in queries:

            print("SEARCH:", q)

            video_url = get_youtube_video(q)

            if video_url:
                break

        if not video_url:
            await channel.send(
                "⚠️ Не удалось найти новое OST видео (SWTOR/KOTOR)"
            )
            return

        sent_videos.add(video_url)

        print("SEND:", video_url)

        await channel.send(f"🎧 OST:\n{video_url}")

    except Exception as e:
        print("SEND ERROR:", e)


# ================= TIME =================

async def sleep_until_10am_msk():
    msk = pytz.timezone("Europe/Moscow")

    now = datetime.now(msk)

    target = now.replace(
        hour=10,
        minute=0,
        second=0,
        microsecond=0
    )

    if now > target:
        target += timedelta(days=1)

    seconds = (target - now).total_seconds()

    print("Sleep seconds:", int(seconds))

    await asyncio.sleep(seconds)


# ================= LOOP =================

async def music_loop():
    await client.wait_until_ready()

    while not client.is_closed():

        try:

            print("LOOP")

            await send_ost()

        except Exception as e:

            print("LOOP ERROR:", e)

        if TEST_MODE:

            print("TEST MODE sleep 60")

            await asyncio.sleep(60)

        else:

            print("PROD MODE wait until 10:00")

            await sleep_until_10am_msk()


# ================= EVENTS =================

@client.event
async def on_ready():
    print("Bot ready:", client.user)

    client.loop.create_task(music_loop())

    await send_ost()


# ================= START =================

threading.Thread(target=run_web, daemon=True).start()

client.run(DISCORD_TOKEN)