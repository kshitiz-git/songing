// Song table used by every list page. Desktop: # / title / album / like / length / menu.
// Mobile (CSS): title + artist rows. Optional reorder mode (drag handle + up/down buttons).
import { h, icon, iconButton, cover, fmtTime } from '../dom.js';
import { player } from '../player.js';
import { heartButton } from './heart.js';
import { openSongMenu, deleteSong } from './songmenu.js';

const TAP_PLAYS = '(max-width: 699.98px), (pointer: coarse)';

function eq() {
  return h('span', { class: 'eq', 'aria-hidden': 'true' }, h('i'), h('i'), h('i'), h('i'));
}

/**
 * songList(songs, options) -> {el, songs(), append(list), remove(song), count()}
 * options: showAlbum=true, reorder=false, onReorder(ids)->Promise, onRemove(song), deletable=false,
 *          onDeleted(song), onChange(), showPrivate=false
 */
export function songList(initial, options = {}) {
  const o = { showAlbum: true, reorder: false, deletable: false, showPrivate: false, ...options };
  let songs = [];
  const byRow = new WeakMap();
  const ol = h('ol', { class: 'tracklist' });
  const head = h(
    'div',
    { class: 'tracklist-head', 'aria-hidden': 'true' },
    h('span', { class: 'th-idx', text: '#' }),
    h('span', { text: 'Title' }),
    h('span', { class: 'th-album', text: o.showAlbum ? 'Album' : '' }),
    h('span'),
    h('span', { class: 'th-dur' }, icon('clock')),
    h('span'),
  );
  const el = h('div', { class: `tracks${o.showAlbum ? '' : ' no-album'}${o.reorder ? ' has-reorder' : ''}${o.onRemove ? ' has-remove' : ''}${o.deletable ? ' has-delete' : ''}` }, head, ol);

  const playAt = (song) => player.playList(songs, Math.max(0, songs.indexOf(song)));
  // The play button on the playing row pauses / resumes instead of restarting.
  const playOrToggle = (song) => {
    const cur = player.song;
    if (cur && cur.id === song.id) player.togglePlay();
    else playAt(song);
  };

  function menuCtx(song) {
    return {
      onPlay: () => playAt(song),
      onRemoveFromPlaylist: o.onRemove ? () => o.onRemove(song) : null,
      onDeleted: (s) => {
        remove(s);
        if (o.onDeleted) o.onDeleted(s);
      },
    };
  }

  function row(song) {
    const cur = player.song;
    const li = h('li', { class: `track${cur && cur.id === song.id ? ' is-current' : ''}`, 'data-song-id': song.id, 'data-title': song.title });
    byRow.set(li, song);

    const playBtn = h('button', { type: 'button', class: 't-play', 'aria-label': `Play ${song.title}`, title: 'Play', onclick: () => playOrToggle(song) }, icon('play'));
    const title = h('span', { class: 't-title', text: song.title });
    const sub = h('span', { class: 't-sub' }, h('a', { href: `/artist/${song.artist.id}`, text: song.artist.name }));
    if (o.showPrivate && song.is_owner && !song.is_public) sub.prepend(h('span', { class: 'chip', text: 'Private' }));
    const main = h('div', { class: 't-main' }, cover(song, { kind: 'song', cls: 't-cover' }), h('div', { class: 't-text' }, title, sub));
    // Phones / touch: tapping the title area plays (no double-click on touch).
    main.addEventListener('click', (e) => {
      if (e.target.closest('a')) return;
      if (matchMedia(TAP_PLAYS).matches) playAt(song);
    });
    li.addEventListener('dblclick', (e) => {
      if (e.target.closest('a, button, input')) return;
      playAt(song);
    });

    li.append(
      h('div', { class: 't-idx' }, h('span', { class: 't-num' }), eq(), playBtn),
      main,
      h('div', { class: 't-album' }, o.showAlbum && song.album ? h('a', { href: `/album/${song.album.id}`, text: song.album.title }) : null),
      h('div', { class: 't-like' }, heartButton(song)),
      h('div', { class: 't-dur', text: fmtTime(song.duration) }),
    );

    const actions = h('div', { class: 't-actions' });
    if (o.reorder) {
      const grip = h('span', { class: 't-grip', draggable: true, title: 'Drag to reorder', 'aria-hidden': 'true' }, icon('grip'));
      wireDrag(grip, li);
      actions.append(
        grip,
        iconButton('up', `Move ${song.title} up`, { class: 't-up', onclick: () => move(li, -1, 't-up') }),
        iconButton('down', `Move ${song.title} down`, { class: 't-down', onclick: () => move(li, 1, 't-down') }),
      );
    }
    if (o.onRemove) actions.append(iconButton('close', `Remove ${song.title} from playlist`, { class: 't-remove', onclick: () => o.onRemove(song) }));
    if (o.deletable && song.is_owner) actions.append(iconButton('trash', `Delete ${song.title}`, { class: 't-delete', onclick: () => deleteSong(song, menuCtx(song)) }));
    const menuBtn = iconButton('more', `More actions for ${song.title}`, { class: 't-more', 'aria-haspopup': 'menu', 'aria-expanded': 'false' });
    menuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openSongMenu(menuBtn, song, menuCtx(song));
    });
    actions.append(menuBtn);
    li.append(actions);
    return li;
  }

  function renumber() {
    [...ol.children].forEach((li, i) => {
      li.querySelector('.t-num').textContent = String(i + 1);
      const up = li.querySelector('.t-up');
      const down = li.querySelector('.t-down');
      if (up) up.disabled = i === 0;
      if (down) down.disabled = i === ol.children.length - 1;
    });
  }

  function syncOrder() {
    songs = [...ol.children].map((li) => byRow.get(li));
    renumber();
    if (o.onReorder) o.onReorder(songs.map((s) => s.id));
    if (o.onChange) o.onChange();
  }

  function move(li, delta, focusClass) {
    const rows = [...ol.children];
    const i = rows.indexOf(li);
    const j = i + delta;
    if (j < 0 || j >= rows.length) return;
    if (delta < 0) ol.insertBefore(li, rows[j]);
    else ol.insertBefore(li, rows[j].nextSibling);
    syncOrder();
    // Moving a node drops focus; put it back (on the other arrow when this one just got disabled).
    const btn = li.querySelector(`.${focusClass}`);
    (btn && !btn.disabled ? btn : li.querySelector(focusClass === 't-up' ? '.t-down' : '.t-up')).focus();
  }

  // ----- drag and drop (mouse); touch / keyboard use the arrow buttons -----
  let dragging = null;
  function clearMarks() {
    for (const r of ol.querySelectorAll('.drop-before, .drop-after')) r.classList.remove('drop-before', 'drop-after');
  }
  function wireDrag(grip, li) {
    grip.addEventListener('dragstart', (e) => {
      dragging = li;
      li.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(byRow.get(li).id));
      try {
        e.dataTransfer.setDragImage(li, 24, 24);
      } catch {
        /* default drag image */
      }
    });
    grip.addEventListener('dragend', () => {
      li.classList.remove('dragging');
      clearMarks();
      dragging = null;
    });
  }
  ol.addEventListener('dragover', (e) => {
    if (!dragging) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    clearMarks();
    const target = e.target.closest('.track');
    if (!target || target === dragging) return;
    const r = target.getBoundingClientRect();
    target.classList.add(e.clientY > r.top + r.height / 2 ? 'drop-after' : 'drop-before');
  });
  ol.addEventListener('drop', (e) => {
    if (!dragging) return;
    e.preventDefault();
    const target = e.target.closest('.track');
    clearMarks();
    if (!target || target === dragging) return;
    const r = target.getBoundingClientRect();
    ol.insertBefore(dragging, e.clientY > r.top + r.height / 2 ? target.nextSibling : target);
    syncOrder();
  });

  // ----- public API -----
  function append(list) {
    for (const s of list) {
      songs.push(s);
      ol.append(row(s));
    }
    renumber();
  }

  function remove(song) {
    const li = ol.querySelector(`[data-song-id="${song.id}"]`);
    if (li) li.remove();
    songs = songs.filter((s) => s.id !== song.id);
    renumber();
    if (o.onChange) o.onChange();
  }

  append(initial);
  return { el, songs: () => songs, append, remove, count: () => songs.length };
}

// Mark the playing row everywhere (rows are created in many places): highlight, and Play/Pause on its button.
function syncRows() {
  const cur = player.song;
  const playing = player.playing;
  for (const li of document.querySelectorAll('.track[data-song-id]')) {
    const isCur = !!cur && String(cur.id) === li.dataset.songId;
    li.classList.toggle('is-current', isCur);
    const btn = li.querySelector('.t-play');
    const active = isCur && playing;
    if (btn && btn.dataset.active !== String(active)) {
      btn.dataset.active = String(active);
      btn.replaceChildren(icon(active ? 'pause' : 'play'));
      btn.setAttribute('aria-label', `${active ? 'Pause' : 'Play'} ${li.dataset.title}`);
      btn.title = active ? 'Pause' : 'Play';
    }
  }
}
player.addEventListener('song', syncRows);
player.addEventListener('state', syncRows);
