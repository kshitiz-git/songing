// Small form helpers: labelled fields with an error line next to each control.
import { h, uid } from '../dom.js';

function wire(control, hintEl, errEl) {
  const ids = [hintEl && hintEl.id, errEl.id].filter(Boolean).join(' ');
  control.setAttribute('aria-describedby', ids);
}

/** Text-like field (input, textarea, select). Returns {el, control, setError(msg)}. */
export function field({ label, control, hint = '', className = '' }) {
  const id = control.id || uid('f');
  control.id = id;
  const err = h('p', { class: 'field-error', id: `${id}-err`, role: 'alert', hidden: true });
  const hintEl = hint ? h('p', { class: 'field-hint', id: `${id}-hint`, text: hint }) : null;
  wire(control, hintEl, err);
  const el = h('div', { class: `field ${className}`.trim() }, h('label', { for: id, text: label }), control, hintEl, err);
  const setError = (msg) => {
    err.textContent = msg || '';
    err.hidden = !msg;
    control.setAttribute('aria-invalid', msg ? 'true' : 'false');
  };
  control.addEventListener('input', () => setError('')); // editing a field clears its error
  return { el, control, setError };
}

/** Checkbox with label text and optional hint. */
export function checkField({ label, name, checked = false, hint = '' }) {
  const control = h('input', { type: 'checkbox', name, checked });
  const id = uid('f');
  control.id = id;
  const err = h('p', { class: 'field-error', id: `${id}-err`, role: 'alert', hidden: true });
  const hintEl = hint ? h('p', { class: 'field-hint', id: `${id}-hint`, text: hint }) : null;
  wire(control, hintEl, err);
  const el = h(
    'div',
    { class: 'field field-check' },
    h('label', { class: 'check', for: id }, control, h('span', { text: label })),
    hintEl,
    err,
  );
  const setError = (msg) => {
    err.textContent = msg || '';
    err.hidden = !msg;
  };
  control.addEventListener('change', () => setError(''));
  return { el, control, setError };
}

/**
 * Show server errors on the matching fields. fields: {name: field}. Returns the leftover message
 * (errors for keys with no field, plus the non-field "_form" message), or ''.
 */
export function showErrors(fields, err) {
  const map = err && err.fields ? err.fields : {};
  let rest = '';
  for (const f of Object.values(fields)) f.setError('');
  for (const [key, msg] of Object.entries(map)) {
    if (fields[key]) fields[key].setError(msg);
    else rest = rest ? `${rest} ${msg}` : msg;
  }
  if (!Object.keys(map).length && err && err.message) rest = err.message;
  return rest;
}

/** Banner for form-level problems (wrong password, 429, network). */
export function formError() {
  const el = h('p', { class: 'form-error', role: 'alert', hidden: true });
  return {
    el,
    set(msg) {
      el.textContent = msg || '';
      el.hidden = !msg;
    },
  };
}
