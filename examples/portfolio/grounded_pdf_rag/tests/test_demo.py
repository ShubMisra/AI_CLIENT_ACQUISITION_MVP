import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import answer_question, load_passages, main

DOCS = Path(__file__).resolve().parents[1] / 'synthetic_docs'

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.passages = load_passages(DOCS)

    def test_exact_citation(self):
        r = answer_question('How long is the refund window?', self.passages)
        self.assertEqual(r['status'], 'GROUNDED')
        self.assertEqual(r['citations'], [{'document': 'faq.txt', 'page': 2}])
        self.assertIn('fourteen', r['answer'])

    def test_abstains_when_unknown(self):
        r = answer_question('How many GPUs are provisioned?', self.passages)
        self.assertEqual(r['status'], 'UNSUPPORTED')
        self.assertEqual(r['citations'], [])

    def test_abstains_on_vague_query(self):
        self.assertEqual(answer_question('refund', self.passages)['status'], 'UNSUPPORTED')

    def test_duplicate_passage_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            content = '[page: 1]\nQ: What is the refund window?\nA: Fourteen days.\n'
            (Path(tmp) / 'a.txt').write_text(content)
            (Path(tmp) / 'b.txt').write_text(content)
            self.assertEqual(len(load_passages(tmp)), 1)

    def test_empty_folder_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_passages(tmp)

    def test_malformed_document_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'bad.txt').write_text('Q: No header?\nA: yes\n')
            with self.assertRaises(ValueError):
                load_passages(tmp)

    def test_symlink_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'source.txt'
            src.write_text('[page: 1]\nQ: What is the refund window?\nA: Fourteen days.\n')
            link = Path(tmp) / 'link.txt'
            try:
                link.symlink_to(src)
            except (OSError, NotImplementedError):
                self.skipTest('Symlinks unavailable')
            with self.assertRaises(ValueError):
                load_passages(tmp)

    def test_deterministic(self):
        self.assertEqual(answer_question('support response time', self.passages), answer_question('support response time', self.passages))

    def test_no_socket_use(self):
        with patch('socket.socket', side_effect=AssertionError('unexpected network')):
            self.assertEqual(answer_question('support response time', self.passages)['status'], 'GROUNDED')

    def test_cli_output(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(['What', 'is', 'the', 'refund', 'window?']), 0)
        self.assertEqual(json.loads(out.getvalue())['status'], 'GROUNDED')

if __name__ == '__main__':
    unittest.main()
