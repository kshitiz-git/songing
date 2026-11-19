"""Playlists: create, edit, add / remove / reorder songs, and who may do what."""
import json

from django.core.files.base import ContentFile

from music.models import Playlist, PlaylistItem, Song

from .base import MusicTestCase, ids, make_image, make_song

PLAYLIST_KEYS = {
    "id", "name", "description", "is_public", "owner", "is_owner", "colors", "cover_urls",
    "song_count", "duration", "updated_at",
}


def make_playlist(owner, name="Mix", is_public=False, songs=()):
    playlist = Playlist.objects.create(owner=owner, name=name, is_public=is_public)
    for position, song in enumerate(songs):
        PlaylistItem.objects.create(playlist=playlist, song=song, position=position)
    return playlist


def song_ids_in(playlist):
    return list(playlist.items.order_by("position").values_list("song_id", flat=True))


def positions_in(playlist):
    return list(playlist.items.order_by("position").values_list("position", flat=True))


class PlaylistTestCase(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.s1, self.s2, self.s3 = make_song("One"), make_song("Two"), make_song("Three")


class CreateTests(PlaylistTestCase):
    def create(self, client=None, **fields):
        return (client or self.alice_api).post("/api/playlists/", fields, format="json")

    def test_create_returns_201_with_the_detail_shape(self):
        response = self.create(name="Study", description="Quiet songs", is_public=True)
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(set(data), PLAYLIST_KEYS | {"songs"})
        self.assertEqual(data["name"], "Study")
        self.assertEqual(data["description"], "Quiet songs")
        self.assertTrue(data["is_public"])
        self.assertEqual(data["owner"], {"id": self.alice.id, "username": "alice"})
        self.assertTrue(data["is_owner"])
        self.assertEqual(data["songs"], [])
        self.assertEqual((data["song_count"], data["duration"], data["cover_urls"]), (0, 0, []))
        self.assertEqual(len(data["colors"]), 2)

    def test_new_playlist_is_private_and_has_no_description_by_default(self):
        data = self.create(name="Study").json()
        self.assertFalse(data["is_public"])
        self.assertEqual(data["description"], "")

    def test_name_is_trimmed(self):
        self.assertEqual(self.create(name="  Study  ").json()["name"], "Study")

    def test_blank_name_is_rejected(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                response = self.create(name=name)
                self.assertEqual(response.status_code, 400)
                self.assertIn("name", response.json())
        self.assertFalse(Playlist.objects.exists())

    def test_missing_name_is_rejected(self):
        response = self.create(description="no name")
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

    def test_name_of_101_characters_is_rejected(self):
        response = self.create(name="x" * 101)
        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

    def test_name_of_100_characters_is_accepted(self):
        self.assertEqual(self.create(name="x" * 100).status_code, 201)

    def test_description_over_300_characters_is_rejected(self):
        response = self.create(name="Study", description="x" * 301)
        self.assertEqual(response.status_code, 400)
        self.assertIn("description", response.json())

    def test_logged_out_create_is_403(self):
        self.assertEqual(self.create(client=self.anon, name="Study").status_code, 403)
        self.assertFalse(Playlist.objects.exists())

    def test_playlist_belongs_to_whoever_created_it_even_if_the_body_names_another_owner(self):
        data = self.create(name="Study", owner=self.bob.id).json()
        self.assertEqual(data["owner"]["id"], self.alice.id)


class ListAndReadTests(PlaylistTestCase):
    def test_list_has_only_my_playlists(self):
        mine = make_playlist(self.alice, "Mine")
        make_playlist(self.bob, "Bobs", is_public=True)
        listed = self.alice_api.get("/api/playlists/").json()
        self.assertEqual(ids(listed), [mine.id])

    def test_list_items_use_the_list_shape_without_songs(self):
        make_playlist(self.alice, "Mine", songs=[self.s1])
        item = self.alice_api.get("/api/playlists/").json()[0]
        self.assertEqual(set(item), PLAYLIST_KEYS)
        self.assertEqual(item["song_count"], 1)

    def test_list_puts_the_most_recently_updated_first(self):
        first = make_playlist(self.alice, "First")
        second = make_playlist(self.alice, "Second")
        self.alice_api.patch(f"/api/playlists/{first.id}/", {"name": "First, renamed"}, format="json")
        self.assertEqual(ids(self.alice_api.get("/api/playlists/").json()), [first.id, second.id])

    def test_logged_out_list_is_403(self):
        self.assertEqual(self.anon.get("/api/playlists/").status_code, 403)

    def test_detail_lists_songs_in_playlist_order(self):
        playlist = make_playlist(self.alice, songs=[self.s3, self.s1, self.s2])
        data = self.alice_api.get(f"/api/playlists/{playlist.id}/").json()
        self.assertEqual(ids(data["songs"]), [self.s3.id, self.s1.id, self.s2.id])

    def test_detail_counts_songs_and_sums_duration(self):
        playlist = make_playlist(self.alice, songs=[self.s1, self.s2])
        data = self.alice_api.get(f"/api/playlists/{playlist.id}/").json()
        self.assertEqual(data["song_count"], 2)
        self.assertEqual(data["duration"], 4.0)

    def test_cover_urls_holds_up_to_four_distinct_song_covers(self):
        songs = []
        for number in range(5):
            cover = ContentFile(make_image(), name="c.jpg")
            songs.append(make_song(f"Cover {number}", cover=cover))
        playlist = make_playlist(self.alice, songs=songs)
        urls = self.alice_api.get(f"/api/playlists/{playlist.id}/").json()["cover_urls"]
        self.assertEqual(len(urls), 4)
        self.assertEqual(len(set(urls)), 4)
        self.assertTrue(all(url.startswith("/media/covers/") for url in urls))

    def test_cover_urls_is_empty_when_no_song_has_a_cover(self):
        playlist = make_playlist(self.alice, songs=[self.s1])
        self.assertEqual(self.alice_api.get(f"/api/playlists/{playlist.id}/").json()["cover_urls"], [])

    def test_unknown_playlist_is_404(self):
        self.assertEqual(self.alice_api.get("/api/playlists/999999/").status_code, 404)


class EditTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = make_playlist(self.alice, "Old name", songs=[self.s1])
        self.url = f"/api/playlists/{self.playlist.id}/"

    def patch(self, **fields):
        return self.alice_api.patch(self.url, fields, format="json")

    def test_patch_name(self):
        response = self.patch(name="New name")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "New name")
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.name, "New name")

    def test_patch_description(self):
        self.assertEqual(self.patch(description="Fresh words").json()["description"], "Fresh words")

    def test_patch_is_public_both_ways(self):
        self.assertTrue(self.patch(is_public=True).json()["is_public"])
        self.assertFalse(self.patch(is_public=False).json()["is_public"])

    def test_patch_returns_the_detail_with_songs(self):
        data = self.patch(name="New name").json()
        self.assertEqual(set(data), PLAYLIST_KEYS | {"songs"})
        self.assertEqual(ids(data["songs"]), [self.s1.id])

    def test_patch_changes_only_the_fields_sent(self):
        self.playlist.description = "Keep me"
        self.playlist.save()
        self.patch(is_public=True)
        self.playlist.refresh_from_db()
        self.assertEqual((self.playlist.name, self.playlist.description), ("Old name", "Keep me"))

    def test_patch_with_bad_values_is_400_and_changes_nothing(self):
        for fields in ({"name": ""}, {"name": "x" * 101}, {"description": "x" * 301}):
            with self.subTest(fields=list(fields)):
                self.assertEqual(self.patch(**fields).status_code, 400)
        self.playlist.refresh_from_db()
        self.assertEqual(self.playlist.name, "Old name")

    def test_delete_returns_204_and_removes_the_playlist(self):
        response = self.alice_api.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Playlist.objects.filter(pk=self.playlist.pk).exists())
        self.assertEqual(self.alice_api.get(self.url).status_code, 404)

    def test_delete_keeps_the_songs(self):
        self.alice_api.delete(self.url)
        self.assertTrue(Song.objects.filter(pk=self.s1.pk).exists())


class AddSongTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = make_playlist(self.alice, "Mix")
        self.url = f"/api/playlists/{self.playlist.id}/songs/"

    def add(self, song_id):
        return self.alice_api.post(self.url, {"song_id": song_id}, format="json")

    def test_add_returns_201_with_the_playlist_detail(self):
        response = self.add(self.s1.id)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ids(response.json()["songs"]), [self.s1.id])

    def test_songs_are_added_at_the_end(self):
        for song in (self.s2, self.s3, self.s1):
            self.add(song.id)
        self.assertEqual(song_ids_in(self.playlist), [self.s2.id, self.s3.id, self.s1.id])
        self.assertEqual(positions_in(self.playlist), [0, 1, 2])

    def test_adding_the_same_song_again_returns_200_and_keeps_one_copy(self):
        self.add(self.s1.id)
        response = self.add(self.s1.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ids(response.json()["songs"]), [self.s1.id])
        self.assertEqual(self.playlist.items.count(), 1)

    def test_one_song_can_be_in_several_playlists(self):
        other = make_playlist(self.alice, "Other")
        self.add(self.s1.id)
        self.alice_api.post(f"/api/playlists/{other.id}/songs/", {"song_id": self.s1.id}, format="json")
        self.assertEqual(PlaylistItem.objects.filter(song=self.s1).count(), 2)

    def test_unknown_song_is_400(self):
        response = self.add(999999)
        self.assertEqual(response.status_code, 400)
        self.assertIn("song_id", response.json())

    def test_missing_or_bad_song_id_is_400(self):
        for body in ({}, {"song_id": "abc"}, {"song_id": None}):
            with self.subTest(body=body):
                response = self.alice_api.post(self.url, body, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("song_id", response.json())

    def test_playlist_totals_follow_the_songs(self):
        self.add(self.s1.id)
        data = self.add(self.s2.id).json()
        self.assertEqual((data["song_count"], data["duration"]), (2, 4.0))


class RemoveSongTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = make_playlist(self.alice, "Mix", songs=[self.s1, self.s2, self.s3])

    def remove(self, song):
        return self.alice_api.delete(f"/api/playlists/{self.playlist.id}/songs/{song.id}/")

    def test_remove_returns_204(self):
        self.assertEqual(self.remove(self.s2).status_code, 204)
        self.assertEqual(song_ids_in(self.playlist), [self.s1.id, self.s3.id])

    def test_positions_close_the_gap(self):
        self.remove(self.s1)
        self.assertEqual(positions_in(self.playlist), [0, 1])
        self.assertEqual(song_ids_in(self.playlist), [self.s2.id, self.s3.id])

    def test_removing_the_last_song_leaves_the_order_alone(self):
        self.remove(self.s3)
        self.assertEqual(song_ids_in(self.playlist), [self.s1.id, self.s2.id])
        self.assertEqual(positions_in(self.playlist), [0, 1])

    def test_a_song_added_after_a_removal_goes_to_the_end(self):
        self.remove(self.s1)
        self.alice_api.post(f"/api/playlists/{self.playlist.id}/songs/", {"song_id": self.s1.id}, format="json")
        self.assertEqual(song_ids_in(self.playlist), [self.s2.id, self.s3.id, self.s1.id])
        self.assertEqual(positions_in(self.playlist), [0, 1, 2])

    def test_remove_does_not_delete_the_song(self):
        self.remove(self.s1)
        self.assertTrue(Song.objects.filter(pk=self.s1.pk).exists())

    def test_removing_a_song_that_is_not_in_the_playlist_changes_nothing(self):
        outsider = make_song("Outsider")
        self.assertEqual(self.remove(outsider).status_code, 204)
        self.assertEqual(song_ids_in(self.playlist), [self.s1.id, self.s2.id, self.s3.id])


class ReorderTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = make_playlist(self.alice, "Mix", songs=[self.s1, self.s2, self.s3])
        self.url = f"/api/playlists/{self.playlist.id}/reorder/"
        self.original = [self.s1.id, self.s2.id, self.s3.id]

    def reorder(self, song_ids):
        return self.alice_api.post(self.url, {"song_ids": song_ids}, format="json")

    def test_exact_ids_in_a_new_order_returns_200_in_that_order(self):
        new_order = [self.s3.id, self.s1.id, self.s2.id]
        response = self.reorder(new_order)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ids(response.json()["songs"]), new_order)

    def test_new_order_is_stored(self):
        new_order = [self.s2.id, self.s3.id, self.s1.id]
        self.reorder(new_order)
        self.assertEqual(song_ids_in(self.playlist), new_order)
        self.assertEqual(positions_in(self.playlist), [0, 1, 2])
        self.assertEqual(ids(self.alice_api.get(f"/api/playlists/{self.playlist.id}/").json()["songs"]), new_order)

    def test_same_order_is_accepted(self):
        self.assertEqual(self.reorder(self.original).status_code, 200)

    def test_missing_id_is_400(self):
        response = self.reorder([self.s1.id, self.s2.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn("song_ids", response.json())

    def test_extra_id_is_400(self):
        extra = make_song("Not in the playlist")
        response = self.reorder(self.original + [extra.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn("song_ids", response.json())

    def test_id_of_a_song_that_does_not_exist_is_400(self):
        self.assertEqual(self.reorder(self.original + [999999]).status_code, 400)

    def test_duplicate_id_is_400(self):
        self.assertEqual(self.reorder([self.s1.id, self.s1.id, self.s2.id, self.s3.id]).status_code, 400)

    def test_duplicate_id_in_place_of_another_is_400(self):
        self.assertEqual(self.reorder([self.s1.id, self.s1.id, self.s2.id]).status_code, 400)

    def test_empty_list_is_400_for_a_playlist_with_songs(self):
        self.assertEqual(self.reorder([]).status_code, 400)

    def test_missing_or_malformed_body_is_400(self):
        for body in ({}, {"song_ids": "1,2,3"}, {"song_ids": ["a", "b"]}, {"song_ids": None}):
            with self.subTest(body=body):
                self.assertEqual(self.alice_api.post(self.url, body, format="json").status_code, 400)

    def test_a_rejected_reorder_keeps_the_old_order(self):
        extra = make_song("Not in the playlist")
        self.reorder([self.s3.id, self.s2.id])
        self.reorder([self.s3.id, self.s2.id, self.s1.id, extra.id])
        self.reorder([self.s3.id, self.s3.id, self.s1.id])
        self.assertEqual(song_ids_in(self.playlist), self.original)

    def test_empty_playlist_accepts_an_empty_order(self):
        empty = make_playlist(self.alice, "Empty")
        response = self.alice_api.post(f"/api/playlists/{empty.id}/reorder/", {"song_ids": []}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["songs"], [])


class OtherUsersTests(PlaylistTestCase):
    """Bob against Alice's playlists: 403 on a public one, 404 on a private one."""

    def setUp(self):
        super().setUp()
        self.public = make_playlist(self.alice, "Public", is_public=True, songs=[self.s1, self.s2])
        self.private = make_playlist(self.alice, "Private", is_public=False, songs=[self.s1, self.s2])

    def writes(self, playlist):
        """Every way to change a playlist, as (method, url, json body)."""
        base = f"/api/playlists/{playlist.id}/"
        return [
            ("PATCH", base, {"name": "Hacked", "is_public": False}),
            ("DELETE", base, None),
            ("POST", f"{base}songs/", {"song_id": self.s3.id}),
            ("DELETE", f"{base}songs/{self.s1.id}/", None),
            ("POST", f"{base}reorder/", {"song_ids": [self.s2.id, self.s1.id]}),
        ]

    def send(self, api, method, url, body):
        if body is None:
            return api.generic(method, url)
        return api.generic(method, url, json.dumps(body), content_type="application/json")

    def snapshot(self, playlist):
        playlist.refresh_from_db()
        return (playlist.name, playlist.is_public, song_ids_in(playlist))

    def test_every_write_on_a_public_playlist_is_403(self):
        for method, url, body in self.writes(self.public):
            with self.subTest(request=f"{method} {url}"):
                response = self.send(self.bob_api, method, url, body)
                self.assertEqual(response.status_code, 403)
                self.assertIn("detail", response.json())

    def test_writes_on_a_public_playlist_change_nothing(self):
        before = self.snapshot(self.public)
        for method, url, body in self.writes(self.public):
            self.send(self.bob_api, method, url, body)
        self.assertEqual(self.snapshot(self.public), before)
        self.assertTrue(Playlist.objects.filter(pk=self.public.pk).exists())

    def test_every_write_on_a_private_playlist_is_404(self):
        for method, url, body in self.writes(self.private):
            with self.subTest(request=f"{method} {url}"):
                response = self.send(self.bob_api, method, url, body)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Not found."})

    def test_writes_on_a_private_playlist_change_nothing(self):
        before = self.snapshot(self.private)
        for method, url, body in self.writes(self.private):
            self.send(self.bob_api, method, url, body)
        self.assertEqual(self.snapshot(self.private), before)
        self.assertTrue(Playlist.objects.filter(pk=self.private.pk).exists())

    def test_logged_out_writes_are_403_and_change_nothing(self):
        before = self.snapshot(self.public)
        for method, url, body in self.writes(self.public):
            with self.subTest(request=f"{method} {url}"):
                self.assertEqual(self.send(self.anon, method, url, body).status_code, 403)
        self.assertEqual(self.snapshot(self.public), before)

    def test_reading_someone_elses_private_playlist_is_404(self):
        for who, api in (("another user", self.bob_api), ("logged out", self.anon)):
            with self.subTest(viewer=who):
                response = api.get(f"/api/playlists/{self.private.id}/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Not found."})

    def test_reading_someone_elses_public_playlist_is_200_and_not_owned(self):
        for who, api in (("another user", self.bob_api), ("logged out", self.anon)):
            with self.subTest(viewer=who):
                response = api.get(f"/api/playlists/{self.public.id}/")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertFalse(data["is_owner"])
                self.assertEqual(data["owner"], {"id": self.alice.id, "username": "alice"})
                self.assertEqual(ids(data["songs"]), [self.s1.id, self.s2.id])

    def test_the_owner_is_marked_as_owner(self):
        self.assertTrue(self.alice_api.get(f"/api/playlists/{self.public.id}/").json()["is_owner"])

    def test_made_public_playlist_becomes_readable_by_others(self):
        self.alice_api.patch(f"/api/playlists/{self.private.id}/", {"is_public": True}, format="json")
        self.assertEqual(self.bob_api.get(f"/api/playlists/{self.private.id}/").status_code, 200)

    def test_made_private_playlist_disappears_for_others(self):
        self.alice_api.patch(f"/api/playlists/{self.public.id}/", {"is_public": False}, format="json")
        self.assertEqual(self.bob_api.get(f"/api/playlists/{self.public.id}/").status_code, 404)

    def test_other_users_list_does_not_show_my_playlists(self):
        self.assertEqual(self.bob_api.get("/api/playlists/").json(), [])


class HiddenSongsInPlaylistTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.private_song = make_song("Alice's private", uploader=self.alice, is_public=False)
        self.playlist = make_playlist(
            self.alice, "Public mix", is_public=True, songs=[self.s1, self.private_song, self.s2]
        )
        self.url = f"/api/playlists/{self.playlist.id}/"

    def test_other_user_does_not_see_the_private_song(self):
        data = self.bob_api.get(self.url).json()
        self.assertEqual(ids(data["songs"]), [self.s1.id, self.s2.id])

    def test_logged_out_visitor_does_not_see_the_private_song(self):
        data = self.anon.get(self.url).json()
        self.assertEqual(ids(data["songs"]), [self.s1.id, self.s2.id])

    def test_counts_and_duration_leave_the_private_song_out(self):
        data = self.bob_api.get(self.url).json()
        self.assertEqual((data["song_count"], data["duration"]), (2, 4.0))

    def test_owner_sees_all_three_songs(self):
        data = self.alice_api.get(self.url).json()
        self.assertEqual(ids(data["songs"]), [self.s1.id, self.private_song.id, self.s2.id])
        self.assertEqual(data["song_count"], 3)

    def test_search_result_for_the_playlist_also_hides_it(self):
        found = self.bob_api.get("/api/search/", {"q": "Public mix"}).json()["playlists"]
        self.assertEqual(found[0]["song_count"], 2)

    def test_private_song_cannot_be_added_to_someone_elses_playlist(self):
        mine = make_playlist(self.bob, "Bobs")
        response = self.bob_api.post(f"/api/playlists/{mine.id}/songs/", {"song_id": self.private_song.id}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(mine.items.count(), 0)
