# CRM lead quality — offline portfolio POC

**Deterministic rule-based example, not an AI model or live CRM connector.** All sixteen sample leads are fictional with example.org addresses. Never use real customer data with this restricted synthetic-demo validator.

Python 3.11+, from this directory:

    python app.py --input synthetic_leads.csv --output demo_output
    python -m unittest discover -s tests -v

Output consists of classified_leads.csv with unmodified original fields and new decisions, review_queue.json for uncertain/bad records, and report.json. The input remains unchanged. Repeated runs give identical outputs.

Rules: normalize whitespace/case, exact email duplicate, same name/company with different email -> NEEDS_REVIEW; missing or invalid fields -> NEEDS_REVIEW. Tags use fixed keyword rules and rule_confidence is not calibrated model confidence. No external calls or messages.

**Not implemented:** Real CRM APIs, a trained model, external emails or account access. A future paid extension could add approved official CRM APIs, validated identity matching, audited human approval, controlled AI classification and deployed workflow monitoring.
