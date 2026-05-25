from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from PIL import Image, ImageDraw, ImageFont

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
        epub.writestr("OEBPS/images/cover.jpg", cover_jpeg(articles[0], metadata), compress_type=ZIP_DEFLATED)
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
    <item id="cover-image" href="images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>
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
    <img src="images/cover.jpg" alt="{escape(metadata.title)}"/>
  </body>
</html>
"""


def cover_jpeg(article: Article, metadata: EpubMetadata) -> bytes:
    width = 1600
    height = 2560
    image = Image.new("RGB", (width, height), "#f5f1e8")
    draw = ImageDraw.Draw(image)

    title_font = cover_font(132, bold=True)
    source_font = cover_font(56)
    byline_font = cover_font(58)

    author = article_author(article)
    domain = article_domain(article)
    byline = f"By {author}" if author else ""
    source = domain.upper() if domain else ""

    draw.rectangle((88, 88, 1512, 2472), outline="#252525", width=8)
    draw.rectangle((120, 120, 1480, 2440), outline="#9a8f7b", width=2)
    draw.text((120, 270), source, fill="#756a58", font=source_font)

    title_lines = image_text_lines(draw, article.title, title_font, max_width=1360, max_lines=8)
    y = 430
    for line in title_lines:
        draw.text((120, y), line, fill="#1f1f1f", font=title_font)
        y += 148

    divider_y = max(1660, y + 90)
    draw.line((120, divider_y, 540, divider_y), fill="#252525", width=6)
    if byline:
        draw.text((120, divider_y + 50), byline, fill="#3a3a3a", font=byline_font)

    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def cover_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = (
        ("Georgia Bold.ttf", "Georgia.ttf"),
        ("Times New Roman Bold.ttf", "Times New Roman.ttf"),
        ("DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf"),
        ("LiberationSerif-Bold.ttf", "LiberationSerif-Regular.ttf"),
    )
    roots = (
        Path("/System/Library/Fonts/Supplemental"),
        Path("/Library/Fonts"),
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/truetype/liberation2"),
    )

    for bold_name, regular_name in names:
        filename = bold_name if bold else regular_name
        for root in roots:
            path = root / filename
            if path.exists():
                return ImageFont.truetype(str(path), size=size)

    return ImageFont.load_default()


def image_text_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = text.split()
    if not words:
        return ["Untitled"]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
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
