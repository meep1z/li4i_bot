import logging

from aiogram import Router
from aiogram.types import (
    InlineQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InlineQueryResultCachedAudio,
    InputTextMessageContent,
)

from config import ytmusic, MAX_QUERY_LENGTH
from storage import load_favorites, load_file_id_cache

router = Router()


def _build_article(video_id: str, title: str, description: str, id_prefix: str = "") -> InlineQueryResultArticle:
    download_btn = InlineKeyboardButton(
        text="⬇️ Скачать", callback_data=f"dl_{video_id}"
    )
    return InlineQueryResultArticle(
        id=f"{id_prefix}{video_id}",
        title=title,
        description=description,
        input_message_content=InputTextMessageContent(
            message_text=f"🎵 <b>{title}</b> — {description}",
            parse_mode="HTML",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[download_btn]]),
    )


@router.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query.strip()

    if not query or len(query) > MAX_QUERY_LENGTH:
        await inline_query.answer([], cache_time=1)
        return

    # Спецзапрос: показать избранное пользователя
    if query.lower() == "избранное":
        user_id = str(inline_query.from_user.id)
        user_favs = load_favorites().get(user_id, {})
        file_ids = load_file_id_cache()
        results = []

        if not user_favs:
            results.append(
                InlineQueryResultArticle(
                    id="no_favs",
                    title="Избранное пусто",
                    description="Добавьте треки через кнопку ➕ В избранное",
                    input_message_content=InputTextMessageContent(
                        message_text="У вас пока нет избранных треков."
                    ),
                )
            )
        else:
            for video_id, info in list(user_favs.items())[:50]:
                title = info.get("title", "Без названия")
                artist = info.get("artist", "Неизвестный")
                cached_file_id = file_ids.get(video_id)
                if cached_file_id:
                    results.append(InlineQueryResultCachedAudio(
                        id=f"fav_{video_id}",
                        audio_file_id=cached_file_id,
                    ))
                else:
                    results.append(_build_article(video_id, title, artist, id_prefix="fav_"))

        await inline_query.answer(results, cache_time=0, is_personal=True)
        return

    # Обычный поиск
    try:
        results_raw = ytmusic.search(query, filter="songs", limit=7)
        file_ids = load_file_id_cache()
        results = []

        for t in results_raw:
            video_id = t.get("videoId")
            if not video_id:
                continue
            title = t["title"]
            artist = t["artists"][0]["name"] if t.get("artists") else "Unknown"
            duration = t.get("duration", "")
            description = artist + (f" • {duration}" if duration else "")

            cached_file_id = file_ids.get(video_id)
            if cached_file_id:
                results.append(InlineQueryResultCachedAudio(
                    id=video_id,
                    audio_file_id=cached_file_id,
                ))
            else:
                results.append(_build_article(video_id, title, description))

        await inline_query.answer(results, cache_time=30, is_personal=True)

    except Exception as e:
        logging.error(f"Inline search error: {e}")
        await inline_query.answer([], cache_time=1)
