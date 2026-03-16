import asyncio
import os
import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from config import bot, user_busy
from storage import load_favorites, save_favorites, cache_file_id
from downloader import download_audio

router = Router()


async def send_favorites_list(target: types.Message, user_id: str, edit: bool = False):
    """Отправляет или редактирует список избранного.
    edit=True — редактировать существующее сообщение бота (из callback).
    edit=False — отправить новое сообщение (из команды).
    """
    data = load_favorites()
    user_favs = data.get(user_id, {})

    if not user_favs:
        text = "Избранное пусто"
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    text = "Избранное:\n\n"
    buttons = []

    for i, (track_id, info) in enumerate(list(user_favs.items())[:10], 1):
        text += f"{i}. {info['title']} - {info['artist']}\n"
        buttons.append([
            InlineKeyboardButton(text=f"▶️ {i}", callback_data=f"play_{track_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"del_{track_id}"),
        ])

    buttons.append([
        InlineKeyboardButton(text="Очистить всё", callback_data="clear_all")
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(Command("favorites"))
async def show_favorites(message: types.Message):
    user_id = str(message.from_user.id)
    await send_favorites_list(message, user_id)


@router.callback_query(lambda c: c.data and c.data.startswith("fav_"))
async def add_to_favorites(callback: types.CallbackQuery):
    track_id = callback.data.split("_")[1]

    title = "Без названия"
    artist = "Неизвестный"

    if callback.message and callback.message.audio:
        title = callback.message.audio.title or title
        artist = callback.message.audio.performer or artist

    user_id = str(callback.from_user.id)
    data = load_favorites()
    data.setdefault(user_id, {})

    if track_id not in data[user_id]:
        data[user_id][track_id] = {"title": title, "artist": artist}
        save_favorites(data)
        await callback.answer("Добавлено")
        new_btn = InlineKeyboardButton(text="✅ В избранном", callback_data="none")
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[new_btn]])
        )
    else:
        await callback.answer("Уже есть")


@router.callback_query(lambda c: c.data and c.data.startswith("play_"))
async def play_from_favorites(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    track_id = callback.data[5:]

    if user_id in user_busy:
        await callback.answer("Дождитесь завершения текущего скачивания", show_alert=True)
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
            audio=audio,
            title=info["title"][:100],
            performer=performer[:100],
        )

        if sent.audio:
            cache_file_id(track_id, sent.audio.file_id)

        os.remove(filename)

    except Exception as e:
        if filename and os.path.exists(filename):
            os.remove(filename)
        await callback.message.answer(f"Ошибка: {str(e)[:100]}")
    finally:
        user_busy.discard(user_id)


@router.callback_query(lambda c: c.data and c.data.startswith("del_"))
async def delete_from_favorites(callback: types.CallbackQuery):
    track_id = callback.data[4:]
    user_id = str(callback.from_user.id)
    data = load_favorites()

    if user_id in data and track_id in data[user_id]:
        del data[user_id][track_id]
        save_favorites(data)
        await callback.answer("Удалено")

    await send_favorites_list(callback.message, user_id, edit=True)


@router.callback_query(lambda c: c.data == "clear_all")
async def clear_all_favorites(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_favorites()
    data[user_id] = {}
    save_favorites(data)
    await callback.answer("Очищено")
    await callback.message.edit_text("Избранное пусто")


@router.callback_query(lambda c: c.data == "none")
async def do_nothing(callback: types.CallbackQuery):
    await callback.answer()
