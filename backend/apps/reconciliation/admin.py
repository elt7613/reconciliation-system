from django.contrib import admin

from .models import Discrepancy, ReconciliationRun


@admin.register(ReconciliationRun)
class ReconciliationRunAdmin(admin.ModelAdmin):
    list_display = ("id", "batch", "created_at", "total_orders", "total_payments", "money_at_risk")


@admin.register(Discrepancy)
class DiscrepancyAdmin(admin.ModelAdmin):
    list_display = ("type", "severity", "order_ref", "amount_at_risk")
    list_filter = ("type", "severity")
    search_fields = ("order_ref",)
