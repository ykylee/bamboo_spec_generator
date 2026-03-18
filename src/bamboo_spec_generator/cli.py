from __future__ import annotations

import argparse
from pathlib import Path

from .api_client import OperationsApiClient, OperationsApiConfig, OperationsApiError
from .parser import discover_input_files, parse_build_definition
from .postgres import PostgresConfig, PostgresError, apply_schema, check_connection
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
    parser.add_argument(
        "--db-check",
        action="store_true",
        help="환경변수 기준 PostgreSQL 연결 상태를 확인한다",
    )
    parser.add_argument(
        "--db-init-schema",
        action="store_true",
        help="설계 문서의 PostgreSQL 스키마 초안을 적용한다",
    )
    parser.add_argument(
        "--api-plan-key",
        help="운영 백엔드 API에서 조회할 대상 Bamboo plan key",
    )
    return parser


def main() -> int:
    args = build_argument_parser().parse_args()

    if args.db_check or args.db_init_schema:
        config = PostgresConfig.from_env()
        try:
            if args.db_check:
                print(f"Checking PostgreSQL connection: {config.masked_dsn()}")
                print(check_connection(config))
            if args.db_init_schema:
                print(f"Applying PostgreSQL schema: {config.masked_dsn()}")
                output = apply_schema(config)
                if output:
                    print(output)
        except PostgresError as error:
            print(f"PostgreSQL operation failed: {error}")
            return 1
        return 0

    if args.api_plan_key:
        output_root = Path(args.output_root)
        try:
            client = OperationsApiClient(OperationsApiConfig.from_env())
            builds = [client.get_build_definition(args.api_plan_key)]
            validate_build_definitions(builds)
        except (OperationsApiError, ValidationError) as error:
            print(f"API generation failed: {error}")
            return 1
        written_files = write_specs_project(output_root, builds)
        print(f"Processed 1 build definition from operations API for plan: {args.api_plan_key}")
        print(f"Generated {len(written_files)} files under: {output_root}")
        return 0

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
