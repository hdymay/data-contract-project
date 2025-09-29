from __future__ import annotations

from pathlib import Path
import os
from typing import Any, Dict, List, Optional
import inspect
import logging

logger = logging.getLogger("uvicorn.error")

try:
    import fitz  
except Exception:  # pragma: no cover
    fitz = None  # type: ignore


def _percentile(values: List[float], percent: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * percent
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def extract_structured_text_pymupdf(page: "fitz.Page", mode: str = "dict") -> Dict[str, Any]:
    data = page.get_text(mode)
    blocks: List[Dict[str, Any]] = data.get("blocks", []) if isinstance(data, dict) else []

    all_sizes: List[float] = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size")
                if isinstance(size, (int, float)):
                    all_sizes.append(float(size))

    heading_threshold = _percentile(all_sizes, 0.90)
    subheading_threshold = _percentile(all_sizes, 0.75)

    headings: List[str] = []
    subheadings: List[str] = []
    body: List[str] = []

    def _add_text(target: List[str], text: str):
        text = (text or "").strip()
        if text:
            target.append(text)

    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                size = float(span.get("size", 0))
                if size >= heading_threshold and size > 0:
                    _add_text(headings, text)
                elif size >= subheading_threshold and size > 0:
                    _add_text(subheadings, text)
                else:
                    _add_text(body, text)

    body_joined = " ".join(body)
    return {
        "mode": mode,
        "thresholds": {
            "heading": heading_threshold,
            "subheading": subheading_threshold,
        },
        "headings": headings,
        "subheadings": subheadings,
        "body": body,
        "body_preview": body_joined[:2000],
    }


def parse_pdf_with_pymupdf(path: Path) -> Dict[str, Any]:
    """PyMuPDF로 1페이지 구조 추출(기본 휴리스틱)."""
    if fitz is None:
        logger.warning("PyMuPDF 미설치")
        return {"success": False, "error": "pymupdf_not_installed"}

    try:
        with fitz.open(path) as doc:
            if doc.page_count == 0:
                return {"success": True, "message": "empty_pdf", "structured_preview": None}

            page = doc.load_page(0)

            # == text extract ==
            # simple_text = page.get_text("text") or ""
            # simple_preview = simple_text[:2000]
            # logger.info("[PyMuPDF simple] %s\n%s", path.name, simple_preview)

            # == dict extract ==
            structured = extract_structured_text_pymupdf(page, mode="dict")
            structured_preview = {
                "headings": structured.get("headings", [])[:100],
                "subheadings": structured.get("subheadings", [])[:100],
                "body_preview": structured.get("body_preview", "")[:2000],
            }
            logger.info(
                "[PyMuPDF structured] %s\nHeadings: %s\nSubheadings: %s\nBody: %s",
                path.name,
                ", ".join(structured_preview["headings"]),
                ", ".join(structured_preview["subheadings"]),
                structured_preview["body_preview"],
            )

            return {
                "success": True,
                "structured_preview": structured_preview,
                "extracted_preview": structured.get("body_preview", "")[:200],
            }
    except Exception as e:  # pragma: no cover
        logger.exception("PyMuPDF 처리 중 오류: %s", e)
        return {"success": False, "error": str(e)}


## MarkItDown 경로는 제거되었습니다.


