"""Find-or-create helpers shared by uploads and the demo seeder (case-insensitive names)."""
from django.db import IntegrityError, transaction

from .models import Album, Artist


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
