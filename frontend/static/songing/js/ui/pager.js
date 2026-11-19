// "Load more" button for paginated song lists ({count, next, results}).
import { h } from '../dom.js';
import { api, relativeUrl } from '../api.js';
import { toast } from './toast.js';

/** pager(list, nextUrl, {signal, onLoaded}) -> Node (empty when there is no next page) */
export function pager(list, next, { signal, onLoaded } = {}) {
  const wrap = h('div', { class: 'pager' });
  let url = next ? relativeUrl(next) : null;
  if (!url) return wrap;
  const btn = h('button', { type: 'button', class: 'btn btn-outline', text: 'Load more' });
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    try {
      const page = await api(url, { signal });
      list.append(page.results);
      url = page.next ? relativeUrl(page.next) : null;
      if (onLoaded) onLoaded(page);
      if (!url) wrap.replaceChildren();
    } catch (err) {
      if (err.name !== 'AbortError') toast(err.message, { kind: 'error' });
    }
    btn.disabled = false;
  });
  wrap.append(btn);
  return wrap;
}
