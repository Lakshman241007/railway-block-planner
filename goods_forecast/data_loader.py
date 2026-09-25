import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data-goods-trains"


def load_json(filename):
    path = DATA_DIR / filename

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)