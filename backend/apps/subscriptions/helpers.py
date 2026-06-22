"""
Non-view logic for the subscriptions app.

- Payment confirmation helpers (shared between the verify endpoint and the webhook)
- Webhook event handler registry (add Phase 2 handlers here, not in views.py)
"""
import logging
import uuid

from django.db import transaction
from django.utils import timezone

from .models import Donation, PaymentHistory

logger = logging.getLogger(__name__)


# ── Reference generation ──────────────────────────────────────────────────────

def generate_reference():
    return f"ocasia-{uuid.uuid4().hex[:16]}"


# ── Payment confirmation ──────────────────────────────────────────────────────

def mark_donation_paid(donation):
    """
    Confirm a donation, flag the user as a donor, and write a PaymentHistory row.

    Idempotent and race-safe: uses a DB row lock so concurrent webhook deliveries
    or a simultaneous verify + webhook cannot both process the same donation.
    """
    with transaction.atomic():
        # Re-fetch with a row lock — concurrent callers block here until we release
        locked = Donation.objects.select_for_update().get(pk=donation.pk)
        if locked.status == Donation.STATUS_SUCCESS:
            return

        now = timezone.now()
        locked.status  = Donation.STATUS_SUCCESS
        locked.paid_at = now
        locked.save(update_fields=["status", "paid_at"])

        if locked.user_id:
            locked.user.__class__.objects.filter(pk=locked.user_id).update(is_donor=True)

        PaymentHistory.objects.get_or_create(
            reference=locked.reference,
            defaults={
                "user_id": locked.user_id,
                "amount":  locked.amount,
                "type":    PaymentHistory.TYPE_DONATION,
                "status":  PaymentHistory.STATUS_SUCCESS,
                "paid_at": now,
            },
        )


# ── Webhook event handlers ────────────────────────────────────────────────────
# Each handler receives the `data` dict from the Paystack event payload.
# Register new handlers in WEBHOOK_HANDLERS below — views.py never changes.

def _on_charge_success(data):
    reference = data.get("reference", "")
    try:
        donation = Donation.objects.get(reference=reference)
    except Donation.DoesNotExist:
        # Not a donation reference.
        # Phase 2: also check Subscription records here for recurring charges.
        return
    mark_donation_paid(donation)
    logger.info("charge.success: donation %s confirmed", reference)


WEBHOOK_HANDLERS = {
    "charge.success": _on_charge_success,
    # Phase 2 — implement and uncomment when subscriptions ship:
    # "subscription.create":    _on_subscription_create,
    # "subscription.disable":   _on_subscription_disable,
    # "invoice.payment_failed": _on_invoice_failed,
    # "invoice.update":         _on_invoice_update,
}
