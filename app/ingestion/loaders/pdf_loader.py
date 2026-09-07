"""PDF file loader."""
from pypdf import PdfReader


def load_pdf(file_path):
    reader = PdfReader(file_path)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)
