import colorsys
import hashlib

from django.conf import settings
from django.urls import reverse
from rest_framework import serializers

from .models import Album, Artist, Like, Playlist, PlaylistItem, Song


def colors_for(key):
    """Two hex colours derived from a stable key, for cover gradients.

    Same key = same colours on every request and machine (sha256, not hash(), which is salted).
    """
    digest = hashlib.sha256(key.encode()).digest()
    hue1 = digest[0] / 255
    hue2 = (hue1 + 0.08 + digest[1] / 255 * 0.3) % 1
    dark = colorsys.hls_to_rgb(hue1, 0.30, 0.55)
    light = colorsys.hls_to_rgb(hue2, 0.55, 0.70)
    return ["#%02x%02x%02x" % tuple(round(c * 255) for c in rgb) for rgb in (dark, light)]


def media_url(name):
    return f"{settings.MEDIA_URL}{name}" if name else None


def _request_user(context):
    request = context.get("request")
    return getattr(request, "user", None)


class ArtistRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class AlbumRefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class SongSerializer(serializers.ModelSerializer):
    artist = ArtistRefSerializer()
    album = AlbumRefSerializer(allow_null=True)
    cover_url = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()
    stream_url = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Song
        fields = [
            "id", "title", "artist", "album", "duration", "genre", "cover_url", "colors",
            "stream_url", "play_count", "is_liked", "is_public", "is_owner", "license",
            "attribution", "source_url", "created_at",
        ]

    def _liked_ids(self):
        # Cached on the root serializer's context: one query per response, not per song.
        ctx = self.context
        if "_liked_ids" not in ctx:
            user = _request_user(ctx)
            ctx["_liked_ids"] = (
                set(Like.objects.filter(user=user).values_list("song_id", flat=True))
                if user is not None and user.is_authenticated
                else set()
            )
        return ctx["_liked_ids"]

    def get_cover_url(self, song):
        if song.cover:
            return media_url(song.cover.name)
        if song.album_id and song.album.cover:
            return media_url(song.album.cover.name)
        return None

    def get_colors(self, song):
        return colors_for(f"album:{song.album_id}" if song.album_id else f"song:{song.id}")

    def get_stream_url(self, song):
        return reverse("song-stream", args=[song.id])

    def get_is_liked(self, song):
        return song.id in self._liked_ids()

    def get_is_owner(self, song):
        user = _request_user(self.context)
        return bool(user is not None and user.is_authenticated and song.uploaded_by_id == user.id)


class AlbumSerializer(serializers.ModelSerializer):
    """List item. Views annotate `song_count` and `first_cover` (visible songs only)."""

    artist = ArtistRefSerializer()
    cover_url = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()
    song_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Album
        fields = ["id", "title", "artist", "year", "cover_url", "colors", "song_count"]

    def get_cover_url(self, album):
        if album.cover:
            return media_url(album.cover.name)
        return media_url(getattr(album, "first_cover", None))

    def get_colors(self, album):
        return colors_for(f"album:{album.id}")


class AlbumDetailSerializer(AlbumSerializer):
    songs = serializers.SerializerMethodField()

    class Meta(AlbumSerializer.Meta):
        fields = AlbumSerializer.Meta.fields + ["songs"]

    def get_songs(self, album):
        return SongSerializer(self.context["songs"], many=True, context=self.context).data


class ArtistSerializer(serializers.ModelSerializer):
    """List item. Views annotate `song_count` (visible songs only)."""

    image_url = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()
    song_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Artist
        fields = ["id", "name", "image_url", "colors", "song_count"]

    def get_image_url(self, artist):
        return media_url(artist.image.name) if artist.image else None

    def get_colors(self, artist):
        return colors_for(f"artist:{artist.id}")


class ArtistDetailSerializer(ArtistSerializer):
    top_songs = serializers.SerializerMethodField()
    albums = serializers.SerializerMethodField()

    class Meta(ArtistSerializer.Meta):
        fields = ArtistSerializer.Meta.fields + ["bio", "top_songs", "albums"]

    def get_top_songs(self, artist):
        return SongSerializer(self.context["top_songs"], many=True, context=self.context).data

    def get_albums(self, artist):
        return AlbumSerializer(self.context["albums"], many=True, context=self.context).data


class PlaylistSerializer(serializers.ModelSerializer):
    """List item. Songs are the ones the requesting user may see, in playlist order."""

    owner = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()
    cover_urls = serializers.SerializerMethodField()
    song_count = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [
            "id", "name", "description", "is_public", "owner", "is_owner", "colors",
            "cover_urls", "song_count", "duration", "updated_at",
        ]

    def visible_songs(self, playlist):
        cache = self.context.setdefault("_playlist_songs", {})
        if playlist.id not in cache:
            user = _request_user(self.context)
            items = (
                PlaylistItem.objects.filter(playlist=playlist, song__in=Song.objects.visible_to(user))
                .select_related("song__artist", "song__album")
                .order_by("position", "id")
            )
            cache[playlist.id] = [item.song for item in items]
        return cache[playlist.id]

    def get_owner(self, playlist):
        return {"id": playlist.owner_id, "username": playlist.owner.username}

    def get_is_owner(self, playlist):
        user = _request_user(self.context)
        return bool(user is not None and user.is_authenticated and playlist.owner_id == user.id)

    def get_colors(self, playlist):
        return colors_for(f"playlist:{playlist.id}")

    def get_cover_urls(self, playlist):
        urls = []
        for song in self.visible_songs(playlist):
            name = song.cover.name if song.cover else (song.album.cover.name if song.album_id and song.album.cover else "")
            url = media_url(name)
            if url and url not in urls:
                urls.append(url)
            if len(urls) == 4:
                break
        return urls

    def get_song_count(self, playlist):
        return len(self.visible_songs(playlist))

    def get_duration(self, playlist):
        return round(sum(song.duration for song in self.visible_songs(playlist)), 2)


class PlaylistDetailSerializer(PlaylistSerializer):
    songs = serializers.SerializerMethodField()

    class Meta(PlaylistSerializer.Meta):
        fields = PlaylistSerializer.Meta.fields + ["songs"]

    def get_songs(self, playlist):
        return SongSerializer(self.visible_songs(playlist), many=True, context=self.context).data


class PlaylistWriteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(min_length=1, max_length=100, trim_whitespace=True)
    description = serializers.CharField(max_length=300, allow_blank=True, required=False, trim_whitespace=True)
    is_public = serializers.BooleanField(required=False)

    class Meta:
        model = Playlist
        fields = ["name", "description", "is_public"]


class SongUploadSerializer(serializers.Serializer):
    """Form fields of POST /api/songs/. File contents are checked in music/uploads.py."""

    audio = serializers.FileField()
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    artist_name = serializers.CharField(max_length=200, trim_whitespace=True)
    album_title = serializers.CharField(max_length=200, allow_blank=True, required=False, trim_whitespace=True)
    genre = serializers.CharField(max_length=50, allow_blank=True, required=False, trim_whitespace=True)
    cover = serializers.FileField(required=False, allow_null=True)
    is_public = serializers.BooleanField(required=False, default=False)


class ReorderSerializer(serializers.Serializer):
    song_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)


class AddSongSerializer(serializers.Serializer):
    song_id = serializers.IntegerField()
