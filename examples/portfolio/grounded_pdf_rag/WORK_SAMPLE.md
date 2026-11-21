# Synthetic PDF evidence demo — review copy

**Status:** author-built local POC; independent review and human demo inspection pending. All documents and questions are fictional test data. No buyer files, client results, external model calls, or provider charges.

**Demonstrated:** three generated binary PDFs with page text and a small table; bounded offline extraction; deterministic lexical passage retrieval; an exact extracted evidence span; document/page citation checks; explicit refusal when sources conflict or fail to answer. The original text-only baseline remains separate.

**Sample local output** for `What is the Team plan PDF upload limit?`:

```json
{"status":"GROUNDED","answer":"Team | 24 MB","evidence_span":"Team | 24 MB","citations":[{"document":"guide.pdf","page":2}],"verified":true,"engine":"OFFLINE_PDF_EXTRACTIVE_DEMO_NO_LLM"}
```

**Development evaluation:** 24 frozen fictional questions, including 14 answerable, 4 ambiguous, and 6 other unanswerable. Results and denominators are in the README and reproducible through `evaluate_pdf.py`. This is a small authored fixture, not a general accuracy estimate. Held-out independent review has not run.

**Not demonstrated:** OCR, semantic/vector retrieval, LLM generation, complex tables, secure multi-user access, deployment, or production reliability. A paid project would require permissioned customer documents, scoped requirements, retrieval and citation validation on client examples, privacy/security controls, and measured acceptance tests. This page does not assert any previous client deliverable.
