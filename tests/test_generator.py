from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.bamboo_spec_generator.parser import discover_input_files, parse_build_definition
from src.bamboo_spec_generator.validator import validate_build_definitions
from src.bamboo_spec_generator.writer import write_specs_project


class GeneratorFlowTest(unittest.TestCase):
    def test_sample_inputs_generate_single_specs_project(self) -> None:
        input_root = Path("build_info_json")
        input_files = discover_input_files(input_root)

        builds = [parse_build_definition(path) for path in input_files]
        validate_build_definitions(builds)

        with TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "bamboo-specs"
            written_files = write_specs_project(output_root, builds)
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
            prepare_script_path = output_root / "scripts" / "generated" / "sample-app-api" / "prepare_build.py"
            api_coverity_script_path = output_root / "scripts" / "generated" / "sample-app-api" / "run_coverity.py"
            api_custom_analysis_path = output_root / "scripts" / "generated" / "sample-app-api" / "run_custom_analysis.py"
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
            mfc_run_build_path = output_root / "scripts" / "generated" / "sample-app-mfc" / "run_build.py"
            mfc_prepare_path = output_root / "scripts" / "generated" / "sample-app-mfc" / "prepare_build.py"
            mfc_custom_analysis_path = output_root / "scripts" / "generated" / "sample-app-mfc" / "run_custom_analysis.py"

            self.assertTrue(any(path.name == "AllPlansRegistry.java" for path in written_files))
            self.assertTrue(
                (output_root / "src" / "main" / "java" / "com" / "example" / "specs" / "generated").exists()
            )
            sample_plan = sample_plan_path.read_text(encoding="utf-8")
            self.assertIn('new Stage("Static Analysis")', sample_plan)
            self.assertIn('Requirement.equals("operating.system", "Linux")', sample_plan)
            self.assertIn('Requirement.exists("system.builder.mvn3.Maven 3")', sample_plan)
            self.assertIn('Requirement.exists("system.cuda.12.1")', sample_plan)
            self.assertIn('.fileFromPath(SCRIPT_ROOT + "/run_coverity.py")', sample_plan)
            self.assertIn('.fileFromPath(SCRIPT_ROOT + "/run_custom_analysis.py")', sample_plan)
            self.assertTrue(coverity_yaml_path.exists())
            self.assertIn(
                'build-command: "python scripts/run_build.py --tool maven --goal package"',
                coverity_yaml_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(prepare_script_path.exists())
            prepare_script = prepare_script_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('services/sample-app-api')", prepare_script)
            self.assertIn("import shlex", prepare_script)
            self.assertIn("shlex.split(command, posix=os.name != \"nt\")", prepare_script)
            self.assertTrue(api_coverity_script_path.exists())
            api_coverity_script = api_coverity_script_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('services/sample-app-api')", api_coverity_script)
            self.assertIn('CONFIG_PATH = REPOSITORY_ROOT / "coverity" / "sample-app-api" / "coverity.yaml"', api_coverity_script)
            self.assertIn("cwd=WORKING_DIRECTORY", api_coverity_script)
            self.assertTrue(api_custom_analysis_path.exists())
            api_custom_analysis = api_custom_analysis_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('services/sample-app-api')", api_custom_analysis)
            self.assertIn("cwd=WORKING_DIRECTORY", api_custom_analysis)
            self.assertTrue(mfc_plan_path.exists())
            self.assertIn(
                'Requirement.exists("system.builder.visualstudio.2022")',
                mfc_plan_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(mfc_run_build_path.exists())
            mfc_run_build = mfc_run_build_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('src/SampleAppMfc')", mfc_run_build)
            self.assertIn('(WORKING_DIRECTORY / "Directory.Build.targets").write_text', mfc_run_build)
            self.assertIn("<Optimization>Disabled</Optimization>", mfc_run_build)
            self.assertIn("<WholeProgramOptimization>false</WholeProgramOptimization>", mfc_run_build)
            self.assertIn('env_var_name = "VS2022_ENV"', mfc_run_build)
            self.assertIn('return ["cmd.exe", "/d", "/s", "/c", f\'call "{vcvars_path}" && {command}\']', mfc_run_build)
            self.assertIn("return run_command(command)", mfc_run_build)
            self.assertTrue(mfc_prepare_path.exists())
            mfc_prepare = mfc_prepare_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('src/SampleAppMfc')", mfc_prepare)
            self.assertIn('env_var_name = "VS2022_ENV"', mfc_prepare)
            self.assertIn("return run_command(command)", mfc_prepare)
            self.assertTrue(mfc_custom_analysis_path.exists())
            mfc_custom_analysis = mfc_custom_analysis_path.read_text(encoding="utf-8")
            self.assertIn("WORKING_DIRECTORY = Path('src/SampleAppMfc')", mfc_custom_analysis)
            self.assertIn('env_var_name = "VS2022_ENV"', mfc_custom_analysis)
            self.assertIn('(WORKING_DIRECTORY / "Directory.Build.targets").write_text', mfc_custom_analysis)
            self.assertIn("result = run_command(command)", mfc_custom_analysis)


if __name__ == "__main__":
    unittest.main()
