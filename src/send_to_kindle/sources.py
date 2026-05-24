from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
from urllib.request import Request, urlopen

from .articles import Article, parse_article
from .config import SourceConfig


def load_articles(config: SourceConfig) -> list[Article]:
    if config.type == "local":
        return list(_load_local_articles(config))
    if config.type == "github":
        return list(_load_github_articles(config))
    raise ValueError(f"Unsupported source.type: {config.type}")


def _load_local_articles(config: SourceConfig) -> Iterable[Article]:
    vault = Path(config.vault_path).expanduser()
    root = vault / config.articles_path
    if not root.exists():
        raise FileNotFoundError(f"Article path does not exist: {root}")

    for path in sorted(root.rglob("*.md")):
        relative_path = path.relative_to(vault).as_posix()
        yield parse_article(relative_path, path.read_text(encoding="utf-8"))


def _load_github_articles(config: SourceConfig) -> Iterable[Article]:
    if not config.owner or not config.repo:
        raise ValueError("GitHub source requires owner and repo")

    prefix = config.path.strip("/")
    tree_url = (
        f"https://api.github.com/repos/{quote(config.owner)}/{quote(config.repo)}"
        f"/git/trees/{quote(config.branch)}?recursive=1"
    )
    tree = _request_json(tree_url, config.token_env)
    for item in tree.get("tree", []):
        path = item.get("path", "")
        if item.get("type") != "blob" or not path.endswith(".md"):
            continue
        if prefix and not (path == prefix or path.startswith(prefix + "/")):
            continue
        yield parse_article(path, _fetch_github_file(config, path))


def _fetch_github_file(config: SourceConfig, path: str) -> str:
    encoded_path = quote(path, safe="/")
    url = (
        f"https://api.github.com/repos/{quote(config.owner)}/{quote(config.repo)}"
        f"/contents/{encoded_path}?ref={quote(config.branch)}"
    )
    payload = _request_json(url, config.token_env)
    if payload.get("encoding") == "base64":
        encoded = payload.get("content", "")
        return base64.b64decode(encoded).decode("utf-8")
    download_url = payload.get("download_url")
    if download_url:
        return _request_text(download_url, config.token_env)
    raise ValueError(f"Could not read GitHub file content for {path}")


def _request_json(url: str, token_env: str) -> dict:
    return json.loads(_request_text(url, token_env))


def _request_text(url: str, token_env: str) -> str:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "send-to-kindle",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get(token_env) if token_env else None
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")
