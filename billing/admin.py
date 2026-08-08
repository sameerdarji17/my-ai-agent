from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "period_end", "created_at"]
    list_filter = ["plan", "status"]
    search_fields = ["user__username", "user__email", "razorpay_order_id", "razorpay_payment_id"]
