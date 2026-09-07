"""Markdown (.md) file loader -- strips markdown syntax down to plain text."""
import markdown
from bs4 import BeautifulSoup


def load_markdown(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    html = markdown.markdown(raw)
    return BeautifulSoup(html, "html.parser").get_text()
