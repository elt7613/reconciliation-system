"""Root URL configuration — API routes only (SPA is served by its own app)."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    """Unauthenticated liveness probe for load balancers and container healthchecks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health, name="health"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.ingestion.urls")),
    path("api/", include("apps.reconciliation.urls")),
    path("api/", include("apps.explain.urls")),
]
