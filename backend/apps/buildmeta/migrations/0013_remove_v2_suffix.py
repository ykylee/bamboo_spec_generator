from django.db import migrations


TABLE_RENAMES = [
    ("buildmeta_project_v2", "buildmeta_project"),
    ("buildmeta_repository_v2", "buildmeta_repository"),
    ("buildmeta_build_unit_v2", "buildmeta_build_unit"),
    ("buildmeta_build_unit_definition_v2", "buildmeta_build_unit_definition"),
    ("buildmeta_build_version_v2", "buildmeta_build_version"),
    ("buildmeta_build_execution_v2", "buildmeta_build_execution"),
    ("buildmeta_execution_artifact_v2", "buildmeta_execution_artifact"),
    ("buildmeta_static_analysis_result_v2", "buildmeta_static_analysis_result"),
    ("buildmeta_deployment_target_v2", "buildmeta_deployment_target"),
    ("buildmeta_deployment_execution_v2", "buildmeta_deployment_execution"),
    ("buildmeta_system_status_snapshot_v2", "buildmeta_system_status_snapshot"),
    ("buildmeta_audit_event_v2", "buildmeta_audit_event"),
    ("buildmeta_bamboo_build_unit_v2", "buildmeta_bamboo_build_unit"),
    ("buildmeta_bamboo_build_info_v2", "buildmeta_bamboo_build_info"),
    ("buildmeta_bamboo_publish_execution_v2", "buildmeta_bamboo_publish_execution"),
    ("buildmeta_jenkins_build_unit_v2", "buildmeta_jenkins_build_unit"),
    ("buildmeta_jenkins_node_snapshot_v2", "buildmeta_jenkins_node_snapshot"),
    ("buildmeta_jenkins_queue_item_snapshot_v2", "buildmeta_jenkins_queue_item_snapshot"),
]


def _drop_table_sql(schema_editor, table_name: str) -> str:
    quoted = schema_editor.quote_name(table_name)
    if schema_editor.connection.vendor == "postgresql":
        return f"DROP TABLE IF EXISTS {quoted} CASCADE"
    return f"DROP TABLE IF EXISTS {quoted}"


def _rename_table_sql(schema_editor, source_table: str, target_table: str) -> str:
    source = schema_editor.quote_name(source_table)
    target = schema_editor.quote_name(target_table)
    return f"ALTER TABLE {source} RENAME TO {target}"


def rename_tables(apps, schema_editor):
    """Replace legacy tables with the v2 schema under the final table names."""
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_keys = OFF")

        try:
            for _, clean_table in reversed(TABLE_RENAMES):
                if clean_table in existing_tables:
                    cursor.execute(_drop_table_sql(schema_editor, clean_table))

            for source_table, target_table in TABLE_RENAMES:
                if source_table in existing_tables:
                    cursor.execute(_rename_table_sql(schema_editor, source_table, target_table))
        finally:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")


def reverse_rename_tables(apps, schema_editor):
    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())

    with connection.cursor() as cursor:
        if connection.vendor == "sqlite":
            cursor.execute("PRAGMA foreign_keys = OFF")

        try:
            for source_table, target_table in reversed(TABLE_RENAMES):
                if target_table in existing_tables:
                    cursor.execute(_rename_table_sql(schema_editor, target_table, source_table))
        finally:
            if connection.vendor == "sqlite":
                cursor.execute("PRAGMA foreign_keys = ON")


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0012_buildunit_v2_models"),
    ]

    operations = [
        migrations.RunPython(rename_tables, reverse_rename_tables),
    ]
