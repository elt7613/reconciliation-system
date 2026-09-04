"""Ingestion routes."""
from django.urls import path

from .views import BatchListView, UploadView

app_name = "ingestion"

urlpatterns = [
    path("imports/", UploadView.as_view(), name="upload"),
    path("batches/", BatchListView.as_view(), name="batches"),
]
