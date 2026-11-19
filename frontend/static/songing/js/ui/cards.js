// Cards and horizontal shelves (home, search, artist pages).
import { h, icon, cover, plural } from '../dom.js';
import { api } from '../api.js';
import { player } from '../player.js';
import { toast } from './toast.js';

function playBtn(label, onclick) {
  return h('button', { type: 'button', class: 'card-play', 'aria-label': label, title: label, onclick }, icon('play'));
}

async function playEntity(kind, id) {
  try {
    const path = kind === 'album' ? `/api/albums/${id}/` : kind === 'playlist' ? `/api/playlists/${id}/` : `/api/artists/${id}/`;
    const d = await api(path);
    const songs = kind === 'artist' ? d.top_songs : d.songs;
    if (!songs || !songs.length) toast('Nothing to play here yet.');
    else player.playAll(songs);
  } catch (err) {
    toast(err.message, { kind: 'error' });
  }
}

export function songCard(song, list) {
  const play = () => player.playList(list, Math.max(0, list.indexOf(song)));
  return h(
    'article',
    { class: 'card card-song' },
    h('div', { class: 'card-art' }, cover(song, { kind: 'song' }), playBtn(`Play ${song.title}`, play)),
    h(
      'div',
      { class: 'card-text' },
      h('h3', { class: 'card-title' }, h('button', { type: 'button', class: 'card-link', onclick: play, text: song.title })),
      h('p', { class: 'card-sub' }, h('a', { href: `/artist/${song.artist.id}`, text: song.artist.name })),
    ),
  );
}

export function albumCard(album) {
  const sub = [album.year, album.artist && album.artist.name].filter(Boolean).join(' · ');
  return h(
    'article',
    { class: 'card card-album' },
    h('div', { class: 'card-art' }, cover(album, { kind: 'album' }), playBtn(`Play ${album.title}`, () => playEntity('album', album.id))),
    h(
      'div',
      { class: 'card-text' },
      h('h3', { class: 'card-title' }, h('a', { class: 'card-link', href: `/album/${album.id}`, text: album.title })),
      h('p', { class: 'card-sub', text: sub }),
    ),
  );
}

export function artistCard(artist) {
  return h(
    'article',
    { class: 'card card-artist' },
    h('div', { class: 'card-art' }, cover(artist, { kind: 'artist', round: true }), playBtn(`Play ${artist.name}`, () => playEntity('artist', artist.id))),
    h(
      'div',
      { class: 'card-text' },
      h('h3', { class: 'card-title' }, h('a', { class: 'card-link', href: `/artist/${artist.id}`, text: artist.name })),
      h('p', { class: 'card-sub', text: `Artist · ${plural(artist.song_count ?? 0, 'song')}` }),
    ),
  );
}

export function playlistCard(pl) {
  const by = pl.is_owner ? 'You' : pl.owner ? pl.owner.username : '';
  return h(
    'article',
    { class: 'card card-playlist' },
    h('div', { class: 'card-art' }, cover(pl, { kind: 'playlist' }), playBtn(`Play ${pl.name}`, () => playEntity('playlist', pl.id))),
    h(
      'div',
      { class: 'card-text' },
      h('h3', { class: 'card-title' }, h('a', { class: 'card-link', href: `/playlist/${pl.id}`, text: pl.name })),
      h('p', { class: 'card-sub', text: `${by ? `By ${by} · ` : ''}${plural(pl.song_count ?? 0, 'song')}` }),
    ),
  );
}

/** Titled horizontally scrolling row. */
export function shelf(title, cards, { id } = {}) {
  const hid = id || `shelf-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
  return h(
    'section',
    { class: 'shelf', 'aria-labelledby': hid },
    h('h2', { class: 'shelf-title', id: hid, text: title }),
    h('div', { class: 'row', role: 'list' }, cards.map((c) => { c.setAttribute('role', 'listitem'); return c; })),
  );
}
