import { h, icon } from '../dom.js';
import { api } from '../api.js';
import { libraryPage } from '../ui/librarypage.js';

export const load = (ctx) => api('/api/library/uploads/', { signal: ctx.signal });

export function render(page, ctx) {
  ctx.setTitle('My uploads');
  return libraryPage({
    title: 'My uploads',
    kind: 'Library',
    glyph: 'note',
    colors: ['#9a3b1f', '#ffb454'],
    page,
    signal: ctx.signal,
    listOptions: { deletable: true, showPrivate: true, showAlbum: true },
    extraActions: [h('a', { class: 'btn btn-outline', href: '/upload' }, icon('upload'), h('span', { text: 'Upload a song' }))],
    empty: { title: 'You have not uploaded anything', text: 'Add an MP3, M4A, OGG, WAV or FLAC file. Uploads are private until you make them public.', action: { label: 'Upload a song', href: '/upload' } },
  });
}
