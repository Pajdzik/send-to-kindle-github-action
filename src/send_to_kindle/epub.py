from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from .articles import Article, article_url
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
        epub.writestr("OEBPS/images/cover.svg", cover_svg(articles[0], metadata), compress_type=ZIP_DEFLATED)
        epub.writestr("OEBPS/cover.xhtml", cover_xhtml(metadata), compress_type=ZIP_DEFLATED)
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
    <meta name="cover" content="cover-image"/>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="styles" href="styles.css" media-type="text/css"/>
    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="cover-image" href="images/cover.svg" media-type="image/svg+xml" properties="cover-image"/>
{manifest_items}
  </manifest>
  <spine>
    <itemref idref="cover" linear="no"/>
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


def cover_xhtml(metadata: EpubMetadata) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
  <head>
    <title>{escape(metadata.title)}</title>
    <style>
      html, body {{
        margin: 0;
        padding: 0;
      }}

      img {{
        display: block;
        height: 100%;
        width: 100%;
      }}
    </style>
  </head>
  <body>
    <img src="images/cover.svg" alt="{escape(metadata.title)}"/>
  </body>
</html>
"""


def cover_svg(article: Article, metadata: EpubMetadata) -> str:
    title_lines = svg_text_lines(article.title, max_chars=24, max_lines=7)
    title_tspans = svg_tspans(title_lines, x=120, y=530, line_height=112)
    author = article_author(article) or metadata.author
    domain = article_domain(article)
    byline = f"By {author}" if author else ""
    source = domain.upper() if domain else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="2560" viewBox="0 0 1600 2560" role="img" aria-label="{escape(article.title)}">
  <rect width="1600" height="2560" fill="#f5f1e8"/>
  <rect x="88" y="88" width="1424" height="2384" fill="none" stroke="#252525" stroke-width="8"/>
  <rect x="120" y="120" width="1360" height="2320" fill="none" stroke="#9a8f7b" stroke-width="2"/>
  <text x="120" y="330" fill="#756a58" font-family="Georgia, 'Times New Roman', serif" font-size="56" letter-spacing="6">{escape(source)}</text>
  <text fill="#1f1f1f" font-family="Georgia, 'Times New Roman', serif" font-size="104" font-weight="700">
{title_tspans}
  </text>
  <line x1="120" y1="1690" x2="540" y2="1690" stroke="#252525" stroke-width="6"/>
  <text x="120" y="1805" fill="#3a3a3a" font-family="Georgia, 'Times New Roman', serif" font-size="58">{escape(byline)}</text>
  <text x="120" y="2235" fill="#756a58" font-family="Georgia, 'Times New Roman', serif" font-size="44">Sent to Kindle</text>
</svg>
"""


def svg_tspans(lines: list[str], x: int, y: int, line_height: int) -> str:
    return "\n".join(
        f'    <tspan x="{x}" y="{y + (index * line_height)}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )


def svg_text_lines(text: str, max_chars: int, max_lines: int) -> list[str]:
    words = text.split()
    if not words:
        return ["Untitled"]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word

    if current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "..."

    return lines


def article_author(article: Article) -> str:
    for key in ("author", "byline", "creator"):
        value = article.frontmatter.get(key)
        if isinstance(value, str) and value.strip():
            return clean_cover_text(value)
    return ""


def article_domain(article: Article) -> str:
    url = article_url(article.frontmatter)
    if not url:
        source = article.frontmatter.get("source")
        url = str(source).strip() if isinstance(source, str) else ""

    parsed = urlsplit(url)
    domain = parsed.netloc or parsed.path
    domain = domain.lower().removeprefix("www.")
    return clean_cover_text(domain)


def clean_cover_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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
