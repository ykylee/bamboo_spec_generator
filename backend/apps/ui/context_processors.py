from __future__ import annotations

from apps.buildmeta.models import Project


def provider_context(request):
    value = (request.GET.get("provider") or request.POST.get("ci_provider") or "").strip().lower()
    current_provider = value or Project.PROVIDER_BAMBOO
    return {"current_provider": current_provider}
