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
            self.assertIn("system.builder.python", generated_readme)
            self.assertIn("coverity", generated_readme)
            self.assertIn("trigger-plan", generated_readme)
            self.assertIn("sample-app-api", generated_readme)
            self.assertIn("VS2022_ENV", generated_readme)
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
            self.assertIn('.inlineBody("python3 -c \\"import base64;exec(base64.b64decode(', sample_plan)
            self.assertIn("new VcsCheckoutTask().addCheckoutOfDefaultRepository()", sample_plan)
            self.assertTrue(coverity_yaml_path.exists())
            self.assertIn(
                'build-command: "mvn -B clean package"',
                coverity_yaml_path.read_text(encoding="utf-8"),
            )
            self.assertFalse((output_root / "scripts").exists())
            self.assertTrue(mfc_plan_path.exists())
            mfc_plan = mfc_plan_path.read_text(encoding="utf-8")
            self.assertIn("@BambooSpec", mfc_plan)
            self.assertIn('Requirement.exists("system.builder.visualstudio.2022")', mfc_plan)
            self.assertIn('Requirement.exists("system.builder.nuget")', mfc_plan)
            self.assertIn('Requirement.exists("system.builder.python")', mfc_plan)
            self.assertIn('private static final String LINKED_REPOSITORY = "SAMPLE/sample-app-mfc";', mfc_plan)
            self.assertIn(".linkedRepositories(LINKED_REPOSITORY)", mfc_plan)
            self.assertIn('.inlineBody("python -c \\"import base64;exec(base64.b64decode(', mfc_plan)
            self.assertTrue(specs_publisher_path.exists())
            specs_publisher = specs_publisher_path.read_text(encoding="utf-8")
            self.assertIn("BambooServer", specs_publisher)
            self.assertIn("FileTokenCredentials", specs_publisher)
            self.assertIn('Arrays.asList(args).contains("--dry-run")', specs_publisher)
            self.assertIn('Arrays.asList(args).contains("--print-plans")', specs_publisher)
            self.assertIn('System.out.println("DRY RUN: " + plan.toString());', specs_publisher)
            self.assertIn("server.publish(plan);", specs_publisher)


if __name__ == "__main__":
    unittest.main()
