import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from ytmusicapi import YTMusic
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

session = AiohttpSession()
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()
ytmusic = YTMusic()

TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

MAX_QUERY_LENGTH = 100
RATE_LIMIT_SECONDS = 3

user_busy: set = set()
user_last_request: dict = {}
