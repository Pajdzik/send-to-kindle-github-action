from __future__ import annotations

from email.message import EmailMessage
import os
from pathlib import Path
import smtplib

from .config import KindleConfig


def send_to_kindle(epub_path: Path, config: KindleConfig) -> None:
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

    message = EmailMessage()
    message["Subject"] = "convert"
    message["From"] = from_email
    message["To"] = kindle_email
    message.set_content("Attached articles for Kindle.")
    message.add_attachment(
        epub_path.read_bytes(),
        maintype="application",
        subtype="epub+zip",
        filename=epub_path.name,
    )

    with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def _value_or_env(value: str, env_name: str) -> str:
    if value:
        return value
    if env_name:
        return os.environ.get(env_name, "")
    return ""
