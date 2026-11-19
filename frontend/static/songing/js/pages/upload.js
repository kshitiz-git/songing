import { h } from '../dom.js';
import { api, uploadForm, ApiError } from '../api.js';
import { navigate, loginUrl } from '../router.js';
import { field, checkField, showErrors, formError } from '../ui/form.js';
import { toast } from '../ui/toast.js';

const MB = 1024 * 1024;
const MAX_AUDIO = 25 * MB;
const MAX_COVER = 5 * MB;
const AUDIO_ACCEPT = '.mp3,.m4a,.ogg,.oga,.wav,.flac,audio/mpeg,audio/mp4,audio/ogg,audio/wav,audio/x-wav,audio/flac,audio/x-flac';
const COVER_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';

const mb = (n) => `${(n / MB).toFixed(1)} MB`;

export async function load(ctx) {
  try {
    const genres = await api('/api/genres/', { signal: ctx.signal });
    return { genres: Array.isArray(genres) ? genres : [] };
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    return { genres: [] };
  }
}

export function render(data, ctx) {
  ctx.setTitle('Upload a song');

  const audio = field({
    label: 'Audio file',
    hint: `MP3, M4A, OGG, WAV or FLAC, up to ${MAX_AUDIO / MB} MB.`,
    control: h('input', { type: 'file', name: 'audio', accept: AUDIO_ACCEPT, required: true, class: 'file-input' }),
  });
  const title = field({ label: 'Title', control: h('input', { type: 'text', name: 'title', required: true, maxlength: 200, autocomplete: 'off' }) });
  const artist = field({ label: 'Artist name', control: h('input', { type: 'text', name: 'artist_name', required: true, maxlength: 200, autocomplete: 'off' }) });
  const album = field({ label: 'Album (optional)', control: h('input', { type: 'text', name: 'album_title', maxlength: 200, autocomplete: 'off' }) });
  const genreList = h('datalist', { id: 'genre-options' }, data.genres.map((g) => h('option', { value: g })));
  const genre = field({ label: 'Genre (optional)', control: h('input', { type: 'text', name: 'genre', maxlength: 100, list: 'genre-options', autocomplete: 'off' }) });
  const coverF = field({
    label: 'Cover image (optional)',
    hint: `JPG, PNG or WebP, up to ${MAX_COVER / MB} MB.`,
    control: h('input', { type: 'file', name: 'cover', accept: COVER_ACCEPT, class: 'file-input' }),
  });
  const pub = checkField({
    label: 'Make this song public',
    name: 'is_public',
    hint: 'Public songs appear in search and on Home for everyone. Leave it off to keep the song private to you.',
  });
  const fields = { audio, title, artist_name: artist, album_title: album, genre, cover: coverF, is_public: pub };
  const err = formError();

  const bar = h('div', { class: 'progress-fill' });
  const progressText = h('span', { class: 'progress-text', text: 'Uploading 0%' });
  const cancelBtn = h('button', { type: 'button', class: 'btn btn-ghost', text: 'Cancel upload' });
  const progress = h(
    'div',
    { class: 'progress', hidden: true },
    h('div', { class: 'progress-track', role: 'progressbar', 'aria-label': 'Upload progress', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': 0 }, bar),
    h('div', { class: 'progress-row' }, progressText, cancelBtn),
  );
  const submit = h('button', { type: 'submit', class: 'btn btn-accent btn-lg', text: 'Upload song' });
  const form = h(
    'form',
    { class: 'form form-wide', novalidate: true },
    err.el,
    audio.el,
    title.el,
    artist.el,
    album.el,
    genre.el,
    genreList,
    coverF.el,
    pub.el,
    progress,
    h('div', { class: 'form-actions' }, submit, h('a', { class: 'btn btn-ghost', href: '/uploads', text: 'Cancel' })),
  );

  // Size / type checks as soon as a file is picked.
  function checkAudio() {
    const f = audio.control.files[0];
    if (!f) return null;
    if (f.size > MAX_AUDIO) {
      audio.setError(`This file is ${mb(f.size)}. The limit is ${MAX_AUDIO / MB} MB.`);
      return false;
    }
    audio.setError('');
    return true;
  }
  function checkCover() {
    const f = coverF.control.files[0];
    if (!f) {
      coverF.setError('');
      return true;
    }
    if (f.size > MAX_COVER) {
      coverF.setError(`This image is ${mb(f.size)}. The limit is ${MAX_COVER / MB} MB.`);
      return false;
    }
    if (f.type && !f.type.startsWith('image/')) {
      coverF.setError('Pick an image file (JPG, PNG or WebP).');
      return false;
    }
    coverF.setError('');
    return true;
  }
  audio.control.addEventListener('change', () => {
    const f = audio.control.files[0];
    if (checkAudio() && f && !title.control.value.trim()) {
      title.control.value = f.name.replace(/\.[^.]+$/, '').replace(/[_]+/g, ' ').trim().slice(0, 200);
    }
  });
  coverF.control.addEventListener('change', checkCover);

  let current = null;
  function setBusy(busy) {
    for (const el of form.querySelectorAll('input, button[type=submit]')) el.disabled = busy;
    progress.hidden = !busy;
  }
  function setProgress(frac) {
    const pct = Math.round(frac * 100);
    bar.style.width = `${pct}%`;
    progress.querySelector('[role=progressbar]').setAttribute('aria-valuenow', String(pct));
    progressText.textContent = pct >= 100 ? 'Upload finished, processing the file...' : `Uploading ${pct}%`;
  }

  cancelBtn.addEventListener('click', () => current && current.abort());

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    err.set('');
    for (const f of Object.values(fields)) f.setError('');
    let bad = null;
    if (!audio.control.files[0]) {
      audio.setError('Choose an audio file.');
      bad = bad || audio.control;
    } else if (checkAudio() === false) bad = bad || audio.control;
    if (!title.control.value.trim()) {
      title.setError('Enter a title.');
      bad = bad || title.control;
    }
    if (!artist.control.value.trim()) {
      artist.setError('Enter the artist name.');
      bad = bad || artist.control;
    }
    if (!checkCover()) bad = bad || coverF.control;
    if (bad) {
      bad.focus();
      return;
    }

    const fd = new FormData();
    fd.append('audio', audio.control.files[0]);
    fd.append('title', title.control.value.trim());
    fd.append('artist_name', artist.control.value.trim());
    if (album.control.value.trim()) fd.append('album_title', album.control.value.trim());
    if (genre.control.value.trim()) fd.append('genre', genre.control.value.trim());
    if (coverF.control.files[0]) fd.append('cover', coverF.control.files[0]);
    fd.append('is_public', pub.control.checked ? 'true' : 'false');

    setProgress(0);
    setBusy(true);
    current = uploadForm('/api/songs/', fd, setProgress);
    try {
      const song = await current.promise;
      toast(`"${song.title}" uploaded`);
      navigate('/uploads');
    } catch (ex) {
      setBusy(false);
      if (ex && ex.name === 'AbortError') {
        err.set('Upload cancelled.');
      } else if (ex instanceof ApiError && (ex.status === 401 || ex.status === 403) && !ex.fields.audio) {
        navigate(loginUrl('/upload'));
      } else if (ex instanceof ApiError && ex.status === 413) {
        err.set('The file is too large for the server.');
      } else {
        const rest = showErrors(fields, ex);
        err.set(rest);
        const firstBad = form.querySelector('[aria-invalid="true"]');
        if (firstBad) firstBad.focus();
        else err.el.scrollIntoView({ block: 'nearest' });
      }
    } finally {
      current = null;
    }
  });

  return {
    el: h('div', { class: 'form-page' }, h('h1', { class: 'page-title', text: 'Upload a song' }), h('p', { class: 'lead', text: 'Add your own music to Songing. Only upload songs you have the right to share.' }), form),
    destroy() {
      if (current) current.abort();
    },
  };
}
