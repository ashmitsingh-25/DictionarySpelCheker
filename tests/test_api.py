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
        self.custom = folder / 'custom_words.txt'
        self.base.write_text('apple\napp\napply\ncat\nbat\ncar\ncats\ncut\nhat\n', encoding='utf-8')
        self.config = {'TESTING': True, 'DICTIONARY_PATH': self.base,
                       'CUSTOM_WORDS_PATH': self.custom}
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

    def test_add_duplicate_and_restart_persistence(self):
        original = self.base.read_text(encoding='utf-8')
        response = self.client.post('/api/words', json={'word': ' Zebra '})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json, {'word': 'zebra', 'added': True})
        duplicate = self.client.post('/api/words', json={'word': 'ZEBRA'})
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.json['added'])
        self.assertEqual(self.custom.read_text(encoding='utf-8'), 'zebra\n')
        restarted = create_app(self.config).test_client()
        self.assertTrue(restarted.get('/api/search?word=zebra').json['found'])
        self.assertEqual(restarted.get('/api/autocomplete?prefix=zeb').json['words'], ['zebra'])
        self.assertEqual(restarted.get('/api/suggestions?word=zebre').json['suggestions'][0],
                         {'word': 'zebra', 'distance': 1})
        self.assertEqual(self.base.read_text(encoding='utf-8'), original)

    def test_custom_file_without_trailing_newline(self):
        self.custom.write_text('zebra', encoding='utf-8')
        client = create_app(self.config).test_client()
        self.assertEqual(client.post('/api/words', json={'word': 'zoo'}).status_code, 201)
        restarted = create_app(self.config).test_client()
        self.assertTrue(restarted.get('/api/search?word=zebra').json['found'])
        self.assertTrue(restarted.get('/api/search?word=zoo').json['found'])

    def test_invalid_query_values(self):
        for endpoint, parameter in [('search', 'word'), ('suggestions', 'word'), ('autocomplete', 'prefix')]:
            for value in ['', 'two words', 'abc123', '<script>', 'é', 'a' * 51]:
                with self.subTest(endpoint=endpoint, value=value):
                    result = self.client.get('/api/' + endpoint, query_string={parameter: value})
                    self.assertEqual(result.status_code, 400)
                    self.assertIn('error', result.json)
            self.assertEqual(self.client.get('/api/' + endpoint).status_code, 400)

    def test_invalid_json_and_word_values(self):
        for body in [{}, [], {'word': None}, {'word': 12}, {'word': 'two words'}, {'word': 'x' * 51}]:
            self.assertEqual(self.client.post('/api/words', json=body).status_code, 400)
        malformed = self.client.post('/api/words', data='{', content_type='application/json')
        self.assertEqual(malformed.status_code, 400)
        self.assertIn('error', malformed.json)
        wrong_type = self.client.post('/api/words', data='hello')
        self.assertEqual(wrong_type.status_code, 415)
        self.assertIn('error', wrong_type.json)
        too_large = self.client.post('/api/words', json={'word': 'a' * 5000})
        self.assertEqual(too_large.status_code, 413)
        self.assertFalse(self.custom.exists())

    def test_failed_save_does_not_modify_dictionary(self):
        with patch('pathlib.Path.open', side_effect=PermissionError('read only')):
            with self.assertLogs(self.app.logger, level='ERROR'):
                response = self.client.post('/api/words', json={'word': 'zebra'})
        self.assertEqual(response.status_code, 500)
        self.assertIn('Could not save', response.json['error'])
        self.assertFalse(self.client.get('/api/search?word=zebra').json['found'])

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
