// Like button. One document-level listener keeps every heart for the same song in sync.
import { h, icon } from '../dom.js';
import { api, ApiError } from '../api.js';
import { store, isLiked, setLiked, on } from '../store.js';
import { navigate, loginUrl } from '../router.js';
import { toast } from './toast.js';

function paint(btn, liked) {
  btn.classList.toggle('on', liked);
  btn.setAttribute('aria-pressed', String(liked));
  btn.replaceChildren(icon(liked ? 'heartFill' : 'heart'));
}

export function heartButton(song, cls = '') {
  const btn = h('button', {
    type: 'button',
    class: `icon-btn heart ${cls}`.trim(),
    'aria-label': `Like ${song.title}`,
    title: 'Like',
    'data-like-id': song.id,
    onclick: (e) => {
      e.stopPropagation();
      toggleLike(song);
    },
  });
  paint(btn, isLiked(song));
  return btn;
}

export async function toggleLike(song) {
  if (!store.user) {
    navigate(loginUrl());
    return;
  }
  const want = !isLiked(song);
  setLiked(song.id, want);
  try {
    await api(`/api/songs/${song.id}/like/`, { method: want ? 'POST' : 'DELETE' });
    toast(want ? 'Added to Liked Songs' : 'Removed from Liked Songs');
  } catch (err) {
    setLiked(song.id, !want);
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) navigate(loginUrl());
    else toast(err.message, { kind: 'error' });
  }
}

on('like', ({ id, liked }) => {
  for (const btn of document.querySelectorAll(`[data-like-id="${id}"]`)) paint(btn, liked);
});
