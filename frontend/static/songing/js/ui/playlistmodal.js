// Create / edit playlist dialog. Resolves with the saved playlist (detail) or null when cancelled.
import { h } from '../dom.js';
import { api } from '../api.js';
import { store, refreshPlaylists } from '../store.js';
import { modal } from './modal.js';
import { field, checkField, showErrors, formError } from './form.js';

export function playlistModal({ playlist = null } = {}) {
  const editing = !!playlist;
  const name = field({
    label: 'Name',
    control: h('input', {
      type: 'text',
      name: 'name',
      required: true,
      maxlength: 100,
      autocomplete: 'off',
      value: editing ? playlist.name : `My playlist #${store.playlists.length + 1}`,
    }),
  });
  const description = field({
    label: 'Description (optional)',
    control: h('textarea', { name: 'description', rows: 3, maxlength: 500, placeholder: 'What is this playlist for?' }),
  });
  description.control.value = editing ? playlist.description || '' : '';
  const pub = checkField({
    label: 'Public playlist',
    name: 'is_public',
    checked: editing ? !!playlist.is_public : false,
    hint: 'Public playlists show up in search for everyone.',
  });
  const err = formError();
  const cancel = h('button', { type: 'button', class: 'btn btn-ghost', text: 'Cancel' });
  const save = h('button', { type: 'submit', class: 'btn btn-accent', text: editing ? 'Save' : 'Create' });

  const form = h('form', { class: 'form', novalidate: true }, err.el, name.el, description.el, pub.el, h('div', { class: 'modal-footer inline' }, cancel, save));
  const m = modal({ title: editing ? 'Edit playlist' : 'Create playlist', body: form });
  name.control.select();
  cancel.addEventListener('click', () => m.close(null));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nm = name.control.value.trim();
    err.set('');
    if (!nm) {
      name.setError('Give the playlist a name.');
      name.control.focus();
      return;
    }
    save.disabled = true;
    try {
      const body = { name: nm, description: description.control.value.trim(), is_public: pub.control.checked };
      const saved = editing
        ? await api(`/api/playlists/${playlist.id}/`, { method: 'PATCH', body })
        : await api('/api/playlists/', { method: 'POST', body });
      refreshPlaylists();
      m.close(saved);
    } catch (ex) {
      save.disabled = false;
      const rest = showErrors({ name, description, is_public: pub }, ex);
      err.set(rest);
    }
  });

  return m.closed.then((v) => v || null);
}
