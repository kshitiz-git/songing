"""Shared setup for the accounts tests: cleared throttle counters and a fast password hasher."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

User = get_user_model()
PASSWORD = "correct-horse-battery-7"

SIGNUP_URL = "/api/auth/signup/"
LOGIN_URL = "/api/auth/login/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"


def make_user(username="alice", password=PASSWORD, **fields):
    return User.objects.create_user(username, password=password, **fields)


class AuthTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the default cache
        override = override_settings(
            # the real hasher takes about half a second per user
            PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
        override.enable()
        self.addCleanup(override.disable)

    def signup(self, client=None, **fields):
        body = {"username": "newuser", "password": PASSWORD, **fields}
        return (client or self.client).post(SIGNUP_URL, body, format="json")

    def login(self, client=None, username="alice", password=PASSWORD):
        return (client or self.client).post(LOGIN_URL, {"username": username, "password": password}, format="json")

    def me(self, client=None):
        return (client or self.client).get(ME_URL).json()["user"]
