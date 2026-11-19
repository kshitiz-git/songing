// Shared app state: the logged-in user, the user's playlists, a tiny event bus, like overrides.
import { api } from './api.js';

export const store = { user: null, playlists: [] };

const bus = new EventTarget();
/** Subscribe; returns an unsubscribe function. */
export function on(name, fn) {
  const handler = (e) => fn(e.detail);
  bus.addEventListener(name, handler);
  return () => bus.removeEventListener(name, handler);
}
export const emit = (name, detail) => bus.dispatchEvent(new CustomEvent(name, { detail }));

// ---------- auth ----------
export async function refreshMe() {
  try {
    const data = await api('/api/auth/me/');
    store.user = (data && data.user) || null;
  } catch {
    store.user = null;
  }
  if (store.user) await refreshPlaylists();
  else store.playlists = [];
  return store.user;
}

export function setUser(user) {
  store.user = user || null;
  likeOverride.clear();
  if (!store.user) store.playlists = [];
  emit('auth', store.user);
}

// ---------- playlists ----------
export async function refreshPlaylists() {
  if (!store.user) {
    store.playlists = [];
    emit('playlists', null);
    return [];
  }
  try {
    const list = await api('/api/playlists/');
    store.playlists = Array.isArray(list) ? list : list && list.results ? list.results : [];
  } catch {
    /* keep what we have */
  }
  emit('playlists', null);
  return store.playlists;
}

// ---------- likes ----------
// Song objects come from many responses and go stale; this map is the freshest answer.
const likeOverride = new Map();

export const isLiked = (song) => (likeOverride.has(song.id) ? likeOverride.get(song.id) : !!song.is_liked);

export function setLiked(id, liked) {
  likeOverride.set(id, liked);
  emit('like', { id, liked });
}
