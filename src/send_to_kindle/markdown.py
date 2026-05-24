from __future__ import annotations

from html import escape
import re


def markdown_to_xhtml(markdown: str) -> str:
    lines = markdown.splitlines()
    html: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                html.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_lines.append(line)
            continue

        if not line.strip():
            if in_list:
                html.append("</ul>")
                in_list = False
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            if in_list:
                html.append("</ul>")
                in_list = False
            level = len(heading.group(1))
            html.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
            continue

        item = re.match(r"^\s*[-*]\s+(.+)$", line)
        if item:
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{inline_markdown(item.group(1))}</li>")
            continue

        quote = re.match(r"^\s*>\s+(.+)$", line)
        if quote:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<blockquote><p>{inline_markdown(quote.group(1))}</p></blockquote>")
            continue

        if in_list:
            html.append("</ul>")
            in_list = False
        html.append(f"<p>{inline_markdown(line)}</p>")

    if in_code:
        html.append("<pre><code>" + escape("\n".join(code_lines)) + "</code></pre>")
    if in_list:
        html.append("</ul>")

    return "\n".join(html)


def inline_markdown(text: str) -> str:
    text = escape(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_to_link, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def image_to_link(match: re.Match[str]) -> str:
    alt = match.group(1).strip() or "Image"
    url = match.group(2).strip()
    return f'<a href="{url}">{alt}</a>'
