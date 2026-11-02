"""Flask API for the Dictionary with Spell Checker mini project."""

from pathlib import Path
import re

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from algorithms import Trie, suggest_words
from dictionary_service import DictionaryService, DefinitionError

BASE_DIR = Path(__file__).resolve().parent


def normalize_word(value):
    if not isinstance(value, str):
        raise ValueError("Enter a word as text.")
    word = value.strip().lower()
    if not re.fullmatch(r"[a-z]{1,50}", word, flags=re.ASCII):
        raise ValueError("Use 1–50 English letters (a–z), without spaces or punctuation.")
    return word


class Dictionary:
    def __init__(self, dictionary_path):
        self.trie = Trie()
        self.words = set()
        # A missing main dictionary is a configuration error, not an empty dictionary.
        self.load(Path(dictionary_path))

    def load(self, path):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                word = normalize_word(line)
            except ValueError as error:
                raise ValueError(f"Invalid word in {path.name}, line {line_number}: {error}") from error
            self.trie.insert(word)
            self.words.add(word)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DICTIONARY_PATH=BASE_DIR / "dictionary.txt",
    )
    if test_config:
        app.config.update(test_config)
    dictionary = Dictionary(app.config["DICTIONARY_PATH"])
    app.extensions["dictionary"] = dictionary
    definitions = DictionaryService()
    app.extensions["definitions"] = definitions

    @app.errorhandler(ValueError)
    def invalid_input(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/search")
    def search():
        word = normalize_word(request.args.get("word"))
        found = dictionary.trie.search(word)
        return jsonify(word=word, found=found)

    @app.get("/api/autocomplete")
    def autocomplete():
        prefix = normalize_word(request.args.get("prefix"))
        words = dictionary.trie.autocomplete(prefix)
        return jsonify(prefix=prefix, words=words)

    @app.get("/api/definitions")
    def get_definitions():
        word = normalize_word(request.args.get("word"))
        try:
            return jsonify(definitions.lookup(word))
        except DefinitionError as error:
            return jsonify(word=word, error=str(error), code=error.code), error.status

    @app.get("/api/suggestions")
    def suggestions():
        word = normalize_word(request.args.get("word"))
        return jsonify(word=word, suggestions=suggest_words(word, dictionary.words))

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000)
