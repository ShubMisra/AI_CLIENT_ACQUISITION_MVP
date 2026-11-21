"""Run only the predeclared development questions; held-out cases are reserved."""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path

from pdf_demo import answer_question, load_pdf_pages, make_passages, retrieve, verify_citations

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "pdf_corpus" / "evaluation_questions.json"


def evaluate() -> dict:
    source = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    canonical_questions = json.dumps(source, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    cases = source["cases"]
    pages = load_pdf_pages()
    passages = make_passages(pages)
    answerable = [case for case in cases if case["expected"] is not None]
    ambiguous = [case for case in cases if case.get("reason") in {"conflicting sources", "multiple plans", "multiple service levels and conflict", "multiple upload types"}]
    unanswerable = [case for case in cases if case["expected"] is None and case not in ambiguous]
    retrieval_hits = correct_answers = ambiguous_abstentions = unanswerable_abstentions = 0
    valid_citations = total_citations = false_citations = 0
    timings = []
    started = time.perf_counter()
    for case in cases:
        tick = time.perf_counter()
        ranked = retrieve(case["question"], passages, k=3)
        result = answer_question(case["question"], pages)
        timings.append((time.perf_counter() - tick) * 1000)
        expected_ref = (case.get("document"), case.get("page"))
        if case in answerable:
            retrieval_hits += any((item.document, item.page) == expected_ref for item in ranked)
            correct_answers += (result["status"] == "GROUNDED"
                                and result["answer"].casefold() == case["expected"].casefold()
                                and {"document": expected_ref[0], "page": expected_ref[1]} in result["citations"])
        elif case in ambiguous:
            ambiguous_abstentions += result["status"] == "ABSTAIN" and not result["citations"]
        else:
            unanswerable_abstentions += result["status"] == "ABSTAIN" and not result["citations"]
        for citation in result["citations"]:
            total_citations += 1
            if verify_citations(result["evidence_span"], [citation], pages):
                valid_citations += 1
            else:
                false_citations += 1
    ordered = sorted(timings)
    return {
        "fixture": "FICTIONAL_SYNTHETIC_PDF_ONLY",
        "question_set_sha256": hashlib.sha256(canonical_questions).hexdigest(),
        "frozen_at_commit": "97c3d16e9ba4de430398693ea1f762e8b959a947",
        "question_count": len(cases),
        "unit_tests_included_in_question_count": False,
        "retrieval_recall_at_3": {"hits": retrieval_hits, "denominator": len(answerable)},
        "correct_grounded_answers": {"hits": correct_answers, "denominator": len(answerable)},
        "support_verified_citation_precision": {"valid": valid_citations, "denominator": total_citations},
        "false_citations": false_citations,
        "ambiguous_abstentions": {"hits": ambiguous_abstentions, "denominator": len(ambiguous)},
        "unanswerable_abstentions": {"hits": unanswerable_abstentions, "denominator": len(unanswerable)},
        "elapsed_ms_total": round((time.perf_counter() - started) * 1000, 2),
        "elapsed_ms_median_per_question": round(statistics.median(timings), 2),
        "elapsed_ms_p95_per_question": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 2),
        "external_provider_calls": 0,
        "external_provider_charges_usd": 0.0,
        "engineering_cost_included": False,
        "heldout_challenge_run": False,
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, sort_keys=True))
