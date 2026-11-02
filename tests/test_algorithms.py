import unittest

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
        result = suggest_words('cat', ['cut', 'cat', 'bat', 'car', 'cats', 'hat', 'cat'], 20)
        self.assertEqual(result, [
            {'word': 'cat', 'distance': 0}, {'word': 'bat', 'distance': 1},
            {'word': 'car', 'distance': 1}, {'word': 'cats', 'distance': 1},
            {'word': 'cut', 'distance': 1}])
        self.assertEqual(suggest_words('cat', []), [])
        self.assertEqual(suggest_words('cat', ['cat'], 0), [])


if __name__ == '__main__':
    unittest.main()
