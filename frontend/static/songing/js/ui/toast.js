import { h } from '../dom.js';

const MAX = 4;

/** toast('Added to Study')  /  toast('Upload failed', {kind: 'error'}) */
export function toast(message, { kind = 'info', timeout = 4000 } = {}) {
  const box = document.getElementById('toasts');
  if (!box) return;
  while (box.children.length >= MAX) box.firstElementChild.remove();
  const el = h('div', { class: `toast toast-${kind}` }, h('span', { text: message }));
  const close = () => {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 200);
  };
  el.append(h('button', { type: 'button', class: 'toast-x', 'aria-label': 'Dismiss', onclick: close }, '×'));
  box.append(el);
  if (timeout) setTimeout(close, timeout);
}
