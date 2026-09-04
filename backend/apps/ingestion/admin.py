from django.contrib import admin

from .models import ImportBatch, Order, Payment


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at", "order_row_count", "payment_row_count")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("normalized_id", "batch", "status", "net_amount", "currency")
    list_filter = ("status", "currency")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_ref", "normalized_order_ref", "type", "status", "amount")
    list_filter = ("type", "status")
