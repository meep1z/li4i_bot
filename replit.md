# Telegram Music Bot (@meep1z_music_bot)

A Telegram bot that searches YouTube Music, downloads tracks as MP3, manages favorites, and supports inline mode with file_id caching.

## Features
- Text search → list of results → download as MP3
- Inline mode (`@meep1z_music_bot query`) — cached tracks deliver audio instantly
- Inline favorites (`@meep1z_music_bot избранное`) — personal favorites list in any chat
- Favorites management: add, play, delete, clear all
- file_id cache — once downloaded, tracks are served instantly on repeat requests
- Easter egg: "мистер робот"
- Security: rate limit (3s), query length cap, per-user busy lock

## Tech Stack
- **Language**: Python 3.12
- **Telegram Framework**: aiogram >= 3.7
- **Music Search**: ytmusicapi
- **Downloader**: yt-dlp + ffmpeg
- **Health-check server**: Flask (port 8080)
- **Config**: python-dotenv

## Setup
- Requires `BOT_TOKEN` secret (from @BotFather)
- Enable inline mode via @BotFather → `/setinline`
- Run with: `python main.py`

## Project Structure
```
main.py              — точка входа: Flask health-check + регистрация роутеров + запуск бота
config.py            — константы, bot/dp/ytmusic инстансы, shared state
storage.py           — JSON-хранилища (favorites.json, file_id_cache.json)
downloader.py        — yt-dlp логика с фолбэками
handlers/
  commands.py        — /start
  favorites.py       — /favorites + callbacks: fav_, play_, del_, clear_all, none
  download.py        — callback dl_ (скачать трек, инлайн и обычный режим)
  search.py          — текстовый поиск + non-text хендлер
  inline.py          — инлайн-режим (поиск + избранное)
favorites.json       — база избранного (per user)
file_id_cache.json   — кеш file_id для инлайн-режима
temp/                — временные MP3 файлы
```

## Data Formats
**favorites.json**: `{ "user_id": { "video_id": { "title": "...", "artist": "..." } } }`
**file_id_cache.json**: `{ "video_id": "telegram_file_id" }`
