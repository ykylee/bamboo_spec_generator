from __future__ import annotations

from apps.buildmeta.models import BambooBuildInfo, BambooBuildUnit


def upsert_build_info(
    *,
    plan_key: str,
    build_key: str,
    operating_system: str,
    pre_process: str,
    build_command: str,
    clean_command: str,
    language: str,
    compiler: str,
    analysis_excluded_files: str,
    coverity_stream: str,
    build_sub_path: str,
) -> BambooBuildInfo | None:
    bamboo_unit = BambooBuildUnit.objects.filter(plan_key=plan_key).first()
    if bamboo_unit is None:
        return None

    build_info, _ = BambooBuildInfo.objects.update_or_create(
        bamboo_build_unit=bamboo_unit,
        build_key=build_key.strip(),
        defaults={
            "operating_system": operating_system.strip(),
            "pre_process": pre_process.strip(),
            "build_command": build_command.strip(),
            "clean_command": clean_command.strip(),
            "language": language.strip(),
            "compiler": compiler.strip(),
            "analysis_excluded_files": analysis_excluded_files.strip(),
            "coverity_stream": coverity_stream.strip(),
            "build_sub_path": build_sub_path.strip(),
        },
    )
    return build_info
