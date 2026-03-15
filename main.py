import os
import asyncio
import logging
import json
import yt_dlp
from ytmusicapi import YTMusic
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.client.session.aiohttp import AiohttpSession
from flask import Flask
import threading
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

# Простая сессия без сложных таймаутов
session = AiohttpSession()
bot = Bot(token=TOKEN, session=session)
dp = Dispatcher()
ytmusic = YTMusic()

app = Flask(__name__)


@app.route("/")
def index():
    return "Бот работает!"


TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

favorites_file = "favorites.json"


def load_favorites():
    try:
        with open(favorites_file, "r") as f:
            return json.load(f)
    except:
        return {}


def save_favorites(data):
    with open(favorites_file, "w") as f:
        json.dump(data, f)


ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }
    ],
    "outtmpl": f"{TEMP_DIR}/%(title)s.%(ext)s",
    "quiet": True,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "extractor_retries": 3,
    "remote_components": ["ejs:github"],
}


def download_audio(video_id, title=None, artist=None):
    """Скачивает аудио с фолбэками: YT Music -> YouTube -> поиск по названию."""
    urls = [
        f"https://music.youtube.com/watch?v={video_id}",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    if title and artist:
        urls.append(f"ytsearch1:{title} {artist}")
    elif title:
        urls.append(f"ytsearch1:{title}")

    last_error = None
    for url in urls:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if "entries" in info:
                    info = info["entries"][0]
                filename = f"{TEMP_DIR}/{info['title']}.mp3"
                return info, filename
        except Exception as e:
            last_error = e
            logging.warning(f"Не удалось скачать с {url}: {e}")
            continue

    raise last_error


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Отправь название трека для поиска\n/favorites - избранное")


@dp.message(Command("favorites"))
async def show_favorites(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_favorites()
    user_favs = data.get(user_id, {})

    if not user_favs:
        await message.answer("Избранное пусто")
        return

    text = "Избранное:\n\n"
    buttons = []

    for i, (track_id, info) in enumerate(list(user_favs.items())[:10], 1):
        text += f"{i}. {info['title']} - {info['artist']}\n"
        buttons.append(
            [
                InlineKeyboardButton(text=f"▶️ {i}", callback_data=f"play_{track_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"del_{track_id}"),
            ]
        )

    if buttons:
        buttons.append(
            [InlineKeyboardButton(text="Очистить всё", callback_data="clear_all")]
        )

    await message.answer(
        text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@dp.message(lambda m: not m.text)
async def non_text(message: types.Message):
    await message.answer("Отправьте текстовое сообщение с названием трека")


@dp.message()
async def search(message: types.Message):
    if "мистер робот" in message.text.lower():
        msg = await message.answer("услышал тебя родной")
        try:
            info, filename = await asyncio.get_event_loop().run_in_executor(
                None, lambda: download_audio("x7dMc0KAeHo")
            )
            audio = FSInputFile(filename)
            performer = info.get("artist") or info.get("uploader") or "Unknown"
            await message.answer_audio(
                audio=audio, title=info["title"][:100], performer=performer[:100]
            )
            os.remove(filename)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"Ошибка: {str(e)[:100]}")
        return
    msg = await message.answer("Поиск...")
    try:
        results = ytmusic.search(message.text, filter="songs", limit=5)
        if not results:
            await msg.edit_text("Ничего не найдено")
            return

        buttons = []
        for t in results:
            artist = t["artists"][0]["name"] if t.get("artists") else "Unknown"
            text = f"{t['title']} - {artist}"
            if len(text) > 40:
                text = text[:37] + "..."
            buttons.append(
                [InlineKeyboardButton(text=text, callback_data=f"dl_{t['videoId']}")]
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await msg.edit_text("Результаты:", reply_markup=keyboard)
    except Exception as e:
        await msg.edit_text(f"Ошибка: {str(e)[:100]}")


@dp.callback_query(lambda c: c.data and c.data.startswith("dl_"))
async def download(callback: types.CallbackQuery):
    video_id = callback.data[3:]

    if len(video_id) < 10:
        await callback.message.edit_text("Ошибка: неверный ID трека")
        return

    await callback.message.edit_text("Скачивание...")

    try:
        info, filename = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_audio(video_id)
        )

        audio = FSInputFile(filename)
        performer = info.get("artist") or info.get("uploader") or "Unknown"

        fav_button = InlineKeyboardButton(
            text="➕ В избранное", callback_data=f"fav_{video_id}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[fav_button]])

        await callback.message.answer_audio(
            audio=audio,
            title=info["title"][:100],
            performer=performer[:100],
            reply_markup=keyboard,
        )

        os.remove(filename)
        await callback.message.delete()

    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {str(e)[:100]}")


@dp.callback_query(lambda c: c.data and c.data.startswith("fav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    track_id = callback.data.split("_")[1]

    title = "Без названия"
    artist = "Неизвестный"

    if callback.message.audio:
        title = callback.message.audio.title or title
        artist = callback.message.audio.performer or artist

    user_id = str(callback.from_user.id)
    data = load_favorites()

    if user_id not in data:
        data[user_id] = {}

    if track_id not in data[user_id]:
        data[user_id][track_id] = {"title": title, "artist": artist}
        save_favorites(data)
        await callback.answer("Добавлено")

        new_button = InlineKeyboardButton(text="✅ В избранном", callback_data="none")
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[new_button]])
        )
    else:
        await callback.answer("Уже есть")


@dp.callback_query(lambda c: c.data and c.data.startswith("play_"))
async def play_from_favorites(callback: types.CallbackQuery):
    track_id = callback.data[5:]
    await callback.answer("Скачивание...")

    user_id = str(callback.from_user.id)
    data = load_favorites()
    track_info = data.get(user_id, {}).get(track_id, {})
    title = track_info.get("title")
    artist = track_info.get("artist")

    try:
        info, filename = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_audio(track_id, title=title, artist=artist)
        )

        audio = FSInputFile(filename)
        performer = info.get("artist") or info.get("uploader") or artist or "Unknown"

        await callback.message.answer_audio(
            audio=audio, title=info["title"][:100], performer=performer[:100]
        )

        os.remove(filename)

    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)[:100]}")

    await callback.answer()


@dp.callback_query(lambda c: c.data and c.data.startswith("del_"))
async def delete_from_favorites(callback: types.CallbackQuery):
    track_id = callback.data[4:]
    user_id = str(callback.from_user.id)
    data = load_favorites()

    if user_id in data and track_id in data[user_id]:
        del data[user_id][track_id]
        save_favorites(data)
        await callback.answer("Удалено")
        await show_favorites(callback.message)


@dp.callback_query(lambda c: c.data == "clear_all")
async def clear_all_favorites(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_favorites()

    if user_id in data:
        data[user_id] = {}
        save_favorites(data)

    await callback.answer("Очищено")
    await callback.message.edit_text("Избранное пусто")


@dp.callback_query(lambda c: c.data == "none")
async def do_nothing(callback: types.CallbackQuery):
    await callback.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    # Запускаем Flask в фоновом потоке
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080), daemon=True
    ).start()
    # Запускаем бота в основном потоке
    asyncio.run(main())
