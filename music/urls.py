from django.urls import path

from . import views
from .stream import stream_song

urlpatterns = [
    path("home/", views.HomeView.as_view(), name="home"),
    path("songs/", views.SongListCreateView.as_view(), name="song-list"),
    path("songs/<int:pk>/", views.SongDetailView.as_view(), name="song-detail"),
    path("songs/<int:pk>/stream/", stream_song, name="song-stream"),
    path("songs/<int:pk>/play/", views.SongPlayView.as_view(), name="song-play"),
    path("songs/<int:pk>/like/", views.SongLikeView.as_view(), name="song-like"),
    path("albums/", views.AlbumListView.as_view(), name="album-list"),
    path("albums/<int:pk>/", views.AlbumDetailView.as_view(), name="album-detail"),
    path("artists/", views.ArtistListView.as_view(), name="artist-list"),
    path("artists/<int:pk>/", views.ArtistDetailView.as_view(), name="artist-detail"),
    path("genres/", views.GenreListView.as_view(), name="genre-list"),
    path("search/", views.SearchView.as_view(), name="search"),
    path("library/liked/", views.LikedSongsView.as_view(), name="library-liked"),
    path("library/recent/", views.RecentSongsView.as_view(), name="library-recent"),
    path("library/uploads/", views.UploadedSongsView.as_view(), name="library-uploads"),
    path("playlists/", views.PlaylistListCreateView.as_view(), name="playlist-list"),
    path("playlists/<int:pk>/", views.PlaylistDetailView.as_view(), name="playlist-detail"),
    path("playlists/<int:pk>/songs/", views.PlaylistSongsView.as_view(), name="playlist-songs"),
    path(
        "playlists/<int:pk>/songs/<int:song_id>/",
        views.PlaylistSongDeleteView.as_view(),
        name="playlist-song-delete",
    ),
    path("playlists/<int:pk>/reorder/", views.PlaylistReorderView.as_view(), name="playlist-reorder"),
]
