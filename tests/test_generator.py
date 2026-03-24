from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import json
import subprocess
import unittest

from src.bamboo_spec_generator import __version__
from src.bamboo_spec_generator.parser import discover_input_files, parse_build_definition
from src.bamboo_spec_generator.java_assets import load_python_wrapper_method
from src.bamboo_spec_generator.script_assets import load_python_script_assets
from src.bamboo_spec_generator.script_renderer import render_python_launcher_scripts, render_python_scripts
from src.bamboo_spec_generator.validator import ValidationError, validate_build_definitions
from src.bamboo_spec_generator.writer import write_specs_project


class GeneratorFlowTest(unittest.TestCase):
    @staticmethod
    def _expected_source_revision() -> str:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return "unknown"
        return result.stdout.strip()

    def test_python_script_assets_exist_for_sample_builds(self) -> None:
        api_build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        mfc_build = parse_build_definition(Path("build_info_json/2026/sample-app-mfc.json"))

        api_assets = load_python_script_assets(api_build)
        mfc_assets = load_python_script_assets(mfc_build)

        self.assertIn("prepare_build.py", api_assets)
        self.assertIn("run_build.py", api_assets)
        self.assertIn("run_custom_analysis.py", api_assets)
        self.assertIn("prepare_build.py", mfc_assets)
        self.assertIn("run_build.py", mfc_assets)
        self.assertIn("run_custom_analysis.py", mfc_assets)
        self.assertIn("parse_command", api_assets["prepare_build.py"])
        self.assertIn("ensure_directory_build_targets", mfc_assets["run_build.py"])

    def test_python_wrapper_assets_exist_for_sample_builds(self) -> None:
        api_build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        mfc_build = parse_build_definition(Path("build_info_json/2026/sample-app-mfc.json"))

        api_wrapper = load_python_wrapper_method(api_build)
        mfc_wrapper = load_python_wrapper_method(mfc_build)

        self.assertIn("cat <<'__BAMBOO_SPEC_PY__'", api_wrapper)
        self.assertIn("powershell -NoProfile -Command ^", mfc_wrapper)

    def test_python_script_templates_render_for_sample_builds(self) -> None:
        api_build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        mfc_build = parse_build_definition(Path("build_info_json/2026/sample-app-mfc.json"))

        api_scripts = render_python_scripts(api_build)
        mfc_scripts = render_python_scripts(mfc_build)
        api_launchers = render_python_launcher_scripts(api_build)
        mfc_launchers = render_python_launcher_scripts(mfc_build)

        self.assertIn("Path('services/sample-app-api')", api_scripts["prepare_build.py"])
        self.assertIn("PLAN_KEY = 'SAMPAPI'", api_scripts["prepare_build.py"])
        self.assertIn("start_execution_if_configured()", api_scripts["prepare_build.py"])
        self.assertIn("command = 'mvn -B clean package'", api_scripts["run_build.py"])
        self.assertIn("start_execution_if_configured()", api_scripts["run_build.py"])
        self.assertIn("finish_execution_if_configured(", api_scripts["run_build.py"])
        self.assertIn("start_execution_if_configured()", api_scripts["run_coverity.py"])
        self.assertIn("record_static_analysis_result(", api_scripts["run_coverity.py"])
        self.assertIn("'custom-tool analyze mvn -B clean package',", api_scripts["run_custom_analysis.py"])
        self.assertIn("start_execution_if_configured()", api_scripts["run_custom_analysis.py"])
        self.assertIn("start_execution_if_configured()", api_scripts["trigger_follow_up.py"])
        self.assertIn("/static-analysis-results", api_scripts["run_coverity.py"])
        self.assertIn("/static-analysis-results", api_scripts["run_custom_analysis.py"])
        self.assertIn("Path('src/SampleAppMfc')", mfc_scripts["prepare_build.py"])
        self.assertIn("VS2022_ENV", mfc_scripts["run_build.py"])
        self.assertIn("Directory.Build.targets", mfc_scripts["run_custom_analysis.py"])
        self.assertIn('echo "[prepare] launching prepare_build.py"', api_launchers["prepare_build.sh"])
        self.assertIn('exec python3 "$SCRIPT_DIR/prepare_build.py" "$@"', api_launchers["prepare_build.sh"])
        self.assertIn("echo [prepare] launching prepare_build.py", mfc_launchers["prepare_build.bat"])
        self.assertIn('python "%SCRIPT_DIR%prepare_build.py" %*', mfc_launchers["prepare_build.bat"])
        self.assertIn('echo "[coverity] launching run_coverity.py"', api_launchers["run_coverity.sh"])

    def test_python_script_templates_render_prepare_context_exports(self) -> None:
        api_build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))

        scripts = render_python_scripts(
            api_build,
            prepare_context={
                "variables": {
                    "BITBUCKET_APPLICATION_LINK": "BITBUCKET_SERVER",
                    "currentRepository.linkageMode": "linked",
                }
            },
        )

        self.assertIn("os.environ['BITBUCKET_APPLICATION_LINK'] = 'BITBUCKET_SERVER'", scripts["prepare_build.py"])
        self.assertIn("os.environ['currentRepository.linkageMode'] = 'linked'", scripts["prepare_build.py"])

    def test_sample_inputs_generate_single_specs_project(self) -> None:
        input_root = Path("build_info_json")
        input_files = discover_input_files(input_root)

        builds = [parse_build_definition(path) for path in input_files]
        validate_build_definitions(builds)

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            written_files = write_specs_project(output_root, builds)
            pom_path = output_root / "pom.xml"
            generated_readme_path = output_root / "README.md"
            sample_plan_path = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SampleAppApiPlanSpecs.java"
            )
            coverity_yaml_path = output_root / "coverity" / "sample-app-api" / "coverity.yaml"
            rendered_api_script_path = output_root / "scripts" / "sample-app-api" / "prepare_build.py"
            rendered_api_launcher_path = output_root / "scripts" / "sample-app-api" / "prepare_build.sh"
            rendered_api_bundle_readme_path = output_root / "scripts" / "sample-app-api" / "README.md"
            rendered_api_manifest_path = output_root / "scripts" / "sample-app-api" / "manifest.json"
            rendered_api_summary_path = output_root / "scripts" / "sample-app-api" / "bundle-summary.txt"
            scripts_index_path = output_root / "scripts" / "index.json"
            scripts_index_summary_path = output_root / "scripts" / "index-summary.txt"
            compare_report_path = output_root / "scripts" / "compare-report.txt"
            compare_report_json_path = output_root / "scripts" / "compare-report.json"
            repository_links_path = output_root / "repository-links.json"
            repository_links_summary_path = output_root / "repository-links-summary.txt"
            mfc_plan_path = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SampleAppMfcPlanSpecs.java"
            )
            specs_publisher_path = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SpecsPublisher.java"
            )

            self.assertTrue(any(path.name == "AllPlansRegistry.java" for path in written_files))
            self.assertTrue(pom_path.exists())
            self.assertTrue(generated_readme_path.exists())
            pom = pom_path.read_text(encoding="utf-8")
            generated_readme = generated_readme_path.read_text(encoding="utf-8")
            self.assertIn("<artifactId>bamboo-specs-parent</artifactId>", pom)
            self.assertIn("<artifactId>bamboo-specs</artifactId>", pom)
            self.assertIn("<mainClass>com.example.specs.generated.SpecsPublisher</mainClass>", pom)
            self.assertIn("<cleanupDaemonThreads>false</cleanupDaemonThreads>", pom)
            self.assertIn("## 사전 점검", generated_readme)
            self.assertIn("## 빌드별 런타임 요구사항", generated_readme)
            self.assertIn("scripts/<bundleId>/", generated_readme)
            self.assertIn("system.builder.python", generated_readme)
            self.assertIn("coverity", generated_readme)
            self.assertIn("trigger-plan", generated_readme)
            self.assertIn("sample-app-api", generated_readme)
            self.assertIn("VS2022_ENV", generated_readme)
            self.assertIn("OS별 launcher", generated_readme)
            self.assertTrue(
                (output_root / "src" / "main" / "java" / "com" / "example" / "specs" / "generated").exists()
            )
            sample_plan = sample_plan_path.read_text(encoding="utf-8")
            self.assertIn("@BambooSpec", sample_plan)
            self.assertIn('new Stage("Analysis")', sample_plan)
            self.assertIn('private static final String LINKED_REPOSITORY = "SAMPLE/sample-app-api";', sample_plan)
            self.assertIn(".linkedRepositories(LINKED_REPOSITORY)", sample_plan)
            self.assertIn('Requirement.equals("operating.system", "Linux")', sample_plan)
            self.assertIn('Requirement.exists("system.builder.mvn3.Maven 3")', sample_plan)
            self.assertIn('Requirement.exists("system.builder.python")', sample_plan)
            self.assertIn('pythonScriptTaskShell("prepare_build.py", PREPARE_BUILD_SCRIPT, "python3")', sample_plan)
            self.assertIn('private static final String PREPARE_BUILD_SCRIPT = """', sample_plan)
            self.assertIn("command = 'mvn -B dependency:go-offline'", sample_plan)
            self.assertIn('cat <<\'__BAMBOO_SPEC_PY__\' > " + SCRIPT_DIRECTORY + "/" + scriptName', sample_plan)
            self.assertIn("new VcsCheckoutTask().addCheckoutOfDefaultRepository()", sample_plan)
            self.assertTrue(coverity_yaml_path.exists())
            self.assertTrue(rendered_api_script_path.exists())
            self.assertTrue(rendered_api_launcher_path.exists())
            self.assertTrue(rendered_api_bundle_readme_path.exists())
            self.assertTrue(rendered_api_manifest_path.exists())
            self.assertTrue(rendered_api_summary_path.exists())
            self.assertTrue(scripts_index_path.exists())
            self.assertTrue(scripts_index_summary_path.exists())
            self.assertTrue(compare_report_path.exists())
            self.assertTrue(compare_report_json_path.exists())
            self.assertTrue(repository_links_path.exists())
            self.assertTrue(repository_links_summary_path.exists())
            self.assertIn("mvn -B dependency:go-offline", rendered_api_script_path.read_text(encoding="utf-8"))
            self.assertIn("BUILD_KEY =", rendered_api_script_path.read_text(encoding="utf-8"))
            self.assertIn('"buildKey": BUILD_KEY', rendered_api_script_path.read_text(encoding="utf-8"))
            self.assertIn('echo "[prepare] launching prepare_build.py"', rendered_api_launcher_path.read_text(encoding="utf-8"))
            self.assertIn('exec python3 "$SCRIPT_DIR/prepare_build.py" "$@"', rendered_api_launcher_path.read_text(encoding="utf-8"))
            bundle_readme = rendered_api_bundle_readme_path.read_text(encoding="utf-8")
            self.assertIn("# Script Bundle: sample-app-api", bundle_readme)
            self.assertIn("prepare_build", bundle_readme)
            self.assertIn("launcher `prepare_build.sh`", bundle_readme)
            self.assertIn("Working subPath: `services/sample-app-api`", bundle_readme)
            self.assertIn("## 저장소 연결", bundle_readme)
            self.assertIn("Linkage mode: `linked`", bundle_readme)
            self.assertIn("Bamboo application link: `BITBUCKET_SERVER`", bundle_readme)
            self.assertIn("Branch trigger policy: dev(order=1, enabled=true), release(order=2, enabled=true), master(order=3, enabled=true)", bundle_readme)
            self.assertIn("Branch matching pattern: `^(dev|release|master)$`", bundle_readme)
            manifest = json.loads(rendered_api_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("sample-app-api", manifest["buildId"])
            self.assertTrue(manifest["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, manifest["generatorVersion"])
            self.assertEqual(self._expected_source_revision(), manifest["sourceRevision"])
            self.assertEqual("python3", manifest["pythonCommand"])
            self.assertEqual("services/sample-app-api", manifest["workingSubPath"])
            self.assertEqual("linked", manifest["repository"]["linkageMode"])
            self.assertEqual("BITBUCKET_SERVER", manifest["repository"]["applicationLink"])
            self.assertEqual(["dev", "release", "master"], manifest["repository"]["branches"])
            self.assertEqual(
                [
                    {"branch": "dev", "order": 1, "enabled": True},
                    {"branch": "release", "order": 2, "enabled": True},
                    {"branch": "master", "order": 3, "enabled": True},
                ],
                manifest["repository"]["branchTriggerPolicy"],
            )
            self.assertEqual("^(dev|release|master)$", manifest["repository"]["branchMatchingPattern"])
            self.assertFalse(manifest["repository"]["requiresRepositoryRegistration"])
            prepare_task = next(task for task in manifest["tasks"] if task["taskName"] == "prepare_build")
            self.assertEqual("prepare_build.py", prepare_task["pythonScript"])
            self.assertEqual("prepare_build.sh", prepare_task["launcherScript"])
            self.assertEqual(
                "scripts/plan_tasks/common/py/prepare_build.py",
                prepare_task["assetSources"]["pythonScript"]["template"],
            )
            self.assertEqual(
                "scripts/plan_tasks/fragments/py/basic_command_support.py",
                prepare_task["assetSources"]["pythonScript"]["commandSupport"],
            )
            self.assertEqual(
                "scripts/plan_tasks/fragments/py/execution_support.py",
                prepare_task["assetSources"]["pythonScript"]["executionSupport"],
            )
            self.assertEqual(
                "scripts/plan_tasks/overlays/task/prepare_build/sh/python_task_launcher.sh",
                prepare_task["assetSources"]["launcherScript"],
            )
            self.assertEqual(64, len(manifest["bundleContentSha256"]))
            self.assertEqual(64, len(manifest["bundleSha256"]))
            self.assertEqual(64, len(prepare_task["checksums"]["pythonScriptSha256"]))
            self.assertEqual(64, len(prepare_task["checksums"]["launcherScriptSha256"]))
            bundle_summary = rendered_api_summary_path.read_text(encoding="utf-8")
            self.assertIn("buildId=sample-app-api", bundle_summary)
            self.assertIn("bundleContentSha256=", bundle_summary)
            self.assertIn("bundleSha256=", bundle_summary)
            self.assertIn("repository.linkageMode=linked", bundle_summary)
            self.assertIn("repository.applicationLink=BITBUCKET_SERVER", bundle_summary)
            self.assertIn("repository.branchTriggerPolicy=dev:1:enabled,release:2:enabled,master:3:enabled", bundle_summary)
            self.assertIn("repository.branchMatchingPattern=^(dev|release|master)$", bundle_summary)
            self.assertIn("repository.requiresRegistration=false", bundle_summary)
            self.assertIn("task.prepare_build.pythonScript=prepare_build.py", bundle_summary)
            self.assertIn(
                "task.prepare_build.source.launcher=scripts/plan_tasks/overlays/task/prepare_build/sh/python_task_launcher.sh",
                bundle_summary,
            )
            scripts_index = json.loads(scripts_index_path.read_text(encoding="utf-8"))
            self.assertTrue(scripts_index["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, scripts_index["generatorVersion"])
            self.assertEqual(self._expected_source_revision(), scripts_index["sourceRevision"])
            self.assertEqual(64, len(scripts_index["indexSha256"]))
            sample_bundle = next(bundle for bundle in scripts_index["bundles"] if bundle["buildId"] == "sample-app-api")
            self.assertTrue(sample_bundle["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, sample_bundle["generatorVersion"])
            self.assertEqual(self._expected_source_revision(), sample_bundle["sourceRevision"])
            self.assertEqual("linked", sample_bundle["linkageMode"])
            self.assertEqual("scripts/sample-app-api", sample_bundle["bundlePath"])
            self.assertEqual("scripts/sample-app-api/manifest.json", sample_bundle["bundleManifest"])
            self.assertEqual(manifest["bundleContentSha256"], sample_bundle["bundleContentSha256"])
            self.assertEqual(manifest["bundleSha256"], sample_bundle["bundleSha256"])
            index_summary = scripts_index_summary_path.read_text(encoding="utf-8")
            self.assertIn(f"generatorVersion={__version__}", index_summary)
            self.assertIn(f"sourceRevision={self._expected_source_revision()}", index_summary)
            self.assertIn("indexSha256=", index_summary)
            self.assertIn("bundle.sample-app-api.path=scripts/sample-app-api", index_summary)
            self.assertIn("bundle.sample-app-api.contentSha256=", index_summary)
            self.assertIn("bundle.sample-app-api.sha256=", index_summary)
            self.assertIn("bundle.sample-app-api.linkageMode=linked", index_summary)
            repository_links = json.loads(repository_links_path.read_text(encoding="utf-8"))
            sample_repository_link = next(entry for entry in repository_links["entries"] if entry["buildId"] == "sample-app-api")
            self.assertEqual("linked", sample_repository_link["linkageMode"])
            self.assertEqual("BITBUCKET_SERVER", sample_repository_link["applicationLink"])
            self.assertEqual(["dev", "release", "master"], sample_repository_link["branches"])
            self.assertEqual(
                [
                    {"branch": "dev", "order": 1, "enabled": True},
                    {"branch": "release", "order": 2, "enabled": True},
                    {"branch": "master", "order": 3, "enabled": True},
                ],
                sample_repository_link["branchTriggerPolicy"],
            )
            self.assertEqual("^(dev|release|master)$", sample_repository_link["branchMatchingPattern"])
            self.assertFalse(sample_repository_link["requiresRepositoryRegistration"])
            repository_links_summary = repository_links_summary_path.read_text(encoding="utf-8")
            self.assertIn("repository.linkageMode=linked", repository_links_summary)
            self.assertIn("repository.applicationLink=BITBUCKET_SERVER", repository_links_summary)
            self.assertIn("repository.branchTriggerPolicy=dev:1:enabled,release:2:enabled,master:3:enabled", repository_links_summary)
            self.assertIn("repository.branchMatchingPattern=^(dev|release|master)$", repository_links_summary)
            self.assertIn("repository.requiresRegistration=false", repository_links_summary)
            compare_report = compare_report_path.read_text(encoding="utf-8")
            self.assertIn("baseline=none", compare_report)
            self.assertIn("status=initial-generation", compare_report)
            compare_report_json = json.loads(compare_report_json_path.read_text(encoding="utf-8"))
            self.assertEqual("none", compare_report_json["baseline"])
            self.assertEqual("initial-generation", compare_report_json["status"])
            self.assertEqual(__version__, compare_report_json["current"]["generatorVersion"])
            self.assertIn(
                'build-command: "mvn -B clean package"',
                coverity_yaml_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(mfc_plan_path.exists())
            mfc_plan = mfc_plan_path.read_text(encoding="utf-8")
            self.assertIn("@BambooSpec", mfc_plan)
            self.assertIn('Requirement.exists("system.builder.visualstudio.2022")', mfc_plan)
            self.assertIn('Requirement.exists("system.builder.nuget")', mfc_plan)
            self.assertIn('Requirement.exists("system.builder.python")', mfc_plan)
            self.assertIn('private static final String LINKED_REPOSITORY = "SAMPLE/sample-app-mfc";', mfc_plan)
            self.assertIn('private static final String REPOSITORY_LINKAGE_MODE = "linked";', mfc_plan)
            self.assertIn('private static final String[] REPOSITORY_BRANCHES = new String[] {"dev", "release", "master"};', mfc_plan)
            self.assertIn(
                'private static final String[] REPOSITORY_BRANCH_TRIGGER_POLICY = new String[] {"dev:1:enabled", "release:2:enabled", "master:3:enabled"};',
                mfc_plan,
            )
            self.assertIn('private static final String REPOSITORY_BRANCH_MATCHING_PATTERN = "^(dev|release|master)$";', mfc_plan)
            self.assertIn("// Branch trigger policy: dev(order=1, enabled=true), release(order=2, enabled=true), master(order=3, enabled=true)", mfc_plan)
            self.assertIn('private static final String BITBUCKET_APPLICATION_LINK = "BITBUCKET_SERVER";', mfc_plan)
            self.assertIn(".planBranchManagement(planBranchManagement())", mfc_plan)
            self.assertIn(".triggers(repositoryTrigger())", mfc_plan)
            self.assertIn(".linkedRepositories(LINKED_REPOSITORY)", mfc_plan)
            self.assertIn('new PlanBranchManagement()', mfc_plan)
            self.assertIn('.createForVcsBranchMatching(REPOSITORY_BRANCH_MATCHING_PATTERN);', mfc_plan)
            self.assertIn('private BitbucketServerTrigger repositoryTrigger() {', mfc_plan)
            self.assertIn("return new BitbucketServerTrigger();", mfc_plan)
            self.assertIn('pythonScriptTaskCmdExe("prepare_build.py", PREPARE_BUILD_SCRIPT, "python")', mfc_plan)
            self.assertIn('private static final String PREPARE_BUILD_SCRIPT = """', mfc_plan)
            self.assertIn("command = 'nuget restore SampleAppMfc.sln'", mfc_plan)
            self.assertIn('powershell -NoProfile -Command ^', mfc_plan)
            self.assertIn('"   $path = Join-Path $scriptDir \'" + scriptName + "\'; ^"', mfc_plan)
            self.assertTrue(specs_publisher_path.exists())
            specs_publisher = specs_publisher_path.read_text(encoding="utf-8")
            self.assertIn("BambooServer", specs_publisher)
            self.assertIn("FileTokenCredentials", specs_publisher)
            self.assertIn('Arrays.asList(args).contains("--dry-run")', specs_publisher)
            self.assertIn('Arrays.asList(args).contains("--print-plans")', specs_publisher)
            self.assertIn('System.out.println("DRY RUN: " + plan.toString());', specs_publisher)
            self.assertIn("server.publish(plan);", specs_publisher)

    def test_write_specs_project_groups_multiple_builds_into_single_plan(self) -> None:
        api_build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        composite_linux = replace(
            api_build,
            build_key="main",
            name="Sample API main",
            language="python",
            compiler="python",
            build=replace(api_build.build, prepare_command="", build_command=""),
        )
        composite_windows = replace(
            api_build,
            build_key="sub",
            name="Sample API sub",
            language="javascript",
            compiler="node.js",
            requirements=replace(api_build.requirements, os="windows"),
            build=replace(api_build.build, prepare_command="", build_command="npm build"),
        )

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(output_root, [composite_linux, composite_windows])

            grouped_plan = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SampleAppApiPlanSpecs.java"
            ).read_text(encoding="utf-8")
            registry = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "AllPlansRegistry.java"
            ).read_text(encoding="utf-8")

            self.assertIn('new Stage("Analysis")', grouped_plan)
            self.assertIn('new Job("sub Build", "BLD1")', grouped_plan)
            self.assertIn('new Job("main Analysis", "ANL1")', grouped_plan)
            self.assertIn('new Job("sub Analysis", "ANL2")', grouped_plan)
            self.assertIn('pythonScriptTaskCmdExe("run_build.py", RUN_BUILD_SCRIPT_SUB, "python")', grouped_plan)
            self.assertIn('pythonScriptTaskCmdExe("run_coverity.py", RUN_COVERITY_SCRIPT_SUB, "python")', grouped_plan)
            self.assertIn('pythonScriptTaskShell("run_coverity.py", RUN_COVERITY_SCRIPT_MAIN, "python3")', grouped_plan)
            self.assertEqual(1, registry.count("new SampleAppApiPlanSpecs().plan()"))

    def test_create_if_missing_outputs_repository_tracking_metadata(self) -> None:
        build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        build = replace(
            build,
            repository=replace(
                build.repository,
                linkage_mode="create_if_missing",
                application_link="BITBUCKET_DC",
                branches=["release", "dev", "master"],
            ),
        )

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(output_root, [build])

            manifest = json.loads((output_root / "scripts" / build.build_id / "manifest.json").read_text(encoding="utf-8"))
            repository_links = json.loads((output_root / "repository-links.json").read_text(encoding="utf-8"))
            plan_java = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SampleAppApiPlanSpecs.java"
            ).read_text(encoding="utf-8")

            self.assertEqual("create_if_missing", manifest["repository"]["linkageMode"])
            self.assertEqual("BITBUCKET_DC", manifest["repository"]["applicationLink"])
            self.assertEqual(["release", "dev", "master"], manifest["repository"]["branches"])
            self.assertEqual(
                [
                    {"branch": "release", "order": 1, "enabled": True},
                    {"branch": "dev", "order": 2, "enabled": True},
                    {"branch": "master", "order": 3, "enabled": True},
                ],
                manifest["repository"]["branchTriggerPolicy"],
            )
            self.assertEqual("^(release|dev|master)$", manifest["repository"]["branchMatchingPattern"])
            self.assertTrue(manifest["repository"]["requiresRepositoryRegistration"])
            self.assertEqual("create_if_missing", repository_links["entries"][0]["linkageMode"])
            self.assertEqual("BITBUCKET_DC", repository_links["entries"][0]["applicationLink"])
            self.assertEqual(
                [
                    {"branch": "release", "order": 1, "enabled": True},
                    {"branch": "dev", "order": 2, "enabled": True},
                    {"branch": "master", "order": 3, "enabled": True},
                ],
                repository_links["entries"][0]["branchTriggerPolicy"],
            )
            self.assertEqual("^(release|dev|master)$", repository_links["entries"][0]["branchMatchingPattern"])
            self.assertTrue(repository_links["entries"][0]["requiresRepositoryRegistration"])
            self.assertIn("// Repository linkage mode: create_if_missing", plan_java)
            self.assertIn("// create_if_missing uses Bamboo application link: BITBUCKET_DC", plan_java)
            self.assertIn("// Repository branches: release, dev, master", plan_java)
            self.assertIn("// Branch trigger policy: release(order=1, enabled=true), dev(order=2, enabled=true), master(order=3, enabled=true)", plan_java)
            self.assertIn(
                'private static final String[] REPOSITORY_BRANCH_TRIGGER_POLICY = new String[] {"release:1:enabled", "dev:2:enabled", "master:3:enabled"};',
                plan_java,
            )
            self.assertIn('private static final String REPOSITORY_BRANCH_MATCHING_PATTERN = "^(release|dev|master)$";', plan_java)
            self.assertIn('private static final String BITBUCKET_APPLICATION_LINK = "BITBUCKET_DC";', plan_java)
            self.assertIn('.createForVcsBranchMatching(REPOSITORY_BRANCH_MATCHING_PATTERN);', plan_java)
            self.assertIn(".triggers(repositoryTrigger())", plan_java)
            self.assertIn(".planRepositories(createBitbucketPlanRepository())", plan_java)
            self.assertIn("private BitbucketServerRepository createBitbucketPlanRepository() {", plan_java)
            self.assertIn('.server(new ApplicationLink().name(BITBUCKET_APPLICATION_LINK))', plan_java)
            self.assertIn('.projectKey("SAMPLE")', plan_java)
            self.assertIn('.repositorySlug("sample-app-api")', plan_java)
            self.assertIn('.branch("release");', plan_java)

    def test_create_if_missing_supports_git_clone_url_fallback(self) -> None:
        build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        build = replace(
            build,
            repository=replace(
                build.repository,
                linkage_mode="create_if_missing",
                application_link=None,
                clone_url="https://git.example.com/scm/sample/sample-app-api.git",
            ),
        )

        validate_build_definitions([build])

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(output_root, [build])
            plan_java = (
                output_root
                / "src"
                / "main"
                / "java"
                / "com"
                / "example"
                / "specs"
                / "generated"
                / "SampleAppApiPlanSpecs.java"
            ).read_text(encoding="utf-8")
            manifest = json.loads((output_root / "scripts" / "sample-app-api" / "manifest.json").read_text(encoding="utf-8"))

            self.assertIn('private static final String GIT_CLONE_URL = "https://git.example.com/scm/sample/sample-app-api.git";', plan_java)
            self.assertIn(".planRepositories(createGitPlanRepository())", plan_java)
            self.assertIn("private GitRepository createGitPlanRepository() {", plan_java)
            self.assertIn('.url(GIT_CLONE_URL)', plan_java)
            self.assertEqual("https://git.example.com/scm/sample/sample-app-api.git", manifest["repository"]["cloneUrl"])

    def test_create_if_missing_requires_application_link_or_clone_url(self) -> None:
        build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))
        build = replace(
            build,
            repository=replace(
                build.repository,
                linkage_mode="create_if_missing",
                application_link=None,
                clone_url=None,
            ),
        )

        with self.assertRaises(ValidationError) as context:
            validate_build_definitions([build])

        self.assertIn("repository.applicationLink or repository.cloneUrl", str(context.exception))

    def test_compare_report_detects_changed_bundle_on_regeneration(self) -> None:
        input_root = Path("build_info_json")
        input_files = discover_input_files(input_root)
        builds = [parse_build_definition(path) for path in input_files]
        validate_build_definitions(builds)

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(output_root, builds)

            api_build = next(build for build in builds if build.build_id == "sample-app-api")
            updated_api_build = replace(
                api_build,
                build=replace(api_build.build, prepare_command="mvn -B -U dependency:go-offline"),
            )
            updated_builds = [
                updated_api_build if build.build_id == "sample-app-api" else build
                for build in builds
            ]

            write_specs_project(output_root, updated_builds)
            compare_report = (output_root / "scripts" / "compare-report.txt").read_text(encoding="utf-8")
            compare_report_json = json.loads((output_root / "scripts" / "compare-report.json").read_text(encoding="utf-8"))
            self.assertIn("baseline=existing-output", compare_report)
            self.assertIn("bundle.sample-app-api.status=changed", compare_report)
            self.assertIn("bundle.sample-app-mfc.status=unchanged", compare_report)
            self.assertIn("bundle.sample-app-api.previousContentSha256=", compare_report)
            self.assertIn("bundle.sample-app-api.currentContentSha256=", compare_report)
            self.assertIn("bundle.sample-app-api.task.prepare_build.status=changed", compare_report)
            self.assertIn("bundle.sample-app-api.task.prepare_build.pythonScript.changed=true", compare_report)
            self.assertNotIn("bundle.sample-app-api.task.run_build.status=changed", compare_report)
            self.assertEqual("existing-output", compare_report_json["baseline"])
            changed_bundle = next(bundle for bundle in compare_report_json["bundles"] if bundle["buildId"] == "sample-app-api")
            self.assertEqual("changed", changed_bundle["status"])
            changed_task = next(task for task in changed_bundle["taskChanges"] if task["taskName"] == "prepare_build")
            self.assertIn("pythonScriptChanged", changed_task)

    def test_compare_report_detects_runtime_requirement_change(self) -> None:
        input_root = Path("build_info_json")
        input_files = discover_input_files(input_root)
        builds = [parse_build_definition(path) for path in input_files]
        validate_build_definitions(builds)

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(output_root, builds)

            api_build = next(build for build in builds if build.build_id == "sample-app-api")
            updated_api_build = replace(
                api_build,
                build=replace(
                    api_build.build,
                    runtime_requirements=replace(
                        api_build.build.runtime_requirements,
                        env_vars=["PATH", "JAVA_HOME"],
                    ),
                ),
            )
            updated_builds = [
                updated_api_build if build.build_id == "sample-app-api" else build
                for build in builds
            ]

            write_specs_project(output_root, updated_builds)
            compare_report = (output_root / "scripts" / "compare-report.txt").read_text(encoding="utf-8")
            compare_report_json = json.loads((output_root / "scripts" / "compare-report.json").read_text(encoding="utf-8"))
            self.assertIn("bundle.sample-app-api.status=changed", compare_report)
            self.assertIn("bundle.sample-app-api.runtime.envVars.changed=true", compare_report)
            self.assertIn("bundle.sample-app-api.runtime.envVars.previous=PATH", compare_report)
            self.assertIn("bundle.sample-app-api.runtime.envVars.current=PATH,JAVA_HOME", compare_report)
            changed_bundle = next(bundle for bundle in compare_report_json["bundles"] if bundle["buildId"] == "sample-app-api")
            self.assertEqual(
                {"previous": ["PATH"], "current": ["PATH", "JAVA_HOME"]},
                changed_bundle["bundleChanges"]["runtimeEnvVars"],
            )

    def test_write_specs_project_records_prepare_context_artifacts(self) -> None:
        build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            write_specs_project(
                output_root,
                [build],
                prepare_contexts={
                    build.plan_key: {
                        "planKey": build.plan_key,
                        "variables": {
                            "BITBUCKET_APPLICATION_LINK": "BITBUCKET_SERVER",
                            "currentRepository.linkageMode": "linked",
                        },
                    }
                },
            )

            prepare_script = (output_root / "scripts" / build.build_id / "prepare_build.py").read_text(encoding="utf-8")
            prepare_context = json.loads(
                (output_root / "scripts" / build.build_id / "prepare-context.json").read_text(encoding="utf-8")
            )
            manifest = json.loads((output_root / "scripts" / build.build_id / "manifest.json").read_text(encoding="utf-8"))
            summary = (output_root / "scripts" / build.build_id / "bundle-summary.txt").read_text(encoding="utf-8")

            self.assertIn("os.environ['BITBUCKET_APPLICATION_LINK'] = 'BITBUCKET_SERVER'", prepare_script)
            self.assertEqual("BITBUCKET_SERVER", prepare_context["variables"]["BITBUCKET_APPLICATION_LINK"])
            self.assertEqual(
                {
                    "planKey": build.plan_key,
                    "variables": {
                        "BITBUCKET_APPLICATION_LINK": "BITBUCKET_SERVER",
                        "currentRepository.linkageMode": "linked",
                    },
                },
                manifest["prepareContext"],
            )
            self.assertIn(
                "prepareContext.variables=BITBUCKET_APPLICATION_LINK,currentRepository.linkageMode",
                summary,
            )


if __name__ == "__main__":
    unittest.main()
