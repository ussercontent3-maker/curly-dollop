import json
from pathlib import Path
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).resolve().parent.parent

STATE_DIR = ROOT_DIR / "state"
CHECKPOINT_FILE = STATE_DIR / "checkpoint.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def default_checkpoint(config):
    return {
        "status": "not_started",

        "domain": config["active_domain"],

        "last_index_page": config["start_page"] - 1,

        "discovered_videos": 0,

        "processed_videos": 0,

        "successful_videos": 0,

        "failed_videos": 0,

        "failed_pages": [],

        "seen_video_ids": [],

        "last_batch": 0,

        "started_at": None,

        "updated_at": utc_now()
    }


def load_checkpoint(config):
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if not CHECKPOINT_FILE.exists():
        checkpoint = default_checkpoint(config)
        save_checkpoint(checkpoint)
        return checkpoint

    try:
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            checkpoint = json.load(f)

        return checkpoint

    except Exception:
        print("WARNING: Checkpoint is corrupted. Creating a new one.")

        checkpoint = default_checkpoint(config)
        save_checkpoint(checkpoint)

        return checkpoint


def save_checkpoint(checkpoint):
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    checkpoint["updated_at"] = utc_now()

    temp_file = CHECKPOINT_FILE.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            checkpoint,
            f,
            ensure_ascii=False,
            indent=2
        )

    temp_file.replace(CHECKPOINT_FILE)


def mark_started(checkpoint):
    if not checkpoint["started_at"]:
        checkpoint["started_at"] = utc_now()

    checkpoint["status"] = "running"


def mark_completed(checkpoint):
    checkpoint["status"] = "completed"


def mark_failed(checkpoint):
    checkpoint["status"] = "failed"
