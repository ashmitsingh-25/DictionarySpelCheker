import unittest
import itertools
import random

from algorithms import Trie, levenshtein_distance, suggest_words


class TrieTests(unittest.TestCase):
    def setUp(self):
        self.trie = Trie()
        for word in ['apple', 'app', 'apply', 'banana', 'bat']:
            self.trie.insert(word)

    def test_exact_search_distinguishes_prefix(self):
        self.assertTrue(self.trie.search('app'))
        self.assertTrue(self.trie.search('apple'))
        self.assertFalse(self.trie.search('ap'))
        self.assertFalse(self.trie.search('apples'))
        self.assertFalse(self.trie.search(''))

    def test_duplicate_does_not_increase_size(self):
        self.assertFalse(self.trie.insert('apple'))
        self.assertEqual(self.trie.size, 5)
        with self.assertRaises(ValueError):
            self.trie.insert('')

    def test_autocomplete_is_sorted_and_limited(self):
        self.assertEqual(self.trie.autocomplete('app'), ['app', 'apple', 'apply'])
        self.assertEqual(self.trie.autocomplete('app', 2), ['app', 'apple'])
        self.assertEqual(self.trie.autocomplete('z'), [])
        self.assertEqual(self.trie.autocomplete('', 1), ['app'])
        self.assertEqual(self.trie.autocomplete('app', 0), [])


class DistanceTests(unittest.TestCase):
    def assert_matches_reference(self, words, queries):
        trie = Trie()
        for word in words:
            trie.insert(word)
        for query in queries:
            for limit in [1, 3, 5, 20]:
                expected = [{'word': word, 'distance': distance} for distance, word in
                            sorted((levenshtein_distance(query, word), word)
                                   for word in set(words))[:min(limit, 5)]]
                with self.subTest(query=query, limit=limit):
                    self.assertEqual(suggest_words(query, trie, limit), expected)

    def test_exact_search_against_exhaustive_reference(self):
        words = [''.join(chars) for length in range(1, 5)
                 for chars in itertools.product('ab', repeat=length)]
        queries = [''.join(chars) for length in range(6)
                   for chars in itertools.product('ab', repeat=length)]
        self.assert_matches_reference(words, queries + ['zzzzzzzz', 'x' * 50])

    def test_random_dictionaries_against_brute_force(self):
        rng = random.Random(2026)
        for _ in range(30):
            words = [''.join(rng.choices('abcdxyz', k=rng.randint(1, 12)))
                     for _ in range(rng.randint(1, 60))]
            rng.shuffle(words)  # Correctness must not depend on insertion order.
            queries = [''.join(rng.choices('abcdxyz', k=rng.randint(1, 15)))
                       for _ in range(10)]
            self.assert_matches_reference(words, queries)

    def test_distant_matches_and_final_distance_ties(self):
        self.assert_matches_reference(['zzzz', 'yyyy', 'xxxx', 'wwww', 'vvvv', 'uuuu'],
                                      ['aaaaaaaa', '', 'u'])

    def test_known_distances_and_symmetry(self):
        cases = [('', '', 0), ('', 'cat', 3), ('cat', 'cat', 0),
                 ('cat', 'cats', 1), ('cat', 'cut', 1),
                 ('kitten', 'sitting', 3), ('flaw', 'lawn', 2),
                 ('ab', 'ba', 2)]  # Transposition is not a single Levenshtein edit.
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                self.assertEqual(levenshtein_distance(first, second), expected)
                self.assertEqual(levenshtein_distance(second, first), expected)

    def test_rank_distance_then_alphabetical_and_cap_five(self):
        trie = Trie()
        for word in ['cut', 'cat', 'bat', 'car', 'cats', 'hat', 'cat']:
            trie.insert(word)
        result = suggest_words('cat', trie, 20)
        self.assertEqual(result, [
            {'word': 'cat', 'distance': 0}, {'word': 'bat', 'distance': 1},
            {'word': 'car', 'distance': 1}, {'word': 'cats', 'distance': 1},
            {'word': 'cut', 'distance': 1}])
        self.assertEqual(suggest_words('cat', Trie()), [])
        self.assertEqual(suggest_words('cat', trie, 0), [])


if __name__ == '__main__':
    unittest.main()
