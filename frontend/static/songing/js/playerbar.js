// Bottom player bar + queue panel. Binds the static markup in index.html to the player engine.
import { h, $, icon, cover, fmtTime, clamp, safeColors } from './dom.js';
import { player } from './player.js';
import { heartButton } from './ui/heart.js';
import { on } from './store.js';

const MOBILE = '(max-width: 699.98px)';

function setPct(el, pct) {
  el.style.setProperty('--pct', `${clamp(pct, 0, 100).toFixed(2)}%`);
}

export function initPlayerBar() {
  const bar = $('#player');
  const els = {
    cover: $('#pl-cover'),
    title: $('#pl-title'),
    artist: $('#pl-artist'),
    heart: $('#pl-heart'),
    play: $('#pl-play'),
    prev: $('#pl-prev'),
    next: $('#pl-next'),
    shuffle: $('#pl-shuffle'),
    repeat: $('#pl-repeat'),
    seek: $('#pl-seek'),
    cur: $('#pl-cur'),
    dur: $('#pl-dur'),
    queueBtn: $('#pl-queue-btn'),
    mute: $('#pl-mute'),
    volume: $('#pl-volume'),
    expand: $('#pl-expand'),
    collapse: $('#pl-collapse'),
  };
  const panel = $('#queue');
  const queueBody = $('#queue-body');
  let dragging = false;
  let lastSongId = null;
  let lastText = '';

  // ---------- render ----------
  function renderSong() {
    const s = player.song;
    bar.classList.toggle('is-empty', !s);
    els.cover.replaceChildren(cover(s, { kind: 'song' }));
    const [c1, c2] = safeColors(s && s.colors);
    bar.style.setProperty('--c1', c1);
    bar.style.setProperty('--c2', c2);
    if (s) {
      els.title.replaceChildren(s.album ? h('a', { href: `/album/${s.album.id}`, text: s.title }) : h('span', { text: s.title }));
      els.artist.replaceChildren(h('a', { href: `/artist/${s.artist.id}`, text: s.artist.name }));
      els.heart.replaceChildren(heartButton(s));
    } else {
      els.title.replaceChildren(h('span', { class: 'muted', text: 'Nothing playing' }));
      els.artist.replaceChildren();
      els.heart.replaceChildren();
    }
    for (const b of [els.play, els.prev, els.next, els.seek]) b.disabled = !s;
    lastSongId = s ? s.id : null;
    renderTime();
    renderState();
  }

  function renderTime() {
    const dur = player.duration;
    const cur = Math.min(player.currentTime, dur || player.currentTime);
    if (!dragging) {
      els.seek.max = String(dur || 0);
      els.seek.value = String(cur);
      els.cur.textContent = fmtTime(cur);
    }
    els.dur.textContent = fmtTime(dur);
    const pct = dur ? ((dragging ? Number(els.seek.value) : cur) / dur) * 100 : 0;
    setPct(els.seek, pct);
    setPct(bar, pct);
    const text = `${fmtTime(dragging ? Number(els.seek.value) : cur)} of ${fmtTime(dur)}`;
    if (text !== lastText) {
      lastText = text;
      els.seek.setAttribute('aria-valuetext', text);
    }
  }

  function renderState() {
    const playing = player.playing;
    document.body.classList.toggle('is-playing', playing);
    els.play.replaceChildren(icon(playing ? 'pause' : 'play'));
    const label = playing ? 'Pause' : 'Play';
    els.play.setAttribute('aria-label', label);
    els.play.title = label;
  }

  function renderMode() {
    els.shuffle.setAttribute('aria-pressed', String(player.shuffle));
    els.shuffle.classList.toggle('on', player.shuffle);
    const r = player.repeat;
    els.repeat.setAttribute('aria-pressed', String(r !== 'off'));
    els.repeat.setAttribute('aria-label', `Repeat: ${r}`);
    els.repeat.title = `Repeat: ${r}`;
    els.repeat.classList.toggle('on', r !== 'off');
    els.repeat.replaceChildren(icon(r === 'one' ? 'repeatOne' : 'repeat'));
  }

  function renderVolume() {
    const v = player.muted ? 0 : player.volume;
    els.volume.value = String(v);
    setPct(els.volume, v * 100);
    els.mute.setAttribute('aria-pressed', String(player.muted));
    els.mute.replaceChildren(icon(v === 0 ? 'volumeMute' : v < 0.5 ? 'volumeLow' : 'volume'));
    els.volume.setAttribute('aria-valuetext', `${Math.round(v * 100)} percent`);
  }

  // ---------- engine events ----------
  player.addEventListener('song', () => {
    renderSong();
    scheduleQueue();
  });
  player.addEventListener('state', renderState);
  player.addEventListener('time', renderTime);
  player.addEventListener('mode', renderMode);
  player.addEventListener('volume', renderVolume);
  player.addEventListener('queue', scheduleQueue);

  // ---------- controls ----------
  els.play.addEventListener('click', () => player.togglePlay());
  els.prev.addEventListener('click', () => player.prev());
  els.next.addEventListener('click', () => player.next());
  els.shuffle.addEventListener('click', () => player.toggleShuffle());
  els.repeat.addEventListener('click', () => player.cycleRepeat());
  els.mute.addEventListener('click', () => player.toggleMute());
  els.volume.addEventListener('input', () => player.setVolume(Number(els.volume.value)));

  els.seek.addEventListener('input', () => {
    dragging = true;
    els.cur.textContent = fmtTime(Number(els.seek.value));
    renderTime();
  });
  els.seek.addEventListener('change', () => {
    player.seek(Number(els.seek.value));
    dragging = false;
    renderTime();
  });
  els.seek.addEventListener('blur', () => {
    dragging = false;
  });
  // The range step is 0.1 s; arrow keys should jump further.
  els.seek.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    player.seek(player.currentTime + (e.key === 'ArrowRight' ? 5 : -5));
  });

  // ---------- mobile expand / collapse ----------
  function setExpanded(on) {
    bar.classList.toggle('expanded', on);
    document.body.classList.toggle('player-expanded', on);
    els.expand.setAttribute('aria-expanded', String(on));
    if (on) els.collapse.focus({ preventScroll: true });
  }
  els.expand.addEventListener('click', () => setExpanded(true));
  els.collapse.addEventListener('click', () => {
    setExpanded(false);
    els.expand.focus({ preventScroll: true });
  });
  on('route', () => {
    if (bar.classList.contains('expanded')) setExpanded(false);
  });
  // Tapping the compact bar (not its buttons) opens the full player.
  $('#pl-now').addEventListener('click', (e) => {
    if (!matchMedia(MOBILE).matches || bar.classList.contains('expanded')) return;
    if (e.target.closest('.heart')) return;
    e.preventDefault();
    setExpanded(true);
  });
  matchMedia(MOBILE).addEventListener('change', (e) => {
    if (!e.matches) setExpanded(false);
  });

  // ---------- queue panel ----------
  // Rendered synchronously so callers (remove button) can move focus into the fresh DOM.
  function scheduleQueue() {
    if (!panel.hidden) renderQueue();
  }

  function queueItem(song, i, kind) {
    const current = kind === 'current';
    const main = h(
      'button',
      {
        type: 'button',
        class: 'q-main',
        'aria-label': current ? `Now playing: ${song.title}. ${player.playing ? 'Pause' : 'Play'}` : `Play ${song.title}`,
        onclick: () => (current ? player.togglePlay() : player.jumpTo(i)),
      },
      cover(song, { kind: 'song', cls: 'q-cover' }),
      h('span', { class: 'q-text' }, h('span', { class: 'q-title', text: song.title }), h('span', { class: 'q-artist', text: song.artist.name })),
    );
    return h(
      'li',
      { class: `q-item${current ? ' is-current' : ''}`, 'data-qi': i, 'aria-current': current ? 'true' : null },
      main,
      h('button', {
        type: 'button',
        class: 'icon-btn q-remove',
        'aria-label': `Remove ${song.title} from queue`,
        title: 'Remove from queue',
        onclick: () => {
          player.removeAt(i);
          const target = queueBody.querySelector(`[data-qi="${Math.min(i, player.queue.length - 1)}"] .q-remove`);
          (target || $('#queue-close')).focus();
        },
      }, icon('close')),
    );
  }

  function renderQueue() {
    const q = player.queue;
    const idx = player.index;
    if (!q.length) {
      queueBody.replaceChildren(h('p', { class: 'queue-empty', text: 'Your queue is empty. Play a song and it will show up here.' }));
      return;
    }
    const upcoming = q.slice(idx + 1);
    const before = q.slice(0, idx);
    const parts = [
      h('h3', { class: 'queue-h', text: 'Now playing' }),
      h('ul', { class: 'queue-list' }, queueItem(q[idx], idx, 'current')),
      h('h3', { class: 'queue-h', text: 'Next up' }),
      upcoming.length
        ? h('ul', { class: 'queue-list' }, upcoming.map((s, k) => queueItem(s, idx + 1 + k, 'next')))
        : h('p', { class: 'queue-empty', text: player.repeat === 'all' ? 'The queue starts over after this song.' : 'Nothing after this song.' }),
    ];
    if (before.length) {
      parts.push(
        h(
          'details',
          { class: 'queue-before' },
          h('summary', { text: `Played earlier (${before.length})` }),
          h('ul', { class: 'queue-list' }, before.map((s, k) => queueItem(s, k, 'before'))),
        ),
      );
    }
    queueBody.replaceChildren(...parts);
  }

  function setQueueOpen(open) {
    panel.hidden = !open;
    els.queueBtn.setAttribute('aria-pressed', String(open));
    document.body.classList.toggle('queue-open', open);
    if (open) {
      renderQueue();
      (queueBody.querySelector('.is-current .q-main') || $('#queue-close')).focus({ preventScroll: true });
    }
  }
  els.queueBtn.addEventListener('click', () => setQueueOpen(panel.hidden));
  $('#queue-close').addEventListener('click', () => {
    setQueueOpen(false);
    els.queueBtn.focus();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || panel.hidden || e.defaultPrevented) return;
    if (document.querySelector('.modal-backdrop, .menu')) return;
    const inside = panel.contains(document.activeElement);
    setQueueOpen(false);
    if (inside) els.queueBtn.focus();
  });

  // ---------- keyboard: Space = play / pause ----------
  document.addEventListener('keydown', (e) => {
    if (e.code !== 'Space' || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
    if (e.defaultPrevented || !player.song) return;
    const t = e.target;
    if (t instanceof Element && t.closest('input, textarea, select, button, summary, [contenteditable=""], [contenteditable="true"], [role="textbox"], [role="menuitem"], [role="slider"]')) return;
    if (document.querySelector('.modal-backdrop, .menu')) return;
    e.preventDefault();
    player.togglePlay();
  });

  renderSong();
  renderMode();
  renderVolume();
  renderQueue();
}
