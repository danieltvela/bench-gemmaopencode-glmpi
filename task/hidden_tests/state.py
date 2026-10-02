"""State bridge between grading phases A (default env) and B (restart)."""

import json
import os


def path():
    return os.environ.get("SHELF_STATE", "")


def load():
    state_path = path()
    if not state_path or not os.path.exists(state_path):
        return {}
    with open(state_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save(data):
    state_path = path()
    if not state_path:
        return
    parent = os.path.dirname(state_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
    os.replace(tmp, state_path)
