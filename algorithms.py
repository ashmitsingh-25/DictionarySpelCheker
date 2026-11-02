"""Manually implemented Trie and Levenshtein distance algorithms."""


class TrieNode:
    def __init__(self):
        self.children = {}  # Maps a character to the next TrieNode.
        self.is_end_of_word = False


class Trie:
    def __init__(self):
        self.root = TrieNode()
        self.size = 0

    def insert(self, word):
        """Insert a normalized word; return False if it already exists."""
        if not word:
            raise ValueError("A word cannot be empty.")
        node = self.root
        for character in word:
            if character not in node.children:
                node.children[character] = TrieNode()
            node = node.children[character]
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


def suggest_words(word, words, limit=5):
    """Rank dictionary candidates by edit distance, then alphabetically."""
    ranked = [(levenshtein_distance(word, candidate), candidate)
              for candidate in set(words)]
    ranked.sort()  # Tuples compare distance first, then the word.
    return [{"word": candidate, "distance": distance}
            for distance, candidate in ranked[:max(0, min(limit, 5))]]
