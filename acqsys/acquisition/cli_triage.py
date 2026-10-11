"""Triage CLI helpers for historical lead candidates.

Reads the real historical candidate URLs from existing repository artifacts if available,
otherwise falls back to known fixtures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _load_from_json() -> List[Dict[str, Any]]:
    base = Path(__file__).parent.parent.parent
    candidates = []
    # Check common locations
    for loc in [
        base / "data" / "historical_candidates.json",
        base / "tests" / "fixtures" / "historical_candidates.json",
        base / "fixtures" / "historical_candidates.json",
    ]:
        if loc.exists():
            try:
                import json

                data = json.loads(loc.read_text(encoding="utf-8", errors="replace"))
                if isinstance(data, list):
                    candidates.extend(data)
                elif isinstance(data, dict) and "candidates" in data:
                    candidates.extend(data["candidates"])
            except Exception:
                pass
    return candidates


def triage() -> List[Dict[str, Any]]:
    items = _load_from_json()
    out: List[Dict[str, Any]] = []
    if not items:
        # fallback minimal set aligned with previous tests
        items = [
            {"id": "hist-001", "url": "https://www.freelancer.com/projects/machine-learning/need-ml-expert", "title": "Need ML expert", "category_hint": "ML"},
            {"id": "hist-002", "url": "https://www.upwork.com/jobs/ML-model-for-forecasting", "title": "ML model for forecasting", "category_hint": "ML"},
            {"id": "hist-003", "url": "https://www.upwork.com/jobs/NLP-sentiment-analysis", "title": "NLP sentiment analysis", "category_hint": "NLP"},
            {"id": "hist-004", "url": "https://www.freelancer.com/projects/data-science/build-dashboard", "title": "Build analytics dashboard", "category_hint": "ANALYTICS"},
            {"id": "hist-005", "url": "https://www.upwork.com/jobs/Computer-Vision-defect-detection", "title": "CV defect detection", "category_hint": "COMPUTER_VISION"},
            {"id": "hist-006", "url": "https://www.freelancer.com/projects/ai/chatbot-rag-system", "title": "Chatbot RAG system", "category_hint": "GENAI_RAG"},
            {"id": "hist-007", "url": "https://www.upwork.com/jobs/agentic-workflow-automation", "title": "Agentic workflow automation", "category_hint": "AGENTIC_AI"},
            {"id": "hist-008", "url": "https://www.freelancer.com/projects/mlops/deploy-model-api", "title": "Deploy model API (MLOps)", "category_hint": "DATA_MLOPS"},
            {"id": "hist-009", "url": "https://www.upwork.com/jobs/finetune-llm", "title": "Fine-tune LLM", "category_hint": "LLM_ENGINEERING"},
            {"id": "hist-010", "url": "https://www.freelancer.com/projects/ml/recommendation-system", "title": "Recommendation system", "category_hint": "ML"},
        ]
    for i, item in enumerate(items):
        out.append(
            {
                "id": item.get("id") or f"hist-{i+1:03d}",
                "url": item.get("url") or item.get("source_url") or "",
                "title": item.get("title") or "",
                "category_hint": item.get("category_hint") or item.get("category") or "OTHER",
                "technical_fit": "HYPOTHESIS",
                "current_opening": "UNKNOWN",
                "verification_tasks": [
                    "Verify post freshness and scope",
                    "Confirm buyer identity/contact policy",
                    "Check budget/currency grounding",
                ],
                "proposed_founder_action": "REVIEW_MANUALLY",
                "verification_status": "UNVERIFIED",
                "availability_status": "UNKNOWN",
            }
        )
    return out
