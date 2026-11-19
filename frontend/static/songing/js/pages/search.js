import { h, icon, colorsFromText } from '../dom.js';
import { api } from '../api.js';
import { songList } from '../ui/songlist.js';
import { albumCard, artistCard, playlistCard, shelf } from '../ui/cards.js';
import { emptyState } from '../ui/empty.js';

export async function load(ctx) {
  const q = (ctx.query.get('q') || '').trim();
  if (!q) {
    const genres = await api('/api/genres/', { signal: ctx.signal });
    return { q, genres: Array.isArray(genres) ? genres : [] };
  }
  const results = await api(`/api/search/?q=${encodeURIComponent(q)}`, { signal: ctx.signal });
  return { q, results };
}

function genreTile(name) {
  const [c1, c2] = colorsFromText(name);
  const a = h('a', { class: 'genre-tile', href: `/genre/${encodeURIComponent(name)}` }, h('span', { class: 'genre-name', text: name }), h('span', { class: 'genre-art', 'aria-hidden': 'true' }, icon('note')));
  a.style.setProperty('--c1', c1);
  a.style.setProperty('--c2', c2);
  return a;
}

function fill(root, data) {
  if (!data.q) {
    root.replaceChildren(
      h('h1', { class: 'page-title', text: 'Browse all' }),
      data.genres.length
        ? h('div', { class: 'genre-grid' }, data.genres.map(genreTile))
        : emptyState({ title: 'No genres yet', text: 'Genres appear once there are songs. Type in the search box to look for something.' }),
    );
    return;
  }
  const r = data.results || {};
  const songs = r.songs || [];
  const artists = r.artists || [];
  const albums = r.albums || [];
  const playlists = r.playlists || [];
  if (!songs.length && !artists.length && !albums.length && !playlists.length) {
    root.replaceChildren(emptyState({ title: `No results for "${data.q}"`, text: 'Check the spelling or try a shorter search.' }));
    return;
  }
  const parts = [h('h1', { class: 'sr-only', text: `Search results for ${data.q}` })];
  if (songs.length) {
    const list = songList(songs);
    parts.push(h('section', { class: 'block', 'aria-labelledby': 'res-songs' }, h('h2', { class: 'shelf-title', id: 'res-songs', text: 'Songs' }), list.el));
  }
  if (artists.length) parts.push(shelf('Artists', artists.map(artistCard), { id: 'res-artists' }));
  if (albums.length) parts.push(shelf('Albums', albums.map(albumCard), { id: 'res-albums' }));
  if (playlists.length) parts.push(shelf('Playlists', playlists.map(playlistCard), { id: 'res-playlists' }));
  root.replaceChildren(...parts);
}

export function render(data, ctx) {
  ctx.setTitle(data.q ? `Search: ${data.q}` : 'Search');
  const root = h('div', { class: 'search-page' });
  fill(root, data);
  return {
    el: root,
    update(next, nextCtx) {
      nextCtx.setTitle(next.q ? `Search: ${next.q}` : 'Search');
      fill(root, next);
    },
  };
}
