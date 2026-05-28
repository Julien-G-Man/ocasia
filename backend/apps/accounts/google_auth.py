"""
Google OAuth authentication integration.
Handles Google sign-in and returns tokens compatible with existing auth system.
"""

import logging
import os
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import user_to_dict
from .views import AuthThrottle

logger = logging.getLogger(__name__)
User = get_user_model()


class GoogleAuthView(APIView):
    """
    POST /api/auth/google/ - Exchange Google ID token for app auth token.

    Frontend sends Google ID token (from Google Sign-In SDK),
    backend verifies it, creates/updates user, returns app auth token.
    """
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        google_token = request.data.get('token')
        if not google_token:
            return Response(
                {'detail': 'Google token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify Google token
            client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
            if not client_id:
                logger.error('GOOGLE_OAUTH_CLIENT_ID is not configured')
                print('GOOGLE_OAUTH_CLIENT_ID is not configured')
                return Response(
                    {'detail': 'Google OAuth is not configured on the server.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            idinfo = id_token.verify_oauth2_token(
                google_token,
                requests.Request(),
                client_id
            )

            # Extract user info from Google token
            email = idinfo.get('email')
            given_name = idinfo.get('given_name', '')
            family_name = idinfo.get('family_name', '')
            picture = idinfo.get('picture', '')
            google_sub = idinfo.get('sub')  # Google user ID

            if not email:
                return Response(
                    {'detail': 'Email not provided by Google.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email.lower(),
                defaults={
                    'username': email.split('@')[0], 
                    'is_email_verified': True, 
                    'profile_image': picture,
                }
            )

            # Update user info if already exists
            if not created:
                if picture and not user.profile_image:
                    user.profile_image = picture
                if not user.is_email_verified:
                    user.is_email_verified = True
                    user.email_verified_at = timezone.now()
                user.save(update_fields=['profile_image', 'is_email_verified', 'email_verified_at'])

            # Update login tracking
            user.last_login = timezone.now()
            user.last_login_ip = self._get_client_ip(request)
            user.save(update_fields=['last_login', 'last_login_ip'])

            # Create or get auth token
            Token.objects.filter(user=user).delete()  # Invalidate old tokens
            token = Token.objects.create(user=user) # create new token

            logger.info(
                "Google auth %s for user: %s",
                "signup" if created else "login",
                user.email,
            )
            print(
                "Google auth %s for user: %s" % (
                    "signup" if created else "login",
                    user.email,
                )
            )

            return Response(
                {
                    'token': token.key,
                    'user': user_to_dict(user),
                    'created': created
                },
                status=status.HTTP_200_OK
            )

        except ValueError as e:
            logger.warning("Invalid Google token: %s", str(e))
            print("Invalid Google token: %s" % str(e))
            return Response(
                {'detail': 'Invalid Google token.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.exception("Google auth failed: %s", str(e))
            print("Google auth failed: %s" % str(e))
            return Response(
                {'detail': 'Google authentication failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_client_ip(self, request):
        """Extract the real client IP, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
