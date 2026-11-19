from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path


def api_not_found(request):
    return JsonResponse({"detail": "Not found."}, status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("music.urls")),
    # Unknown API paths answer in JSON like the rest of the API. Only paths ending in "/" so a
    # missing slash still gets Django's APPEND_SLASH redirect.
    re_path(r"^api/.*/$", api_not_found),
]
# Covers in development. static() returns [] when DEBUG is off; production serving comes with deploy.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += [path("", include("frontend.urls"))]
