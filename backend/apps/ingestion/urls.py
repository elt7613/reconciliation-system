"""Ingestion routes."""
from django.urls import path

from .views import BatchListView, SampleDataView, UploadView

app_name = "ingestion"

urlpatterns = [
    path("imports/", UploadView.as_view(), name="upload"),
    path("imports/sample/", SampleDataView.as_view(), name="sample"),
    path("batches/", BatchListView.as_view(), name="batches"),
]
