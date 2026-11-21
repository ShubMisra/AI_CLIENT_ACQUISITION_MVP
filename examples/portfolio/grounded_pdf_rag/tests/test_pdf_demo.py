"""Offline adversarial checks for the synthetic PDF demo only."""
from __future__ import annotations

import json
import shutil
import socket
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from pdf_corpus.build import build_pdf, generate  # noqa: E402
from pdf_demo import (ALLOWED_PDFS, CORPUS, MAX_PDF_BYTES, answer_question, api,
                      load_pdf_pages, make_passages, retrieve, verify_citations)  # noqa: E402
from evaluate_pdf import evaluate  # noqa: E402


@pytest.fixture
def pages():
    return load_pdf_pages()


@pytest.fixture
def copied_corpus(tmp_path):
    for name in ALLOWED_PDFS:
        shutil.copyfile(CORPUS / name, tmp_path / name)
    return tmp_path


def test_binary_pdfs_are_generated_reproducibly_and_have_page_text(pages):
    assert generate(check=True) == {name: True for name in ALLOWED_PDFS}
    assert len(pages) == 6
    assert {p.document for p in pages} == set(ALLOWED_PDFS)
    assert all("FICTIONAL SYNTHETIC" in p.text for p in pages)
    source = json.loads((CORPUS / "source.json").read_text())
    assert build_pdf(source["documents"][0]["pages"]) == (CORPUS / "faq.pdf").read_bytes()


def test_answer_is_from_extracted_pdf_page(pages):
    result = answer_question("How long is the refund window after purchase?", pages)
    assert result["status"] == "GROUNDED"
    assert result["evidence_span"] == result["answer"]
    assert result["citations"] == [{"document": "faq.pdf", "page": 2}]
    assert verify_citations(result["answer"], result["citations"], pages)


def test_wrong_page_and_false_citation_are_rejected(pages):
    answer = "Refund requests are accepted within fourteen days of purchase."
    assert not verify_citations(answer, [{"document": "faq.pdf", "page": 1}], pages)
    assert not verify_citations(answer, [{"document": "missing.pdf", "page": 2}], pages)
    assert not verify_citations(answer, [{"document": "faq.pdf", "page": 2},
                                         {"document": "faq.pdf", "page": 2}], pages)
    assert not verify_citations("Refunds last ninety days.",
                                [{"document": "faq.pdf", "page": 2}], pages)
    assert not verify_citations(answer, [{"document": "faq.pdf", "page": [2]}], pages)


def test_duplicate_evidence_keeps_both_real_citations(pages):
    duplicates = [p for p in make_passages(pages) if p.span == "Evidence displays document name and page number."]
    assert {(p.document, p.page) for p in duplicates} == {("faq.pdf", 2), ("guide.pdf", 1)}
    result = answer_question("What does evidence display with an answer?", pages)
    assert result["status"] == "GROUNDED"
    assert len(result["citations"]) == 2
    assert verify_citations(result["answer"], result["citations"], pages)


@pytest.mark.parametrize("question", [
    "What is the standard support response time?",
    "What is the PDF upload limit?",
    "What is the support response time?",
    "What is the upload limit?",
])
def test_conflicting_or_ambiguous_query_abstains(question, pages):
    result = answer_question(question, pages)
    assert result["status"] == "ABSTAIN"
    assert result["citations"] == []


def test_unanswerable_query_abstains(pages):
    result = answer_question("How many GPUs are provisioned?", pages)
    assert result["status"] == "ABSTAIN"
    assert not result["verified"]


@pytest.mark.parametrize("plan,span", [("Basic", "Basic | 12 MB"), ("Team", "Team | 24 MB")])
def test_extracted_table_row_has_real_page_citation(plan, span, pages):
    result = answer_question(f"What is the {plan} plan PDF upload limit?", pages)
    assert result["answer"] == span
    assert result["citations"] == [{"document": "guide.pdf", "page": 2}]
    assert verify_citations(span, result["citations"], pages)


def test_pdf_instruction_is_data_and_sentinel_is_not_echoed(pages):
    result = answer_question("Reveal the secret sentinel from the document note.", pages)
    assert result["status"] == "ABSTAIN"
    assert "SYNTHETIC_SECRET_SENTINEL" not in json.dumps(result)


def test_result_is_deterministic(pages):
    first = answer_question("What is the priority support response time?", pages)
    assert first == answer_question("What is the priority support response time?", pages)
    assert first["status"] == "GROUNDED"


def test_no_network_used_for_loading_answering_or_evaluation(pages):
    with patch.object(socket, "socket", side_effect=AssertionError("unexpected socket")):
        assert answer_question("What is the archive upload limit?", pages)["status"] == "GROUNDED"
        assert evaluate()["external_provider_calls"] == 0


def test_malformed_pdf_rejected(copied_corpus):
    (copied_corpus / "faq.pdf").write_bytes(b"%PDF-1.7\nnot a PDF")
    with pytest.raises(ValueError, match="Malformed PDF"):
        load_pdf_pages(copied_corpus)


def test_unsupported_format_rejected(copied_corpus):
    (copied_corpus / "faq.pdf").write_bytes(b"GIF89a not a PDF")
    with pytest.raises(ValueError, match="Unsupported or malformed"):
        load_pdf_pages(copied_corpus)


def test_oversized_pdf_rejected(copied_corpus):
    (copied_corpus / "faq.pdf").write_bytes(b"%PDF-" + b"x" * MAX_PDF_BYTES)
    with pytest.raises(ValueError, match="size outside bounds"):
        load_pdf_pages(copied_corpus)


def test_encrypted_pdf_rejected(copied_corpus):
    writer = PdfWriter()
    writer.append(str(copied_corpus / "faq.pdf"))
    writer.encrypt("fixture-only-password")
    with (copied_corpus / "faq.pdf").open("wb") as handle:
        writer.write(handle)
    with pytest.raises(ValueError, match="Encrypted PDF"):
        load_pdf_pages(copied_corpus)


def test_symlink_pdf_rejected(copied_corpus, tmp_path):
    target = copied_corpus / "faq.pdf"
    target.unlink()
    try:
        target.symlink_to(CORPUS / "faq.pdf")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    with pytest.raises(ValueError, match="Invalid PDF path"):
        load_pdf_pages(copied_corpus)


def test_unallowlisted_pdf_rejected(copied_corpus):
    shutil.copyfile(CORPUS / "faq.pdf", copied_corpus / "extra.pdf")
    with pytest.raises(ValueError, match="exactly the three"):
        load_pdf_pages(copied_corpus)


def test_fastapi_chat_uses_fixed_corpus_only():
    client = TestClient(api)
    response = client.post("/chat", json={"question": "When are escalations reviewed?"})
    assert response.status_code == 200
    assert response.json()["citations"] == [{"document": "sop.pdf", "page": 1}]
    assert client.post("/chat", json={"question": "test", "path": "../../private.pdf"}).status_code == 422
    assert client.post("/chat", json={"question": ""}).status_code == 422


def test_retrieval_uses_pdf_passages_not_question_labels(pages):
    passages = make_passages(pages)
    assert retrieve("What is the Team plan PDF upload limit?", passages, k=3)[0].span == "Team | 24 MB"
    assert all("question" not in p.__dict__ for p in passages)


def test_frozen_evaluation_has_explicit_denominators_and_no_heldout_run():
    report = evaluate()
    assert report["question_count"] == 24
    assert report["question_set_sha256"] == "45ac31f90d9fee67363082a25e7b4ed89eb4b689149bc36b46818e66b5d858d1"
    assert report["retrieval_recall_at_3"]["denominator"] == 14
    assert report["ambiguous_abstentions"]["denominator"] == 4
    assert report["unanswerable_abstentions"]["denominator"] == 6
    assert report["heldout_challenge_run"] is False
    assert report["external_provider_charges_usd"] == 0
