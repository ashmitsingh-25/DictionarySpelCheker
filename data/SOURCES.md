# Bundled English vocabulary

- Project: [dwyl/english-words](https://github.com/dwyl/english-words)
- Revision: `20f5cc9b3f0ccc8ce45d814c532b7c2031bba31c`
- File: [`words_alpha.txt`](https://github.com/dwyl/english-words/blob/20f5cc9b3f0ccc8ce45d814c532b7c2031bba31c/words_alpha.txt)
- Retrieved: 2026-11-02
- Upstream entries: **370,105**; bundled unique entries: **370,105**.
- Length range: 1–31 ASCII letters. No source entry was removed by normalization.
- Original download SHA-256: `3ed0c94610d8bcf7c11bbb49c56aa49c7234d32b66824df91f554169e572da48`
- Bundled `dictionary.txt` SHA-256: `1198a3786bed510b4f8127f73a74c38596088a220d318d962e689dc6f0792599`

Transformation: decode UTF-8, split lines, trim, lowercase, retain alphabetic ASCII
words of at most 50 characters, deduplicate, sort alphabetically, and write one
word per line with LF endings and a final newline. This imports the complete
alphabetic file, not a hand-selected or frequency-limited subset. No inflections
are generated: the available inflected forms come from the source itself.
The list is committed to the repository; app startup does not download anything.

## License and provenance review

The upstream repository includes the Unlicense/public-domain dedication in
[english-words-LICENSE.md](english-words-LICENSE.md), preserved verbatim here.
Its original [README](english-words-README.md), also preserved verbatim, traces
the list to an Infochimps dataset and explicitly states that copyright still
belongs to that source. That upstream statement is retained rather than claiming
independently verified rights to all entries. The repository's license declaration
and its historical provenance statement are distinct; this project does not
resolve that ambiguity or assign this license to its own code.

## Coverage and quality

The broad list includes everyday, uncommon, archaic, academic and technical
vocabulary, variant spellings and many inflected forms. It is not every English
word, is not a current linguistic authority, and is not a frequency-ranked or
editorially verified spelling dictionary. Names, recent coinages, compounds with
punctuation, apostrophes and accented words may be absent. Some abbreviations,
questionable spellings, offensive terms and extremely rare forms can be present.
Recognised means membership in this list, not proof of contextually correct usage.
The online meaning provider has separate coverage and separate content licenses.
