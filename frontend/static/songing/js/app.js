// Songing frontend entry point.
import { hydrateIcons } from './dom.js';
import { api, ApiError } from './api.js';
import { refreshMe, on, setLiked } from './store.js';
import { start } from './router.js';
import { initShell } from './shell.js';
import { initPlayerBar } from './playerbar.js';
import { player } from './player.js';

/** The restored / current song may be stale (liked elsewhere, deleted, logged out). Ask the server once. */
async function refreshCurrentSong() {
  const s = player.song;
  if (!s) return;
  try {
    const fresh = await api(`/api/songs/${s.id}/`);
    setLiked(s.id, !!fresh.is_liked);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) player.removeSongId(s.id);
  }
}

async function boot() {
  hydrateIcons();
  await refreshMe();
  initShell();
  initPlayerBar();
  player.restore();
  start();
  refreshCurrentSong();
  on('auth', refreshCurrentSong);
  document.body.classList.add('ready');
}

boot().catch((err) => {
  console.error(err);
  document.getElementById('main').textContent = 'Songing could not start. Reload the page to try again.';
});
