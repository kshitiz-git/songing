"""Signup, login, logout and /api/auth/me/."""
from rest_framework.test import APIClient

from .base import LOGIN_URL, LOGOUT_URL, ME_URL, PASSWORD, SIGNUP_URL, AuthTestCase, User, make_user


class MeTests(AuthTestCase):
    def test_logged_out_user_is_null(self):
        response = self.client.get(ME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user": None})

    def test_logged_in_user_has_id_username_and_email(self):
        user = make_user("alice", email="a@b.c")
        self.client.force_login(user)
        self.assertEqual(self.client.get(ME_URL).json(), {"user": {"id": user.id, "username": "alice", "email": "a@b.c"}})


class SignupTests(AuthTestCase):
    def test_signup_returns_201_with_the_new_user(self):
        response = self.signup(username="kshitiz", email="k@example.com")
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(username="kshitiz")
        self.assertEqual(response.json(), {"user": {"id": user.id, "username": "kshitiz", "email": "k@example.com"}})

    def test_signup_logs_the_user_in(self):
        self.signup(username="kshitiz")
        self.assertEqual(self.me()["username"], "kshitiz")

    def test_response_never_contains_the_password(self):
        self.assertNotIn(PASSWORD, self.signup().content.decode())

    def test_password_is_stored_hashed(self):
        self.signup(username="kshitiz")
        user = User.objects.get(username="kshitiz")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_email_is_optional(self):
        response = self.signup(username="kshitiz")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "")

    def test_taken_username_is_400_with_a_username_error(self):
        make_user("alice")
        response = self.signup(username="alice")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_taken_username_is_checked_ignoring_case(self):
        make_user("Alice")
        for attempt in ("alice", "ALICE", "aLiCe"):
            with self.subTest(username=attempt):
                response = self.signup(username=attempt)
                self.assertEqual(response.status_code, 400)
                self.assertIn("username", response.json())
        self.assertEqual(User.objects.count(), 1)

    def test_taken_username_does_not_log_in_or_change_the_existing_user(self):
        existing = make_user("alice")
        self.signup(username="alice", password="another-fine-password-9")
        self.assertIsNone(self.me())
        existing.refresh_from_db()
        self.assertTrue(existing.check_password(PASSWORD))

    def test_weak_password_is_400_with_a_password_error(self):
        weak = {"too short": "abc1", "too common": "password", "all digits": "48151623420"}
        for why, password in weak.items():
            with self.subTest(why):
                response = self.signup(username="kshitiz", password=password)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.json())

    def test_password_too_close_to_the_username_is_400(self):
        response = self.signup(username="kshitiz", password="kshitiz123")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_rejected_signup_creates_no_user_and_does_not_log_in(self):
        self.signup(username="kshitiz", password="password")
        self.assertFalse(User.objects.exists())
        self.assertIsNone(self.me())

    def test_missing_username_or_password_is_400(self):
        for field in ("username", "password"):
            with self.subTest(missing=field):
                body = {"username": "kshitiz", "password": PASSWORD}
                del body[field]
                response = self.client.post(SIGNUP_URL, body, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_username_with_a_space_or_symbol_is_400(self):
        for username in ("two words", "bad!name", "a/b"):
            with self.subTest(username=username):
                self.assertEqual(self.signup(username=username).status_code, 400)

    def test_username_over_150_characters_is_400(self):
        self.assertEqual(self.signup(username="u" * 151).status_code, 400)

    def test_malformed_email_is_400(self):
        response = self.signup(username="kshitiz", email="not-an-email")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_signup_cannot_make_an_admin(self):
        self.signup(username="kshitiz", is_staff=True, is_superuser=True)
        user = User.objects.get(username="kshitiz")
        self.assertFalse(user.is_staff or user.is_superuser)


class LoginTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.alice = make_user("alice", email="a@b.c")

    def test_login_returns_200_with_the_user(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user": {"id": self.alice.id, "username": "alice", "email": "a@b.c"}})

    def test_login_makes_me_return_the_user(self):
        self.assertIsNone(self.me())
        self.login()
        self.assertEqual(self.me()["username"], "alice")

    def test_wrong_password_is_400_with_the_documented_message(self):
        response = self.login(password="not-the-password")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Wrong username or password."})

    def test_wrong_password_does_not_log_in(self):
        self.login(password="not-the-password")
        self.assertIsNone(self.me())

    def test_unknown_user_gets_the_same_answer_as_a_wrong_password(self):
        wrong_password = self.login(password="not-the-password")
        unknown_user = self.login(username="nobody")
        self.assertEqual((unknown_user.status_code, unknown_user.json()), (wrong_password.status_code, wrong_password.json()))

    def test_inactive_user_cannot_log_in(self):
        self.alice.is_active = False
        self.alice.save()
        response = self.login()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Wrong username or password."})

    def test_missing_fields_are_400(self):
        for body in ({}, {"username": "alice"}, {"password": PASSWORD}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(LOGIN_URL, body, format="json").status_code, 400)

    def test_logging_in_as_someone_else_switches_the_session(self):
        make_user("bob")
        self.login()
        self.login(username="bob")
        self.assertEqual(self.me()["username"], "bob")


class LogoutTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        make_user("alice")
        self.login()

    def test_logout_returns_204(self):
        self.assertEqual(self.client.post(LOGOUT_URL).status_code, 204)

    def test_me_is_null_after_logout(self):
        self.assertIsNotNone(self.me())
        self.client.post(LOGOUT_URL)
        self.assertIsNone(self.me())

    def test_logged_in_only_endpoints_are_403_after_logout(self):
        self.assertEqual(self.client.get("/api/library/liked/").status_code, 200)
        self.client.post(LOGOUT_URL)
        self.assertEqual(self.client.get("/api/library/liked/").status_code, 403)

    def test_logging_out_twice_is_fine(self):
        self.client.post(LOGOUT_URL)
        self.assertEqual(self.client.post(LOGOUT_URL).status_code, 204)

    def test_logging_out_when_never_logged_in_is_fine(self):
        fresh = APIClient()
        self.assertEqual(fresh.post(LOGOUT_URL).status_code, 204)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(LOGOUT_URL).status_code, 405)
        self.assertIsNotNone(self.me())
