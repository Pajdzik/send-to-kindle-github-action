from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from .articles import Article, parse_scalar


@dataclass(frozen=True)
class BaseHints:
    folders: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    require: dict[str, Any] = field(default_factory=dict)
    exclude: dict[str, Any] = field(default_factory=dict)


def load_base_hints(path: str) -> BaseHints:
    if not path:
        return BaseHints()

    text = Path(path).expanduser().read_text(encoding="utf-8")
    folders = tuple(_clean_folder(item) for item in re.findall(r"file\.inFolder\([\"'](.+?)[\"']\)", text))
    tag_matches = re.findall(r"file\.hasTag\([\"'](.+?)[\"']\)", text)
    tag_matches += re.findall(r"tag\s+contains\s+[\"'](.+?)[\"']", text)
    tags = tuple(_clean_tag(item) for item in tag_matches)

    require: dict[str, Any] = {}
    exclude: dict[str, Any] = {}
    for key, op, raw_value in re.findall(r"(?:note\.)?([A-Za-z0-9_-]+)\s*(==|!=)\s*([\"'][^\"']+[\"']|true|false|\d+)", text):
        value = parse_scalar(raw_value)
        if op == "==":
            require[key] = value
        else:
            exclude[key] = value

    return BaseHints(
        folders=tuple(folder for folder in folders if folder),
        tags=tuple(tag for tag in tags if tag),
        require=require,
        exclude=exclude,
    )


def matches_selection(
    article: Article,
    *,
    required: dict[str, Any],
    excluded: dict[str, Any],
    base_hints: BaseHints,
) -> bool:
    if base_hints.folders and not any(_path_in_folder(article.path, folder) for folder in base_hints.folders):
        return False

    if base_hints.tags:
        article_tags = {_clean_tag(str(tag)) for tag in _as_list(article.frontmatter.get("tags"))}
        inline_tags = {_clean_tag(tag) for tag in re.findall(r"(?<!\w)#([\w/-]+)", article.markdown)}
        all_tags = article_tags | inline_tags
        if not all(_clean_tag(tag) in all_tags for tag in base_hints.tags):
            return False

    merged_required = {**base_hints.require, **required}
    merged_excluded = {**base_hints.exclude, **excluded}

    for key, expected in merged_required.items():
        if not value_matches(article.frontmatter.get(key), expected):
            return False

    for key, expected in merged_excluded.items():
        if value_matches(article.frontmatter.get(key), expected):
            return False

    return True


def value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(actual, list):
        return expected in actual or str(expected) in {str(item) for item in actual}
    return actual == expected or str(actual).lower() == str(expected).lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _clean_folder(folder: str) -> str:
    return folder.strip().strip("/")


def _clean_tag(tag: str) -> str:
    return tag.strip().lstrip("#")


def _path_in_folder(path: str, folder: str) -> bool:
    normalized_path = path.strip("/")
    normalized_folder = folder.strip("/")
    return normalized_path == normalized_folder or normalized_path.startswith(normalized_folder + "/")
