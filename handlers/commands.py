from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Отправь название трека для поиска\n"
        "/favorites - избранное\n\n"
        "В инлайн-режиме: @meep1z_music_bot избранное — показать избранное"
    )
