"""Explain routes."""
from django.urls import path

from .views import ExplainDiscrepancyView, SummarizeRunView

app_name = "explain"

urlpatterns = [
    path("discrepancies/<int:discrepancy_id>/explain/", ExplainDiscrepancyView.as_view(), name="explain"),
    path("runs/<int:run_id>/summarize/", SummarizeRunView.as_view(), name="summarize"),
]
