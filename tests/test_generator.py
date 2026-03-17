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
            self.assertIn("import shlex", prepare_script)
            self.assertIn("shlex.split(command, posix=os.name != \"nt\")", prepare_script)


if __name__ == "__main__":
    unittest.main()
