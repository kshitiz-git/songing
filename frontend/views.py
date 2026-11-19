from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def index(request, **kwargs):
    """The single-page app. Sets the csrftoken cookie the JS sends back as X-CSRFToken."""
    return render(request, "frontend/index.html")


@ensure_csrf_cookie
def not_found(request, **kwargs):
    """Unknown paths get the app too (it draws its 404 page), with a real 404 status."""
    return render(request, "frontend/index.html", status=404)
