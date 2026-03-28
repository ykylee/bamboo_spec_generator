from __future__ import annotations

from ninja import NinjaAPI

from apps.api.auth import GeneratorTokenAuth
from apps.api.routers import (
    build_plans_router,
    executions_router,
    jenkins_jobs_router,
    module_registry_router,
    projects_router,
    system_settings_router,
)


api = NinjaAPI(title="bamboo_spec_generator API", version="1.0", auth=GeneratorTokenAuth())
api.add_router("/v1/projects", projects_router)
api.add_router("/v1/build-plans", build_plans_router)
api.add_router("/v1/jenkins-jobs", jenkins_jobs_router)
api.add_router("/v1/admin/modules", module_registry_router)
api.add_router("/v1/system-settings", system_settings_router)
api.add_router("/v1", executions_router)
