const wordInput = document.querySelector('#word');
const status = document.querySelector('#status');
const autocomplete = document.querySelector('#autocomplete');
const suggestions = document.querySelector('#suggestions');
const definitionStatus = document.querySelector('#definition-status');
const definitionContent = document.querySelector('#definition-content');
const onlineLookup = document.querySelector('#online-lookup');
let definitionVersion = 0;
let definitionController;
let checkedWord = '';
let checkedRecognised = false;
let inputVersion = 0;
let checkVersion = 0;
let debounceTimer;

function validWord(value) {
  return /^[a-zA-Z]{1,50}$/.test(value.trim());
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request failed. Please try again.');
  return data;
}

function message(element, text, type = '') {
  element.textContent = text;
  element.className = type;
}

function resetDefinitions() {
  ++definitionVersion;
  definitionController?.abort();
  checkedWord = '';
  checkedRecognised = false;
  onlineLookup.hidden = true;
  onlineLookup.disabled = false;
  definitionContent.replaceChildren();
  message(definitionStatus, 'Check a local word to load its meaning automatically.');
}

function appendText(parent, tag, text, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  parent.append(element);
  return element;
}

function attributionLink(parent, label, url) {
  // Provider text is never interpreted as HTML; only HTTP(S) links are clickable.
  try {
    const parsed = new URL(url);
    if (['https:', 'http:'].includes(parsed.protocol)) {
      const link = appendText(parent, 'a', label);
      link.href = parsed.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      return;
    }
  } catch { /* Preserve non-URL attribution as plain text. */ }
  appendText(parent, 'span', label);
}

function renderDefinitions(data) {
  definitionContent.replaceChildren();
  appendText(definitionContent, 'h4', data.word);
  for (const phonetic of data.phonetics) appendText(definitionContent, 'p', phonetic, 'phonetic');
  const list = document.createElement('ol');
  definitionContent.append(list);
  for (const item of data.definitions.slice(0, 3)) {
    const row = document.createElement('li');
    if (item.partOfSpeech) appendText(row, 'strong', item.partOfSpeech);
    appendText(row, 'p', item.definition);
    if (item.example) appendText(row, 'p', `Example: ${item.example}`, 'example');
    list.append(row);
  }
  const attribution = document.createElement('div');
  attribution.className = 'attribution';
  appendText(attribution, 'p', 'Meanings provided by Free Dictionary API.');
  for (const url of data.sourceUrls) {
    const line = appendText(attribution, 'p', 'Source: ');
    attributionLink(line, url, url);
  }
  for (const license of data.licenses) {
    const line = appendText(attribution, 'p', 'License: ');
    attributionLink(line, license.name || license.url, license.url);
  }
  definitionContent.append(attribution);
}

async function loadDefinition(word, searchVersion) {
  const version = ++definitionVersion;
  definitionController?.abort();
  definitionController = new AbortController();
  onlineLookup.disabled = true;
  onlineLookup.hidden = true;
  definitionContent.replaceChildren();
  message(definitionStatus, `Loading meaning for “${word}”…`);
  try {
    const data = await api(`/api/definitions?word=${encodeURIComponent(word)}`, {
      signal: definitionController.signal
    });
    if (version !== definitionVersion || searchVersion !== checkVersion) return;
    renderDefinitions(data);
    message(definitionStatus, 'Online meaning');
  } catch (error) {
    if (version !== definitionVersion || searchVersion !== checkVersion || error.name === 'AbortError') return;
    message(definitionStatus, checkedRecognised
      ? 'Word recognised; definition unavailable from the online dictionary.'
      : 'Definition unavailable from the online dictionary.');
    appendText(definitionContent, 'p', error.message, 'hint');
    const fallback = appendText(definitionContent, 'p', '');
    attributionLink(fallback, `Search Wiktionary for “${word}” (external)`,
      `https://en.wiktionary.org/w/index.php?search=${encodeURIComponent(word)}`);
    onlineLookup.hidden = false;
  } finally {
    if (version === definitionVersion && searchVersion === checkVersion) onlineLookup.disabled = false;
  }
}

onlineLookup.addEventListener('click', () => {
  if (checkedWord) loadDefinition(checkedWord, checkVersion);
});

function showWords(container, items, emptyText) {
  container.replaceChildren();
  if (!items.length) {
    const paragraph = document.createElement('p');
    paragraph.className = 'empty';
    paragraph.textContent = emptyText;
    container.append(paragraph);
  }
  for (const item of items) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'chip';
    button.textContent = item.word;
    if (item.distance !== undefined) {
      const distance = document.createElement('small');
      distance.textContent = `${item.distance} edit${item.distance === 1 ? '' : 's'}`;
      button.append(distance);
      if (item.distance > 2) {
        button.classList.add('distant');
        button.append(document.createTextNode(' · distant match'));
      }
    }
    button.addEventListener('click', () => {
      wordInput.value = item.word;
      wordInput.dispatchEvent(new Event('input'));
      document.querySelector('#search-form').requestSubmit();
    });
    container.append(button);
  }
}

wordInput.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  const version = ++inputVersion;
  ++checkVersion;
  resetDefinitions();
  showWords(suggestions, [], 'Check a spelling to see suggestions.');
  showWords(autocomplete, [], 'Your matching words will appear here.');
  message(status, 'Ready when you are. Enter a word to begin.');
  const prefix = wordInput.value.trim();
  if (!validWord(prefix)) return;
  debounceTimer = setTimeout(async () => {
    try {
      const data = await api(`/api/autocomplete?prefix=${encodeURIComponent(prefix)}`);
      if (version === inputVersion) showWords(autocomplete, data.words.map(word => ({word})), 'No words begin with this prefix.');
    } catch (error) {
      if (version === inputVersion) showWords(autocomplete, [], `Autocomplete unavailable: ${error.message}`);
    }
  }, 200);
});

document.querySelector('#search-form').addEventListener('submit', async event => {
  event.preventDefault();
  const word = wordInput.value.trim();
  const version = ++checkVersion;
  resetDefinitions();
  if (!validWord(word)) {
    message(status, 'Please enter 1–50 English letters, without spaces or punctuation.', 'error');
    return;
  }
  message(status, 'Checking the dictionary…');
  showWords(suggestions, [], 'Finding the nearest dictionary words…');
  try {
    const query = encodeURIComponent(word);
    const result = await api(`/api/search?word=${query}`);
    if (version !== checkVersion) return;
    checkedWord = result.word;
    checkedRecognised = result.found;
    if (result.found) {
      message(status, `“${result.word}”: Spelling recognised`, 'success');
      showWords(suggestions, [], 'You have an exact match. No correction needed.');
      loadDefinition(result.word, version);
    } else {
      message(status, `“${result.word}”: Word not recognised. Did you mean…?`);
      message(definitionStatus, 'You can also look up this word’s meaning online.');
      onlineLookup.hidden = false;
      const data = await api(`/api/suggestions?word=${query}`);
      if (version !== checkVersion) return;
      showWords(suggestions, data.suggestions, 'No local suggestions are available.');
    }
  } catch (error) {
    if (version === checkVersion) {
      if (checkedWord) showWords(suggestions, [], `Suggestions unavailable: ${error.message}`);
      else message(status, `Could not check spelling: ${error.message}`, 'error');
    }
  }
});
