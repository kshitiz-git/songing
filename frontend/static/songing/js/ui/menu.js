// Popup menu anchored to a trigger button. Arrow keys, Home/End, Esc, outside click.
// items: [{label, icon?, danger?, disabled?, keepOpen?, separator?, onSelect(ctrl)}]
// ctrl.setItems(items) swaps the content (used for the "Add to playlist" sub view).
import { h, icon } from '../dom.js';

let active = null;

export function closeMenu() {
  if (active) active.close();
}

export function openMenu(trigger, items, { label = 'Menu' } = {}) {
  closeMenu();
  const backdrop = h('div', { class: 'menu-backdrop' });
  const menu = h('div', { class: 'menu', role: 'menu', 'aria-label': label });
  let closed = false;

  function build(list) {
    menu.replaceChildren(
      ...list.map((item) => {
        if (item.separator) return h('div', { class: 'menu-sep', role: 'separator' });
        if (item.heading) return h('div', { class: 'menu-heading', text: item.heading });
        const btn = h(
          'button',
          {
            type: 'button',
            role: 'menuitem',
            class: `menu-item${item.danger ? ' danger' : ''}`,
            disabled: item.disabled,
            onclick: () => {
              if (!item.keepOpen) close();
              if (item.onSelect) item.onSelect(ctrl);
            },
          },
          item.icon ? icon(item.icon) : h('span', { class: 'ico' }),
          h('span', { class: 'menu-label', text: item.label }),
        );
        return btn;
      }),
    );
  }

  function position() {
    if (window.matchMedia('(max-width: 699.98px)').matches) {
      menu.style.top = '';
      menu.style.left = '';
      return;
    }
    const r = trigger.getBoundingClientRect();
    const mw = menu.offsetWidth;
    const mh = menu.offsetHeight;
    let left = r.right - mw;
    let top = r.bottom + 4;
    if (left < 8) left = 8;
    if (left + mw > innerWidth - 8) left = innerWidth - mw - 8;
    if (top + mh > innerHeight - 8) top = Math.max(8, r.top - mh - 4);
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
  }

  function focusables() {
    return [...menu.querySelectorAll('.menu-item:not([disabled])')];
  }

  function onKey(e) {
    const list = focusables();
    const i = list.indexOf(document.activeElement);
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      close(true);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      list[(i + 1) % list.length]?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      list[(i - 1 + list.length) % list.length]?.focus();
    } else if (e.key === 'Home') {
      e.preventDefault();
      list[0]?.focus();
    } else if (e.key === 'End') {
      e.preventDefault();
      list[list.length - 1]?.focus();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      close(true);
    }
  }

  function close(restoreFocus = false) {
    if (closed) return;
    closed = true;
    document.removeEventListener('keydown', onKey, true);
    removeEventListener('resize', dismiss);
    document.getElementById('main')?.removeEventListener('scroll', dismiss);
    backdrop.remove();
    menu.remove();
    trigger.setAttribute('aria-expanded', 'false');
    if (active === ctrl) active = null;
    if (restoreFocus && trigger.isConnected) trigger.focus();
  }

  const dismiss = () => close(false);
  const ctrl = {
    close,
    setItems(list) {
      build(list);
      position();
      (focusables()[0] || menu).focus();
    },
  };

  build(items);
  backdrop.addEventListener('mousedown', () => close());
  backdrop.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    close();
  });
  document.body.append(backdrop, menu);
  trigger.setAttribute('aria-expanded', 'true');
  position();
  document.addEventListener('keydown', onKey, true);
  addEventListener('resize', dismiss);
  document.getElementById('main')?.addEventListener('scroll', dismiss, { passive: true });
  menu.tabIndex = -1;
  (focusables()[0] || menu).focus();
  active = ctrl;
  return ctrl;
}
