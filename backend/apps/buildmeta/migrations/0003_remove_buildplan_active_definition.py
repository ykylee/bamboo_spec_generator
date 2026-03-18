from __future__ import annotations

from django.db import migrations


def migrate_active_definition_flag(apps, schema_editor) -> None:
    BuildPlan = apps.get_model("buildmeta", "BuildPlan")
    BuildPlanDefinition = apps.get_model("buildmeta", "BuildPlanDefinition")

    for plan in BuildPlan.objects.exclude(active_definition_id__isnull=True):
        BuildPlanDefinition.objects.filter(build_plan_id=plan.id, is_active=True).update(is_active=False)
        BuildPlanDefinition.objects.filter(pk=plan.active_definition_id).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0002_definition_year_and_branch_version_scope"),
    ]

    operations = [
        migrations.RunPython(migrate_active_definition_flag, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="buildplan",
            name="active_definition",
        ),
    ]
