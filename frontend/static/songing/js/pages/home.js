import { h } from '../dom.js';
import { api } from '../api.js';
import { store } from '../store.js';
import { songCard, albumCard, artistCard, shelf } from '../ui/cards.js';
import { emptyState } from '../ui/empty.js';

export const load = (ctx) => api('/api/home/', { signal: ctx.signal });

function greeting() {
  const hr = new Date().getHours();
  const part = hr < 5 ? 'Late night' : hr < 12 ? 'Good morning' : hr < 18 ? 'Good afternoon' : 'Good evening';
  return store.user ? `${part}, ${store.user.username}` : part;
}

export function render(d, ctx) {
  ctx.setTitle('');
  const root = h('div', { class: 'home' }, h('h1', { class: 'page-title', text: greeting() }));
  const songs = (title, list, id) => list && list.length && root.append(shelf(title, list.map((s) => songCard(s, list)), { id }));

  songs('Recently played', d.recently_played, 'shelf-recent');
  songs('Made for you', d.made_for_you, 'shelf-made');
  songs('Trending now', d.trending, 'shelf-trending');
  if (d.new_releases && d.new_releases.length) root.append(shelf('New releases', d.new_releases.map(albumCard), { id: 'shelf-new' }));
  if (d.artists && d.artists.length) root.append(shelf('Artists', d.artists.map(artistCard), { id: 'shelf-artists' }));

  if (root.children.length === 1) {
    root.append(
      emptyState({
        title: 'No music here yet',
        text: store.user ? 'Upload a song and it will show up here.' : 'Log in to upload your own songs, or come back once the library has music.',
        action: store.user ? { label: 'Upload a song', href: '/upload' } : { label: 'Log in', href: '/login' },
      }),
    );
  }
  return root;
}
