// Display only: Python controls the deadline. No target prefetch or retry.
const token = document.body.dataset.token;
const target = Number(document.body.dataset.time);
const state = document.getElementById('state');
const countdown = document.getElementById('countdown');
const timer = setInterval(() => {
  countdown.textContent = Math.max(0, (target - Date.now()) / 1000).toFixed(1);
}, 100);
const source = new EventSource(`/events/${token}`);
let finished = false;
source.addEventListener('open', async () => {
  try {
    const response = await fetch(`/armed/${token}`, {method: 'POST'});
    if (!response.ok) throw new Error('Readiness rejected');
    if (!finished) {
      state.textContent = 'Primed. Waiting to navigate at the scheduled time.';
      document.body.dataset.ready = 'true';
    }
  } catch {
    if (finished) return;
    finished = true;
    source.close();
    clearInterval(timer);
    state.textContent = 'Could not prepare the tab. Check the terminal and schedule a new time.';
  }
});
source.addEventListener('navigate', event => {
  if (finished) return;
  finished = true;
  source.close();
  clearInterval(timer);
  try {
    const command = JSON.parse(event.data);
    if (command.expires_ms !== null &&
        (!Number.isFinite(command.expires_ms) || Date.now() > command.expires_ms)) {
      state.textContent = 'The signal exceeded the maximum lateness. No destination visit was requested.';
      return;
    }
    window.location.replace(command.url);
  } catch {
    state.textContent = 'Invalid signal. No destination visit was requested.';
  }
});
source.addEventListener('error', () => {
  source.close();
  clearInterval(timer);
  if (!finished) {
    finished = true;
    state.textContent = 'Scheduler disconnected or cancelled. Check the terminal; an in-flight action cannot be undone.';
  }
});
