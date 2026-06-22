import hashlib
import hmac
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

MAX_DONATION_GHS = 10_000

from . import paystack as paystack_client
from .helpers import generate_reference, mark_donation_paid, WEBHOOK_HANDLERS
from .models import Donation

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def initiate_donation(request):
    """
    POST /api/subscriptions/donate/initiate/

    Body:
        amount  — donation amount in GHS (minimum 5)
        email   — required for anonymous donors; ignored if authenticated

    Returns:
        { authorization_url, reference }
    """
    amount = request.data.get("amount")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return Response({"error": "amount must be a number."}, status=status.HTTP_400_BAD_REQUEST)

    if amount < 5:
        return Response({"error": "Minimum donation is 5 GHS."}, status=status.HTTP_400_BAD_REQUEST)

    if amount > MAX_DONATION_GHS:
        return Response({"error": f"Maximum donation is GHS {MAX_DONATION_GHS}."}, status=status.HTTP_400_BAD_REQUEST)

    if request.user and request.user.is_authenticated:
        email = request.user.email
        user  = request.user
    else:
        email = request.data.get("email", "").strip()
        if not email:
            return Response({"error": "email is required for anonymous donations."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except ValidationError:
            return Response({"error": "Invalid email address."}, status=status.HTTP_400_BAD_REQUEST)
        user = None

    reference    = generate_reference()
    callback_url = f"{settings.FRONTEND_URL}/donate/thank-you"
    metadata     = {"user_id": user.id if user else None, "type": "donation"}

    try:
        result = paystack_client.initialize_transaction(
            email=email,
            amount_ghs=amount,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Paystack initialize error: %s", exc)
        return Response({"error": "Payment provider unavailable. Please try again."}, status=status.HTTP_502_BAD_GATEWAY)

    if not result.get("status"):
        return Response({"error": result.get("message", "Failed to initiate payment.")}, status=status.HTTP_400_BAD_REQUEST)

    Donation.objects.create(
        user=user,
        amount=amount,
        reference=reference,
        status=Donation.STATUS_PENDING,
        email=email,
    )

    return Response({
        "authorization_url": result["data"]["authorization_url"],
        "reference": reference,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def verify_donation(request):
    """
    GET /api/subscriptions/donate/verify/?reference=xxx

    Called by the frontend after Paystack redirects back.
    """
    reference = request.query_params.get("reference", "").strip()
    if not reference:
        return Response({"error": "reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        donation = Donation.objects.get(reference=reference)
    except Donation.DoesNotExist:
        return Response({"error": "Donation not found."}, status=status.HTTP_404_NOT_FOUND)

    if donation.status == Donation.STATUS_SUCCESS:
        return Response({"status": "success", "amount": str(donation.amount)})

    if donation.status == Donation.STATUS_FAILED:
        return Response({"status": "failed"})

    # Auto-fail stale pending donations (>30 min old) without hitting Paystack
    if (timezone.now() - donation.created_at) > timedelta(minutes=30):
        donation.status = Donation.STATUS_FAILED
        donation.save(update_fields=["status"])
        logger.info("verify: stale pending donation %s auto-failed", reference)
        return Response({"status": "failed"})

    try:
        result = paystack_client.verify_transaction(reference)
    except Exception as exc:
        logger.error("Paystack verify error: %s", exc)
        return Response({"error": "Could not verify payment. Please contact support."}, status=status.HTTP_502_BAD_GATEWAY)

    data = result.get("data", {})
    if result.get("status") and data.get("status") == "success":
        confirmed_amount = data.get("amount", 0) / 100  # pesewas → GHS
        if round(float(confirmed_amount), 2) != round(float(donation.amount), 2):
            logger.warning(
                "Paystack amount mismatch for ref=%s: expected=%s confirmed=%s",
                reference, donation.amount, confirmed_amount,
            )
            return Response({"error": "Payment amount mismatch. Contact support."}, status=status.HTTP_402_PAYMENT_REQUIRED)
        mark_donation_paid(donation)
        return Response({"status": "success", "amount": str(donation.amount)})

    paystack_status = data.get("status", "failed")
    donation.status = Donation.STATUS_FAILED
    donation.save(update_fields=["status"])
    return Response({"status": paystack_status})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def webhook(request):
    """
    POST /api/subscriptions/webhook/

    Single entry point for all Paystack events.
    Signature is always verified before dispatch.
    To handle new event types, register a handler in helpers.WEBHOOK_HANDLERS.
    """
    if not settings.PAYSTACK_SECRET_KEY:
        logger.error("Webhook received but PAYSTACK_SECRET_KEY is not configured")
        return Response({"error": "Not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    paystack_sig = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
    secret       = settings.PAYSTACK_SECRET_KEY.encode("utf-8")
    expected     = hmac.new(secret, request.body, hashlib.sha512).hexdigest()

    if not hmac.compare_digest(expected, paystack_sig):
        logger.warning("Rejected webhook: invalid signature")
        return Response({"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return Response({"error": "Invalid JSON."}, status=status.HTTP_400_BAD_REQUEST)

    event   = payload.get("event")
    handler = WEBHOOK_HANDLERS.get(event)

    if handler:
        try:
            handler(payload.get("data", {}))
        except Exception as exc:
            logger.error("Webhook handler error for event '%s': %s", event, exc)
    else:
        logger.debug("Unhandled webhook event: %s", event)

    return Response({"received": True})
