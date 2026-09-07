"""HTML file loader -- strips tags down to plain text."""
from bs4 import BeautifulSoup


def load_html(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    return BeautifulSoup(raw, "html.parser").get_text()
