// CET means a fixed UTC+1 offset here, not daylight-saving-aware Europe/Berlin.
const serverMs = Number(document.body.dataset.time);
const started = performance.now();
function tick() {
  document.getElementById('clock').textContent =
    new Date(serverMs + performance.now() - started + 3600000).toISOString().slice(11, 23);
}
tick();
setInterval(tick, 100);
document.getElementById('wisdom-button').addEventListener('click', () => {
  const wisdom = document.getElementById('wisdom');
  wisdom.textContent = "Two plus two is four, minus one that's three; quick math.";
  wisdom.hidden = false;
});
// A readiness proxy, NOT a hardware screen-paint timestamp. Each document has
// its own identifier so a late preload receipt cannot replace the reload's.
const trial = document.body.dataset.trial;
const visit = document.body.dataset.visit;
if (trial) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const navigation = performance.getEntriesByType('navigation')[0];
    const paint = performance.getEntriesByName('first-contentful-paint')[0];
    const payload = JSON.stringify({trial, visit, event: 'interactive',
      navigation_type: navigation?.type ?? null,
      dom_content_loaded_ms: navigation?.domContentLoadedEventEnd ?? null,
      first_contentful_paint_ms: paint?.startTime ?? null});
    navigator.sendBeacon('/metrics', new Blob([payload], {type: 'application/json'}));
  }));
}
