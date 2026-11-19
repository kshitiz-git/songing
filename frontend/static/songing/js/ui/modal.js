// In-page dialogs. Never window.alert / confirm / prompt.
import { h, uid } from '../dom.js';

let open = 0;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * modal({title, body, footer, wide}) -> {el, close(value), closed: Promise<value>}
 * Esc and a click on the backdrop close it with value undefined.
 */
export function modal({ title, body, footer, wide = false }) {
  const previous = document.activeElement;
  const titleId = uid('modal-title');
  const dialog = h(
    'div',
    { class: `modal${wide ? ' modal-wide' : ''}`, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': titleId, tabindex: '-1' },
    h('h2', { class: 'modal-title', id: titleId, text: title }),
    h('div', { class: 'modal-body' }, body),
    footer ? h('div', { class: 'modal-footer' }, footer) : null,
  );
  const backdrop = h('div', { class: 'modal-backdrop' }, dialog);

  let resolve;
  const closed = new Promise((r) => (resolve = r));
  let done = false;

  function close(value) {
    if (done) return;
    done = true;
    document.removeEventListener('keydown', onKey, true);
    backdrop.remove();
    open = Math.max(0, open - 1);
    if (open === 0) {
      const app = document.getElementById('app');
      if (app) app.inert = false;
    }
    if (previous && previous.isConnected && previous.focus) previous.focus();
    resolve(value);
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close(undefined);
    } else if (e.key === 'Tab') {
      const items = [...dialog.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) {
        e.preventDefault();
        return;
      }
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === firstEl || document.activeElement === dialog)) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    }
  }

  backdrop.addEventListener('mousedown', (e) => {
    if (e.target === backdrop) close(undefined);
  });

  document.body.append(backdrop);
  open += 1;
  const app = document.getElementById('app');
  if (app) app.inert = true;
  document.addEventListener('keydown', onKey, true);
  const autofocus = dialog.querySelector('[data-autofocus]') || dialog.querySelector('input, textarea, select') || dialog;
  autofocus.focus();

  return { el: dialog, close, closed };
}

/** In-page confirm. Resolves true / false. */
export function confirmModal({ title, message, confirmText = 'Delete', cancelText = 'Cancel', danger = true }) {
  const cancel = h('button', { type: 'button', class: 'btn btn-ghost', text: cancelText });
  const ok = h('button', { type: 'button', class: `btn ${danger ? 'btn-danger' : 'btn-accent'}`, text: confirmText, 'data-autofocus': '' });
  const m = modal({ title, body: h('p', { class: 'modal-text', text: message }), footer: [cancel, ok] });
  cancel.addEventListener('click', () => m.close(false));
  ok.addEventListener('click', () => m.close(true));
  return m.closed.then((v) => v === true);
}
