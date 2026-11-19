from django.apps import AppConfig


class MusicConfig(AppConfig):
    name = 'music'

    def ready(self):
        from . import signals  # noqa: F401  (connects the file-cleanup receivers)
