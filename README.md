# Telegram Music Bot

A Telegram bot that lets users search for music on YouTube Music, download tracks as MP3, and manage a personal favorites list.

## Features
- Search YouTube Music for tracks
- Download tracks as MP3 (via yt-dlp + ffmpeg)
- Save/manage favorite tracks (stored in favorites.json)

## Tech Stack
- **Language**: Python 3.12
- **Telegram Framework**: aiogram >= 3.7
- **Music Search**: ytmusicapi
- **Downloader**: yt-dlp
- **Audio Processing**: ffmpeg (system) + ffmpeg-python
- **Config**: python-dotenv

## Setup
- Requires `BOT_TOKEN` secret (Telegram Bot API token from @BotFather)
- Run with: `python main.py`

## Project Structure
- `main.py` — Main bot logic (handlers, download, favorites)
- `favorites.json` — Local favorites database (per user)
- `requirements.txt` — Python dependencies
