"""Plain text (.txt) file loader."""


def load_text(file_path):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()
