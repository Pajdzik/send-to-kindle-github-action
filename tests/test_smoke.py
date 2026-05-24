import tempfile
import unittest
import zipfile
from pathlib import Path

from send_to_kindle.articles import parse_article
from send_to_kindle.base_filters import BaseHints, matches_selection
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


if __name__ == "__main__":
    unittest.main()
