"""Offline, extractive PDF evidence demo. The TXT starter in app.py is unchanged."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from pypdf import PdfReader

CORPUS = Path(__file__).resolve().parent / "pdf_corpus"
ALLOWED_PDFS = ("faq.pdf", "guide.pdf", "sop.pdf")
MAX_PDF_BYTES = 256_000
MAX_PAGES = 8
MAX_PAGE_CHARS = 20_000
ABSTENTION = "The supplied PDFs do not support one unambiguous answer."
ENGINE = "OFFLINE_PDF_EXTRACTIVE_DEMO_NO_LLM"
STOPWORDS = frozenset("a an and are can do does for from how i in is it of on or the to what when where who why with you your after before much many an at as".split())


@dataclass(frozen=True)
class Page:
    document: str
    number: int
    text: str


@dataclass(frozen=True)
class Passage:
    document: str
    page: int
    text: str  # Search text, including a table heading for each table row.
    span: str  # Exact line extracted from the cited PDF page.


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _tokens(text: str) -> set[str]:
    result = set()
    for token in re.findall(r"[a-z0-9]+", text.casefold()):
        if token in STOPWORDS or len(token) < 2:
            continue
        if token.endswith("ed") and len(token) > 5:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 4 and not token.endswith("ss"):
            token = token[:-1]
        result.add(token)
    return result


def load_pdf_pages(folder: Path = CORPUS) -> list[Page]:
    """Read only the three fixed PDF names; caller cannot supply paths through /chat."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("PDF corpus directory is missing or linked")
    root = folder.resolve(strict=True)
    present = {path.name for path in folder.glob("*.pdf")}
    if present != set(ALLOWED_PDFS):
        raise ValueError("PDF corpus must contain exactly the three allowlisted PDFs")
    pages: list[Page] = []
    for name in ALLOWED_PDFS:
        path = folder / name
        if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root:
            raise ValueError(f"Invalid PDF path: {name}")
        size = path.stat().st_size
        if size < 8 or size > MAX_PDF_BYTES:
            raise ValueError(f"PDF size outside bounds: {name}")
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError(f"Unsupported or malformed PDF: {name}")
            handle.seek(0)
            try:
                reader = PdfReader(handle, strict=True)
                if reader.is_encrypted:
                    raise ValueError(f"Encrypted PDF rejected: {name}")
                if not 1 <= len(reader.pages) <= MAX_PAGES:
                    raise ValueError(f"PDF page count outside bounds: {name}")
                for number, page in enumerate(reader.pages, start=1):
                    extracted = page.extract_text()
                    if not extracted or len(extracted) > MAX_PAGE_CHARS:
                        raise ValueError(f"PDF page text missing or oversized: {name}:{number}")
                    pages.append(Page(name, number, extracted))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f"Malformed PDF rejected: {name}") from exc
    return pages


def make_passages(pages: list[Page]) -> list[Passage]:
    out: list[Passage] = []
    seen: set[tuple[str, int, str]] = set()
    for page in pages:
        table_title = ""
        table_header = ""
        for raw in page.text.splitlines():
            line = raw.strip()
            if not line or line.startswith("FICTIONAL SYNTHETIC"):
                continue
            if line.startswith("UNTRUSTED DOCUMENT NOTE:"):
                continue  # It remains data in the PDF, but is never an answer candidate.
            if line.startswith("TABLE:"):
                table_title = line.removeprefix("TABLE:").strip()
                continue
            if line.startswith("Plan |"):
                table_header = line
                continue
            search_text = f"{table_title} {table_header} {line}" if " | " in line else line
            key = (page.document, page.number, _normalize(line))
            if key not in seen:
                out.append(Passage(page.document, page.number, search_text, line))
                seen.add(key)
    return out


def _rank(query: str, passages: list[Passage]) -> list[tuple[float, Passage]]:
    duration_query = "how long" in query.casefold() or "window" in _tokens(query)
    # Duration phrasing expresses intent; it need not appear verbatim in evidence.
    terms = _tokens(query) - ({"long", "window"} if duration_query else set())
    if len(terms) < 2:
        return []
    scored = []
    for passage in passages:
        overlap = terms & _tokens(passage.text)
        coverage = len(overlap) / len(terms)
        if len(overlap) < 2 or coverage < 0.6:
            continue
        duration_boost = 0.25 if duration_query and re.search(r"\b(day|days|hour|hours|week|weeks|month|months)\b", passage.span, re.I) else 0.0
        scored.append((coverage + duration_boost, passage))
    return sorted(scored, key=lambda row: (-row[0], row[1].document, row[1].page, row[1].span))


def retrieve(query: str, passages: list[Passage], *, k: int = 3) -> list[Passage]:
    if k < 1:
        raise ValueError("k must be positive")
    return [passage for _, passage in _rank(query, passages)[:k]]


def verify_citations(answer: str, citations: list[dict], pages: list[Page]) -> bool:
    if not answer or not citations or len(citations) > len(pages):
        return False
    by_ref = {(p.document, p.number): p.text for p in pages}
    seen = set()
    needle = _normalize(answer)
    for cite in citations:
        if (not isinstance(cite, dict) or set(cite) != {"document", "page"}
                or not isinstance(cite["document"], str)
                or type(cite["page"]) is not int):
            return False
        ref = (cite["document"], cite["page"])
        if ref in seen or ref not in by_ref or needle not in _normalize(by_ref[ref]):
            return False
        seen.add(ref)
    return True


def answer_question(query: str, pages: list[Page]) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("Question must contain 1 to 500 characters")
    passages = make_passages(pages)
    ranked = _rank(query, passages)
    abstain = {"status": "ABSTAIN", "answer": ABSTENTION, "evidence_span": None,
               "citations": [], "verified": False, "engine": ENGINE}
    if not ranked:
        return abstain
    top_score, top = ranked[0]
    competing = [p for score, p in ranked[1:] if top_score - score <= 0.15]
    if any(_normalize(p.span) != _normalize(top.span) for p in competing):
        return abstain
    citations = [{"document": p.document, "page": p.page} for p in passages
                 if _normalize(p.span) == _normalize(top.span)]
    if not verify_citations(top.span, citations, pages):
        return abstain
    return {"status": "GROUNDED", "answer": top.span, "evidence_span": top.span,
            "citations": citations, "verified": True, "engine": ENGINE}


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)


api = FastAPI(title="Synthetic PDF evidence demo", description="Offline fictional fixtures only")


@api.post("/chat")
def chat(request: ChatRequest) -> dict:
    return answer_question(request.question, load_pdf_pages())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('Usage: python pdf_demo.py "What is the refund window?"', file=sys.stderr)
        return 2
    print(json.dumps(answer_question(" ".join(argv), load_pdf_pages()), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
