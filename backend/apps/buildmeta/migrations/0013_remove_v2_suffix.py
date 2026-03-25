"""
Migration to remove _v2 suffix from table names.

Since data reset is acceptable, this migration drops the old _v2 tables
and recreates them with clean names.

Tables to be recreated:
- buildmeta_project_v2 -> buildmeta_project
- buildmeta_repository_v2 -> buildmeta_repository
- buildmeta_build_unit_v2 -> buildmeta_build_unit
- buildmeta_build_unit_definition_v2 -> buildmeta_build_unit_definition
- buildmeta_build_version_v2 -> buildmeta_build_version
- buildmeta_build_execution_v2 -> buildmeta_build_execution
- buildmeta_execution_artifact_v2 -> buildmeta_execution_artifact
- buildmeta_static_analysis_result_v2 -> buildmeta_static_analysis_result
- buildmeta_deployment_target_v2 -> buildmeta_deployment_target
- buildmeta_deployment_execution_v2 -> buildmeta_deployment_execution
- buildmeta_system_status_snapshot_v2 -> buildmeta_system_status_snapshot
- buildmeta_audit_event_v2 -> buildmeta_audit_event
- buildmeta_bamboo_build_unit_v2 -> buildmeta_bamboo_build_unit
- buildmeta_bamboo_build_info_v2 -> buildmeta_bamboo_build_info
- buildmeta_bamboo_publish_execution_v2 -> buildmeta_bamboo_publish_execution
- buildmeta_jenkins_build_unit_v2 -> buildmeta_jenkins_build_unit
- buildmeta_jenkins_node_snapshot_v2 -> buildmeta_jenkins_node_snapshot
- buildmeta_jenkins_queue_item_snapshot_v2 -> buildmeta_jenkins_queue_item_snapshot

NOTE: This migration requires a fresh database or data loss is acceptable.
"""

from django.db import migrations


OLD_TABLES = [
    "buildmeta_project_v2",
    "buildmeta_repository_v2",
    "buildmeta_build_unit_v2",
    "buildmeta_build_unit_definition_v2",
    "buildmeta_build_version_v2",
    "buildmeta_build_execution_v2",
    "buildmeta_execution_artifact_v2",
    "buildmeta_static_analysis_result_v2",
    "buildmeta_deployment_target_v2",
    "buildmeta_deployment_execution_v2",
    "buildmeta_system_status_snapshot_v2",
    "buildmeta_audit_event_v2",
    "buildmeta_bamboo_build_unit_v2",
    "buildmeta_bamboo_build_info_v2",
    "buildmeta_bamboo_publish_execution_v2",
    "buildmeta_jenkins_build_unit_v2",
    "buildmeta_jenkins_node_snapshot_v2",
    "buildmeta_jenkins_queue_item_snapshot_v2",
]


def drop_old_tables(apps, schema_editor):
    """Drop all old _v2 tables if they exist."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for table in OLD_TABLES:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"Dropped table: {table}")
            except Exception as e:
                print(f"Error dropping {table}: {e}")


def recreate_tables(apps, schema_editor):
    """Recreate tables using current model definitions.
    
    This is done by calling makemigrations after this migration
    has been applied. The models will create tables with the new names.
    """
    pass  # Models will create tables on next makemigrations


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0012_buildunit_v2_models"),
    ]

    operations = [
        migrations.RunPython(drop_old_tables, recreate_tables),
    ]
