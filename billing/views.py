import hmac
import hashlib
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .models import Subscription

PREMIUM_PRICE_PAISE = 10900  # ₹109.00 for 3 months
PREMIUM_DURATION_DAYS = 90


def _get_or_create_subscription(user):
    sub, _ = Subscription.objects.get_or_create(user=user, defaults={"plan": "free", "status": "paid"})
    return sub


@login_required
def plans_view(request):
    """Pricing page — Free vs Premium, with an 'Upgrade' button that opens Razorpay checkout."""
    sub = _get_or_create_subscription(request.user)
    context = {
        "subscription": sub,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "razorpay_configured": bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
        "price_display": f"₹{PREMIUM_PRICE_PAISE / 100:.0f}",
    }
    return render(request, "billing/plans.html", context)


@login_required
def create_order(request):
    """
    POST /billing/create-order/
    Creates a Razorpay order for the Premium plan (₹109 / 3 months) and
    returns the order_id to the frontend, which opens Razorpay's checkout.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        return JsonResponse(
            {"error": "Razorpay is not configured yet. Add RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET to .env."},
            status=400,
        )

    import razorpay

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create(
        {
            "amount": PREMIUM_PRICE_PAISE,
            "currency": "INR",
            "receipt": f"user-{request.user.id}-upgrade",
            "notes": {"user_id": str(request.user.id)},
        }
    )

    sub = _get_or_create_subscription(request.user)
    sub.razorpay_order_id = order["id"]
    sub.status = "created"
    sub.save(update_fields=["razorpay_order_id", "status"])

    return JsonResponse(
        {
            "order_id": order["id"],
            "amount": PREMIUM_PRICE_PAISE,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
        }
    )


@csrf_exempt
@login_required
def verify_payment(request):
    """
    POST /billing/verify-payment/
    Called by the frontend after Razorpay's checkout succeeds. Verifies the
    signature server-side before activating the 3-month Premium period.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        data = json.loads(request.body)
        razorpay_order_id = data["razorpay_order_id"]
        razorpay_payment_id = data["razorpay_payment_id"]
        razorpay_signature = data["razorpay_signature"]
    except (KeyError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid payload"}, status=400)

    sub = _get_or_create_subscription(request.user)
    if sub.razorpay_order_id != razorpay_order_id:
        return JsonResponse({"error": "Order mismatch"}, status=400)

    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, razorpay_signature):
        sub.status = "failed"
        sub.save(update_fields=["status"])
        return JsonResponse({"error": "Signature verification failed"}, status=400)

    sub.plan = "premium"
    sub.status = "paid"
    sub.period_end = timezone.now() + timedelta(days=PREMIUM_DURATION_DAYS)
    sub.razorpay_payment_id = razorpay_payment_id
    sub.razorpay_signature = razorpay_signature
    sub.save()

    return JsonResponse({"success": True, "plan": "premium", "period_end": sub.period_end.isoformat()})
