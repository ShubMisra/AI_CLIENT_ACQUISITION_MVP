# Public work sample: evidence-first document Q&A

**Demonstrated:** Reproducible offline Python retrieves verbatim answers from three fictional FAQ/SOP/guide documents, cites a document and page, and explicitly declines unsupported questions. Regression tests demonstrate parsing constraints and no network use.

**Not demonstrated:** PDF/OCR ingestion, embeddings, vector search, LLM answer generation, FastAPI endpoint, live deployment, client data or real client results.

**Potential paid extension:** Add production document ingestion, retrieval and reranking, access-aware citations, measured hallucination control, evaluation, API deployment, monitoring, and handover.

Run: python app.py "What is the refund window?"
