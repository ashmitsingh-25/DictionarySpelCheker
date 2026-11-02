// Dependency-free mocked DOM/fetch regression tests; run with node --test.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor(tag = 'div') {
    this.tag = tag;
    this.children = [];
    this.events = {};
    this.value = '';
    this.classList = {add() {}};
  }
  set textContent(text) { this.text = text; this.children = []; }
  get textContent() { return (this.text || '') + this.children.map(child => child.textContent).join(''); }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; this.text = ''; }
  addEventListener(name, action) { this.events[name] = action; }
}

function setup(fetch) {
  const elements = new Map(['word', 'status', 'autocomplete', 'suggestions',
    'definition-status', 'definition-content', 'online-lookup', 'search-form']
    .map(id => ['#' + id, new Element()]));
  const context = vm.createContext({
    fetch, URL, AbortController, setTimeout: () => 1, clearTimeout() {},
    document: {
      querySelector: selector => elements.get(selector),
      createElement: tag => new Element(tag),
      createTextNode: text => { const element = new Element('text'); element.textContent = text; return element; }
    }
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/script.js'), 'utf8'), context);
  return elements;
}

const response = (ok, data) => ({ok, json: async () => data});
const flush = () => new Promise(resolve => setImmediate(resolve));
async function submit(elements, word) {
  elements.get('#word').value = word;
  await elements.get('#search-form').events.submit({preventDefault() {}});
  await flush();
}

test('recognised word retains spelling status with exact-word external fallback for 404 and 502', async () => {
  for (const [code, message] of [['not_found', 'No definition found online for this word.'],
    ['server_error', 'The online dictionary returned a server error (HTTP 502).']]) {
    const requests = [];
    const elements = setup(async url => {
      requests.push(url);
      return url.includes('/search?') ? response(true, {word: 'brei', found: true})
        : response(false, {code, error: message});
    });
    await submit(elements, 'brei');
    assert.match(elements.get('#status').textContent, /Spelling recognised/);
    assert.equal(elements.get('#definition-status').textContent,
      'Word recognised; definition unavailable from the online dictionary.');
    const content = elements.get('#definition-content');
    assert.equal(content.children[0].textContent, message);
    const link = content.children[1].children[0];
    assert.equal(link.href, 'https://en.wiktionary.org/w/index.php?search=brei');
    assert.equal(link.rel, 'noopener noreferrer');
    assert.deepEqual(requests, ['/api/search?word=brei', '/api/definitions?word=brei']);
    assert.equal(elements.get('#online-lookup').hidden, false);
  }
});

test('stale failed lookup cannot replace a newer successful definition', async () => {
  let finishOld;
  const elements = setup(async url => {
    const word = new URL(url, 'http://localhost').searchParams.get('word');
    if (url.includes('/search?')) return response(true, {word, found: true});
    if (word === 'brei') return new Promise(resolve => { finishOld = resolve; });
    return response(true, {word, definitions: [{definition: 'A fruit.'}],
      phonetics: [], sourceUrls: [], licenses: []});
  });
  await submit(elements, 'brei');
  await submit(elements, 'apple');
  finishOld(response(false, {error: 'HTTP 502', code: 'server_error'}));
  await flush();
  assert.equal(elements.get('#definition-status').textContent, 'Online meaning');
  assert.match(elements.get('#definition-content').textContent, /apple/);
  assert.doesNotMatch(elements.get('#definition-content').textContent, /brei|HTTP 502|Wiktionary/);
});
