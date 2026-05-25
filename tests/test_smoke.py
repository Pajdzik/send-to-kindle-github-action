import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from send_to_kindle.articles import parse_article
from send_to_kindle.base_filters import BaseHints, matches_selection
from send_to_kindle.cli import created_on_or_after, main
from send_to_kindle.config import KindleConfig
from send_to_kindle.epub import EpubMetadata, build_epub
from send_to_kindle.kindle import attachment_filename, send_to_kindle
from send_to_kindle.markdown import inline_markdown


class SmokeTest(unittest.TestCase):
    def test_parse_article_frontmatter_and_title(self):
        article = parse_article(
            "Articles/example.md",
            """---
title: Example Article
tags: [kindle, article]
kindle: true
---
# Ignored Heading

Hello **world**.
""",
        )

        self.assertEqual(article.title, "Example Article")
        self.assertIs(article.frontmatter["kindle"], True)
        self.assertEqual(article.frontmatter["tags"], ["kindle", "article"])

    def test_parse_article_uses_heading_when_frontmatter_title_is_filename(self):
        article = parse_article(
            "Articles/20260524-clipped-note.md",
            """---
title: 20260524 clipped note
---
# A Much Better Article Title

Hello.
""",
        )

        self.assertEqual(article.title, "A Much Better Article Title")

    def test_article_id_uses_url_and_survives_moves(self):
        text = """---
title: Example
URL: "https://Example.com:443/path?x=1#section"
---
Body
"""
        first = parse_article("Articles/example.md", text)
        moved = parse_article("Archive/example.md", text)

        self.assertEqual(first.id, moved.id)

    def test_article_id_falls_back_to_content_when_url_is_missing(self):
        text = """---
title: Example
---
Body
"""
        first = parse_article("Articles/example.md", text)
        moved = parse_article("Archive/example.md", text)

        self.assertEqual(first.id, moved.id)

    def test_selection_matches_tags_and_properties(self):
        article = parse_article(
            "Articles/example.md",
            """---
title: Example Article
tags:
  - kindle
kindle: true
---
Body
""",
        )

        self.assertTrue(
            matches_selection(
                article,
                required={"kindle": True},
                excluded={},
                base_hints=BaseHints(folders=("Articles",), tags=("kindle",)),
            )
        )


    def test_build_epub(self):
        article = parse_article("Articles/example.md", "# Example\n\nHello [site](https://example.com).")
        with tempfile.TemporaryDirectory() as tmp:
            output = build_epub([article], EpubMetadata(title="Test Articles", author="Kamil"), Path(tmp))

            self.assertTrue(output.exists())
            with zipfile.ZipFile(output) as epub:
                names = set(epub.namelist())

        self.assertIn("mimetype", names)
        self.assertIn("OEBPS/content.opf", names)
        self.assertIn("OEBPS/cover.xhtml", names)
        self.assertIn("OEBPS/images/cover.svg", names)
        self.assertIn("OEBPS/article-1.xhtml", names)

    def test_build_epub_declares_svg_cover(self):
        article = parse_article(
            "Articles/example.md",
            """---
title: A Larger Article Title
author: Jane Writer
url: https://www.example.com/path
---
Body
""",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = build_epub([article], EpubMetadata(title=article.title, author="Kamil"), Path(tmp))

            with zipfile.ZipFile(output) as epub:
                opf = epub.read("OEBPS/content.opf").decode("utf-8")
                cover = epub.read("OEBPS/images/cover.svg").decode("utf-8")

        self.assertIn('<meta name="cover" content="cover-image"/>', opf)
        self.assertIn('properties="cover-image"', opf)
        self.assertIn('<itemref idref="cover" linear="no"/>', opf)
        self.assertIn("A Larger Article Title", cover)
        self.assertIn("By Jane Writer", cover)
        self.assertIn("EXAMPLE.COM", cover)

    def test_cli_builds_one_epub_per_article_in_dry_run(self):
        first = parse_article("Articles/first.md", "# First\n\nHello.")
        second = parse_article("Articles/second.md", "# Second\n\nHello.")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "config.toml"
            config_path.write_text(
                f"""
[source]
type = "local"
vault_path = "{tmp_path}"
articles_path = "Articles"

[selection]
require = {{}}
exclude = {{}}
limit = 10

[output]
title = "Ignored Bundle Title"
author = "Kamil"
directory = "{tmp_path / "out"}"

[kindle]
dry_run = true

[state]
path = "{tmp_path / "state.json"}"
""",
                encoding="utf-8",
            )

            with patch("send_to_kindle.cli.load_articles", return_value=[first, second]):
                result = main(["--config", str(config_path)])

            self.assertEqual(result, 0)
            epub_files = sorted((tmp_path / "out").glob("*.epub"))
            self.assertEqual(len(epub_files), 2)
            self.assertTrue(any(path.name.startswith("first-") for path in epub_files))
            self.assertTrue(any(path.name.startswith("second-") for path in epub_files))

    def test_cli_sends_readable_article_title_to_kindle(self):
        article = parse_article("Articles/clipped-note.md", "# Actual Article Title\n\nHello.")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = tmp_path / "config.toml"
            config_path.write_text(
                f"""
[source]
type = "local"
vault_path = "{tmp_path}"
articles_path = "Articles"

[selection]
require = {{}}
exclude = {{}}
limit = 10

[output]
title = "Ignored Bundle Title"
author = "Kamil"
directory = "{tmp_path / "out"}"

[kindle]
dry_run = false

[state]
path = "{tmp_path / "state.json"}"
""",
                encoding="utf-8",
            )

            with (
                patch("send_to_kindle.cli.load_articles", return_value=[article]),
                patch("send_to_kindle.cli.send_to_kindle") as mocked_send,
            ):
                result = main(["--config", str(config_path)])

            self.assertEqual(result, 0)
            mocked_send.assert_called_once()
            self.assertEqual(mocked_send.call_args.kwargs["document_title"], "Actual Article Title")

    def test_kindle_attachment_filename_uses_document_title(self):
        self.assertEqual(
            attachment_filename('A Better: Article / Title?'),
            "A Better Article Title.epub",
        )

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "temp-slug-20260524.epub"
            epub_path.write_bytes(b"epub")
            config = KindleConfig(
                dry_run=False,
                kindle_email="kindle@example.com",
                from_email="from@example.com",
            )

            with (
                patch.dict("os.environ", {"SMTP_USER": "user", "SMTP_PASSWORD": "password"}),
                patch("send_to_kindle.kindle.smtplib.SMTP") as smtp_class,
            ):
                send_to_kindle(epub_path, config, document_title="Actual Article Title")

            smtp = smtp_class.return_value.__enter__.return_value
            message = smtp.send_message.call_args.args[0]
            attachment = next(message.iter_attachments())
            self.assertEqual(attachment.get_filename(), "Actual Article Title.epub")

    def test_markdown_images_render_as_links(self):
        html = inline_markdown("![Architecture](https://example.com/diagram.svg)")

        self.assertEqual(html, '<a href="https://example.com/diagram.svg">Architecture</a>')
        self.assertNotIn("<img", html)

    def test_created_cutoff(self):
        self.assertTrue(created_on_or_after("2026-02-04", "2026-02-01"))
        self.assertTrue(created_on_or_after("2026-02-04T12:00:00", "2026-02-04"))
        self.assertFalse(created_on_or_after("2026-01-31", "2026-02-01"))
        self.assertFalse(created_on_or_after(None, "2026-02-01"))
        self.assertTrue(created_on_or_after(None, ""))


if __name__ == "__main__":
    unittest.main()
