import { h } from '../dom.js';

/** Friendly empty / error block. action: {label, href} or {label, onclick} */
export function emptyState({ title, text = '', action = null }) {
  return h(
    'div',
    { class: 'empty' },
    h('h2', { class: 'empty-title', text: title }),
    text ? h('p', { class: 'empty-text', text }) : null,
    action
      ? action.href
        ? h('a', { class: 'btn btn-light', href: action.href, text: action.label })
        : h('button', { type: 'button', class: 'btn btn-light', onclick: action.onclick, text: action.label })
      : null,
  );
}
