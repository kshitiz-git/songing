import { h, cover, icon, fmtTotal, plural } from '../dom.js';
import { api } from '../api.js';
import { on, refreshPlaylists } from '../store.js';
import { navigate, reload } from '../router.js';
import { songList } from '../ui/songlist.js';
import { hero, detail, bigPlay, metaList } from '../ui/hero.js';
import { credits } from '../ui/credits.js';
import { emptyState } from '../ui/empty.js';
import { confirmModal } from '../ui/modal.js';
import { playlistModal } from '../ui/playlistmodal.js';
import { toast } from '../ui/toast.js';

export const load = (ctx) => api(`/api/playlists/${ctx.params.id}/`, { signal: ctx.signal });

export function render(d, ctx) {
  ctx.setTitle(d.name);
  const songs = d.songs || [];
  const owner = !!d.is_owner;
  const empty = emptyState({
    title: owner ? 'This playlist is empty' : 'No songs here yet',
    text: owner ? 'Open the menu on any song and choose Add to playlist.' : '',
    action: owner ? { label: 'Find songs', href: '/search' } : null,
  });

  // Order saves go out one at a time so the last move always wins.
  let chain = Promise.resolve();
  function saveOrder(ids) {
    chain = chain.catch(() => {}).then(() => api(`/api/playlists/${d.id}/reorder/`, { method: 'POST', body: { song_ids: ids } }));
    chain.then(
      () => toast('Order saved', { timeout: 1500 }),
      (err) => {
        toast(`Could not save the new order. ${err.message}`, { kind: 'error' });
        reload();
      },
    );
  }

  async function removeSong(song) {
    try {
      await api(`/api/playlists/${d.id}/songs/${song.id}/`, { method: 'DELETE' });
      list.remove(song);
      toast(`Removed from ${d.name}`);
      refreshPlaylists();
    } catch (err) {
      toast(err.message, { kind: 'error' });
    }
  }

  const list = songList(songs, {
    showAlbum: true,
    reorder: owner,
    onReorder: saveOrder,
    onRemove: owner ? removeSong : null,
    onChange: () => {
      empty.hidden = list.count() > 0;
      listWrap.hidden = list.count() === 0;
    },
  });
  const listWrap = h('div', {}, list.el, credits(songs));
  empty.hidden = songs.length > 0;
  listWrap.hidden = songs.length === 0;

  const total = songs.reduce((n, s) => n + (Number(s.duration) || 0), 0);
  const meta = metaList([
    d.owner ? h('span', { class: 'strong', text: owner ? 'You' : d.owner.username }) : null,
    plural(songs.length, 'song'),
    songs.length ? fmtTotal(total) : null,
    d.is_public ? 'Public' : 'Private',
  ]);

  const actions = h('div', { class: 'actions' }, bigPlay(() => list.songs(), `Play ${d.name}`));
  if (owner) {
    actions.append(
      h('button', { type: 'button', class: 'btn btn-outline', onclick: edit }, icon('edit'), h('span', { text: 'Edit details' })),
      h('button', { type: 'button', class: 'btn btn-outline btn-danger-outline', onclick: remove }, icon('trash'), h('span', { text: 'Delete playlist' })),
    );
  }

  async function edit() {
    const saved = await playlistModal({ playlist: d });
    if (saved) {
      toast('Playlist updated');
      reload();
    }
  }
  async function remove() {
    const ok = await confirmModal({
      title: 'Delete this playlist?',
      message: `"${d.name}" will be deleted. The songs themselves are not touched.`,
      confirmText: 'Delete playlist',
    });
    if (!ok) return;
    try {
      await api(`/api/playlists/${d.id}/`, { method: 'DELETE' });
      toast('Playlist deleted');
      await refreshPlaylists();
      navigate('/');
    } catch (err) {
      toast(err.message, { kind: 'error' });
    }
  }

  const unsub = on('playlist-changed', ({ id }) => {
    if (id === d.id) reload();
  });

  const el = detail(
    d.colors,
    hero({ kind: 'Playlist', title: d.name, description: d.description, coverEl: cover(d, { kind: 'playlist' }), meta }),
    actions,
    empty,
    listWrap,
  );
  return { el, destroy: unsub };
}
