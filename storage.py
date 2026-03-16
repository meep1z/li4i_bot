import json

FAVORITES_FILE = "favorites.json"
FILE_ID_CACHE_FILE = "file_id_cache.json"


def load_favorites() -> dict:
    try:
        with open(FAVORITES_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_favorites(data: dict):
    with open(FAVORITES_FILE, "w") as f:
        json.dump(data, f)


def load_file_id_cache() -> dict:
    try:
        with open(FILE_ID_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_file_id_cache(data: dict):
    with open(FILE_ID_CACHE_FILE, "w") as f:
        json.dump(data, f)


def cache_file_id(video_id: str, file_id: str):
    data = load_file_id_cache()
    data[video_id] = file_id
    save_file_id_cache(data)
