"""Triage CLI helpers for 10 historical candidates."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


TRIAGE_ITEMS = [
    {
        "id": "hist-001",
        "url": "https://www.freelancer.com/projects/machine-learning/need-ml-expert",
        "title": "Need ML expert",
        "category_hint": "ML",
    },
    {
        "id": "hist-002",
        "url": "https://www.upwork.com/jobs/ML-model-for-forecasting",
        "title": "ML model for forecasting",
        "category_hint": "ML",
    },
    {
        "id": "hist-003",
        "url": "https://www.upwork.com/jobs/NLP-sentiment-analysis",
        "title": "NLP sentiment analysis",
        "category_hint": "NLP",
    },
    {
        "id": "hist-004",
        "url": "https://www.freelancer.com/projects/data-science/build-dashboard",
        "title": "Build analytics dashboard",
        "category_hint": "ANALYTICS",
    },
    {
        "id": "hist-005",
        "url": "https://www.upwork.com/jobs/Computer-Vision-defect-detection",
        "title": "CV defect detection",
        "category_hint": "COMPUTER_VISION",
    },
    {
        "id": "hist-006",
        "url": "https://www.freelancer.com/projects/ai/chatbot-rag-system",
        "title": "Chatbot RAG system",
        "category_hint": "GENAI_RAG",
    },
    {
        "id": "hist-007",
        "url": "https://www.upwork.com/jobs/agentic-workflow-automation",
        "title": "Agentic workflow automation",
        "category_hint": "AGENTIC_AI",
    },
    {
        "id": "hist-008",
        "url": "https://www.freelancer.com/projects/mlops/deploy-model-api",
        "title": "Deploy model API (MLOps)",
        "category_hint": "DATA_MLOPS",
    },
    {
        "id": "hist-009",
        "url": "https://www.upwork.com/jobs/finetune-llm",
        "title": "Fine-tune LLM",
        "category_hint": "LLM_ENGINEERING",
    },
    {
        "id": "hist-010",
        "url": "https://www.freelancer.com/projects/ml/recommendation-system",
        "title": "Recommendation system",
        "category_hint": "ML",
    },
]


def triage() -> List[Dict[str, Any]]:
    out = []
    for item in TRIAGE_ITEMS:
        out.append(
            {
                "id": item["id"],
                "url": item["url"],
                "title": item["title"],
                "category_hint": item["category_hint"],
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
