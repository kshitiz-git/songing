from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

User = get_user_model()


class CsrfAlwaysSessionAuthentication(SessionAuthentication):
    """Session auth that checks the CSRF token for logged-out requests too.

    DRF's SessionAuthentication checks CSRF only for logged-in users. Login and signup must
    check it as well, or another site could log a visitor into an account it controls
    (login CSRF).
    """

    def authenticate(self, request):
        self.enforce_csrf(request)
        return super().authenticate(request)


def user_data(user):
    return {"id": user.id, "username": user.username, "email": user.email}


class SignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
    password = serializers.CharField(max_length=128, write_only=True, trim_whitespace=False)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs.get("email", ""))
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ClientIPRateThrottle(ScopedRateThrottle):
    """The "auth" limit, always counted per client IP.

    DRF's ScopedRateThrottle counts a logged-in request against the user id. Signup logs the
    client in, so each new account would start a fresh count and signups would never be
    limited. Counting by IP closes that, and also stops a logged-in attacker from getting a
    separate login-guess budget per account.
    """

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class AuthThrottledView(APIView):
    authentication_classes = [CsrfAlwaysSessionAuthentication]
    throttle_classes = [ClientIPRateThrottle]
    throttle_scope = "auth"


class MeView(APIView):
    def get(self, request):
        user = request.user
        return Response({"user": user_data(user) if user.is_authenticated else None})


class SignupView(AuthThrottledView):
    def post(self, request):
        form = SignupSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        user = User.objects.create_user(
            username=data["username"], password=data["password"], email=data.get("email", "")
        )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"user": user_data(user)}, status=status.HTTP_201_CREATED)


class LoginView(AuthThrottledView):
    def post(self, request):
        form = LoginSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        user = authenticate(
            request, username=form.validated_data["username"], password=form.validated_data["password"]
        )
        if user is None:
            return Response({"detail": "Wrong username or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response({"user": user_data(user)})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
