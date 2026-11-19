"""GET /api/search/?q= : songs, artists, albums and playlists."""
from music.models import Playlist

from .base import MusicTestCase, ids, make_song

SEARCH_URL = "/api/search/"


class SearchTestCase(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.rain = make_song("Midnight Rain", artist="Luna Wave", album="Night Sessions")
        self.sun = make_song("Sunny Day", artist="Solar Band", album="Daylight")
        self.public_mix = Playlist.objects.create(owner=self.bob, name="Rainy Day Mix", is_public=True)
        self.bobs_private = Playlist.objects.create(owner=self.bob, name="Rain Secrets", is_public=False)
        self.alices_private = Playlist.objects.create(owner=self.alice, name="Rain For Alice", is_public=False)

    def search(self, query, api=None):
        return (api or self.anon).get(SEARCH_URL, {"q": query}).json()


class ShapeTests(SearchTestCase):
    def test_result_has_exactly_four_lists(self):
        self.assertEqual(set(self.search("rain")), {"songs", "artists", "albums", "playlists"})

    def test_no_match_gives_four_empty_lists(self):
        self.assertEqual(self.search("zzzzzz"), {"songs": [], "artists": [], "albums": [], "playlists": []})


class BlankQueryTests(SearchTestCase):
    EMPTY = {"songs": [], "artists": [], "albums": [], "playlists": []}

    def test_empty_q_gives_four_empty_lists(self):
        self.assertEqual(self.search(""), self.EMPTY)

    def test_whitespace_q_gives_four_empty_lists(self):
        self.assertEqual(self.search("   "), self.EMPTY)

    def test_missing_q_gives_four_empty_lists(self):
        self.assertEqual(self.anon.get(SEARCH_URL).json(), self.EMPTY)

    def test_blank_q_is_still_200(self):
        self.assertEqual(self.anon.get(SEARCH_URL, {"q": ""}).status_code, 200)


class SongSearchTests(SearchTestCase):
    def test_matches_title_ignoring_case(self):
        for query in ("midnight rain", "MIDNIGHT RAIN", "Midnight"):
            with self.subTest(q=query):
                self.assertEqual(ids(self.search(query)["songs"]), [self.rain.id])

    def test_matches_part_of_a_title(self):
        self.assertEqual(ids(self.search("night r")["songs"]), [self.rain.id])

    def test_matches_artist_name_ignoring_case(self):
        for query in ("luna wave", "LUNA", "wave"):
            with self.subTest(q=query):
                self.assertEqual(ids(self.search(query)["songs"]), [self.rain.id])

    def test_non_matching_songs_are_left_out(self):
        self.assertNotIn(self.sun.id, ids(self.search("rain")["songs"]))

    def test_result_items_are_full_songs(self):
        item = self.search("rain")["songs"][0]
        self.assertEqual(item["title"], "Midnight Rain")
        self.assertEqual(item["artist"]["name"], "Luna Wave")
        self.assertEqual(item["stream_url"], f"/api/songs/{self.rain.id}/stream/")

    def test_at_most_20_songs(self):
        for number in range(21):
            make_song(f"Echo {number}")
        self.assertEqual(len(self.search("echo")["songs"]), 20)

    def test_is_liked_is_set_for_the_logged_in_user(self):
        self.alice_api.post(f"/api/songs/{self.rain.id}/like/")
        self.assertTrue(self.search("rain", self.alice_api)["songs"][0]["is_liked"])
        self.assertFalse(self.search("rain", self.bob_api)["songs"][0]["is_liked"])


class ArtistAndAlbumSearchTests(SearchTestCase):
    def test_artist_matches_by_name_ignoring_case(self):
        for query in ("luna wave", "LUNA", "wave"):
            with self.subTest(q=query):
                self.assertEqual(ids(self.search(query)["artists"]), [self.rain.artist_id])
        self.assertEqual(ids(self.search("SOLAR")["artists"]), [self.sun.artist_id])

    def test_artist_is_not_matched_by_a_song_title(self):
        self.assertEqual(self.search("midnight")["artists"], [])

    def test_artist_item_has_the_artist_shape(self):
        item = self.search("luna")["artists"][0]
        self.assertEqual(set(item), {"id", "name", "image_url", "colors", "song_count"})
        self.assertEqual(item["song_count"], 1)

    def test_album_matches_by_title_ignoring_case(self):
        for query in ("night sessions", "NIGHT", "sessions"):
            with self.subTest(q=query):
                self.assertEqual(ids(self.search(query)["albums"]), [self.rain.album_id])

    def test_album_is_not_matched_by_a_song_title(self):
        self.assertEqual(self.search("midnight")["albums"], [])

    def test_album_item_has_the_album_shape(self):
        item = self.search("night sessions")["albums"][0]
        self.assertEqual(set(item), {"id", "title", "artist", "year", "cover_url", "colors", "song_count"})
        self.assertEqual(item["artist"]["name"], "Luna Wave")


class PlaylistSearchTests(SearchTestCase):
    def test_public_playlist_is_found_by_anyone(self):
        for who, api in (("logged out", self.anon), ("alice", self.alice_api), ("bob", self.bob_api)):
            with self.subTest(viewer=who):
                self.assertIn(self.public_mix.id, ids(self.search("rainy", api)["playlists"]))

    def test_playlist_name_match_ignores_case(self):
        self.assertEqual(ids(self.search("RAINY DAY")["playlists"]), [self.public_mix.id])

    def test_own_private_playlist_is_found(self):
        self.assertIn(self.alices_private.id, ids(self.search("rain", self.alice_api)["playlists"]))
        self.assertIn(self.bobs_private.id, ids(self.search("rain", self.bob_api)["playlists"]))

    def test_other_users_private_playlist_is_not_found(self):
        alice_sees = ids(self.search("rain", self.alice_api)["playlists"])
        bob_sees = ids(self.search("rain", self.bob_api)["playlists"])
        self.assertNotIn(self.bobs_private.id, alice_sees)
        self.assertNotIn(self.alices_private.id, bob_sees)

    def test_logged_out_sees_public_playlists_only(self):
        self.assertEqual(ids(self.search("rain")["playlists"]), [self.public_mix.id])

    def test_alice_sees_public_plus_her_own(self):
        found = ids(self.search("rain", self.alice_api)["playlists"])
        self.assertEqual(sorted(found), sorted([self.public_mix.id, self.alices_private.id]))

    def test_playlist_item_has_the_list_shape_without_songs(self):
        item = self.search("rainy")["playlists"][0]
        self.assertNotIn("songs", item)
        self.assertEqual(item["owner"], {"id": self.bob.id, "username": "bob"})
        self.assertFalse(item["is_owner"])
