from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    type: str = "local"
    vault_path: str = ""
    articles_path: str = "Articles"
    owner: str = ""
    repo: str = ""
    branch: str = "main"
    path: str = "Articles"
    token_env: str = "GITHUB_TOKEN"


@dataclass(frozen=True)
class SelectionConfig:
    base_file: str = ""
    require: dict[str, Any] = field(default_factory=dict)
    exclude: dict[str, Any] = field(default_factory=dict)
    limit: int = 10


@dataclass(frozen=True)
class OutputConfig:
    title: str = "Clipped Articles"
    author: str = "Unknown"
    directory: str = "out"


@dataclass(frozen=True)
class KindleConfig:
    dry_run: bool = True
    kindle_email: str = ""
    kindle_email_env: str = "KINDLE_EMAIL"
    from_email: str = ""
    from_email_env: str = "FROM_EMAIL"
    smtp_host: str = "smtp.gmail.com"
    smtp_host_env: str = "SMTP_HOST"
    smtp_port: int = 587
    smtp_port_env: str = "SMTP_PORT"
    smtp_user_env: str = "SMTP_USER"
    smtp_password_env: str = "SMTP_PASSWORD"


@dataclass(frozen=True)
class StateConfig:
    path: str = ".send-to-kindle-state.json"


@dataclass(frozen=True)
class AppConfig:
    source: SourceConfig = field(default_factory=SourceConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    kindle: KindleConfig = field(default_factory=KindleConfig)
    state: StateConfig = field(default_factory=StateConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    section = data.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"[{name}] must be a TOML table")
    return section


def load_config(path: Path) -> AppConfig:
    with path.open("rb") as file:
        raw = tomllib.load(file)

    return AppConfig(
        source=SourceConfig(**_section(raw, "source")),
        selection=SelectionConfig(**_section(raw, "selection")),
        output=OutputConfig(**_section(raw, "output")),
        kindle=KindleConfig(**_section(raw, "kindle")),
        state=StateConfig(**_section(raw, "state")),
    )
