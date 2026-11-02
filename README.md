# Dictionary with Spell Checker

An Advanced Data Structures mini project with a manually implemented **Trie** for
local word lookup and prefix autocomplete, and **Levenshtein edit distance** for
spelling suggestions. A Flask backend separately fetches online meanings from
Free Dictionary API. The responsive Wordwise interface uses plain HTML, CSS and JavaScript.

## Features

- Exact local word lookup, with lowercase normalization.
- Alphabetical prefix autocomplete, limited to 10 results.
- Up to five nearest local words ranked by edit distance, then alphabetically.
- Clickable suggestions that check the selected word and fetch its meaning.
- Automatic online meanings for local matches: up to three definitions, part of
  speech, example sentences and phonetic text when supplied.
- A **Look up meaning online** option for words missing from the local dictionary.
  Missing local words are not automatically declared misspelled.
- Provider source and license attribution, safe text rendering, and protection
  against older requests overwriting a newer search.
- Independent local results: spelling and autocomplete still work without internet.
- Backend support for persistent custom words. **There is no custom-word form in
  the frontend**; the former “Grow your dictionary” section has been removed.

## Technology stack

Python 3.9+, Flask 3.1.3, Jinja templates, HTML5, CSS and browser JavaScript with
`fetch`/JSON. Online requests use Python's standard-library `urllib`; caching uses
`OrderedDict`, `monotonic` and a lock. Tests use `unittest`, `unittest.mock` and
Flask's test client. No separate test packages, database, API key, Node build step,
external fonts or frontend framework are required.

`requirements.txt` lists the direct runtime dependency; pip installs Flask's
transitive dependencies. The application requires no environment variables, so
there is no `.env.example` or dotenv dependency.

## Windows setup and commands

In PowerShell, clone the repository and enter the folder:

```powershell
git clone https://github.com/ashmitsingh-25/DictionarySpelCheker.git
cd DictionarySpelCheker
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

If using the existing project folder and `.venv`, skip cloning and environment
creation. Run the install, test or start commands as needed. Activation is optional
because each command selects the virtual environment's Python explicitly.

Open **http://127.0.0.1:5000/**, using HTTP, and keep the terminal open. Stop with
**Ctrl+C**. Restart Flask after Python/template edits and refresh the browser after
frontend edits. The default server has debug mode off and binds only to localhost.

Try `app` for autocomplete, `apple` for a local match and meaning, and `aple` for
suggestions. Click the `apple` suggestion to check it and display its definition.

## Project structure

```text
DictionarySpelCheker/
├── app.py                         # Flask routes, validation, dictionary loading/persistence
├── algorithms.py                  # Manual Trie and Levenshtein implementation
├── dictionary_service.py          # Online provider, response parsing and cache
├── dictionary.txt                 # Bundled demonstration word list
├── templates/
│   └── index.html                 # Search, autocomplete, suggestions, meanings and footer
├── static/
│   ├── style.css                  # Responsive styling
│   └── script.js                  # Fetch calls, result rendering and request versioning
├── tests/
│   ├── test_algorithms.py
│   ├── test_api.py
│   └── test_dictionary_service.py
├── requirements.txt
├── .gitignore
└── README.md
```

`.venv/`, Python caches and the optional `custom_words.txt` are local files excluded
from Git. The custom file is created on the first successful backend word addition.

## Algorithms and complexity

### Trie

Each node has a character-to-child map and an `is_end_of_word` flag. Insertion
creates missing nodes along the word. Exact search follows those nodes and checks
the end flag: a prefix can exist without being a complete dictionary word. This
is a manual Trie; Python dictionaries only provide the child maps.

Autocomplete walks to the prefix node, then recursively visits sorted children.
It returns complete words in alphabetical order and stops after 10 matches. A
prefix that is itself a word is included.

### Levenshtein distance and ranking

Dynamic programming computes the minimum number of insertions, deletions and
substitutions. Each cell takes the minimum of left + 1 (insert), above + 1
(delete), and diagonal + a character mismatch cost (substitute). Only the current
and previous rows are stored. Adjacent transposition is two edits, not one.

Suggestions scan every unique local word, compute its distance, sort
`(distance, word)` tuples and return at most five. There is no distance cutoff;
these are the nearest available words, even when none is a plausible correction.
An exact match has distance zero, though the UI hides corrections for local matches.

Let L be maximum word length, P prefix length, W number of unique words, S total
stored characters, V visited autocomplete nodes, K returned words, Q query length,
and M/N the lengths of two strings passed to edit distance. Hash-map access is
expected O(1); the alphabet is fixed at 26 letters.

| Implemented operation | Time | Additional space |
| --- | --- | --- |
| Trie insert a length-L word | O(L) expected | At most O(L) new nodes |
| Trie exact search | O(L) expected | O(1) |
| Trie autocomplete | O(P + VL) upper bound | O(L² + KL), including constructed strings and results |
| Levenshtein distance | O((M+1)(N+1)); O(MN) for nonempty strings | O(N+1) |
| Suggestions over W words | O(WQL + WL log W) worst-case bound for nonempty words | O(W + L), excluding stored input words |
| Load dictionary files | O(S) expected | O(S) for loaded data, Trie and word set |

Autocomplete constructs `word + character` at each visited edge; copying these
strings costs up to O(L) per visit. Recursive frames retain partial strings,
which can occupy O(L²) along a path, beyond the O(L) stack frames. Sorted child
lists have bounded size. Suggestions sort all candidates, not just five, and
alphabetical comparisons on distance ties can cost O(L). Their word references,
ranking tuples and the endpoint's set snapshot require O(W) space. The Trie and
word set together occupy O(S) storage.

Backend custom-word addition also reads the existing custom file to handle a
missing final newline, so its file work is O(B + L) time and O(B) auxiliary space
for B existing file characters; it is not simply an O(L) Trie operation.

## Local dictionary and persistence

`dictionary.txt` contains 341 unique words assembled as a small demonstration
list for this project. It was not imported from an external dictionary dataset;
no upstream word-list source or license notice was supplied. No project license
has been assigned. This list is not comprehensive or an authoritative spelling
reference; valid English words, names and technical terms can be absent.

At startup, `app.py` reads the UTF-8 main dictionary and, if present,
`custom_words.txt`. It ignores blank lines, trims and lowercases words, validates
1–50 ASCII letters and deduplicates via the Trie/set. Invalid lines or a missing
main dictionary fail startup clearly. Paths are relative to `app.py`, not the
terminal's working directory. Edit the main list and restart to load changes.

The retained `POST /api/words` endpoint saves new words to `custom_words.txt` before
updating memory. Existing saved words continue to load and participate in lookup,
autocomplete and suggestions. Personal test entries are not distributed with this
repository. Do not delete your local custom file if you want to keep those words.

A lock coordinates requests inside one server process. It does not coordinate
multiple processes, and the text file is not transactional storage.

## Online meanings and attribution

Provider: [Free Dictionary API](https://dictionaryapi.dev/).

```text
https://api.dictionaryapi.dev/api/v2/entries/en/{word}
```

Flask validates and URL-encodes the word, contacts this fixed HTTPS URL and parses
the JSON response. Redirects are disabled. Each request has a five-second socket
timeout and a 1 MB response-size limit; the socket timeout is not a strict overall
wall-clock deadline. The server needs internet access for uncached meanings.
No provider API key is required.

The app returns at most three definitions across entries, their available parts
of speech/examples, available phonetic text, source URLs and license names/URLs.
Missing optional fields are hidden, not invented. Source/license metadata supplied
by the provider is retained and displayed, including nested attribution. Those
licenses apply to the attributed provider content; they do not assign a license
to this project's code or local word list. Audio is not played.

Successful results are cached per process for one hour, bounded to 128 entries,
with least-recently-used eviction. Expired entries are removed on access or after
a successful lookup. Failures are not cached. Restarting clears the cache, and
simultaneous cache misses may make duplicate upstream requests.

## Frontend and Flask flow

1. Flask renders `templates/index.html` at `/` and serves CSS/JavaScript from `/static/`.
2. Typing a valid prefix debounces a same-origin `/api/autocomplete` fetch by 200 ms.
   This never triggers a provider lookup.
3. Submitting a word calls `/api/search`. A local match starts a separate
   `/api/definitions` request; local status remains visible while it loads.
4. A missing local word triggers `/api/suggestions` and exposes the explicit
   online-meaning button. Looking online does not add the word locally.
5. Clicking a suggestion fills the input and submits a new check, which loads its
   meaning if it is a local match.

All browser API calls use JSON. The browser contacts Flask, not the external
provider directly. Request counters ignore stale results; definition requests
also use `AbortController`. Provider text is rendered with `textContent`, and
only HTTP(S) attribution URLs become clickable links.

## API reference

Words/prefixes are trimmed, lowercased and validated as 1–50 ASCII English letters.
Internal spaces, punctuation, numbers, accents and missing/empty input are invalid.
GET endpoints below return 200 on success; examples assume the bundled word list.

### Exact local search

`GET /api/search?word=apple`

```json
{"word":"apple","found":true}
```

`GET /api/search?word=aple` returns `{"word":"aple","found":false}`.

### Prefix autocomplete

`GET /api/autocomplete?prefix=app`

```json
{"prefix":"app","words":["apple","application","apply"]}
```

At most 10 words; an unmatched prefix returns an empty list.

### Nearest spelling suggestions

`GET /api/suggestions?word=aple`

```json
{"word":"aple","suggestions":[{"word":"apple","distance":1},{"word":"apply","distance":2},{"word":"file","distance":2},{"word":"sample","distance":2},{"word":"table","distance":2}]}
```

Custom words can change the ranking. Empty dictionaries return an empty list.

### Online definitions

`GET /api/definitions?word=apple` works for valid nonlocal words too. The response
has `word`, `definitions`, `phonetics`, `sourceUrls` and `licenses`. For example,
the following is an **illustrative mocked response**, not a guarantee of live wording:

```json
{
  "word": "apple",
  "definitions": [{"definition": "A fruit.", "partOfSpeech": "noun", "example": "I ate an apple."}],
  "phonetics": [],
  "sourceUrls": [],
  "licenses": []
}
```

Real responses include attribution and phonetics when supplied by the provider.
A no-definition response is 404:

```json
{"word":"exampleword","code":"not_found","error":"No definition found online for this word."}
```

### Add a custom word (backend only)

`POST /api/words`, `Content-Type: application/json`, body `{"word":"codex"}`:

```json
{"word":"codex","added":true}
```

New words return 201; duplicates return 200 with `added:false`. There is no
corresponding website form. To deliberately add a word from PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:5000/api/words' -ContentType 'application/json' -Body '{"word":"codex"}'
```

This modifies your local custom file. The automated tests use temporary files instead.

## Errors and troubleshooting

Errors contain an `error` message. Provider errors also include `code` and `word`.

| Status | Meaning |
| --- | --- |
| 400 | Invalid word, missing field, invalid JSON object or malformed JSON |
| 404 | No online definition found (or unknown route) |
| 413 | Request body exceeds 4 KiB |
| 415 | POST body is not JSON |
| 500 | Custom-word file could not be saved |
| 502 | Provider HTTP failure, redirect, malformed/oversized/incomplete response |
| 503 | Provider rate limit or connection failure |
| 504 | Provider lookup timeout |

Provider failures appear in the meaning panel and leave local features usable.
The online button allows another attempt. An unavailable definition does not
prove a spelling is wrong.

- **Localhost will not open:** start Flask, keep its terminal open, and visit
  `http://127.0.0.1:5000/` rather than HTTPS. Check the terminal for startup errors.
- **Port 5000 is occupied:** stop the other app or run
  `.\.venv\Scripts\python.exe -m flask --app app:create_app run --port 5001`, then
  open `http://127.0.0.1:5001/`.
- **Python or Flask is missing:** install Python with PATH support if needed, reopen
  PowerShell, create `.venv`, and install `requirements.txt` using the commands above.
- **PowerShell activation policy error:** use the explicit `.venv` Python commands;
  activation is unnecessary.
- **Missing/invalid dictionary:** restore `dictionary.txt`; correct the indicated
  line to one ASCII word, or repair your local custom file, then restart.
- **Online meanings fail:** check internet/DNS access and try later for rate limits
  or provider outages. Local spelling checks do not require provider availability.
- **Cannot save a backend custom word:** ensure the project directory/custom file
  is writable. A failed save does not update the in-memory dictionary.
- **Old UI appears:** restart Flask and hard-refresh the browser (Ctrl+F5).

## Verification

Run the offline automated suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

It covers Trie exact/prefix distinctions and duplicate insertion, known edit
distances, ranking ties and limits, Flask validation, persistence across restarts,
failed writes, provider errors/schema handling and cache behavior. Provider
responses are mocked; these tests do not verify live provider availability.
No pytest or extra test dependency is required. They do not modify real saved words.

Optional JavaScript syntax check (requires Node.js; not needed to run the app):

```powershell
node --check static/script.js
```

Separate live provider check (requires internet):

```powershell
.\.venv\Scripts\python.exe -c "from dictionary_service import DictionaryService; print(DictionaryService().lookup('apple'))"
```

For manual browser verification, type `app`, check `aple`, select its `apple`
suggestion, confirm a local match and online definition, and check that the footer
follows the meaning panel without the removed custom-word form. Inspect browser
console errors separately. Automated Python tests do not replace browser testing.

## Limitations and future improvements

- Small English-only list; single words only, maximum 50 letters. No sentence
  checking, grammar checking, stemming or multilingual support.
- Full dictionary scans and sorting for suggestions; no measured performance
  claims. Trie-based DP pruning or a bounded ranking heap could improve scale.
- No authentication, user-specific dictionaries or deletion UI. The write endpoint
  is intended for a trusted local demonstration, not an unprotected public service.
- File persistence and cache are per local installation/process. Public multi-worker
  hosting would need durable coordinated storage and suitable cache/rate-limit design.
- Online definitions depend on third-party availability and coverage. Potential
  improvements include request coalescing, richer accessibility/browser tests,
  and a broader explicitly licensed local word list.

## Local use, GitHub and deployment

Running `app.py` starts a development website on your computer. Pushing this
repository to GitHub publishes source code; it does **not** deploy Flask or create
a live public application URL. GitHub Pages cannot run this Python backend.

Public deployment is a separate task requiring a Python-capable hosting service,
a production WSGI server, HTTPS, persistent storage, and protections appropriate
for the exposed API. No public deployment URL is provided by this project.
