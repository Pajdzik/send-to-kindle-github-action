from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


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
    article_id = article_identity(text, frontmatter)
    return Article(
        id=article_id,
        path=path,
        title=title,
        markdown=body.strip(),
        frontmatter=frontmatter,
    )


def article_identity(text: str, frontmatter: dict[str, Any]) -> str:
    url = article_url(frontmatter)
    if url:
        return digest_id("url", url)
    return digest_id("content", normalize_content(text))


def article_url(frontmatter: dict[str, Any]) -> str:
    url_keys = {
        "url",
        "source_url",
        "sourceurl",
        "canonical_url",
        "canonicalurl",
        "original_url",
        "originalurl",
        "link",
    }

    for key, value in frontmatter.items():
        normalized_key = str(key).strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_key not in url_keys:
            continue
        if isinstance(value, str):
            normalized = normalize_url(value)
            if normalized:
                return normalized
    return ""


def normalize_url(value: str) -> str:
    url = value.strip()
    if not url:
        return ""

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""

    netloc = parsed.netloc.lower()
    if parsed.scheme.lower() == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    if parsed.scheme.lower() == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]

    return urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, "")
    )


def normalize_content(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def digest_id(namespace: str, value: str) -> str:
    return hashlib.sha256((namespace + "\0" + value).encode("utf-8")).hexdigest()[:16]


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
    filename_title = infer_title_from_path(path)
    body_title = infer_title_from_body(body)

    title_keys = ("title", "name", "article_title", "articleTitle", "headline", "page_title", "pageTitle")
    for key in title_keys:
        value = frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            title = clean_title(value)
            if body_title and equivalent_title(title, filename_title):
                return body_title
            return title

    return body_title or filename_title or "Untitled"


def infer_title_from_body(body: str) -> str:
    for line in body.splitlines():
        match = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if match:
            return clean_title(match.group(1))

    lines = body.splitlines()
    for index, line in enumerate(lines[:-1]):
        if line.strip() and re.match(r"^\s*(=+|-+)\s*$", lines[index + 1]):
            return clean_title(line)

    return ""


def infer_title_from_path(path: str) -> str:
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled"


def clean_title(value: str) -> str:
    title = value.strip()
    link_match = re.match(r"^\[(.+?)\]\([^)]+\)$", title)
    if link_match:
        title = link_match.group(1).strip()
    return re.sub(r"\s+", " ", title)


def equivalent_title(first: str, second: str) -> bool:
    first_key = title_key(first)
    second_key = title_key(second)
    return bool(first_key and second_key and first_key == second_key)


def title_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


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
