"""Site-wide behaviour that has no app of its own: the single-page app routes, the JSON 404
for unknown API paths, and the settings guard that refuses to start without a secret key."""
import os
import subprocess
import sys

from django.conf import settings
from rest_framework.test import APIClient

from .base import LOGIN_URL, PASSWORD, AuthTestCase, make_user

SPA_PAGES = [
    "/", "/search", "/genre/Lo-fi", "/album/3", "/artist/1", "/playlist/2", "/liked", "/recent",
    "/uploads", "/upload", "/login", "/signup",
]


class SpaRouteTests(AuthTestCase):
    """The template frontend/templates/frontend/index.html must exist for these to pass."""

    def test_every_app_route_is_200_html(self):
        for path in SPA_PAGES:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])

    def test_root_page_names_the_app(self):
        self.assertContains(self.client.get("/"), "Songing")

    def test_every_app_route_sets_the_csrf_cookie(self):
        for path in ("/", "/album/3", "/liked"):
            with self.subTest(path=path):
                client = APIClient()
                client.get(path)
                self.assertTrue(client.cookies["csrftoken"].value)

    def test_csrf_cookie_from_the_page_works_as_the_x_csrftoken_header(self):
        make_user("alice")
        client = APIClient(enforce_csrf_checks=True)
        client.get("/")
        token = client.cookies["csrftoken"].value
        body = {"username": "alice", "password": PASSWORD}
        self.assertEqual(client.post(LOGIN_URL, body, format="json").status_code, 403)
        self.assertEqual(client.post(LOGIN_URL, body, format="json", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_page_is_served_the_same_to_logged_in_users(self):
        self.client.force_login(make_user("alice"))
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_unknown_page_is_a_404_with_html(self):
        response = self.client.get("/no/such/page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response["Content-Type"])

    def test_unknown_page_serves_the_app_so_it_can_draw_its_own_404(self):
        self.assertContains(self.client.get("/no/such/page"), "Songing", status_code=404)

    def test_unknown_page_also_sets_the_csrf_cookie(self):
        client = APIClient()
        client.get("/no/such/page")
        self.assertTrue(client.cookies["csrftoken"].value)

    def test_album_page_with_a_non_numeric_id_is_a_404_page(self):
        self.assertEqual(self.client.get("/album/abc").status_code, 404)


class UnknownApiPathTests(AuthTestCase):
    def test_unknown_api_path_is_404_json(self):
        response = self.client.get("/api/no-such/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response["Content-Type"])
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_deeper_unknown_api_path_is_404_json(self):
        response = self.client.get("/api/songs/1/no-such/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_unknown_auth_path_is_404_json(self):
        response = self.client.get("/api/auth/no-such/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Not found."})

    def test_unknown_api_path_is_not_the_app_page(self):
        self.assertNotIn("text/html", self.client.get("/api/no-such/")["Content-Type"])


class SettingsGuardTests(AuthTestCase):
    """manage.py check imports the settings; they must refuse to run without a secret key
    unless DEBUG is on."""

    def run_check(self, **env):
        # DJANGO_SECRET_KEY is set explicitly, even to "": the .env loader only fills in unset keys
        environment = {**os.environ, **env}
        return subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True, timeout=120,
        )

    def test_debug_off_and_no_secret_key_refuses_to_start(self):
        result = self.run_check(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Refusing to start", result.stderr)

    def test_debug_off_with_a_secret_key_starts(self):
        result = self.run_check(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="a-long-random-test-key-" + "x" * 40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_debug_on_with_no_secret_key_starts_with_the_dev_key(self):
        result = self.run_check(DJANGO_DEBUG="1", DJANGO_SECRET_KEY="")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_debug_is_off_when_the_variable_is_missing_or_unclear(self):
        for value in ("", "maybe", "off", "false"):
            with self.subTest(DJANGO_DEBUG=value):
                result = self.run_check(DJANGO_DEBUG=value, DJANGO_SECRET_KEY="")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Refusing to start", result.stderr)
