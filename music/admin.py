from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Album, Artist, Like, PlayEvent, Playlist, PlaylistItem, Song
from .uploads import check_audio, process_cover


class SongAdminForm(forms.ModelForm):
    """Admin uploads go through the same audio / cover checks as the API."""

    class Meta:
        model = Song
        fields = "__all__"
        exclude = ["duration"]

    def clean_audio(self):
        audio = self.cleaned_data.get("audio")
        if audio and hasattr(audio, "content_type"):  # a newly uploaded file
            ext, self._duration = check_audio(audio)
            audio.name = f"upload{ext}"
        return audio

    def clean_cover(self):
        cover = self.cleaned_data.get("cover")
        if cover and hasattr(cover, "content_type"):
            return process_cover(cover)
        return cover

    def save(self, commit=True):
        song = super().save(commit=False)
        if getattr(self, "_duration", None):
            song.duration = self._duration
        if commit:
            song.save()
            self.save_m2m()
        return song


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name"]


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "year", "created_at"]
    search_fields = ["title", "artist__name"]
    autocomplete_fields = ["artist"]


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    form = SongAdminForm
    list_display = ["title", "artist", "album", "genre", "duration", "is_public", "uploaded_by", "play_count", "license"]
    list_filter = ["is_public", "genre", "license"]
    search_fields = ["title", "artist__name", "album__title"]
    autocomplete_fields = ["artist", "album", "uploaded_by"]
    readonly_fields = ["duration", "play_count", "created_at"]


class PlaylistItemInline(admin.TabularInline):
    model = PlaylistItem
    extra = 0
    autocomplete_fields = ["song"]
    ordering = ["position"]


@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_public", "updated_at"]
    list_filter = ["is_public"]
    search_fields = ["name", "owner__username"]
    autocomplete_fields = ["owner"]
    inlines = [PlaylistItemInline]


@admin.register(PlaylistItem)
class PlaylistItemAdmin(admin.ModelAdmin):
    list_display = ["playlist", "position", "song", "added_at"]
    autocomplete_fields = ["playlist", "song"]


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ["user", "song", "created_at"]
    autocomplete_fields = ["user", "song"]


@admin.register(PlayEvent)
class PlayEventAdmin(admin.ModelAdmin):
    list_display = ["song", "user", "played_at"]
    list_filter = ["played_at"]
    autocomplete_fields = ["user", "song"]
    date_hierarchy = "played_at"
