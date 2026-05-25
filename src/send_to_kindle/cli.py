from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys
from typing import Any

from .articles import article_sort_key
from .base_filters import load_base_hints, matches_selection
from .config import load_config
from .epub import EpubMetadata, build_epub
from .kindle import send_to_kindle
from .sources import load_articles
from .state import SendState


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send clipped Obsidian articles to Kindle.")
    parser.add_argument("--config", default="config.toml", help="Path to config TOML.")
    parser.add_argument("--dry-run", action="store_true", help="Build EPUB without sending or marking sent.")
    parser.add_argument("--list", action="store_true", help="List selected articles without building an EPUB.")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        print("Start with: cp config.example.toml config.toml", file=sys.stderr)
        return 2

    config = load_config(config_path)
    state_path = Path(config.state.path)
    state = SendState.load(state_path)
    base_hints = load_base_hints(config.selection.base_file)

    articles = [
        article
        for article in load_articles(config.source)
        if matches_selection(
            article,
            required=config.selection.require,
            excluded=config.selection.exclude,
            base_hints=base_hints,
            excluded_tags=tuple(config.selection.skip_tags),
        )
        and created_on_or_after(article.frontmatter.get("created"), config.selection.earliest_created)
    ]
    articles.sort(key=article_sort_key, reverse=True)
    articles = [article for article in articles if article.id not in state.sent_ids]
    if config.selection.limit > 0:
        articles = articles[: config.selection.limit]

    if args.list:
        for article in articles:
            print(f"{article.id}  {article.path}  {article.title}")
        return 0

    if not articles:
        print("No new articles selected.")
        return 0

    output_dir = Path(config.output.directory)
    epub_jobs = [
        (
            article,
            build_epub(
                [article],
                EpubMetadata(title=article.title, author=config.output.author),
                output_dir,
            ),
        )
        for article in articles
    ]
    effective_dry_run = args.dry_run or config.kindle.dry_run
    if effective_dry_run:
        for _article, epub_path in epub_jobs:
            print(f"Built EPUB: {epub_path}")
        print(f"Dry run: not sent, and state was not updated. Articles: {len(articles)}")
        return 0

    for article, epub_path in epub_jobs:
        send_to_kindle(epub_path, config.kindle, document_title=article.title)
    state.mark_sent([article.id for article in articles])
    state.save(state_path)
    print(f"Sent {len(articles)} article(s) to Kindle.")
    return 0


def created_on_or_after(created_value: Any, earliest_created: str) -> bool:
    cutoff = parse_date(earliest_created)
    if cutoff is None:
        return True

    created = parse_date(created_value)
    if created is None:
        return False
    return created >= cutoff


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
