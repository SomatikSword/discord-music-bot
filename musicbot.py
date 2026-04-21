import discord
import os
import feedparser
import random
import threading
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

print("TOKEN:", bool(DISCORD_TOKEN))
print("CHANNEL_ID:", CHANNEL_ID)

# --- Flask ---

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    print("Запуск Flask на порту:", port)
    app.run(host="0.0.0.0", port=port)

# --- Discord ---

intents = discord.Intents.default()
client = discord.Client(intents=intents)

def get_youtube_video(query):
    print("Ищем видео по запросу:", query)

    url = f"https://www.youtube.com/feeds/videos.xml?search_query={query.replace(' ', '+')}"
    feed = feedparser.parse(url)

    if not feed.entries:
        print("Видео не найдено")
        return None

    print("Видео найдено")
    return feed.entries[0].link


async def send_ost():
    print("send_ost() вызвана")

    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        print("ОШИБКА: канал не найден")
        return

    print("Канал найден")

    queries = [
        "Star Wars The Old Republic OST",
        "Knights of the Old Republic soundtrack",
        "Star Wars movie soundtrack",
        "SWTOR ambient music"
    ]

    query = random.choice(queries)
    video_url = get_youtube_video(query)

    if video_url:
        print("Отправляем сообщение")
        await channel.send(f"🎧 TEST OST:\n{video_url}")
        print("Сообщение отправлено")
    else:
        print("Видео отсутствует")

# --- Scheduler ---

scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("interval", minutes=1)
async def test_task():
    print("Scheduler задача запущена")
    await send_ost()

@client.event
async def on_ready():
    print("Бот подключился:", client.user)

    print("Запускаем scheduler")
    scheduler.start()

    print("Отправляем тестовое сообщение сразу")
    await send_ost()

# запуск Flask
threading.Thread(target=run_web).start()

client.run(DISCORD_TOKEN)