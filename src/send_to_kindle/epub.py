from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
import uuid
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from .articles import Article
from .markdown import markdown_to_xhtml


@dataclass(frozen=True)
class EpubMetadata:
    title: str
    author: str


def build_epub(articles: list[Article], metadata: EpubMetadata, output_dir: Path) -> Path:
    if not articles:
        raise ValueError("No articles selected")

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = slugify(metadata.title) + "-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".epub"
    output_path = output_dir / filename
    book_id = f"urn:uuid:{uuid.uuid4()}"
    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with ZipFile(output_path, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=ZIP_STORED)
        epub.writestr("META-INF/container.xml", container_xml(), compress_type=ZIP_DEFLATED)
        epub.writestr("OEBPS/styles.css", styles_css(), compress_type=ZIP_DEFLATED)
        epub.writestr("OEBPS/nav.xhtml", nav_xhtml(articles, metadata), compress_type=ZIP_DEFLATED)
        for index, article in enumerate(articles, start=1):
            epub.writestr(
                f"OEBPS/article-{index}.xhtml",
                article_xhtml(article, index),
                compress_type=ZIP_DEFLATED,
            )
        epub.writestr(
            "OEBPS/content.opf",
            content_opf(articles, metadata, book_id, modified),
            compress_type=ZIP_DEFLATED,
        )

    return output_path


def container_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def content_opf(articles: list[Article], metadata: EpubMetadata, book_id: str, modified: str) -> str:
    manifest_items = "\n".join(
        f'    <item id="article-{index}" href="article-{index}.xhtml" media-type="application/xhtml+xml"/>'
        for index, _article in enumerate(articles, start=1)
    )
    spine_items = "\n".join(f'    <itemref idref="article-{index}"/>' for index, _article in enumerate(articles, start=1))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" unique-identifier="book-id" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{escape(book_id)}</dc:identifier>
    <dc:title>{escape(metadata.title)}</dc:title>
    <dc:creator>{escape(metadata.author)}</dc:creator>
    <dc:language>en</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="styles" href="styles.css" media-type="text/css"/>
{manifest_items}
  </manifest>
  <spine>
{spine_items}
  </spine>
</package>
"""


def nav_xhtml(articles: list[Article], metadata: EpubMetadata) -> str:
    items = "\n".join(
        f'      <li><a href="article-{index}.xhtml">{escape(article.title)}</a></li>'
        for index, article in enumerate(articles, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
  <head>
    <title>{escape(metadata.title)}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>{escape(metadata.title)}</h1>
      <ol>
{items}
      </ol>
    </nav>
  </body>
</html>
"""


def article_xhtml(article: Article, index: int) -> str:
    source = article.frontmatter.get("source") or article.frontmatter.get("url")
    source_html = f'<p class="source"><a href="{escape(str(source))}">{escape(str(source))}</a></p>' if source else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
  <head>
    <title>{escape(article.title)}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
  </head>
  <body>
    <article id="article-{index}">
      <h1>{escape(article.title)}</h1>
      {source_html}
      {markdown_to_xhtml(article.markdown)}
    </article>
  </body>
</html>
"""


def styles_css() -> str:
    return """
body {
  font-family: serif;
  line-height: 1.5;
}

h1, h2, h3 {
  line-height: 1.2;
}

.source {
  font-size: 0.85em;
}

blockquote {
  border-left: 0.2em solid #999;
  margin-left: 0;
  padding-left: 1em;
}

img {
  max-width: 100%;
}
"""


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "articles"
