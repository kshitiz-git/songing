// The "..." menu on a song row (also used from the queue / cards), plus delete and song-info dialogs.
import { h, fmtTime, safeUrl } from '../dom.js';
import { api, ApiError } from '../api.js';
import { store, refreshPlaylists, emit } from '../store.js';
import { player } from '../player.js';
import { navigate, loginUrl } from '../router.js';
import { openMenu } from './menu.js';
import { modal, confirmModal } from './modal.js';
import { playlistModal } from './playlistmodal.js';
import { toast } from './toast.js';

/**
 * ctx (all optional): onPlay(), onRemoveFromPlaylist(), onDeleted(song)
 */
export function openSongMenu(trigger, song, ctx = {}) {
  const root = [
    { label: 'Play', icon: 'play', onSelect: () => (ctx.onPlay ? ctx.onPlay() : player.playList([song], 0)) },
    {
      label: 'Add to queue',
      icon: 'queueAdd',
      onSelect: () => {
        player.addToQueue(song);
        toast('Added to queue');
      },
    },
    { label: 'Add to playlist', icon: 'plus', keepOpen: true, onSelect: (ctrl) => choosePlaylist(ctrl, song, root) },
    { separator: true },
    { label: 'Go to artist', icon: 'person', onSelect: () => navigate(`/artist/${song.artist.id}`) },
  ];
  if (song.album) root.push({ label: 'Go to album', icon: 'album', onSelect: () => navigate(`/album/${song.album.id}`) });
  root.push({ label: 'Song info', icon: 'info', onSelect: () => showSongInfo(song) });
  if (ctx.onRemoveFromPlaylist) {
    root.push({ separator: true }, { label: 'Remove from this playlist', icon: 'close', onSelect: () => ctx.onRemoveFromPlaylist() });
  }
  if (song.is_owner) {
    root.push({ separator: true }, { label: 'Delete', icon: 'trash', danger: true, onSelect: () => deleteSong(song, ctx) });
  }
  return openMenu(trigger, root, { label: `Actions for ${song.title}` });
}

function choosePlaylist(ctrl, song, back) {
  if (!store.user) {
    ctrl.close();
    navigate(loginUrl());
    return;
  }
  ctrl.setItems([
    { label: 'Back', icon: 'back', keepOpen: true, onSelect: () => ctrl.setItems(back) },
    { label: 'New playlist', icon: 'plus', onSelect: () => addToNewPlaylist(song) },
    ...(store.playlists.length ? [{ separator: true }, { heading: 'Your playlists' }] : []),
    ...store.playlists.map((p) => ({ label: p.name, icon: 'list', onSelect: () => addToPlaylist(p, song) })),
  ]);
}

export async function addToPlaylist(playlist, song) {
  try {
    const { status } = await api(`/api/playlists/${playlist.id}/songs/`, { method: 'POST', body: { song_id: song.id }, full: true });
    toast(status === 201 ? `Added to ${playlist.name}` : `Already in ${playlist.name}`);
    refreshPlaylists();
    emit('playlist-changed', { id: playlist.id });
  } catch (err) {
    if (err instanceof ApiError && (err.status === 401 || err.status === 403)) navigate(loginUrl());
    else toast(err.message, { kind: 'error' });
  }
}

async function addToNewPlaylist(song) {
  const created = await playlistModal();
  if (created) await addToPlaylist(created, song);
}

export async function deleteSong(song, ctx = {}) {
  const ok = await confirmModal({
    title: 'Delete this song?',
    message: `"${song.title}" will be deleted for good and removed from every playlist and queue.`,
    confirmText: 'Delete song',
  });
  if (!ok) return;
  try {
    await api(`/api/songs/${song.id}/`, { method: 'DELETE' });
    player.removeSongId(song.id);
    toast('Song deleted');
    refreshPlaylists();
    if (ctx.onDeleted) ctx.onDeleted(song);
  } catch (err) {
    toast(err.message, { kind: 'error' });
  }
}

export function showSongInfo(song) {
  const rows = [
    ['Title', song.title],
    ['Artist', song.artist.name],
    ['Album', song.album ? song.album.title : ''],
    ['Genre', song.genre],
    ['Length', fmtTime(song.duration)],
    ['Plays', String(song.play_count ?? 0)],
    ['License', song.license],
    ['Credit', song.attribution],
  ].filter(([, v]) => v);
  const dl = h('dl', { class: 'info-list' }, rows.map(([k, v]) => [h('dt', { text: k }), h('dd', { text: v })]));
  const src = safeUrl(song.source_url);
  if (src) {
    dl.append(h('dt', { text: 'Source' }), h('dd', {}, h('a', { href: src, target: '_blank', rel: 'noopener noreferrer', text: src })));
  }
  const close = h('button', { type: 'button', class: 'btn btn-light', text: 'Close', 'data-autofocus': '' });
  const m = modal({ title: 'Song info', body: dl, footer: close });
  close.addEventListener('click', () => m.close());
}
