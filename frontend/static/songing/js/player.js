// Audio engine: queue, shuffle, repeat, play counting, persistence, Media Session.
// No DOM here except the Audio element. The player bar and queue panel subscribe to its events:
//   song (current song or queue changed), state (play/pause), time, queue, mode (shuffle/repeat), volume
import { api } from './api.js';
import { clamp } from './dom.js';
import { toast } from './ui/toast.js';

const KEY = 'songing.player.v1';
const COUNT_AFTER = 30; // seconds of real listening before a play is recorded

const audio = new Audio();
audio.preload = 'metadata';

let queue = []; // songs in play order
let orig = []; // ids in the order the list had before shuffle
let index = -1;
let shuffle = false;
let repeat = 'off'; // off | all | one
let volume = 0.8;
let muted = false;

let listened = 0;
let lastT = null;
let counted = false;
let pendingSeek = null;
let intendPlay = false; // the last load asked for playback
let errorStreak = 0;
let lastSave = 0;
const manual = new Set(); // queue entries added with "Add to queue"

class Player extends EventTarget {
  emit(name) {
    this.dispatchEvent(new Event(name));
  }
  get song() {
    return queue[index] || null;
  }
  get queue() {
    return queue;
  }
  get index() {
    return index;
  }
  get playing() {
    return !audio.paused;
  }
  get shuffle() {
    return shuffle;
  }
  get repeat() {
    return repeat;
  }
  get volume() {
    return volume;
  }
  get muted() {
    return muted;
  }
  get currentTime() {
    return pendingSeek != null ? pendingSeek : audio.currentTime || 0;
  }
  get duration() {
    const d = audio.duration;
    if (Number.isFinite(d) && d > 0) return d;
    return (this.song && this.song.duration) || 0;
  }

  // ---------- starting playback ----------
  /** Queue = songs, starting at start. Playing the song that is already current just swaps the queue around it. */
  playList(songs, start = 0, { autoplay = true } = {}) {
    songs = (songs || []).filter(validSong);
    if (!songs.length) return;
    start = clamp(start, 0, songs.length - 1);
    const startSong = songs[start];
    manual.clear();
    orig = songs.map((s) => s.id);
    const cur = this.song;
    queue = shuffle ? shuffled(songs, startSong) : songs.slice();
    const at = queue.indexOf(startSong);
    if (cur && cur.id === startSong.id) {
      index = at;
      queue[at] = cur; // keep the object the audio element was loaded for
      this.emit('queue');
      this.emit('song');
      save();
      if (autoplay && audio.paused) this.play();
      return;
    }
    load(at, autoplay);
  }

  /** Big play button on a page: with shuffle on, start somewhere random. */
  playAll(songs) {
    if (!songs || !songs.length) return;
    this.playList(songs, shuffle ? Math.floor(Math.random() * songs.length) : 0);
  }

  addToQueue(song) {
    if (!validSong(song)) return;
    if (!queue.length) return this.playList([song], 0);
    const copy = { ...song }; // own identity so "manual" membership is per entry
    let pos = index + 1;
    while (pos < queue.length && manual.has(queue[pos])) pos++;
    queue.splice(pos, 0, copy);
    manual.add(copy);
    orig.push(copy.id);
    this.emit('queue');
    save();
  }

  // ---------- transport ----------
  play() {
    if (!this.song) return;
    if (audio.error || !audio.getAttribute('src')) {
      load(index, true, this.currentTime);
      return;
    }
    intendPlay = true;
    const p = audio.play();
    if (p && p.catch) {
      p.catch((err) => {
        // AbortError: a new load interrupted us. NotSupportedError: the 'error' listener reports it.
        if (err.name !== 'AbortError' && err.name !== 'NotSupportedError') this.emit('state');
      });
    }
  }
  pause() {
    intendPlay = false;
    audio.pause();
  }
  togglePlay() {
    if (audio.paused) this.play();
    else this.pause();
  }
  next() {
    advance(false);
  }
  prev() {
    if (!queue.length) return;
    if (audio.currentTime > 3 || (index === 0 && repeat !== 'all')) {
      this.seek(0);
      return;
    }
    load(index > 0 ? index - 1 : queue.length - 1, true);
  }
  seek(t) {
    if (!this.song) return;
    const d = this.duration;
    t = clamp(Number(t) || 0, 0, d || Infinity);
    if (pendingSeek != null) pendingSeek = t;
    else audio.currentTime = t;
    this.emit('time');
  }
  jumpTo(i) {
    if (i >= 0 && i < queue.length) load(i, true);
  }

  // ---------- queue editing ----------
  removeAt(i) {
    if (i < 0 || i >= queue.length) return;
    const wasPlaying = !audio.paused;
    const [gone] = queue.splice(i, 1);
    manual.delete(gone);
    const k = orig.indexOf(gone.id);
    if (k >= 0) orig.splice(k, 1);
    if (!queue.length) return clearAll();
    if (i < index) {
      index -= 1;
    } else if (i === index) {
      if (i >= queue.length) return load(repeat === 'all' ? 0 : queue.length - 1, wasPlaying && repeat === 'all');
      return load(i, wasPlaying);
    }
    this.emit('queue');
    save();
  }
  removeSongId(id) {
    for (let i = queue.length - 1; i >= 0; i--) if (queue[i].id === id) this.removeAt(i);
  }

  // ---------- modes ----------
  toggleShuffle() {
    shuffle = !shuffle;
    const cur = this.song;
    if (cur) {
      if (shuffle) {
        orig = queue.map((s) => s.id);
        queue = shuffled(queue, cur);
        index = 0;
      } else {
        const byId = new Map(queue.map((s) => [s.id, s]));
        const ordered = orig.map((id) => byId.get(id)).filter(Boolean);
        for (const s of queue) if (!ordered.includes(s)) ordered.push(s);
        queue = ordered;
        index = Math.max(0, queue.indexOf(cur));
      }
    }
    this.emit('mode');
    this.emit('queue');
    save();
  }
  cycleRepeat() {
    repeat = repeat === 'off' ? 'all' : repeat === 'all' ? 'one' : 'off';
    this.emit('mode');
    save();
  }

  // ---------- volume ----------
  setVolume(v) {
    volume = clamp(Number(v) || 0, 0, 1);
    if (volume > 0) muted = false;
    audio.volume = volume;
    audio.muted = muted;
    this.emit('volume');
    save();
  }
  toggleMute() {
    muted = !muted;
    if (!muted && volume === 0) volume = 0.5;
    audio.volume = volume;
    audio.muted = muted;
    this.emit('volume');
    save();
  }

  // ---------- persistence ----------
  restore() {
    let raw = null;
    try {
      raw = JSON.parse(localStorage.getItem(KEY));
    } catch {
      /* private mode or corrupt JSON: start empty */
    }
    if (!raw || typeof raw !== 'object') {
      audio.volume = volume;
      return;
    }
    if (typeof raw.volume === 'number') volume = clamp(raw.volume, 0, 1);
    muted = raw.muted === true;
    shuffle = raw.shuffle === true;
    repeat = ['off', 'all', 'one'].includes(raw.repeat) ? raw.repeat : 'off';
    audio.volume = volume;
    audio.muted = muted;
    const q = Array.isArray(raw.queue) ? raw.queue.filter(validSong).slice(0, 500) : [];
    if (q.length) {
      queue = q;
      orig = Array.isArray(raw.orig) ? raw.orig.filter(Number.isInteger) : q.map((s) => s.id);
      const i = clamp(Number.isInteger(raw.index) ? raw.index : 0, 0, q.length - 1);
      load(i, false, Number(raw.position) > 0 ? Number(raw.position) : 0);
    }
    this.emit('mode');
    this.emit('volume');
  }
}

export const player = new Player();

// ---------- internals ----------
function validSong(s) {
  return !!(
    s &&
    Number.isInteger(s.id) &&
    typeof s.title === 'string' &&
    s.artist &&
    typeof s.artist.name === 'string' &&
    typeof s.stream_url === 'string' &&
    s.stream_url.startsWith('/') &&
    !s.stream_url.startsWith('//')
  );
}

function shuffled(list, first) {
  const rest = list.filter((s) => s !== first);
  for (let i = rest.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [rest[i], rest[j]] = [rest[j], rest[i]];
  }
  return [first, ...rest];
}

function resetCounting() {
  listened = 0;
  lastT = null;
  counted = false;
}

function load(i, autoplay, position = 0) {
  index = i;
  const song = queue[i];
  resetCounting();
  intendPlay = autoplay;
  pendingSeek = position > 0 ? position : null;
  audio.pause();
  audio.src = song.stream_url;
  if (autoplay) player.play();
  player.emit('song');
  player.emit('queue');
  player.emit('time');
  updateMediaSession();
  save();
}

function clearAll() {
  queue = [];
  orig = [];
  index = -1;
  manual.clear();
  intendPlay = false;
  pendingSeek = null;
  audio.pause();
  audio.removeAttribute('src');
  audio.load();
  resetCounting();
  player.emit('song');
  player.emit('queue');
  player.emit('state');
  player.emit('time');
  updateMediaSession();
  save();
}

/** Next song. At the end of the queue: repeat all -> first and play; otherwise first, paused. */
function advance(auto) {
  if (!queue.length) return;
  if (index + 1 < queue.length) return load(index + 1, true);
  load(0, repeat === 'all');
  if (auto && repeat !== 'all') player.emit('state');
}

function countPlay() {
  const song = player.song;
  if (!song || counted) return;
  counted = true;
  api(`/api/songs/${song.id}/play/`, { method: 'POST' }).catch(() => {});
}

function save(force = true) {
  const now = Date.now();
  if (!force && now - lastSave < 2000) return;
  lastSave = now;
  const state = { queue, orig, index, position: Math.floor(player.currentTime * 10) / 10, volume, muted, shuffle, repeat };
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    try {
      localStorage.setItem(KEY, JSON.stringify({ ...state, queue: queue.slice(index, index + 1), orig: [], index: 0 }));
    } catch {
      /* storage full or blocked */
    }
  }
}

// ---------- audio element events ----------
audio.addEventListener('loadedmetadata', () => {
  if (pendingSeek != null) {
    try {
      audio.currentTime = Math.min(pendingSeek, Math.max(0, (audio.duration || pendingSeek) - 0.25));
    } catch {
      /* ignore */
    }
    pendingSeek = null;
  }
  player.emit('time');
  updatePosition(true);
});
audio.addEventListener('durationchange', () => {
  player.emit('time');
  updatePosition(true);
});
audio.addEventListener('timeupdate', () => {
  const t = audio.currentTime;
  if (!audio.paused && !audio.seeking && lastT != null) {
    const d = t - lastT;
    if (d > 0 && d < 5) listened += d; // a seek resets lastT above, so a big jump never lands here
  }
  lastT = t;
  if (!counted && listened >= COUNT_AFTER) countPlay();
  player.emit('time');
  updatePosition(false);
  save(false);
});
audio.addEventListener('seeking', () => {
  lastT = null;
});
audio.addEventListener('seeked', () => {
  lastT = audio.currentTime;
  player.emit('time');
  updatePosition(true);
});
audio.addEventListener('play', () => {
  lastT = audio.currentTime;
  setPlaybackState('playing');
  player.emit('state');
  updatePosition(true);
});
audio.addEventListener('playing', () => {
  errorStreak = 0;
});
audio.addEventListener('pause', () => {
  lastT = null;
  setPlaybackState('paused');
  player.emit('state');
  updatePosition(true);
  save();
});
audio.addEventListener('ended', () => {
  const dur = Number.isFinite(audio.duration) ? audio.duration : (player.song && player.song.duration) || 0;
  if (!counted && dur > 0 && dur < COUNT_AFTER) countPlay();
  if (repeat === 'one') {
    resetCounting();
    audio.currentTime = 0;
    player.play();
    return;
  }
  advance(true);
});
audio.addEventListener('error', () => {
  const song = player.song;
  if (!song || !audio.getAttribute('src')) return;
  if (!intendPlay) {
    // A restored song that cannot load: stay quiet, report when the user presses play.
    return;
  }
  errorStreak += 1;
  toast(`Could not play "${song.title}".`, { kind: 'error' });
  if (errorStreak >= queue.length) {
    errorStreak = 0;
    intendPlay = false;
    player.emit('state');
    return;
  }
  if (index + 1 < queue.length || repeat === 'all') advance(true);
  else player.emit('state');
});

addEventListener('pagehide', () => save());
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') save();
});

// ---------- Media Session ----------
const ms = 'mediaSession' in navigator ? navigator.mediaSession : null;
const artCache = new Map();

function gradientArt(colors) {
  const key = (colors || []).join('|');
  if (artCache.has(key)) return artCache.get(key);
  let url = '';
  try {
    const c = document.createElement('canvas');
    c.width = c.height = 256;
    const g = c.getContext('2d');
    const grad = g.createLinearGradient(0, 0, 256, 256);
    grad.addColorStop(0, (colors && colors[0]) || '#3b1f6e');
    grad.addColorStop(1, (colors && colors[1]) || '#1f6e4a');
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
    url = c.toDataURL('image/png');
  } catch {
    /* canvas blocked */
  }
  artCache.set(key, url);
  return url;
}

function updateMediaSession() {
  if (!ms || typeof MediaMetadata === 'undefined') return;
  const s = player.song;
  if (!s) {
    ms.metadata = null;
    return;
  }
  let artwork = [];
  if (s.cover_url) {
    try {
      artwork = [{ src: new URL(s.cover_url, location.origin).href, sizes: '512x512' }];
    } catch {
      /* bad url */
    }
  } else {
    const src = gradientArt(s.colors);
    if (src) artwork = [{ src, sizes: '256x256', type: 'image/png' }];
  }
  ms.metadata = new MediaMetadata({
    title: s.title,
    artist: s.artist.name,
    album: s.album ? s.album.title : '',
    artwork,
  });
}

function setPlaybackState(state) {
  if (ms) ms.playbackState = state;
}

let lastPosUpdate = 0;
function updatePosition(force) {
  if (!ms || !ms.setPositionState) return;
  const now = Date.now();
  if (!force && now - lastPosUpdate < 1000) return;
  lastPosUpdate = now;
  const d = audio.duration;
  if (!Number.isFinite(d) || d <= 0) return;
  try {
    ms.setPositionState({ duration: d, playbackRate: audio.playbackRate || 1, position: clamp(audio.currentTime, 0, d) });
  } catch {
    /* position/duration out of range during a load */
  }
}

if (ms) {
  const set = (action, fn) => {
    try {
      ms.setActionHandler(action, fn);
    } catch {
      /* action not supported in this browser */
    }
  };
  set('play', () => player.play());
  set('pause', () => player.pause());
  set('stop', () => player.pause());
  set('previoustrack', () => player.prev());
  set('nexttrack', () => player.next());
  set('seekto', (d) => player.seek(d.seekTime));
  set('seekbackward', (d) => player.seek(audio.currentTime - (d.seekOffset || 10)));
  set('seekforward', (d) => player.seek(audio.currentTime + (d.seekOffset || 10)));
}
