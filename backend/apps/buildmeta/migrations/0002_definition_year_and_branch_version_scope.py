from __future__ import annotations

from django.db import migrations, models


def populate_definition_year(apps, schema_editor) -> None:
    BuildPlanDefinition = apps.get_model("buildmeta", "BuildPlanDefinition")
    for definition in BuildPlanDefinition.objects.all():
        year = str(definition.definition_json.get("year", "") or "")
        BuildPlanDefinition.objects.filter(pk=definition.pk).update(year=year)


class Migration(migrations.Migration):

    dependencies = [
        ("buildmeta", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="buildplandefinition",
            name="year",
            field=models.CharField(default="", max_length=16),
            preserve_default=False,
        ),
        migrations.RunPython(populate_definition_year, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name="buildversion",
            name="ix_build_version_commit",
        ),
        migrations.RemoveConstraint(
            model_name="buildversion",
            name="uq_build_version_commit",
        ),
        migrations.AddIndex(
            model_name="buildversion",
            index=models.Index(
                fields=["build_plan", "branch_kind", "commit_hash"],
                name="ix_build_version_branch_commit",
            ),
        ),
        migrations.AddConstraint(
            model_name="buildversion",
            constraint=models.UniqueConstraint(
                fields=("build_plan", "branch_kind", "commit_hash"),
                name="uq_build_version_branch_commit",
            ),
        ),
    ]
