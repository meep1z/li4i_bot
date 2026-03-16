import asyncio
import logging
import os

from aiogram import Router, types
from aiogram.types import (
    FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio
)

from config import bot, user_busy
from storage import cache_file_id
from downloader import download_audio

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("dl_"))
async def download(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    video_id = callback.data[3:]

    if len(video_id) < 10:
        await callback.answer("Неверный ID трека", show_alert=True)
        return

    if user_id in user_busy:
        await callback.answer("Дождитесь завершения текущего скачивания", show_alert=True)
        return

    user_busy.add(user_id)
    is_inline = callback.message is None
    filename = None

    if is_inline:
        await callback.answer("Скачивание...")
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
            # Отправляем в личку, чтобы получить file_id
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

            # Заменяем инлайн-сообщение аудио прямо в том же чате
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
                try:
                    await bot.delete_message(
                        chat_id=callback.from_user.id,
                        message_id=dm_msg.message_id,
                    )
                except Exception:
                    pass
            else:
                try:
                    await bot.edit_message_text(
                        text=f"✅ <b>{title_str}</b> — {performer}\n(отправлено в личку)",
                        inline_message_id=callback.inline_message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        else:
            fav_btn = InlineKeyboardButton(
                text="➕ В избранное", callback_data=f"fav_{video_id}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[fav_btn]])

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
