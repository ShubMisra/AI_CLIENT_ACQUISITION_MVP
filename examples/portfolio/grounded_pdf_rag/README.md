# Grounded document Q&A — offline portfolio POC

**Deterministic lexical demonstration, not LLM-based RAG.** All three .txt sources are fictional; no client data, credentials, network or paid inference.

Python 3.11+, from this directory:

    python app.py "What is the refund window?"
    python app.py "How many GPUs are provisioned?"
    python -m unittest discover -s tests -v

The loader reads only 1–32 local .txt files with explicit [page: N] headers and Q/A lines, rejects symlinks/oversized/malformed files, and deduplicates exact question/answer pairs. The answer function matches keywords and extracts a verbatim answer plus document/page citation; for unsupported questions it declines to guess.

**Limitations:** No binary PDF parsing, OCR, vector search, LLM generation, FastAPI endpoint, UI, auth or deployment. It is NOT production-grade RAG and not a client deliverable. A paid extension could add permissioned PDF/OCR ingestion, chunk metadata, embeddings, reranking, citations, evaluation and API deployment.
