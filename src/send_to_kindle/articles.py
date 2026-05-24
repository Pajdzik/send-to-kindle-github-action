from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any


@dataclass(frozen=True)
class Article:
    id: str
    path: str
    title: str
    markdown: str
    frontmatter: dict[str, Any]


def parse_article(path: str, text: str) -> Article:
    frontmatter, body = split_frontmatter(text)
    title = infer_title(path, body, frontmatter)
    digest = hashlib.sha256((path + "\0" + text).encode("utf-8")).hexdigest()[:16]
    return Article(id=digest, path=path, title=title, markdown=body.strip(), frontmatter=frontmatter)


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter_text = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return parse_simple_yaml(frontmatter_text), body

    return {}, text


def parse_simple_yaml(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        list_match = re.match(r"^\s*-\s+(.*)$", line)
        if list_match and current_key:
            values.setdefault(current_key, [])
            if isinstance(values[current_key], list):
                values[current_key].append(parse_scalar(list_match.group(1)))
            continue

        if ":" not in line:
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        current_key = key
        values[key] = [] if raw_value == "" else parse_scalar(raw_value)

    return values


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "none", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def infer_title(path: str, body: str, frontmatter: dict[str, Any]) -> str:
    for key in ("title", "name"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    for line in body.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()

    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled"


def article_sort_key(article: Article) -> tuple[str, str]:
    for key in ("published", "created", "date", "clipped"):
        value = article.frontmatter.get(key)
        if isinstance(value, str):
            normalized = normalize_date(value)
            if normalized:
                return (normalized, article.title.lower())
    return ("", article.title.lower())


def normalize_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return value
