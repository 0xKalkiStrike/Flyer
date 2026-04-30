import json
from datetime import datetime
from pathlib import Path
from typing import Any

JSON_STORE_PATH = Path("data/verification_results.json")


def ensure_store_path() -> None:
    JSON_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not JSON_STORE_PATH.exists():
        JSON_STORE_PATH.write_text("[]", encoding="utf-8")


def load_verification_results() -> list[dict[str, Any]]:
    ensure_store_path()
    try:
        with JSON_STORE_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return []


def append_verification_result(record: dict[str, Any]) -> None:
    results = load_verification_results()
    record["saved_at"] = datetime.utcnow().isoformat() + "Z"
    results.append(record)
    with JSON_STORE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
