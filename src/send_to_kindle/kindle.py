from __future__ import annotations

from email.message import EmailMessage
import os
from pathlib import Path
import re
import smtplib

from .config import KindleConfig


def send_to_kindle(epub_path: Path, config: KindleConfig, document_title: str | None = None) -> None:
    if config.dry_run:
        return

    kindle_email = _value_or_env(config.kindle_email, config.kindle_email_env)
    from_email = _value_or_env(config.from_email, config.from_email_env)
    if not kindle_email:
        raise ValueError("kindle.kindle_email or kindle.kindle_email_env is required when dry_run is false")
    if not from_email:
        raise ValueError("kindle.from_email or kindle.from_email_env is required when dry_run is false")

    username = os.environ.get(config.smtp_user_env)
    password = os.environ.get(config.smtp_password_env)
    if not username or not password:
        raise ValueError(
            f"Missing SMTP credentials in {config.smtp_user_env} and {config.smtp_password_env}"
        )

    smtp_host = _value_from_env_or_default(config.smtp_host_env, config.smtp_host)
    smtp_port = _int_from_env_or_default(config.smtp_port_env, config.smtp_port)

    message = EmailMessage()
    message["Subject"] = "convert"
    message["From"] = from_email
    message["To"] = kindle_email
    message.set_content("Attached articles for Kindle.")
    message.add_attachment(
        epub_path.read_bytes(),
        maintype="application",
        subtype="epub+zip",
        filename=attachment_filename(document_title) or epub_path.name,
    )

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def _value_or_env(value: str, env_name: str) -> str:
    if value:
        return value
    if env_name:
        return os.environ.get(env_name, "")
    return ""


def _value_from_env_or_default(env_name: str, default: str) -> str:
    if env_name:
        value = os.environ.get(env_name)
        if value:
            return value
    return default


def _int_from_env_or_default(env_name: str, default: int) -> int:
    if env_name:
        value = os.environ.get(env_name)
        if value:
            try:
                return int(value)
            except ValueError as error:
                raise ValueError(f"{env_name} must be an integer") from error
    return default


def attachment_filename(document_title: str | None) -> str:
    if not document_title:
        return ""

    stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]+', " ", document_title)
    stem = re.sub(r"\s+", " ", stem).strip().rstrip(".")
    if not stem:
        return ""
    if len(stem) > 120:
        stem = stem[:120].rstrip()
    return f"{stem}.epub"
