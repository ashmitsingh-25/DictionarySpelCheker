"""Online meanings only; spelling algorithms stay in algorithms.py."""

from collections import OrderedDict
from copy import deepcopy
from http.client import HTTPException
import json
import re
import socket
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROVIDER_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


class DefinitionError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.status = status


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None  # Never follow the provider to an arbitrary URL.


def text(value):
    return value.strip() if isinstance(value, str) else ""


def parse_definitions(payload, word):
    """Reduce provider entries to three definitions and retain attribution."""
    if not isinstance(payload, list):
        raise ValueError("Expected an entry list")
    definitions, phonetics, sources, licenses = [], [], [], []

    def attribution(item):
        # Attribution can occur on entries, phonetics, or individual meanings.
        if isinstance(item, dict):
            urls = item.get("sourceUrls", [])
            if isinstance(urls, list):
                for url in urls:
                    if text(url) and url not in sources:
                        sources.append(url)
            if text(item.get("sourceUrl")) and item["sourceUrl"] not in sources:
                sources.append(item["sourceUrl"])
            license_info = item.get("license")
            if isinstance(license_info, dict):
                license_info = {key: text(license_info.get(key)) for key in ("name", "url")
                                if text(license_info.get(key))}
                if license_info and license_info not in licenses:
                    licenses.append(license_info)
            for value in item.values():
                attribution(value)
        elif isinstance(item, list):
            for value in item:
                attribution(value)

    for entry in payload:
        if not isinstance(entry, dict) or not isinstance(entry.get("meanings"), list):
            raise ValueError("Invalid entry")
        attribution(entry)
        if text(entry.get("phonetic")) and entry["phonetic"] not in phonetics:
            phonetics.append(entry["phonetic"])
        for phonetic in entry.get("phonetics", []) if isinstance(entry.get("phonetics"), list) else []:
            if isinstance(phonetic, dict) and text(phonetic.get("text")) and phonetic["text"] not in phonetics:
                phonetics.append(phonetic["text"])
        for meaning in entry["meanings"]:
            if not isinstance(meaning, dict) or not isinstance(meaning.get("definitions"), list):
                raise ValueError("Invalid meaning")
            for item in meaning["definitions"]:
                if not isinstance(item, dict) or not text(item.get("definition")):
                    raise ValueError("Invalid definition")
                if len(definitions) < 3:
                    result = {"definition": item["definition"]}
                    if text(meaning.get("partOfSpeech")):
                        result["partOfSpeech"] = meaning["partOfSpeech"]
                    if text(item.get("example")):
                        result["example"] = item["example"]
                    definitions.append(result)
    if not definitions:
        raise DefinitionError("not_found", "No definition found online for this word.", 404)
    return {"word": word, "definitions": definitions, "phonetics": phonetics,
            "sourceUrls": sources, "licenses": licenses}


class DictionaryService:
    def __init__(self, max_size=128, ttl=3600, timeout=5, clock=monotonic):
        self.max_size = max_size
        self.ttl = ttl
        self.timeout = timeout
        self.clock = clock
        self.cache = OrderedDict()
        self.lock = Lock()
        self.opener = build_opener(NoRedirects())

    def lookup(self, word):
        # Validate again so this service is safe to call outside a Flask route.
        if not isinstance(word, str) or not re.fullmatch(r"[a-z]{1,50}", word, flags=re.ASCII):
            raise ValueError("Expected 1–50 lowercase English letters.")
        with self.lock:
            cached = self.cache.get(word)
            if cached and cached[0] > self.clock():
                self.cache.move_to_end(word)
                return deepcopy(cached[1])
            self.cache.pop(word, None)

        request = Request(PROVIDER_URL + quote(word, safe=""),
                          headers={"Accept": "application/json", "User-Agent": "Wordwise-MiniProject/1.0"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Response too large")
            result = parse_definitions(json.loads(raw), word)
        except HTTPError as error:
            if error.code == 404:
                raise DefinitionError("not_found", "No definition found online for this word.", 404) from error
            if error.code == 429:
                raise DefinitionError("rate_limited", "The meaning provider is busy. Please try again later.", 503) from error
            raise DefinitionError("provider_error", "The meaning provider is unavailable. Please try again later.", 502) from error
        except (TimeoutError, socket.timeout) as error:
            raise DefinitionError("timeout", "The meaning lookup timed out. Please try again.", 504) from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise DefinitionError("timeout", "The meaning lookup timed out. Please try again.", 504) from error
            raise DefinitionError("connection_error", "Cannot connect to the meaning provider. Check your internet connection.", 503) from error
        except (ValueError, UnicodeError, RecursionError, HTTPException) as error:
            raise DefinitionError("malformed_response", "The meaning provider returned an unreadable response. Please try again later.", 502) from error
        except OSError as error:
            raise DefinitionError("connection_error", "The connection to the meaning provider failed. Please try again.", 503) from error

        with self.lock:
            now = self.clock()
            for key in list(self.cache):
                if self.cache[key][0] <= now:
                    del self.cache[key]
            self.cache[word] = (now + self.ttl, deepcopy(result))
            self.cache.move_to_end(word)
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
        return result
