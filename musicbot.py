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

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


intents = discord.Intents.default()
client = discord.Client(intents=intents)


def get_youtube_video(query):
    url = f"https://www.youtube.com/feeds/videos.xml?search_query={query.replace(' ', '+')}"
    feed = feedparser.parse(url)

    if not feed.entries:
        return None

    return feed.entries[0].link


async def send_ost():
    channel = client.get_channel(CHANNEL_ID)

    if channel is None:
        print("Канал не найден")
        return

    queries = [
        "Star Wars The Old Republic OST",
        "Knights of the Old Republic soundtrack",
        "Star Wars movie soundtrack",
        "SWTOR ambient music"
    ]

    query = random.choice(queries)
    video_url = get_youtube_video(query)

    if video_url:
        await channel.send(f"🎧 Daily Star Wars OST:\n{video_url}")
    else:
        await channel.send("⚠️ OST не найден")


scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=10, minute=45)
async def daily_task():
    await send_ost()


@client.event
async def on_ready():
    print(f"Бот запущен как {client.user}")
    scheduler.start()


threading.Thread(target=run_web).start()

client.run(DISCORD_TOKEN)