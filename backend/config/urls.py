"""Root URL configuration: API routes + SPA fallback for the built React app."""
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.ingestion.urls")),
    path("api/", include("apps.reconciliation.urls")),
    path("api/", include("apps.explain.urls")),
    # SPA: serve the built React app for any non-API path (single deployment unit)
    re_path(
        r"^(?!api/|admin/|static/).*$",
        TemplateView.as_view(template_name="index.html"),
        name="spa",
    ),
]
