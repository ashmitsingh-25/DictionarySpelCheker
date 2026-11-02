# Dictionary with Spell Checker

A Flask spell checker with **370,105 bundled English words**, a manually implemented
Trie, and exact Levenshtein nearest-neighbour search. Wordwise keeps local spelling
recognition separate from online meanings and preserves a responsive HTML/CSS interface.

## Features and behaviour

- Submit a word: trim/lowercase it, validate 1–50 ASCII letters, then search the Trie.
- A local match displays **“Spelling recognised”** and automatically loads meanings.
- A missing word displays **“Word not recognised. Did you mean…?”** with up to five
  globally nearest words, ordered by edit distance and then alphabetically.
- Click any suggestion to check that word and fetch its meaning.
- Prefix autocomplete uses the Trie and returns up to 10 alphabetical matches.
- Results over two edits are explicitly labelled **distant match**. Two edits is
  only a UI label boundary, never a search cutoff. Even nearby matches are not
  guaranteed corrections; this project has no context or frequency ranking.
- Definition errors stay in the meaning panel and do not change recognised spelling.
- Local lookup and corrections work offline. Only online definitions require internet.
- No custom-word addition, file writing, account system or sentence checking.

## Vocabulary: source, license and limitations

The bundled `dictionary.txt` is the entire alphabetic word list from
[dwyl/english-words](https://github.com/dwyl/english-words), pinned to revision
`20f5cc9b3f0ccc8ce45d814c532b7c2031bba31c`. There are **370,105 unique entries**,
with lengths from 1 to 31. Normalization trims/lowercases, deduplicates, sorts, and
writes LF line endings. All upstream alphabetic entries survived the 1–50 ASCII
letter validation; there is no frequency cutoff or manually selected subset.

The source includes everyday, advanced, uncommon, academic and technical words,
variant spellings, and available inflected forms. Examples include `epistemology`,
`syzygy`, `thermodynamics`, `endocrinology`, `running`, `ran`, and `universities`.
No additional inflections are generated.

This is **not every English word** and not an editorial guarantee of correctness.
Names, new terminology, accented words, apostrophes and hyphenated compounds may
be missing. Rare/archaic words, abbreviations, offensive terms and questionable
entries may be present. Alphabetical tie-breaking can put an obscure word ahead
of the intended everyday correction. For example, `aple` has several distance-one
matches alphabetically before `apple`; exact ranking deliberately does not hide them.

The upstream repository provides an Unlicense/public-domain dedication, preserved
verbatim in [data/english-words-LICENSE.md](data/english-words-LICENSE.md).
Its [original README](data/english-words-README.md) attributes historical data to
Infochimps and states that copyright remains with that source. We retain that
provenance caveat rather than asserting independently cleared rights to every
entry. [data/SOURCES.md](data/SOURCES.md) records the revision, transformation,
checksums and license review. This data license does not assign a license to the
project's code. Online definition content has separate provider attribution.

The dictionary is committed with the application. Each `create_app()` call loads
it once into its own Trie; requests reuse that Trie. No dictionary download happens
at startup or per request. Loading streams UTF-8 lines, ignores blanks, validates
entries and deduplicates through the Trie. A missing or invalid file fails startup
with a clear error. File paths resolve relative to `app.py`. Editing the bundled
list requires a restart. The old ignored local custom file is never read or written.

## Technology and project structure

Python 3.9+, Flask 3.1.3, Jinja templates, HTML5, CSS and vanilla JavaScript.
`urllib`, `json`, `unittest` and the benchmark memory probes use the Python standard
library. Flask is the only direct dependency; tests need no additional packages.
No API key, environment variables, Node build step or database is required.

```text
app.py                         Flask factory, top-level app, validation and JSON routes
algorithms.py                  Manual Trie, DP distance and exact pruned correction search
dictionary_service.py          Meaning provider, errors, attribution and expiring cache
dictionary.txt                 370,105 bundled words
data/SOURCES.md                Source revision, checksums and provenance caveat
data/english-words-LICENSE.md  Verbatim upstream license
data/english-words-README.md   Verbatim upstream provenance
data/benchmark-windows.json    Actual local benchmark results
scripts/benchmark.py           Reproducible startup/memory/suggestion measurements
templates/index.html           Search, suggestions, meaning panel and footer
static/style.css               Responsive design and distant-match styling
static/script.js               Fetch requests, safe rendering and stale-response guards
tests/test_algorithms.py       DP/Trie tests and optimized-vs-brute-force comparisons
tests/test_api.py              Flask routes, validation and provider isolation
tests/test_dictionary_data.py  Bundled snapshot integrity and startup-only loading
tests/test_dictionary_service.py  Mocked provider and cache tests
requirements.txt               Flask dependency
.gitignore                     Local environments, caches, logs and private files
```

## Windows setup

Run in PowerShell:

```powershell
git clone https://github.com/ashmitsingh-25/DictionarySpelCheker.git
cd DictionarySpelCheker
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

For an existing checkout/virtual environment, skip cloning and environment creation.
Open **http://127.0.0.1:5000/**. Keep the terminal open; Ctrl+C stops the server.
Activation is optional because the commands explicitly select `.venv` Python.
Try `photo` for autocomplete, `photosynthesis` for recognition, and `dictionry`
for a correction. Click `dictionary` to see its meaning. Try `zzzzzzzzzz` to see
distant matches rather than an empty result caused by a fixed distance cutoff.

## Algorithms and exactness

### Trie

Each node stores a child map and an end-of-word flag. Insertion creates character
nodes; exact search must reach a marked terminal node, not merely a prefix.
Autocomplete finds the prefix node, recursively visits sorted children and stops
after 10 results. `__slots__` avoids per-node attribute dictionaries and leaf nodes
share an immutable empty child map to reduce memory.

Each node also stores the minimum/maximum total word lengths among its terminals
and a bit mask of characters that can occur after that prefix. Insertion updates
these summaries. They accelerate pruning; they never replace Trie recognition.

### Levenshtein DP rows and branch-and-bound

The independent `levenshtein_distance` function implements insertion, deletion and
substitution with two DP rows. Adjacent transposition is two edits. It supplies
initial candidate distances and the brute-force test reference.

Correction search traverses Trie edges and calculates a DP row for each visited
prefix. `row[j]` is the distance between that prefix and the first j query letters.
A child's row uses insertion (left + 1), deletion (above + 1) and substitution
(diagonal + mismatch). Shared prefixes reuse the previous row.

The search retains only the best five `(distance, word)` pairs. Initial candidates
come from autocomplete near the longest matching prefix; their distances provide
an upper bound, not a heuristic exclusion. At every subtree it computes an
admissible lower bound from:

1. The DP cost at each query-prefix position.
2. The minimum length adjustment required for any terminal in the subtree.
3. The number of remaining query letters absent from all possible descendant letters.

For each DP cell, the remaining cost is at least the **maximum** of bounds 2 and 3;
adding that to the cell value and taking the minimum across cells bounds the whole
subtree. A branch is discarded only if it cannot improve the current worst retained
pair. Equal-distance branches remain eligible unless their prefix already proves
that all descendants are alphabetically too late. Thus all candidates that could
win a final-distance tie are considered. Siblings are explored by bound then prefix.

This is exact top-k branch-and-bound, not a fixed distance-2 search. It returns five
results whenever the dictionary has at least five words, even for large mistakes.
There is no full per-word edit-distance scan or complete dictionary sort per request:
only five candidates and at most 26 siblings are sorted. Exhaustive small-alphabet
and seeded randomized tests compare the full result against brute force, including
large distances, insertion-order changes, empty queries, small dictionaries and ties.

### Complexity

Let Q be query length, L maximum dictionary word length, P prefix length, S total
stored characters, N Trie nodes, V nodes visited in a request, A alphabet size (26),
K returned words (at most 5 for corrections/10 for autocomplete), R total nodes
visited by autocomplete while seeding corrections, and C the number
of cached character-mask suffix arrays (at most 1,024 per correction request).
Hash-map operations are expected O(1).

| Operation | Time | Auxiliary space / storage |
| --- | --- | --- |
| Insert length-L word | O(L) | O(L) new nodes and temporary suffix masks |
| Exact search | O(Q) | O(1) |
| Load dictionary | O(S) expected | O(N) Trie storage plus O(L) streaming/insertion workspace |
| Prefix autocomplete | O(P + VL) upper bound | O(L² + KL), including copied path strings |
| Two-string distance (M and Q) | O((M+1)(Q+1)) | O(Q+1) |
| Pruned top-k suggestions | O(V(Q + L) + Q² + RL + KQL) upper bound for fixed A/K | O(AL(Q+L) + CQ + KL) |

For fixed A and K, the dominant correction work is DP over visited nodes, O(VQ),
plus path-string construction/comparisons. Q² + RL accounts for repeated
prefix-seed autocomplete calls and KQL for seed distances. Pending sibling rows/path strings are retained along DFS depth;
the bounded per-query suffix-array cache costs O(CQ). Autocomplete's recursion
retains copied partial strings, hence its O(L²) path space. Pruning is data-dependent:
in the worst case V can approach N. No constant-time or uniformly fast correction
guarantee is made. The implementation never fully sorts W dictionary candidates.

## Local measurements and Vercel limitations

Run a fresh-process benchmark (no network and no suggestion-result cache):

```powershell
.\.venv\Scripts\python.exe scripts/benchmark.py --output data/benchmark-windows.json
```

The committed [raw report](data/benchmark-windows.json) records three sequential
runs per query, Python/CPU details, one cold module-import measurement, and process
working-set memory from Windows. Cold import includes Flask import and building
the module-level app/Trie, but excludes interpreter launch. Memory is process
working set, not Python heap allocation or Vercel memory. Suggestion timings exclude
HTTP/browser/network overhead and online definitions. No concurrency/load test was run.

Measured on Windows / Python 3.14.3: cold import **2.630 s**;
loaded working set **281.49 MiB**; peak through
all queries **290.82 MiB**. Baseline before import:
**20.93 MiB**. Three samples are not a percentile estimate.

| Query | Median suggestion time (ms) | Nearest distance |
| --- | ---: | ---: |
| `aple` | 0.790 | 1 |
| `dictionry` | 28.972 | 1 |
| `accomodation` | 37.705 | 1 |
| `photosyntheis` | 86.801 | 1 |
| `zzzzzzzzzz` | 246.811 | 6 |
| `qzxvbnmlkjhgfdsa` | 810.105 | 10 |
| `abcdefghijklmno` | 538.223 | 9 |
| `x` repeated 50 times | 555.987 | 47 |
| `pneumonoultramicroscopicsilicovolcanoconiosis` | 505.413 | 27 |

The initial threshold-repetition prototype took about 41 seconds for 50 repeated
`x` characters in an exploratory run. The final implementation uses a tightening
upper bound, letter/length bounds, slotted nodes, shared leaf maps, streamed loading
and a bounded suffix cache; the table reports the final code's measurements.

These local results **do not establish Vercel production suitability**. The sizable
Trie is rebuilt on cold starts and duplicated per worker/instance. Adversarial
queries can still visit many nodes, and concurrent CPU-heavy requests can increase
latency. Verify cold starts, memory, request duration and load on the actual Vercel
plan before relying on it. No Vercel build, deployed latency or production load
measurement is claimed here. Potential further work includes a compact Trie
representation, isolated search workers, shared result caching and request rate limits.

## Online meanings and frontend communication

[Free Dictionary API](https://dictionaryapi.dev/) supplies meanings using:

```text
https://api.dictionaryapi.dev/api/v2/entries/en/{word}
```

The browser calls same-origin Flask JSON endpoints via `fetch`. Typing debounces
local autocomplete by 200 ms; autocomplete never calls the external provider.
Submitting checks local spelling first. A recognised word starts a separate
meaning request, leaving its spelling result visible. Missing words expose an
explicit online-meaning button. Clicking a suggestion fills the input and submits
it. Request counters ignore stale results; definition requests also use
`AbortController`. Provider strings use `textContent`, not HTML interpretation.

Python validates and URL-encodes input, uses the fixed provider URL, disables
redirects, enforces a five-second socket timeout and limits responses to 1 MB.
The timeout is not a strict end-to-end deadline. Up to three definitions, available
parts of speech, examples and phonetic text are displayed. Missing optional data
is hidden. Source URLs and license metadata are retained, including nested
attribution; only HTTP(S) attribution links are clickable. Audio is not played.
Provider coverage is independent of the local list, and a missing meaning or
provider failure never invalidates recognised spelling.

Successful meanings have a per-process 128-entry LRU cache and one-hour TTL.
Failures are not cached. Concurrent misses can issue duplicate requests; restart
clears the cache. Internet is required for uncached meanings. Provider-content
licenses do not assign a license to this project's code or local list.

## API examples

All four JSON endpoints are GET requests. Input is trimmed, lowercased and limited
to 1–50 ASCII letters; punctuation, numbers, accents and internal spaces are rejected.
Examples below refer to the pinned bundled list.

- `/api/search?word=photosynthesis` returns
  `{"word":"photosynthesis","found":true}`.
- `/api/autocomplete?prefix=photosynthe` returns `prefix` and an alphabetical `words`
  array (up to 10). An unmatched prefix returns `[]`.
- `/api/suggestions?word=dictionry` returns:

```json
{"word":"dictionry","suggestions":[{"word":"dictionary","distance":1},{"word":"diction","distance":2},{"word":"dictional","distance":2},{"word":"dictions","distance":2},{"word":"fictionary","distance":2}]}
```

- `/api/definitions?word=apple` returns `word`, `definitions`, `phonetics`,
  `sourceUrls` and `licenses`. This is an **illustrative mocked shape**, not live wording:

```json
{"word":"apple","definitions":[{"definition":"A fruit.","partOfSpeech":"noun","example":"I ate an apple."}],"phonetics":[],"sourceUrls":[],"licenses":[]}
```

Optional fields are omitted; real responses retain provider attribution. Definition
lookup accepts nonlocal words too and never changes local vocabulary. There are
no dictionary mutation endpoints. `/` serves the template; `/static/` serves assets.

## Errors and troubleshooting

Errors contain `error`; provider errors also contain `word` and `code`.

| Status | Meaning |
| --- | --- |
| 400 | Invalid/missing word or prefix |
| 404 | No online definition, or unknown route |
| 502 | Provider HTTP failure, redirect, malformed/oversized/incomplete response |
| 503 | Provider rate limit or connection failure |
| 504 | Provider timeout |

- Localhost unavailable: start Flask, keep its terminal open, and use HTTP rather
  than HTTPS. Check startup errors; allow time for the full Trie to load.
- Port occupied: stop the old process, or run
  `.\.venv\Scripts\python.exe -m flask --app app:app run --port 5001` and open port 5001.
- Missing Python/Flask: install Python with PATH support, recreate `.venv`, then
  install `requirements.txt`. Explicit environment paths avoid activation-policy issues.
- Missing/invalid dictionary: restore the bundled file and restart. Integrity tests
  intentionally fail if the pinned snapshot changes without updated provenance.
- Meaning unavailable: check internet/DNS, or retry later for provider errors.
  The recognised spelling status remains visible.
- Old interface: restart Flask and hard-refresh (Ctrl+F5).

## Tests and verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover Trie search/autocomplete, exact nearest results against brute force,
bundled data integrity/coverage, startup-only loading, API validation and failure
isolation, mocked provider errors and cache behaviour. Temporary dictionary
fixtures keep tests isolated. No extra test dependencies or live network are needed.

Optional JavaScript syntax check (Node.js is not required to run the application):

```powershell
node --check static/script.js
```

Separate live meaning check (requires internet):

```powershell
.\.venv\Scripts\python.exe -c "from dictionary_service import DictionaryService; print(DictionaryService().lookup('apple'))"
```

In a browser, type `photo`, submit `dictionry`, click `dictionary`, and check both
recognition and meanings. Submit `zzzzzzzzzz` for distant labels. Python unit tests
do not replace browser interaction tests or deployed performance verification.

Verification on 2026-11-02: all 31 Python tests and the JavaScript syntax check
passed. Browser checks covered broad-prefix autocomplete, suggestion selection
followed by a live definition, distant-match labels, and a recognised word
remaining recognised after a live no-definition response. Provider unit tests
use mocks; these browser/live checks are separate. Vercel deployment and load
testing were not performed.

## Vercel, GitHub and local use

The module-level **`app = create_app()`** is preserved for Vercel entrypoint
recognition. Local startup calls `app.run(host='127.0.0.1', port=5000)` only in the
main block. Importing the module builds the Trie but does not run a development server.

Use the repository root as Vercel's Root Directory and Flask framework detection.
Keep `dictionary.txt`, `templates/`, and `static/` in the deployment source. No
startup download or API key is required. See [Vercel's Flask documentation](https://vercel.com/docs/frameworks/backend/flask).
For `FLASK_ENTRYPOINT_NOT_FOUND`, ensure the latest commit exposing `app` is deployed.
If the Git integration does not trigger a deployment, redeploy in the dashboard.
Then inspect logs and verify `/`, `/api/search?word=photosynthesis` and online meanings.

```powershell
.\.venv\Scripts\python.exe -c "from app import app; from flask import Flask; assert isinstance(app, Flask); print('Flask entrypoint OK')"
```

A GitHub push publishes code and may trigger a separately configured Vercel project;
it is not proof of deployment success. No live deployment URL or Vercel performance
claim is supplied. GitHub Pages cannot run the Flask backend. Local `app.py` uses
the development server; public hosting requires production serving, HTTPS and
appropriate access/rate controls. See the measured memory/cold-start limitations above.

## Further limitations

This is single-word, English ASCII spelling recognition, not grammar or semantic
correction. The list's breadth trades precision for coverage. Suggestions follow
edit distance/alphabetical order rather than frequency or contextual likelihood.
Future improvements could add explicitly licensed frequency data, a better-audited
vocabulary, Unicode/tokenisation support and broader browser/concurrency testing.
