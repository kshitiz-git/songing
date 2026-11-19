import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class PrivateAudioStorage(FileSystemStorage):
    """Song audio lives outside MEDIA_ROOT, so no URL serves it directly.

    The only way to hear a song is /api/songs/<id>/stream/, which checks who may hear it.
    The location is read from settings on every use so tests can point it at a temp dir.
    """

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)


audio_storage = PrivateAudioStorage()


def audio_upload_to(instance, filename):
    """Random stored name, keeping only the (already validated) extension."""
    ext = os.path.splitext(filename)[1].lower()
    return f"audio/{uuid.uuid4().hex}{ext}"


def cover_upload_to(instance, filename):
    """Covers are re-encoded to JPEG before saving, so the extension is always .jpg."""
    return f"covers/{uuid.uuid4().hex}.jpg"


def visible_song_q(user, prefix=""):
    """Q for songs a user may see: public ones, plus their own private uploads.

    `prefix` lets other models filter through a relation, e.g. prefix="songs__".
    """
    q = Q(**{f"{prefix}is_public": True})
    if user is not None and user.is_authenticated:
        q |= Q(**{f"{prefix}uploaded_by": user})
    return q


class Artist(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    image = models.ImageField(upload_to=cover_upload_to, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="artist_name_unique_ci"),
        ]

    def __str__(self):
        return self.name


class Album(models.Model):
    title = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="albums")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    cover = models.ImageField(upload_to=cover_upload_to, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(Lower("title"), "artist", name="album_title_unique_per_artist_ci"),
        ]

    def __str__(self):
        return f"{self.title} ({self.artist})"


class SongQuerySet(models.QuerySet):
    def visible_to(self, user):
        return self.filter(visible_song_q(user))


class Song(models.Model):
    title = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="songs")
    album = models.ForeignKey(
        Album, on_delete=models.SET_NULL, null=True, blank=True, related_name="songs"
    )
    track_number = models.PositiveSmallIntegerField(null=True, blank=True)
    audio = models.FileField(storage=audio_storage, upload_to=audio_upload_to)
    duration = models.FloatField(default=0, help_text="Seconds, read from the file with mutagen.")
    genre = models.CharField(max_length=50, blank=True, db_index=True)
    cover = models.ImageField(upload_to=cover_upload_to, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="uploads",
        help_text="Empty for demo / catalogue songs.",
    )
    is_public = models.BooleanField(default=False)
    license = models.CharField(max_length=100, blank=True)
    attribution = models.TextField(blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    play_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = SongQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.artist}"


class Playlist(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="playlists"
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    is_public = models.BooleanField(default=False)
    songs = models.ManyToManyField(Song, through="PlaylistItem", related_name="playlists")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class PlaylistItem(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="items")
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="playlist_items")
    position = models.PositiveIntegerField()
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["playlist", "song"], name="song_once_per_playlist"),
        ]

    def __str__(self):
        return f"{self.playlist} #{self.position}: {self.song}"


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "song"], name="like_once_per_user"),
        ]

    def __str__(self):
        return f"{self.user} likes {self.song}"


class PlayEvent(models.Model):
    """One counted play (30 s of listening, or a whole short song)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="play_events",
    )
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="play_events")
    played_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-played_at"]
        indexes = [models.Index(fields=["user", "-played_at"], name="play_user_recent_idx")]

    def __str__(self):
        return f"{self.song} at {self.played_at:%Y-%m-%d %H:%M}"
