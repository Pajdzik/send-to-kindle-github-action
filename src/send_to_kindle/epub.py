from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import re
from urllib.parse import urlsplit
import uuid
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

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
    width = 1600
    height = 2560
    title_font = cover_font(bold=True)
    regular_font = cover_font()
    title_size = 132
    source_size = 56
    byline_size = 58

    author = article_author(article)
    domain = article_domain(article)
    byline = f"By {author}" if author else ""
    source = domain.upper() if domain else ""

    title_lines = svg_text_lines(article.title, title_font, title_size, max_width=1360, max_lines=8)
    y = 430
    title_paths: list[str] = []
    for line in title_lines:
        title_paths.append(svg_text_path(line, title_font, title_size, x=120, baseline=y + title_size))
        y += 148

    divider_y = max(1660, y + 90)
    source_path = svg_text_path(source, regular_font, source_size, x=120, baseline=330) if source else ""
    byline_path = (
        svg_text_path(byline, regular_font, byline_size, x=120, baseline=divider_y + 108)
        if byline
        else ""
    )

    title_paths_svg = "\n".join(f'  <path fill="#1f1f1f" d="{path}"/>' for path in title_paths if path)
    source_path_svg = f'  <path fill="#756a58" d="{source_path}"/>' if source_path else ""
    byline_path_svg = f'  <path fill="#3a3a3a" d="{byline_path}"/>' if byline_path else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <title>{escape(article.title)}</title>
  <rect x="0" y="0" width="{width}" height="{height}" fill="#f5f1e8"/>
  <rect x="88" y="88" width="1424" height="2384" fill="none" stroke="#252525" stroke-width="8"/>
  <rect x="120" y="120" width="1360" height="2320" fill="none" stroke="#9a8f7b" stroke-width="2"/>
{source_path_svg}
{title_paths_svg}
  <line x1="120" y1="{divider_y}" x2="540" y2="{divider_y}" stroke="#252525" stroke-width="6"/>
{byline_path_svg}
</svg>
"""


def cover_font(bold: bool = False) -> TTFont:
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
                return TTFont(str(path))

    raise RuntimeError("No usable TrueType cover font found")


def svg_text_lines(
    text: str,
    font: TTFont,
    size: int,
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
        if svg_text_width(candidate, font, size) <= max_width:
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


def svg_text_path(text: str, font: TTFont, size: int, x: int, baseline: int) -> str:
    glyph_set = font.getGlyphSet()
    cmap = best_cmap(font)
    advances = font["hmtx"].metrics
    scale = size / font["head"].unitsPerEm
    cursor = x
    pen = SVGPathPen(glyph_set)

    for character in text:
        glyph_name = cmap.get(ord(character))
        if not glyph_name:
            cursor += size * 0.35
            continue
        glyph = glyph_set[glyph_name]
        transform_pen = TransformPen(pen, (scale, 0, 0, -scale, cursor, baseline))
        glyph.draw(transform_pen)
        cursor += advances.get(glyph_name, (font["head"].unitsPerEm // 2, 0))[0] * scale

    return pen.getCommands()


def svg_text_width(text: str, font: TTFont, size: int) -> float:
    cmap = best_cmap(font)
    advances = font["hmtx"].metrics
    scale = size / font["head"].unitsPerEm
    total = 0.0
    for character in text:
        glyph_name = cmap.get(ord(character))
        if not glyph_name:
            total += size * 0.35
            continue
        total += advances.get(glyph_name, (font["head"].unitsPerEm // 2, 0))[0] * scale
    return total


def best_cmap(font: TTFont) -> dict[int, str]:
    cmap = font.getBestCmap()
    return cmap or {}


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
