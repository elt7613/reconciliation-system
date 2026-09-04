"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.ingestion.urls")),
    path("api/", include("apps.reconciliation.urls")),
    path("api/", include("apps.explain.urls")),
]
