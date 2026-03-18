from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
import json
import unittest

from src.bamboo_spec_generator import __version__
from src.bamboo_spec_generator.parser import discover_input_files, parse_build_definition
from src.bamboo_spec_generator.java_assets import load_python_wrapper_method
from src.bamboo_spec_generator.script_assets import load_python_script_assets
from src.bamboo_spec_generator.script_renderer import render_python_launcher_scripts, render_python_scripts
from src.bamboo_spec_generator.validator import validate_build_definitions
from src.bamboo_spec_generator.writer import write_specs_project


class GeneratorFlowTest(unittest.TestCase):
    EXPECTED_SOURCE_REVISION = "70ce5ed87ee42c082b186979db11d496b6f7a31f"

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
        self.assertIn("command = 'mvn -B clean package'", api_scripts["run_build.py"])
        self.assertIn("'custom-tool analyze mvn -B clean package',", api_scripts["run_custom_analysis.py"])
        self.assertIn("Path('src/SampleAppMfc')", mfc_scripts["prepare_build.py"])
        self.assertIn("VS2022_ENV", mfc_scripts["run_build.py"])
        self.assertIn("Directory.Build.targets", mfc_scripts["run_custom_analysis.py"])
        self.assertIn('echo "[prepare] launching prepare_build.py"', api_launchers["prepare_build.sh"])
        self.assertIn('exec python3 "$SCRIPT_DIR/prepare_build.py" "$@"', api_launchers["prepare_build.sh"])
        self.assertIn("echo [prepare] launching prepare_build.py", mfc_launchers["prepare_build.bat"])
        self.assertIn('python "%SCRIPT_DIR%prepare_build.py" %*', mfc_launchers["prepare_build.bat"])
        self.assertIn('echo "[coverity] launching run_coverity.py"', api_launchers["run_coverity.sh"])

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
            self.assertIn("## 사전 점검", generated_readme)
            self.assertIn("## 빌드별 런타임 요구사항", generated_readme)
            self.assertIn("scripts/<buildId>/", generated_readme)
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
            self.assertIn('new Stage("Static Analysis")', sample_plan)
            self.assertIn('private static final String LINKED_REPOSITORY = "SAMPLE/sample-app-api";', sample_plan)
            self.assertIn(".linkedRepositories(LINKED_REPOSITORY)", sample_plan)
            self.assertIn('Requirement.equals("operating.system", "Linux")', sample_plan)
            self.assertIn('Requirement.exists("system.builder.mvn3.Maven 3")', sample_plan)
            self.assertIn('Requirement.exists("system.builder.python")', sample_plan)
            self.assertIn('pythonScriptTask("prepare_build.py", PREPARE_BUILD_SCRIPT)', sample_plan)
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
            self.assertIn("mvn -B dependency:go-offline", rendered_api_script_path.read_text(encoding="utf-8"))
            self.assertIn('echo "[prepare] launching prepare_build.py"', rendered_api_launcher_path.read_text(encoding="utf-8"))
            self.assertIn('exec python3 "$SCRIPT_DIR/prepare_build.py" "$@"', rendered_api_launcher_path.read_text(encoding="utf-8"))
            bundle_readme = rendered_api_bundle_readme_path.read_text(encoding="utf-8")
            self.assertIn("# Script Bundle: sample-app-api", bundle_readme)
            self.assertIn("prepare_build", bundle_readme)
            self.assertIn("launcher `prepare_build.sh`", bundle_readme)
            self.assertIn("Working subPath: `services/sample-app-api`", bundle_readme)
            manifest = json.loads(rendered_api_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("sample-app-api", manifest["buildId"])
            self.assertTrue(manifest["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, manifest["generatorVersion"])
            self.assertEqual(self.EXPECTED_SOURCE_REVISION, manifest["sourceRevision"])
            self.assertEqual("python3", manifest["pythonCommand"])
            self.assertEqual("services/sample-app-api", manifest["workingSubPath"])
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
            self.assertIn("task.prepare_build.pythonScript=prepare_build.py", bundle_summary)
            self.assertIn(
                "task.prepare_build.source.launcher=scripts/plan_tasks/overlays/task/prepare_build/sh/python_task_launcher.sh",
                bundle_summary,
            )
            scripts_index = json.loads(scripts_index_path.read_text(encoding="utf-8"))
            self.assertTrue(scripts_index["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, scripts_index["generatorVersion"])
            self.assertEqual(self.EXPECTED_SOURCE_REVISION, scripts_index["sourceRevision"])
            self.assertEqual(64, len(scripts_index["indexSha256"]))
            sample_bundle = next(bundle for bundle in scripts_index["bundles"] if bundle["buildId"] == "sample-app-api")
            self.assertTrue(sample_bundle["generatedAtUtc"].endswith("Z"))
            self.assertEqual(__version__, sample_bundle["generatorVersion"])
            self.assertEqual(self.EXPECTED_SOURCE_REVISION, sample_bundle["sourceRevision"])
            self.assertEqual("scripts/sample-app-api", sample_bundle["bundlePath"])
            self.assertEqual("scripts/sample-app-api/manifest.json", sample_bundle["bundleManifest"])
            self.assertEqual(manifest["bundleContentSha256"], sample_bundle["bundleContentSha256"])
            self.assertEqual(manifest["bundleSha256"], sample_bundle["bundleSha256"])
            index_summary = scripts_index_summary_path.read_text(encoding="utf-8")
            self.assertIn(f"generatorVersion={__version__}", index_summary)
            self.assertIn(f"sourceRevision={self.EXPECTED_SOURCE_REVISION}", index_summary)
            self.assertIn("indexSha256=", index_summary)
            self.assertIn("bundle.sample-app-api.path=scripts/sample-app-api", index_summary)
            self.assertIn("bundle.sample-app-api.contentSha256=", index_summary)
            self.assertIn("bundle.sample-app-api.sha256=", index_summary)
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
            self.assertIn(".linkedRepositories(LINKED_REPOSITORY)", mfc_plan)
            self.assertIn('pythonScriptTask("prepare_build.py", PREPARE_BUILD_SCRIPT)', mfc_plan)
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


if __name__ == "__main__":
    unittest.main()
