import json
from http.client import IncompleteRead
import unittest
from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

from dictionary_service import DictionaryService, DefinitionError, PROVIDER_URL


def entry():
    return [{"word": "apple", "phonetics": [{"text": "/apple/"}],
             "sourceUrls": ["https://example.org/apple"],
             "license": {"name": "CC BY-SA 3.0", "url": "https://example.org/license"},
             "meanings": [{"partOfSpeech": "noun", "definitions": [
                 {"definition": "A fruit.", "example": "I ate an apple."},
                 {"definition": "Second meaning."}, {"definition": "Third meaning."},
                 {"definition": "Fourth meaning."}]}]}]


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.service = DictionaryService()
        self.open = MagicMock()
        self.service.opener.open = self.open
        self.respond(entry())

    def respond(self, payload):
        self.open.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

    def assert_failure(self, code, status):
        with self.assertRaises(DefinitionError) as caught:
            self.service.lookup('apple')
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))
        self.assertEqual(len(self.service.cache), 0)

    def test_success_limit_attribution_and_fixed_url(self):
        result = self.service.lookup('apple')
        self.assertEqual(len(result['definitions']), 3)
        self.assertEqual(result['definitions'][0], {
            'partOfSpeech': 'noun', 'definition': 'A fruit.', 'example': 'I ate an apple.'})
        self.assertEqual(result['phonetics'], ['/apple/'])
        self.assertEqual(result['sourceUrls'], ['https://example.org/apple'])
        self.assertEqual(result['licenses'][0]['name'], 'CC BY-SA 3.0')
        request = self.open.call_args.args[0]
        self.assertEqual(request.full_url, PROVIDER_URL + 'apple')
        self.assertEqual(self.open.call_args.kwargs['timeout'], 5)

    def test_missing_optional_fields(self):
        self.respond([{'meanings': [{'definitions': [{'definition': 'A fruit.'}]}]}])
        result = self.service.lookup('apple')
        self.assertEqual(result['definitions'], [{'definition': 'A fruit.'}])
        self.assertEqual(result['phonetics'], [])
        self.assertEqual(result['licenses'], [])
        self.assertEqual(result['sourceUrls'], [])

    def test_not_found(self):
        self.open.side_effect = HTTPError(PROVIDER_URL, 404, 'Not found', {}, None)
        self.assert_failure('not_found', 404)

    def test_empty_definitions(self):
        for payload in [[], [{'meanings': []}]]:
            self.respond(payload)
            self.assert_failure('not_found', 404)

    def test_timeouts(self):
        for error in [TimeoutError(), URLError(TimeoutError())]:
            self.open.side_effect = error
            self.assert_failure('timeout', 504)

    def test_connection_failure(self):
        self.open.side_effect = URLError('offline')
        self.assert_failure('connection_error', 503)

    def test_rate_limit_server_error_and_redirect(self):
        for http_status, code, status in [(429, 'rate_limited', 503), (500, 'provider_error', 502),
                                           (503, 'provider_error', 502), (302, 'provider_error', 502)]:
            self.open.side_effect = HTTPError(PROVIDER_URL, http_status, 'Error', {}, None)
            self.assert_failure(code, status)

    def test_malformed_json_and_schema(self):
        for payload in [{}, [None], [{'meanings': 'bad'}],
                        [{'meanings': [{'definitions': [{'definition': 123}]}]}]]:
            self.respond(payload)
            self.assert_failure('malformed_response', 502)
        self.open.return_value.__enter__.return_value.read.return_value = b'not json'
        self.assert_failure('malformed_response', 502)

    def test_cache_hit_expiry_eviction_and_copy(self):
        now = [0]
        self.service.clock = lambda: now[0]
        self.service.ttl = 10
        self.service.max_size = 2
        result = self.service.lookup('apple')
        result['definitions'].clear()
        self.assertEqual(len(self.service.lookup('apple')['definitions']), 3)
        self.assertEqual(self.open.call_count, 1)
        self.service.lookup('cat')
        self.service.lookup('apple')  # Most recently used; evict cat next.
        self.service.lookup('dog')
        self.assertEqual(list(self.service.cache), ['apple', 'dog'])
        now[0] = 10
        self.service.lookup('apple')
        self.assertEqual(self.open.call_count, 4)
        self.assertEqual(list(self.service.cache), ['apple'])

    def test_incomplete_http_response(self):
        self.open.return_value.__enter__.return_value.read.side_effect = IncompleteRead(b'partial')
        self.assert_failure('malformed_response', 502)

    def test_invalid_word_never_calls_provider(self):
        for word in ['../apple', 'https://example.org', '', 'a' * 51, None, 'APPLE']:
            with self.assertRaises(ValueError):
                self.service.lookup(word)
        self.open.assert_not_called()
