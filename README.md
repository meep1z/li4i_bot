# 🎵 Telegram Music Bot (@meep1z_music_bot)

A Telegram bot for searching and downloading music from YouTube Music. Supports inline mode with instant audio delivery via file_id caching, personal favorites, and security features.

## Features

- **Text search** — send a track name, get a list of results, tap to download as MP3
- **Inline mode** — type `@meep1z_music_bot <query>` in any chat; cached tracks appear as instant audio
- **Inline favorites** — type `@meep1z_music_bot избранное` to browse and share your favorites from any chat
- **file_id cache** — once a track is downloaded, it's served instantly on all future requests without re-downloading
- **Favorites** — save tracks, play from list, delete individually or clear all
- **Download fallback chain** — tries YouTube Music → YouTube → title/artist search
- **Rate limiting** — 3-second cooldown per user, 100-character query cap
- **Easter egg** — try typing "мистер робот"

## Tech Stack

| Component | Library |
|---|---|
| Telegram framework | aiogram >= 3.7 |
| Music search | ytmusicapi |
| Downloader | yt-dlp |
| Audio conversion | ffmpeg |
| Health-check server | Flask |
| Config | python-dotenv |

## Setup

1. Create a bot via [@BotFather](https://t.me/BotFather), get the token
2. Enable inline mode: BotFather → `/setinline`
3. Set the `BOT_TOKEN` secret in your environment
4. Run: `python main.py`

## Project Structure

```
main.py              — entry point: Flask health-check + router registration + bot polling
config.py            — env vars, bot/dp/ytmusic instances, shared state
storage.py           — JSON persistence (favorites, file_id cache)
downloader.py        — yt-dlp download logic with fallback chain
handlers/
  commands.py        — /start
  favorites.py       — /favorites + callbacks: add, play, delete, clear
  download.py        — dl_ callback: download in normal and inline context
  search.py          — text search handler + non-text guard
  inline.py          — inline query: search + favorites mode
favorites.json       — per-user favorites database
file_id_cache.json   — video_id → Telegram file_id cache
temp/                — temporary MP3 files (auto-cleaned)
```

## Inline Mode Details

| Query | Result |
|---|---|
| `@meep1z_music_bot <song name>` | Search results; cached tracks = instant audio, new tracks = article + download button |
| `@meep1z_music_bot избранное` | Your personal favorites list |

When a new track is downloaded for the first time via the inline button:
1. Bot downloads the MP3 and sends it silently to your DM to obtain a Telegram `file_id`
2. `file_id` is saved to the cache
3. The inline message in the original chat is replaced with the audio file via `editMessageMedia`
4. The DM copy is deleted

On all future searches, cached tracks skip the download entirely.

## Data Formats

**favorites.json**
```json
{
  "123456789": {
    "VIDEO_ID": { "title": "Track Name", "artist": "Artist" }
  }
}
```

**file_id_cache.json**
```json
{
  "VIDEO_ID": "BQACAgIAAxkB..."
}
```
