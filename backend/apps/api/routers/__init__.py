from .build_plans import router as build_plans_router
from .executions import router as executions_router
from .jenkins_jobs import router as jenkins_jobs_router
from .projects import router as projects_router
from .system_settings import router as system_settings_router

__all__ = ["build_plans_router", "executions_router", "jenkins_jobs_router", "projects_router", "system_settings_router"]
