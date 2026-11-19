"""A private upload is visible to its owner only; deleting an upload removes its files."""
import os

from django.core.files.uploadedfile import SimpleUploadedFile

from music.models import Like, PlayEvent, Playlist, Song

from .base import MusicTestCase, audio_upload, ids, make_image, make_song, stored_files

NOT_FOUND = {"detail": "Not found."}


class HiddenSongTestCase(MusicTestCase):
    """Alice has one private song with its own album and artist; one public song exists too."""

    def setUp(self):
        super().setUp()
        self.secret = make_song(
            "Hidden Gem", artist="Secret Artist", album="Secret Album", genre="Secret Genre",
            uploader=self.alice, is_public=False,
        )
        self.open = make_song("Open Song", artist="Open Artist", album="Open Album", genre="Open Genre")
        self.song_url = f"/api/songs/{self.secret.id}/"
        self.album_url = f"/api/albums/{self.secret.album_id}/"
        self.artist_url = f"/api/artists/{self.secret.artist_id}/"
        self.outsiders = [("another user", self.bob_api), ("logged out", self.anon)]


class OutsiderCannotSeePrivateSongTests(HiddenSongTestCase):
    def test_song_detail_is_404(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                response = api.get(self.song_url)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), NOT_FOUND)

    def test_stream_is_404(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                response = api.get(f"{self.song_url}stream/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), NOT_FOUND)

    def test_not_in_the_song_list(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                listed = ids(api.get("/api/songs/").json()["results"])
                self.assertEqual(listed, [self.open.id])

    def test_not_in_the_song_list_even_when_searched_for_there(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                self.assertEqual(api.get("/api/songs/?q=Hidden").json()["count"], 0)

    def test_not_found_by_search(self):
        for who, api in self.outsiders:
            for query in ("Hidden Gem", "Secret Artist", "Secret Album", "secret"):
                with self.subTest(viewer=who, q=query):
                    found = api.get("/api/search/", {"q": query}).json()
                    self.assertEqual(found["songs"], [])
                    self.assertEqual(found["artists"], [])
                    self.assertEqual(found["albums"], [])

    def test_private_only_album_is_404_and_not_listed(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                self.assertEqual(api.get(self.album_url).status_code, 404)
                self.assertNotIn(self.secret.album_id, ids(api.get("/api/albums/").json()["results"]))

    def test_private_only_artist_is_404_and_not_listed(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                self.assertEqual(api.get(self.artist_url).status_code, 404)
                self.assertNotIn(self.secret.artist_id, ids(api.get("/api/artists/").json()["results"]))

    def test_genre_is_not_listed(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                self.assertEqual(api.get("/api/genres/").json(), ["Open Genre"])

    def test_not_on_the_home_page(self):
        for who, api in self.outsiders:
            with self.subTest(viewer=who):
                home = api.get("/api/home/").json()
                self.assertNotIn(self.secret.id, ids(home["trending"]))
                self.assertNotIn(self.secret.id, ids(home["made_for_you"]))
                self.assertNotIn(self.secret.album_id, ids(home["new_releases"]))
                self.assertNotIn(self.secret.artist_id, ids(home["artists"]))

    def test_cannot_like_play_or_playlist_it(self):
        playlist = Playlist.objects.create(owner=self.bob, name="Bob's")
        checks = [
            self.bob_api.post(f"{self.song_url}like/"),
            self.bob_api.post(f"{self.song_url}play/"),
        ]
        self.assertEqual([r.status_code for r in checks], [404, 404])
        added = self.bob_api.post(f"/api/playlists/{playlist.id}/songs/", {"song_id": self.secret.id}, format="json")
        self.assertEqual(added.status_code, 400)
        self.assertIn("song_id", added.json())

    def test_failed_like_play_and_playlist_add_change_nothing(self):
        playlist = Playlist.objects.create(owner=self.bob, name="Bob's")
        self.bob_api.post(f"{self.song_url}like/")
        self.bob_api.post(f"{self.song_url}play/")
        self.bob_api.post(f"/api/playlists/{playlist.id}/songs/", {"song_id": self.secret.id}, format="json")
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.play_count, 0)
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(PlayEvent.objects.count(), 0)
        self.assertEqual(playlist.items.count(), 0)


class OwnerSeesPrivateSongTests(HiddenSongTestCase):
    def test_detail(self):
        response = self.alice_api.get(self.song_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "Hidden Gem")
        self.assertFalse(data["is_public"])
        self.assertTrue(data["is_owner"])

    def test_stream(self):
        self.assertEqual(self.alice_api.get(f"{self.song_url}stream/").status_code, 200)

    def test_song_list_and_search(self):
        self.assertIn(self.secret.id, ids(self.alice_api.get("/api/songs/").json()["results"]))
        found = self.alice_api.get("/api/search/", {"q": "Hidden"}).json()
        self.assertEqual(ids(found["songs"]), [self.secret.id])

    def test_search_finds_its_artist_and_album(self):
        by_artist = self.alice_api.get("/api/search/", {"q": "Secret Artist"}).json()
        by_album = self.alice_api.get("/api/search/", {"q": "Secret Album"}).json()
        self.assertEqual(ids(by_artist["artists"]), [self.secret.artist_id])
        self.assertEqual(ids(by_album["albums"]), [self.secret.album_id])

    def test_album_and_artist_pages(self):
        album = self.alice_api.get(self.album_url)
        artist = self.alice_api.get(self.artist_url)
        self.assertEqual(album.status_code, 200)
        self.assertEqual(ids(album.json()["songs"]), [self.secret.id])
        self.assertEqual(artist.status_code, 200)
        self.assertEqual(ids(artist.json()["top_songs"]), [self.secret.id])

    def test_album_and_artist_lists(self):
        self.assertIn(self.secret.album_id, ids(self.alice_api.get("/api/albums/").json()["results"]))
        self.assertIn(self.secret.artist_id, ids(self.alice_api.get("/api/artists/").json()["results"]))

    def test_genre_list(self):
        self.assertEqual(self.alice_api.get("/api/genres/").json(), ["Open Genre", "Secret Genre"])

    def test_own_uploads_library(self):
        self.assertEqual(ids(self.alice_api.get("/api/library/uploads/").json()["results"]), [self.secret.id])

    def test_can_like_play_and_playlist_it(self):
        playlist = Playlist.objects.create(owner=self.alice, name="Mine")
        self.assertEqual(self.alice_api.post(f"{self.song_url}like/").status_code, 204)
        self.assertEqual(self.alice_api.post(f"{self.song_url}play/").status_code, 204)
        added = self.alice_api.post(f"/api/playlists/{playlist.id}/songs/", {"song_id": self.secret.id}, format="json")
        self.assertEqual(added.status_code, 201)


class MixedAlbumTests(MusicTestCase):
    """An album or artist with one public and one private song shows only the public one to others."""

    def setUp(self):
        super().setUp()
        self.public = make_song("Public Track", artist="Duo", album="Mixed", uploader=self.alice, is_public=True)
        self.private = make_song("Private Track", artist="Duo", album="Mixed", uploader=self.alice, is_public=False)

    def test_album_song_count_and_songs_hide_the_private_one(self):
        data = self.bob_api.get(f"/api/albums/{self.public.album_id}/").json()
        self.assertEqual(data["song_count"], 1)
        self.assertEqual(ids(data["songs"]), [self.public.id])

    def test_artist_song_count_and_top_songs_hide_the_private_one(self):
        data = self.bob_api.get(f"/api/artists/{self.public.artist_id}/").json()
        self.assertEqual(data["song_count"], 1)
        self.assertEqual(ids(data["top_songs"]), [self.public.id])

    def test_owner_sees_both(self):
        data = self.alice_api.get(f"/api/albums/{self.public.album_id}/").json()
        self.assertEqual(data["song_count"], 2)
        self.assertEqual(sorted(ids(data["songs"])), sorted([self.public.id, self.private.id]))


class DeleteTests(MusicTestCase):
    def upload(self, **extra):
        fields = {"audio": audio_upload(), "title": "Mine", "artist_name": "Me", **extra}
        response = self.alice_api.post("/api/songs/", fields, format="multipart")
        self.assertEqual(response.status_code, 201, response.content)
        return Song.objects.get(pk=response.json()["id"])

    def test_owner_deletes_own_upload(self):
        song = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Song.objects.filter(pk=song.pk).exists())
        self.assertEqual(self.alice_api.get(f"/api/songs/{song.id}/").status_code, 404)

    def test_audio_file_is_removed_from_disk_after_commit(self):
        song = self.upload()
        path = song.audio.path
        self.assertTrue(os.path.exists(path))
        with self.captureOnCommitCallbacks(execute=True):
            self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertFalse(os.path.exists(path))
        self.assertEqual(stored_files(self.private_root), [])

    def test_file_is_kept_until_the_transaction_commits(self):
        song = self.upload()
        path = song.audio.path
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertTrue(os.path.exists(path))
        for callback in callbacks:
            callback()
        self.assertFalse(os.path.exists(path))

    def test_cover_file_is_removed_too(self):
        cover = SimpleUploadedFile("c.png", make_image(), content_type="image/png")
        song = self.upload(cover=cover)
        self.assertEqual(len(stored_files(self.media_root)), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertEqual(stored_files(self.media_root), [])

    def test_deleting_removes_the_song_from_playlists_and_likes(self):
        song = self.upload()
        playlist = Playlist.objects.create(owner=self.alice, name="Mix")
        self.alice_api.post(f"/api/playlists/{playlist.id}/songs/", {"song_id": song.id}, format="json")
        self.alice_api.post(f"/api/songs/{song.id}/like/")
        with self.captureOnCommitCallbacks(execute=True):
            self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertEqual(playlist.items.count(), 0)
        self.assertEqual(Like.objects.count(), 0)

    def test_another_user_gets_403_on_a_public_song_they_do_not_own(self):
        song = make_song("Shared", uploader=self.alice, is_public=True)
        response = self.bob_api.delete(f"/api/songs/{song.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Song.objects.filter(pk=song.pk).exists())
        self.assertTrue(os.path.exists(song.audio.path))

    def test_nobody_can_delete_a_catalogue_song_with_no_uploader(self):
        song = make_song("Catalogue", uploader=None, is_public=True)
        response = self.alice_api.delete(f"/api/songs/{song.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Song.objects.filter(pk=song.pk).exists())

    def test_logged_out_delete_is_403(self):
        song = make_song("Shared", uploader=self.alice, is_public=True)
        self.assertEqual(self.anon.delete(f"/api/songs/{song.id}/").status_code, 403)
        self.assertTrue(Song.objects.filter(pk=song.pk).exists())

    def test_another_users_private_song_is_404_not_403(self):
        song = make_song("Secret", uploader=self.alice, is_public=False)
        self.assertEqual(self.bob_api.delete(f"/api/songs/{song.id}/").status_code, 404)
        self.assertTrue(Song.objects.filter(pk=song.pk).exists())

    def test_deleting_an_unknown_song_is_404(self):
        self.assertEqual(self.alice_api.delete("/api/songs/999999/").status_code, 404)

    def test_deleting_one_upload_leaves_the_other_files_alone(self):
        keep, drop = self.upload(), self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            self.alice_api.delete(f"/api/songs/{drop.id}/")
        self.assertTrue(os.path.exists(keep.audio.path))
        self.assertEqual(len(stored_files(self.private_root)), 1)
