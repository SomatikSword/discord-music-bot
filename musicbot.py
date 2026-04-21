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
TEST_MODE = False  # True = каждую минуту, False = каждый день в 10:00 МСК

# ================= STATE =================
sent_videos = set()      # хранит ссылки уже отправленных видео
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

def is_valid_ost_video(title: str, description: str, channel_title: str, strict: bool = True) -> bool:
    blob = normalize_text(f"{title} {description} {channel_title}")

    has_theme = any(k in blob for k in THEME_KEYWORDS)
    has_music = any(k in blob for k in MUSIC_KEYWORDS)
    has_banned = any(k in blob for k in BANNED_WORDS)

    if strict:
        return has_theme and has_music and not has_banned
    return has_theme and not has_banned

# ========== НОВАЯ ФУНКЦИЯ (раньше её не было) ==========
def fetch_search_items(query: str, max_results: int = 50):
    """
    Выполняет поиск на YouTube и возвращает список items.
    Если произошла ошибка или ничего не найдено, возвращает пустой список.
    """
    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            maxResults=max_results,
            order="relevance"
        )
        response = request.execute()
        items = response.get("items", [])
        return items
    except HttpError as e:
        print(f"YouTube API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in fetch_search_items: {e}")
        return []

def get_youtube_video(query: str):
    try:
        items = fetch_search_items(query=query, max_results=50)
        print(f"По запросу '{query}' найдено {len(items)} видео")
        if not items:
            return None

        # Выведем первые 5 названий
        for i, v in enumerate(items[:5]):
            title = v.get("snippet", {}).get("title", "")
            print(f"  {i+1}. {title}")

        random.shuffle(items)

        # Строгий проход
        for v in items:
            snippet = v.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel_title = snippet.get("channelTitle", "")

            if not is_valid_ost_video(title, description, channel_title, strict=True):
                continue

            video_id = v.get("id", {}).get("videoId")
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in sent_videos:
                    print(f"✅ Найдено (строгий): {title}")
                    return url

        # Мягкий проход
        for v in items:
            snippet = v.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel_title = snippet.get("channelTitle", "")

            if not is_valid_ost_video(title, description, channel_title, strict=False):
                continue

            video_id = v.get("id", {}).get("videoId")
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                if url not in sent_videos:
                    print(f"✅ Найдено (мягкий): {title}")
                    return url

        # Если всё уже было отправлено – очистить и взять первое мягкое
        sent_videos.clear()
        for v in items:
            snippet = v.get("snippet", {})
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            channel_title = snippet.get("channelTitle", "")

            if not is_valid_ost_video(title, description, channel_title, strict=False):
                continue

            video_id = v.get("id", {}).get("videoId")
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                print(f"✅ Найдено после очистки: {title}")
                return url

        print("❌ Не найдено подходящих видео")
        return None

    except Exception as e:
        print("Ошибка в get_youtube_video:", e)
        return None

# ================= FLASK (для поддержания бота на хостинге) =================
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

# ================= ОТПРАВКА OST =================
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

# ================= ЦИКЛ ОТПРАВКИ =================
async def music_loop():
    await client.wait_until_ready()

    while True:
        print("LOOP TICK")
        try:
            await send_ost()
        except Exception as e:
            print("LOOP ERROR:", e)

        if TEST_MODE:
            await asyncio.sleep(60)          # тест: каждую минуту
        else:
            await sleep_until_12am()         # прод: каждый день в 12:00 МСК

async def sleep_until_10am():
    msk = pytz.timezone("Europe/Moscow")
    now = datetime.now(msk)
    target = now.replace(hour=10, minute=0, second=0, microsecond=0)

    if now > target:
        target += timedelta(days=1)

    wait_seconds = (target - now).total_seconds()
    print(f"Сплю {wait_seconds} секунд до следующей отправки в 10:00 МСК")
    await asyncio.sleep(wait_seconds)

# ================= СТОРОЖЕВОЙ ЗАДАЧА (для отладки) =================
async def watchdog():
    while True:
        print("watchdog alive")
        await asyncio.sleep(300)   # раз в 5 минут пишем в лог

# ================= СОБЫТИЯ DISCORD =================
@client.event
async def on_ready():
    global loop_started
    print("Bot ready:", client.user)

    if not loop_started:
        loop_started = True
        asyncio.create_task(music_loop())
        asyncio.create_task(watchdog())
        print("LOOPS STARTED")

    # Отправить одно видео сразу после запуска (для проверки)
    await send_ost()

# ================= ЗАПУСК =================
threading.Thread(target=run_web, daemon=True).start()
client.run(DISCORD_TOKEN)