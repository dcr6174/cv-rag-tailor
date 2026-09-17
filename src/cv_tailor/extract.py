"""Extract plain text from uploaded CV files.

Supported formats: .txt, .md, .pdf, .docx. Extraction is local-only;
uploaded content is held in memory and never written to disk.
"""
from __future__ import annotations

import io

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_TEXT_CHARS = 200_000

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf", ".docx")


class UnsupportedFileError(ValueError):
    """Raised when the uploaded file type is not supported."""


class ExtractionError(ValueError):
    """Raised when text cannot be pulled out of a supported file."""


def _extension(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""


def extract_text(filename: str, data: bytes) -> str:
    """Return the plain-text content of an uploaded CV file."""
    if not data:
        raise ExtractionError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ExtractionError("The file is larger than 5 MB.")

    ext = _extension(filename)
    if ext in (".txt", ".md"):
        text = _decode(data)
    elif ext == ".pdf":
        text = _from_pdf(data)
    elif ext == ".docx":
        text = _from_docx(data)
    else:
        raise UnsupportedFileError(
            f"Unsupported file type '{ext or 'unknown'}'. Upload a .txt, .md, .pdf, or .docx file."
        )

    text = text.strip()
    if not text:
        raise ExtractionError("No readable text was found in the file.")
    return text[:MAX_TEXT_CHARS]


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _from_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # pypdf raises several parser-specific errors
        raise ExtractionError(f"Could not read the PDF: {exc}") from exc
    return "\n".join(pages)


def _from_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(f"Could not read the DOCX: {exc}") from exc
    return "\n".join(p.text for p in document.paragraphs)
