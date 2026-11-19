import { api } from '../api.js';
import { libraryPage } from '../ui/librarypage.js';

export const load = (ctx) => api('/api/library/recent/', { signal: ctx.signal });

export function render(songs, ctx) {
  ctx.setTitle('Recently played');
  return libraryPage({
    title: 'Recently played',
    kind: 'History',
    glyph: 'clock',
    colors: ['#0e6b5c', '#2fd566'],
    page: Array.isArray(songs) ? songs : songs.results || [],
    signal: ctx.signal,
    empty: { title: 'Nothing played yet', text: 'Songs you listen to for 30 seconds show up here.', action: { label: 'Go to Home', href: '/' } },
  });
}
