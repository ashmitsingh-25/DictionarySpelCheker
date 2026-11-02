from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from dictionary_service import DefinitionError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        folder = Path(self.temporary.name)
        self.base = folder / 'dictionary.txt'
        self.base.write_text('apple\napp\napply\ncat\nbat\ncar\ncats\ncut\nhat\n', encoding='utf-8')
        self.config = {'TESTING': True, 'DICTIONARY_PATH': self.base}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def test_home_and_frontend_assets(self):
        for path in ['/', '/static/style.css', '/static/script.js']:
            with self.client.get(path) as response:
                self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dictionary & spell checker', self.client.get('/').data)

    def test_search_normalization_and_prefix_not_word(self):
        result = self.client.get('/api/search', query_string={'word': ' APPLE '})
        self.assertEqual(result.json, {'word': 'apple', 'found': True})
        self.assertFalse(self.client.get('/api/search?word=ap').json['found'])

    def test_autocomplete(self):
        self.assertEqual(self.client.get('/api/autocomplete?prefix=APP').json['words'],
                         ['app', 'apple', 'apply'])
        self.assertEqual(self.client.get('/api/autocomplete?prefix=xyz').json['words'], [])
        for index in range(15):
            self.app.extensions['dictionary'].trie.insert('prefix' + chr(97 + index))
        self.assertEqual(len(self.client.get('/api/autocomplete?prefix=prefix').json['words']), 10)

    def test_suggestion_ranking(self):
        result = self.client.get('/api/suggestions?word=cat')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['suggestions'], [
            {'word': 'cat', 'distance': 0}, {'word': 'bat', 'distance': 1},
            {'word': 'car', 'distance': 1}, {'word': 'cats', 'distance': 1},
            {'word': 'cut', 'distance': 1}])

    def test_suggestions_include_five_distant_matches(self):
        result = self.client.get('/api/suggestions?word=zzzzzzzzzz')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json['suggestions']), 5)
        self.assertTrue(all(item['distance'] > 2 for item in result.json['suggestions']))

    def test_invalid_query_values(self):
        for endpoint, parameter in [('search', 'word'), ('suggestions', 'word'), ('autocomplete', 'prefix')]:
            for value in ['', 'two words', 'abc123', '<script>', 'é', 'a' * 51]:
                with self.subTest(endpoint=endpoint, value=value):
                    result = self.client.get('/api/' + endpoint, query_string={parameter: value})
                    self.assertEqual(result.status_code, 400)
                    self.assertIn('error', result.json)
            self.assertEqual(self.client.get('/api/' + endpoint).status_code, 400)

    def test_missing_and_invalid_dictionary_fail_clearly(self):
        self.base.write_text('valid\nnot valid\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'line 2'):
            create_app(self.config)
        with self.assertRaises(FileNotFoundError):
            create_app({**self.config, 'DICTIONARY_PATH': self.base.parent / 'missing.txt'})

    def test_definition_route_normalizes_and_allows_nonlocal_words(self):
        service = self.app.extensions['definitions']
        with patch.object(service, 'lookup', return_value={'word': 'zebra', 'definitions': []}) as lookup:
            result = self.client.get('/api/definitions', query_string={'word': ' ZEBRA '})
            self.assertEqual(result.status_code, 200)
            lookup.assert_called_once_with('zebra')
            self.assertFalse(self.client.get('/api/search?word=zebra').json['found'])

    def test_definition_failure_leaves_local_features_working(self):
        service = self.app.extensions['definitions']
        with patch.object(service, 'lookup', side_effect=DefinitionError('timeout', 'Try later.', 504)) as lookup:
            result = self.client.get('/api/definitions?word=apple')
            self.assertEqual(result.status_code, 504)
            self.assertEqual(result.json['code'], 'timeout')
            self.assertTrue(self.client.get('/api/search?word=apple').json['found'])
            self.assertEqual(self.client.get('/api/autocomplete?prefix=app').status_code, 200)
            self.assertEqual(self.client.get('/api/suggestions?word=appl').status_code, 200)
            self.assertEqual(lookup.call_count, 1)

    def test_definition_validation_precedes_network(self):
        with patch.object(self.app.extensions['definitions'], 'lookup') as lookup:
            for word in ['', '../apple', 'two words', 'a' * 51]:
                result = self.client.get('/api/definitions', query_string={'word': word})
                self.assertEqual(result.status_code, 400)
            lookup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
