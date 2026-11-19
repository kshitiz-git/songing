"""Load the Creative Commons demo music listed in seed/tracks.json.

Safe to run more than once: a track already in the database (same title + artist, no
uploader) is updated in place, never duplicated, and its audio is not stored twice.
Audio files missing from seed/audio/ are downloaded from each track's `url` first.
"""
import json
import os
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from music.catalog import existing_or_new_album, existing_or_new_artist
from music.models import Song
from music.uploads import check_audio

SEED_DIR = Path(settings.BASE_DIR) / "seed"
REQUIRED_KEYS = {"title", "artist", "album", "genre", "file", "url", "license", "attribution", "source_url"}
MAX_DOWNLOAD_BYTES = 30 * 1024 * 1024


def download(url, dest):
    if not url.startswith(("https://", "http://")):
        raise CommandError(f"Refusing to download a non-http URL: {url}")
    part = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Songing-seed/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response, open(part, "wb") as out:
        total = 0
        while chunk := response.read(64 * 1024):
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                out.close()
                part.unlink(missing_ok=True)
                raise CommandError(f"{url} is larger than {MAX_DOWNLOAD_BYTES // 2**20} MB")
            out.write(chunk)
    os.replace(part, dest)


class Command(BaseCommand):
    help = "Load the demo music in seed/tracks.json (downloads missing audio). Safe to run twice."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-download", action="store_true", help="Skip tracks whose audio is not in seed/audio/."
        )

    def handle(self, *args, **options):
        tracks_file = SEED_DIR / "tracks.json"
        if not tracks_file.is_file():
            raise CommandError(f"{tracks_file} not found")
        tracks = json.loads(tracks_file.read_text(encoding="utf-8"))
        audio_dir = SEED_DIR / "audio"
        audio_dir.mkdir(exist_ok=True)

        counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        for n, track in enumerate(tracks, 1):
            missing = REQUIRED_KEYS - track.keys()
            if missing:
                raise CommandError(f"Track {n} is missing keys: {sorted(missing)}")
            name = track["file"]
            if Path(name).name != name or name.startswith("."):
                raise CommandError(f"Track {n}: 'file' must be a plain file name, got {name!r}")
            path = audio_dir / name
            label = f"{track['artist']} - {track['title']}"

            if not path.is_file():
                if options["no_download"]:
                    self.stdout.write(self.style.WARNING(f"skip (no audio): {label}"))
                    counts["skipped"] += 1
                    continue
                self.stdout.write(f"downloading {label} ...")
                download(track["url"], path)

            result = self.load_track(track, path)
            counts[result] += 1
            self.stdout.write(f"{result}: {label}")

        self.stdout.write(self.style.SUCCESS(", ".join(f"{k} {v}" for k, v in counts.items())))

    @transaction.atomic
    def load_track(self, track, path):
        artist = existing_or_new_artist(track["artist"].strip())
        album = None
        if track["album"].strip():
            album = existing_or_new_album(track["album"].strip(), artist)
            if album.year is None and track.get("year"):
                album.year = track["year"]
                album.save(update_fields=["year"])

        fields = {
            "album": album,
            "track_number": track.get("track_number"),
            "genre": track["genre"].strip(),
            "license": track["license"].strip(),
            "attribution": track["attribution"].strip(),
            "source_url": track["source_url"].strip(),
            "is_public": True,
        }
        song = Song.objects.filter(
            title__iexact=track["title"].strip(), artist=artist, uploaded_by__isnull=True
        ).first()
        if song is not None:
            changed = [k for k, v in fields.items() if getattr(song, k) != v]
            if not changed:
                return "unchanged"
            for key in changed:
                setattr(song, key, fields[key])
            song.save(update_fields=changed)
            return "updated"

        with path.open("rb") as fh:
            audio = File(fh, name=path.name)
            try:
                ext, duration = check_audio(audio)
            except ValidationError as exc:
                raise CommandError(f"{path.name}: {' '.join(exc.messages)}")
            song = Song(title=track["title"].strip(), artist=artist, duration=duration, **fields)
            song.audio.save(f"seed{ext}", audio, save=False)
            song.save()
        return "created"
