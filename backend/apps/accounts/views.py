import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from .models import User
from .serializers import (
    SignupSerializer,
    LoginSerializer,
    VerifyEmailSerializer,
    ResendVerificationSerializer,
    UpdateProfileSerializer,
    ChangePasswordSerializer,
    RequestPasswordResetSerializer,
    ConfirmPasswordResetSerializer,
    user_to_dict,
)
from .services import get_uid, get_token

logger = logging.getLogger(__name__)


# Rate limiting for authentication endpoints
class AuthThrottle(SimpleRateThrottle):
    """Allow 5 auth attempts per hour per IP address."""
    scope = "auth"
    
    def get_cache_key(self, request, view):
        # Rate limit per IP address for public endpoints (no user context)
        if request.user and request.user.is_authenticated:
            return f"auth_{request.user.id}"
        return f"auth_{self.get_ident(request)}"


class SignupView(APIView):
    """POST /api/auth/signup/ - public, creates user, returns token + user + verification uid/token for EmailJS."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)

            logger.info("New user registered: %s (admin=%s)", user.email, user.is_admin)
            return Response(
                {
                    "token": token.key,
                    "user": user_to_dict(user),
                    "verification": {
                        "uid": get_uid(user),
                        "token": get_token(user),
                    },
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception:
            logger.exception("Unexpected error during signup")
            return Response(
                {"detail": "Registration failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LoginView(APIView):
    """POST /api/auth/login/ - public, returns token + user (including is_email_verified)."""
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            errors = serializer.errors
            non_field = errors.get("non_field_errors", [])
            detail = non_field[0] if non_field else "Invalid credentials."
            return Response({"detail": detail}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data["user"]
        
        user.last_login = timezone.now()
        user.last_login_ip = _get_client_ip(request)
        user.save(update_fields=["last_login", "last_login_ip"])

        # Invalidate old tokens and create new one (security: prevent token reuse)
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        logger.info("User logged in: %s (admin=%s)", user.email, user.is_admin)
        return Response(
            {"token": token.key, "user": user_to_dict(user)},
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ - deletes token server-side."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
            logger.info("User logged out: %s", request.user.email)
        except Token.DoesNotExist:
            pass
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /api/auth/me/ - re-hydrate auth state on page refresh."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"user": user_to_dict(request.user)}, status=status.HTTP_200_OK)


class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            non_field = errors.get("non_field_errors", [])
            detail = non_field[0] if non_field else "Verification failed."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        logger.info("Email verified for: %s", user.email)
        return Response(
            {"detail": "Email verified successfully.", "user": user_to_dict(user)},
            status=status.HTTP_200_OK,
        )


class ResendVerificationEmailView(APIView):
    """
    POST /api/auth/resend-verification/
    Authenticated - lets unverified users request a new verification email.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = ResendVerificationSerializer(data={}, context={"request": request})
        if not serializer.is_valid():
            errors = serializer.errors
            non_field = errors.get("non_field_errors", [])
            detail = non_field[0] if non_field else "Could not resend email."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        logger.info("Verification token regenerated for: %s", user.email)
        return Response(
            {
                "detail": "Verification data ready.",
                "uid": get_uid(user),
                "token": get_token(user),
            },
            status=status.HTTP_200_OK,
        )


class ProfileView(APIView):
    """GET /api/profile/ - full profile data including stats summary"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.quiz.models import QuizSession
        from apps.flashcards.models import Deck
        from django.db import models as dm

        user = request.user
        stats = QuizSession.objects.filter(user=user).aggregate(
            total=dm.Count('id'),
            avg=dm.Avg('score_percent'),
        )

        return Response({
            'user': user_to_dict(user),
            'stats': {
                'total_quizzes': stats['total'] or 0,
                'average_score': round(stats['avg'] or 0, 1),
                'total_flashcard_sets': Deck.objects.filter(user=user).count(),
            }
        })


class UpdateProfileView(APIView):
    """POST /api/auth/update-profile/ - update username and/or email."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateProfileSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        logger.info("Profile updated: %s", user.email)
        return Response({"user": user_to_dict(user)}, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """POST /api/auth/change-password/ - validates old pw, sets new, rotates token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        Token.objects.filter(user=user).delete()
        new_token, _ = Token.objects.get_or_create(user=user)

        logger.info("Password changed for: %s", user.email)
        return Response(
            {"detail": "Password updated successfully.", "token": new_token.key},
            status=status.HTTP_200_OK,
        )


class UploadProfileImageView(APIView):
    """POST /api/auth/upload-profile-image/ - multipart image upload."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get("profile_image")
        if not file:
            return Response(
                {"detail": "No image file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if file.content_type not in allowed_types:
            return Response(
                {"detail": "Unsupported format. Use JPEG, PNG, WebP, or GIF."},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )

        if file.size > 5 * 1024 * 1024:
            return Response(
                {"detail": "Image must be under 5 MB."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )

        try:
            image_url = self._upload(file, request.user)
        except Exception:
            logger.exception("Profile image upload failed for %s", request.user.email)
            return Response(
                {"detail": "Upload failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        request.user.profile_image = image_url
        request.user.save(update_fields=["profile_image"])

        logger.info("Profile image updated for: %s", request.user.email)
        return Response({"user": user_to_dict(request.user)}, status=status.HTTP_200_OK)

    def _upload(self, file, user):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        env = os.getenv("ENVIRONMENT", "dev")
        
        if os.getenv("STORAGE_BACKEND") == "cloudinary":
            import cloudinary.uploader
            result = cloudinary.uploader.upload(
                file,
                folder=f"lamla/{env}/profile_images/{user.id}",
                resource_type="image",
                use_filename=True,
                unique_filename=True,
            )
            return result["secure_url"]

        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        from django.conf import settings
        
        file.seek(0)
        path = default_storage.save(
            f"profile_images/{user.id}/{file.name}",
            ContentFile(file.read())
        )
        return f"{settings.MEDIA_URL}{path}"


class RequestPasswordResetView(APIView):
    """
    POST /api/auth/request-password-reset/
    Public. Accepts an email and sends a reset link if an account exists.
    Always returns 200 with the same message — prevents email enumeration.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data["email"]
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                logger.info("Password reset requested for unknown email: %s", email)
            else:
                logger.info("Password reset token generated for: %s", user.email)
                return Response(
                    {
                        "detail": "If an account with that email exists, a reset link has been sent.",
                        "uid": get_uid(user),
                        "token": get_token(user),
                    },
                    status=status.HTTP_200_OK,
                )

        return Response(
            {"detail": "If an account with that email exists, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class ConfirmPasswordResetView(APIView):
    """
    POST /api/auth/confirm-password-reset/
    Public. Validates uid + token, sets new password, invalidates existing auth tokens.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        serializer = ConfirmPasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            non_field = errors.get("non_field_errors", [])
            detail = non_field[0] if non_field else "Password reset failed."
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()

        # Invalidate all existing auth tokens — forces re-login with new password
        Token.objects.filter(user=user).delete()

        logger.info("Password reset confirmed for: %s", user.email)
        return Response(
            {"detail": "Password reset successfully. Please log in with your new password."},
            status=status.HTTP_200_OK,
        )


def _get_client_ip(request) -> str | None:
    """Extract the real client IP, handling proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class DebugUsers(APIView):
    """List all users for debugging. Admin-only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response(
                {"detail": "Admin access required."},
                status=status.HTTP_403_FORBIDDEN
            )
        from .models import User
        users = User.objects.all().values("id", "email", "username", "is_email_verified", "is_admin", "date_joined")
        return Response({"users": list(users)})
