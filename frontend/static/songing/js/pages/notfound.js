import { h } from '../dom.js';

export function render() {
  return h(
    'div',
    { class: 'empty notfound' },
    h('p', { class: 'notfound-code', 'aria-hidden': 'true', text: '404' }),
    h('h1', { class: 'empty-title', text: 'Page not found' }),
    h('p', { class: 'empty-text', text: 'This page does not exist, or it is private. Check the link and try again.' }),
    h('a', { class: 'btn btn-light', href: '/', text: 'Back to Home' }),
  );
}
