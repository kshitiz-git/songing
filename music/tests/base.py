"""Shared setup for the music tests: temp media folders, fast hashing, a few factories.

Every test class that touches songs inherits MusicTestCase. It points MEDIA_ROOT and
PRIVATE_MEDIA_ROOT at fresh temp folders, so the real media folders are never written to,
and clears the default cache, where the throttle counters live.
"""
import io
import os
import shutil
import tempfile
import wave

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient, APITestCase

from music.models import Album, Artist, Song

User = get_user_model()
PASSWORD = "correct-horse-battery-7"


def make_wav(seconds=2, rate=8000):
    """A real mono 16-bit WAV (2 s at 8 kHz = 32044 bytes).

    The samples are a repeating pattern, not silence, so a test that reads the wrong byte
    range of the file notices.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(i % 251 for i in range(2 * rate * seconds)))
    return buffer.getvalue()


def make_image(width=40, height=30, fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 40, 40)).save(buffer, format=fmt)
    return buffer.getvalue()


WAV = make_wav()  # built once; every factory song stores a copy of it


def make_user(username="alice"):
    return User.objects.create_user(username, password=PASSWORD)


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


def make_song(title="Song", artist="Some Artist", album=None, uploader=None, is_public=True,
              genre="", **fields):
    """A song with a real WAV stored through the model, like the seeder does."""
    artist_row, _ = Artist.objects.get_or_create(name=artist)
    album_row = Album.objects.get_or_create(title=album, artist=artist_row)[0] if album else None
    return Song.objects.create(
        title=title, artist=artist_row, album=album_row, genre=genre, uploaded_by=uploader,
        is_public=is_public, duration=2.0, audio=ContentFile(WAV, name="song.wav"), **fields,
    )


def ids(items):
    return [item["id"] for item in items]


def stored_files(root):
    """Every file under a folder, as paths relative to it."""
    return [
        os.path.relpath(os.path.join(folder, name), root)
        for folder, _, names in os.walk(root)
        for name in names
    ]


class MusicTestCase(APITestCase):
    """Temp media folders, cleared throttles, two users and their API clients.

    self.client / self.anon is logged out; self.alice_api and self.bob_api are logged in.
    """

    def setUp(self):
        cache.clear()
        self.media_root = tempfile.mkdtemp(prefix="songing-media-")
        self.private_root = tempfile.mkdtemp(prefix="songing-private-")
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.private_root, ignore_errors=True)
        override = override_settings(
            MEDIA_ROOT=self.media_root,
            PRIVATE_MEDIA_ROOT=self.private_root,
            # the real hasher takes about half a second per user
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        override.enable()
        self.addCleanup(override.disable)

        self.anon = self.client
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.alice_api = client_for(self.alice)
        self.bob_api = client_for(self.bob)


def audio_upload(name="My Secret Song.mp3", data=None):
    """A multipart-ready audio file. The name and content type are what a browser would send."""
    return SimpleUploadedFile(name, WAV if data is None else data, content_type="audio/mpeg")
