"""Auth endpoints: signup, login (token pair), refresh, current user."""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import SignupSerializer, UserSerializer


class SignupView(APIView):
    """Create a new account; returns a JWT pair so the user lands logged-in."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """Email+password login returning access/refresh JWT pair."""


class MeView(APIView):
    """Current authenticated user profile."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)
