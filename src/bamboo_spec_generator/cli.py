from __future__ import annotations

import argparse
from pathlib import Path

from .parser import discover_input_files, parse_build_definition
from .validator import ValidationError, validate_build_definitions
from .writer import write_specs_project


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate sample Bamboo Specs Java sources.")
    parser.add_argument(
        "--input-root",
        default="build_info_json",
        help="연도별 빌드 JSON 파일이 저장된 루트 디렉터리",
    )
    parser.add_argument(
        "--output-root",
        default="bamboo-specs",
        help="생성된 Bamboo Specs 샘플 프로젝트 출력 디렉터리",
    )
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()
    input_root = Path(args.input_root)
    output_root = Path(args.output_root)

    input_files = discover_input_files(input_root)
    if not input_files:
        print(f"No JSON input files found under: {input_root}")
        return 1

    builds = [parse_build_definition(path) for path in input_files]

    try:
        validate_build_definitions(builds)
    except ValidationError as error:
        print(f"Validation failed: {error}")
        return 1

    written_files = write_specs_project(output_root, builds)
    print(f"Processed {len(builds)} build definitions from {len(input_files)} files.")
    print(f"Generated {len(written_files)} files under: {output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
