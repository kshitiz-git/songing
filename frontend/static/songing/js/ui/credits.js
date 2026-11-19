// Licence / attribution list for the songs on a page (Creative Commons tracks must be credited).
import { h, safeUrl } from '../dom.js';

export function credits(songs) {
  const rows = songs.filter((s) => s.attribution || s.license);
  if (!rows.length) return null;
  return h(
    'details',
    { class: 'credits' },
    h('summary', { text: 'Music credits and licences' }),
    h(
      'ul',
      {},
      rows.map((s) => {
        const src = safeUrl(s.source_url);
        return h(
          'li',
          {},
          h('strong', { text: s.title }),
          s.attribution ? h('span', { text: ` ${s.attribution}` }) : null,
          s.license ? h('span', { class: 'lic', text: ` Licence: ${s.license}.` }) : null,
          src ? h('a', { href: src, target: '_blank', rel: 'noopener noreferrer', text: ' Source' }) : null,
        );
      }),
    ),
  );
}
