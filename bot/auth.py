import json
from pathlib import Path
from typing import Optional

from config import settings


class Auth:
    def __init__(self, config_path: str | None = None):
        self._path = Path(config_path or settings.users_config)

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._path.read_text())
            return data.get("authorized_users", [])
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def is_authorized(self, user_id: int) -> bool:
        return any(u.get("id") == user_id for u in self._load())

    def get_user_info(self, user_id: int) -> Optional[dict]:
        for u in self._load():
            if u.get("id") == user_id:
                return u
        return None


auth = Auth()
