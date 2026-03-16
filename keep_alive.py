import threading
import time
import logging
import urllib.request


def _ping_loop(url: str, interval: int):
    while True:
        try:
            urllib.request.urlopen(url, timeout=10)
            logging.info(f"Keep-alive ping OK → {url}")
        except Exception as e:
            logging.warning(f"Keep-alive ping failed: {e}")
        time.sleep(interval)


def start(url: str = "http://localhost:8080/", interval: int = 60):
    t = threading.Thread(target=_ping_loop, args=(url, interval), daemon=True)
    t.start()
