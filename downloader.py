import logging
import yt_dlp
from config import TEMP_DIR

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
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "extractor_retries": 3,
    "remote_components": ["ejs:github"],
}


def download_audio(video_id: str, title: str = None, artist: str = None):
    """Скачивает аудио с фолбэками: YT Music → YouTube → поиск по названию."""
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

    raise last_error
