"""Read source text from HTML and PDF financial evidence links."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import requests

from app.tools._utils import DEFAULT_HEADERS, clean_text


@dataclass
class SourceReadResult:
    url: str
    content_type: str
    text: str
    success: bool
    error: str | None = None


def read_source_text(
    url: str,
    timeout: float = 20.0,
    max_chars: int = 20000,
) -> SourceReadResult:
    """Read bounded text from a source URL.

    HTML is preferred because IR/key-figures pages are usually easier to parse
    than long annual-report PDFs. PDF extraction uses pypdf when available.
    """

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:
        return SourceReadResult(url=url, content_type="unknown", text="", success=False, error=str(exc))

    content_type = response.headers.get("content-type", "").lower()
    is_pdf = "application/pdf" in content_type or url.lower().split("?", 1)[0].endswith(".pdf")
    try:
        if is_pdf:
            text = _read_pdf_text(response.content, max_chars=max_chars)
            return SourceReadResult(url=url, content_type="pdf", text=text, success=bool(text))
        text = _read_html_text(response.text, max_chars=max_chars)
        return SourceReadResult(url=url, content_type="html", text=text, success=bool(text))
    except Exception as exc:
        return SourceReadResult(url=url, content_type="pdf" if is_pdf else "html", text="", success=False, error=str(exc))


def _read_html_text(html: str, max_chars: int) -> str:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript", "svg", "nav", "header", "footer", "aside"]):
            element.decompose()
        return clean_text(soup.get_text(" "), max_chars=max_chars)
    except Exception:
        return clean_text(html, max_chars=max_chars)


def _read_pdf_text(content: bytes, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("PDF text extraction requires pypdf") from exc

    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    total_chars = 0
    for page in reader.pages[:20]:
        page_text = page.extract_text() or ""
        parts.append(page_text)
        total_chars += len(page_text)
        if total_chars >= max_chars:
            break
    return clean_text(" ".join(parts), max_chars=max_chars)
