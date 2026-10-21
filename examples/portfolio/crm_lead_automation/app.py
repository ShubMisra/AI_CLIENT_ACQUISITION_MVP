"""Deterministic offline CRM lead-quality work sample. No LLM, network or emails sent."""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import Counter
from pathlib import Path

EMAIL = re.compile(r'^[a-z0-9][a-z0-9._+\-]*@example\.org$')
CATEGORIES = (
    ('RAG / NLP', ('rag', 'chatbot', 'document ocr', 'llm')),
    ('Data Engineering', ('etl', 'sql', 'data migration', 'dashboard')),
    ('ML / Analytics', ('forecast', 'predict')),
    ('Automation / API', ('automation', 'api integration', 'workflow')),
)
FIELDS = ('lead_id', 'name', 'company', 'email', 'interest')

def norm(value: str) -> str:
    return ' '.join(value.strip().casefold().split())

def category(interest: str) -> str:
    term = norm(interest)
    return next((label for label, terms in CATEGORIES if any(t in term for t in terms)), 'Unclassified')

def parse_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text, newline=''))
    if reader.fieldnames != list(FIELDS):
        raise ValueError('CSV header does not match the public fixture schema')
    rows = list(reader)
    if not rows or len(rows) > 5000 or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError('Invalid or empty source rows')
    if len({norm(r['lead_id']) for r in rows}) != len(rows):
        raise ValueError('Duplicate lead_id values in source')
    return rows

def process(rows: list[dict]) -> tuple[list[dict], dict]:
    emails: dict[str, str] = {}
    identities: dict[tuple[str, str], str] = {}
    decisions: list[dict] = []
    for row in rows:
        name, company, email = norm(row['name']), norm(row['company']), norm(row['email'])
        valid_email = bool(EMAIL.fullmatch(email))
        key = (name, company)
        status, reason, confidence = 'VALID', 'Required fields and synthetic email valid', '1.00'
        if not norm(row['lead_id']) or not name or not company or not valid_email:
            status, reason, confidence = 'NEEDS_REVIEW', 'Missing required name/company or invalid/synthetic email', '0.00'
        elif email in emails:
            status, reason, confidence = 'EXACT_DUPLICATE', 'Exact normalized email matches '+emails[email], '1.00'
        elif key in identities:
            status, reason, confidence = 'NEEDS_REVIEW', 'Name and company match '+identities[key]+' but email differs', '0.50'
        if status == 'VALID':
            emails[email] = row['lead_id'].strip()
            identities[key] = row['lead_id'].strip()
        item = dict(row)
        item.update({'decision':status, 'reason':reason, 'rule_confidence':confidence, 'category':category(row['interest'])})
        decisions.append(item)
    counts = Counter(row['decision'] for row in decisions)
    report = {'source_rows':len(rows),'valid':counts['VALID'],'needs_review':counts['NEEDS_REVIEW'],
              'exact_duplicates':counts['EXACT_DUPLICATE'],'decision_engine':'DETERMINISTIC_RULES_ONLY',
              'automated_contact_count':0,'model_calls':0}
    return decisions, report

def run(input_path: str | Path, output_dir: str | Path) -> dict:
    source = Path(input_path)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 512000:
        raise ValueError('Missing, symlinked or oversized CSV')
    before = source.read_bytes()
    rows = parse_csv(before.decode('utf-8-sig'))
    decisions, report = process(rows)
    dest = Path(output_dir)
    if dest.resolve() == source.parent.resolve():
        raise ValueError('Outputs must be in a separate folder')
    dest.mkdir(parents=True,exist_ok=True)
    with (dest / 'classified_leads.csv').open('w',encoding='utf-8',newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(FIELDS)+['decision','reason','rule_confidence','category'])
        writer.writeheader()
        writer.writerows(decisions)
    (dest / 'review_queue.json').write_text(json.dumps([x for x in decisions if x['decision']=='NEEDS_REVIEW'],indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (dest / 'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    if source.read_bytes()!=before:
        raise RuntimeError('Source changed during run')
    return report

def main():
    parser=argparse.ArgumentParser(description='Public offline synthetic lead-quality example')
    parser.add_argument('--input', default=str(Path(__file__).parent/'synthetic_leads.csv'))
    parser.add_argument('--output', default=str(Path(__file__).parent/'demo_output'))
    args=parser.parse_args()
    print(json.dumps(run(args.input,args.output),indent=2,sort_keys=True))

if __name__=='__main__':
    main()
