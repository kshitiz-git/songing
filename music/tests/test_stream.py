"""GET /api/songs/<id>/stream/ : the audio bytes and HTTP Range support."""
import os

from .base import WAV, MusicTestCase, make_song

SIZE = len(WAV)


def body(response):
    return b"".join(response.streaming_content)


class StreamTestCase(MusicTestCase):
    def setUp(self):
        super().setUp()
        self.song = make_song("Streamed", is_public=True)
        self.url = f"/api/songs/{self.song.id}/stream/"

    def get(self, range_header=None):
        extra = {"HTTP_RANGE": range_header} if range_header is not None else {}
        return self.anon.get(self.url, **extra)


class WholeFileTests(StreamTestCase):
    def test_no_range_header_gives_200_and_the_full_file(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body(response), WAV)

    def test_full_response_advertises_range_support_and_length(self):
        response = self.get()
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Length"], str(SIZE))
        self.assertNotIn("Content-Range", response)

    def test_content_type_is_audio(self):
        self.assertTrue(self.get()["Content-Type"].startswith("audio/"))

    def test_response_is_not_cacheable_by_shared_caches(self):
        self.assertIn("private", self.get()["Cache-Control"])

    def test_head_request_has_the_headers_and_no_body(self):
        response = self.anon.head(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Length"], str(SIZE))
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response.content, b"")

    def test_post_is_not_allowed(self):
        self.assertEqual(self.anon.post(self.url).status_code, 405)

    def test_unknown_song_is_404_json(self):
        response = self.anon.get("/api/songs/999999/stream/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_song_whose_file_is_gone_from_disk_is_404(self):
        os.remove(self.song.audio.path)
        response = self.get()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})


class RangeTests(StreamTestCase):
    def test_closed_range_gives_206_with_exactly_those_bytes(self):
        response = self.get("bytes=100-199")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(body(response), WAV[100:200])

    def test_closed_range_headers(self):
        response = self.get("bytes=100-199")
        self.assertEqual(response["Content-Range"], f"bytes 100-199/{SIZE}")
        self.assertEqual(response["Content-Length"], "100")
        self.assertEqual(response["Accept-Ranges"], "bytes")

    def test_range_body_is_not_the_start_of_the_file(self):
        # guards against a server that ignores the offset: the sample pattern repeats every 251 bytes
        self.assertNotEqual(WAV[100:200], WAV[0:100])
        self.assertNotEqual(body(self.get("bytes=100-199")), WAV[0:100])

    def test_open_range_runs_to_the_end_of_the_file(self):
        response = self.get("bytes=100-")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes 100-{SIZE - 1}/{SIZE}")
        self.assertEqual(response["Content-Length"], str(SIZE - 100))
        self.assertEqual(body(response), WAV[100:])

    def test_suffix_range_gives_the_last_bytes(self):
        response = self.get("bytes=-10")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes {SIZE - 10}-{SIZE - 1}/{SIZE}")
        self.assertEqual(response["Content-Length"], "10")
        self.assertEqual(body(response), WAV[-10:])

    def test_first_byte_only(self):
        response = self.get("bytes=0-0")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes 0-0/{SIZE}")
        self.assertEqual(body(response), WAV[:1])

    def test_last_byte_only(self):
        response = self.get(f"bytes={SIZE - 1}-{SIZE - 1}")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(body(response), WAV[-1:])

    def test_range_end_past_the_file_is_clamped(self):
        response = self.get(f"bytes=100-{SIZE * 10}")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes 100-{SIZE - 1}/{SIZE}")
        self.assertEqual(body(response), WAV[100:])

    def test_suffix_longer_than_the_file_gives_the_whole_file(self):
        response = self.get(f"bytes=-{SIZE * 10}")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Range"], f"bytes 0-{SIZE - 1}/{SIZE}")
        self.assertEqual(body(response), WAV)

    def test_range_starting_at_the_file_size_is_416(self):
        response = self.get(f"bytes={SIZE}-")
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response["Content-Range"], f"bytes */{SIZE}")

    def test_range_far_past_the_file_is_416(self):
        response = self.get(f"bytes={SIZE + 5000}-{SIZE + 6000}")
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response["Content-Range"], f"bytes */{SIZE}")

    def test_zero_length_suffix_is_416(self):
        response = self.get("bytes=-0")
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response["Content-Range"], f"bytes */{SIZE}")

    def test_unsatisfiable_range_has_no_audio_body(self):
        self.assertEqual(self.get(f"bytes={SIZE}-").content, b"")

    def test_ranges_the_server_does_not_understand_get_the_whole_file(self):
        # api.md promises single ranges only; the module docstring says anything else gets a 200
        for header in ("bytes=abc", "items=0-5", "bytes=0-9,20-29", "bytes=-", ""):
            with self.subTest(header=header):
                response = self.get(header)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body(response), WAV)

    def test_head_with_range_reports_the_partial_length(self):
        response = self.anon.head(self.url, HTTP_RANGE="bytes=100-199")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Content-Length"], "100")
        self.assertEqual(response["Content-Range"], f"bytes 100-199/{SIZE}")
        self.assertEqual(response.content, b"")

    def test_two_ranges_in_a_row_reassemble_the_file(self):
        first = body(self.get("bytes=0-9999"))
        second = body(self.get("bytes=10000-"))
        self.assertEqual(first + second, WAV)


class PrivateStreamTests(StreamTestCase):
    def setUp(self):
        super().setUp()
        self.private = make_song("Mine", uploader=self.alice, is_public=False)
        self.private_url = f"/api/songs/{self.private.id}/stream/"

    def test_owner_can_stream_and_seek_in_a_private_song(self):
        response = self.alice_api.get(self.private_url, HTTP_RANGE="bytes=100-199")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(body(response), WAV[100:200])

    def test_another_user_gets_404(self):
        self.assertEqual(self.bob_api.get(self.private_url).status_code, 404)

    def test_logged_out_visitor_gets_404(self):
        self.assertEqual(self.anon.get(self.private_url).status_code, 404)
