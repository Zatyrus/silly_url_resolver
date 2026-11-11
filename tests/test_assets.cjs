/** JavaScript logic tests with a small fake DOM (NOT real-browser verification).
 * Run: node --test tests/test_assets.cjs. Node is optional developer tooling.
 * Browser integration remains covered separately by test_browser.py.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.join(__dirname, '../src/timed_url_caller/browser/assets');
const demoAssets = path.join(__dirname, '../src/url_caller_demo/assets');

function element() {
  return {textContent: '', hidden: true, listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; }};
}

test('wisdom button reveals the exact requested text', () => {
  const nodes = {'#clock': element(), '#wisdom-button': element(), '#wisdom': element()};
  const context = {document: {body: {dataset: {time: String(Date.UTC(2026, 6, 1, 12)), trial: ''}},
    getElementById: id => nodes['#' + id]}, performance: {now: () => 0}, Date, setInterval: () => 1};
  vm.runInNewContext(fs.readFileSync(path.join(demoAssets, 'demo.js'), 'utf8'), context);
  nodes['#wisdom-button'].listeners.click();
  assert.equal(nodes['#wisdom'].textContent, "Two plus two is four, minus one that's three; quick math.");
  assert.equal(nodes['#wisdom'].hidden, false);
});

test('clock ticks at fixed UTC+1 even on a summer date', () => {
  const nodes = {'#clock': element(), '#wisdom-button': element(), '#wisdom': element()};
  let now = 0;
  let tick;
  const context = {document: {body: {dataset: {time: String(Date.UTC(2026, 6, 1, 12)), trial: ''}},
    getElementById: id => nodes['#' + id]}, performance: {now: () => now}, Date,
    setInterval: fn => { tick = fn; return 1; }};
  vm.runInNewContext(fs.readFileSync(path.join(demoAssets, 'demo.js'), 'utf8'), context);
  assert.equal(nodes['#clock'].textContent, '13:00:00.000');
  now = 1500; tick();
  assert.equal(nodes['#clock'].textContent, '13:00:01.500');
});

function armed() {
  const nodes = {'state': element(), 'countdown': element(), 'h1': element()};
  let source;
  let navigation = [];
  let requests = [];
  class EventSource {
    constructor(url) { this.url = url; this.handlers = {}; source = this; this.closed = false; }
    addEventListener(name, fn) { this.handlers[name] = fn; }
    close() { this.closed = true; }
  }
  const context = {document: {body: {dataset: {token: 'test-token', time: String(Date.now()+1000)}},
    getElementById: id => nodes[id], querySelector: id => nodes[id]}, Date, EventSource,
    setInterval: () => 1, clearInterval: () => {},
    fetch: async (...args) => { requests.push(args); return {ok: true}; },
    window: {location: {replace: url => navigation.push(url)}}};
  vm.runInNewContext(fs.readFileSync(path.join(assets, 'ready.js'), 'utf8'), context);
  return {nodes, source, navigation, requests, context};
}

test('ready acknowledgement does not navigate or prefetch target', async () => {
  const fixture = armed();
  await fixture.source.handlers.open();
  assert.equal(fixture.requests.length, 1);
  assert.equal(fixture.requests[0][0], '/armed/test-token');
  assert.equal(fixture.requests[0][1].method, 'POST');
  assert.equal(fixture.navigation.length, 0);
  assert.equal(fixture.context.document.body.dataset.ready, 'true');
});

test('one navigation event replaces the page once and closes stream', () => {
  const fixture = armed();
  const event = {data: JSON.stringify({url: 'http://127.0.0.1:8765/#work', expires_ms: Date.now()+1000})};
  fixture.source.handlers.navigate(event);
  fixture.source.handlers.navigate(event);
  assert.deepEqual(fixture.navigation, ['http://127.0.0.1:8765/#work']);
  assert.equal(fixture.source.closed, true);
});

test('disconnect closes the stream without navigation or retry', () => {
  const fixture = armed();
  fixture.source.handlers.error();
  assert.equal(fixture.source.closed, true);
  assert.equal(fixture.navigation.length, 0);
  assert.match(fixture.nodes.state.textContent, /disconnected or cancelled/);
});

test('expired navigation signal does not visit the destination', () => {
  const fixture = armed();
  fixture.source.handlers.navigate({data: JSON.stringify({url: 'http://127.0.0.1/', expires_ms: Date.now()-1})});
  assert.equal(fixture.navigation.length, 0);
  assert.match(fixture.nodes.state.textContent, /maximum lateness/);
});

test('best-effort navigation has no browser expiry cutoff', () => {
  const fixture = armed();
  fixture.source.handlers.navigate({data: JSON.stringify({url: 'http://127.0.0.1/', expires_ms: null})});
  assert.deepEqual(fixture.navigation, ['http://127.0.0.1/']);
});

test('late readiness acknowledgement cannot overwrite disconnection', async () => {
  const fixture = armed();
  let finish;
  fixture.context.fetch = () => new Promise(resolve => { finish = resolve; });
  const opening = fixture.source.handlers.open();
  fixture.source.handlers.error();
  finish({ok: true});
  await opening;
  assert.match(fixture.nodes.state.textContent, /disconnected or cancelled/);
  assert.notEqual(fixture.context.document.body.dataset.ready, 'true');
  fixture.source.handlers.navigate({data: JSON.stringify({url: 'http://127.0.0.1/', expires_ms: null})});
  assert.equal(fixture.navigation.length, 0);
});

test('invalid signal is rejected without a destination request', () => {
  const fixture = armed();
  fixture.source.handlers.navigate({data: 'not JSON'});
  assert.equal(fixture.navigation.length, 0);
  assert.match(fixture.nodes.state.textContent, /Invalid signal/);
});
