from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class SendState:
    sent_ids: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path) -> "SendState":
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(sent_ids=set(payload.get("sent_ids", [])))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sent_ids": sorted(self.sent_ids),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def unseen(self, article_ids: list[str]) -> list[str]:
        return [article_id for article_id in article_ids if article_id not in self.sent_ids]

    def mark_sent(self, article_ids: list[str]) -> None:
        self.sent_ids.update(article_ids)
