import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from send_to_kindle.articles import parse_article
from send_to_kindle.base_filters import BaseHints, matches_selection
from send_to_kindle.cli import main
from send_to_kindle.epub import EpubMetadata, build_epub


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
        self.assertIn("OEBPS/article-1.xhtml", names)

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


if __name__ == "__main__":
    unittest.main()
