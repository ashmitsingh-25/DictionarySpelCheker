"""Manually implemented Trie and Levenshtein distance algorithms."""

from bisect import insort
from functools import lru_cache
from types import MappingProxyType

EMPTY_CHILDREN = MappingProxyType({})


class TrieNode:
    # Slots avoid a per-node attribute dictionary in the large vocabulary Trie.
    __slots__ = ("children", "is_end_of_word", "min_length", "max_length", "letters")

    def __init__(self):
        # Leaf nodes share an immutable empty map instead of allocating a dict.
        self.children = EMPTY_CHILDREN
        self.min_length = 51
        self.max_length = 0
        self.letters = 0
        self.is_end_of_word = False


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.size = 0

    def insert(self, word):
        """Insert a normalized word; return False if it already exists."""
        if not word:
            raise ValueError("A word cannot be empty.")
        suffix_masks = [0] * (len(word) + 1)
        for index in range(len(word) - 1, -1, -1):
            suffix_masks[index] = suffix_masks[index + 1] | (1 << (ord(word[index]) - 97))
        node = self.root
        node.letters |= suffix_masks[0]
        length = len(word)
        node.min_length = min(node.min_length, length)
        node.max_length = max(node.max_length, length)
        for index, character in enumerate(word):
            if not node.children:
                node.children = {}
            if character not in node.children:
                node.children[character] = TrieNode()
            node = node.children[character]
            node.letters |= suffix_masks[index + 1]
            node.min_length = min(node.min_length, length)
            node.max_length = max(node.max_length, length)
        if node.is_end_of_word:
            return False
        node.is_end_of_word = True
        self.size += 1
        return True

    def search(self, word):
        node = self.root
        for character in word:
            if character not in node.children:
                return False
            node = node.children[character]
        return node.is_end_of_word

    def autocomplete(self, prefix, limit=10):
        """Walk to the prefix, then collect words in alphabetical order."""
        if limit <= 0:
            return []
        node = self.root
        for character in prefix:
            if character not in node.children:
                return []
            node = node.children[character]

        results = []

        def collect(current, word):
            if len(results) >= limit:
                return
            if current.is_end_of_word:
                results.append(word)
            for character in sorted(current.children):
                if len(results) >= limit:
                    break
                collect(current.children[character], word + character)

        collect(node, prefix)
        return results


def levenshtein_distance(first, second):
    """Minimum insertions, deletions, and substitutions using two DP rows."""
    previous = list(range(len(second) + 1))
    for row, first_character in enumerate(first, start=1):
        current = [row]
        for column, second_character in enumerate(second, start=1):
            insertion = current[column - 1] + 1
            deletion = previous[column] + 1
            substitution = previous[column - 1] + (first_character != second_character)
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def suggest_words(word, trie, limit=5):
    """Exact top-k branch-and-bound search using Levenshtein DP rows.

    The current fifth-best candidate is an upper bound, never a fixed cutoff.
    Subtree lower bounds use the DP row, terminal lengths and available letters.
    Alphabetical ties are considered before a branch is safely discarded.
    """
    limit = min(5, max(0, limit), trie.size)
    if not limit:
        return []
    query_length = len(word)
    # Seed an upper bound from words near the longest matching prefix. These
    # seeds only affect traversal speed; every potentially better branch is searched.
    prefix = word
    seeds = trie.autocomplete(prefix, limit)
    while len(seeds) < limit and prefix:
        prefix = prefix[:-1]
        seeds = trie.autocomplete(prefix, limit)
    best = sorted((levenshtein_distance(word, candidate), candidate) for candidate in seeds)
    query_bits = [1 << (ord(character) - 97) for character in word]

    @lru_cache(maxsize=1024)
    def missing_suffixes(mask):
        # A query letter absent from every descendant requires an edit.
        counts = [0] * (query_length + 1)
        for index in range(query_length - 1, -1, -1):
            counts[index] = counts[index + 1] + (not (mask & query_bits[index]))
        return counts

    def cannot_improve(bound, prefix):
        return bound > best[-1][0] or (bound == best[-1][0] and prefix >= best[-1][1])

    def visit(node, prefix, previous):
        branches = []
        for character, child in node.children.items():
            candidate = prefix + character
            depth = len(candidate)
            length_bound = max(0, child.min_length - query_length,
                               query_length - child.max_length)
            if cannot_improve(length_bound, candidate):
                continue
            row = [depth]
            for column, query_character in enumerate(word, 1):
                row.append(min(row[-1] + 1, previous[column] + 1,
                               previous[column - 1] + (character != query_character)))
            missing = missing_suffixes(child.letters)
            lower_bound = query_length + child.max_length
            for column, value in enumerate(row):
                remaining = query_length - column
                adjustment = max(missing[column], child.min_length - depth - remaining,
                                 remaining - (child.max_length - depth))
                lower_bound = min(lower_bound, value + adjustment)
            if cannot_improve(lower_bound, candidate):
                continue
            if child.is_end_of_word:
                pair = (row[-1], candidate)
                if pair < best[-1] and pair not in best:
                    insort(best, pair)
                    best.pop()
            if child.children:
                branches.append((lower_bound, candidate, child, row))
        # Only siblings (at most 26) are sorted, not the dictionary.
        branches.sort(key=lambda branch: (branch[0], branch[1]))
        for bound, candidate, child, row in branches:
            if not cannot_improve(bound, candidate):
                visit(child, candidate, row)

    visit(trie.root, '', list(range(query_length + 1)))
    return [{'word': candidate, 'distance': distance} for distance, candidate in best]
