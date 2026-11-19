import random
from collections import Counter
from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Album, Artist, Like, PlayEvent, Playlist, PlaylistItem, Song, visible_song_q
from .serializers import (
    AddSongSerializer,
    AlbumDetailSerializer,
    AlbumSerializer,
    ArtistDetailSerializer,
    ArtistSerializer,
    PlaylistDetailSerializer,
    PlaylistSerializer,
    PlaylistWriteSerializer,
    ReorderSerializer,
    SongSerializer,
    SongUploadSerializer,
)
from .uploads import check_audio, process_cover

SEARCH_MAX_LEN = 100


# ---------------------------------------------------------------- query helpers

def visible_songs(user):
    return Song.objects.visible_to(user).select_related("artist", "album")


def visible_albums(user):
    """Albums with at least one song this user may see, annotated for AlbumSerializer."""
    first_cover = (
        Song.objects.visible_to(user)
        .filter(album=OuterRef("pk"))
        .exclude(cover="")
        .order_by("track_number", "id")
        .values("cover")[:1]
    )
    return (
        Album.objects.select_related("artist")
        .annotate(
            song_count=Count("songs", filter=visible_song_q(user, "songs__"), distinct=True),
            first_cover=Subquery(first_cover),
        )
        .filter(song_count__gt=0)
    )


def visible_artists(user):
    """Artists with at least one song this user may see, annotated for ArtistSerializer."""
    q = visible_song_q(user, "songs__")
    return Artist.objects.annotate(
        song_count=Count("songs", filter=q, distinct=True),
        total_plays=Sum("songs__play_count", filter=q),
    ).filter(song_count__gt=0)


def visible_playlists(user):
    q = Q(is_public=True)
    if user.is_authenticated:
        q |= Q(owner=user)
    return Playlist.objects.filter(q).select_related("owner")


def songs_data(songs, request):
    return SongSerializer(songs, many=True, context={"request": request}).data


def paginated(request, view, queryset, serialize):
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(serialize(page))


def recent_songs(user, limit):
    """Songs the user played, newest play first, each song once."""
    rows = (
        PlayEvent.objects.filter(user=user)
        .values("song_id")
        .annotate(last_played=Max("played_at"))
        .order_by("-last_played")[: limit * 2]  # some may have become hidden since
    )
    ids = [row["song_id"] for row in rows]
    by_id = {song.id: song for song in visible_songs(user).filter(id__in=ids)}
    return [by_id[i] for i in ids if i in by_id][:limit]


def made_for_you(user, limit=10):
    """Random picks from the user's favourite genres (likes + plays), topped up at random."""
    songs = visible_songs(user)
    if not user.is_authenticated:
        return list(songs.order_by("?")[:limit])
    liked_ids = set(Like.objects.filter(user=user).values_list("song_id", flat=True))
    genres = Counter(
        g for g in Song.objects.filter(likes__user=user).values_list("genre", flat=True) if g
    )
    genres.update(
        g for g in Song.objects.filter(play_events__user=user).values_list("genre", flat=True)[:200] if g
    )
    top = [g for g, _ in genres.most_common(3)]
    picks = list(songs.filter(genre__in=top).exclude(id__in=liked_ids).order_by("?")[:limit]) if top else []
    if len(picks) < limit:
        taken = {s.id for s in picks}
        picks += list(songs.exclude(id__in=taken).order_by("?")[: limit - len(picks)])
    random.shuffle(picks)
    return picks


def existing_or_new_artist(name):
    artist = Artist.objects.filter(name__iexact=name).first()
    if artist:
        return artist
    try:
        with transaction.atomic():
            return Artist.objects.create(name=name)
    except IntegrityError:  # created by a parallel request
        return Artist.objects.get(name__iexact=name)


def existing_or_new_album(title, artist):
    album = Album.objects.filter(title__iexact=title, artist=artist).first()
    if album:
        return album
    try:
        with transaction.atomic():
            return Album.objects.create(title=title, artist=artist)
    except IntegrityError:
        return Album.objects.get(title__iexact=title, artist=artist)


def get_visible_song(user, pk):
    return get_object_or_404(visible_songs(user), pk=pk)


# ---------------------------------------------------------------- browse

class HomeView(APIView):
    def get(self, request):
        user = request.user
        week_ago = timezone.now() - timedelta(days=7)
        trending = (
            visible_songs(user)
            .annotate(recent_plays=Count("play_events", filter=Q(play_events__played_at__gte=week_ago)))
            .order_by("-recent_plays", "-play_count", "-created_at")[:10]
        )
        albums = visible_albums(user).order_by("-created_at")[:10]
        artists = visible_artists(user).order_by(F("total_plays").desc(nulls_last=True), "name")[:10]
        ctx = {"request": request}
        return Response({
            "trending": SongSerializer(trending, many=True, context=ctx).data,
            "new_releases": AlbumSerializer(albums, many=True, context=ctx).data,
            "artists": ArtistSerializer(artists, many=True, context=ctx).data,
            "recently_played": (
                SongSerializer(recent_songs(user, 10), many=True, context=ctx).data
                if user.is_authenticated else []
            ),
            "made_for_you": SongSerializer(made_for_you(user), many=True, context=ctx).data,
        })


class SongListCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get(self, request):
        songs = visible_songs(request.user)
        q = request.query_params.get("q", "").strip()[:SEARCH_MAX_LEN]
        genre = request.query_params.get("genre", "").strip()[:50]
        if q:
            songs = songs.filter(Q(title__icontains=q) | Q(artist__name__icontains=q))
        if genre:
            songs = songs.filter(genre__iexact=genre)
        songs = songs.order_by("-play_count", "title", "id")
        return paginated(request, self, songs, lambda page: songs_data(page, request))

    def post(self, request):
        form = SongUploadSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        errors = {}
        try:
            ext, duration = check_audio(data["audio"])
        except DjangoValidationError as exc:
            errors["audio"] = exc.messages
        cover_file = None
        if data.get("cover"):
            try:
                cover_file = process_cover(data["cover"])
            except DjangoValidationError as exc:
                errors["cover"] = exc.messages
        if errors:
            raise ValidationError(errors)

        genre = data.get("genre", "")
        if genre:  # reuse the existing spelling, so "lo-fi" and "Lo-fi" stay one genre
            genre = Song.objects.filter(genre__iexact=genre).values_list("genre", flat=True).first() or genre

        artist = existing_or_new_artist(data["artist_name"])
        album_title = data.get("album_title", "")
        album = existing_or_new_album(album_title, artist) if album_title else None
        song = Song(
            title=data["title"],
            artist=artist,
            album=album,
            genre=genre,
            duration=duration,
            uploaded_by=request.user,
            is_public=data.get("is_public", False),
        )
        song.audio.save(f"upload{ext}", data["audio"], save=False)
        if cover_file is not None:
            song.cover.save("cover.jpg", cover_file, save=False)
        song.save()
        return Response(SongSerializer(song, context={"request": request}).data, status=status.HTTP_201_CREATED)


class SongDetailView(APIView):
    def get(self, request, pk):
        song = get_visible_song(request.user, pk)
        return Response(SongSerializer(song, context={"request": request}).data)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            raise PermissionDenied("Log in to delete songs.")
        song = get_visible_song(request.user, pk)
        if song.uploaded_by_id != request.user.id:
            raise PermissionDenied("Only the uploader can delete this song.")
        song.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SongPlayView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "play"

    def post(self, request, pk):
        song = get_visible_song(request.user, pk)
        with transaction.atomic():
            Song.objects.filter(pk=song.pk).update(play_count=F("play_count") + 1)
            PlayEvent.objects.create(song=song, user=request.user if request.user.is_authenticated else None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SongLikeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        song = get_visible_song(request.user, pk)
        try:
            with transaction.atomic():
                Like.objects.get_or_create(user=request.user, song=song)
        except IntegrityError:  # a parallel request liked it first: still liked
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request, pk):
        song = get_visible_song(request.user, pk)
        Like.objects.filter(user=request.user, song=song).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlbumListView(APIView):
    def get(self, request):
        albums = visible_albums(request.user).order_by("title", "id")
        ctx = {"request": request}
        return paginated(request, self, albums, lambda page: AlbumSerializer(page, many=True, context=ctx).data)


class AlbumDetailView(APIView):
    def get(self, request, pk):
        album = get_object_or_404(visible_albums(request.user), pk=pk)
        songs = (
            visible_songs(request.user)
            .filter(album=album)
            .order_by(F("track_number").asc(nulls_last=True), "title", "id")
        )
        ctx = {"request": request, "songs": songs}
        return Response(AlbumDetailSerializer(album, context=ctx).data)


class ArtistListView(APIView):
    def get(self, request):
        artists = visible_artists(request.user).order_by("name", "id")
        ctx = {"request": request}
        return paginated(request, self, artists, lambda page: ArtistSerializer(page, many=True, context=ctx).data)


class ArtistDetailView(APIView):
    def get(self, request, pk):
        user = request.user
        artist = get_object_or_404(visible_artists(user), pk=pk)
        ctx = {
            "request": request,
            "top_songs": visible_songs(user).filter(artist=artist).order_by("-play_count", "title")[:10],
            "albums": visible_albums(user).filter(artist=artist).order_by(
                F("year").desc(nulls_last=True), "title"
            ),
        }
        return Response(ArtistDetailSerializer(artist, context=ctx).data)


class GenreListView(APIView):
    def get(self, request):
        genres = (
            Song.objects.visible_to(request.user)
            .exclude(genre="")
            .values_list("genre", flat=True)
            .distinct()
            .order_by("genre")
        )
        return Response(list(genres))


class SearchView(APIView):
    def get(self, request):
        q = request.query_params.get("q", "").strip()[:SEARCH_MAX_LEN]
        if not q:
            return Response({"songs": [], "artists": [], "albums": [], "playlists": []})
        user = request.user
        ctx = {"request": request}
        songs = (
            visible_songs(user)
            .filter(Q(title__icontains=q) | Q(artist__name__icontains=q))
            .order_by("-play_count", "title")[:20]
        )
        artists = visible_artists(user).filter(name__icontains=q).order_by("name")[:10]
        albums = visible_albums(user).filter(title__icontains=q).order_by("title")[:10]
        playlists = visible_playlists(user).filter(name__icontains=q).order_by("-updated_at")[:10]
        return Response({
            "songs": SongSerializer(songs, many=True, context=ctx).data,
            "artists": ArtistSerializer(artists, many=True, context=ctx).data,
            "albums": AlbumSerializer(albums, many=True, context=ctx).data,
            "playlists": PlaylistSerializer(playlists, many=True, context=ctx).data,
        })


# ---------------------------------------------------------------- library

class LikedSongsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        likes = (
            Like.objects.filter(user=request.user, song__in=Song.objects.visible_to(request.user))
            .select_related("song__artist", "song__album")
            .order_by("-created_at", "-id")
        )
        return paginated(request, self, likes, lambda page: songs_data([like.song for like in page], request))


class RecentSongsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(songs_data(recent_songs(request.user, 30), request))


class UploadedSongsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        songs = (
            Song.objects.filter(uploaded_by=request.user)
            .select_related("artist", "album")
            .order_by("-created_at", "-id")
        )
        return paginated(request, self, songs, lambda page: songs_data(page, request))


# ---------------------------------------------------------------- playlists

def get_playlist(request, pk, owner_only=False):
    """Someone else's private playlist is 404; someone else's public one is 403 for edits."""
    playlist = get_object_or_404(visible_playlists(request.user), pk=pk)
    if owner_only and playlist.owner_id != request.user.id:
        raise PermissionDenied("Only the owner can change this playlist.")
    return playlist


def playlist_detail(request, playlist, code=status.HTTP_200_OK):
    return Response(PlaylistDetailSerializer(playlist, context={"request": request}).data, status=code)


class PlaylistListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        playlists = Playlist.objects.filter(owner=request.user).select_related("owner").order_by("-updated_at", "-id")
        return Response(PlaylistSerializer(playlists, many=True, context={"request": request}).data)

    def post(self, request):
        form = PlaylistWriteSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        playlist = form.save(owner=request.user)
        return playlist_detail(request, playlist, status.HTTP_201_CREATED)


class PlaylistDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request, pk):
        return playlist_detail(request, get_playlist(request, pk))

    def patch(self, request, pk):
        playlist = get_playlist(request, pk, owner_only=True)
        form = PlaylistWriteSerializer(playlist, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        form.save()
        return playlist_detail(request, playlist)

    def delete(self, request, pk):
        get_playlist(request, pk, owner_only=True).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistSongsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        playlist = get_playlist(request, pk, owner_only=True)
        form = AddSongSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        song = visible_songs(request.user).filter(pk=form.validated_data["song_id"]).first()
        if song is None:
            raise ValidationError({"song_id": ["Song not found."]})
        with transaction.atomic():
            if PlaylistItem.objects.filter(playlist=playlist, song=song).exists():
                return playlist_detail(request, playlist, status.HTTP_200_OK)
            last = playlist.items.aggregate(last=Max("position"))["last"]
            try:
                with transaction.atomic():
                    PlaylistItem.objects.create(playlist=playlist, song=song, position=0 if last is None else last + 1)
            except IntegrityError:  # added by a parallel request
                return playlist_detail(request, playlist, status.HTTP_200_OK)
            playlist.save(update_fields=["updated_at"])
        return playlist_detail(request, playlist, status.HTTP_201_CREATED)


def renumber(playlist, song_ids_in_order):
    """Write positions 0..n-1 for the given song order."""
    items = {item.song_id: item for item in playlist.items.all()}
    changed = []
    for position, song_id in enumerate(song_ids_in_order):
        item = items[song_id]
        if item.position != position:
            item.position = position
            changed.append(item)
    PlaylistItem.objects.bulk_update(changed, ["position"])


class PlaylistSongDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, song_id):
        playlist = get_playlist(request, pk, owner_only=True)
        with transaction.atomic():
            deleted, _ = PlaylistItem.objects.filter(playlist=playlist, song_id=song_id).delete()
            if deleted:
                renumber(playlist, list(playlist.items.order_by("position", "id").values_list("song_id", flat=True)))
                playlist.save(update_fields=["updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        playlist = get_playlist(request, pk, owner_only=True)
        form = ReorderSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        new_order = form.validated_data["song_ids"]
        with transaction.atomic():
            current = list(playlist.items.order_by("position", "id").values_list("song_id", flat=True))
            # The owner sees only songs visible to them; any hidden ones keep their order at the end.
            visible_ids = set(
                Song.objects.visible_to(request.user).filter(id__in=current).values_list("id", flat=True)
            )
            visible_current = [i for i in current if i in visible_ids]
            if len(new_order) != len(set(new_order)) or sorted(new_order) != sorted(visible_current):
                raise ValidationError({"song_ids": ["Must list exactly the songs in this playlist, each once."]})
            renumber(playlist, new_order + [i for i in current if i not in visible_ids])
            playlist.save(update_fields=["updated_at"])
        return playlist_detail(request, playlist)
