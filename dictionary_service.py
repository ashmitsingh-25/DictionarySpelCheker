"""Online meanings only; spelling algorithms stay in algorithms.py."""

from collections import OrderedDict
from copy import deepcopy
from http.client import HTTPException
import json
import logging
import re
import socket
import ssl
from threading import Lock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

PROVIDER_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


class DefinitionError(Exception):
    def __init__(self, code, message, status, upstream_status=None, detail=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.upstream_status = upstream_status
        self.detail = detail
        self.lookup_id = None


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
        if text(entry.get('word')).lower() != word:
            raise ValueError('Provider entry does not match the requested word')
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
    def __init__(self, max_size=128, ttl=3600, timeout=5, clock=monotonic, logger=None):
        self.max_size = max_size
        self.ttl = ttl
        self.timeout = timeout
        self.clock = clock
        self.cache = OrderedDict()
        self.lock = Lock()
        self.opener = build_opener(NoRedirects())
        self.logger = logger or logging.getLogger(__name__)

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

        lookup_id = uuid4().hex[:12]
        started = self.clock()
        try:
            result, upstream_status = self._fetch(word)
        except DefinitionError as error:
            error.lookup_id = lookup_id
            # No words, response bodies, URLs, headers, credentials or raw
            # exception messages: fields below are codes or sanitized metadata.
            self.logger.warning(
                'definition_lookup id=%s upstream_status=%s outcome=%s detail=%s elapsed_ms=%.1f',
                lookup_id, error.upstream_status, error.code, error.detail,
                (self.clock() - started) * 1000)
            raise
        self.logger.info('definition_lookup id=%s upstream_status=%s outcome=success elapsed_ms=%.1f',
                         lookup_id, upstream_status, (self.clock() - started) * 1000)

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

    def _fetch(self, word):
        """One request for this exact word; never substitute or follow redirects."""
        request = Request(PROVIDER_URL + quote(word, safe=""),
                          headers={"Accept": "application/json", "User-Agent": "Wordwise-MiniProject/1.0"})
        upstream_status = None
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                upstream_status = response.status
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Response too large")
            try:
                result = parse_definitions(json.loads(raw), word)
            except DefinitionError as error:
                error.upstream_status = upstream_status
                error.detail = 'empty_definitions'
                raise
            return result, upstream_status
        except HTTPError as error:
            # Retain only an allowlisted provider classification, never its body.
            detail = 'http_error'
            try:
                body = json.loads(error.read(4096))
                if isinstance(body, dict) and body.get('error_name') in (
                        'origin_bad_gateway', 'origin_unreachable', 'origin_timeout'):
                    detail = body['error_name']
            except (ValueError, OSError, HTTPException):
                pass
            finally:
                error.close()
            if error.code == 404:
                raise DefinitionError("not_found", "No definition found online for this word.", 404, error.code, detail) from error
            if error.code == 429:
                raise DefinitionError("rate_limited", "The online dictionary rate limit was reached. Please try again later.", 503, error.code, detail) from error
            if 300 <= error.code < 400:
                raise DefinitionError("redirect", "The online dictionary returned a redirect; it was not followed.", 502, error.code, 'redirect_blocked') from error
            if error.code >= 500:
                raise DefinitionError("server_error", f"The online dictionary returned a server error (HTTP {error.code}). This does not tell us whether a definition exists.", 502, error.code, detail) from error
            raise DefinitionError("provider_error", f"The online dictionary rejected the request (HTTP {error.code}).", 502, error.code, detail) from error
        except (TimeoutError, socket.timeout) as error:
            raise DefinitionError("timeout", "The meaning lookup timed out. Please try again.", 504, upstream_status, 'socket_timeout') from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise DefinitionError("timeout", "The meaning lookup timed out. Please try again.", 504, upstream_status, 'socket_timeout') from error
            if isinstance(error.reason, ssl.SSLError):
                raise DefinitionError("tls_error", "A secure connection to the online dictionary could not be verified. Please try again later.", 503, upstream_status, 'tls_failure') from error
            raise DefinitionError("connection_error", "Cannot connect to the meaning provider. Check your internet connection.", 503, upstream_status, 'connection_failure') from error
        except ssl.SSLError as error:
            raise DefinitionError("tls_error", "A secure connection to the online dictionary could not be verified. Please try again later.", 503, upstream_status, 'tls_failure') from error
        except (ValueError, UnicodeError, RecursionError, HTTPException) as error:
            raise DefinitionError("malformed_response", "The meaning provider returned an unreadable response. Please try again later.", 502, upstream_status, 'invalid_response') from error
        except OSError as error:
            raise DefinitionError("connection_error", "The connection to the meaning provider failed. Please try again.", 503, upstream_status, 'connection_failure') from error
