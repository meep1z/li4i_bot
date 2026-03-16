import asyncio
import os
import time

from aiogram import Router, types
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
)

from config import ytmusic, user_busy, user_last_request, MAX_QUERY_LENGTH, RATE_LIMIT_SECONDS
from downloader import download_audio

router = Router()

EASTER_EGG_VIDEO_ID = "x7dMc0KAeHo"


@router.message(lambda m: not m.text)
async def non_text(message: types.Message):
    await message.answer("Отправьте текстовое сообщение с названием трека")


@router.message()
async def search(message: types.Message):
    user_id = str(message.from_user.id)

    now = time.time()
    last = user_last_request.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last)) + 1
        await message.answer(f"Подождите {wait} сек. перед следующим запросом")
        return

    if len(message.text) > MAX_QUERY_LENGTH:
        await message.answer(f"Запрос слишком длинный (максимум {MAX_QUERY_LENGTH} символов)")
        return

    # Easter egg
    if "мистер робот" in message.text.lower():
        user_last_request[user_id] = time.time()
        msg = await message.answer("услышал тебя родной")
        filename = None
        try:
            info, filename = await asyncio.get_event_loop().run_in_executor(
                None, lambda: download_audio(EASTER_EGG_VIDEO_ID)
            )
            audio = FSInputFile(filename)
            performer = info.get("artist") or info.get("uploader") or "Unknown"
            await message.answer_audio(
                audio=audio,
                title=info["title"][:100],
                performer=performer[:100],
            )
            os.remove(filename)
            await msg.delete()
        except Exception as e:
            if filename and os.path.exists(filename):
                os.remove(filename)
            await msg.edit_text(f"Ошибка: {str(e)[:100]}")
        return

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
            label = f"{t['title']} - {artist}"
            if len(label) > 40:
                label = label[:37] + "..."
            buttons.append([
                InlineKeyboardButton(text=label, callback_data=f"dl_{t['videoId']}")
            ])

        await msg.edit_text("Результаты:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    except Exception as e:
        await msg.edit_text(f"Ошибка: {str(e)[:100]}")
    finally:
        user_busy.discard(user_id)
