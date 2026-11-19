from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """DRF's handler, but every 404 says {"detail": "Not found."} as docs/api.md promises.

    DRF passes Django's message through ("No Song matches the given query."), which also
    tells a caller which model a hidden id belongs to.
    """
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    return exception_handler(exc, context)
