import os
import asyncio
import logging
import json
import time
import yt_dlp
from ytmusicapi import YTMusic
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InlineQueryResultArticle, InlineQueryResultCachedAudio,
    InputMediaAudio, InputTextMessageContent,
)
from aiogram.client.session.aiohttp import AiohttpSession
from flask import Flask
import threading
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")

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

MAX_QUERY_LENGTH = 100
RATE_LIMIT_SECONDS = 3

user_busy: set = set()
user_last_request: dict = {}

favorites_file = "favorites.json"
file_id_cache_file = "file_id_cache.json"


def load_favorites():
    try:
        with open(favorites_file, "r") as f:
            return json.load(f)
    except:
        return {}


def save_favorites(data):
    with open(favorites_file, "w") as f:
        json.dump(data, f)


def load_file_id_cache():
    try:
        with open(file_id_cache_file, "r") as f:
            return json.load(f)
    except:
        return {}


def save_file_id_cache(data):
    with open(file_id_cache_file, "w") as f:
        json.dump(data, f)


def cache_file_id(video_id: str, file_id: str):
    data = load_file_id_cache()
    data[video_id] = file_id
    save_file_id_cache(data)


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


@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query or len(query) > MAX_QUERY_LENGTH:
        await inline_query.answer([], cache_time=1)
        return

    try:
        results_raw = ytmusic.search(query, filter="songs", limit=7)
        file_ids = load_file_id_cache()
        results = []

        for t in results_raw:
            artist = t["artists"][0]["name"] if t.get("artists") else "Unknown"
            title = t["title"]
            video_id = t.get("videoId")
            if not video_id:
                continue
            duration = t.get("duration", "")
            description = artist + (f" • {duration}" if duration else "")

            cached_file_id = file_ids.get(video_id)
            if cached_file_id:
                # Трек уже скачивался — отправляем сразу как аудио
                results.append(
                    InlineQueryResultCachedAudio(
                        id=video_id,
                        audio_file_id=cached_file_id,
                    )
                )
            else:
                # Новый трек — статья с кнопкой скачать (один раз)
                download_btn = InlineKeyboardButton(
                    text="⬇️ Скачать", callback_data=f"dl_{video_id}"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[download_btn]])
                results.append(
                    InlineQueryResultArticle(
                        id=video_id,
                        title=title,
                        description=description,
                        input_message_content=InputTextMessageContent(
                            message_text=f"🎵 <b>{title}</b> — {artist}",
                            parse_mode="HTML",
                        ),
                        reply_markup=keyboard,
                    )
                )

        await inline_query.answer(results, cache_time=30, is_personal=True)

    except Exception as e:
        logging.error(f"Inline search error: {e}")
        await inline_query.answer([], cache_time=1)


@dp.message(lambda m: not m.text)
async def non_text(message: types.Message):
    await message.answer("Отправьте текстовое сообщение с названием трека")


@dp.message()
async def search(message: types.Message):
    user_id = str(message.from_user.id)

    # Rate limit
    now = time.time()
    last = user_last_request.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last)) + 1
        await message.answer(f"Подождите {wait} сек. перед следующим запросом")
        return

    # Length limit
    if len(message.text) > MAX_QUERY_LENGTH:
        await message.answer(
            f"Запрос слишком длинный (максимум {MAX_QUERY_LENGTH} символов)"
        )
        return

    # Easter egg — bypass busy check
    if "мистер робот" in message.text.lower():
        user_last_request[user_id] = time.time()
        msg = await message.answer("услышал тебя родной")
        filename = None
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
            if filename and os.path.exists(filename):
                os.remove(filename)
            await msg.edit_text(f"Ошибка: {str(e)[:100]}")
        return

    # Busy check
    if user_id in user_busy:
        await message.answer("Дождитесь завершения текущего запроса")
        return

    user_busy.add(user_id)
    user_last_request[user_id] = time.time()
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
    finally:
        user_busy.discard(user_id)


@dp.callback_query(lambda c: c.data and c.data.startswith("dl_"))
async def download(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    video_id = callback.data[3:]

    if len(video_id) < 10:
        await callback.answer("Неверный ID трека", show_alert=True)
        return

    if user_id in user_busy:
        await callback.answer(
            "Дождитесь завершения текущего скачивания", show_alert=True
        )
        return

    user_busy.add(user_id)
    is_inline = callback.message is None
    filename = None

    # Уведомляем о начале скачивания
    if is_inline:
        await callback.answer("Скачивание — трек придёт в личку...")
        try:
            await bot.edit_message_text(
                text="⏳ Скачивание...",
                inline_message_id=callback.inline_message_id,
            )
        except Exception:
            pass
    else:
        await callback.message.edit_text("Скачивание...")

    try:
        info, filename = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_audio(video_id)
        )

        audio = FSInputFile(filename)
        performer = info.get("artist") or info.get("uploader") or "Unknown"
        title_str = info["title"][:100]

        if is_inline:
            # Тихо отправляем в личку, чтобы получить file_id
            dm_msg = await bot.send_audio(
                chat_id=callback.from_user.id,
                audio=audio,
                title=title_str,
                performer=performer,
                disable_notification=True,
            )
            file_id = dm_msg.audio.file_id if dm_msg.audio else None
            if file_id:
                cache_file_id(video_id, file_id)

            # Заменяем инлайн-сообщение на аудио прямо в том чате
            inline_ok = False
            if file_id:
                try:
                    await bot.edit_message_media(
                        media=InputMediaAudio(
                            media=file_id,
                            title=title_str,
                            performer=performer,
                        ),
                        inline_message_id=callback.inline_message_id,
                    )
                    inline_ok = True
                except Exception as e:
                    logging.warning(f"edit_message_media failed: {e}")

            if inline_ok:
                # Удаляем лишнее сообщение из лички
                try:
                    await bot.delete_message(
                        chat_id=callback.from_user.id,
                        message_id=dm_msg.message_id,
                    )
                except Exception:
                    pass
            else:
                # Fallback: аудио остаётся в личке
                try:
                    await bot.edit_message_text(
                        text=f"✅ <b>{title_str}</b> — {performer}\n(отправлено в личку)",
                        inline_message_id=callback.inline_message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
        else:
            fav_button = InlineKeyboardButton(
                text="➕ В избранное", callback_data=f"fav_{video_id}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[fav_button]])

            sent = await callback.message.answer_audio(
                audio=audio,
                title=title_str,
                performer=performer,
                reply_markup=keyboard,
            )
            if sent.audio:
                cache_file_id(video_id, sent.audio.file_id)

            await callback.message.delete()

        os.remove(filename)

    except Exception as e:
        if filename and os.path.exists(filename):
            os.remove(filename)
        if is_inline:
            try:
                await bot.edit_message_text(
                    text=f"❌ Ошибка: {str(e)[:100]}",
                    inline_message_id=callback.inline_message_id,
                )
            except Exception:
                pass
        else:
            await callback.message.edit_text(f"Ошибка: {str(e)[:100]}")
    finally:
        user_busy.discard(user_id)


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
    user_id = str(callback.from_user.id)
    track_id = callback.data[5:]

    if user_id in user_busy:
        await callback.answer(
            "Дождитесь завершения текущего скачивания", show_alert=True
        )
        return

    await callback.answer("Скачивание...")
    user_busy.add(user_id)

    data = load_favorites()
    track_info = data.get(user_id, {}).get(track_id, {})
    title = track_info.get("title")
    artist = track_info.get("artist")

    filename = None
    try:
        info, filename = await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_audio(track_id, title=title, artist=artist)
        )

        audio = FSInputFile(filename)
        performer = info.get("artist") or info.get("uploader") or artist or "Unknown"

        sent = await callback.message.answer_audio(
            audio=audio, title=info["title"][:100], performer=performer[:100]
        )

        # Кешируем file_id для инлайн-режима
        if sent.audio:
            cache_file_id(track_id, sent.audio.file_id)

        os.remove(filename)

    except Exception as e:
        if filename and os.path.exists(filename):
            os.remove(filename)
        await callback.message.answer(f"Ошибка: {str(e)[:100]}")
    finally:
        user_busy.discard(user_id)


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
