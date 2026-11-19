"""Browse endpoints: songs, albums, artists, genres, home. Checks the JSON shapes of docs/api.md."""
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone

from music.models import Album, Artist, Like, Song

from .base import MusicTestCase, ids, make_image, make_song

SONG_KEYS = {
    "id", "title", "artist", "album", "duration", "genre", "cover_url", "colors", "stream_url",
    "play_count", "is_liked", "is_public", "is_owner", "license", "attribution", "source_url",
    "created_at",
}
ALBUM_KEYS = {"id", "title", "artist", "year", "cover_url", "colors", "song_count"}
ARTIST_KEYS = {"id", "name", "image_url", "colors", "song_count"}
HEX_COLOR = r"^#[0-9a-f]{6}$"


class SongShapeTests(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.song = make_song(
            "Carefree", artist="Kevin MacLeod", album="Lo-fi Nights", genre="Lo-fi",
            license="CC BY 4.0", attribution="Kevin MacLeod (incompetech.com)",
            source_url="https://incompetech.com/", play_count=12,
        )
        self.url = f"/api/songs/{self.song.id}/"

    def test_detail_has_exactly_the_documented_fields(self):
        self.assertEqual(set(self.anon.get(self.url).json()), SONG_KEYS)

    def test_detail_values(self):
        data = self.anon.get(self.url).json()
        self.assertEqual(data["id"], self.song.id)
        self.assertEqual(data["title"], "Carefree")
        self.assertEqual(data["artist"], {"id": self.song.artist_id, "name": "Kevin MacLeod"})
        self.assertEqual(data["album"], {"id": self.song.album_id, "title": "Lo-fi Nights"})
        self.assertEqual(data["duration"], 2.0)
        self.assertEqual(data["genre"], "Lo-fi")
        self.assertEqual(data["stream_url"], f"/api/songs/{self.song.id}/stream/")
        self.assertEqual(data["play_count"], 12)
        self.assertTrue(data["is_public"])
        self.assertEqual(data["license"], "CC BY 4.0")
        self.assertEqual(data["attribution"], "Kevin MacLeod (incompetech.com)")
        self.assertEqual(data["source_url"], "https://incompetech.com/")

    def test_created_at_is_an_iso_utc_string(self):
        self.assertRegex(self.anon.get(self.url).json()["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*Z$")

    def test_song_without_album_has_null_album_and_empty_genre(self):
        song = make_song("Single")
        data = self.anon.get(f"/api/songs/{song.id}/").json()
        self.assertIsNone(data["album"])
        self.assertEqual(data["genre"], "")

    def test_colors_are_two_hex_values_and_stable(self):
        first = self.anon.get(self.url).json()["colors"]
        second = self.bob_api.get(self.url).json()["colors"]
        self.assertEqual(len(first), 2)
        for color in first:
            self.assertRegex(color, HEX_COLOR)
        self.assertEqual(first, second)

    def test_songs_of_one_album_share_their_colors(self):
        other = make_song("Same album", artist="Kevin MacLeod", album="Lo-fi Nights")
        mine = self.anon.get(self.url).json()["colors"]
        theirs = self.anon.get(f"/api/songs/{other.id}/").json()["colors"]
        self.assertEqual(mine, theirs)

    def test_cover_url_is_null_without_a_cover(self):
        self.assertIsNone(self.anon.get(self.url).json()["cover_url"])

    def test_cover_url_points_under_media_when_there_is_a_cover(self):
        song = make_song("Covered", cover=ContentFile(make_image(), name="c.jpg"))
        cover_url = self.anon.get(f"/api/songs/{song.id}/").json()["cover_url"]
        self.assertTrue(cover_url.startswith("/media/covers/") and cover_url.endswith(".jpg"), cover_url)

    def test_is_owner_is_false_for_everyone_but_the_uploader(self):
        song = make_song("Alices", uploader=self.alice)
        url = f"/api/songs/{song.id}/"
        self.assertTrue(self.alice_api.get(url).json()["is_owner"])
        self.assertFalse(self.bob_api.get(url).json()["is_owner"])
        self.assertFalse(self.anon.get(url).json()["is_owner"])

    def test_unknown_song_is_404_with_the_plain_message(self):
        response = self.anon.get("/api/songs/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})


class SongListTests(MusicTestCase):
    def test_list_is_paginated_with_the_documented_envelope(self):
        make_song("One")
        data = self.anon.get("/api/songs/").json()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        self.assertEqual((data["count"], data["next"], data["previous"]), (1, None, None))
        self.assertEqual(set(data["results"][0]), SONG_KEYS)

    def test_logged_out_visitor_sees_public_songs_only(self):
        public = make_song("Public")
        make_song("Private", uploader=self.alice, is_public=False)
        self.assertEqual(ids(self.anon.get("/api/songs/").json()["results"]), [public.id])

    def test_other_users_private_songs_stay_hidden_but_own_ones_show(self):
        make_song("Public")
        mine = make_song("Mine", uploader=self.bob, is_public=False)
        make_song("Alices", uploader=self.alice, is_public=False)
        listed = ids(self.bob_api.get("/api/songs/").json()["results"])
        self.assertIn(mine.id, listed)
        self.assertEqual(len(listed), 2)

    def test_most_played_first_then_by_title(self):
        quiet_b, quiet_a = make_song("B quiet"), make_song("A quiet")
        hit = make_song("Hit", play_count=9)
        self.assertEqual(ids(self.anon.get("/api/songs/").json()["results"]), [hit.id, quiet_a.id, quiet_b.id])

    def test_q_filters_by_title_ignoring_case(self):
        match, _ = make_song("Blue Monday"), make_song("Red Sunday")
        self.assertEqual(ids(self.anon.get("/api/songs/", {"q": "BLUE"}).json()["results"]), [match.id])

    def test_q_filters_by_artist_name(self):
        match, _ = make_song("Anything", artist="Fleetwood"), make_song("Else", artist="Other")
        self.assertEqual(ids(self.anon.get("/api/songs/", {"q": "fleet"}).json()["results"]), [match.id])

    def test_genre_filter_ignores_case(self):
        match, _ = make_song("A", genre="Lo-fi"), make_song("B", genre="Rock")
        self.assertEqual(ids(self.anon.get("/api/songs/", {"genre": "lo-FI"}).json()["results"]), [match.id])

    def test_q_and_genre_combine(self):
        match = make_song("Blue Monday", genre="Pop")
        make_song("Blue Sky", genre="Rock")
        make_song("Green Day", genre="Pop")
        found = self.anon.get("/api/songs/", {"q": "blue", "genre": "pop"}).json()["results"]
        self.assertEqual(ids(found), [match.id])

    def test_page_size_is_30_and_page_2_has_the_rest(self):
        for number in range(31):
            make_song(f"Song {number:02d}", uploader=self.alice)
        first = self.alice_api.get("/api/songs/").json()
        self.assertEqual((first["count"], len(first["results"])), (31, 30))
        self.assertIsNotNone(first["next"])
        self.assertIsNone(first["previous"])
        second = self.alice_api.get("/api/songs/?page=2").json()
        self.assertEqual(len(second["results"]), 1)
        self.assertIsNone(second["next"])
        self.assertIsNotNone(second["previous"])
        self.assertEqual(len(set(ids(first["results"])) | set(ids(second["results"]))), 31)

    def test_liked_and_uploads_libraries_are_paginated_the_same_way(self):
        for number in range(31):
            song = make_song(f"Song {number:02d}", uploader=self.alice)
            Like.objects.create(user=self.alice, song=song)
        for url in ("/api/library/liked/", "/api/library/uploads/"):
            with self.subTest(url=url):
                page = self.alice_api.get(url).json()
                self.assertEqual((page["count"], len(page["results"])), (31, 30))
                self.assertEqual(len(self.alice_api.get(f"{url}?page=2").json()["results"]), 1)

    def test_page_past_the_end_is_404(self):
        make_song("One")
        response = self.anon.get("/api/songs/?page=99")
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())


class AlbumTests(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.third = make_song("Third", artist="Duo", album="Record", track_number=3)
        self.first = make_song("First", artist="Duo", album="Record", track_number=1)
        self.untracked = make_song("Untracked", artist="Duo", album="Record")
        self.album = Album.objects.get(title="Record")

    def test_list_item_has_the_documented_fields(self):
        data = self.anon.get("/api/albums/").json()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        item = data["results"][0]
        self.assertEqual(set(item), ALBUM_KEYS)
        self.assertEqual(item["title"], "Record")
        self.assertEqual(item["artist"], {"id": self.album.artist_id, "name": "Duo"})
        self.assertEqual(item["song_count"], 3)
        self.assertIsNone(item["cover_url"])
        self.assertEqual(len(item["colors"]), 2)

    def test_detail_is_the_list_item_plus_songs(self):
        detail = self.anon.get(f"/api/albums/{self.album.id}/").json()
        self.assertEqual(set(detail), ALBUM_KEYS | {"songs"})
        self.assertEqual(set(detail["songs"][0]), SONG_KEYS)

    def test_songs_come_in_track_order_with_untracked_last(self):
        songs = self.anon.get(f"/api/albums/{self.album.id}/").json()["songs"]
        self.assertEqual(ids(songs), [self.first.id, self.third.id, self.untracked.id])

    def test_album_without_visible_songs_is_not_listed(self):
        Album.objects.create(title="Empty", artist=self.album.artist)
        titles = [item["title"] for item in self.anon.get("/api/albums/").json()["results"]]
        self.assertEqual(titles, ["Record"])

    def test_empty_album_is_404(self):
        empty = Album.objects.create(title="Empty", artist=self.album.artist)
        self.assertEqual(self.anon.get(f"/api/albums/{empty.id}/").status_code, 404)

    def test_unknown_album_is_404_with_the_plain_message(self):
        response = self.anon.get("/api/albums/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_list_is_sorted_by_title(self):
        make_song("Z", artist="Other", album="Alpha")
        titles = [item["title"] for item in self.anon.get("/api/albums/").json()["results"]]
        self.assertEqual(titles, ["Alpha", "Record"])

    def test_album_cover_comes_from_a_song_cover(self):
        make_song("Covered", artist="Duo", album="Record", track_number=0, cover=ContentFile(make_image(), name="c.jpg"))
        cover_url = self.anon.get(f"/api/albums/{self.album.id}/").json()["cover_url"]
        self.assertTrue(cover_url.startswith("/media/covers/"), cover_url)


class ArtistTests(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.hit = make_song("Hit", artist="Kevin MacLeod", album="Old", play_count=50)
        self.deep_cut = make_song("Deep cut", artist="Kevin MacLeod", album="New", play_count=1)
        self.artist = self.hit.artist
        Album.objects.filter(title="Old").update(year=2010)
        Album.objects.filter(title="New").update(year=2020)

    def test_list_item_has_the_documented_fields(self):
        data = self.anon.get("/api/artists/").json()
        self.assertEqual(set(data), {"count", "next", "previous", "results"})
        item = data["results"][0]
        self.assertEqual(set(item), ARTIST_KEYS)
        self.assertEqual(item["name"], "Kevin MacLeod")
        self.assertEqual(item["song_count"], 2)
        self.assertIsNone(item["image_url"])

    def test_detail_is_the_list_item_plus_bio_top_songs_and_albums(self):
        detail = self.anon.get(f"/api/artists/{self.artist.id}/").json()
        self.assertEqual(set(detail), ARTIST_KEYS | {"bio", "top_songs", "albums"})
        self.assertEqual(detail["bio"], "")
        self.assertEqual(set(detail["top_songs"][0]), SONG_KEYS)
        self.assertEqual(set(detail["albums"][0]), ALBUM_KEYS)

    def test_top_songs_are_ordered_by_play_count(self):
        top = self.anon.get(f"/api/artists/{self.artist.id}/").json()["top_songs"]
        self.assertEqual(ids(top), [self.hit.id, self.deep_cut.id])

    def test_top_songs_stop_at_ten(self):
        for number in range(11):
            make_song(f"Extra {number}", artist="Kevin MacLeod")
        top = self.anon.get(f"/api/artists/{self.artist.id}/").json()["top_songs"]
        self.assertEqual(len(top), 10)

    def test_albums_are_listed_newest_year_first(self):
        albums = self.anon.get(f"/api/artists/{self.artist.id}/").json()["albums"]
        self.assertEqual([album["title"] for album in albums], ["New", "Old"])

    def test_detail_leaves_out_other_artists_albums_and_songs(self):
        other = make_song("Elsewhere", artist="Someone Else", album="Not Kevin's")
        detail = self.anon.get(f"/api/artists/{self.artist.id}/").json()
        self.assertNotIn(other.id, ids(detail["top_songs"]))
        self.assertNotIn(other.album_id, ids(detail["albums"]))

    def test_list_is_sorted_by_name(self):
        make_song("A", artist="Abba")
        names = [item["name"] for item in self.anon.get("/api/artists/").json()["results"]]
        self.assertEqual(names, ["Abba", "Kevin MacLeod"])

    def test_artist_without_visible_songs_is_not_listed_and_is_404(self):
        empty = Artist.objects.create(name="Nobody")
        self.assertNotIn(empty.id, ids(self.anon.get("/api/artists/").json()["results"]))
        self.assertEqual(self.anon.get(f"/api/artists/{empty.id}/").status_code, 404)

    def test_unknown_artist_is_404_with_the_plain_message(self):
        response = self.anon.get("/api/artists/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})


class GenreTests(MusicTestCase):
    def test_lists_each_genre_once_sorted(self):
        make_song("A", genre="Rock")
        make_song("B", genre="Ambient")
        make_song("C", genre="Rock")
        self.assertEqual(self.anon.get("/api/genres/").json(), ["Ambient", "Rock"])

    def test_songs_without_a_genre_add_nothing(self):
        make_song("A", genre="")
        self.assertEqual(self.anon.get("/api/genres/").json(), [])

    def test_empty_library_gives_an_empty_list(self):
        self.assertEqual(self.anon.get("/api/genres/").json(), [])


class HomeTests(MusicTestCase):
    def test_home_has_the_five_documented_lists(self):
        data = self.anon.get("/api/home/").json()
        self.assertEqual(set(data), {"trending", "new_releases", "artists", "recently_played", "made_for_you"})

    def test_empty_library_gives_five_empty_lists(self):
        data = self.anon.get("/api/home/").json()
        self.assertEqual(data, {key: [] for key in data})

    def test_item_shapes(self):
        make_song("Song", artist="Artist", album="Album")
        data = self.anon.get("/api/home/").json()
        self.assertEqual(set(data["trending"][0]), SONG_KEYS)
        self.assertEqual(set(data["new_releases"][0]), ALBUM_KEYS)
        self.assertEqual(set(data["artists"][0]), ARTIST_KEYS)
        self.assertEqual(set(data["made_for_you"][0]), SONG_KEYS)

    def test_new_releases_are_albums_newest_first(self):
        made = []
        for number in range(3):
            song = make_song(f"Song {number}", artist=f"Artist {number}", album=f"Album {number}")
            made.append(song.album_id)
            Album.objects.filter(pk=song.album_id).update(created_at=timezone.now() - timedelta(days=10 - number))
        self.assertEqual(ids(self.anon.get("/api/home/").json()["new_releases"]), made[::-1])

    def test_lists_stop_at_ten(self):
        for number in range(12):
            make_song(f"Song {number}", artist=f"Artist {number}", album=f"Album {number}")
        data = self.anon.get("/api/home/").json()
        for key in ("trending", "new_releases", "artists", "made_for_you"):
            with self.subTest(list=key):
                self.assertEqual(len(data[key]), 10)

    def test_artists_are_ordered_by_total_plays(self):
        quiet = make_song("Quiet", artist="Quiet Band", play_count=1)
        loud = make_song("Loud", artist="Loud Band", play_count=40)
        self.assertEqual(ids(self.anon.get("/api/home/").json()["artists"]), [loud.artist_id, quiet.artist_id])

    def test_made_for_you_leaves_out_other_users_private_songs(self):
        make_song("Alices", uploader=self.alice, is_public=False)
        public = make_song("Public")
        for _ in range(5):  # the pick is random, so look more than once
            self.assertEqual(ids(self.bob_api.get("/api/home/").json()["made_for_you"]), [public.id])

    def test_made_for_you_includes_the_users_own_private_songs(self):
        mine = make_song("Alices", uploader=self.alice, is_public=False)
        public = make_song("Public")
        picks = ids(self.alice_api.get("/api/home/").json()["made_for_you"])
        self.assertEqual(sorted(picks), sorted([mine.id, public.id]))

    def test_made_for_you_for_a_logged_in_user_stays_within_ten(self):
        for number in range(12):
            make_song(f"Song {number}", genre="Pop")
        self.alice_api.post(f"/api/songs/{Song.objects.first().id}/like/")
        self.assertLessEqual(len(self.alice_api.get("/api/home/").json()["made_for_you"]), 10)
