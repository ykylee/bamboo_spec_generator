from __future__ import annotations

from apps.buildmeta.models import Project


def provider_context(request):
    value = (request.GET.get("provider") or request.POST.get("ci_provider") or "").strip().lower()
    current_provider = value or Project.PROVIDER_BAMBOO
    provider_query = "" if current_provider == Project.PROVIDER_BAMBOO else f"?provider={current_provider}"
    return {
        "current_provider": current_provider,
        "provider_query": provider_query,
    }
