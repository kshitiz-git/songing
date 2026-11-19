"""CSRF protection and the rate limit on the auth endpoints."""
from django.conf import settings
from rest_framework.test import APIClient

from music.models import Playlist

from .base import LOGIN_URL, LOGOUT_URL, ME_URL, PASSWORD, SIGNUP_URL, AuthTestCase, User, make_user

# Any 32-character secret is a valid CSRF cookie value, and the same string is a valid header token.
# Using one here keeps these tests independent of the page template that normally sets the cookie.
CSRF_SECRET = "a" * 32


def csrf_client():
    """A client like a browser: it checks CSRF tokens, which APIClient skips by default."""
    return APIClient(enforce_csrf_checks=True)


def with_csrf_cookie(client):
    client.cookies["csrftoken"] = CSRF_SECRET
    return {"HTTP_X_CSRFTOKEN": CSRF_SECRET}


class CsrfTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user("alice")
        self.credentials = {"username": "alice", "password": PASSWORD}

    def test_login_without_a_token_is_403(self):
        client = csrf_client()
        response = client.post(LOGIN_URL, self.credentials, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("detail", response.json())

    def test_login_without_a_token_does_not_log_in(self):
        client = csrf_client()
        client.post(LOGIN_URL, self.credentials, format="json")
        self.assertIsNone(self.me(client))

    def test_signup_without_a_token_is_403_and_creates_no_user(self):
        client = csrf_client()
        response = client.post(SIGNUP_URL, {"username": "newuser", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_login_with_a_cookie_but_no_header_is_403(self):
        client = csrf_client()
        with_csrf_cookie(client)
        self.assertEqual(client.post(LOGIN_URL, self.credentials, format="json").status_code, 403)

    def test_login_with_a_header_that_does_not_match_the_cookie_is_403(self):
        client = csrf_client()
        with_csrf_cookie(client)
        response = client.post(LOGIN_URL, self.credentials, format="json", HTTP_X_CSRFTOKEN="b" * 32)
        self.assertEqual(response.status_code, 403)

    def test_login_with_a_matching_cookie_and_header_works(self):
        client = csrf_client()
        headers = with_csrf_cookie(client)
        response = client.post(LOGIN_URL, self.credentials, format="json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.me(client)["username"], "alice")

    def test_signup_with_a_matching_cookie_and_header_works(self):
        client = csrf_client()
        headers = with_csrf_cookie(client)
        body = {"username": "newuser", "password": PASSWORD}
        self.assertEqual(client.post(SIGNUP_URL, body, format="json", **headers).status_code, 201)

    def test_logout_of_a_logged_in_user_needs_a_token(self):
        client = csrf_client()
        client.force_login(self.alice)
        self.assertEqual(client.post(LOGOUT_URL).status_code, 403)
        self.assertIsNotNone(self.me(client))

    def test_logout_with_a_token_works(self):
        client = csrf_client()
        client.force_login(self.alice)
        headers = with_csrf_cookie(client)
        self.assertEqual(client.post(LOGOUT_URL, **headers).status_code, 204)
        self.assertIsNone(self.me(client))

    def test_logged_in_writes_to_the_music_api_need_a_token(self):
        client = csrf_client()
        client.force_login(self.alice)
        response = client.post("/api/playlists/", {"name": "No token"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Playlist.objects.exists())

    def test_logged_in_writes_to_the_music_api_work_with_a_token(self):
        client = csrf_client()
        client.force_login(self.alice)
        headers = with_csrf_cookie(client)
        response = client.post("/api/playlists/", {"name": "With token"}, format="json", **headers)
        self.assertEqual(response.status_code, 201)

    def test_reads_need_no_token(self):
        client = csrf_client()
        client.force_login(self.alice)
        self.assertEqual(client.get(ME_URL).status_code, 200)
        self.assertEqual(client.get("/api/playlists/").status_code, 200)


class ThrottleTests(AuthTestCase):
    """Every request here comes from a new APIClient (no cookies), like a script that does not
    keep its session. The limit is per client address, read from settings, never hard-coded."""

    def setUp(self):
        super().setUp()
        make_user("alice")
        self.limit = int(settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["auth"].split("/")[0])

    def fail_login(self, **extra):
        return APIClient().post(LOGIN_URL, {"username": "alice", "password": "wrong"}, format="json", **extra)

    def new_signup(self, number):
        return APIClient().post(SIGNUP_URL, {"username": f"user{number}", "password": PASSWORD}, format="json")

    def use_up_the_limit(self):
        for _ in range(self.limit):
            self.assertEqual(self.fail_login().status_code, 400)

    def test_requests_up_to_the_limit_still_get_the_normal_answer(self):
        statuses = {self.fail_login().status_code for _ in range(self.limit)}
        self.assertEqual(statuses, {400})

    def test_login_is_429_after_the_limit(self):
        self.use_up_the_limit()
        response = self.fail_login()
        self.assertEqual(response.status_code, 429)
        self.assertIn("detail", response.json())

    def test_429_response_has_a_retry_after_header(self):
        self.use_up_the_limit()
        self.assertIn("Retry-After", self.fail_login())

    def test_right_password_is_also_blocked_once_the_limit_is_hit(self):
        self.use_up_the_limit()
        client = APIClient()
        self.assertEqual(self.login(client).status_code, 429)
        self.assertIsNone(self.me(client))

    def test_signup_is_429_after_the_limit(self):
        for number in range(self.limit):
            self.assertEqual(self.new_signup(number).status_code, 201)
        response = self.new_signup(self.limit)
        self.assertEqual(response.status_code, 429)
        self.assertIn("detail", response.json())

    def test_429_signup_creates_no_user(self):
        for number in range(self.limit + 1):
            self.new_signup(number)
        self.assertFalse(User.objects.filter(username=f"user{self.limit}").exists())

    def test_login_and_signup_share_one_budget(self):
        half = self.limit // 2
        for number in range(half):
            self.new_signup(number)
        for _ in range(self.limit - half):
            self.fail_login()
        self.assertEqual(self.fail_login().status_code, 429)

    def test_limit_is_per_client_address(self):
        self.use_up_the_limit()
        self.assertEqual(self.fail_login(REMOTE_ADDR="10.0.0.9").status_code, 400)

    def test_a_spoofed_forwarded_for_header_does_not_reset_the_limit(self):
        self.use_up_the_limit()
        for number in range(3):
            response = self.fail_login(HTTP_X_FORWARDED_FOR=f"203.0.113.{number}")
            self.assertEqual(response.status_code, 429)

    def test_me_and_logout_are_not_throttled(self):
        self.use_up_the_limit()
        client = APIClient()
        self.assertEqual(client.get(ME_URL).status_code, 200)
        self.assertEqual(client.post(LOGOUT_URL).status_code, 204)

    def test_signup_stays_limited_for_a_client_that_keeps_its_session(self):
        """A browser or script keeps its cookie jar, so after the first signup it is logged in.
        DRF's ScopedRateThrottle then keys it on the user id (rest_framework/throttling.py:242),
        and every new account gives a fresh key, so this client is never limited."""
        client = APIClient()
        statuses = [self.signup(client, username=f"user{number}").status_code for number in range(self.limit + 3)]
        self.assertEqual(statuses[self.limit:], [429, 429, 429], statuses)
