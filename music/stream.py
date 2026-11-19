"""Audio streaming with HTTP Range support (RFC 9110 section 14).

Browsers request `Range: bytes=<start>-` when the user seeks; answering 206 with the right
Content-Range is what makes the seek bar work. Only single ranges are supported; a multi-range
or malformed header gets the whole file (200), which the RFC allows.
"""
import mimetypes
import os
import re

from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_safe

from .models import Song

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK = 64 * 1024

mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/ogg", ".ogg")


def parse_range(header, size):
    """Return (start, end) inclusive, None for "send the whole file", or "invalid" for 416."""
    match = RANGE_RE.match(header.strip()) if header else None
    if not match:
        return None
    first, last = match.groups()
    if first == "" and last == "":
        return None
    if first == "":  # suffix range: the last N bytes
        length = int(last)
        if length == 0:
            return "invalid"
        return max(0, size - length), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        return "invalid"
    return start, end


def _read(path, start, length):
    with open(path, "rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@require_safe
def stream_song(request, pk):
    song = Song.objects.visible_to(request.user).filter(pk=pk).first()
    if song is None or not song.audio:
        return JsonResponse({"detail": "Not found."}, status=404)
    try:
        path = song.audio.path
        size = os.path.getsize(path)
    except (OSError, ValueError):
        return JsonResponse({"detail": "Not found."}, status=404)

    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    byte_range = parse_range(request.headers.get("Range", ""), size)
    if byte_range == "invalid":
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{size}"
        response["Accept-Ranges"] = "bytes"
        return response

    if byte_range is None:
        start, end, code = 0, size - 1, 200
    else:
        (start, end), code = byte_range, 206
    length = end - start + 1 if size else 0

    if request.method == "HEAD":
        response = HttpResponse(status=code, content_type=content_type)
    else:
        response = StreamingHttpResponse(_read(path, start, length), status=code, content_type=content_type)
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if code == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    # private: a shared cache must never keep someone's private upload
    response["Cache-Control"] = "private, max-age=3600"
    return response
