import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = ROOT_DIR / "config" / "sources.json"


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_active_domain(config):
    return config["active_domain"].rstrip("/")
