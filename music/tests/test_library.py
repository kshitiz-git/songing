"""Likes, the liked-songs library and the uploads library."""
from datetime import timedelta

from django.utils import timezone

from music.models import Like, Song

from .base import MusicTestCase, ids, make_song


class LikeTestCase(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.song = make_song("Likeable")
        self.like_url = f"/api/songs/{self.song.id}/like/"
        self.detail_url = f"/api/songs/{self.song.id}/"


class LikeTests(LikeTestCase):
    def test_like_returns_204(self):
        response = self.alice_api.post(self.like_url)
        self.assertEqual(response.status_code, 204)
        self.assertTrue(Like.objects.filter(user=self.alice, song=self.song).exists())

    def test_liking_twice_is_idempotent(self):
        first = self.alice_api.post(self.like_url)
        second = self.alice_api.post(self.like_url)
        self.assertEqual((first.status_code, second.status_code), (204, 204))
        self.assertEqual(Like.objects.filter(user=self.alice, song=self.song).count(), 1)

    def test_is_liked_is_true_in_song_detail_after_liking(self):
        self.assertFalse(self.alice_api.get(self.detail_url).json()["is_liked"])
        self.alice_api.post(self.like_url)
        self.assertTrue(self.alice_api.get(self.detail_url).json()["is_liked"])

    def test_is_liked_is_true_in_the_song_list_after_liking(self):
        self.alice_api.post(self.like_url)
        song = self.alice_api.get("/api/songs/").json()["results"][0]
        self.assertTrue(song["is_liked"])

    def test_liked_song_appears_in_the_liked_library(self):
        self.alice_api.post(self.like_url)
        liked = self.alice_api.get("/api/library/liked/").json()
        self.assertEqual(liked["count"], 1)
        self.assertEqual(ids(liked["results"]), [self.song.id])

    def test_liked_library_lists_the_newest_like_first(self):
        older, newer = make_song("Older"), make_song("Newer")
        self.alice_api.post(f"/api/songs/{older.id}/like/")
        self.alice_api.post(f"/api/songs/{newer.id}/like/")
        # Make the order independent of the clock's resolution
        Like.objects.filter(song=older).update(created_at=timezone.now() - timedelta(hours=1))
        liked = self.alice_api.get("/api/library/liked/").json()["results"]
        self.assertEqual(ids(liked), [newer.id, older.id])

    def test_likes_belong_to_one_user(self):
        self.alice_api.post(self.like_url)
        self.assertFalse(self.bob_api.get(self.detail_url).json()["is_liked"])
        self.assertEqual(self.bob_api.get("/api/library/liked/").json()["count"], 0)

    def test_liking_an_unknown_song_is_404(self):
        self.assertEqual(self.alice_api.post("/api/songs/999999/like/").status_code, 404)


class UnlikeTests(LikeTestCase):
    def setUp(self):
        super().setUp()
        self.alice_api.post(self.like_url)

    def test_unlike_returns_204_and_removes_it(self):
        response = self.alice_api.delete(self.like_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Like.objects.exists())

    def test_unliking_twice_is_idempotent(self):
        first = self.alice_api.delete(self.like_url)
        second = self.alice_api.delete(self.like_url)
        self.assertEqual((first.status_code, second.status_code), (204, 204))

    def test_unliked_song_leaves_the_liked_library(self):
        self.alice_api.delete(self.like_url)
        self.assertEqual(self.alice_api.get("/api/library/liked/").json()["count"], 0)

    def test_is_liked_goes_back_to_false(self):
        self.alice_api.delete(self.like_url)
        self.assertFalse(self.alice_api.get(self.detail_url).json()["is_liked"])

    def test_unliking_does_not_touch_another_users_like(self):
        self.bob_api.post(self.like_url)
        self.alice_api.delete(self.like_url)
        self.assertTrue(Like.objects.filter(user=self.bob, song=self.song).exists())


class LoggedOutLibraryTests(LikeTestCase):
    def test_like_unlike_and_liked_list_need_a_login(self):
        requests = [
            ("POST", self.like_url),
            ("DELETE", self.like_url),
            ("GET", "/api/library/liked/"),
            ("GET", "/api/library/recent/"),
            ("GET", "/api/library/uploads/"),
        ]
        for method, url in requests:
            with self.subTest(request=f"{method} {url}"):
                response = self.anon.generic(method, url)
                self.assertEqual(response.status_code, 403)
                self.assertIn("detail", response.json())

    def test_logged_out_like_does_not_create_a_like(self):
        self.anon.post(self.like_url)
        self.assertFalse(Like.objects.exists())

    def test_is_liked_is_false_when_logged_out(self):
        self.alice_api.post(self.like_url)
        self.assertFalse(self.anon.get(self.detail_url).json()["is_liked"])


class UploadsLibraryTests(MusicTestCase):
    def test_lists_own_public_and_private_uploads_only(self):
        mine_public = make_song("Mine Public", uploader=self.alice, is_public=True)
        mine_private = make_song("Mine Private", uploader=self.alice, is_public=False)
        make_song("Bobs", uploader=self.bob, is_public=True)
        make_song("Catalogue", uploader=None, is_public=True)
        uploads = self.alice_api.get("/api/library/uploads/").json()
        self.assertEqual(uploads["count"], 2)
        self.assertEqual(sorted(ids(uploads["results"])), sorted([mine_public.id, mine_private.id]))

    def test_newest_upload_first(self):
        older = make_song("Older", uploader=self.alice)
        newer = make_song("Newer", uploader=self.alice)
        Song.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(ids(self.alice_api.get("/api/library/uploads/").json()["results"]), [newer.id, older.id])

    def test_another_user_sees_none_of_them(self):
        make_song("Mine", uploader=self.alice, is_public=True)
        self.assertEqual(self.bob_api.get("/api/library/uploads/").json()["count"], 0)

    def test_every_item_is_marked_as_owned(self):
        make_song("Mine", uploader=self.alice)
        self.assertTrue(self.alice_api.get("/api/library/uploads/").json()["results"][0]["is_owner"])
