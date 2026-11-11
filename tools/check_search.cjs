/**
 * Exercise the generated documentation's actual search worker in Node.js.
 * Run: node tools/check_search.cjs (after mkdocs build --strict).
 * No network access, browser simulation or third-party Node packages are used.
 * This validates the search engine and index, not browser UI rendering.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

async function main() {
  const root = process.argv[2] ? path.resolve(process.argv[2]) : path.resolve(__dirname, '..', 'site');
  const folder = path.join(root, 'assets', 'javascripts', 'workers');
  const worker = fs.readdirSync(folder).find(name => /^search\..*\.min\.js$/.test(name));
  const data = JSON.parse(fs.readFileSync(path.join(root, 'search', 'search_index.json')));
  data.options = { suggest: true };
  let handler;
  const messages = [];
  const sandbox = {
    console,
    addEventListener: (name, callback) => { if (name === 'message') handler = callback; },
    postMessage: message => messages.push(message),
    importScripts: () => { throw new Error('Unexpected external search dependency'); }
  };
  sandbox.self = sandbox;
  vm.runInNewContext(fs.readFileSync(path.join(folder, worker), 'utf8'), sandbox);
  await handler({ data: { type: 0, data } });
  assert.equal(messages.pop().type, 1, 'Search worker failed to initialize');
  const results = {};
  for (const query of ['refresh', 'max-late-ms', 'Chromium', 'notebook', 'CET', 'Python API']) {
    await handler({ data: { type: 2, data: query } });
    const result = messages.pop();
    assert.equal(result.type, 3);
    assert.ok(result.data.items.length > 0, `No search results for ${query}`);
    results[query] = result.data.items.length;
  }
  console.log(JSON.stringify({ status: 'passed', engine: 'generated Material search worker', results }, null, 2));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
