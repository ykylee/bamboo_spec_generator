from __future__ import annotations

from apps.buildmeta.services import get_infra_readiness


def provider_context(request):
    infra_readiness = get_infra_readiness()
    return {
        "current_provider": "",
        "provider_query": "",
        "infraReadiness": infra_readiness,
    }
