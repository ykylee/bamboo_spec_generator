from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


class UiPlaywrightE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.sqlite_path = Path(cls.temp_dir.name) / "playwright-e2e.sqlite3"
        cls.port = cls._find_free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_env = os.environ.copy()
        cls.server_env.update(
            {
                "DJANGO_SETTINGS_MODULE": "config.settings.local",
                "BAMBOO_DB_ENGINE": "sqlite",
                "BAMBOO_DB_SQLITE_NAME": str(cls.sqlite_path),
                "DJANGO_ALLOWED_HOSTS": "127.0.0.1,localhost",
                "DJANGO_ALLOW_ASYNC_UNSAFE": "true",
            }
        )

        subprocess.run(
            ["python3", "backend/manage.py", "migrate", "--noinput"],
            cwd=REPO_ROOT,
            env=cls.server_env,
            check=True,
        )

        sys.path.insert(0, str(BACKEND_ROOT))
        os.environ.update(cls.server_env)
        import django

        django.setup()
        from django.core.management import call_command

        cls._call_command = staticmethod(call_command)
        from apps.buildmeta.models import BuildPlan, BuildPlanDefinition, Project, ProjectBuild, ProjectRepository

        cls.BuildPlan = BuildPlan
        cls.BuildPlanDefinition = BuildPlanDefinition
        cls.Project = Project
        cls.ProjectBuild = ProjectBuild
        cls.ProjectRepository = ProjectRepository

        cls.server_process = subprocess.Popen(
            ["python3", "backend/manage.py", "runserver", f"127.0.0.1:{cls.port}", "--noreload"],
            cwd=REPO_ROOT,
            env=cls.server_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls._wait_for_server()

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.firefox.launch(headless=True)

    @classmethod
    def tearDownClass(cls) -> None:
        browser = getattr(cls, "browser", None)
        if browser is not None:
            browser.close()
        playwright = getattr(cls, "playwright", None)
        if playwright is not None:
            playwright.stop()

        server_process = getattr(cls, "server_process", None)
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=10)

        temp_dir = getattr(cls, "temp_dir", None)
        if temp_dir is not None:
            temp_dir.cleanup()

    def setUp(self) -> None:
        type(self)._call_command("flush", interactive=False, verbosity=0)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()

    def tearDown(self) -> None:
        self.context.close()

    @classmethod
    def _find_free_port(cls) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @classmethod
    def _wait_for_server(cls) -> None:
        last_error: Exception | None = None
        for _ in range(100):
            if cls.server_process.poll() is not None:
                raise RuntimeError(f"runserver exited early with code {cls.server_process.returncode}")
            try:
                with urlopen(cls.base_url, timeout=1) as response:
                    if response.status == 200:
                        return
            except Exception as exc:  # pragma: no cover - only for server boot timing
                last_error = exc
                time.sleep(0.2)
        raise RuntimeError(f"Timed out waiting for Django server at {cls.base_url}: {last_error}")

    def _create_project_with_build(
        self,
        *,
        jira_project_key: str,
        bitbucket_project_key: str,
        repo_slug: str,
        build_name: str,
        build_id: str,
        plan_key: str,
        build_type: str = "python",
        runtime_stack: str = "python3.12",
        coverity_project: str = "",
        coverity_stream: str = "",
        with_active_definition: bool = False,
        definition_year: str = "2026",
    ) -> None:
        project = self.Project.objects.create(
            jira_project_key=jira_project_key,
            bitbucket_project_key=bitbucket_project_key,
            representative_repo_slug=repo_slug,
        )
        repository = self.ProjectRepository.objects.create(
            project=project,
            repo_slug=repo_slug,
            coverity_project=coverity_project,
            coverity_stream=coverity_stream,
            is_representative=True,
        )
        build_plan = self.BuildPlan.objects.create(build_id=build_id, plan_key=plan_key)
        self.ProjectBuild.objects.create(
            project=project,
            repository=repository,
            build_plan=build_plan,
            build_name=build_name,
            build_type=build_type,
            runtime_stack=runtime_stack,
        )
        if with_active_definition:
            self.BuildPlanDefinition.objects.create(
                build_plan=build_plan,
                project=project,
                year=definition_year,
                source_kind=self.BuildPlanDefinition.SOURCE_KIND_JSON,
                definition_json={"buildId": build_id, "planKey": plan_key},
                definition_hash=f"sha256:{plan_key.lower()}",
                is_active=True,
            )

    def test_registration_panel_toggle_and_repeaters_work_in_browser(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded")

        registration_panel = self.page.locator("#project-registration-panel")
        toggle_button = self.page.locator("[data-toggle-registration]")

        self.assertEqual("", registration_panel.get_attribute("hidden"))
        self.assertEqual("false", toggle_button.get_attribute("aria-expanded"))
        self.assertEqual(1, self.page.locator("[data-repository-row]").count())
        self.assertEqual(1, self.page.locator("[data-build-row]").count())

        toggle_button.click()
        self.page.wait_for_timeout(150)

        self.assertIsNone(registration_panel.get_attribute("hidden"))
        self.assertEqual("true", toggle_button.get_attribute("aria-expanded"))

        self.page.locator("[data-add-repository]").click()
        self.page.locator("[data-add-build]").click()

        self.assertEqual(2, self.page.locator("[data-repository-row]").count())
        self.assertEqual(2, self.page.locator("[data-build-row]").count())

    def test_registration_flow_redirects_to_detail_in_browser(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.locator("[data-toggle-registration]").click()

        self.page.locator('input[name="jira_project_key"]').fill("OPS")
        self.page.locator('input[name="bitbucket_project_key"]').fill("OPS")
        self.page.locator('input[name="representative_repo_slug"]').fill("ops-api")

        self.page.locator('input[name="repo_slug"]').first.fill("ops-api")
        self.page.locator('input[name="coverity_project"]').first.fill("ops-api")
        self.page.locator('input[name="coverity_stream"]').first.fill("ops-api-dev")

        self.page.locator('input[name="build_name"]').first.fill("Operations API")
        self.page.locator('input[name="build_type"]').first.fill("python")
        self.page.locator('input[name="runtime_stack"]').first.fill("python3.12")
        self.page.locator('input[name="build_id"]').first.fill("ops-api")
        self.page.locator('input[name="plan_key"]').first.fill("OPSAPI")
        self.page.locator('input[name="build_repository_slug"]').first.fill("ops-api")

        self.page.get_by_role("button", name="등록하기").click()
        self.page.wait_for_url(f"{self.base_url}/projects/OPS/")

        self.assertEqual(f"{self.base_url}/projects/OPS/", self.page.url)
        self.assertTrue(self.Project.objects.filter(jira_project_key="OPS").exists())
        self.assertEqual("OPS", self.page.locator(".hero__title").inner_text())
        self.assertTrue(self.page.get_by_text("Specs 준비 필요").is_visible())
        self.assertTrue(self.page.get_by_text("Repository: ops-api").is_visible())

    def test_detail_edit_panel_shows_validation_error_in_browser(self) -> None:
        self._create_project_with_build(
            jira_project_key="SAMPLE",
            bitbucket_project_key="SAMPLE",
            repo_slug="sample-app-api",
            build_name="Sample API",
            build_id="sample-app-api",
            plan_key="SAMPAPI",
            build_type="maven",
            runtime_stack="java",
            coverity_project="sample-app-api",
            coverity_stream="sample-app-api-dev",
            with_active_definition=True,
        )

        self.page.goto(f"{self.base_url}/projects/SAMPLE/", wait_until="domcontentloaded")
        edit_panel = self.page.locator("#project-edit-panel")
        toggle_button = self.page.locator("[data-toggle-edit]")

        self.assertEqual("", edit_panel.get_attribute("hidden"))
        self.assertEqual("false", toggle_button.get_attribute("aria-expanded"))

        toggle_button.click()
        self.page.wait_for_timeout(150)

        representative_input = self.page.locator('input[name="representative_repo_slug"]')
        representative_input.fill("missing-repo")
        self.page.get_by_role("button", name="수정 저장").click()

        self.page.wait_for_load_state("domcontentloaded")
        self.assertTrue(self.page.get_by_text("대표 저장소는 등록한 저장소 목록 중 하나여야 합니다.").is_visible())
        self.assertIsNone(edit_panel.get_attribute("hidden"))
        self.assertEqual("true", toggle_button.get_attribute("aria-expanded"))
        self.assertEqual("missing-repo", representative_input.input_value())
