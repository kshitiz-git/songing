from django.urls import path, re_path

from . import views

# Keep in sync with the router in frontend/static/songing/js/ (docs/plan.md lists them).
SPA_ROUTES = [
    "",
    "search",
    "genre/<str:name>",
    "album/<int:pk>",
    "artist/<int:pk>",
    "playlist/<int:pk>",
    "liked",
    "recent",
    "uploads",
    "upload",
    "login",
    "signup",
]

urlpatterns = [path(route, views.index) for route in SPA_ROUTES] + [
    re_path(r"^(?!api/|static/|media/|admin/).*$", views.not_found),
]
