"""Offline lexical document-grounding demonstration; no LLM or network access."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

STOPWORDS = frozenset('a an and are can do does for from how i in is it of on or the to what when where who why with you your'.split())
PAGE = re.compile(r'^\[page:\s*(\d+)\]$', re.IGNORECASE)
Q = re.compile(r'^Q:\s*(.+)$', re.IGNORECASE)
A = re.compile(r'^A:\s*(.+)$', re.IGNORECASE)

@dataclass(frozen=True)
class Passage:
    document: str
    page: int
    question: str
    answer: str

def words(text: str) -> set[str]:
    return {w for w in re.findall(r'[a-z0-9]+', text.casefold()) if len(w) > 2 and w not in STOPWORDS}

def load_passages(folder: str | Path) -> list[Passage]:
    base = Path(folder).resolve(strict=True)
    if not base.is_dir():
        raise ValueError('Documents path must be a directory')
    paths = sorted(base.glob('*.txt'))
    if not paths or len(paths) > 32:
        raise ValueError('Provide 1 to 32 .txt files')
    out: list[Passage] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError('Symlink or oversized document not permitted')
        page = 0
        question = ''
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if match := PAGE.fullmatch(line):
                page = int(match.group(1))
                if page < 1 or page > 1000:
                    raise ValueError('Invalid page number')
                question = ''
            elif match := Q.fullmatch(line):
                if page == 0:
                    raise ValueError('Missing page header')
                question = match.group(1).strip()
            elif match := A.fullmatch(line):
                if not question:
                    raise ValueError('Answer without question')
                ans = match.group(1).strip()
                if not ans:
                    raise ValueError('Empty answer')
                key = (question.casefold(), ans.casefold())
                if key not in seen:
                    seen.add(key)
                    out.append(Passage(path.name, page, question, ans))
                question = ''
            elif line:
                raise ValueError(f'Unsupported line syntax in {path.name}')
        if question:
            raise ValueError('Question without answer')
    if not out:
        raise ValueError('No valid question-answer passages')
    return out

def answer_question(query: str, passages: list[Passage]) -> dict:
    query_words = words(query)
    if len(query_words) < 2:
        return {'status': 'UNSUPPORTED', 'answer': 'Not found in the supplied documents.', 'citations': [], 'engine': 'LEXICAL_DEMO_ONLY'}
    scored = []
    for p in passages:
        question_words = words(p.question)
        common = query_words & question_words
        score = len(common) / max(1, len(query_words))
        if len(common) >= 2 and score >= 0.5:
            scored.append((score, len(common), p))
    if not scored:
        return {'status': 'UNSUPPORTED', 'answer': 'Not found in the supplied documents.', 'citations': [], 'engine': 'LEXICAL_DEMO_ONLY'}
    scored.sort(key=lambda row: (-row[0], -row[1], row[2].document, row[2].page, row[2].question))
    p = scored[0][2]
    return {'status': 'GROUNDED', 'answer': p.answer, 'citations': [{'document': p.document, 'page': p.page}], 'engine': 'LEXICAL_DEMO_ONLY'}

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('Usage: python app.py "What is the refund window?"', file=sys.stderr)
        return 2
    result = answer_question(' '.join(argv), load_passages(Path(__file__).parent / 'synthetic_docs'))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
