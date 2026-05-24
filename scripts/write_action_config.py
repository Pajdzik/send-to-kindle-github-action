from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write send-to-kindle config for the GitHub Action.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--articles-path", required=True)
    parser.add_argument("--base-file", default="")
    parser.add_argument("--earliest-created", default="")
    parser.add_argument("--limit", default="10")
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--dry-run", default="false")
    parser.add_argument("--smtp-host", default="")
    parser.add_argument("--smtp-port", default="")
    args = parser.parse_args()
    smtp_host = args.smtp_host or os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = args.smtp_port or os.environ.get("SMTP_PORT") or "587"
    earliest_created = args.earliest_created or os.environ.get("EARLIEST_CREATED") or ""

    output = Path(args.output)
    output.write_text(
        "\n".join(
            [
                "[source]",
                'type = "local"',
                'vault_path = "."',
                f"articles_path = {toml_string(args.articles_path)}",
                "",
                "[selection]",
                f"base_file = {toml_string(args.base_file)}",
                "require = {}",
                "exclude = {}",
                f"earliest_created = {toml_string(earliest_created)}",
                f"limit = {toml_int(args.limit, default=10)}",
                "",
                "[output]",
                f"title = {toml_string(args.title)}",
                f"author = {toml_string(args.author)}",
                'directory = "out"',
                "",
                "[kindle]",
                f"dry_run = {toml_bool(args.dry_run)}",
                'kindle_email = ""',
                'kindle_email_env = "KINDLE_EMAIL"',
                'from_email = ""',
                'from_email_env = "FROM_EMAIL"',
                f"smtp_host = {toml_string(smtp_host)}",
                'smtp_host_env = "SMTP_HOST"',
                f"smtp_port = {toml_int(smtp_port, default=587)}",
                'smtp_port_env = "SMTP_PORT"',
                'smtp_user_env = "SMTP_USER"',
                'smtp_password_env = "SMTP_PASSWORD"',
                "",
                "[state]",
                f"path = {toml_string(args.state_path)}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return 0


def toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def toml_bool(value: str) -> str:
    return "true" if value.strip().lower() in {"1", "true", "yes", "on"} else "false"


def toml_int(value: str, *, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


if __name__ == "__main__":
    raise SystemExit(main())
