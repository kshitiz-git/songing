"""Checks for uploaded audio and cover files.

Audio: mutagen must parse the file as one of the allowed formats and find a real duration.
The client's file name and Content-Type are never trusted; the stored extension comes from
the detected format. Covers: Pillow must decode the image, and it is re-encoded to a fresh
JPEG, which drops metadata and anything hidden after the image data.
"""
import io

import mutagen
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis
from mutagen.wave import WAVE
from PIL import Image, UnidentifiedImageError

AUDIO_EXTENSIONS = {
    MP3: ".mp3",
    MP4: ".m4a",
    OggVorbis: ".ogg",
    OggOpus: ".ogg",
    WAVE: ".wav",
    FLAC: ".flac",
}

COVER_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
COVER_MAX_PIXELS = 40_000_000  # refuse decompression bombs before decoding
COVER_SIZE = (800, 800)


def _mb(n):
    return f"{n // (1024 * 1024)} MB"


def check_audio(upload):
    """Return (extension, duration_seconds) or raise ValidationError."""
    limit = settings.MAX_AUDIO_UPLOAD_BYTES
    if upload.size > limit:
        raise ValidationError(f"File is larger than {_mb(limit)}.")
    upload.seek(0)
    try:
        parsed = mutagen.File(upload.file)
    except Exception:  # mutagen raises many error types for broken files
        parsed = None
    finally:
        upload.seek(0)
    ext = AUDIO_EXTENSIONS.get(type(parsed))
    if parsed is None or ext is None:
        raise ValidationError("This is not a supported audio file (mp3, m4a, ogg, wav, flac).")
    duration = float(getattr(parsed.info, "length", 0) or 0)
    if duration <= 0:
        raise ValidationError("Could not read the length of this audio file.")
    return ext, round(duration, 2)


def process_cover(upload):
    """Return a ContentFile with a clean JPEG (max 800x800) or raise ValidationError."""
    limit = settings.MAX_COVER_UPLOAD_BYTES
    if upload.size > limit:
        raise ValidationError(f"Image is larger than {_mb(limit)}.")
    try:
        upload.seek(0)
        with Image.open(upload) as probe:
            if probe.format not in COVER_FORMATS:
                raise ValidationError("Cover must be a JPEG, PNG, WebP or GIF image.")
            if probe.width * probe.height > COVER_MAX_PIXELS:
                raise ValidationError("Image dimensions are too large.")
            probe.verify()
        upload.seek(0)
        with Image.open(upload) as img:
            img = img.convert("RGB")
            img.thumbnail(COVER_SIZE)
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=85, optimize=True)
    except ValidationError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise ValidationError("This is not a valid image file.")
    finally:
        upload.seek(0)
    return ContentFile(out.getvalue(), name="cover.jpg")
