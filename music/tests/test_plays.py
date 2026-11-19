"""Play counting, recently played and the home page's trending list."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from music.models import PlayEvent

from .base import MusicTestCase, ids, make_song


def add_plays(song, user=None, count=1, days_ago=0, minutes_ago=0):
    """Insert play events at an exact time, so ordering never depends on the clock."""
    when = timezone.now() - timedelta(days=days_ago, minutes=minutes_ago)
    PlayEvent.objects.bulk_create([PlayEvent(song=song, user=user, played_at=when) for _ in range(count)])


class PlayTests(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.song = make_song("Played")
        self.url = f"/api/songs/{self.song.id}/play/"

    def test_play_returns_204(self):
        self.assertEqual(self.alice_api.post(self.url).status_code, 204)

    def test_play_adds_one_to_the_count(self):
        self.alice_api.post(self.url)
        self.song.refresh_from_db()
        self.assertEqual(self.song.play_count, 1)

    def test_play_count_shows_in_song_detail(self):
        self.alice_api.post(self.url)
        self.assertEqual(self.alice_api.get(f"/api/songs/{self.song.id}/").json()["play_count"], 1)

    def test_each_play_adds_one_more(self):
        for _ in range(3):
            self.alice_api.post(self.url)
        self.song.refresh_from_db()
        self.assertEqual(self.song.play_count, 3)
        self.assertEqual(PlayEvent.objects.filter(song=self.song).count(), 3)

    def test_play_records_an_event_for_the_listener(self):
        self.alice_api.post(self.url)
        event = PlayEvent.objects.get()
        self.assertEqual((event.song, event.user), (self.song, self.alice))
        self.assertLess(timezone.now() - event.played_at, timedelta(minutes=1))

    def test_logged_out_play_counts_without_a_user(self):
        self.assertEqual(self.anon.post(self.url).status_code, 204)
        self.song.refresh_from_db()
        self.assertEqual(self.song.play_count, 1)
        self.assertIsNone(PlayEvent.objects.get().user)

    def test_unknown_song_is_404_and_records_nothing(self):
        self.assertEqual(self.alice_api.post("/api/songs/999999/play/").status_code, 404)
        self.assertFalse(PlayEvent.objects.exists())

    def test_get_is_not_allowed(self):
        self.assertEqual(self.alice_api.get(self.url).status_code, 405)

    def test_play_reports_are_rate_limited(self):
        limit = int(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["play"].split("/")[0])
        statuses = [self.alice_api.post(self.url).status_code for _ in range(limit + 1)]
        self.assertEqual(statuses[:limit], [204] * limit)
        self.assertEqual(statuses[limit], 429)


class RecentlyPlayedTests(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = make_song("A"), make_song("B"), make_song("C")

    def recent(self, api=None):
        return ids((api or self.alice_api).get("/api/library/recent/").json())

    def test_a_played_song_shows_up(self):
        self.alice_api.post(f"/api/songs/{self.a.id}/play/")
        self.assertEqual(self.recent(), [self.a.id])

    def test_newest_play_comes_first(self):
        add_plays(self.a, self.alice, minutes_ago=30)
        add_plays(self.b, self.alice, minutes_ago=20)
        add_plays(self.c, self.alice, minutes_ago=10)
        self.assertEqual(self.recent(), [self.c.id, self.b.id, self.a.id])

    def test_a_song_played_twice_is_listed_once_at_its_latest_play(self):
        add_plays(self.a, self.alice, minutes_ago=30)
        add_plays(self.b, self.alice, minutes_ago=20)
        add_plays(self.a, self.alice, minutes_ago=5)
        self.assertEqual(self.recent(), [self.a.id, self.b.id])

    def test_other_users_and_logged_out_plays_are_not_included(self):
        add_plays(self.a, self.bob)
        add_plays(self.b, None)
        self.assertEqual(self.recent(), [])

    def test_lists_at_most_30_songs(self):
        for number in range(31):
            add_plays(make_song(f"Song {number}"), self.alice, minutes_ago=number)
        self.assertEqual(len(self.recent()), 30)

    def test_each_item_is_a_full_song(self):
        add_plays(self.a, self.alice)
        item = self.alice_api.get("/api/library/recent/").json()[0]
        self.assertEqual(item["title"], "A")
        self.assertEqual(item["stream_url"], f"/api/songs/{self.a.id}/stream/")

    def test_home_page_recently_played_matches(self):
        add_plays(self.a, self.alice, minutes_ago=20)
        add_plays(self.b, self.alice, minutes_ago=10)
        home = self.alice_api.get("/api/home/").json()
        self.assertEqual(ids(home["recently_played"]), [self.b.id, self.a.id])

    def test_home_page_recently_played_is_empty_when_logged_out(self):
        add_plays(self.a, None)
        self.assertEqual(self.anon.get("/api/home/").json()["recently_played"], [])


class TrendingTests(MusicTestCase):
    def trending(self):
        return ids(self.anon.get("/api/home/").json()["trending"])

    def test_orders_by_plays_in_the_last_seven_days(self):
        few, many, some = make_song("Few"), make_song("Many"), make_song("Some")
        add_plays(few, count=1)
        add_plays(many, count=5)
        add_plays(some, count=3)
        self.assertEqual(self.trending(), [many.id, some.id, few.id])

    def test_plays_older_than_a_week_do_not_count_for_the_ranking(self):
        old_hit = make_song("Old hit", play_count=500)
        new_song = make_song("New", play_count=1)
        add_plays(old_hit, count=500, days_ago=8)
        add_plays(new_song, count=1, days_ago=1)
        self.assertEqual(self.trending(), [new_song.id, old_hit.id])

    def test_all_time_plays_break_ties(self):
        popular = make_song("Popular", play_count=50)
        quiet = make_song("Quiet", play_count=2)
        self.assertEqual(self.trending(), [popular.id, quiet.id])

    def test_a_play_through_the_api_moves_a_song_up(self):
        first, second = make_song("First", play_count=10), make_song("Second", play_count=0)
        self.assertEqual(self.trending(), [first.id, second.id])
        self.bob_api.post(f"/api/songs/{second.id}/play/")
        self.assertEqual(self.trending(), [second.id, first.id])

    def test_lists_at_most_ten_songs(self):
        for number in range(12):
            make_song(f"Song {number}")
        self.assertEqual(len(self.trending()), 10)

    def test_songs_nobody_played_are_still_listed(self):
        quiet = make_song("Quiet")
        self.assertEqual(self.trending(), [quiet.id])
