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
        from apps.buildmeta.models import BambooBuildUnit, BuildUnit, BuildUnitDefinition, Project, Repository

        cls.Project = Project
        cls.Repository = Repository
        cls.BuildUnit = BuildUnit
        cls.BambooBuildUnit = BambooBuildUnit
        cls.BuildUnitDefinition = BuildUnitDefinition

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
        build_plan_coverity_project: str = "",
        static_analysis_tool_version: str = "",
        with_active_definition: bool = False,
        definition_year: str = "2026",
    ) -> None:
        project = self.Project.objects.create(
            project_key=jira_project_key,
            name=jira_project_key,
            ci_provider="bamboo",
        )
        repository = self.Repository.objects.create(
            project=project,
            repo_key=bitbucket_project_key,
            repo_slug=repo_slug,
            coverity_project=coverity_project,
            coverity_stream=coverity_stream,
            is_representative=True,
        )
        project.representative_repository = repository
        project.save()
        build_unit = self.BuildUnit.objects.create(
            project=project,
            repository=repository,
            ci_provider="bamboo",
            external_key=build_id,
            display_name=build_name,
            compiler=build_type,
            runtime_stack=runtime_stack,
        )
        self.BambooBuildUnit.objects.create(
            build_unit=build_unit,
            plan_key=plan_key,
            build_id=build_id,
            coverity_project=build_plan_coverity_project,
            static_analysis_tool_version=static_analysis_tool_version,
        )
        if with_active_definition:
            self.BuildUnitDefinition.objects.create(
                build_unit=build_unit,
                year=definition_year,
                source_kind="json",
                definition_json={
                    "buildId": build_id,
                    "name": build_name,
                    "planKey": plan_key,
                    "language": "java",
                    "compiler": "maven",
                    "repository": {
                        "provider": "bitbucket",
                        "projectKey": bitbucket_project_key,
                        "repoSlug": repo_slug,
                        "linkageMode": "create_if_missing",
                        "applicationLink": "BITBUCKET_DC",
                        "branches": ["dev", "release", "master"],
                    },
                    "requirements": {"os": "linux", "extraCapabilities": []},
                    "build": {
                        "subPath": "services/sample-app-api",
                        "prepareCommand": "mvn -B dependency:go-offline",
                        "buildCommand": "mvn -B clean package",
                        "staticAnalysis": {"customTool": {"commands": ["custom-tool analyze {buildCommand}"]}},
                        "runtimeRequirements": {"commands": ["mvn", "coverity"], "envVars": ["JAVA_HOME"]},
                        "postBuildTrigger": {"type": "plan", "targetPlanKey": "POSTBUILD"},
                    },
                },
                definition_hash=f"sha256:{plan_key.lower()}",
                is_active=True,
            )

    def test_registration_panel_toggle_and_repeaters_work_in_browser(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded")

        registration_panel = self.page.locator("#project-registration-panel")
        toggle_button = self.page.get_by_role("button", name="프로젝트 등록")

        self.assertEqual("", registration_panel.get_attribute("hidden"))
        self.assertEqual("false", toggle_button.get_attribute("aria-expanded"))
        self.assertEqual(1, self.page.locator("[data-repository-row]").count())
        self.assertEqual(1, self.page.locator("[data-build-row]").count())

        toggle_button.click()
        self.page.wait_for_timeout(150)

        self.assertIsNone(registration_panel.get_attribute("hidden"))
        self.assertEqual("true", toggle_button.get_attribute("aria-expanded"))
        header_box = self.page.locator(".app-header").bounding_box()
        panel_box = registration_panel.bounding_box()
        self.assertIsNotNone(header_box)
        self.assertIsNotNone(panel_box)
        self.assertGreaterEqual(panel_box["y"], header_box["height"] - 2)

        self.page.locator("[data-add-repository]").click()
        self.page.locator("[data-add-build]").click()

        self.assertEqual(2, self.page.locator("[data-repository-row]").count())
        self.assertEqual(2, self.page.locator("[data-build-row]").count())

        self.page.locator('input[name="jira_project_key"]').fill("TEMP")
        self.page.locator('input[name="repo_slug"]').first.fill("temp-repo")
        self.page.locator('input[name="build_name"]').first.fill("Temp Build")

        self.page.get_by_role("button", name="접기", exact=True).click()
        self.page.wait_for_timeout(350)
        self.assertEqual("", registration_panel.get_attribute("hidden"))
        self.assertEqual("false", toggle_button.get_attribute("aria-expanded"))

        toggle_button.click()
        self.page.wait_for_timeout(150)
        self.assertEqual("", self.page.locator('input[name="jira_project_key"]').input_value())
        self.assertEqual("", self.page.locator('input[name="repo_slug"]').first.input_value())
        self.assertEqual("", self.page.locator('input[name="build_name"]').first.input_value())
        self.assertEqual(1, self.page.locator("[data-repository-row]").count())
        self.assertEqual(1, self.page.locator("[data-build-row]").count())

    def test_nav_search_requires_keyword_and_filters_matching_projects(self) -> None:
        self._create_project_with_build(
            jira_project_key="OPS",
            bitbucket_project_key="OPSBB",
            repo_slug="ops-api",
            build_name="Operations API",
            build_id="ops-api",
            plan_key="OPSAPI",
            with_active_definition=True,
        )
        self._create_project_with_build(
            jira_project_key="WEB",
            bitbucket_project_key="WEBBB",
            repo_slug="web-portal",
            build_name="Web Portal",
            build_id="web-portal",
            plan_key="WEBPORTAL",
            with_active_definition=True,
        )

        self.page.goto(self.base_url, wait_until="domcontentloaded")

        self.assertTrue(self.page.get_by_text("주의가 필요한 프로젝트를 먼저 보여줍니다.").is_visible())
        self.assertTrue(self.page.get_by_text("프로젝트 리스트").is_visible())
        self.page.wait_for_timeout(300)
        self.assertTrue(self.page.get_by_text("주의가 필요한 프로젝트를 먼저 보여줍니다.").is_visible())
        self.assertTrue(self.page.locator("#failed-build-panel .panel__title").is_visible())

        search_input = self.page.locator("#project-nav-search")
        results = self.page.locator("[data-project-search-results]")

        search_input.click()
        self.assertTrue(results.is_hidden())

        search_input.fill("ops")
        self.page.wait_for_timeout(150)

        self.assertTrue(results.is_visible())
        self.assertEqual(["OPS"], self.page.locator("[data-project-search-item]:not([hidden]) strong").all_inner_texts())

        search_input.fill("")
        self.page.wait_for_timeout(150)
        self.assertTrue(results.is_hidden())

    def test_registration_inputs_allow_manual_entry_and_searchable_suggestions(self) -> None:
        self._create_project_with_build(
            jira_project_key="OPS",
            bitbucket_project_key="OPSBB",
            repo_slug="ops-api",
            build_name="Operations API",
            build_id="ops-api",
            plan_key="OPSAPI",
            with_active_definition=True,
        )

        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.get_by_role("button", name="프로젝트 등록").click()
        self.page.locator('select[name="ci_provider"]').select_option("jenkins")
        self.page.wait_for_timeout(150)

        self.assertTrue(self.page.get_by_text("Job Key").first.is_visible())
        self.assertTrue(self.page.get_by_text("Job Path").first.is_visible())

        self.page.locator('select[name="ci_provider"]').select_option("bamboo")
        self.page.wait_for_timeout(150)

        representative_input = self.page.locator('input[name="representative_repo_slug"]')
        representative_input.fill("ops")
        self.page.wait_for_timeout(150)

        suggestion_panel = self.page.locator(".project-form__suggestions").filter(has=representative_input).first
        self.assertTrue(self.page.get_by_role("button", name="ops-api").is_visible())

        self.page.get_by_role("button", name="ops-api").click()
        self.assertEqual("ops-api", representative_input.input_value())

        representative_input.fill("manual-custom-repo")
        self.page.wait_for_timeout(150)
        self.assertEqual("manual-custom-repo", representative_input.input_value())

    def test_registration_flow_redirects_to_detail_in_browser(self) -> None:
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.get_by_role("button", name="프로젝트 등록").click()

        self.page.locator('select[name="ci_provider"]').select_option("bamboo")
        self.page.locator('input[name="jira_project_key"]').fill("OPS")
        self.page.locator('input[name="bitbucket_project_key"]').fill("OPS")
        self.page.locator('input[name="representative_repo_slug"]').fill("ops-api")

        self.page.locator('select[name="repo_type"]').first.select_option("git")
        self.page.locator('input[name="repo_slug"]').first.fill("ops-api")
        self.page.locator('input[name="coverity_project"]').first.fill("ops-api")
        self.page.locator('input[name="coverity_stream"]').first.fill("ops-api-dev")

        self.page.locator('input[name="build_name"]').first.fill("Operations API")
        self.page.locator('input[name="build_type"]').first.fill("python")
        self.page.locator('input[name="runtime_stack"]').first.fill("python3.12")
        self.page.locator('input[name="build_id"]').first.fill("ops-api")
        self.page.locator('input[name="plan_key"]').first.fill("OPSAPI")
        self.page.locator('select[name="repository_linkage_mode"]').first.select_option("create_if_missing")
        self.page.locator('input[name="build_repository_slug"]').first.fill("ops-api")

        self.page.get_by_role("button", name="등록하기").click()
        self.page.wait_for_url(f"{self.base_url}/projects/OPS/")

        self.assertEqual(f"{self.base_url}/projects/OPS/", self.page.url)
        self.assertTrue(self.Project.objects.filter(project_key="OPS", ci_provider="bamboo").exists())
        self.assertTrue(self.Repository.objects.filter(project__project_key="OPS", repo_type="git").exists())
        self.assertTrue(
            self.BambooBuildUnit.objects.filter(build_unit__project__project_key="OPS", repository_linkage_mode="create_if_missing").exists()
        )
        self.assertEqual("OPS", self.page.locator(".hero__title").inner_text())
        self.assertTrue(self.page.get_by_text("연결 점검 필요").is_visible())
        self.assertTrue(self.page.locator("#project-repository-add-panel").count() == 1)
        self.assertTrue(self.page.locator("#project-build-add-panel").count() == 1)

    def test_project_list_pagination_updates_only_list_panel_in_browser(self) -> None:
        for index in range(11):
            self._create_project_with_build(
                jira_project_key=f"PAG{index:02d}",
                bitbucket_project_key="PAGE",
                repo_slug=f"page-repo-{index:02d}",
                build_name=f"Page Build {index:02d}",
                build_id=f"page-build-{index:02d}",
                plan_key=f"PAGE{index:02d}",
                with_active_definition=True,
            )

        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.get_by_role("button", name="프로젝트 등록").click()
        registration_panel = self.page.locator("#project-registration-panel")
        self.assertIsNone(registration_panel.get_attribute("hidden"))

        self.page.locator(".pagination").get_by_role("link", name="2").click()
        self.page.wait_for_timeout(300)

        self.assertTrue(self.page.url.endswith("/?page=2"))
        self.assertIsNone(registration_panel.get_attribute("hidden"))
        self.assertTrue(
            self.page.locator("[data-project-list-container]").get_by_text("PAG10", exact=True).first.is_visible()
        )

    def test_build_plan_page_is_reachable_from_navigation(self) -> None:
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
            build_plan_coverity_project="sample-api-coverity",
            static_analysis_tool_version="coverity-2024.12",
            with_active_definition=True,
        )

        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.get_by_role("link", name="빌드 플랜").first.click()
        self.page.wait_for_url(f"{self.base_url}/build-plans/")

        self.assertTrue(self.page.get_by_text("빌드 플랜 인덱스").is_visible())
        self.assertTrue(self.page.locator("table.project-table").get_by_text("Sample API").is_visible())
        self.assertIn("coverity-2024.12", self.page.locator("body").text_content())
        self.page.get_by_role("link", name="플랜 상세").first.click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/builds/SAMPAPI/")

    def test_build_detail_updates_plan_metadata_and_registers_build_info(self) -> None:
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
        )

        self.page.goto(f"{self.base_url}/projects/SAMPLE/builds/SAMPAPI/", wait_until="domcontentloaded")
        metadata_panel = self.page.locator("#build-plan-metadata-panel")
        self.assertEqual("", metadata_panel.get_attribute("hidden"))
        self.page.get_by_role("button", name="빌드 플랜 수정").first.click()
        self.page.wait_for_timeout(300)
        self.assertIsNone(metadata_panel.get_attribute("hidden"))
        self.page.locator('input[name="static_analysis_tool_version"]').fill("coverity-2024.12")
        self.page.locator('input[name="coverity_project"]').fill("sample-api-coverity")
        self.page.get_by_role("button", name="수정 저장").click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/builds/SAMPAPI/")

        self.assertTrue(self.page.locator(".signal-hero").get_by_text("coverity-2024.12").first.is_visible())
        self.assertTrue(self.page.locator(".signal-hero").get_by_text("sample-api-coverity").first.is_visible())

        build_info_panel = self.page.locator("#build-info-add-panel")
        self.assertEqual("", build_info_panel.get_attribute("hidden"))
        self.page.get_by_role("link", name="빌드 정보 등록").first.click()
        self.page.wait_for_timeout(300)
        self.assertIn("/projects/SAMPLE/builds/SAMPAPI/?add_build_info=open", self.page.url)
        self.assertIsNone(build_info_panel.get_attribute("hidden"))
        self.page.locator('input[name="build_key"]').fill("api-linux")
        self.page.locator('input[name="operating_system"]').fill("linux")
        self.page.locator('input[name="language"]').fill("java")
        self.page.locator('input[name="compiler"]').fill("maven")
        self.page.locator('input[name="coverity_stream"]').fill("sample-api-dev")
        self.page.locator('input[name="build_sub_path"]').fill("services/api")
        self.page.locator('textarea[name="build_command"]').fill("mvn -B clean package")
        self.page.get_by_role("button", name="빌드 정보 등록").click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/builds/SAMPAPI/")
        self.assertTrue(self.page.get_by_text("api-linux").first.is_visible())
        self.assertTrue(self.page.get_by_role("heading", name="예상 Bamboo Plan 구성").is_visible())
        self.assertTrue(self.page.get_by_text("현재 입력 데이터 기준으로 계산한 예상 Bamboo stage, job, task 구조입니다.").is_visible())
        self.assertTrue(self.page.get_by_text("Build", exact=True).is_visible())
        self.page.locator('[data-task-select]').filter(has_text="Run Build Script").first.click()
        self.assertTrue(self.page.get_by_text("mvn -B clean package").first.is_visible())
        self.assertTrue(self.page.get_by_text("linux").first.is_visible())
        self.assertTrue(self.page.locator('[data-task-select]').filter(has_text="Run Coverity Script").first.is_visible())
        self.assertTrue(self.page.locator('[data-task-select]').filter(has_text="Run Custom Analysis Script").first.is_visible())
        self.assertTrue(self.page.locator('[data-task-select]').filter(has_text="Trigger Follow-up").first.is_visible())
        self.page.locator('[data-task-select]').filter(has_text="Run Coverity Script").first.click()
        self.page.locator(f'a[href="/projects/SAMPLE/builds/SAMPAPI/infos/api-linux/"]').first.click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/builds/SAMPAPI/infos/api-linux/")
        self.assertTrue(self.page.get_by_role("heading", name="빌드 정보 수정").is_visible())

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
        toggle_button = self.page.get_by_role("button", name="프로젝트 수정")

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

    def test_detail_edit_panel_resets_unsaved_changes_when_collapsed(self) -> None:
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
        open_button = self.page.get_by_role("button", name="프로젝트 수정")

        open_button.click()
        self.page.wait_for_timeout(150)

        bitbucket_input = self.page.locator('input[name="bitbucket_project_key"]')
        representative_input = self.page.locator('input[name="representative_repo_slug"]')
        bitbucket_input.fill("SAMPLE-EDIT")
        representative_input.fill("sample-app-web")

        edit_panel.get_by_role("button", name="접기", exact=True).click()
        self.page.wait_for_timeout(350)

        self.assertEqual("", edit_panel.get_attribute("hidden"))
        self.assertEqual("false", open_button.get_attribute("aria-expanded"))

        open_button.click()
        self.page.wait_for_timeout(150)

        self.assertIsNone(edit_panel.get_attribute("hidden"))
        self.assertEqual("true", open_button.get_attribute("aria-expanded"))
        self.assertEqual("SAMPLE", bitbucket_input.input_value())
        self.assertEqual("sample-app-api", representative_input.input_value())

    def test_repository_and_build_management_flows_are_embedded_in_project_detail(self) -> None:
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
        self.page.get_by_role("button", name="저장소 추가").click()
        self.page.wait_for_timeout(150)

        repository_panel = self.page.locator("#project-repository-add-panel")
        self.assertIsNone(repository_panel.get_attribute("hidden"))
        self.page.locator('input[name="repo_slug"]').fill("sample-app-web")
        self.page.locator('input[name="coverity_project"]').fill("sample-app-web")
        self.page.locator('input[name="coverity_stream"]').fill("sample-app-web-dev")
        self.page.get_by_role("button", name="저장소 등록").click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/repositories/sample-app-web/")

        self.assertTrue(self.page.get_by_role("heading", name="저장소 메타데이터").is_visible())
        self.assertTrue(self.page.get_by_role("heading", name="sample-app-web", exact=True).is_visible())

        self.page.goto(f"{self.base_url}/projects/SAMPLE/", wait_until="domcontentloaded")
        self.page.get_by_role("button", name="빌드 추가").click()
        self.page.wait_for_timeout(150)
        build_panel = self.page.locator("#project-build-add-panel")
        self.assertIsNone(build_panel.get_attribute("hidden"))
        self.page.locator('input[name="build_name"]').fill("Sample Web")
        self.page.locator('input[name="build_type"]').fill("node")
        self.page.locator('input[name="runtime_stack"]').fill("node20")
        self.page.locator('input[name="build_id"]').fill("sample-app-web")
        self.page.locator('input[name="plan_key"]').fill("SAMPWEB")
        self.page.locator('input[name="build_repository_slug"]').fill("sample-app-web")
        self.page.get_by_role("button", name="빌드 등록").click()
        self.page.wait_for_url(f"{self.base_url}/projects/SAMPLE/builds/SAMPWEB/")

        self.assertTrue(self.page.get_by_role("heading", name="빌드 플랜 메타데이터").is_visible())
        self.assertTrue(self.page.get_by_role("heading", name="Sample Web", exact=True).is_visible())
