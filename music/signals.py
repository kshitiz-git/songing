"""Delete stored files when their database row goes away.

post_delete also fires for rows removed by a cascade (e.g. a user deleting their account
removes their uploads), which a Song.delete() override would miss. Files are removed only
after the transaction commits, so a rolled-back delete keeps its files.
"""
from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Album, Artist, Song


def _delete_files_on_commit(*field_files):
    for field_file in field_files:
        if field_file and field_file.name:
            storage, name = field_file.storage, field_file.name
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))


@receiver(post_delete, sender=Song)
def delete_song_files(sender, instance, **kwargs):
    _delete_files_on_commit(instance.audio, instance.cover)


@receiver(post_delete, sender=Album)
def delete_album_cover(sender, instance, **kwargs):
    _delete_files_on_commit(instance.cover)


@receiver(post_delete, sender=Artist)
def delete_artist_image(sender, instance, **kwargs):
    _delete_files_on_commit(instance.image)
