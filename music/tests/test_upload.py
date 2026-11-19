"""POST /api/songs/ : what an upload accepts, rejects and stores."""
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from music.models import Album, Artist, Song

from .base import WAV, MusicTestCase, audio_upload, make_image, make_wav, stored_files

UPLOAD_URL = "/api/songs/"


class UploadTestCase(MusicTestCase):
    def upload(self, client=None, **overrides):
        """Upload as alice unless told otherwise. Pass a field as None to leave it out."""
        fields = {"audio": audio_upload(), "title": "Night Drive", "artist_name": "The Testers"}
        fields.update(overrides)
        fields = {key: value for key, value in fields.items() if value is not None}
        return (client or self.alice_api).post(UPLOAD_URL, fields, format="multipart")

    def assertNothingStored(self):
        self.assertEqual(Song.objects.count(), 0)
        self.assertEqual(stored_files(self.private_root), [])
        self.assertEqual(stored_files(self.media_root), [])


class AudioCheckTests(UploadTestCase):
    def test_real_wav_is_accepted(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data["title"], "Night Drive")
        self.assertEqual(data["artist"]["name"], "The Testers")

    def test_duration_is_read_from_the_file(self):
        data = self.upload().json()
        self.assertAlmostEqual(data["duration"], 2.0, delta=0.05)

    def test_uploader_is_the_owner(self):
        data = self.upload().json()
        self.assertTrue(data["is_owner"])
        self.assertEqual(Song.objects.get(pk=data["id"]).uploaded_by, self.alice)

    def test_upload_response_matches_the_song_shape(self):
        data = self.upload().json()
        self.assertEqual(data["stream_url"], f"/api/songs/{data['id']}/stream/")
        self.assertIsNone(data["cover_url"])
        self.assertIsNone(data["album"])
        self.assertEqual(data["license"], "")
        self.assertEqual(data["play_count"], 0)
        self.assertFalse(data["is_liked"])
        self.assertRegex(data["created_at"], r"^\d{4}-\d\d-\d\dT.*Z$")

    def test_text_file_named_mp3_is_rejected(self):
        response = self.upload(audio=audio_upload("x.mp3", b"this is just some text, not audio"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())

    def test_rejected_audio_stores_nothing(self):
        self.upload(audio=audio_upload("x.mp3", b"this is just some text, not audio"))
        self.assertNothingStored()

    def test_empty_file_is_rejected(self):
        response = self.upload(audio=audio_upload("x.wav", b""))
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())

    def test_wav_with_no_samples_is_rejected(self):
        response = self.upload(audio=audio_upload("x.wav", make_wav(seconds=0)))
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())

    def test_image_sent_as_audio_is_rejected(self):
        response = self.upload(audio=audio_upload("cover.mp3", make_image()))
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())

    def test_missing_audio_field_is_rejected(self):
        response = self.upload(audio=None)
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())

    def test_missing_title_or_artist_is_rejected(self):
        for field in ("title", "artist_name"):
            with self.subTest(missing=field):
                response = self.upload(**{field: None})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertNothingStored()

    def test_logged_out_upload_is_403(self):
        response = self.upload(client=self.anon)
        self.assertEqual(response.status_code, 403)
        self.assertNothingStored()


class StoredFileTests(UploadTestCase):
    def stored_name(self, **overrides):
        data = self.upload(**overrides).json()
        return Song.objects.get(pk=data["id"]).audio.name

    def test_stored_name_is_random_not_the_uploaded_name(self):
        name = self.stored_name()
        self.assertRegex(name, r"^audio/[0-9a-f]{32}\.wav$")
        self.assertNotIn("Secret", name)

    def test_same_upload_twice_gets_two_different_stored_names(self):
        self.assertNotEqual(self.stored_name(), self.stored_name())

    def test_stored_extension_follows_the_detected_format_not_the_uploaded_name(self):
        for client_name in ("song.mp3", "song.html", "song", "SONG.FLAC", "../../x.php"):
            with self.subTest(uploaded_as=client_name):
                name = self.stored_name(audio=audio_upload(client_name))
                self.assertTrue(name.endswith(".wav"), name)

    def test_audio_goes_to_the_private_folder_with_the_exact_bytes(self):
        song = Song.objects.get(pk=self.upload().json()["id"])
        self.assertTrue(song.audio.path.startswith(os.path.abspath(self.private_root)))
        with open(song.audio.path, "rb") as stored:
            self.assertEqual(stored.read(), WAV)
        self.assertEqual(stored_files(self.media_root), [])


class CoverTests(UploadTestCase):
    def test_fake_cover_image_is_rejected(self):
        fake = SimpleUploadedFile("x.png", b"not an image at all", content_type="image/png")
        response = self.upload(cover=fake)
        self.assertEqual(response.status_code, 400)
        self.assertIn("cover", response.json())
        self.assertNotIn("audio", response.json())

    def test_rejected_cover_stores_nothing(self):
        fake = SimpleUploadedFile("x.png", b"not an image at all", content_type="image/png")
        self.upload(cover=fake)
        self.assertNothingStored()

    def test_real_png_cover_is_accepted(self):
        png = SimpleUploadedFile("cover.png", make_image(), content_type="image/png")
        response = self.upload(cover=png)
        self.assertEqual(response.status_code, 201, response.content)
        cover_url = response.json()["cover_url"]
        self.assertTrue(cover_url.startswith("/media/covers/"), cover_url)
        self.assertTrue(cover_url.endswith(".jpg"), cover_url)

    def test_cover_is_stored_as_a_fresh_jpeg(self):
        png = SimpleUploadedFile("cover.png", make_image(), content_type="image/png")
        cover_url = self.upload(cover=png).json()["cover_url"]
        path = os.path.join(self.media_root, cover_url.removeprefix("/media/"))
        with Image.open(path) as stored:
            self.assertEqual(stored.format, "JPEG")

    def test_large_cover_is_shrunk_to_800_pixels(self):
        big = SimpleUploadedFile("big.png", make_image(1600, 1200), content_type="image/png")
        cover_url = self.upload(cover=big).json()["cover_url"]
        path = os.path.join(self.media_root, cover_url.removeprefix("/media/"))
        with Image.open(path) as stored:
            self.assertEqual(stored.size, (800, 600))

    def test_cover_over_the_size_limit_is_rejected(self):
        png = SimpleUploadedFile("cover.png", make_image(), content_type="image/png")
        with self.settings(MAX_COVER_UPLOAD_BYTES=100):
            response = self.upload(cover=png)
        self.assertEqual(response.status_code, 400)
        self.assertIn("cover", response.json())


class SizeLimitTests(UploadTestCase):
    def test_file_over_the_limit_is_rejected(self):
        with self.settings(MAX_AUDIO_UPLOAD_BYTES=1000):
            response = self.upload()
        self.assertEqual(response.status_code, 400)
        self.assertIn("audio", response.json())
        self.assertNothingStored()

    def test_file_one_byte_over_the_limit_is_rejected(self):
        with self.settings(MAX_AUDIO_UPLOAD_BYTES=len(WAV) - 1):
            response = self.upload()
        self.assertEqual(response.status_code, 400)

    def test_file_exactly_at_the_limit_is_accepted(self):
        with self.settings(MAX_AUDIO_UPLOAD_BYTES=len(WAV)):
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.content)


class BodySizeTests(UploadTestCase):
    def test_body_far_over_both_limits_is_413_before_it_is_parsed(self):
        # views.py refuses a body larger than audio limit + cover limit + 1 MB; the file content is irrelevant
        huge = audio_upload("big.wav", b"x" * (1024 * 1024 + 5000))
        with self.settings(MAX_AUDIO_UPLOAD_BYTES=1000, MAX_COVER_UPLOAD_BYTES=1000):
            response = self.upload(audio=huge)
        self.assertEqual(response.status_code, 413)
        self.assertIn("detail", response.json())
        self.assertNothingStored()


class MetadataTests(UploadTestCase):
    def test_upload_is_private_by_default(self):
        self.assertFalse(self.upload().json()["is_public"])

    def test_is_public_true_makes_it_public(self):
        self.assertTrue(self.upload(is_public="true").json()["is_public"])

    def test_is_public_false_stays_private(self):
        self.assertFalse(self.upload(is_public="false").json()["is_public"])

    def test_album_and_genre_are_stored(self):
        data = self.upload(album_title="Road Songs", genre="Lo-fi").json()
        self.assertEqual(data["album"]["title"], "Road Songs")
        self.assertEqual(data["genre"], "Lo-fi")

    def test_artist_is_reused_ignoring_case(self):
        self.upload(artist_name="Kevin MacLeod")
        self.upload(artist_name="kevin macleod", title="Second")
        self.assertEqual(Artist.objects.count(), 1)
        self.assertEqual(Song.objects.values("artist").distinct().count(), 1)

    def test_album_is_reused_ignoring_case_for_the_same_artist(self):
        self.upload(album_title="Road Songs")
        self.upload(album_title="ROAD songs", title="Second")
        self.assertEqual(Album.objects.count(), 1)

    def test_genre_spelling_of_the_first_upload_is_kept(self):
        self.upload(genre="Lo-fi")
        second = self.upload(genre="lo-fi", title="Second").json()
        self.assertEqual(second["genre"], "Lo-fi")

    def test_title_and_artist_are_trimmed(self):
        data = self.upload(title="  Padded  ", artist_name="  Spaced Out ").json()
        self.assertEqual(data["title"], "Padded")
        self.assertEqual(data["artist"]["name"], "Spaced Out")

    def test_title_over_200_characters_is_rejected(self):
        response = self.upload(title="x" * 201)
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.json())
