from django.conf import settings
from django.db import models
from django.utils import timezone

PLAN_CHOICES = [
    ("free", "Free"),
    ("premium", "Premium"),
]

STATUS_CHOICES = [
    ("created", "Order created"),
    ("paid", "Paid / active"),
    ("failed", "Failed"),
    ("expired", "Expired"),
]


class Subscription(models.Model):
    """
    Tracks a user's plan. `status` becomes "paid" only after Razorpay's
    payment signature is verified server-side (see billing/views.py).
    Premium plans last 3 months from the payment date (`period_end`).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="created")
    period_end = models.DateTimeField(null=True, blank=True)

    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_signature = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_premium(self):
        if self.plan != "premium" or self.status != "paid":
            return False
        if self.period_end and self.period_end < timezone.now():
            return False
        return True

    def __str__(self):
        return f"{self.user} — {self.plan} ({self.status})"
