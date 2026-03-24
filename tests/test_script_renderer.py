from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from src.bamboo_spec_generator.parser import parse_build_definition
from src.bamboo_spec_generator.script_renderer import ScriptRenderError, render_python_scripts


class ScriptRendererTest(unittest.TestCase):
    def test_render_python_scripts_raises_when_placeholder_remains(self) -> None:
        build = parse_build_definition(Path("build_info_json/2026/sample-app-api.json"))

        with patch(
            "src.bamboo_spec_generator.script_renderer.load_python_script_assets",
            return_value={"broken.py": "value {{MISSING}}"},
        ):
            with self.assertRaises(ScriptRenderError):
                render_python_scripts(build)
