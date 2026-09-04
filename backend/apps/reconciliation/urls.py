"""Reconciliation routes."""
from django.urls import path

from .views import (
    DiscrepancyDetailView,
    RunDetailView,
    RunDiscrepanciesView,
    RunListView,
)

app_name = "reconciliation"

urlpatterns = [
    path("runs/", RunListView.as_view(), name="runs"),
    path("runs/<int:run_id>/", RunDetailView.as_view(), name="run-detail"),
    path("runs/<int:run_id>/discrepancies/", RunDiscrepanciesView.as_view(), name="run-discrepancies"),
    path("discrepancies/<int:discrepancy_id>/", DiscrepancyDetailView.as_view(), name="discrepancy-detail"),
]
