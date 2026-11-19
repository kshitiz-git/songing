# Songing API

JSON over HTTP, served by Django REST Framework under `/api/`. The single-page frontend is served by
Django at every other path (`/`, `/search`, `/album/3`, ...), so a page refresh works on any route.

## Conventions

- Auth is the Django session cookie. Every `POST`, `PATCH`, `PUT`, `DELETE` must send the header
  `X-CSRFToken: <value of the csrftoken cookie>`; the page that serves the app sets that cookie.
- Requests and responses are JSON (`Content-Type: application/json`), except the song upload
  (`multipart/form-data`) and the audio stream.
- Errors: status 400 with `{"field": ["message"], ...}` or `{"detail": "message"}`; 401/403 with
  `{"detail": "..."}`; 404 with `{"detail": "Not found."}`.
- Lists that can grow are paginated: `{"count": n, "next": url|null, "previous": url|null,
  "results": [...]}`, 30 per page, `?page=2`.
- Ids are integers. Durations are seconds (float). Times are ISO 8601 UTC strings.

## Shapes

```jsonc
// User
{"id": 1, "username": "kshitiz", "email": "a@b.c"}

// ArtistRef / AlbumRef (embedded)
{"id": 2, "name": "Kevin MacLeod"}
{"id": 5, "title": "Lo-fi Nights"}

// Song
{
  "id": 7,
  "title": "Carefree",
  "artist": {"id": 2, "name": "Kevin MacLeod"},
  "album": {"id": 5, "title": "Lo-fi Nights"},   // or null
  "duration": 183.4,
  "genre": "Lo-fi",                              // "" when unknown
  "cover_url": "/media/covers/ab12.jpg",         // or null -> draw a gradient from "colors"
  "colors": ["#3b1f6e", "#ff6b4a"],              // two hex colours, stable per song/album
  "stream_url": "/api/songs/7/stream/",
  "play_count": 12,
  "is_liked": false,                             // always false when logged out
  "is_public": true,
  "is_owner": false,                             // true when the logged-in user uploaded it
  "license": "CC BY 4.0",                        // "" for user uploads
  "attribution": "\"Carefree\" Kevin MacLeod (incompetech.com) ...",
  "source_url": "https://...",                   // "" when none
  "created_at": "2026-11-19T10:00:00Z"
}

// Album (list item)
{"id": 5, "title": "Lo-fi Nights", "artist": {"id": 2, "name": "..."}, "year": 2014,
 "cover_url": null, "colors": ["#..", "#.."], "song_count": 4}

// Album (detail) = Album list item + {"songs": [Song, ...]} ordered by track number

// Artist (list item)
{"id": 2, "name": "Kevin MacLeod", "image_url": null, "colors": ["#..", "#.."], "song_count": 9}

// Artist (detail) = Artist list item + {"bio": "", "top_songs": [Song x up to 10],
//                                       "albums": [Album list item, ...]}

// Playlist (list item)
{"id": 3, "name": "Study", "description": "", "is_public": false,
 "owner": {"id": 1, "username": "kshitiz"}, "is_owner": true,
 "colors": ["#..", "#.."], "cover_urls": ["/media/..", ...],   // up to 4 song covers, may be []
 "song_count": 12, "duration": 2400.5, "updated_at": "..."}

// Playlist (detail) = Playlist list item + {"songs": [Song, ...]} in playlist order
```

## Endpoints

### Auth
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/api/auth/me/` | | `{"user": User}` or `{"user": null}` |
| POST | `/api/auth/signup/` | `{"username", "password", "email"?}` | 201 `{"user": User}`, now logged in. 400 on taken username / weak password |
| POST | `/api/auth/login/` | `{"username", "password"}` | 200 `{"user": User}`; 400 `{"detail": "Wrong username or password."}` |
| POST | `/api/auth/logout/` | | 204 |

Auth endpoints are rate limited (429 `{"detail": ...}` when exceeded).

### Browse
| Method | Path | Result |
|---|---|---|
| GET | `/api/home/` | `{"trending": [Song x<=10], "new_releases": [Album x<=10], "artists": [Artist x<=10], "recently_played": [Song x<=10], "made_for_you": [Song x<=10]}`. `recently_played` is `[]` when logged out. Trending = most plays in the last 7 days, then all-time plays |
| GET | `/api/songs/?q=&genre=&page=` | paginated Song list (public songs + the user's own private uploads) |
| GET | `/api/songs/<id>/` | Song |
| GET | `/api/albums/?page=` / `/api/albums/<id>/` | paginated Album list / Album detail |
| GET | `/api/artists/?page=` / `/api/artists/<id>/` | paginated Artist list / Artist detail |
| GET | `/api/genres/` | `["Ambient", "Lo-fi", ...]` (genres that have at least one visible song) |
| GET | `/api/search/?q=` | `{"songs": [Song x<=20], "artists": [Artist x<=10], "albums": [Album x<=10], "playlists": [Playlist x<=10]}`; empty lists when `q` is blank. Matches title / name, case-insensitive. Playlists = public ones + the user's own |

### Playback
| Method | Path | Result |
|---|---|---|
| GET | `/api/songs/<id>/stream/` | the audio file. Supports `Range: bytes=a-b` (206 Partial Content), so seeking works. Private song of another user: 404 |
| POST | `/api/songs/<id>/play/` | 204. Records one play (counts toward trending and, when logged in, recently played). The frontend calls it once per song after 30 s of listening, or at the end of a song shorter than 30 s |

### Your library (logged in; 403 otherwise)
| Method | Path | Body | Result |
|---|---|---|---|
| POST | `/api/songs/<id>/like/` | | 204 (idempotent) |
| DELETE | `/api/songs/<id>/like/` | | 204 (idempotent) |
| GET | `/api/library/liked/?page=` | | paginated Song list, newest like first |
| GET | `/api/library/recent/` | | `[Song x<=30]`, newest play first, no duplicates |
| GET | `/api/library/uploads/?page=` | | paginated Song list the user uploaded |
| POST | `/api/songs/` | multipart: `audio` (file, required; mp3/m4a/ogg/wav/flac, <= 25 MB), `title` (required), `artist_name` (required), `album_title`, `genre`, `cover` (image, <= 5 MB), `is_public` (`true`/`false`, default false) | 201 Song. 400 when the file is not real audio |
| DELETE | `/api/songs/<id>/` | | 204, owner only (403 otherwise) |

### Playlists
| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/api/playlists/` | | `[Playlist]` the user owns, newest update first (logged in) |
| POST | `/api/playlists/` | `{"name", "description"?, "is_public"?}` | 201 Playlist detail. Name 1..100 chars |
| GET | `/api/playlists/<id>/` | | Playlist detail. Someone else's private playlist: 404 |
| PATCH | `/api/playlists/<id>/` | any of `name`, `description`, `is_public` | 200 Playlist detail, owner only |
| DELETE | `/api/playlists/<id>/` | | 204, owner only |
| POST | `/api/playlists/<id>/songs/` | `{"song_id"}` | 201 Playlist detail; adding a song already in it returns 200 unchanged |
| DELETE | `/api/playlists/<id>/songs/<song_id>/` | | 204 |
| POST | `/api/playlists/<id>/reorder/` | `{"song_ids": [ids in the new order]}` | 200 Playlist detail. Must contain exactly the playlist's songs, else 400 |
