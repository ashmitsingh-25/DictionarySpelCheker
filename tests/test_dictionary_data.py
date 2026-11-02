"""Check the bundled snapshot, broad examples, and startup-only loading."""

import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from app import app, BASE_DIR


class BundledDictionaryTests(unittest.TestCase):
    def test_pinned_word_list_integrity_and_coverage(self):
        raw = (BASE_DIR / 'dictionary.txt').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '1198a3786bed510b4f8127f73a74c38596088a220d318d962e689dc6f0792599')
        words = raw.decode('utf-8').splitlines()
        self.assertEqual(len(words), 370105)
        self.assertEqual(words, sorted(set(words)))
        self.assertEqual(app.extensions['dictionary'].trie.size, len(words))
        for word in ['apple', 'epistemology', 'syzygy', 'photosynthesis',
                     'thermodynamics', 'endocrinology', 'running', 'ran', 'universities']:
            self.assertTrue(app.extensions['dictionary'].trie.search(word), word)

    def test_local_requests_do_not_reload_or_download_dictionary(self):
        client = app.test_client()
        with patch.object(Path, 'open', side_effect=AssertionError('Unexpected file read')):
            with patch.object(app.extensions['definitions'], 'lookup',
                              side_effect=AssertionError('Unexpected online lookup')):
                self.assertTrue(client.get('/api/search?word=photosynthesis').json['found'])
                self.assertEqual(client.get('/api/autocomplete?prefix=photo').status_code, 200)
                result = client.get('/api/suggestions?word=dictionry')
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json['suggestions'][0], {'word': 'dictionary', 'distance': 1})
