import asyncio
import threading

from flask import Flask

from config import bot, dp
from handlers import commands, inline, download, favorites, search

app = Flask(__name__)


@app.route("/")
def index():
    return "Бот работает!"


def register_handlers():
    dp.include_router(commands.router)
    dp.include_router(inline.router)
    dp.include_router(download.router)
    dp.include_router(favorites.router)
    dp.include_router(search.router)


async def main():
    register_handlers()
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080),
        daemon=True,
    ).start()
    asyncio.run(main())
