import os
import asyncio
import logging
import json
import yt_dlp
from ytmusicapi import YTMusic
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=TOKEN)
dp = Dispatcher()
ytmusic = YTMusic()

favorites_file = 'favorites.json'

def load_favorites():
    try:
        with open(favorites_file, 'r') as f:
            return json.load(f)
    except:
        return {}

def save_favorites(data):
    with open(favorites_file, 'w') as f:
        json.dump(data, f)

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': '%(title)s.%(ext)s',
    'quiet': True
}

@dp.message(Command('start')) 
async def start(message: types.Message):
    await message.answer("Отправь название трека для поиска\n/favorites - избранное")

@dp.message(Command('favorites'))
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
        buttons.append([
            InlineKeyboardButton(text=f"▶️ {i}", callback_data=f"play_{track_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"del_{track_id}")
        ])
    
    if buttons:
        buttons.append([InlineKeyboardButton(text="Очистить всё", callback_data="clear_all")])
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.message()
async def search(message: types.Message):
    msg = await message.answer("Поиск...")
    try:
        results = ytmusic.search(message.text, filter='songs', limit=5)
        if not results:
            await msg.edit_text("Ничего не найдено")
            return
        
        buttons = []
        for t in results:
            artist = t['artists'][0]['name'] if t.get('artists') else "Unknown"
            text = f"{t['title']} - {artist}"
            if len(text) > 40:
                text = text[:37] + "..."
            buttons.append([InlineKeyboardButton(
                text=text,
                callback_data=f"dl_{t['videoId']}"
            )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await msg.edit_text("Результаты:", reply_markup=keyboard)
    except Exception as e:
        await msg.edit_text(f"Ошибка: {str(e)[:100]}")

@dp.callback_query(lambda c: c.data and c.data.startswith('dl_'))
async def download(callback: types.CallbackQuery):
    video_id = callback.data[3:]
    await callback.message.edit_text("Скачивание...")
    
    try:
        url = f"https://music.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = f"{info['title']}.mp3"
            
            audio = FSInputFile(filename)
            performer = info.get('artist') or info.get('uploader') or 'Unknown'
            
            fav_button = InlineKeyboardButton(
                text="Добавить в избранное", 
                callback_data=f"fav_{video_id}_{info['title'][:30]}_{performer[:30]}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[fav_button]])
            
            await callback.message.answer_audio(
                audio=audio,
                title=info['title'][:100],
                performer=performer[:100],
                reply_markup=keyboard
            )
            
            os.remove(filename)
            await callback.message.delete()
            
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {str(e)[:100]}")

@dp.callback_query(lambda c: c.data and c.data.startswith('fav_'))
async def add_to_favorites(callback: types.CallbackQuery):
    parts = callback.data.split('_')
    track_id = parts[1]
    title = parts[2] if len(parts) > 2 else "Без названия"
    artist = parts[3] if len(parts) > 3 else "Неизвестный"
    
    user_id = str(callback.from_user.id)
    data = load_favorites()
    
    if user_id not in data:
        data[user_id] = {}
    
    if track_id not in data[user_id]:
        data[user_id][track_id] = {
            'title': title,
            'artist': artist
        }
        save_favorites(data)
        await callback.answer("Добавлено в избранное")
        
        new_button = InlineKeyboardButton(text="В избранном", callback_data="none")
        await callback.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[new_button]])
        )
    else:
        await callback.answer("Уже в избранном")

@dp.callback_query(lambda c: c.data and c.data.startswith('play_'))
async def play_from_favorites(callback: types.CallbackQuery):
    track_id = callback.data[5:]
    await callback.answer("Скачивание...")
    
    try:
        url = f"https://music.youtube.com/watch?v={track_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = f"{info['title']}.mp3"
            
            audio = FSInputFile(filename)
            performer = info.get('artist') or info.get('uploader') or 'Unknown'
            
            await callback.message.answer_audio(
                audio=audio,
                title=info['title'][:100],
                performer=performer[:100]
            )
            
            os.remove(filename)
            
    except Exception as e:
        await callback.message.answer(f"Ошибка: {str(e)[:100]}")
    
    await callback.answer()

@dp.callback_query(lambda c: c.data and c.data.startswith('del_'))
async def delete_from_favorites(callback: types.CallbackQuery):
    track_id = callback.data[4:]
    user_id = str(callback.from_user.id)
    data = load_favorites()
    
    if user_id in data and track_id in data[user_id]:
        del data[user_id][track_id]
        save_favorites(data)
        await callback.answer("Удалено из избранного")
        await show_favorites(callback.message)

@dp.callback_query(lambda c: c.data == 'clear_all')
async def clear_all_favorites(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_favorites()
    
    if user_id in data:
        data[user_id] = {}
        save_favorites(data)
    
    await callback.answer("Избранное очищено")
    await callback.message.edit_text("Избранное пусто")

@dp.callback_query(lambda c: c.data == 'none')
async def do_nothing(callback: types.CallbackQuery):
    await callback.answer()

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())