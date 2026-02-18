#!/usr/bin/env python3
"""Translate webpage content to Korean and export it as a PDF.

This implementation intentionally uses only Python standard library modules.
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


class WebpageTranslationError(RuntimeError):
    """Raised when webpage translation pipeline fails."""


@dataclass
class TranslationConfig:
    source_lang: str = "auto"
    target_lang: str = "ko"
    timeout_s: int = 20
    chunk_size: int = 1500


class TextExtractor(HTMLParser):
    """Collect visible text from HTML while skipping non-content tags."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg", "meta", "link"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "meta", "link"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)


def fetch_webpage_text(url: str, timeout_s: int) -> str:
    """Fetch a webpage and extract visible text."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            raw_html = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise WebpageTranslationError(f"웹페이지를 불러오지 못했습니다: {exc}") from exc

    parser = TextExtractor()
    parser.feed(raw_html)

    text = "\n".join(parser.parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not text:
        raise WebpageTranslationError("웹페이지에서 번역할 본문 텍스트를 찾지 못했습니다.")

    return text


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Split text into translation API friendly chunks."""
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        candidate = f"{current}\n{paragraph}" if current else paragraph
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        elif len(paragraph) > max_chars:
            for piece in textwrap.wrap(paragraph, width=max_chars):
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def _translate_chunk(chunk: str, source: str, target: str, timeout_s: int) -> str:
    query = urllib.parse.urlencode(
        {
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": chunk,
        }
    )
    url = f"https://translate.googleapis.com/translate_a/single?{query}"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as response:
            payload = response.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        raise WebpageTranslationError(f"번역 API 호출 실패: {exc}") from exc

    try:
        data = json.loads(payload)
        segments = [item[0] for item in data[0] if item and item[0]]
    except Exception as exc:
        raise WebpageTranslationError(f"번역 결과 파싱 실패: {exc}") from exc

    result = "".join(segments).strip()
    if not result:
        raise WebpageTranslationError("번역 결과가 비어 있습니다.")
    return result


def translate_text(text: str, config: TranslationConfig) -> str:
    chunks = chunk_text(text, config.chunk_size)
    translated = [
        _translate_chunk(chunk, config.source_lang, config.target_lang, config.timeout_s)
        for chunk in chunks
    ]
    return "\n\n".join(translated)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(text: str, output_path: Path, title: str) -> None:
    """Write translated text into a basic multi-page PDF.

    Uses an Adobe Korea1 CID font reference (`HYSMyeongJo-Medium`) so Korean glyphs
    can be rendered in standard PDF viewers.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"번역 결과: {title}", ""]
    for para in text.split("\n"):
        wrapped = textwrap.wrap(para, width=46) or [""]
        lines.extend(wrapped)

    page_line_limit = 40
    pages = [lines[i : i + page_line_limit] for i in range(0, len(lines), page_line_limit)]

    objects: list[bytes] = []

    def add_obj(content: str | bytes) -> int:
        data = content.encode("latin-1") if isinstance(content, str) else content
        objects.append(data)
        return len(objects)

    font_obj = add_obj(
        "<< /Type /Font /Subtype /Type0 /BaseFont /HYSMyeongJo-Medium "
        "/Encoding /UniKS-UCS2-H /DescendantFonts [2 0 R] >>"
    )

    descendant_font = add_obj(
        "<< /Type /Font /Subtype /CIDFontType0 /BaseFont /HYSMyeongJo-Medium "
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (Korea1) /Supplement 1 >> "
        "/DW 1000 >>"
    )

    # Replace placeholder reference to descendant font object now that we know IDs.
    objects[font_obj - 1] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /HYSMyeongJo-Medium "
        f"/Encoding /UniKS-UCS2-H /DescendantFonts [{descendant_font} 0 R] >>"
    ).encode("latin-1")

    page_obj_ids = []
    content_obj_ids = []

    for page_lines in pages:
        stream_ops = ["BT", "/F1 12 Tf", "50 780 Td", "16 TL"]
        first = True
        for line in page_lines:
            encoded = ("\ufeff" + line).encode("utf-16-be").hex().upper()
            if first:
                stream_ops.append(f"<{encoded}> Tj")
                first = False
            else:
                stream_ops.append("T*")
                stream_ops.append(f"<{encoded}> Tj")
        stream_ops.append("ET")
        stream_text = "\n".join(stream_ops)
        stream_bytes = stream_text.encode("latin-1")

        content_id = add_obj(
            b"<< /Length " + str(len(stream_bytes)).encode("ascii") + b" >>\nstream\n" + stream_bytes + b"\nendstream"
        )
        content_obj_ids.append(content_id)

        page_id = add_obj(
            "<< /Type /Page /Parent PAGES_REF /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_obj_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_ids)} >>")

    # Patch page objects with real parent reference.
    for pid in page_obj_ids:
        objects[pid - 1] = objects[pid - 1].replace(b"PAGES_REF", f"{pages_obj} 0 R".encode("latin-1"))

    catalog_obj = add_obj(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")

    pdf = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = [0]

    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )

    output_path.write_bytes(pdf)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="웹페이지 내용을 한국어로 번역하고 PDF 파일로 저장합니다."
    )
    parser.add_argument("url", help="번역할 웹페이지 URL")
    parser.add_argument("-o", "--output", default="translated_webpage.pdf", help="출력 PDF 파일 경로")
    parser.add_argument("--source-lang", default="auto", help="원본 언어 코드")
    parser.add_argument("--target-lang", default="ko", help="번역 대상 언어 코드")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    config = TranslationConfig(source_lang=args.source_lang, target_lang=args.target_lang)

    original_text = fetch_webpage_text(args.url, timeout_s=config.timeout_s)
    translated_text = translate_text(original_text, config)
    write_pdf(translated_text, Path(args.output), title=args.url)

    print(f"완료: PDF 파일이 생성되었습니다 -> {args.output}")


if __name__ == "__main__":
    main()
