import { api } from '../api.js';
import { libraryPage } from '../ui/librarypage.js';

export const load = (ctx) => api('/api/library/liked/', { signal: ctx.signal });

export function render(page, ctx) {
  ctx.setTitle('Liked Songs');
  return libraryPage({
    title: 'Liked Songs',
    kind: 'Playlist',
    glyph: 'heartFill',
    colors: ['#5b3cc4', '#a78bfa'],
    page,
    signal: ctx.signal,
    empty: { title: 'Songs you like will appear here', text: 'Tap the heart on any song to save it.', action: { label: 'Find songs', href: '/search' } },
  });
}
