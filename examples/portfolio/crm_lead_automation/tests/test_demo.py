import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import category, parse_csv, process, run

SOURCE=Path(__file__).resolve().parents[1]/'synthetic_leads.csv'

class CRMTests(unittest.TestCase):
    def setUp(self):
        self.original=SOURCE.read_bytes()
        self.rows=parse_csv(self.original.decode('utf-8'))

    def test_exact_email_duplicate(self):
        d,_=process(self.rows)
        self.assertEqual(next(x for x in d if x['lead_id']=='L002')['decision'],'EXACT_DUPLICATE')

    def test_name_and_company_near_match(self):
        d,_=process(self.rows)
        x=next(x for x in d if x['lead_id']=='L005')
        self.assertEqual(x['decision'],'NEEDS_REVIEW')
        self.assertIn('L004',x['reason'])

    def test_missing_email_review(self):
        d,_=process(self.rows)
        self.assertEqual(next(x for x in d if x['lead_id']=='L003')['decision'],'NEEDS_REVIEW')

    def test_invalid_email_review(self):
        d,_=process(self.rows)
        self.assertEqual(next(x for x in d if x['lead_id']=='L008')['decision'],'NEEDS_REVIEW')

    def test_missing_company_review(self):
        d,_=process(self.rows)
        self.assertEqual(next(x for x in d if x['lead_id']=='L009')['decision'],'NEEDS_REVIEW')

    def test_input_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            run(SOURCE,temp)
            self.assertEqual(SOURCE.read_bytes(),self.original)

    def test_idempotent_output(self):
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a';b=Path(temp)/'b'
            run(SOURCE,a);run(SOURCE,b)
            for n in ['classified_leads.csv','review_queue.json','report.json']:
                self.assertEqual((a/n).read_bytes(),(b/n).read_bytes())

    def test_no_network_or_send(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch('socket.socket',side_effect=AssertionError('network not allowed')):
                r=run(SOURCE,temp)
            self.assertEqual(r['automated_contact_count'],0)
            self.assertEqual(r['model_calls'],0)

    def test_invalid_schema(self):
        with self.assertRaises(ValueError):
            parse_csv('name,email\nx,y\n')

    def test_no_duplicate_ids(self):
        r=[dict(self.rows[0]),dict(self.rows[0])]
        text='\n'.join([','.join(['lead_id','name','company','email','interest'])]+[','.join(x[k] for k in ['lead_id','name','company','email','interest']) for x in r])
        with self.assertRaises(ValueError):
            parse_csv(text)

    def test_categories(self):
        self.assertEqual(category('new ETL pipeline'),'Data Engineering')
        self.assertEqual(category('new RAG chatbot'),'RAG / NLP')

    def test_report_reconciles(self):
        d,r=process(self.rows)
        self.assertEqual(r['valid']+r['needs_review']+r['exact_duplicates'],r['source_rows'])
        self.assertEqual(r['source_rows'],len(d))

if __name__=='__main__':
    unittest.main()
